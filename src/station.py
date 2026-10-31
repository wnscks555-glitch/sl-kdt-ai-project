"""모의 설비, PLC 스캔, 판정 PC를 한 주기씩 교대로 돌려 소프트웨어 간 Modbus TCP를 시연한다."""

import argparse
import csv
from dataclasses import dataclass
from decimal import Decimal
import json
from pathlib import Path

from src.generate import Generator, load_setup
from src.modbus import (
    HEARTBEAT_REGISTER, JUDGE_REGISTER, READ_INPUT, ModbusClient, ModbusException, ModbusResponseError, ModbusServer,
    ModbusTimeout, Table, restore_value,
)
from src.plc import (
    INPUTS, JUDGE_FAIL, JUDGE_PASS, MEASURE, OUTPUTS, REG_HEARTBEAT, REG_MEASURE_ID, REG_STATE,
    REG_VALUE_HIGH, REG_VALUE_LOW, STATE_NAMES, CHECK, CLAMP, WAIT_JUDGE, Plc, Timing,
)
from src.recipe import is_measured
from src.recipe_rules import judge_value


TIMEOUT_KEYS = ("check_scans", "clamp_scans", "measure_scans", "judge_scans", "unclamp_scans", "discharge_scans")
DELAY_KEYS = ("arrive", "seat", "clamp_close", "measure", "clamp_open", "discharge")
INTEGER_KEYS = ("heartbeat_scans", "plc_stale_cycles", "post_alarm_cycles", "max_cycles")
TOP_KEYS = ("generator", "inspection", "timeouts", "delays") + INTEGER_KEYS
INJECTED_PRODUCT = 5
SOCKET_TIMEOUT = 1.0
RECORD_COLUMNS = ("cycle", "state", "alarm", "outputs", "processed", "events", "value")
MODBUS_COLUMNS = ("cycle", "order", "direction", "function", "hex")


class StationError(ValueError):
    """설정 문제를 위치와 함께 모아서 보고한다. 종료 코드는 3이다."""

    def __init__(self, errors):
        super().__init__("\n".join(errors))
        self.errors = errors


@dataclass(frozen=True)
class Scenario:
    state: int = -1
    signal: str = ""
    pc: str = ""


SCENARIOS = {
    "normal": Scenario(),
    "seat_ng": Scenario(CHECK, signal="seated"),
    "clamp_stuck": Scenario(CLAMP, signal="clamp_closed"),
    "judge_lost": Scenario(WAIT_JUDGE, pc="no_judge"),
    "pc_silent": Scenario(MEASURE, pc="no_heartbeat"),
    "disconnect": Scenario(MEASURE, pc="close"),
    "guard_open": Scenario(MEASURE, signal="guard_closed"),
    "stale_judge": Scenario(WAIT_JUDGE, pc="stale"),
}


@dataclass(frozen=True)
class Station:
    generator: Path
    inspection: str
    timing: Timing
    plc_stale_cycles: int
    delays: dict
    post_alarm_cycles: int
    max_cycles: int


def _check_keys(data, allowed, location, errors):
    if not isinstance(data, dict):
        errors.append(location + ": 객체여야 함")
        return False
    errors.extend(location + "." + key + ": 없는 키" for key in allowed if key not in data)
    errors.extend(location + "." + key + ": 허용 밖 키" for key in data if key not in allowed)
    return True


def _check_integer(value, location, errors):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        errors.append(location + ": 1 이상의 정수여야 함")


def load_station(path):
    """설정을 읽어 검증한다. 문제는 위치와 함께 모아서 보고한다."""
    path = Path(path)
    try:
        data = json.loads(path.read_bytes().decode("utf-8-sig"))
    except ValueError as error:
        raise StationError(["$: JSON 오류: " + str(error)]) from error
    errors = []
    _check_keys(data, TOP_KEYS, "$", errors)
    if errors:
        raise StationError(errors)
    for key in ("generator", "inspection"):
        if not isinstance(data[key], str) or not data[key].strip():
            errors.append("$." + key + ": 비어 있지 않은 문자열이어야 함")
    for key in INTEGER_KEYS:
        _check_integer(data[key], "$." + key, errors)
    for name, keys in (("timeouts", TIMEOUT_KEYS), ("delays", DELAY_KEYS)):
        location = "$." + name
        if _check_keys(data[name], keys, location, errors):
            for key in keys:
                if key in data[name]:
                    _check_integer(data[name][key], location + "." + key, errors)
    if errors:
        raise StationError(errors)
    return Station(path.parent / data["generator"], data["inspection"],
                   Timing(data["heartbeat_scans"], dict(data["timeouts"])), data["plc_stale_cycles"],
                   dict(data["delays"]), data["post_alarm_cycles"], data["max_cycles"])


def two_sided_item(models, inspection):
    """모든 모델에서 수치가 같은 양측 규격의 검사를 돌려준다. `7`과 `7.000`은 같은 규격이다."""
    items = [item for model in models.values() for item in model.inspections if item.id == inspection]
    if not items or any(item.lsl is None or item.usl is None for item in items):
        raise ValueError(inspection + ": 모든 모델에서 양측 규격이어야 함")
    if len({(Decimal(item.lsl), Decimal(item.usl)) for item in items}) != 1:
        raise ValueError(inspection + ": 모든 모델에서 규격이 같아야 함")
    return items[0]


def load_values(station, seed, products):
    """측정 설정의 정상 사건에서 LEAK 최초 측정 value를 제품 순서대로 가져온다."""
    config, _, recipe, book = load_setup(station.generator)
    if "process_cpk" not in config or not is_measured(recipe.models):
        raise ValueError("generator는 측정 설정이어야 함")
    item = two_sided_item(recipe.models, station.inspection)
    first = {}
    for row in Generator(seed, config, recipe.models, book).normal_events(products):
        if row["inspection"] == station.inspection and row["value"]:
            first.setdefault(row["product_id"], row["value"])
    if len(first) != products:
        raise ValueError(station.inspection + ": 측정값이 없는 제품이 있음")
    # 문자열로 정렬하면 GEN_10000이 GEN_1001 앞에 온다.
    ordered = sorted(first, key=lambda product: int(product.rpartition("_")[2]))
    return [first[product] for product in ordered], item


class Plant:
    """모의 설비다. 직전 스캔의 출력과 자기 상태만 보고 입력 비트를 갱신한다."""

    def __init__(self, table, delays, values):
        self.table = table
        self.delays = delays
        self.values = values
        self.product = 0
        self.inputs = {name: False for name in INPUTS}
        self.inputs["clamp_open"] = self.inputs["guard_closed"] = True
        self.raw = ""
        self.timers = {}
        self.forced = {}
        self.feed_hold = False
        self._publish()

    def _due(self, name, trigger, cycle):
        """트리거를 처음 본 주기를 기억하고, 지연이 지나면 참을 돌려준다. 트리거가 꺼지면 취소한다."""
        if not trigger:
            self.timers.pop(name, None)
            return False
        due = self.timers.setdefault(name, cycle + self.delays[name])
        if cycle >= due:
            del self.timers[name]
            return True
        return False

    def _publish(self):
        merged = {**self.inputs, **self.forced}
        with self.table.lock:
            self.table.discrete[:len(INPUTS)] = [merged[name] for name in INPUTS]

    def update(self, cycle, outputs):
        """트리거는 갱신 전 값으로 본다. 주입은 정상 갱신 뒤에 덮어쓴다."""
        now = dict(self.inputs)
        changes = {}
        if self._due("arrive", not now["part_present"] and self.product < len(self.values) and not self.feed_hold,
                     cycle):
            changes["part_present"] = True
        if self._due("seat", now["part_present"] and not now["seated"], cycle):
            changes["seated"] = changes["direction_ok"] = True
        if outputs["clamp_cmd"]:
            changes["clamp_open"] = False
        elif not now["clamp_open"]:
            changes["clamp_closed"] = False
        if self._due("clamp_close", outputs["clamp_cmd"] and not now["clamp_closed"], cycle):
            changes["clamp_closed"] = True
        if self._due("clamp_open", not outputs["clamp_cmd"] and not now["clamp_open"], cycle):
            changes["clamp_open"] = True
        if not outputs["measure_cmd"]:
            changes["measure_done"] = False
            self.raw = ""
        if self._due("measure", outputs["measure_cmd"] and not now["measure_done"], cycle):
            changes["measure_done"] = True
            self.raw = self.values[self.product]
        if self._due("discharge", (outputs["gate_ok"] or outputs["gate_ng"]) and now["part_present"], cycle):
            changes["part_present"] = changes["seated"] = changes["direction_ok"] = False
            self.product += 1
        self.inputs.update(changes)
        self._publish()

    def remove_product(self):
        """작업자 제거다. 복귀 조건이 제품 부재이므로 복귀 완료까지 투입을 막는다. 값은 다시 쓰지 않는다."""
        self.inputs.update(part_present=False, seated=False, direction_ok=False)
        self.product += 1
        self.feed_hold = True
        self._publish()


class Pc:
    """판정 PC다. 요청마다 응답을 다 받은 뒤 다음으로 넘어간다."""

    def __init__(self, client, item, stale_cycles):
        self.client = client
        self.item = item
        self.stale_cycles = stale_cycles
        self.heartbeat = 0
        self.judged_id = 0
        self.plc_heartbeat = 0
        self.plc_change = 0
        self.stale_noted = False
        self.fault = ""
        self.events = []

    def _exchange(self, cycle):
        if self.fault != "no_heartbeat":
            self.heartbeat = (self.heartbeat + 1) % 65536
            self.client.write_register(HEARTBEAT_REGISTER, self.heartbeat)
        registers = self.client.read_registers(READ_INPUT, 0, 7)
        if registers[REG_HEARTBEAT] != self.plc_heartbeat:
            self.plc_heartbeat = registers[REG_HEARTBEAT]
            self.plc_change = cycle
            self.stale_noted = False
        if cycle - self.plc_change > self.stale_cycles:
            if not self.stale_noted:
                self.stale_noted = True
                self.events.append("PLC 무응답")
            return
        measure_id = registers[REG_MEASURE_ID]
        if registers[REG_STATE] != WAIT_JUDGE or measure_id == self.judged_id or self.fault == "no_judge":
            return
        self.judged_id = measure_id
        value = restore_value(registers[REG_VALUE_HIGH], registers[REG_VALUE_LOW])
        verdict = JUDGE_PASS if judge_value(value, self.item) == "PASS" else JUDGE_FAIL
        self.client.write_registers(JUDGE_REGISTER, [measure_id - 1 if self.fault == "stale" else measure_id, verdict])

    def cycle(self, cycle):
        self.events = []
        if self.fault == "close":
            self.client.close()
        if self.client.closed:
            return
        try:
            self._exchange(cycle)
        except (ModbusResponseError, ModbusException) as error:
            self.events.append("통신 실패: " + str(error))


@dataclass
class Outcome:
    processed: int = 0
    ok_count: int = 0
    ng_count: int = 0
    alarm: int = 0
    heartbeat_scan: int = 0
    records: list = None
    frames: list = None
    target_clamped: bool = False


def _bits(outputs):
    return "".join("1" if outputs[name] else "0" for name in OUTPUTS)


def run_scenario(station, name, values, item, connect=ModbusClient):
    """시나리오 하나를 끝까지 돌린다. 기록은 메모리에 모아 돌려준다."""
    scenario = SCENARIOS[name]
    table = Table()
    plc = Plc(table, station.timing)
    plant = Plant(table, station.delays, values)
    server = ModbusServer(table)
    records, frames = [], []
    cycle = 0

    def log(direction, function, text):
        frames.append({"cycle": cycle, "order": len(frames) + 1, "direction": direction,
                       "function": "%02X" % function, "hex": text})

    client = connect(server.port, SOCKET_TIMEOUT, log)
    pc = Pc(client, item, station.plc_stale_cycles)
    injected = False
    arrived = clamp_on = False
    alarm_cycle = None
    try:
        while plc.processed < len(values) and (alarm_cycle is None or cycle - alarm_cycle < station.post_alarm_cycles):
            if cycle >= station.max_cycles:
                raise ValueError("max_cycles 초과")
            cycle += 1
            plant.update(cycle, plc.outputs)
            plc.scan(plant.raw)
            target = plc.processed + 1 == INJECTED_PRODUCT
            arrived = arrived or (target and plant.inputs["part_present"])
            clamp_on = clamp_on or (arrived and plc.outputs["clamp_cmd"])
            if not injected and target and plc.state == scenario.state:
                injected = True
                pc.fault = scenario.pc
                if scenario.signal:
                    plant.forced[scenario.signal] = False
            events = list(plc.events)
            pc.cycle(cycle)
            events.extend(pc.events)
            records.append({"cycle": cycle, "state": STATE_NAMES[plc.state], "alarm": plc.alarm,
                            "outputs": _bits(plc.outputs), "processed": plc.processed, "events": "; ".join(events),
                            "value": plant.raw})
            if plc.alarm and alarm_cycle is None:
                alarm_cycle = cycle
    finally:
        client.close()
        server.close()
    return Outcome(plc.processed, plc.ok_count, plc.ng_count, plc.alarm, plc.heartbeat_scan, records, frames, clamp_on)


def _write_csv(path, columns, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def run(path, seed, products, names):
    """시나리오를 돌리고, 전부 끝까지 성공했을 때만 보고서를 쓴다."""
    if products < 1:
        raise ValueError("products는 양의 정수여야 함")
    station = load_station(path)
    values, item = load_values(station, seed, products)
    outcomes = {name: run_scenario(station, name, values, item) for name in names}
    directory = Path("reports")
    directory.mkdir(exist_ok=True)
    written = []
    for name, outcome in outcomes.items():
        stem = "plc_station_" + name
        _write_csv(directory / (stem + ".csv"), RECORD_COLUMNS, outcome.records)
        _write_csv(directory / (stem + "_modbus.csv"), MODBUS_COLUMNS, outcome.frames)
        written.extend((directory / (stem + ".csv"), directory / (stem + "_modbus.csv")))
    return outcomes, written


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("station", type=Path)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--products", type=int, default=20)
    parser.add_argument("--scenario", default="normal", help="시나리오 이름 또는 all")
    args = parser.parse_args(argv)
    names = list(SCENARIOS) if args.scenario == "all" else [args.scenario]
    if any(name not in SCENARIOS for name in names):
        parser.exit(2, "오류: 없는 시나리오 " + args.scenario + "\n")
    try:
        outcomes, written = run(args.station, args.seed, args.products, names)
    except StationError as error:
        parser.exit(3, "스테이션 입력 오류:\n" + "\n".join(error.errors) + "\n")
    except ModbusTimeout as error:
        parser.exit(2, "오류: " + str(error) + ". 결과를 믿을 수 없어 보고서를 쓰지 않음\n")
    except (OSError, UnicodeError, csv.Error, ValueError, KeyError) as error:
        parser.exit(2, "오류: " + str(error) + "\n")
    print("Python 기반 PLC 스캔 모의. 실제 PLC·설비가 아니다.")
    print("scenario | processed | ok | ng | alarm | last_pc_heartbeat_scan")
    for name, outcome in outcomes.items():
        print(" | ".join(map(str, (name, outcome.processed, outcome.ok_count, outcome.ng_count, outcome.alarm,
                                   outcome.heartbeat_scan))))
    print("저장 파일: " + ", ".join(path.as_posix() for path in written))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

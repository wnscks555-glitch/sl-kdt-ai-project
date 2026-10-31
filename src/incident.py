"""합성 평균 이동 고장의 경보–정지–격리 과정을 잇는다. 한 PC 안의 소프트웨어 모의이고 사고 대응 실무가 아니다."""

import argparse
import csv
from dataclasses import dataclass
from fractions import Fraction
import json
from pathlib import Path
import random

from src import anomaly, spc
from src.anomaly import _integer, _keys, _number, _write_csv, show
from src.modbus import (
    PC_STOP_COIL, READ_COILS, READ_DISCRETE, READ_INPUT, HEARTBEAT_REGISTER, JUDGE_REGISTER, RELEASE_COIL, RESET_COIL,
    ModbusClient, ModbusException, ModbusResponseError, ModbusServer, ModbusTimeout, Table, restore_value,
)
from src.msa import parse_seeds
from src.plc import (
    ALARM_PC_STOP, IDLE, INPUTS, JUDGE_FAIL, JUDGE_PASS, REG_ALARM, REG_MEASURE_ID, REG_STATE, REG_VALUE_HIGH,
    REG_VALUE_LOW, WAIT_JUDGE, Plc,
)
from src.recipe_rules import judge_value
from src.station import MODBUS_COLUMNS, SOCKET_TIMEOUT, Plant, StationError, load_station


NOTICE = ("합성 고장 시나리오의 경보, 정지, 격리 추적이다. 한 PC 안의 소프트웨어 모의이고, 실제 라인 정지나 사고 대응 기록이 "
          "아니다. 수리하면 이동이 사라진다는 것은 가정이다.")
TOP_KEYS = ("station", "spc", "spc_report", "pfmea", "products", "onset_product", "shift_sigma", "repair_cycles",
            "max_cycles", "story_seed", "summary_seeds", "methods", "scopes", "pfmea_links")
METHODS = ("rule_3_2", "ewma_chart", "cusum")
SCOPES = ("last_20", "last_50", "change_point")
SCOPE_SPANS = {"last_20": 20, "last_50": 50}
REPAIR_OFFSET = 1000000
MAX_SEED = 2 ** 31 - 1 - REPAIR_OFFSET
FRAME_WINDOW = 20
RUN, WAIT_ALARM, WAIT_CLAMP, REPAIR, RESET, WAIT_IDLE = range(6)
TIMELINE_COLUMNS = ("method", "incident_id", "cycle", "product", "event", "detail")
COMPARE_COLUMNS = ("section", "method", "scope", "name", "value", "stops", "false_stops", "detection", "a", "delay",
                   "suspect_measured", "suspect_passed", "suspect_failed", "suspect_aborted", "captured",
                   "captured_parts", "scope_start", "scope_size", "over_scope", "seeds")
SUSPECT_COLUMNS = ("method", "incident_id", "scope", "product", "value", "fault_value", "disposition")
FRAME_COLUMNS = ("incident_id",) + MODBUS_COLUMNS


class IncidentError(ValueError):
    """설정 문제를 위치와 함께 모아서 보고한다. 종료 코드는 3이다."""

    def __init__(self, errors):
        super().__init__("\n".join(errors))
        self.errors = errors


@dataclass(frozen=True)
class Settings:
    station: Path
    spc: Path
    spc_report: Path
    pfmea: Path
    products: int
    onset_product: int
    shift_sigma: float
    repair_cycles: int
    max_cycles: int
    story_seed: int
    summary_seeds: range
    methods: tuple
    scopes: tuple
    pfmea_links: tuple


def _check_list(data, key, allowed, errors):
    values = data[key]
    valid = isinstance(values, list) and values and all(isinstance(value, str) for value in values)
    if not valid or len(set(values)) != len(values):
        errors.append("$." + key + ": 비어 있지 않고 중복 없는 문자열 목록이어야 함")
    elif allowed and any(value not in allowed for value in values):
        errors.append("$." + key + ": 없는 ID")


def _check(data):
    errors = []
    for key in ("station", "spc", "spc_report", "pfmea"):
        if not isinstance(data[key], str) or not data[key].strip():
            errors.append("$." + key + ": 비어 있지 않은 문자열이어야 함")
    for key, high in (("products", 100000), ("repair_cycles", 100000), ("max_cycles", 10000000)):
        if not _integer(data[key]) or not 1 <= data[key] <= high:
            errors.append("$.%s: 1–%d의 정수여야 함" % (key, high))
    products = data["products"] if _integer(data["products"]) else 0
    if not _integer(data["onset_product"]) or not 1 <= data["onset_product"] <= products:
        errors.append("$.onset_product: 1 이상 products 이하여야 함")
    if not _number(data["shift_sigma"]) or not 0 < data["shift_sigma"] <= 100:
        errors.append("$.shift_sigma: 0 초과 100 이하여야 함")
    if not _integer(data["story_seed"]) or not 0 <= data["story_seed"] <= MAX_SEED:
        errors.append("$.story_seed: 범위 밖")
    seeds = parse_seeds(data["summary_seeds"])
    if seeds is None or seeds.stop - 1 > MAX_SEED:
        errors.append("$.summary_seeds: `시작-끝` 형식의 범위여야 함")
    _check_list(data, "methods", METHODS, errors)
    _check_list(data, "scopes", SCOPES, errors)
    _check_list(data, "pfmea_links", (), errors)
    if not errors and "change_point" in data["scopes"] and "cusum" not in data["methods"]:
        errors.append("$.scopes: change_point에는 cusum이 있어야 함")
    return errors


def load_settings(path):
    path = Path(path)
    try:
        data = json.loads(path.read_bytes().decode("utf-8-sig"))
    except ValueError as error:
        raise IncidentError(["$: JSON 오류: " + str(error)]) from error
    errors = []
    _keys(data, TOP_KEYS, "$", errors)
    if errors:
        raise IncidentError(errors)
    errors = _check(data)
    if errors:
        raise IncidentError(errors)
    return Settings(path.parent / data["station"], path.parent / data["spc"], path.parent / data["spc_report"],
                    path.parent / data["pfmea"], data["products"], data["onset_product"], data["shift_sigma"],
                    data["repair_cycles"], data["max_cycles"], data["story_seed"], parse_seeds(data["summary_seeds"]),
                    tuple(data["methods"]), tuple(data["scopes"]), tuple(data["pfmea_links"]))


def check_seeds(settings, base):
    """사건 평가에 한계 추정과 11·13단계 평가 자료를 다시 쓰지 않는다."""
    used = set()
    for seeds in base.splits.values():
        used.update(seeds)
    errors = []
    if settings.story_seed in used:
        errors.append("$.story_seed: 11·13단계 시드와 겹침")
    if used & set(settings.summary_seeds):
        errors.append("$.summary_seeds: 11·13단계 시드와 겹침")
    if errors:
        raise IncidentError(errors)


def read_pfmea(path, links):
    with path.open(encoding="utf-8-sig", newline="") as source:
        table = {row["id"]: row for row in csv.DictReader(source)}
    missing = [link for link in links if link not in table]
    if missing:
        raise IncidentError(["$.pfmea_links: 표에 없는 ID " + ", ".join(missing)])
    return {link: table[link] for link in links}


def check_generator(station, base):
    """두 경로로 얻은 공정이 같아야 한다. 다르면 사건과 한계가 다른 자료를 보게 된다."""
    if station.generator.resolve() != base.generator.resolve() or station.inspection != base.inspection:
        raise ValueError("station과 anomaly의 생성 설정이 다름")
    process = anomaly.load_process(base)
    if anomaly.load_process(station) != process:
        raise ValueError("station과 anomaly의 공정이 다름")
    return process


def checked_limits(settings, config, base, process):
    """보고서 한계를 쓰되, 현재 설정으로 다시 추정해 같을 때만 쓴다."""
    rows = spc.load_limits(settings.spc_report)
    seeds = [seed for index, seed in enumerate(base.splits["train"]) if anomaly.assignment(index, base.shifts) == 0]
    limits = spc.estimate(spc.training_series([anomaly.build_scenario(seed, 0, base, process) for seed in seeds],
                                              process))
    tuning = config.tuning
    expected = {"center": process.center, "sigma": process.sigma, "window": base.window,
                "ewma_lambda": tuning.ewma_lambda, "ewma_l": tuning.ewma_l, "cusum_k": tuning.cusum_k,
                "cusum_h": tuning.cusum_h}
    expected.update({name: getattr(limits, name) for name in ("xbarbar", "rbar", "sigma_hat", "ucl_x", "lcl_x",
                                                              "ucl_r", "sigma_xbar", "subgroups")})
    for name, value in expected.items():
        if rows.get(name) != repr(value):
            raise ValueError("spc_report: limits의 %s가 현재 설정과 다름" % name)
    return limits, tuning


def fault_series(seed, products, onset, shift, process):
    """`F[n]`이다. 번호 n은 0부터 세고 n ≥ o이면 고장 이동을 쓴다."""
    rng = random.Random(seed)
    return [anomaly.measure(rng, process, shift if product >= onset else 0) for product in range(products)]


def repair_series(seed, products, process):
    """`N[n]`이다. 전체 번호에 미리 만들어 방법과 재가동 위치에 상관없이 같은 번호가 같은 값이다."""
    rng = random.Random(seed + REPAIR_OFFSET)
    return [anomaly.measure(rng, process, 0) for _ in range(products)]


class Tracker:
    """구간 하나의 방법 상태다. 재가동마다 새로 만든다. `s`는 구간 안 위치다."""

    def __init__(self, method, first, chart):
        self.method = method
        self.first = first
        self.start = chart["start"]
        self.process = chart["process"]
        self.s = -1
        self.fails = []
        self.chart = None
        if method == "ewma_chart":
            self.chart = spc.Ewma(chart["limits"], chart["tuning"])
        elif method == "cusum":
            self.chart = spc.Cusum(chart["limits"], chart["tuning"])

    def update(self, value):
        self.s += 1
        if self.chart is None:
            self.fails.append(judge_value(value, self.process.item) == "FAIL")
            hit = sum(self.fails[-anomaly.RULE_WINDOW:]) >= anomaly.RULE_FAILS
        else:
            hit = self.chart.update((float(value) - self.process.center) / self.process.sigma)
        return hit and self.s >= self.start

    def evidence(self, value):
        if self.method == "rule_3_2":
            recent = ",".join("FAIL" if fail else "PASS" for fail in self.fails[-anomaly.RULE_WINDOW:])
            return "value=%s 최근 3건 %s" % (value, recent)
        if self.method == "ewma_chart":
            return "value=%s z=%.4f limit=%.4f" % (value, self.chart.value, self.chart.limit)
        return "value=%s C+=%.4f C-=%.4f bound=%.4f" % (value, self.chart.plus[-1], self.chart.minus[-1],
                                                        self.chart.bound)

    def change_point(self):
        return self.first + self.chart.change_point() if self.method == "cusum" else None


@dataclass(frozen=True)
class Stop:
    number: int
    product: int
    change_point: object
    evidence: str


class Flow:
    """제품이 측정되는 순서의 공통 규칙이다. 소켓 실행과 메모리 실행이 똑같이 쓴다."""

    def __init__(self, method, fault, normal, onset, item, make_tracker):
        self.method = method
        self.fault = fault
        self.normal = normal
        self.onset = onset
        self.item = item
        self.make_tracker = make_tracker
        self.tracker = make_tracker(method, 0)
        self.repaired = False
        self.stops = []
        self.values = {}
        self.shifted = {}
        self.disposition = {}

    def value(self, product):
        return (self.normal if self.repaired else self.fault)[product]

    def observe(self, product, value):
        """값 하나를 처리한다. 경보면 정지 위치를 고정하고 참을 돌려준다. 수리는 고장 뒤 첫 정지에서만 일어난다."""
        self.values[product] = value
        self.shifted[product] = product >= self.onset and not self.repaired
        if not self.tracker.update(value):
            self.disposition[product] = "OK" if judge_value(value, self.item) == "PASS" else "NG"
            return False
        self.stops.append(Stop(len(self.stops) + 1, product, self.tracker.change_point(),
                               self.tracker.evidence(value)))
        self.disposition[product] = "aborted"
        if product >= self.onset:
            self.repaired = True
        self.tracker = self.make_tracker(self.method, product + 1)
        return True

    def count(self, name):
        return sum(1 for value in self.disposition.values() if value == name)


def run_memory(flow, products):
    """설비 주기 없이 같은 규칙을 돌린다."""
    for product in range(products):
        flow.observe(product, flow.value(product))
    return flow


class Live:
    """모의 설비가 읽는 측정값이다. 수리 여부에 따라 그때의 값을 준다."""

    def __init__(self, flow, products):
        self.flow = flow
        self.products = products

    def __len__(self):
        return self.products

    def __getitem__(self, product):
        return self.flow.value(product)


class StoryPc:
    """판정 PC에 경보·복구 순서를 더한다. 요청마다 응답을 다 받은 뒤 다음으로 넘어간다."""

    def __init__(self, client, plant, flow, repair_cycles, frames):
        self.client = client
        self.plant = plant
        self.flow = flow
        self.repair_cycles = repair_cycles
        self.frames = frames
        self.heartbeat = 0
        self.judged_id = 0
        self.phase = RUN
        self.repair_until = 0
        self.cycle_number = 0
        self.incident = ""
        self.events = []
        self.fault_seen = False
        self.stop_product = 0
        self.stop_cycles = {}

    def _event(self, event, product, detail="", incident=None):
        self.events.append({"method": self.flow.method, "incident_id": self.incident if incident is None else incident,
                            "cycle": self.cycle_number, "product": product, "event": event, "detail": detail})

    def _bit(self, name):
        return self.client.read_bits(READ_DISCRETE, 0, len(INPUTS))[INPUTS.index(name)]

    def _judge(self, registers):
        measure_id = registers[REG_MEASURE_ID]
        self.judged_id = measure_id
        product = measure_id - 1
        if product != self.plant.product:
            raise ValueError("제품 번호와 측정 ID가 어긋남")
        value = restore_value(registers[REG_VALUE_HIGH], registers[REG_VALUE_LOW])
        if product >= self.flow.onset and not self.flow.repaired and not self.fault_seen:
            self.fault_seen = True
            self._event("fault_start", product, "value=" + value, "")
        if not self.flow.observe(product, value):
            verdict = JUDGE_PASS if self.flow.disposition[product] == "OK" else JUDGE_FAIL
            self.client.write_registers(JUDGE_REGISTER, [measure_id, verdict])
            return
        stop = self.flow.stops[-1]
        self.incident = "%s-%d" % (self.flow.method, stop.number)
        self.stop_product = product
        self._event("alarm", product, stop.evidence)
        order = len(self.frames) + 1
        self.client.write_coil(PC_STOP_COIL, True)
        self._event("pc_stop", product, "frame=%d" % order)
        self.stop_cycles[self.incident] = self.cycle_number
        self.phase = WAIT_ALARM

    def _recover(self, registers):
        product = self.stop_product
        if self.phase == WAIT_ALARM:
            if registers[REG_ALARM] == ALARM_PC_STOP:
                self._event("alarm_26", product)
                self.client.write_coil(RELEASE_COIL, True)
                self._event("release", product)
                self.phase = WAIT_CLAMP
        elif self.phase == WAIT_CLAMP:
            if self._bit("clamp_open"):
                self._event("clamp_open", product)
                self.plant.remove_product()
                self._event("remove", product)
                self.repair_until = self.cycle_number + self.repair_cycles
                self.phase = REPAIR
        elif self.phase == REPAIR:
            if self.cycle_number >= self.repair_until:
                self.client.write_coil(PC_STOP_COIL, False)
                self.client.write_coil(RELEASE_COIL, False)
                self.phase = RESET
        elif self.phase == RESET:
            bits = dict(zip(INPUTS, self.client.read_bits(READ_DISCRETE, 0, len(INPUTS))))
            stop = self.client.read_bits(READ_COILS, PC_STOP_COIL, 1)[0]
            self.client.write_coil(RESET_COIL, True)
            self._event("reset", product, "guard_closed=%d clamp_open=%d clamp_closed=%d part_present=%d pc_stop=%d"
                        % (bits["guard_closed"], bits["clamp_open"], bits["clamp_closed"], bits["part_present"], stop))
            self.phase = WAIT_IDLE
        elif registers[REG_STATE] == IDLE and registers[REG_ALARM] == 0:
            self.client.write_coil(RESET_COIL, False)
            self.plant.feed_hold = False
            self._event("restart", self.plant.product)
            self.incident = ""
            self.phase = RUN

    def cycle(self, cycle):
        self.cycle_number = cycle
        self.heartbeat = (self.heartbeat + 1) % 65536
        self.client.write_register(HEARTBEAT_REGISTER, self.heartbeat)
        registers = self.client.read_registers(READ_INPUT, 0, 7)
        if registers[REG_ALARM] not in (0, ALARM_PC_STOP):
            raise ValueError("알람 26이 아닌 알람: %d" % registers[REG_ALARM])
        if self.phase != RUN:
            self._recover(registers)
        elif registers[REG_STATE] == WAIT_JUDGE and registers[REG_MEASURE_ID] != self.judged_id:
            self._judge(registers)


@dataclass
class Story:
    flow: Flow
    events: list
    frames: list
    stop_cycles: dict
    ok_count: int
    ng_count: int
    cycles: int


def run_story(station, flow, products, repair_cycles, max_cycles, connect=ModbusClient, hook=None):
    """방법 하나의 사건을 실제 소켓으로 끝까지 돌린다. hook은 시험에서 설비 신호를 건드리는 자리다."""
    table = Table()
    plc = Plc(table, station.timing)
    plant = Plant(table, station.delays, Live(flow, products))
    server = ModbusServer(table)
    frames = []
    cycle = 0

    def log(direction, function, text):
        frames.append({"cycle": cycle, "order": len(frames) + 1, "direction": direction,
                       "function": "%02X" % function, "hex": text})

    client = connect(server.port, SOCKET_TIMEOUT, log)
    pc = StoryPc(client, plant, flow, repair_cycles, frames)
    try:
        while not (plant.product == products and plc.state == IDLE and pc.phase == RUN):
            if cycle >= max_cycles:
                raise ValueError("max_cycles 초과")
            cycle += 1
            if hook is not None:
                hook(cycle, plant)
            plant.update(cycle, plc.outputs)
            plc.scan(plant.raw)
            pc.cycle(cycle)
    finally:
        client.close()
        server.close()
    aborted = flow.count("aborted")
    if plc.ok_count + plc.ng_count + aborted != products or plc.ok_count != flow.count("OK"):
        raise ValueError("처리 수가 맞지 않음")
    pc.cycle_number = cycle
    pc._event("finish", products - 1, "OK=%d NG=%d aborted=%d" % (plc.ok_count, plc.ng_count, aborted), "")
    return Story(flow, pc.events, frames, pc.stop_cycles, plc.ok_count, plc.ng_count, cycle)


def true_stop(stops, onset):
    return next((stop for stop in stops if stop.product >= onset), None)


def scope_start(scope, a, change_point):
    """범위의 첫 제품 번호다. 해당 없는 조합은 None이다."""
    if scope == "change_point":
        return change_point
    return max(0, a - SCOPE_SPANS[scope] + 1)


def applies(method, scope):
    return scope != "change_point" or method == "cusum"


def detection_of(stops, onset):
    if true_stop(stops, onset) is not None:
        return "detected"
    return "early" if stops else "missed"


def suspect_counts(flow):
    names = {"OK": 0, "NG": 0, "aborted": 0}
    for product, shifted in flow.shifted.items():
        if shifted:
            names[flow.disposition[product]] += 1
    return names


@dataclass(frozen=True)
class ScopeResult:
    start: object
    captured: bool
    captured_parts: int
    size: object
    over: object


def scope_result(start, a, onset, shifted, disposition):
    """범위 하나의 지표다. 고장 뒤 정지가 없으면 빈 범위가 포착으로 읽히지 않게 거짓으로 둔다."""
    if a is None or start is None:
        return ScopeResult(None, False, 0, None, None)
    products = range(start, a + 1)
    parts = sum(1 for product in products if shifted.get(product) and disposition.get(product) == "OK")
    return ScopeResult(start, start <= onset, parts, len(products), sum(1 for product in products
                                                                        if not shifted.get(product)))


def run_scopes(flow, scopes):
    stop = true_stop(flow.stops, flow.onset)
    return {scope: scope_result(None if stop is None else scope_start(scope, stop.product, stop.change_point),
                                None if stop is None else stop.product, flow.onset, flow.shifted, flow.disposition)
            for scope in scopes}


@dataclass
class Summary:
    runs: int = 0
    detected: int = 0
    early: int = 0
    missed: int = 0
    delay: int = 0
    suspect_passed: int = 0
    stops: int = 0
    false_stops: int = 0


@dataclass
class ScopeSummary:
    captured_runs: int = 0
    captured_parts: int = 0
    ranged: int = 0
    size: int = 0
    over: int = 0


def add_run(summary, scopes, flow):
    stop = true_stop(flow.stops, flow.onset)
    summary.runs += 1
    detection = detection_of(flow.stops, flow.onset)
    setattr(summary, detection, getattr(summary, detection) + 1)
    if stop is not None:
        summary.delay += stop.product - flow.onset
    summary.suspect_passed += suspect_counts(flow)["OK"]
    summary.stops += len(flow.stops)
    summary.false_stops += len(flow.stops) - (stop is not None)
    for scope, result in run_scopes(flow, scopes).items():
        target = scopes[scope]
        target.captured_runs += result.captured
        target.captured_parts += result.captured_parts
        if result.size is not None:
            target.ranged += 1
            target.size += result.size
            target.over += result.over


def _ratio(top, bottom):
    return show(Fraction(top, bottom)) if bottom else ""


def summary_values(summary):
    return (("detected", summary.detected), ("early", summary.early), ("missed", summary.missed),
            ("mean_delay", _ratio(summary.delay, summary.detected)),
            ("mean_suspect_passed", _ratio(summary.suspect_passed, summary.runs)),
            ("mean_stops", _ratio(summary.stops, summary.runs)),
            ("mean_false_stops", _ratio(summary.false_stops, summary.runs)))


def scope_values(summary, target):
    return (("run_capture_rate", _ratio(target.captured_runs, summary.runs)),
            ("part_capture_rate", _ratio(target.captured_parts, summary.suspect_passed)),
            ("mean_scope_size", _ratio(target.size, target.ranged)),
            ("mean_over_scope", _ratio(target.over, target.ranged)))


def _compare(section, **fields):
    row = {column: "" for column in COMPARE_COLUMNS}
    row["section"] = section
    row.update(fields)
    return row


def _blank_none(value):
    return "" if value is None else value


def story_rows(story, scopes):
    flow = story.flow
    stop = true_stop(flow.stops, flow.onset)
    counts = suspect_counts(flow)
    rows = [_compare("story", method=flow.method, stops=len(flow.stops),
                     false_stops=len(flow.stops) - (stop is not None), detection=detection_of(flow.stops, flow.onset),
                     a="" if stop is None else stop.product, delay="" if stop is None else stop.product - flow.onset,
                     suspect_measured=sum(counts.values()), suspect_passed=counts["OK"], suspect_failed=counts["NG"],
                     suspect_aborted=counts["aborted"])]
    for scope, result in run_scopes(flow, scopes).items():
        if not applies(flow.method, scope):
            rows.append(_compare("story_scope", method=flow.method, scope=scope))
            continue
        rows.append(_compare("story_scope", method=flow.method, scope=scope, captured=int(result.captured),
                             captured_parts=result.captured_parts, scope_start=_blank_none(result.start),
                             scope_size=_blank_none(result.size), over_scope=_blank_none(result.over)))
    return rows


def summary_rows(method, summary, scope_table, seeds):
    rows = [_compare("summary", method=method, name=name, value=value, seeds=seeds)
            for name, value in summary_values(summary)]
    for scope, target in scope_table.items():
        rows.extend(_compare("summary_scope", method=method, scope=scope, name=name,
                             value=value if applies(method, scope) else "", seeds=seeds)
                    for name, value in scope_values(summary, target))
    return rows


def suspect_rows(story, scopes):
    flow = story.flow
    stop = true_stop(flow.stops, flow.onset)
    rows = []
    if stop is None:
        return rows
    incident = "%s-%d" % (flow.method, stop.number)
    for scope, result in run_scopes(flow, scopes).items():
        if result.start is None:
            continue
        rows.extend({"method": flow.method, "incident_id": incident, "scope": scope, "product": product,
                     "value": flow.values[product], "fault_value": int(bool(flow.shifted[product])),
                     "disposition": flow.disposition[product]} for product in range(result.start, stop.product + 1))
    return rows


def frame_rows(story):
    flow = story.flow
    stop = true_stop(flow.stops, flow.onset)
    if stop is None:
        return []
    incident = "%s-%d" % (flow.method, stop.number)
    center = story.stop_cycles[incident]
    return [dict(frame, incident_id=incident) for frame in story.frames
            if abs(frame["cycle"] - center) <= FRAME_WINDOW]


def pfmea_text(stories, links, scopes):
    lines = ["# 합성 사건과 PFMEA 행의 연결", "", NOTICE, "",
             "조치 판단은 쓰지 않고 S·O·D는 건드리지 않는다. 관측값은 `story` 실행의 값이다.", "",
             "| PFMEA | 고장 모드 | 사건 ID | 관측 |", "| --- | --- | --- | --- |"]
    for link, row in links.items():
        for story in stories:
            flow = story.flow
            stop = true_stop(flow.stops, flow.onset)
            counts = suspect_counts(flow)
            if stop is None:
                incident, seen = "", "%s: 고장 뒤 정지 없음, 의심 통과 %d" % (flow.method, counts["OK"])
            else:
                incident = "%s-%d" % (flow.method, stop.number)
                result = run_scopes(flow, scopes)
                capture = ", ".join("%s %d/%d" % (name, value.captured_parts, counts["OK"])
                                    for name, value in result.items() if value.start is not None)
                seen = "제품 %d에서 정지, 지연 %d, 의심 통과 %d, 포착 %s" % (stop.product, stop.product - flow.onset,
                                                                   counts["OK"], capture)
            lines.append("| %s | %s | %s | %s |" % (link, row["failure_mode"], incident, seen))
    return "\n".join(lines) + "\n"


def run(path):
    path = Path(path)
    settings = load_settings(path)
    station = load_station(settings.station)
    config = spc.load_settings(settings.spc)
    base = anomaly.load_settings(config.anomaly)
    check_seeds(settings, base)
    links = read_pfmea(settings.pfmea, settings.pfmea_links)
    process = check_generator(station, base)
    limits, tuning = checked_limits(settings, config, base, process)
    chart = {"limits": limits, "tuning": tuning, "process": process, "start": base.window - 1}
    onset = settings.onset_product - 1

    def make_tracker(method, first):
        return Tracker(method, first, chart)

    def flow_of(method, seed):
        return Flow(method, fault_series(seed, settings.products, onset, settings.shift_sigma, process),
                    repair_series(seed, settings.products, process), onset, process.item, make_tracker)

    stories = [run_story(station, flow_of(method, settings.story_seed), settings.products, settings.repair_cycles,
                         settings.max_cycles) for method in settings.methods]
    for story in stories:
        memory = run_memory(flow_of(story.flow.method, settings.story_seed), settings.products)
        if [stop.product for stop in memory.stops] != [stop.product for stop in story.flow.stops]:
            raise ValueError("소켓 실행과 메모리 실행의 정지 위치가 다름")
    compare = [_compare("notice", value=NOTICE)]
    for story in stories:
        compare.extend(story_rows(story, settings.scopes))
    seeds_text = "%d-%d" % (settings.summary_seeds.start, settings.summary_seeds.stop - 1)
    for method in settings.methods:
        summary, table = Summary(), {scope: ScopeSummary() for scope in settings.scopes}
        for seed in settings.summary_seeds:
            add_run(summary, table, run_memory(flow_of(method, seed), settings.products))
        compare.extend(summary_rows(method, summary, table, seeds_text))
    timeline = [event for story in stories for event in story.events]
    suspects = [row for story in stories for row in suspect_rows(story, settings.scopes)]
    frames = [row for story in stories if story.flow.method == "cusum" for row in frame_rows(story)]
    text = pfmea_text(stories, links, settings.scopes)
    directory = Path("reports")
    directory.mkdir(exist_ok=True)
    stem = path.stem
    written = [directory / (stem + suffix) for suffix in ("_timeline.csv", "_compare.csv", "_suspects.csv",
                                                          "_modbus.csv", "_pfmea.md")]
    _write_csv(written[0], TIMELINE_COLUMNS, timeline)
    _write_csv(written[1], COMPARE_COLUMNS, compare)
    _write_csv(written[2], SUSPECT_COLUMNS, suspects)
    _write_csv(written[3], FRAME_COLUMNS, frames)
    written[4].write_bytes(text.encode("utf-8"))
    return stories, compare, written


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    args = parser.parse_args(argv)
    try:
        stories, compare, written = run(args.config)
    except (IncidentError, StationError, spc.SpcError, anomaly.AnomalyError) as error:
        parser.exit(3, "사건 추적 입력 오류:\n" + "\n".join(error.errors) + "\n")
    except ModbusTimeout as error:
        parser.exit(2, "오류: " + str(error) + ". 결과를 믿을 수 없어 보고서를 쓰지 않음\n")
    except (OSError, UnicodeError, csv.Error, ValueError, KeyError, ModbusResponseError, ModbusException) as error:
        parser.exit(2, "오류: " + str(error) + "\n")
    print(NOTICE)
    print("method | stops | false_stops | detection | a | delay | suspect_passed")
    for row in compare:
        if row["section"] == "story":
            print(" | ".join(str(row[column]) for column in ("method", "stops", "false_stops", "detection", "a",
                                                             "delay", "suspect_passed")))
    print("저장 파일: " + ", ".join(item.as_posix() for item in written))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

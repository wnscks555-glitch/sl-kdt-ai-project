import copy
import csv
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from src import station as module
from src.modbus import ModbusClient, ModbusTimeout, Table, to_words
from src.plc import OUTPUTS
from src.recipe_rules import judge_value
from src.station import (
    Pc, Plant, SCENARIOS, StationError, load_station, load_values, run_scenario,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "recipes" / "plc_station.json"
RAW = json.loads(CONFIG.read_text(encoding="utf-8"))


def run_cli(*arguments, cwd):
    environment = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, "-m", "src.station", *map(str, arguments)], cwd=cwd, env=environment,
                          capture_output=True, text=True, encoding="utf-8")


def clamp_on(record):
    return record["outputs"][OUTPUTS.index("clamp_cmd")] == "1"


def measure_on(record):
    return record["outputs"][OUTPUTS.index("measure_cmd")] == "1"


def gate_on(record):
    return "1" in record["outputs"][2:4]


class ScenarioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.station = load_station(CONFIG)
        cls.values, cls.item = load_values(cls.station, 42, 20)
        cls.outcomes = {name: run_scenario(cls.station, name, cls.values, cls.item) for name in SCENARIOS}

    def test_t167_normal(self):
        outcome = self.outcomes["normal"]
        self.assertEqual((outcome.processed, outcome.alarm), (20, 0))

    def test_t167_alarms(self):
        expected = {"seat_ng": 11, "clamp_stuck": 12, "judge_lost": 14, "pc_silent": 21, "disconnect": 21,
                    "guard_open": 22, "stale_judge": 14}
        for name, code in expected.items():
            outcome = self.outcomes[name]
            self.assertEqual((outcome.processed, outcome.alarm), (4, code), name)

    def test_t167_seat_ng_never_clamps_the_fifth_product(self):
        self.assertFalse(self.outcomes["seat_ng"].target_clamped)
        self.assertTrue(any(clamp_on(record) for record in self.outcomes["seat_ng"].records))

    def test_t167_no_discharge_of_the_fifth_product(self):
        for name in ("judge_lost", "pc_silent", "disconnect"):
            fifth = [record for record in self.outcomes[name].records if record["processed"] == 4]
            self.assertFalse(any(gate_on(record) for record in fifth), name)

    def test_t167_guard_open_drops_measure_at_alarm(self):
        records = self.outcomes["guard_open"].records
        alarm = next(index for index, record in enumerate(records) if record["alarm"])
        self.assertTrue(measure_on(records[alarm - 1]))
        self.assertFalse(measure_on(records[alarm]))

    def test_t167_stale_judge_is_rejected_once(self):
        rejected = [record for record in self.outcomes["stale_judge"].records if "판정 거절" in record["events"]]
        self.assertEqual(len(rejected), 1)

    def test_t167_disconnect_records_close_and_stops_traffic(self):
        frames = self.outcomes["disconnect"].frames
        self.assertEqual(frames[-1]["direction"], "close")
        self.assertEqual(sum(frame["direction"] == "close" for frame in frames), 1)

    def test_t169_verdicts_match_judge_value(self):
        outcome = self.outcomes["normal"]
        verdicts = [judge_value(value, self.item) for value in self.values]
        self.assertEqual(outcome.ok_count, verdicts.count("PASS"))
        self.assertEqual(outcome.ng_count, verdicts.count("FAIL"))
        self.assertGreater(outcome.ng_count, 0)

    def test_t169_records_keep_generated_values(self):
        recorded = [record["value"] for record in self.outcomes["normal"].records if record["value"]]
        unique = [value for index, value in enumerate(recorded) if index == 0 or recorded[index - 1] != value]
        self.assertEqual(unique, self.values)

    def test_modbus_log_is_complete_frames_in_order(self):
        frames = self.outcomes["normal"].frames
        self.assertEqual([frame["order"] for frame in frames], list(range(1, len(frames) + 1)))
        for frame in frames:
            if frame["direction"] != "close":
                data = bytes.fromhex(frame["hex"])
                self.assertEqual(len(data), 6 + int.from_bytes(data[4:6], "big"))
        words = bytes.fromhex("%04x%04x" % to_words(self.values[0])).hex(" ")
        self.assertTrue(any(frame["function"] == "04" and words in frame["hex"] for frame in frames))
        judge = next(frame for frame in frames if frame["function"] == "10" and frame["direction"] == "request")
        self.assertEqual(judge["hex"].split()[7:], "10 00 01 00 02 04 00 01 00 01".split())


class ValueOrderTests(unittest.TestCase):
    def test_values_follow_product_number_past_9999(self):
        station = load_station(CONFIG)
        rows = [{"inspection": "LEAK", "product_id": name, "value": value}
                for name, value in (("GEN_10000", "3.000"), ("GEN_1001", "2.000"), ("GEN_0002", "1.000"))]
        with mock.patch.object(module.Generator, "normal_events", return_value=rows):
            self.assertEqual(load_values(station, 0, 3)[0], ["1.000", "2.000", "3.000"])


class PlantTests(unittest.TestCase):
    def setUp(self):
        self.table = Table()
        self.plant = Plant(self.table, RAW["delays"], ["10.000"])
        self.off = {name: False for name in OUTPUTS}

    def test_initial_inputs(self):
        self.assertEqual(self.table.discrete[:7], [False, False, False, False, True, True, False])

    def test_delay_counts_from_first_seen_cycle(self):
        self.plant.update(1, self.off)
        self.plant.update(2, self.off)
        self.assertFalse(self.plant.inputs["part_present"])
        self.plant.update(3, self.off)
        self.assertTrue(self.plant.inputs["part_present"])

    def test_clamp_releases_old_sensor_at_once(self):
        on = dict(self.off, clamp_cmd=True)
        self.plant.update(1, on)
        self.assertFalse(self.plant.inputs["clamp_open"])
        self.assertFalse(self.plant.inputs["clamp_closed"])
        self.plant.update(2, on)
        self.plant.update(3, on)
        self.assertFalse(self.plant.inputs["clamp_closed"])
        self.plant.update(4, on)
        self.assertTrue(self.plant.inputs["clamp_closed"])

    def test_dropped_trigger_cancels_the_timer(self):
        on = dict(self.off, measure_cmd=True)
        self.plant.update(1, on)
        self.plant.update(2, self.off)
        for cycle in range(3, 12):
            self.plant.update(cycle, self.off)
        self.assertFalse(self.plant.inputs["measure_done"])

    def test_forced_signal_overrides_plant(self):
        self.plant.forced["guard_closed"] = False
        self.plant.update(1, self.off)
        self.assertFalse(self.table.discrete[5])
        self.assertTrue(self.plant.inputs["guard_closed"])


class StubClient:
    closed = False

    def __init__(self, registers):
        self.registers = registers
        self.writes = []

    def write_register(self, address, value):
        self.writes.append(("heartbeat", value))

    def read_registers(self, function, start, count):
        return list(self.registers)

    def write_registers(self, start, values):
        self.writes.append(("judge", values))


class PcTests(unittest.TestCase):
    def setUp(self):
        self.item = load_values(load_station(CONFIG), 42, 1)[1]

    def test_judges_each_measure_id_once(self):
        client = StubClient([5, 0, 3, 0x0000, 0x280A, 1, 0])
        pc = Pc(client, self.item, 20)
        pc.cycle(1)
        client.registers[5] = 2
        pc.cycle(2)
        self.assertEqual([row for row in client.writes if row[0] == "judge"], [("judge", [3, 1])])

    def test_out_of_spec_value_writes_fail(self):
        pc_client = StubClient([5, 0, 1, 0x0000, 0x4E20, 1, 0])
        Pc(pc_client, self.item, 20).cycle(1)
        self.assertEqual(pc_client.writes[-1], ("judge", [1, 2]))

    def test_no_judge_before_wait_state(self):
        client = StubClient([4, 0, 1, 0, 0x280A, 1, 0])
        Pc(client, self.item, 20).cycle(1)
        self.assertFalse(any(row[0] == "judge" for row in client.writes))

    def test_stale_plc_heartbeat_blocks_judgement(self):
        client = StubClient([5, 0, 1, 0, 0x280A, 7, 0])
        pc = Pc(client, self.item, 20)
        pc.cycle(1)
        client.registers[2] = 2
        pc.cycle(22)
        self.assertEqual(pc.events, ["PLC 무응답"])
        pc.cycle(23)
        self.assertEqual(pc.events, [])
        self.assertEqual(sum(row[0] == "judge" for row in client.writes), 1)


class ConfigTests(unittest.TestCase):
    def write(self, folder, mutate):
        data = copy.deepcopy(RAW)
        mutate(data)
        data["generator"] = str(ROOT / "recipes" / "generator_measured.json")
        path = Path(folder) / "station.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_t170_config_errors_exit_3(self):
        cases = [
            lambda data: data["timeouts"].update(check_scans=-1),
            lambda data: data.pop("max_cycles"),
            lambda data: data.update(extra=1),
            lambda data: data["delays"].update(extra=1),
            lambda data: data["timeouts"].pop("clamp_scans"),
            lambda data: data.update(heartbeat_scans=True),
            lambda data: data.update(timeouts=[]),
        ]
        for mutate in cases:
            with tempfile.TemporaryDirectory() as folder:
                result = run_cli(self.write(folder, mutate), cwd=folder)
                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertFalse((Path(folder) / "reports").exists())

    def test_t170_run_errors_exit_2(self):
        with tempfile.TemporaryDirectory() as folder:
            data = copy.deepcopy(RAW)
            data["generator"] = str(ROOT / "recipes" / "generator.json")
            plain = Path(folder) / "plain.json"
            plain.write_text(json.dumps(data), encoding="utf-8")
            short = self.write(folder, lambda value: value.update(max_cycles=10))
            for arguments in ((plain,), (CONFIG, "--scenario", "nothing"), (short,), (CONFIG, "--products", 0)):
                result = run_cli(*arguments, cwd=folder)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertFalse((Path(folder) / "reports").exists())

    def test_t170_load_reports_location(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.write(folder, lambda data: data["delays"].update(seat=0))
            with self.assertRaises(StationError) as caught:
                load_station(path)
            self.assertIn("$.delays.seat", caught.exception.errors[0])

    def test_t170_silent_server_stops_the_run(self):
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        self.addCleanup(listener.close)
        port = listener.getsockname()[1]

        def silent(_, timeout, log):
            return ModbusClient(port, 0.05, log)

        station = load_station(CONFIG)
        values, item = load_values(station, 42, 2)
        with self.assertRaises(ModbusTimeout):
            run_scenario(station, "normal", values, item, connect=silent)

    def test_t170_timeout_exits_2_without_reports(self):
        with tempfile.TemporaryDirectory() as folder:
            before = Path.cwd()
            os.chdir(folder)
            try:
                with mock.patch.object(module, "run_scenario", side_effect=ModbusTimeout("x")):
                    with self.assertRaises(SystemExit) as caught, mock.patch("sys.stderr"):
                        module.main([str(CONFIG)])
            finally:
                os.chdir(before)
            self.assertEqual(caught.exception.code, 2)
            self.assertFalse((Path(folder) / "reports").exists())


class ReportTests(unittest.TestCase):
    def test_t168_reports_repeat_byte_for_byte(self):
        contents = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as folder:
                result = run_cli(CONFIG, "--scenario", "all", cwd=folder)
                self.assertEqual(result.returncode, 0, result.stderr)
                paths = sorted((Path(folder) / "reports").iterdir())
                self.assertEqual(len(paths), 16)
                contents.append({path.name: path.read_bytes() for path in paths})
        self.assertEqual(contents[0], contents[1])

    def test_t168_reports_hold_no_port_time_or_path(self):
        with tempfile.TemporaryDirectory() as folder:
            run_cli(CONFIG, "--scenario", "normal", cwd=folder)
            text = (Path(folder) / "reports" / "plc_station_normal.csv").read_text(encoding="utf-8-sig")
            rows = list(csv.DictReader(text.splitlines()))
            self.assertEqual(list(rows[0]), list(module.RECORD_COLUMNS))
            self.assertNotIn(str(ROOT), text)
            self.assertNotIn("127.0.0.1", text)

    def test_t171_existing_files_unchanged(self):
        tracked = [path for folder in ("recipes", "data", "reports") for path in (ROOT / folder).rglob("*")
                   if path.is_file() and not path.name.startswith("plc_station")]
        before = {path: path.read_bytes() for path in tracked}
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(run_cli(CONFIG, cwd=folder).returncode, 0)
        self.assertEqual({path: path.read_bytes() for path in tracked}, before)


if __name__ == "__main__":
    unittest.main()

import csv
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from src import anomaly
from src.incident import (
    COMPARE_COLUMNS, FRAME_COLUMNS, SUSPECT_COLUMNS, TIMELINE_COLUMNS, Flow, IncidentError, ScopeSummary, Stop, Summary,
    add_run, check_seeds, detection_of, fault_series, load_settings, read_pfmea, repair_series, run_memory, run_scopes, run_story,
    scope_result, scope_start, scope_values, suspect_counts, summary_values, true_stop,
)
from src.modbus import PC_STOP_COIL, READ_COILS, Table, handle_pdu
from src.plc import ALARM, ALARM_PC_STOP, CHECK, IDLE, WAIT_JUDGE
from src.spc import Cusum, Ewma, Limits, Tuning
from src.station import Plant, load_station
from src.incident import Tracker
from tests.test_plc import Rig


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "recipes" / "incident_lamp.json"
RAW = json.loads(CONFIG.read_text(encoding="utf-8"))
STATION = load_station(ROOT / "recipes" / "plc_station.json")
PROCESS = anomaly.load_process(STATION)
DELAYS = {"arrive": 2, "seat": 1, "clamp_close": 3, "measure": 5, "clamp_open": 3, "discharge": 2}
LIMITS = Limits(0.0, 2.326, 1.0, 1.342, -1.342, 4.917, 0.4474, 10)
TUNING = Tuning(0.2, 3, 0.5, 5)


class Forced:
    """정해진 제품에서 경보를 낸다."""

    def __init__(self, first, alarms):
        self.first = first
        self.product = first - 1
        self.alarms = alarms

    def update(self, _):
        self.product += 1
        return self.product in self.alarms

    def evidence(self, value):
        return "value=" + value

    def change_point(self):
        return self.first


def flow_of(alarms, products=12, onset=5, seed=3042):
    fault = fault_series(seed, products, onset, 1.5, PROCESS)
    normal = repair_series(seed, products, PROCESS)
    return Flow("cusum", fault, normal, onset, PROCESS.item, lambda method, first: Forced(first, alarms))


def real_flow(method, seed, products=60, onset=30):
    chart = {"limits": LIMITS, "tuning": TUNING, "process": PROCESS, "start": 9}
    return Flow(method, fault_series(seed, products, onset, 3.0, PROCESS), repair_series(seed, products, PROCESS),
                onset, PROCESS.item, lambda name, first: Tracker(name, first, chart))


def write_config(folder, **changes):
    data = dict(RAW, station=str(ROOT / "recipes" / "plc_station.json"), spc=str(ROOT / "recipes" / "spc_lamp.json"),
                spc_report=str(ROOT / "reports" / "spc_lamp_methods.csv"), pfmea=str(ROOT / "data" / "pfmea_lamp.csv"),
                products=40, onset_product=20, summary_seeds="3000-3002")
    data.update(changes)
    path = Path(folder) / "incident.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def run_cli(*arguments, cwd):
    environment = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, "-m", "src.incident", *map(str, arguments)], cwd=cwd, env=environment,
                          capture_output=True, text=True, encoding="utf-8")


class PlcAdditionTests(unittest.TestCase):
    def test_t221_check_alarm(self):
        rig = Rig()
        rig.reach(CHECK)
        rig.table.coils[PC_STOP_COIL] = True
        self.assertEqual(rig.scan(), ALARM)
        self.assertEqual(rig.plc.alarm, ALARM_PC_STOP)

    def test_t221_guard_wins(self):
        rig = Rig()
        rig.reach(CHECK)
        rig.table.coils[PC_STOP_COIL] = True
        rig.set(guard_closed=False)
        rig.scan()
        self.assertEqual(rig.plc.alarm, 22)

    def test_t221_keeps_existing_code(self):
        rig = Rig()
        rig.reach(CHECK)
        rig.set(guard_closed=False)
        rig.scan()
        rig.set(guard_closed=True)
        rig.table.coils[PC_STOP_COIL] = True
        rig.scan()
        self.assertEqual(rig.plc.alarm, 22)

    def test_t221_keeps_clamp_on_entry(self):
        rig = Rig()
        rig.reach(WAIT_JUDGE)
        self.assertTrue(rig.plc.outputs["clamp_cmd"])
        rig.table.coils[PC_STOP_COIL] = True
        rig.scan()
        self.assertEqual(rig.plc.alarm, ALARM_PC_STOP)
        self.assertTrue(rig.plc.outputs["clamp_cmd"])

    def test_t222_reset_needs_stop_off(self):
        rig = Rig()
        rig.reach(CHECK)
        rig.table.coils[PC_STOP_COIL] = True
        rig.scan()
        rig.set(part_present=False, seated=False, direction_ok=False)
        rig.table.coils[8] = True
        rig.scan()
        self.assertEqual(rig.plc.state, ALARM)
        rig.table.coils[8] = False
        rig.table.coils[PC_STOP_COIL] = False
        rig.scan()
        self.assertEqual(rig.plc.state, ALARM)
        rig.table.coils[8] = True
        before = rig.plc.measure_id
        self.assertEqual(rig.scan(), IDLE)
        self.assertEqual((rig.plc.alarm, rig.plc.measure_id), (0, before))

    def test_t223_fc05_echo(self):
        table = Table()
        request = bytes.fromhex("05 00 0a ff 00")
        self.assertEqual(handle_pdu(request, table), request)
        self.assertTrue(table.coils[PC_STOP_COIL])
        self.assertEqual(handle_pdu(bytes.fromhex("01 00 0a 00 01"), table), bytes.fromhex("01 01 01"))
        self.assertEqual(READ_COILS, 1)

    def test_t224_remove_product(self):
        plant = Plant(Table(), DELAYS, ["10.000", "10.100"])
        for cycle in range(1, 6):
            plant.update(cycle, {"clamp_cmd": False, "measure_cmd": False, "gate_ok": False, "gate_ng": False})
        self.assertTrue(plant.inputs["seated"])
        plant.remove_product()
        self.assertEqual((plant.inputs["part_present"], plant.inputs["seated"], plant.product), (False, False, 1))
        self.assertTrue(plant.feed_hold)
        idle = {"clamp_cmd": False, "measure_cmd": False, "gate_ok": False, "gate_ng": False}
        for cycle in range(6, 36):
            plant.update(cycle, idle)
            self.assertFalse(plant.inputs["part_present"])
        plant.feed_hold = False
        plant.update(36, idle)
        self.assertFalse(plant.inputs["part_present"])
        plant.update(38, idle)
        self.assertTrue(plant.inputs["part_present"])


class SeriesTests(unittest.TestCase):
    def test_t225_same_series_and_boundary(self):
        self.assertEqual(fault_series(5, 40, 20, 1.5, PROCESS), fault_series(5, 40, 20, 1.5, PROCESS))

    def test_t225_shift_boundary(self):
        import random

        class Mean(random.Random):
            def random(self):
                return 1.0

            def gauss(self, mu, sigma):
                return mu

        original = random.Random
        random.Random = Mean
        try:
            values = fault_series(1, 5, 2, 1.5, PROCESS)
        finally:
            random.Random = original
        center = anomaly.confirm_value(PROCESS.center)
        shifted = anomaly.confirm_value(PROCESS.center + 1.5 * PROCESS.sigma)
        self.assertEqual(values, [center, center, shifted, shifted, shifted])

    def test_t226_repair_values_match_by_number(self):
        first = flow_of({6})
        second = flow_of({8})
        run_memory(first, 12)
        run_memory(second, 12)
        self.assertEqual(first.values[10], second.values[10])
        self.assertEqual(first.values[10], first.normal[10])
        self.assertNotEqual(first.normal, first.fault)

    def test_t226_early_stop_keeps_fault(self):
        flow = run_memory(flow_of({2}), 12)
        self.assertFalse(flow.repaired)
        self.assertEqual(flow.values[8], flow.fault[8])
        self.assertTrue(flow.shifted[8])

    def test_t259_early_then_fault_stop(self):
        flow = run_memory(flow_of({2, 8}), 12)
        self.assertEqual([stop.product for stop in flow.stops], [2, 8])
        self.assertEqual(flow.values[7], flow.fault[7])
        self.assertEqual(flow.values[9], flow.normal[9])
        self.assertFalse(flow.shifted[9])


class TrackerTests(unittest.TestCase):
    def chart(self):
        return {"limits": LIMITS, "tuning": TUNING, "process": PROCESS, "start": 9}

    def test_t258_new_segment_state(self):
        tracker = Tracker("cusum", 200, self.chart())
        self.assertEqual((tracker.s, tracker.chart.plus), (-1, []))
        ewma = Tracker("ewma_chart", 50, self.chart())
        self.assertEqual((ewma.s, ewma.chart.value), (-1, LIMITS.xbarbar))

    def test_t258_decision_start(self):
        high = anomaly.confirm_value(PROCESS.center + 9 * PROCESS.sigma)
        tracker = Tracker("cusum", 0, self.chart())
        results = [tracker.update(high) for _ in range(10)]
        self.assertEqual(results, [False] * 9 + [True])

    def test_t258_change_point_uses_global_number(self):
        center = anomaly.confirm_value(PROCESS.center)
        high = anomaly.confirm_value(PROCESS.center + 9 * PROCESS.sigma)
        tracker = Tracker("cusum", 200, self.chart())
        for value in [center] * 5 + [high] * 5:
            tracker.update(value)
        self.assertEqual(tracker.change_point(), 205)

    def test_rule_window(self):
        center = anomaly.confirm_value(PROCESS.center)
        tracker = Tracker("rule_3_2", 0, self.chart())
        results = [tracker.update(value) for value in [center] * 9 + ["13.100", center, "13.100"]]
        self.assertEqual(results[-3:], [False, False, True])
        self.assertIsNone(tracker.change_point())

    def test_rule_needs_decision_start(self):
        tracker = Tracker("rule_3_2", 0, self.chart())
        results = [tracker.update("13.100") for _ in range(10)]
        self.assertEqual(results, [False] * 9 + [True])


class StoryTests(unittest.TestCase):
    def test_t227_order(self):
        flow = flow_of({6})
        story = run_story(STATION, flow, 12, 30, 2000)
        events = [event["event"] for event in story.events if event["incident_id"]]
        self.assertEqual(events, ["alarm", "pc_stop", "alarm_26", "release", "clamp_open", "remove", "reset",
                                  "restart"])
        table = {event["event"]: event for event in story.events if event["incident_id"]}
        self.assertEqual({event["product"] for event in story.events if event["event"] in
                          ("alarm", "pc_stop", "alarm_26", "release", "clamp_open", "remove", "reset")}, {6})
        self.assertGreaterEqual(table["reset"]["cycle"], table["remove"]["cycle"] + 30)
        self.assertEqual(table["restart"]["product"], 7)
        self.assertIn("pc_stop=0", table["reset"]["detail"])

    def test_t227_judgment_not_written(self):
        story = run_story(STATION, flow_of({6}), 12, 30, 2000)
        cycle = next(event["cycle"] for event in story.events if event["event"] == "alarm")
        requests = [frame for frame in story.frames if frame["cycle"] == cycle and frame["direction"] == "request"]
        self.assertEqual([frame["function"] for frame in requests], ["06", "04", "05"])

    def test_t228_counts(self):
        story = run_story(STATION, flow_of({6}), 12, 30, 2000)
        self.assertEqual(story.flow.count("aborted"), 1)
        self.assertEqual(story.ok_count + story.ng_count, 11)
        self.assertEqual(story.flow.disposition[6], "aborted")

    def test_t228_last_product_stop(self):
        story = run_story(STATION, flow_of({11}), 12, 30, 2000)
        self.assertEqual(story.ok_count + story.ng_count + story.flow.count("aborted"), 12)
        self.assertEqual([event["event"] for event in story.events][-2:], ["restart", "finish"])

    def test_t229_silent_run(self):
        story = run_story(STATION, flow_of(set()), 12, 30, 2000)
        flow = story.flow
        self.assertEqual((flow.stops, detection_of(flow.stops, flow.onset)), ([], "missed"))
        result = run_scopes(flow, ("last_20",))["last_20"]
        self.assertEqual((result.captured, result.captured_parts), (False, 0))

    def test_t232_socket_matches_memory(self):
        for method in ("rule_3_2", "ewma_chart", "cusum"):
            socket_flow = real_flow(method, 3042)
            story = run_story(STATION, socket_flow, 60, 5, 5000)
            memory = run_memory(real_flow(method, 3042), 60)
            self.assertEqual([stop.product for stop in socket_flow.stops], [stop.product for stop in memory.stops])
            self.assertEqual(socket_flow.disposition, memory.disposition)
            self.assertEqual(socket_flow.values, memory.values)
            self.assertEqual(story.ok_count, memory.count("OK"))

    def test_t234_other_alarm_refused(self):
        def hook(cycle, plant):
            if cycle == 20:
                plant.forced["guard_closed"] = False
        with self.assertRaises(ValueError):
            run_story(STATION, flow_of(set()), 12, 30, 2000, hook=hook)

    def test_t234_cycle_limit(self):
        with self.assertRaises(ValueError):
            run_story(STATION, flow_of(set()), 12, 30, 100)


class ScopeTests(unittest.TestCase):
    def test_t230_ranges(self):
        self.assertEqual(scope_start("last_20", 10, None), 0)
        self.assertEqual(scope_start("last_20", 100, None), 81)
        self.assertEqual(scope_start("last_50", 10, None), 0)
        self.assertEqual(scope_start("last_50", 100, None), 51)
        self.assertEqual(scope_start("change_point", 100, 90), 90)
        self.assertIsNone(scope_start("change_point", 100, None))

    def shifted(self, onset=100, last=110):
        return {product: product >= onset for product in range(last + 1)}

    def test_t231_full_capture(self):
        disposition = {product: "OK" for product in range(111)}
        result = scope_result(100, 110, 100, self.shifted(), disposition)
        self.assertEqual((result.captured, result.over, result.size, result.captured_parts), (True, 0, 11, 11))

    def test_t231_partial_range(self):
        disposition = {product: "OK" for product in range(111)}
        result = scope_result(105, 110, 100, self.shifted(), disposition)
        self.assertEqual((result.captured, result.captured_parts), (False, 6))

    def test_t231_early_stop_is_not_capture(self):
        stops = [Stop(1, 95, None, "")]
        self.assertEqual(detection_of(stops, 100), "early")
        self.assertIsNone(true_stop(stops, 100))
        self.assertFalse(scope_result(None, None, 100, {}, {}).captured)

    def test_t231_later_stop_is_a(self):
        stops = [Stop(1, 95, None, ""), Stop(2, 120, None, "")]
        self.assertEqual(true_stop(stops, 100).product, 120)
        self.assertEqual(detection_of(stops, 100), "detected")

    def test_suspect_counts_split(self):
        flow = run_memory(flow_of({8}), 12)
        counts = suspect_counts(flow)
        self.assertEqual(sum(counts.values()), 4)
        self.assertEqual(counts["aborted"], 1)

    def test_t260_rates(self):
        hit = run_memory(flow_of({8}), 12)
        silent = run_memory(flow_of(set()), 12)
        summary, table = Summary(), {"last_20": ScopeSummary()}
        add_run(summary, table, hit)
        add_run(summary, table, silent)
        values = dict(scope_values(summary, table["last_20"]))
        self.assertEqual(values["run_capture_rate"], "0.5000")
        expected = table["last_20"].captured_parts / summary.suspect_passed
        self.assertAlmostEqual(float(values["part_capture_rate"]), expected, places=4)

    def test_t260_no_detection_blank_delay(self):
        summary, table = Summary(), {"last_20": ScopeSummary()}
        add_run(summary, table, run_memory(flow_of(set()), 12))
        self.assertEqual(dict(summary_values(summary))["mean_delay"], "")
        self.assertEqual(dict(scope_values(summary, table["last_20"]))["mean_scope_size"], "")


class ConfigTests(unittest.TestCase):
    def invalid(self, **changes):
        with tempfile.TemporaryDirectory() as folder:
            result = run_cli(write_config(folder, **changes), cwd=folder)
            self.assertEqual(result.returncode, 3, str(changes) + result.stderr)
            self.assertFalse((Path(folder) / "reports").exists())

    def test_t233_invalid_values(self):
        for changes in ({"onset_product": 0}, {"onset_product": 41}, {"products": 65536}, {"methods": ["xbar_r"]}, {"methods": []},
                        {"scopes": ["last_20", "last_20"]}, {"pfmea_links": ["PF-99"]}, {"pfmea_links": []},
                        {"products": 10 ** 400}, {"shift_sigma": float("nan")}, {"shift_sigma": True},
                        {"story_seed": 42}, {"summary_seeds": "0-29"}, {"summary_seeds": "abc"}, {"story_seed": True},
                        {"methods": ["rule_3_2"], "scopes": ["change_point"]}, {"extra": 1}):
            with self.subTest(changes=str(changes)[:50]):
                self.invalid(**changes)

    def test_t233_missing_key(self):
        with tempfile.TemporaryDirectory() as folder:
            path = write_config(folder)
            data = json.loads(path.read_text(encoding="utf-8"))
            del data["max_cycles"]
            path.write_text(json.dumps(data), encoding="utf-8")
            self.assertEqual(run_cli(path, cwd=folder).returncode, 3)

    def test_t233_location(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(IncidentError) as caught:
                load_settings(write_config(folder, onset_product=0))
        self.assertIn("$.onset_product", str(caught.exception))

    def test_t233_repair_series_seed_overlap(self):
        base = anomaly.load_settings(ROOT / "recipes" / "anomaly_lamp.json")
        moved = replace(base, splits=dict(base.splits, train=range(1003000, 1003300)))
        with tempfile.TemporaryDirectory() as folder:
            settings = load_settings(write_config(folder, story_seed=3000, summary_seeds="3001-3002"))
            with self.assertRaises(IncidentError):
                check_seeds(settings, moved)
            with self.assertRaises(IncidentError):
                check_seeds(replace(settings, story_seed=9000, summary_seeds=range(3000, 3001)), moved)
            check_seeds(replace(settings, story_seed=9000, summary_seeds=range(9001, 9002)), moved)

    def test_read_pfmea_keeps_order(self):
        links = read_pfmea(ROOT / "data" / "pfmea_lamp.csv", ("PF-06", "PF-02"))
        self.assertEqual(list(links), ["PF-06", "PF-02"])

    def refused(self, **changes):
        with tempfile.TemporaryDirectory() as folder:
            result = run_cli(write_config(folder, **changes), cwd=folder)
            self.assertEqual(result.returncode, 2, str(changes) + result.stderr)
            self.assertFalse((Path(folder) / "reports").exists())

    def test_t234_file_and_limit_refusals(self):
        self.refused(pfmea="없는파일.csv")
        self.refused(spc_report="없는파일.csv")
        self.refused(max_cycles=100)

    def test_t234_changed_limits(self):
        with tempfile.TemporaryDirectory() as folder:
            source = (ROOT / "reports" / "spc_lamp_methods.csv").read_bytes().decode("utf-8-sig")
            rows = source.split("\r\n")
            index = next(i for i, row in enumerate(rows) if row.startswith("limits,,,,sigma_hat,"))
            rows[index] = "limits,,,,sigma_hat,1.5,,,,,,,,,,,"
            report = Path(folder) / "limits.csv"
            report.write_bytes("\r\n".join(rows).encode("utf-8-sig"))
            self.refused(spc_report=str(report))
            missing = [row for row in rows if not row.startswith("limits,")]
            report.write_bytes("\r\n".join(missing).encode("utf-8-sig"))
            self.refused(spc_report=str(report))

    def test_t234_generator_mismatch(self):
        with tempfile.TemporaryDirectory() as folder:
            data = json.loads((ROOT / "recipes" / "plc_station.json").read_text(encoding="utf-8"))
            data["generator"] = str(ROOT / "recipes" / "generator_lot.json")
            path = Path(folder) / "station.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            self.refused(station=str(path))


class ReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.config = write_config(cls.folder.name)
        result = run_cli(cls.config, cwd=cls.folder.name)
        assert result.returncode == 0, result.stderr
        cls.reports = Path(cls.folder.name) / "reports"

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def rows(self, name):
        with (self.reports / name).open(encoding="utf-8-sig", newline="") as source:
            return list(csv.DictReader(source))

    def test_headers(self):
        for name, columns in (("incident_timeline.csv", TIMELINE_COLUMNS), ("incident_compare.csv", COMPARE_COLUMNS),
                              ("incident_suspects.csv", SUSPECT_COLUMNS), ("incident_modbus.csv", FRAME_COLUMNS)):
            with (self.reports / name).open(encoding="utf-8-sig", newline="") as source:
                self.assertEqual(tuple(next(csv.reader(source))), columns)

    def test_sections(self):
        sections = [row["section"] for row in self.rows("incident_compare.csv")]
        self.assertEqual(sections[0], "notice")
        self.assertEqual(sections.count("story"), 3)
        self.assertEqual(sections.count("story_scope"), 9)
        self.assertEqual(sections.count("summary"), 21)
        self.assertEqual(sections.count("summary_scope"), 36)

    def test_not_applicable_scope_is_blank(self):
        rows = self.rows("incident_compare.csv")
        story = [row for row in rows if row["section"] == "story_scope" and row["method"] == "rule_3_2"
                 and row["scope"] == "change_point"]
        self.assertEqual((story[0]["captured"], story[0]["captured_parts"]), ("", ""))
        summary = [row for row in rows if row["section"] == "summary_scope" and row["method"] == "ewma_chart"
                   and row["scope"] == "change_point"]
        self.assertEqual({row["value"] for row in summary}, {""})

    def test_t261_incident_links(self):
        timeline = self.rows("incident_timeline.csv")
        frames = {row["order"]: row for row in self.rows("incident_modbus.csv")}
        stops = [row for row in timeline if row["event"] == "pc_stop" and row["method"] == "cusum"]
        identifiers = {row["incident_id"] for row in frames.values()}
        linked = [row for row in stops if row["incident_id"] in identifiers]
        self.assertEqual(len(linked), len(identifiers))
        for row in linked:
            frame = frames[row["detail"].split("=")[1]]
            self.assertEqual((frame["direction"], frame["function"]), ("request", "05"))
            self.assertIn("00 0a ff 00", frame["hex"])
        text = (self.reports / "incident_pfmea.md").read_text(encoding="utf-8")
        for identifier in identifiers:
            self.assertIn(identifier, text)
            self.assertTrue(any(row["incident_id"] == identifier for row in self.rows("incident_suspects.csv")))

    def test_t235_repeat_byte_for_byte(self):
        names = ("incident_timeline.csv", "incident_compare.csv", "incident_suspects.csv", "incident_modbus.csv",
                 "incident_pfmea.md")
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(run_cli(write_config(folder), cwd=folder).returncode, 0)
            for name in names:
                self.assertEqual((Path(folder) / "reports" / name).read_bytes(), (self.reports / name).read_bytes())


class RealConfigTests(unittest.TestCase):
    def test_t223_step_10_reports_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            environment = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONIOENCODING="utf-8")
            result = subprocess.run([sys.executable, "-m", "src.station", str(ROOT / "recipes" / "plc_station.json"),
                                     "--scenario", "all"], cwd=folder, env=environment, capture_output=True,
                                    text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stderr)
            produced = sorted((Path(folder) / "reports").iterdir())
            self.assertEqual(len(produced), 16)
            for path in produced:
                self.assertEqual(path.read_bytes(), (ROOT / "reports" / path.name).read_bytes(), path.name)

    def test_t236_t262_default_config(self):
        watched = sorted((ROOT / "recipes").glob("*.json")) + [ROOT / "data" / "pfmea_lamp.csv"]
        before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in watched}
        with tempfile.TemporaryDirectory() as folder:
            result = run_cli(CONFIG, cwd=folder)
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(before, {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in watched})


if __name__ == "__main__":
    unittest.main()

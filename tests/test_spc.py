import copy
import csv
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from src import spc
from src.anomaly import Metrics, Scenario, add_outcome, holdout_result
from src.spc import (
    CHART_COLUMNS, METHOD_COLUMNS, Cusum, Ewma, Limits, SpcError, Tuning, alarm_of, count_triggers, decision_count,
    estimate, exposure_end, false_per_1000_decisions, first_alarm, load_limits, load_settings, restricted_run,
    run_rules, select_method, subgroup_alarm, subgroups_of, training_series,
)


ROOT = Path(__file__).resolve().parents[1]
ANOMALY_RAW = json.loads((ROOT / "recipes" / "anomaly_lamp.json").read_text(encoding="utf-8"))
RAW = json.loads((ROOT / "recipes" / "spc_lamp.json").read_text(encoding="utf-8"))
START = 9
UNIT = Tuning(0.2, 3, 0.5, 1.5)
UNIT_LIMITS = Limits(0.0, 2.326, 1.0, 1.342, -1.342, 4.917, 0.4474, 10)


class FakeProcess:
    center = 0.0
    sigma = 1.0


def fake_scenario(shift, onset, values):
    return Scenario(0, shift, onset, [str(value) for value in values], [], [], [])


def settings_stub():
    return mock.Mock(false_limit=2, min_detection=0.90, min_shift_detection=0.70)


def metrics(cost, detected=9, faults=10, alarms=0, shift=(9, 10)):
    return Metrics(faults=faults, detected=detected, cost=cost, alarms=alarms, exposure=10000,
                   by_shift={1.0: shift})


def write_anomaly(folder, **changes):
    data = copy.deepcopy(ANOMALY_RAW)
    data["generator"] = str(ROOT / "recipes" / "generator_measured.json")
    data["iterations"] = 5
    data["length"] = 120
    data["onset_min"] = 20
    data["onset_max"] = 80
    data["splits"] = {"train": {"seed_start": 0, "count": 12}, "validation": {"seed_start": 100, "count": 12},
                      "holdout": {"seed_start": 200, "count": 12}}
    data.update(changes)
    path = Path(folder) / "anomaly.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def cli(module, *arguments, cwd):
    environment = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, "-m", module, *map(str, arguments)], cwd=cwd, env=environment,
                          capture_output=True, text=True, encoding="utf-8")


def write_spc(folder, **changes):
    data = dict(RAW, anomaly="anomaly.json", anomaly_report="reports/anomaly_methods.csv",
                anomaly_model="reports/anomaly_model.csv", anomaly_replay="reports/anomaly_replay.csv")
    data.update(changes)
    path = Path(folder) / "spc.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def prepare(folder, **changes):
    path = write_anomaly(folder, **changes)
    result = cli("src.anomaly", path, cwd=folder)
    assert result.returncode == 0, result.stderr
    return write_spc(folder)


def edit(path, change):
    text = path.read_bytes().decode("utf-8-sig")
    updated = change(text)
    assert updated != text
    path.write_bytes(updated.encode("utf-8-sig"))


class EstimateTests(unittest.TestCase):
    def test_t205_limits(self):
        limits = estimate([[1, 2, 3, 4, 5, 2, 3, 4, 5, 6]])
        self.assertEqual((limits.xbarbar, limits.rbar), (3.5, 4))
        self.assertAlmostEqual(limits.sigma_hat, 1.7197, places=4)
        self.assertAlmostEqual(limits.ucl_x, 5.808, places=3)
        self.assertAlmostEqual(limits.lcl_x, 1.192, places=3)
        self.assertAlmostEqual(limits.ucl_r, 8.456, places=3)
        self.assertAlmostEqual(limits.sigma_xbar, 0.7693, places=4)

    def test_t206_leftover_values_are_dropped(self):
        self.assertEqual(len(subgroups_of(list(range(12)))), 2)
        self.assertEqual(estimate([list(range(10)) + [100, 200]]).subgroups, 2)

    def test_t207_only_training_normals(self):
        normal = [fake_scenario(0, None, [1, 2, 3, 4, 5]), fake_scenario(0, None, [2, 3, 4, 5, 6])]
        faults = [fake_scenario(1.0, 3, [9, 9, 9, 9, 9]), fake_scenario(1.0, 3, [7, 7, 7, 8, 8])]
        changed = [fake_scenario(1.0, 3, [100, 200, 300, 400, 500]), fake_scenario(2.5, 3, [0, 0, 0, 0, 0])]
        first = estimate(training_series(normal + faults, FakeProcess))
        second = estimate(training_series(normal + changed, FakeProcess))
        self.assertEqual(first, second)
        self.assertEqual(first.subgroups, 2)

    def test_t253_estimation_refused(self):
        for series in ([], [[1, 2, 3, 4]], [[5, 5, 5, 5, 5]]):
            with self.assertRaises(ValueError):
                estimate(series)


class SubgroupTests(unittest.TestCase):
    def flat(self, length):
        return [0.0] * length

    def test_t208_only_decision_positions(self):
        limits = UNIT_LIMITS
        early = self.flat(20)
        early[:5] = [9.0] * 5
        self.assertEqual(subgroup_alarm(early, limits, START, False), (None, []))
        late = self.flat(20)
        late[10:15] = [9.0] * 5
        self.assertEqual(subgroup_alarm(late, limits, START, False), (14, ["limit"]))

    def test_t209_range_alarm(self):
        x = self.flat(20)
        x[10:15] = [-3.0, 0.0, 0.0, 0.0, 3.0]
        self.assertEqual(subgroup_alarm(x, UNIT_LIMITS, START, False), (14, ["range"]))

    def test_t210_run_rules(self):
        self.assertIn("run_2of3", run_rules([2.5, 0, 2.5]))
        self.assertNotIn("run_2of3", run_rules([2.5, 0, -2.5]))
        third = run_rules([1.5, 1.5, 0, 1.5, 1.5])
        self.assertIn("run_4of5", third)
        self.assertNotIn("run_2of3", third)
        self.assertEqual(run_rules([0.5] * 8), ["run_8"])
        self.assertEqual(run_rules([0.5] * 7), [])
        self.assertEqual(run_rules([0.5] * 7 + [-0.5]), [])

    def test_t210_lower_side(self):
        self.assertIn("run_2of3", run_rules([-2.5, 0, -2.5]))
        self.assertIn("run_4of5", run_rules([-1.5, -1.5, 0, -1.5, -1.5]))
        self.assertEqual(run_rules([-0.5] * 8), ["run_8"])

    def test_t211_boundaries(self):
        self.assertNotIn("run_2of3", run_rules([2, 0, 2]))
        self.assertNotIn("run_4of5", run_rules([1, 1, 0, 1, 1]))
        self.assertNotIn("run_8", run_rules([0.5, 0.5, 0.5, 0, 0.5, 0.5, 0.5, 0.5]))
        fifth = run_rules([2] * 5)
        self.assertNotIn("run_2of3", fifth)
        self.assertIn("run_4of5", fifth)

    def test_runs_count_from_first_subgroup_but_alarm_at_decision(self):
        limits = Limits(0.0, 2.326, 1.0, 100.0, -100.0, 100.0, 1.0, 10)
        x = [0.5] * 45
        self.assertEqual(subgroup_alarm(x, limits, START, True), (39, ["run_8"]))
        self.assertEqual(subgroup_alarm(x, limits, START, False), (None, []))


class EwmaCusumTests(unittest.TestCase):
    def test_t212_ewma(self):
        chart = Ewma(UNIT_LIMITS, UNIT)
        chart.update(1)
        self.assertAlmostEqual(chart.value, 0.2)
        self.assertAlmostEqual(chart.limit, 0.6)
        for _ in range(200):
            chart.update(0)
        self.assertAlmostEqual(chart.limit, 1.0, places=9)

    def test_t212_small_lambda_keeps_positive_limit(self):
        chart = Ewma(UNIT_LIMITS, Tuning(1e-20, 3, 0.5, 1.5))
        self.assertEqual([chart.update(0.1) for _ in range(12)], [False] * 12)
        self.assertGreater(chart.limit, 0)

    def test_t212_lambda_one(self):
        chart = Ewma(UNIT_LIMITS, Tuning(1.0, 3, 0.5, 1.5))
        chart.update(1)
        self.assertEqual((chart.value, chart.limit), (1.0, 3.0))

    def test_t213_ewma_start(self):
        later = [0.0] * 3 + [9.0] + [0.0] * 8 + [9.0]
        self.assertTrue(Ewma(UNIT_LIMITS, UNIT).update(9.0))
        self.assertEqual(first_alarm(Ewma(UNIT_LIMITS, UNIT), later, START), 12)
        self.assertEqual(first_alarm(Ewma(UNIT_LIMITS, UNIT), [0.0] * 9 + [9.0], START), 9)

    def test_t214_cusum(self):
        chart = Cusum(UNIT_LIMITS, UNIT)
        flags = [chart.update(value) for value in (1, 1, 0, 2)]
        self.assertEqual(chart.plus, [0.5, 1.0, 0.5, 2.0])
        self.assertEqual(flags, [False, False, False, True])
        self.assertEqual(chart.change_point(), 0)

    def test_t215_change_point(self):
        for sign in (1, -1):
            chart = Cusum(UNIT_LIMITS, UNIT)
            flags = [chart.update(sign * value) for value in (0, 0, 1, 2)]
            self.assertTrue(flags[-1])
            self.assertEqual(chart.change_point(), 2)

    def test_t215_decision_start(self):
        # 명세 이견: 표는 첫 초과를 0으로 적었지만 C⁺_0 = 1.5는 h = 1.5를 초과하지 않는다. 식을 따른다.
        self.assertEqual(first_alarm(Cusum(UNIT_LIMITS, UNIT), [2.0] * 12, 0), 1)
        self.assertEqual(first_alarm(Cusum(UNIT_LIMITS, UNIT), [2.0] * 12, START), 9)


class SelectionTests(unittest.TestCase):
    def table(self, costs, **changes):
        return [(name, metrics(cost, **changes)) for name, cost in zip(spc.METHODS, costs)]

    def test_t216_lowest_cost(self):
        self.assertEqual(select_method(self.table((40, 30, 20, 10)), settings_stub()), "cusum")

    def test_t216_tie_keeps_table_order(self):
        self.assertEqual(select_method(self.table((10, 10, 10, 10)), settings_stub()), "xbar_r")

    def test_t216_shift_rate_fails(self):
        rows = self.table((40, 30, 20, 10))
        rows[3] = ("cusum", metrics(10, shift=(6, 10)))
        self.assertEqual(select_method(rows, settings_stub()), "ewma_chart")

    def test_t216_all_fail(self):
        self.assertIsNone(select_method(self.table((1, 2, 3, 4), detected=5), settings_stub()))

    def test_t217_holdout(self):
        stub = settings_stub()
        self.assertEqual(holdout_result("cusum", metrics(1), stub), "확인")
        self.assertEqual(holdout_result("cusum", metrics(1, detected=5), stub), "미달")
        self.assertEqual(holdout_result(None, None, stub), "검증할 선택 없음")


class DenominatorTests(unittest.TestCase):
    def test_t251_counts(self):
        self.assertEqual(decision_count("xbar_r", 9, exposure_end(None, None, 400)), 79)
        self.assertEqual(decision_count("cusum", 9, exposure_end(None, None, 400)), 391)
        self.assertEqual(decision_count("xbar_r", 9, exposure_end(None, 19, 400)), 3)
        self.assertEqual(decision_count("xbar_we", 10, 13), 0)
        stats = Metrics()
        add_outcome(stats, 0, None, 19, 400, 10)
        self.assertEqual(stats.exposure, 11)

    def test_t251_exposure_matches_add_outcome(self):
        for onset, alarm in ((None, None), (None, 50), (100, None), (100, 50), (100, 150)):
            stats = Metrics()
            add_outcome(stats, 1.0, onset, alarm, 400, 10)
            self.assertEqual(decision_count("cusum", 9, exposure_end(onset, alarm, 400)), stats.exposure)

    def test_t251_per_decision_rate(self):
        outcomes = [(0, None, 19), (0, None, None)]
        rate = false_per_1000_decisions("xbar_r", outcomes, 400, 9)
        self.assertEqual(rate, Fraction(1000, 82))
        self.assertEqual(false_per_1000_decisions("cusum", outcomes, 400, 9), Fraction(1000, 402))

    def test_t252_restricted_run(self):
        mean, silent = restricted_run([(0, None, 9), (0, None, 108), (0, None, None), (1.0, 50, 60)], 400, 9)
        self.assertEqual((mean, silent), (164, 1))

    def test_t257_trigger_count(self):
        counts = count_triggers([["limit", "run_2of3"], ["run_8"], []])
        self.assertEqual((counts["limit"], counts["run_8"], counts["run_2of3"], counts["joint"]), (1, 1, 0, 1))

    def test_alarm_of_dispatch(self):
        x = [0.0] * 20 + [9.0] * 20
        for method in spc.METHODS:
            self.assertIsNotNone(alarm_of(method, x, UNIT_LIMITS, UNIT, START))


class ConfigTests(unittest.TestCase):
    def invalid(self, **changes):
        with tempfile.TemporaryDirectory() as folder:
            result = cli("src.spc", write_spc(folder, **changes), cwd=folder)
            self.assertEqual(result.returncode, 3, str(changes) + result.stderr)
            self.assertFalse((Path(folder) / "reports").exists())

    def test_t218_invalid_values(self):
        for changes in ({"subgroup": 4}, {"subgroup": True}, {"ewma_lambda": 0}, {"ewma_lambda": 1.5},
                        {"cusum_k": 0}, {"cusum_h": 10 ** 400}, {"ewma_l": float("nan")}, {"ewma_l": True},
                        {"extra": 1}):
            with self.subTest(changes=str(changes)[:40]):
                self.invalid(**changes)

    def test_t218_missing_key(self):
        with tempfile.TemporaryDirectory() as folder:
            path = write_spc(folder)
            data = json.loads(path.read_text(encoding="utf-8"))
            del data["cusum_k"]
            path.write_text(json.dumps(data), encoding="utf-8")
            self.assertEqual(cli("src.spc", path, cwd=folder).returncode, 3)

    def test_settings_location(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(SpcError) as caught:
                load_settings(write_spc(folder, subgroup=4))
        self.assertIn("$.subgroup", str(caught.exception))


class ReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.config = prepare(cls.folder.name)
        cls.anomaly_before = (Path(cls.folder.name) / "reports" / "anomaly_methods.csv").read_bytes()
        result = cli("src.spc", cls.config, cwd=cls.folder.name)
        assert result.returncode == 0, result.stderr
        cls.reports = Path(cls.folder.name) / "reports"

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def rows(self, name="spc_methods.csv"):
        with (self.reports / name).open(encoding="utf-8-sig", newline="") as source:
            return list(csv.DictReader(source))

    def section(self, name):
        return [row for row in self.rows() if row["section"] == name]

    def test_headers(self):
        self.assertEqual(tuple(self.rows()[0]), METHOD_COLUMNS)
        self.assertEqual(tuple(self.rows("spc_chart.csv")[0]), CHART_COLUMNS)

    def test_section_sizes(self):
        expected = {"notice": 1, "provenance": 5, "limits": 15, "validation": 4, "holdout": 4, "reference": 6,
                    "clean_limits": 8, "clean_holdout": 4, "selection": 2, "triggers": 12}
        for name, size in expected.items():
            self.assertEqual(len(self.section(name)), size, name)

    def test_subgroup_columns(self):
        table = {row["method"]: row for row in self.section("holdout")}
        self.assertEqual((table["xbar_r"]["decision_interval"], table["xbar_r"]["max_wait"]), ("5", "4"))
        self.assertEqual((table["cusum"]["decision_interval"], table["cusum"]["max_wait"]), ("1", "0"))
        self.assertEqual(table["cusum"]["false_per_1000"], table["cusum"]["false_per_1000_decisions"])

    def test_reference_rows_copy_step_11(self):
        with (self.reports / "anomaly_methods.csv").open(encoding="utf-8-sig", newline="") as source:
            original = {(row["section"], row["method"]): row for row in csv.DictReader(source)}
        for row in self.section("reference"):
            source = original[(row["split"], row["method"])]
            self.assertEqual(row["mean_delay_cost"], source["mean_delay_cost"])
            self.assertEqual(row["false_per_1000"], source["false_per_1000"])

    def test_limits_round_trip(self):
        rows = load_limits(self.reports / "spc_methods.csv")
        self.assertEqual(set(rows), {"center", "sigma", "xbarbar", "rbar", "sigma_hat", "ucl_x", "lcl_x", "ucl_r",
                                     "sigma_xbar", "subgroups", "ewma_lambda", "ewma_l", "cusum_k", "cusum_h",
                                     "window"})
        self.assertEqual(float(rows["ewma_lambda"]), 0.2)

    def test_chart_rows(self):
        rows = self.rows("spc_chart.csv")
        self.assertEqual(len(rows), 120)
        self.assertEqual([row["t"] for row in rows if row["xbar"]][:2], ["4", "9"])
        self.assertEqual(rows[0]["seed"], "201")

    def test_t219_repeat_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as folder:
            config = prepare(folder)
            self.assertEqual(cli("src.spc", config, cwd=folder).returncode, 0)
            for name in ("spc_methods.csv", "spc_chart.csv"):
                self.assertEqual((Path(folder) / "reports" / name).read_bytes(), (self.reports / name).read_bytes())

    def test_t220_step_11_reports_unchanged(self):
        self.assertEqual((self.reports / "anomaly_methods.csv").read_bytes(), self.anomaly_before)

    def test_t255_provenance(self):
        before = {row["name"]: row["value"] for row in self.section("provenance")}
        path = self.reports / "anomaly_methods.csv"
        self.assertEqual(before["anomaly_methods.csv"], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(set(before), {"spc.json", "anomaly.json", "anomaly_methods.csv", "anomaly_model.csv",
                                       "anomaly_replay.csv"})

    def test_t256_clean_limits_are_narrower(self):
        normal = {row["name"]: float(row["value"]) for row in self.section("limits")}
        clean = {row["name"]: float(row["value"]) for row in self.section("clean_limits")}
        self.assertLess(clean["rbar"], normal["rbar"])

    def test_t256_clean_section_does_not_change_selection(self):
        self.assertEqual(len(self.section("selection")), 2)
        self.assertEqual(self.section("clean_holdout")[0]["section"], "clean_holdout")


class RefusalTests(unittest.TestCase):
    def refused(self, change):
        with tempfile.TemporaryDirectory() as folder:
            config = prepare(folder)
            change(Path(folder))
            result = cli("src.spc", config, cwd=folder)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertFalse((Path(folder) / "reports" / "spc_methods.csv").exists())

    def test_t217_missing_row(self):
        def drop(folder):
            edit(folder / "reports" / "anomaly_methods.csv",
                 lambda text: "\n".join(line for line in text.split("\n") if not line.startswith("holdout,logistic")))
        self.refused(drop)

    def test_t254_setting_changed(self):
        self.refused(lambda folder: edit(folder / "reports" / "anomaly_model.csv",
                                         lambda text: text.replace("setting,window,10", "setting,window,11")))

    def test_t254_split_changed(self):
        self.refused(lambda folder: edit(folder / "reports" / "anomaly_model.csv",
                                         lambda text: text.replace("split,holdout,200-211", "split,holdout,200-212")))

    def test_t254_rule_row_changed(self):
        def change(folder):
            path = folder / "reports" / "anomaly_methods.csv"
            rows = path.read_bytes().decode("utf-8-sig").split("\r\n")
            index = next(i for i, line in enumerate(rows) if line.startswith("validation,rule_3_2,,"))
            cells = rows[index].split(",")
            cells[8] = "999.0000"
            rows[index] = ",".join(cells)
            path.write_bytes("\r\n".join(rows).encode("utf-8-sig"))
        self.refused(change)

    def test_t254_duplicate_row_either_order(self):
        def duplicate(first):
            def change(folder):
                path = folder / "reports" / "anomaly_methods.csv"
                rows = path.read_bytes().decode("utf-8-sig").split("\r\n")
                index = next(i for i, line in enumerate(rows) if line.startswith("validation,rule_3_2,,"))
                cells = rows[index].split(",")
                cells[8] = "999.0000"
                pair = [",".join(cells), rows[index]] if first else [rows[index], ",".join(cells)]
                rows[index:index + 1] = pair
                path.write_bytes("\r\n".join(rows).encode("utf-8-sig"))
            return change
        self.refused(duplicate(True))
        self.refused(duplicate(False))

    def test_t254_duplicate_model_row(self):
        self.refused(lambda folder: edit(folder / "reports" / "anomaly_model.csv",
                                         lambda text: text.replace("setting,window,10", "setting,window,11\r\nsetting,window,10")))

    def test_t254_replay_value_changed(self):
        def change(folder):
            path = folder / "reports" / "anomaly_replay.csv"
            rows = path.read_bytes().decode("utf-8-sig").split("\r\n")
            cells = rows[1].split(",")
            cells[5] = "1.234"
            rows[1] = ",".join(cells)
            path.write_bytes("\r\n".join(rows).encode("utf-8-sig"))
        self.refused(change)

    def test_t254_moving_average_changed(self):
        def change(folder):
            path = folder / "reports" / "anomaly_methods.csv"
            rows = path.read_bytes().decode("utf-8-sig").split("\r\n")
            index = next(i for i, line in enumerate(rows) if line.startswith("holdout,moving_average,,"))
            cells = rows[index].split(",")
            if not cells[3]:
                self.skipTest("작은 설정에 임계값이 없음")
            cells[8] = "999.0000"
            rows[index] = ",".join(cells)
            path.write_bytes("\r\n".join(rows).encode("utf-8-sig"))
        self.refused(change)

    def test_t254_generator_values_changed_with_same_rule_result(self):
        with tempfile.TemporaryDirectory() as folder:
            source = json.loads((ROOT / "recipes" / "generator_measured.json").read_text(encoding="utf-8"))
            source["defective_product_probability"] = 0.0
            source["process_cpk"] = 5.0
            directory = ROOT / "recipes"
            for key in ("recipe", "equipment"):
                if key in source and isinstance(source[key], str):
                    source[key] = str(directory / source[key])
            generator = Path(folder) / "generator_measured.json"
            generator.write_text(json.dumps(source), encoding="utf-8")
            config = prepare(folder, generator=str(generator))
            source["process_cpk"] = 6.0
            generator.write_text(json.dumps(source), encoding="utf-8")
            result = cli("src.spc", config, cwd=folder)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertFalse((Path(folder) / "reports" / "spc_methods.csv").exists())

    def test_t254_length_only_changed(self):
        def change(folder):
            write_anomaly(folder, length=119)
        self.refused(change)

    def test_t253_short_scenarios_exit_2(self):
        with tempfile.TemporaryDirectory() as folder:
            config = prepare(folder, length=4, onset_min=2, onset_max=3, window=2)
            result = cli("src.spc", config, cwd=folder)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertFalse((Path(folder) / "reports" / "spc_methods.csv").exists())

    def test_t253_zero_range_exit_2(self):
        with tempfile.TemporaryDirectory() as folder:
            config = prepare(folder)
            current = os.getcwd()
            os.chdir(folder)
            try:
                with mock.patch("src.spc.normalized", lambda values, process: [0.0] * len(values)):
                    with self.assertRaises(SystemExit) as caught, mock.patch("sys.stderr"):
                        spc.main([str(config)])
            finally:
                os.chdir(current)
            self.assertEqual(caught.exception.code, 2)
            self.assertFalse((Path(folder) / "reports" / "spc_methods.csv").exists())


if __name__ == "__main__":
    unittest.main()

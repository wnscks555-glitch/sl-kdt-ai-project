import copy
import csv
from fractions import Fraction
import json
import math
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

from src.anomaly import (
    AnomalyError, Metrics, Process, Scenario, add_outcome, assignment, build_scenario, build_split, choose_threshold,
    ewma_of, first_rule_alarm, fit_logistic, fit_model, holdout_result, linear_score, load_process, load_settings,
    logistic_scores, rule_outcomes,
    measure, measure_alarms, policy_row, quantize, replay_range, replay_rows, reproduce_stops, sample_loss,
    select_method, select_threshold, sigmoid, standardizer, stop_flags, trace_of, window_features,
)
from src.equipment import EquipmentState
from src.generate import load_setup


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "recipes" / "anomaly_lamp.json"
RAW = json.loads(CONFIG.read_text(encoding="utf-8"))
SETTINGS = load_settings(CONFIG)
PROCESS = load_process(SETTINGS)
SIGMA = 6 / (6 * 1.33)


class StubRandom:
    """gauss는 평균을 그대로 돌려주고, random은 주어진 값을 돌려준다."""

    def __init__(self, draw=1.0):
        self.draw = draw

    def random(self):
        return self.draw

    def gauss(self, mean, _):
        return mean


def small_config(folder, **changes):
    data = copy.deepcopy(RAW)
    data["generator"] = str(ROOT / "recipes" / "generator_measured.json")
    data["iterations"] = 20
    data["splits"] = {"train": {"seed_start": 0, "count": 12}, "validation": {"seed_start": 100, "count": 12},
                      "holdout": {"seed_start": 200, "count": 12}}
    data.update(changes)
    path = Path(folder) / "anomaly.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def run_cli(*arguments, cwd):
    environment = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, "-m", "src.anomaly", *map(str, arguments)], cwd=cwd, env=environment,
                          capture_output=True, text=True, encoding="utf-8")


def metric(alarms=0, exposure=1000, detected=3, faults=3, cost=9):
    return Metrics(faults=faults, detected=detected, cost=cost, alarms=alarms, exposure=exposure,
                   by_shift={1.0: (detected, faults)})


class SeriesTests(unittest.TestCase):
    def test_t172_measure_values(self):
        cases = [(1.0, 0, "10.000"), (1.0, 2.5, "11.880"), (0.0, 0, "13.759"), (0.0, 2.5, "15.639")]
        for draw, shift, expected in cases:
            self.assertEqual(measure(StubRandom(draw), PROCESS, shift), expected)

    def test_t172_onset_boundary(self):
        original = random.Random
        try:
            random.Random = lambda seed: type("R", (StubRandom,), {"randint": lambda self, low, high: 150})(1.0)
            scenario = build_scenario(1, 2.5, SETTINGS, PROCESS)
        finally:
            random.Random = original
        self.assertEqual(scenario.onset, 150)
        self.assertEqual(scenario.values[149], "10.000")
        self.assertEqual(scenario.values[150], "11.880")

    def test_t173_repeatable_and_assigned(self):
        self.assertEqual(build_scenario(5, 1.5, SETTINGS, PROCESS).values, build_scenario(5, 1.5, SETTINGS, PROCESS).values)
        shifts = (1.0, 1.5, 2.5)
        self.assertEqual([assignment(index, shifts) for index in (0, 1, 3, 5, 7)], [0, 1.0, 1.5, 2.5, 1.0])
        counts = [assignment(index, shifts) for index in range(300)]
        self.assertEqual(counts.count(0), 150)
        self.assertEqual([counts.count(shift) for shift in shifts], [50, 50, 50])

    def test_normal_scenario_also_draws_defects_and_no_onset(self):
        scenario = build_scenario(0, 0, SETTINGS, PROCESS)
        self.assertIsNone(scenario.onset)
        self.assertEqual(len(scenario.values), 400)
        self.assertEqual(len(scenario.features), 391)

    def test_t174_features(self):
        x = [0.0] * 9 + [10.0]
        fails = [False] * 9 + [True]
        mean, sd, maximum, slope, ewma, share = window_features(x, fails, ewma_of(x, 0.2), 10, 9)
        self.assertAlmostEqual(mean, 1.0)
        self.assertAlmostEqual(maximum, 10.0)
        self.assertAlmostEqual(sd, math.sqrt(10))
        self.assertAlmostEqual(slope, 6 / 11)
        self.assertAlmostEqual(share, 0.1)
        self.assertAlmostEqual(ewma, 2.0)

    def test_t174_ewma_recursion(self):
        self.assertEqual(ewma_of([1.0, 1.0], 0.5), [0.5, 0.75])

    def test_t175_features_ignore_later_values(self):
        x = [float(index % 7) for index in range(30)]
        fails = [index % 5 == 0 for index in range(30)]
        before = window_features(x, fails, ewma_of(x, 0.2), 10, 15)
        changed = x[:16] + [99.0] * 14
        after = window_features(changed, fails[:16] + [True] * 14, ewma_of(changed, 0.2), 10, 15)
        self.assertEqual(before, after)

    def test_t177_validation_change_reaches_evaluation_but_not_the_model(self):
        moved = {"train": {"seed_start": 0, "count": 12}, "validation": {"seed_start": 300, "count": 12},
                 "holdout": {"seed_start": 200, "count": 12}}
        reports = []
        for changes in ({}, {"splits": moved}):
            with tempfile.TemporaryDirectory() as folder:
                self.assertEqual(run_cli(small_config(folder, **changes), cwd=folder).returncode, 0)
                directory = Path(folder) / "reports"
                with (directory / "anomaly_model.csv").open(encoding="utf-8-sig", newline="") as source:
                    model = [row for row in csv.DictReader(source)
                             if row["section"] in ("mean", "scale", "weight", "bias", "windows")]
                with (directory / "anomaly_methods.csv").open(encoding="utf-8-sig", newline="") as source:
                    validation = [row for row in csv.DictReader(source) if row["section"] == "validation"]
                reports.append((model, validation))
        self.assertEqual(reports[0][0], reports[1][0])
        self.assertNotEqual(reports[0][1], reports[1][1])

    def test_t177_zero_variance_divides_by_one(self):
        means, scales = standardizer([(1.0, 5.0), (3.0, 5.0)])
        self.assertEqual(means, [2.0, 5.0])
        self.assertEqual(scales, [1.0, 1.0])


class LogisticTests(unittest.TestCase):
    def test_t178_separable_points(self):
        rows, labels = [[-2.0], [-1.0], [1.0], [2.0]], [0, 0, 1, 1]
        first = fit_logistic(rows, labels, 0.1, 300, 0.001)
        self.assertEqual(first, fit_logistic(rows, labels, 0.1, 300, 0.001))
        weights, bias, norm = first
        predicted = [int(sigmoid(linear_score(row, weights, bias)) >= 0.5) for row in rows]
        self.assertEqual(predicted, labels)
        self.assertGreater(norm, 0)

    def test_t178_norm_uses_final_coefficients(self):
        rows, labels = [[-2.0], [2.0]], [0, 1]
        weights, bias, norm = fit_logistic(rows, labels, 0.1, 1, 0.0)
        probabilities = [sigmoid(linear_score(row, weights, bias)) for row in rows]
        errors = [probability - label for probability, label in zip(probabilities, labels)]
        expected = math.hypot(sum(error * row[0] for error, row in zip(errors, rows)) / 2, sum(errors) / 2)
        self.assertAlmostEqual(norm, expected)

    def test_t178_extreme_scores_are_finite(self):
        for z in (40.0, -40.0, 1000.0, -1000.0):
            for label in (0, 1):
                self.assertTrue(math.isfinite(sample_loss(z, label)))
            self.assertTrue(0 <= sigmoid(z) <= 1)

    def test_loss_matches_cross_entropy(self):
        for z in (-2.0, 0.0, 1.5):
            p = sigmoid(z)
            self.assertAlmostEqual(sample_loss(z, 1), -math.log(p))
            self.assertAlmostEqual(sample_loss(z, 0), -math.log(1 - p))


class ThresholdTests(unittest.TestCase):
    def test_t179_threshold_selection(self):
        candidates = [(2000, metric(alarms=3, cost=3)), (3000, metric(alarms=2, cost=15)),
                      (4000, metric(alarms=2, cost=15)), (5000, metric(alarms=1, detected=2, cost=9))]
        self.assertEqual(select_threshold(candidates, SETTINGS)[0], 4000)
        self.assertIsNone(select_threshold([candidates[0], candidates[3]], SETTINGS))

    def test_quantize_half_up(self):
        self.assertEqual(quantize(0.12345), 1235)
        self.assertEqual(quantize(-0.12345), -1235)

    def test_trace_finds_first_alarm_from_running_peak(self):
        scenario = Scenario(0, 1.0, 100, [], [], [], [])
        trace = trace_of(scenario, [5, 3, 7, 7, 9], 10)
        self.assertEqual(trace.peaks, [5, 7, 9])
        self.assertEqual([trace.first_alarm(h) for h in (4, 5, 6, 8, 9, 10)], [9, 9, 11, 13, 13, None])

    def test_peak_candidates_match_exhaustive_search(self):
        rng = random.Random(3)
        traces = []
        for index in range(40):
            onset = 30 if index % 2 else None
            shift = 1.0 if index % 2 else 0
            scores = [rng.randint(0, 40) + (index % 2) * 5 * (t >= 30) for t in range(60)]
            traces.append(trace_of(Scenario(index, shift, onset, [], [], [], []), scores, 2))

        class Loose:
            false_limit, min_detection, min_shift_detection = 900, 0.5, 0.5
            length, window = 60, 2

        fast, _ = choose_threshold(traces, Loose)
        unique = sorted(set().union(*(trace.values for trace in traces)))
        rows = [(h, measure_alarms([(trace.shift, trace.onset, trace.first_alarm(h)) for trace in traces], 60, 2))
                for h in unique + [max(unique) + 1]]
        slow = select_threshold(rows, Loose)
        self.assertEqual(fast[0], slow[0])
        self.assertEqual(fast[1].mean_cost, slow[1].mean_cost)


class MetricTests(unittest.TestCase):
    def test_t180_alarm_classes(self):
        outcomes = [(1.0, 200, 199), (1.0, 200, 200), (1.0, 200, 210), (1.0, 200, None)]
        metrics = measure_alarms(outcomes, 400, 10)
        self.assertEqual((metrics.early, metrics.detected, metrics.missed), (1, 2, 1))
        self.assertEqual(metrics.cost, 200 + 0 + 10 + 200)
        self.assertEqual(metrics.mean_cost, Fraction(1025, 10))
        self.assertEqual(metrics.detection_rate, Fraction(1, 2))
        self.assertEqual(metrics.mean_detected, 5)

    def test_t181_exposure(self):
        metrics = measure_alarms([(0, None, None), (0, None, 9), (1.0, 100, None)], 400, 10)
        self.assertEqual(metrics.exposure, 483)
        self.assertEqual(metrics.alarms, 1)
        self.assertEqual(round(float(metrics.false_per_1000), 4), 2.0704)
        self.assertGreater(metrics.false_per_1000, 2)

    def test_exposure_stops_at_early_alarm_and_ignores_post_onset(self):
        metrics = Metrics()
        add_outcome(metrics, 1.0, 100, 50, 400, 10)
        self.assertEqual((metrics.exposure, metrics.alarms), (42, 1))
        metrics = Metrics()
        add_outcome(metrics, 1.0, 100, 150, 400, 10)
        self.assertEqual((metrics.exposure, metrics.alarms), (91, 0))

    def test_t182_method_selection(self):
        good = lambda cost: metric(cost=cost * 3)
        selection = lambda *rows: select_method(list(zip(("rule_3_2", "moving_average", "logistic"), rows)), SETTINGS)
        self.assertEqual(selection(good(30), good(20), good(10)), "logistic")
        self.assertEqual(selection(good(10), good(10), good(10)), "rule_3_2")
        weak = metric(cost=3)
        weak.by_shift = {1.0: (3, 5), 2.5: (9, 9)}
        self.assertEqual(selection(weak, good(20), None), "moving_average")
        self.assertIsNone(selection(metric(alarms=9), metric(detected=1), None))

    def test_t183_rule_reproduction(self):
        _, _, _, book = load_setup(ROOT / "recipes" / "generator_measured.json")
        fails = [True, True, False, False] + [False] * 8 + [True, False, True]
        self.assertTrue(reproduce_stops(fails, book)[1])
        self.assertEqual(first_rule_alarm(fails, book.window, book.fails, 9), 14)
        rng = random.Random(1)
        series = [rng.random() < 0.3 for _ in range(500)]
        state = EquipmentState()
        expected = []
        for t, fail in enumerate(series):
            state = state.record("FAIL" if fail else "PASS", str(t), book)
            expected.append(state.stopped_at_seq is not None)
        self.assertEqual(reproduce_stops(series, book), expected)
        self.assertEqual(stop_flags(series, book.window, book.fails), expected)

    def test_t183_comparison_rule_ignores_generator_stop_rule(self):
        scenario = Scenario(0, 1.0, 10, [], [False] * 9 + [True, True] + [False] * 9, [], [])
        settings = load_settings(CONFIG)
        self.assertEqual(rule_outcomes([scenario], settings), [(1.0, 10, 10)])

    def test_t184_policy(self):
        metrics = measure_alarms([(1.0, 200, 200), (1.0, 200, 205), (1.0, 200, None), (1.0, 200, 150)], 400, 10)
        self.assertEqual([metrics.suspect], [1 + 6 + 200 + 200])
        self.assertEqual(metrics.suspect_output, Fraction(10175, 100))
        row = policy_row("logistic", metrics, "", SETTINGS)
        self.assertEqual(row["suspect_output"], "101.7500")
        self.assertEqual(row["stop_minutes"], "7500.0000")

    def test_t185_holdout(self):
        self.assertEqual(holdout_result("logistic", metric(), SETTINGS), "확인")
        self.assertEqual(holdout_result("logistic", metric(alarms=9), SETTINGS), "미달")
        self.assertEqual(holdout_result(None, None, SETTINGS), "검증할 선택 없음")


class ReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.settings = load_settings(small_config(cls.folder.name))
        cls.model = fit_model(build_split(cls.settings.splits["train"], cls.settings, PROCESS), cls.settings)
        cls.scenario = build_scenario(201, 2.5, cls.settings, PROCESS)

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def test_t189_ranges(self):
        self.assertEqual(replay_range(200, 203, 10, 400), (195, 203))
        self.assertEqual(replay_range(200, 150, 10, 400), (150, 150))
        self.assertEqual(replay_range(200, 199, 10, 400), (195, 199))
        self.assertEqual(replay_range(200, 195, 10, 400), (195, 195))
        self.assertEqual(replay_range(200, 194, 10, 400), (194, 194))
        self.assertEqual(replay_range(200, None, 10, 400), (195, 220))
        self.assertEqual(replay_range(390, None, 10, 400), (385, 399))
        self.assertEqual(replay_range(10, None, 10, 400), (9, 30))

    def test_t189_statuses(self):
        onset = self.scenario.onset
        early = replay_rows(self.scenario, self.model, -1, self.settings)
        self.assertEqual(len(early), 1)
        self.assertEqual(early[0]["status"], "early")
        silent = replay_rows(self.scenario, self.model, 10001, self.settings)
        self.assertEqual({row["status"] for row in silent}, {"missed"})
        self.assertEqual(silent[-1]["t"], min(onset + 20, 399))
        blank = replay_rows(self.scenario, self.model, None, self.settings)
        self.assertEqual({row["status"] for row in blank}, {"임계값 없음"})
        self.assertEqual({row["threshold"] for row in blank}, {""})
        self.assertEqual({row["alarm"] for row in blank}, {""})

    def test_t189_detected_ends_at_alarm(self):
        scores = logistic_scores(self.scenario, self.model)
        trace = trace_of(self.scenario, scores, 10)
        threshold = next(peak for peak, t in zip(trace.peaks, trace.times) if t >= self.scenario.onset)
        rows = replay_rows(self.scenario, self.model, threshold, self.settings)
        self.assertEqual(rows[-1]["alarm"], 1)
        self.assertEqual(rows[-1]["status"], "detected")

    def test_t189_rows_recompute_from_their_own_fields(self):
        rows = replay_rows(self.scenario, self.model, None, self.settings)
        for row in rows:
            values = [float(value) for value in row["window_values"].split()]
            x = [(value - PROCESS.center) / PROCESS.sigma for value in values]
            ewma = 0.2 * x[-1] + 0.8 * float(row["ewma_prev"])
            fails = [value < 7 or value > 13 for value in values]
            features = list(window_features(x, fails, [ewma] * 10, 10, 9))
            z = self.model.z(features)
            self.assertAlmostEqual(z, float(row["z"]), places=6)
            self.assertAlmostEqual(sigmoid(z), float(row["p"]), places=6)


class CliTests(unittest.TestCase):
    def test_t176_t187_config_errors_exit_3(self):
        overlapping = {"train": {"seed_start": 0, "count": 12}, "validation": {"seed_start": 6, "count": 12},
                       "holdout": {"seed_start": 200, "count": 12}}
        inner = {"train": {"seed_start": 0, "count": 12, "x": 1}, "validation": {"seed_start": 100, "count": 12},
                 "holdout": {"seed_start": 200, "count": 12}}
        odd = {"train": {"seed_start": 0, "count": 10}, "validation": {"seed_start": 100, "count": 12},
               "holdout": {"seed_start": 200, "count": 12}}
        cases = [dict(splits=overlapping), dict(extra=1), dict(splits=inner), dict(window=1), dict(onset_min=301),
                 dict(shifts=[]), dict(shifts=[1.0, 1.0]), dict(iterations=0.5), dict(splits=odd),
                 dict(l2=float("nan")), dict(length=True)]
        for changes in cases:
            with tempfile.TemporaryDirectory() as folder:
                result = run_cli(small_config(folder, **changes), cwd=folder)
                self.assertEqual(result.returncode, 3, str(changes) + result.stderr)
                self.assertFalse((Path(folder) / "reports").exists())

    def test_t187_missing_key_exit_3(self):
        with tempfile.TemporaryDirectory() as folder:
            path = small_config(folder)
            data = json.loads(path.read_text(encoding="utf-8"))
            del data["window"]
            path.write_text(json.dumps(data), encoding="utf-8")
            self.assertEqual(run_cli(path, cwd=folder).returncode, 3)

    def test_t187_plain_generator_exit_2(self):
        with tempfile.TemporaryDirectory() as folder:
            path = small_config(folder, generator=str(ROOT / "recipes" / "generator.json"))
            self.assertEqual(run_cli(path, cwd=folder).returncode, 2)
            self.assertFalse((Path(folder) / "reports").exists())

    def test_t186_reports_repeat_byte_for_byte(self):
        contents = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as folder:
                result = run_cli(small_config(folder), cwd=folder)
                self.assertEqual(result.returncode, 0, result.stderr)
                paths = sorted((Path(folder) / "reports").iterdir())
                self.assertEqual([path.name for path in paths],
                                 ["anomaly_methods.csv", "anomaly_model.csv", "anomaly_replay.csv"])
                contents.append([path.read_bytes() for path in paths])
        self.assertEqual(contents[0], contents[1])

    def test_method_report_sections(self):
        with tempfile.TemporaryDirectory() as folder:
            run_cli(small_config(folder), cwd=folder)
            path = Path(folder) / "reports" / "anomaly_methods.csv"
            with path.open(encoding="utf-8-sig", newline="") as source:
                sections = {row["section"] for row in csv.DictReader(source)}
        self.assertLessEqual({"notice", "validation", "holdout", "selection"}, sections)

    def test_t188_existing_files_unchanged(self):
        tracked = [path for folder in ("recipes", "data", "reports") for path in (ROOT / folder).rglob("*")
                   if path.is_file() and not path.name.startswith("anomaly_lamp")]
        before = {path: path.read_bytes() for path in tracked}
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(run_cli(small_config(folder), cwd=folder).returncode, 0)
        self.assertEqual({path: path.read_bytes() for path in tracked}, before)

    def test_t187_huge_integers_exit_3(self):
        for changes in (dict(min_detection=10 ** 400), dict(learning_rate=10 ** 400), dict(shifts=[10 ** 400])):
            with tempfile.TemporaryDirectory() as folder:
                result = run_cli(small_config(folder, **changes), cwd=folder)
                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertFalse((Path(folder) / "reports").exists())

    def test_load_settings_reports_location(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(AnomalyError) as caught:
                load_settings(small_config(folder, ewma_lambda=2))
            self.assertIn("$.ewma_lambda", caught.exception.errors[0])


if __name__ == "__main__":
    unittest.main()

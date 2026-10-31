import copy
import csv
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

from src.anomaly import Process, load_process
from src.msa import (
    GRR_COLUMNS, GUARD_COLUMNS, STUDY_COLUMNS, Gauge, MsaError, Tally, acceptance_limits, anova, average_range,
    build_study, distinct_categories, f_tail, fixed_operator_pairs, grr_row, holdout_result, load_settings, ndc_ok,
    noise_sigma, observed_cpk, operator_offsets, parse_seeds, percent_grr, sample_pairs, select_guard, verdict,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "recipes" / "msa_lamp.json"
RAW = json.loads(CONFIG.read_text(encoding="utf-8"))
SETTINGS = load_settings(CONFIG)
PROCESS = load_process(SETTINGS)
ITEM = PROCESS.item


def table(*cells):
    """2×2×2 연구를 칸 순서대로 받는다."""
    return [[cells[0], cells[1]], [cells[2], cells[3]]]


T190 = table(("1", "3"), ("3", "5"), ("5", "7"), ("7", "9"))
T191 = table(("1", "2"), ("3", "4"), ("3", "4"), ("1", "2"))


class LoggingRandom:
    """gauss는 평균을 돌려주고, 호출을 기록한다."""

    def __init__(self):
        self.calls = []

    def gauss(self, mean, sigma):
        self.calls.append((mean, sigma))
        return mean


def small_config(folder, **changes):
    data = copy.deepcopy(RAW)
    data["generator"] = str(ROOT / "recipes" / "generator_measured.json")
    data["products"] = 50
    data["dev_seeds"] = "0-1"
    data["holdout_seeds"] = "10-11"
    data.update(changes)
    path = Path(folder) / "msa.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def run_cli(*arguments, cwd):
    environment = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, "-m", "src.msa", *map(str, arguments)], cwd=cwd, env=environment,
                          capture_output=True, text=True, encoding="utf-8")


class AnovaTests(unittest.TestCase):
    def test_t190_pooled_interaction(self):
        result = anova(T190)
        self.assertEqual((result.ss_part, result.ss_op, result.ss_int, result.ss_e), (32, 8, 0, 8))
        self.assertEqual(result.p_int, 1.0)
        self.assertTrue(result.pooled)
        self.assertEqual((result.var_e, result.var_op, result.var_part, result.var_int),
                         (Fraction(8, 5), Fraction(8, 5), Fraction(38, 5), 0))
        self.assertAlmostEqual(percent_grr(result), 54.43, places=2)
        self.assertEqual(distinct_categories(result), 2)

    def test_t191_kept_interaction(self):
        result = anova(T191)
        self.assertEqual((result.ss_part, result.ss_op, result.ss_int, result.ss_e), (0, 0, 8, 2))
        self.assertAlmostEqual(result.p_int, 0.0161, places=4)
        self.assertFalse(result.pooled)
        self.assertEqual((result.var_e, result.var_int, result.var_op, result.var_part),
                         (Fraction(1, 2), Fraction(15, 4), 0, 0))
        self.assertEqual(percent_grr(result), 100)
        self.assertEqual(distinct_categories(result), 0)

    def test_t192_all_values_equal(self):
        result = anova(table(("5", "5"), ("5", "5"), ("5", "5"), ("5", "5")))
        self.assertIsNone(percent_grr(result))
        self.assertIsNone(distinct_categories(result))
        self.assertEqual(verdict(percent_grr(result)), "판정 불가")

    def test_t192_no_cell_error_with_interaction(self):
        result = anova(table(("1", "1"), ("3", "3"), ("3", "3"), ("1", "1")))
        self.assertEqual(result.p_int, 0.0)
        self.assertEqual((result.var_e, result.var_int), (0, 4))

    def test_t193_f_tail(self):
        self.assertAlmostEqual(f_tail(1, 1, 1), 0.5, places=9)
        self.assertAlmostEqual(f_tail(2, 10, 3), 0.09536743, places=7)
        self.assertAlmostEqual(f_tail(1, 4, 16), 0.01613009, places=7)
        tail = f_tail(1, 4, 1000000)
        self.assertTrue(math.isfinite(tail))
        self.assertLess(tail, 1e-10)
        self.assertGreater(tail, 0)

    def test_t194_average_range(self):
        ev, av, pv = average_range(T190)
        self.assertAlmostEqual(ev, 1.7724, places=4)
        self.assertAlmostEqual(av, 1.1021, places=4)
        self.assertAlmostEqual(pv, 2.8284, places=4)

    def test_t195_verdict_boundaries(self):
        self.assertEqual([verdict(value) for value in (9.999, 10, 30, 30.001)],
                         ["허용", "조건부", "조건부", "부적합"])
        self.assertEqual((ndc_ok(4), ndc_ok(5), ndc_ok(None)), (False, True, None))

    def test_t196_observed_cpk(self):
        sigma = 6 / (6 * 1.33)
        self.assertAlmostEqual(observed_cpk(1.33, sigma, 0.5 * sigma), 1.1896, places=4)
        self.assertEqual(observed_cpk(1.33, sigma, 0), 1.33)


class StudyTests(unittest.TestCase):
    def test_t197_same_seed(self):
        gauge = SETTINGS.gauges["good"]
        first = build_study(random.Random(1), 10, 1, gauge, SETTINGS)
        second = build_study(random.Random(1), 10, 1, gauge, SETTINGS)
        self.assertEqual(first, second)
        self.assertEqual(sum(len(cell) for row in first for cell in row), 90)

    def test_t197_call_order(self):
        rng = LoggingRandom()
        gauge = Gauge(0.5, 0.25, 0.0)
        build_study(rng, 10, 2, gauge, SETTINGS)
        p, o, r = SETTINGS.parts, SETTINGS.operators, SETTINGS.trials
        expected = [(10, 2)] * p + [(0, 0.5)] * o + [(0, 0.0)] * (p * o) + [(0, 1.0)] * (p * o * r)
        self.assertEqual(rng.calls, expected)


class GuardTests(unittest.TestCase):
    def test_t198_inward_limits(self):
        self.assertEqual(tuple(map(str, acceptance_limits("7", "13", "1.5", 0.1))), ("7.150", "12.850"))
        self.assertIsNone(acceptance_limits("7", "13", "40", 0.1))
        self.assertEqual(tuple(map(str, acceptance_limits("7", "13", "0.5", 0.001))), ("7.001", "12.999"))

    def test_t199_counts(self):
        tally = Tally()
        tally.add([("13.100", "12.900"), ("12.900", "13.100"), ("10.000", "10.000"), ("13.100", "13.200")], ITEM,
                  acceptance_limits(ITEM.lsl, ITEM.usl, "0", 0.1))
        self.assertEqual((tally.true_defects, tally.false_accepts, tally.true_good, tally.false_rejects),
                         (2, 1, 2, 1))

    def test_t199_zero_denominators(self):
        limits = acceptance_limits(ITEM.lsl, ITEM.usl, "0", 0.1)
        good = Tally()
        good.add([("10.000", "10.000")], ITEM, limits)
        bad = Tally()
        bad.add([("13.100", "13.100")], ITEM, limits)
        self.assertIsNone(good.false_accept)
        self.assertIsNone(bad.false_reject)
        limit = Fraction(5, 100)
        self.assertIsNone(select_guard([("0", good.false_accept, good.false_reject)], limit))
        self.assertIsNone(select_guard([("0", bad.false_accept, bad.false_reject)], limit))

    def test_t200_selection(self):
        rows = [("0", Fraction(6, 100), Fraction(1, 100)), ("1", Fraction(5, 100), Fraction(3, 100)),
                ("2", Fraction(5, 100), Fraction(3, 100)), ("3", Fraction(1, 100), Fraction(9, 100))]
        self.assertEqual(select_guard(rows, Fraction(5, 100)), "1")
        self.assertIsNone(select_guard([(row[0], Fraction(6, 100), row[2]) for row in rows], Fraction(5, 100)))

    def test_t201_holdout(self):
        limit = Fraction(5, 100)
        self.assertEqual(holdout_result("1", Tally(100, 5, 10, 0), limit), "확인")
        self.assertEqual(holdout_result("1", Tally(100, 6, 10, 0), limit), "미달")
        self.assertEqual(holdout_result("1", Tally(0, 0, 10, 0), limit), "미달")
        self.assertEqual(holdout_result(None, Tally(), limit), "검증할 선택 없음")

    def test_t249_operator_offsets(self):
        self.assertEqual([round(value, 9) for value in operator_offsets(3, 0.15, 1)], [-0.15, 0, 0.15])
        self.assertEqual([round(value, 9) for value in operator_offsets(2, 0.15, 1)], [-0.15, 0.15])

    def test_t249_same_truth_and_operator_order(self):
        offsets = operator_offsets(3, 0.3, PROCESS.sigma)
        pairs = fixed_operator_pairs(5, 30, PROCESS, offsets, 0.1)
        plain = sample_pairs(5, 30, PROCESS, 0.1)
        self.assertEqual([len(group) for group in pairs], [10, 10, 10])
        for index in range(3):
            self.assertEqual([truth for truth, _ in pairs[index]], [truth for truth, _ in plain[index::3]])

    def test_t249_offset_reaches_measurement(self):
        process = Process(ITEM, 10.0, 1.0, 0.0, 0.0)
        pairs = fixed_operator_pairs(5, 3000, process, [-1.0, 0.0, 1.0], 1e-9)
        differences = [sum(float(measured) - float(truth) for truth, measured in group) / len(group)
                       for group in pairs]
        self.assertEqual([round(value) for value in differences], [-1, 0, 1])


class ConfigTests(unittest.TestCase):
    def invalid(self, **changes):
        with tempfile.TemporaryDirectory() as folder:
            result = run_cli(small_config(folder, **changes), cwd=folder)
            self.assertEqual(result.returncode, 3, str(changes) + result.stderr)
            self.assertFalse((Path(folder) / "reports").exists())

    def test_t202_invalid_values(self):
        gauges = copy.deepcopy(RAW["gauges"])
        cases = [
            {"parts": 11}, {"parts": True}, {"trials": 4}, {"operators": 1}, {"products": 10 ** 400},
            {"study_seed": 2 ** 31}, {"max_false_accept": float("nan")}, {"max_false_accept": 2},
            {"guard_multipliers": ["1", "0"]}, {"guard_multipliers": ["1", "1.0"]}, {"guard_multipliers": []},
            {"guard_multipliers": [1]}, {"dev_seeds": "5-1"}, {"dev_seeds": "abc"}, {"dev_seeds": "-1-3"},
            {"holdout_seeds": "1-2"}, {"gauges": {}},
            {"gauges": {"Bad-Name": gauges["good"]}},
            {"gauges": {"good": dict(gauges["good"], extra=1)}},
            {"gauges": {"good": dict(gauges["good"], repeatability=0)}},
            {"gauges": {"good": dict(gauges["good"], operator=-1)}},
            {"gauges": {"good": dict(gauges["good"], operator=10 ** 400)}},
            {"gauges": {"good": dict(gauges["good"], operator=True)}},
        ]
        for changes in cases:
            with self.subTest(changes=str(changes)[:60]):
                self.invalid(**changes)

    def test_t202_missing_and_extra_keys(self):
        with tempfile.TemporaryDirectory() as folder:
            path = small_config(folder)
            data = json.loads(path.read_text(encoding="utf-8"))
            del data["parts"]
            path.write_text(json.dumps(data), encoding="utf-8")
            self.assertEqual(run_cli(path, cwd=folder).returncode, 3)
        self.invalid(extra=1)

    def test_t202_plain_generator_exit_2(self):
        with tempfile.TemporaryDirectory() as folder:
            config = small_config(folder, generator=str(ROOT / "recipes" / "generator.json"))
            result = run_cli(config, cwd=folder)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertFalse((Path(folder) / "reports").exists())

    def test_parse_seeds(self):
        self.assertEqual(parse_seeds("3-5"), range(3, 6))
        self.assertIsNone(parse_seeds(5))


class ReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.config = small_config(cls.folder.name)
        result = run_cli(cls.config, cwd=cls.folder.name)
        assert result.returncode == 0, result.stderr
        cls.reports = Path(cls.folder.name) / "reports"

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def rows(self, name):
        with (self.reports / name).open(encoding="utf-8-sig", newline="") as source:
            return list(csv.DictReader(source))

    def test_t203_repeat_byte_for_byte(self):
        names = ("msa_study.csv", "msa_grr.csv", "msa_guard.csv")
        with tempfile.TemporaryDirectory() as folder:
            result = run_cli(small_config(folder), cwd=folder)
            self.assertEqual(result.returncode, 0, result.stderr)
            for name in names:
                self.assertEqual((Path(folder) / "reports" / name).read_bytes(), (self.reports / name).read_bytes())

    def test_t250_headers(self):
        for name, columns in (("msa_study.csv", STUDY_COLUMNS), ("msa_grr.csv", GRR_COLUMNS),
                              ("msa_guard.csv", GUARD_COLUMNS)):
            self.assertEqual(tuple(self.rows(name)[0]), columns)

    def test_t250_sections_and_order(self):
        rows = self.rows("msa_guard.csv")
        self.assertEqual(rows[0]["section"], "notice")
        for gauge in RAW["gauges"]:
            selected = [row for row in rows if row["gauge"] == gauge]
            sections = [row["section"] for row in selected]
            self.assertEqual(sections.count("development"), len(RAW["guard_multipliers"]))
            self.assertEqual(sections.count("selection"), 1)
            self.assertEqual(sections.count("holdout"), 1)
            self.assertIn("operator_sensitivity", sections)
        self.assertEqual([row["gauge"] for row in self.rows("msa_grr.csv")], list(RAW["gauges"]))

    def test_t250_blank_ndc_keeps_ndc_ok_blank(self):
        flat = table(("5", "5"), ("5", "5"), ("5", "5"), ("5", "5"))
        row = grr_row("flat", flat, anova(flat), 6.0, PROCESS, 1.33)
        self.assertEqual((row["ndc"], row["ndc_ok"], row["pct_grr"], row["verdict"]), ("", "", "", "판정 불가"))

    def test_t250_pool_flag_values(self):
        for row in self.rows("msa_grr.csv"):
            self.assertIn(row["pooled"], ("0", "1"))


class RealConfigTests(unittest.TestCase):
    def test_t204_existing_files_unchanged(self):
        recipes = sorted((ROOT / "recipes").glob("*.json"))
        before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in recipes}
        with tempfile.TemporaryDirectory() as folder:
            config = small_config(folder)
            self.assertEqual(run_cli(config, cwd=folder).returncode, 0)
            self.assertEqual(sorted(path.name for path in (Path(folder) / "reports").iterdir()),
                             ["msa_grr.csv", "msa_guard.csv", "msa_study.csv"])
        self.assertEqual(before, {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in recipes})

    def test_gauge_noise_uses_all_terms(self):
        gauge = Gauge(0.3, 0.4, 0.0)
        self.assertAlmostEqual(noise_sigma(gauge, 2.0), 1.0)

    def test_invalid_settings_collects_location(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(MsaError) as caught:
                load_settings(small_config(folder, parts=11))
        self.assertIn("$.parts", str(caught.exception))


if __name__ == "__main__":
    unittest.main()

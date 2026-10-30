from fractions import Fraction
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from src.equipment import load_equipment
from src.evaluate import aggregate, evaluate, holdout_verdict, parse_seeds, run_metrics, select_rule
from src.recipe import load_recipe
from src.summary import build_analysis
from tests.test_restart import RECIPE, RESTART_EQUIPMENT, leak, prepared, restart


ROOT = Path(__file__).resolve().parents[1]
BASELINE_CONFIG = ROOT / "recipes" / "generator.json"


def cli(directory, *arguments):
    return subprocess.run(["py", "-m", "src.evaluate", *arguments], cwd=directory, capture_output=True,
                          env={**os.environ, "PYTHONPATH": str(ROOT), "PYTHONIOENCODING": "utf-8"})


def metrics(detection, delay, false_stops, median_unfinished=20):
    return {"detection_rate": Fraction(detection), "mean_delay": Fraction(delay),
            "mean_false_stops": Fraction(false_stops), "unfinished_median": Fraction(median_unfinished)}


class MetricTests(unittest.TestCase):
    def test_t62_hand_written_true_and_false_stops(self):
        models = load_recipe(RECIPE).models
        book = load_equipment(RESTART_EQUIPMENT, models)
        events = prepared("abcdef") + [
            leak(100, "a", "PASS", "LEAK-2"), leak(101, "b", "FAIL", "LEAK-2"),
            leak(102, "c", "PASS", "LEAK-2"), leak(103, "d", "FAIL", "LEAK-2"),
            restart(104, "FIXED", "LEAK-2"),
            leak(105, "e", "FAIL", "LEAK-1"), leak(106, "f", "FAIL", "LEAK-1"),
        ]
        run = run_metrics(build_analysis(events, models, book), {"LEAK-2"}, set())
        self.assertEqual((run.true_stops, run.false_stops, run.detected, run.delay_sum), (1, 1, 1, 4))
        self.assertEqual(aggregate([run], 1)["stop_precision"], Fraction(1, 2))

    def test_t62_repaired_equipment_stopping_again_is_false(self):
        models = load_recipe(RECIPE).models
        book = load_equipment(RESTART_EQUIPMENT, models)
        events = prepared("abcd") + [
            leak(100, "a", "FAIL", "LEAK-2"), leak(101, "b", "FAIL", "LEAK-2"), restart(102, "FIXED", "LEAK-2"),
            leak(103, "c", "FAIL", "LEAK-2"), leak(104, "d", "FAIL", "LEAK-2"),
        ]
        run = run_metrics(build_analysis(events, models, book), {"LEAK-2"}, set())
        self.assertEqual((run.true_stops, run.false_stops, run.delay_sum), (1, 1, 2))

    def test_t63_reproduces_the_prior_measurement(self):
        _, rule_metrics, _ = evaluate(BASELINE_CONFIG, range(30), [(3, 2)], 500)
        result = rule_metrics[3, 2]
        self.assertEqual(result["detection_rate"], 1)
        self.assertEqual(result["false_stop_runs"], 25)
        self.assertEqual(round(float(result["mean_false_stops"]), 2), 1.57)
        self.assertEqual(result["full_outage_runs"], 14)
        self.assertEqual((result["unfinished_min"], result["unfinished_median"], result["unfinished_max"]), (10, 22, 417))
        self.assertEqual(round(float(result["mean_held"]), 2), 13.73)
        self.assertEqual(round(float(result["mean_normal_held"]), 2), 8.50)

    def test_detection_rate_denominator_is_runs(self):
        models = load_recipe(RECIPE).models
        book = load_equipment(RESTART_EQUIPMENT, models)
        events = prepared("ab") + [leak(20, "a", "FAIL", "LEAK-2"), leak(21, "b", "FAIL", "LEAK-2")]
        run = run_metrics(build_analysis(events, models, book), {"LEAK-2", "LEAK-3"}, set())
        self.assertEqual(aggregate([run], 2)["detection_rate"], 1)

    def test_several_faulty_equipment_are_refused(self):
        config = json.loads(BASELINE_CONFIG.read_text(encoding="utf-8-sig"))
        config.update(recipe=str(ROOT / "recipes" / config["recipe"]),
                      equipment=str(ROOT / "recipes" / config["equipment"]),
                      faulty_equipment={"LEAK-2": 0.5, "LEAK-3": 0.5})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "여러 대"):
                evaluate(path, range(1), [(3, 2)], 5)


class CommandTests(unittest.TestCase):
    def test_t64_same_command_same_reports(self):
        arguments = ("--seeds", "0-1", "--rules", "3:2,5:3", "--products", "40")
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(cli(directory, *arguments, "--out", "one").returncode, 0)
            self.assertEqual(cli(directory, *arguments, "--out", "two").returncode, 0)
            for suffix in ("rules", "runs"):
                one = (Path(directory) / "reports" / ("one_" + suffix + ".csv")).read_bytes()
                two = (Path(directory) / "reports" / ("two_" + suffix + ".csv")).read_bytes()
                self.assertEqual(one, two)
            text = (Path(directory) / "reports" / "one_rules.csv").read_text(encoding="utf-8-sig")
            self.assertIn("config_sha256", text)
            self.assertIn("selection", text)

    def test_t64_bad_arguments_exit_two_without_reports(self):
        for seeds, rules in (("0-1", "5:6"), ("5-3", "3:2"), ("0-1", "3:2,3:2"), ("x", "3:2"), ("0-1", "3")):
            with self.subTest(seeds=seeds, rules=rules), tempfile.TemporaryDirectory() as directory:
                result = cli(directory, "--seeds", seeds, "--rules", rules, "--out", "bad")
                self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
                self.assertFalse((Path(directory) / "reports").exists())

    def test_holdout_flag_never_selects(self):
        with tempfile.TemporaryDirectory() as directory:
            result = cli(directory, "--seeds", "0-1", "--rules", "3:2", "--products", "40", "--out", "h", "--holdout")
            self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
            text = (Path(directory) / "reports" / "h_rules.csv").read_text(encoding="utf-8-sig")
            self.assertNotIn("selection", text)

    def test_seed_range_includes_both_ends(self):
        self.assertEqual(list(parse_seeds("3-5")), [3, 4, 5])


class SelectionTests(unittest.TestCase):
    def test_t65_detection_and_delay_limits_exclude_rules(self):
        rules = {(3, 2): metrics("0.94", 5, 0), (5, 2): metrics("0.95", 11, 0), (5, 3): metrics("0.95", 10, 3)}
        self.assertEqual(select_rule(rules), (5, 3))

    def test_t65_ties_use_delay_then_median_then_window_then_fails(self):
        self.assertEqual(select_rule({(5, 2): metrics(1, 6, 1), (3, 2): metrics(1, 7, 1)}), (5, 2))
        self.assertEqual(select_rule({(5, 2): metrics(1, 6, 1, 30), (10, 3): metrics(1, 6, 1, 20)}), (10, 3))
        self.assertEqual(select_rule({(10, 4): metrics(1, 6, 1), (5, 3): metrics(1, 6, 1)}), (5, 3))
        self.assertEqual(select_rule({(5, 3): metrics(1, 6, 1), (5, 2): metrics(1, 6, 1)}), (5, 2))

    def test_t65_no_candidate_means_no_selection(self):
        self.assertIsNone(select_rule({(3, 2): metrics("0.5", 5, 0), (5, 2): metrics(1, 20, 0)}))

    def test_t66_holdout_verdict(self):
        self.assertEqual(holdout_verdict(metrics("0.96", 9, 0)), "확인")
        self.assertEqual(holdout_verdict(metrics("0.93", 9, 0)), "미확인")


if __name__ == "__main__":
    unittest.main()

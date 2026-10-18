"""T45 hand calculations below were fixed before implementing src.summary.

Four registered products: a(A) completes with all first PASS; b(B) completes
after LEAK first FAIL and one retest PASS; c(B) waits for two inspections;
d(A) is only registered and lacks three inspections. Two rejected rows:
d skips to P3 and a repeats LEAK without a request.
Thus first results=5, first FAIL=1 (1/5=0.2000), all results=6, all FAIL=1
(1/6=0.1667), FPY=1/4=0.2500, completed=2, missing inspections=5.
LEAK first FAIL=1/2=0.5000, all FAIL=1/3=0.3333; LIGHT=0/2; FINAL=0/1.
LEAK-2 has first/all FAIL=1/1; LEAK-1 first=0/1, all=0/2.
Input Pareto ties sort PRESERVE_DUP_RESULT then SEQ_SKIP, one row each.
"""

from dataclasses import replace
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

from src.equipment import load_equipment
from src.main import read_events
from src.recipe import load_recipe
from src.recipe_rules import EQUIPMENT_INPUT_COLUMNS
from src.summary import ASSUMPTION_NOTICE, SUMMARY_COLUMNS, build_analysis, build_summary, write_summary
from src.trace import build_trace


ROOT = Path(__file__).resolve().parents[1]


class SummaryTests(unittest.TestCase):
    def setUp(self):
        self.models = load_recipe(ROOT / "recipes/lamp_models_retest.json").models
        self.book = load_equipment(ROOT / "recipes/equipment.json", self.models)
        self.events = read_events(ROOT / "tests/fixtures/summary_events.csv", EQUIPMENT_INPUT_COLUMNS)

    def summary(self, events=None, meta=None):
        self.analysis = build_analysis(self.events if events is None else events, self.models, self.book)
        return build_summary(self.analysis, meta)

    def find(self, rows, section, key):
        return next(row for row in rows if row["section"] == section and row["key"] == key)

    def test_t45_hand_calculated_metrics_and_paretos(self):
        rows = self.summary()
        overall = self.find(rows, "inspection_metrics", "ALL")
        self.assertEqual(tuple(overall[name] for name in (
            "first_count", "first_fail_count", "first_fail_rate", "all_count",
            "all_fail_count", "all_fail_rate", "rejected_count", "unperformed_count",
        )), (5, 1, "0.2000", 6, 1, "0.1667", 1, 5))
        leak = self.find(rows, "inspection_metrics", "LEAK")
        self.assertEqual((leak["first_count"], leak["first_fail_count"], leak["first_fail_rate"],
                          leak["all_count"], leak["all_fail_count"], leak["all_fail_rate"]),
                         (2, 1, "0.5000", 3, 1, "0.3333"))
        self.assertEqual(self.find(rows, "inspection_metrics", "LIGHT")["first_fail_rate"], "0.0000")
        self.assertEqual(self.find(rows, "inspection_metrics", "FINAL")["all_count"], 1)
        leak_one = self.find(rows, "equipment_metrics", "LEAK-1")
        self.assertEqual((leak_one["first_count"], leak_one["all_count"], leak_one["all_fail_count"]), (1, 2, 0))
        leak_two = self.find(rows, "equipment_metrics", "LEAK-2")
        self.assertEqual((leak_two["first_fail_rate"], leak_two["all_fail_rate"]), ("1.0000", "1.0000"))
        self.assertEqual(self.find(rows, "product_metrics", "registered_count")["value"], 4)
        self.assertEqual(self.find(rows, "product_metrics", "fpy")["value"], "0.2500")
        self.assertEqual({row["key"]: row["count"] for row in rows if row["section"] == "status_distribution"},
                         {"완료": 2, "보류": 0, "폐기": 0, "검사 대기": 1, "공정 진행 중": 0, "등록": 1})
        quality = [row for row in rows if row["section"] == "quality_pareto"]
        self.assertEqual([(row["inspection"], row["equipment"], row["first_fail_count"], row["all_fail_count"])
                          for row in quality], [("LEAK", "LEAK-2", 1, 1)])
        errors = [row for row in rows if row["section"] == "input_error_pareto"]
        self.assertEqual([(row["key"], row["rule_id"], row["count"]) for row in errors],
                         [("PRESERVE_DUP_RESULT", "RULE_PRESERVE", 1), ("SEQ_SKIP", "RULE_SEQ", 1)])
        self.assertEqual(self.find(rows, "notice", "generation_assumption")["value"], ASSUMPTION_NOTICE)
        self.assertTrue(all(tuple(row) == SUMMARY_COLUMNS for row in rows))

    def test_t45_zero_denominators_and_injection_comparison(self):
        empty = self.summary([])
        self.assertEqual(self.find(empty, "product_metrics", "fpy")["value"], "")
        self.assertEqual(self.find(empty, "inspection_metrics", "ALL")["first_fail_rate"], "")
        self.assertFalse(any(row["section"] == "injection_comparison" for row in empty))
        rows = self.summary(meta={"normal_rows": 24, "injected_errors": {"SEQ_SKIP": 1, "PRESERVE_DUP_RESULT": 1}})
        comparison = self.find(rows, "injection_comparison", "SEQ_SKIP")
        self.assertEqual((comparison["normal_rows"], comparison["injected_count"], comparison["injection_rate"],
                          comparison["actual_rejections"]), (24, 1, "0.0417", 1))
        self.assertEqual(self.find(rows, "rejection_totals", "rejection_rate")["value"], "0.0769")

    def test_t46_stopped_equipment_causes_and_error_separation(self):
        events = read_events(ROOT / "data/sample_events_equipment.csv", EQUIPMENT_INPUT_COLUMNS)
        rows = self.summary(events)
        stop = self.find(rows, "equipment_stops", "LEAK-2")
        self.assertEqual((stop["state"], stop["seq"], stop["product_id"], stop["cause_seqs"], stop["rejected_count"]),
                         ("정지", "25", "T33_P3", "14;25", 2))
        self.assertEqual([item.seq for item in self.analysis.stops["LEAK-2"].fail_causes], ["14", "25"])
        self.assertNotIn("EQUIP_STOPPED", [row["key"] for row in rows if row["section"] == "input_error_pareto"])
        counts = {row["key"]: row["value"] for row in rows if row["section"] == "rejection_totals"}
        self.assertEqual((counts["rejected_rows"], counts["input_errors"], counts["equipment_stopped"],
                          counts["other_rejections"]), (7, 5, 2, 0))
        self.assertEqual(counts["rejected_rows"], counts["input_errors"] + counts["equipment_stopped"] + counts["other_rejections"])

    def test_t46_physical_order_is_independent_of_seq_and_retests(self):
        events = [dict(event) for event in self.events]
        for event in events:
            event["seq"] = "1"
        self.summary(events)
        self.assertEqual([record.row_index for record in self.analysis.first_inspections], [5, 8, 9, 13, 18])
        self.assertEqual([record.row_index for record in self.analysis.all_inspections], [5, 8, 9, 13, 15, 18])
        self.assertEqual(self.analysis.all_inspections[4].retest_number, 1)

    def test_t45_discarded_first_result_and_retest_fail_counts_are_preserved(self):
        events = read_events(ROOT / "data/sample_events_equipment.csv", EQUIPMENT_INPUT_COLUMNS)
        rows = self.summary([event for event in events if event["product_id"] == "T36"])
        leak = self.find(rows, "inspection_metrics", "LEAK")
        self.assertEqual((leak["first_count"], leak["first_fail_count"], leak["all_count"], leak["all_fail_count"]),
                         (1, 1, 3, 3))
        self.assertEqual(self.find(rows, "status_distribution", "폐기")["count"], 1)
        self.assertEqual(self.find(rows, "equipment_stops", "LEAK-1")["state"], "가동")

    def test_t45_quality_pareto_retains_fail_on_retest_only_equipment(self):
        events = [dict(event) for event in self.events if event["product_id"] == "b" and int(event["seq"]) <= 15]
        events[-1]["result"] = "FAIL"
        rows = self.summary(events)
        quality = [row for row in rows if row["section"] == "quality_pareto"]
        self.assertEqual([(row["inspection"], row["equipment"], row["first_fail_count"], row["all_fail_count"])
                          for row in quality], [("LEAK", "LEAK-2", 1, 1), ("LEAK", "LEAK-1", 0, 1)])

    def test_t45_analysis_works_without_retest_history(self):
        models = load_recipe(ROOT / "recipes/lamp_models.json").models
        events = [event for event in self.events if event["product_id"] == "a"][:-1]
        analysis = build_analysis(events, models, self.book)
        self.assertEqual(len(analysis.first_inspections), 3)
        self.assertEqual(len(analysis.all_inspections), 3)
        self.assertEqual(self.find(build_summary(analysis), "product_metrics", "fpy")["value"], "1.0000")

    def test_t49_unknown_reason_fails_before_any_write(self):
        analysis = build_analysis(self.events, self.models, self.book)
        analysis.decisions[-1] = replace(analysis.decisions[-1], reason="표에 없는 인위적 거절")
        with self.assertRaisesRegex(ValueError, "알 수 없는 거절 사유"):
            build_summary(analysis)

    def test_t45_missing_csv_values_remain_rejected_without_breaking_summary(self):
        # DictReader fills missing trailing CSV fields with None.
        missing = dict(seq="27", product_id="a", event="INSPECT", inspection=None,
                       result=None, model=None, equipment=None)
        rows = self.summary(self.events + [missing])
        self.assertEqual(self.find(rows, "input_error_pareto", "PRESERVE_COLUMNS")["count"], 1)
        self.assertEqual(self.find(rows, "rejection_totals", "rejected_rows")["value"], 3)
        self.assertEqual(self.find(rows, "inspection_metrics", "ALL")["rejected_count"], 2)
        self.assertEqual(self.find(rows, "equipment_metrics", "")["rejected_count"], 1)
        self.assertIsNone(self.analysis.events[-1]["inspection"])

    def test_t45_summary_csv_bytes_are_reproducible(self):
        rows = self.summary()
        with tempfile.TemporaryDirectory() as directory:
            stem = str(Path(directory) / "fixed")
            path = write_summary(stem, rows)
            first = path.read_bytes()
            self.assertEqual(write_summary(stem, rows).read_bytes(), first)

    def cli(self, directory, *options):
        return subprocess.run(
            ["py", "-m", "src.main", str(ROOT / "tests/fixtures/summary_events.csv"), *options],
            cwd=directory, capture_output=True,
            env={**os.environ, "PYTHONPATH": str(ROOT), "PYTHONIOENCODING": "utf-8"},
        )

    def test_t45_cli_summary_is_separate_and_legacy_four_reports_are_unchanged(self):
        options = ("--recipe", str(ROOT / "recipes/lamp_models_retest.json"),
                   "--equipment", str(ROOT / "recipes/equipment.json"))
        with tempfile.TemporaryDirectory() as directory:
            legacy = self.cli(directory, *options)
            self.assertEqual(legacy.returncode, 0, legacy.stderr.decode("utf-8"))
            original = {path.name: path.read_bytes() for path in (Path(directory) / "reports").glob("*.csv")}
            self.assertEqual(len(original), 4)
            summary = self.cli(directory, *options, "--summary")
            self.assertEqual(summary.returncode, 0, summary.stderr.decode("utf-8"))
            self.assertIn(ASSUMPTION_NOTICE, summary.stdout.decode("utf-8"))
            for name, content in original.items():
                self.assertEqual((Path(directory) / "reports" / name).read_bytes(), content)
            summary_path = Path(directory) / "reports/summary_events_summary.csv"
            self.assertTrue(summary_path.exists())
            self.assertEqual(len(list((Path(directory) / "reports").glob("*.csv"))), 5)
            first = summary_path.read_bytes()
            again = self.cli(directory, *options, "--summary")
            self.assertEqual(again.returncode, 0)
            self.assertEqual(again.stdout, summary.stdout)
            self.assertEqual(summary_path.read_bytes(), first)

    def test_t48_summary_requires_equipment_without_creating_reports(self):
        for options in (("--summary",), ("--recipe", str(ROOT / "recipes/lamp_models_retest.json"), "--summary")):
            with self.subTest(options=options), tempfile.TemporaryDirectory() as directory:
                result = self.cli(directory, *options)
                self.assertEqual(result.returncode, 2)
                self.assertFalse((Path(directory) / "reports").exists())


class TraceTests(unittest.TestCase):
    def setUp(self):
        self.models = load_recipe(ROOT / "recipes/lamp_models_retest.json").models
        self.book = load_equipment(ROOT / "recipes/equipment.json", self.models)
        self.events = read_events(ROOT / "data/sample_events_equipment.csv", EQUIPMENT_INPUT_COLUMNS)

    def test_t47_other_product_stop_causes_and_final_evidence(self):
        analysis = build_analysis(self.events, self.models, self.book)
        rows = build_trace(analysis, "T34")
        events = [row for row in rows if row["section"] == "event"]
        self.assertEqual([row["seq"] for row in events], ["26", "27", "28", "29", "30", "31"])
        self.assertTrue(all(row["product_id"] == "T34" for row in rows))
        rejected = events[-2]
        self.assertEqual((rejected["rule_id"], rejected["decision"], rejected["equipment"]),
                         ("RULE_EQUIP", "거절", "LEAK-2"))
        self.assertEqual((rejected["stop_seq"], rejected["stop_product_id"],
                          rejected["cause_seqs"], rejected["cause_product_ids"]),
                         ("25", "T33_P3", "14;25", "T33_T35_A;T33_P3"))
        self.assertEqual(rows[-1]["section"], "current_state")
        self.assertEqual(rows[-1]["state"], analysis.process.products["T34"].status)
        self.assertIn("PASS@31[LEAK-1]", rows[-1]["history"])
        self.assertIn("P4 미완료", rows[-1]["incomplete_reason"])

    def test_t47_duplicate_decreasing_seq_keeps_physical_order_and_causes(self):
        for index, event in enumerate(self.events):
            event["seq"] = str(3 - index % 3)
        analysis = build_analysis(self.events, self.models, self.book)
        rows = build_trace(analysis, "T34")
        events = [row for row in rows if row["section"] == "event"]
        self.assertEqual([row["row_index"] for row in events], [26, 27, 28, 29, 30, 31])
        self.assertEqual([row["seq"] for row in events], [self.events[i - 1]["seq"] for i in range(26, 32)])
        self.assertEqual((events[-2]["stop_row_index"], events[-2]["cause_row_indices"]), (25, "14;25"))

    def run_cli(self, directory, *options):
        return subprocess.run(
            ["py", "-m", "src.main", str(ROOT / "data/sample_events_equipment.csv"), *options],
            cwd=directory, capture_output=True,
            env={**os.environ, "PYTHONPATH": str(ROOT), "PYTHONIOENCODING": "utf-8"})

    def test_t47_cli_repeated_trace_and_summary_use_separate_files(self):
        options = ("--recipe", str(ROOT / "recipes/lamp_models_retest.json"),
                   "--equipment", str(ROOT / "recipes/equipment.json"), "--summary",
                   "--trace", "T34", "--trace", "T33_T35_A")
        with tempfile.TemporaryDirectory() as directory:
            run = self.run_cli(directory, *options)
            self.assertEqual(run.returncode, 0, run.stderr.decode("utf-8"))
            reports = Path(directory) / "reports"
            before = {path.name: path.read_bytes() for path in reports.iterdir()}
            self.assertEqual(len(before), 7)
            self.assertIn("sample_events_equipment_trace_T34.csv", before)
            self.assertIn("현재 상태의 근거", run.stdout.decode("utf-8"))
            self.assertEqual(self.run_cli(directory, *options).stdout, run.stdout)
            self.assertEqual({path.name: path.read_bytes() for path in reports.iterdir()}, before)
            for suffix in ("rows", "products", "rejections", "equipment"):
                name = "sample_events_equipment_" + suffix + ".csv"
                self.assertEqual(before[name], (ROOT / "reports" / name).read_bytes())

    def test_t48_unknown_trace_and_non_equipment_modes_create_no_reports(self):
        for options in (("--trace", "T34"),
                        ("--recipe", str(ROOT / "recipes/lamp_models_retest.json"), "--trace", "T34"),
                        ("--recipe", str(ROOT / "recipes/lamp_models_retest.json"),
                         "--equipment", str(ROOT / "recipes/equipment.json"), "--summary",
                         "--trace", "T34", "--trace", "NO_SUCH_PRODUCT")):
            with self.subTest(options=options), tempfile.TemporaryDirectory() as directory:
                result = self.run_cli(directory, *options)
                self.assertEqual(result.returncode, 2)
                self.assertFalse((Path(directory) / "reports").exists())


if __name__ == "__main__":
    unittest.main()

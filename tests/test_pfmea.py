import csv
from fractions import Fraction
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from src.equipment import load_equipment
from src.generate import load_setup
from src.pfmea import (
    INPUT_COLUMNS, PfmeaError, Reference, build_report, check_table, collect, effect_result, evidence_status,
    merge_counts, read_table, reference_value, resolve_reference, run, run_counts, scored_fields, METRICS,
)
from src.recipe import load_recipe
from src.recipe_rules import input_columns
from src.summary import build_analysis


ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "recipes" / "lamp_models_measured.json"
EQUIPMENT = ROOT / "recipes" / "equipment_measured.json"
CONFIG = ROOT / "recipes" / "generator_measured.json"
PLAIN_CONFIG = ROOT / "recipes" / "generator_restart.json"
TABLE = ROOT / "data" / "pfmea_lamp.csv"
MODELS = load_recipe(RECIPE).models
BOOK = load_equipment(EQUIPMENT, MODELS)
COLUMNS = input_columns(BOOK, True)
TEST_REFERENCE = "test:tests/test_measurement.py::GeneratorTests::test_t107_injections_match_rejections"
METRIC_REFERENCE = "metric:defect_escape"


class Rows:
    def __init__(self):
        self.rows = []

    def add(self, product_id, event, inspection="", result="", model="", equipment="", value=""):
        self.rows.append(dict(zip(COLUMNS, (str(len(self.rows) + 1), product_id, event, inspection, result, model,
                                            equipment, value))))
        return self

    def product(self, product_id):
        self.add(product_id, "REGISTER", model="B")
        return self.add(product_id, "P1").add(product_id, "P2")

    def leak(self, product_id, value, equipment):
        return self.add(product_id, "INSPECT", "LEAK", equipment=equipment, value=str(value))

    def light(self, product_id, value):
        return self.add(product_id, "INSPECT", "LIGHT", equipment="LIGHT-1", value=str(value))

    def retest(self, product_id):
        return self.add(product_id, "RETEST_REQUEST", "LEAK")

    def restart(self, equipment, result):
        return self.add("", "EQUIP_RESTART", result=result, equipment=equipment)

    def finish(self, product_id):
        self.add(product_id, "P3").add(product_id, "P4")
        return self.light(product_id, 10)

    def stops(self, equipment, values, prefix):
        for index, value in enumerate(values):
            self.product(prefix + str(index)).leak(prefix + str(index), value, equipment)
        return self

    def counts(self, defective=(), faulty=()):
        analysis = build_analysis(self.rows, MODELS, BOOK)
        self.assert_accepted(analysis)
        return run_counts(analysis, defective, sorted(faulty))

    @staticmethod
    def assert_accepted(analysis):
        rejected = [decision.reason for decision in analysis.decisions if not decision.accepted]
        assert not rejected, rejected


def fixture_f():
    rows = Rows()
    for product_id in "abcd":
        rows.product(product_id)
    rows.leak("a", 14, "LEAK-1").retest("a").leak("a", 10, "LEAK-1").finish("a")
    rows.leak("b", 14, "LEAK-2")
    rows.leak("c", 10, "LEAK-3").finish("c")
    rows.leak("d", 14, "LEAK-3")
    return rows


def table_row(**fields):
    row = dict.fromkeys(INPUT_COLUMNS, "")
    row.update(id="PF-01", failure_type="record", process_step="ALL", function_requirement="f", failure_mode="m",
               effect="e", cause="c", prevention_control="없음", detection_control="없음")
    row.update(fields)
    return row


def write_table(path, rows, columns=INPUT_COLUMNS):
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def run_cli(*arguments, cwd):
    environment = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, "-m", "src.pfmea", *map(str, arguments)], cwd=cwd, env=environment,
                          capture_output=True, encoding="utf-8")


def read_report(path):
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def full_action(**fields):
    row = dict(action="a", action_owner="o", action_goal="g", action_state="효과 확인", control_before="b",
               control_after="c", success_reference=METRIC_REFERENCE, success_op=">=", success_value="0.5",
               action_evidence=TEST_REFERENCE, residual_risk="r")
    row.update(fields)
    return row


class MetricTests(unittest.TestCase):
    def test_t115_product_metrics(self):
        counts, _ = fixture_f().counts(defective={"a", "b"})
        self.assertEqual(counts["defect_escape"], (1, 2))
        self.assertEqual(counts["all_defect_first_fail"], (2, 3))
        self.assertEqual(counts["leak_defect_first_fail"], (2, 2))
        self.assertEqual(counts["leak_defect_retest_pass"], (1, 1))
        self.assertEqual(counts["normal_reject"], (1, 2))

    def test_t116_equipment_metrics_over_two_runs(self):
        first = Rows().stops("LEAK-2", (10, 14, 14), "x").stops("LEAK-1", (14, 14), "y").counts(faulty={"LEAK-2"})
        second = Rows().stops("LEAK-2", (10,), "x").stops("LEAK-1", (10,), "y").counts(faulty={"LEAK-2"})
        total, _ = merge_counts([first, second])
        self.assertEqual(total["fault_stop_run"], (1, 2))
        self.assertEqual(total["fault_no_stop_run"], (1, 2))
        self.assertEqual(total["fault_stop_delay"], (3, 1))
        self.assertEqual(total["normal_stop_rate"], (1, 3))

    def test_t117_zero_denominators(self):
        counts, _ = Rows().stops("LEAK-1", (10,), "x").counts()
        for name in ("defect_escape", "all_defect_first_fail", "leak_defect_first_fail", "leak_defect_retest_pass",
                     "fault_stop_run", "fault_no_stop_run", "fault_stop_delay"):
            self.assertEqual(counts[name][1], 0, name)
        reference = Reference("metric:defect_escape", "metric", "product")
        self.assertIsNone(reference_value(reference, counts))

    def test_t118_fault_equipment_stays_out_of_normal_rate(self):
        rows = Rows().stops("LEAK-2", (14, 14), "x").restart("LEAK-2", "FIXED").stops("LEAK-2", (14, 14), "y")
        rows.stops("LEAK-1", (14, 14), "z").restart("LEAK-1", "NO_FAULT").stops("LEAK-1", (10,), "w")
        counts, _ = rows.counts(faulty={"LEAK-2"})
        self.assertEqual(counts["fault_stop_delay"], (2, 1))
        self.assertEqual(counts["normal_stop_rate"], (1, 3))

    def test_t119_totals_add_raw_counts(self):
        total, _ = merge_counts([({"defect_escape": (1, 1)}, {}), ({"defect_escape": (0, 9)}, {})])
        self.assertEqual(total["defect_escape"], (1, 10))
        config, _, recipe, book = load_setup(CONFIG)
        together, _ = collect(config, recipe, book, range(2), 20)
        one, _ = collect(config, recipe, book, range(1), 20)
        other, _ = collect(config, recipe, book, range(1, 2), 20)
        self.assertEqual(together["normal_reject"][1], one["normal_reject"][1] + other["normal_reject"][1])
        self.assertEqual(together["normal_reject"][1] + together["defect_escape"][1], 40)

    def test_t120_two_fault_equipment(self):
        counts, detail = Rows().stops("LEAK-2", (14, 14), "x").stops("LEAK-1", (10,), "y").counts(
            faulty={"LEAK-1", "LEAK-2"})
        self.assertEqual(counts["fault_stop_run"], (1, 2))
        self.assertEqual(counts["fault_no_stop_run"], (1, 2))
        self.assertEqual(counts["fault_stop_run"][0] + counts["fault_no_stop_run"][0], counts["fault_stop_run"][1])
        self.assertEqual(detail, {"LEAK-1": (0, 1), "LEAK-2": (1, 1)})


class TableTests(unittest.TestCase):
    def assert_error(self, location, *rows):
        with self.assertRaises(PfmeaError) as caught:
            check_table(list(rows), MODELS)
        self.assertIn(location, "\n".join(caught.exception.errors))

    def test_t121_table_errors(self):
        cases = (
            ("1.id", table_row(id="PF-1")),
            ("1.failure_type", table_row(failure_type="x")),
            ("1.process_step", table_row(process_step="P9")),
            ("1.severity", table_row(severity="8")),
            ("1.severity", table_row(severity="11", occurrence="1", detection="1")),
            ("1.severity", table_row(severity="01", occurrence="1", detection="1")),
            ("1.effect", table_row(effect="   ")),
            ("1.evidence_note", table_row(evidence=TEST_REFERENCE)),
            ("1.action_owner", table_row(action_owner="담당")),
            ("1.action_evidence", table_row(action="a", action_owner="o", action_goal="g", action_state="계획",
                                            action_evidence=TEST_REFERENCE)),
            ("1.action_evidence", table_row(action="a", action_owner="o", action_goal="g", action_state="완료",
                                            control_before="b", control_after="c")),
            ("1.success_value", table_row(**full_action(success_value=""))),
            ("1.residual_risk", table_row(**full_action(residual_risk=""))),
            ("1.post_severity", table_row(action="a", action_owner="o", action_goal="g", action_state="계획",
                                          post_severity="1", post_occurrence="1", post_detection="1")),
            ("1.post_severity", table_row(**full_action(post_severity="1", post_occurrence="1", post_detection="1"))),
            ("1.success_op", table_row(**full_action(success_op=">"))),
            ("1.success_reference", table_row(**full_action(success_reference=TEST_REFERENCE))),
            ("1.action_state", table_row(action_state="진행")),
        )
        for location, row in cases:
            with self.subTest(location=location, row=row["id"]):
                self.assert_error(location, row)
        self.assert_error("2.id", table_row(), table_row())
        self.assert_error("2.id", table_row(id="PF-02"), table_row(id="PF-01"))

    def test_t121_wrong_header_exits_3_without_reports(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            path = folder / "bad.csv"
            write_table(path, [table_row()], INPUT_COLUMNS[::-1])
            result = run_cli(path, "--seeds", "0-0", "--products", 5, "--config", CONFIG, cwd=folder)
            self.assertEqual(result.returncode, 3)
            self.assertFalse((folder / "reports").exists())

    def test_t122_reference_errors(self):
        bad = ("rule:RULE_NOPE", "reason:NOPE", "test:tests/test_none.py::A::b",
               "test:tests/test_measurement.py::GeneratorTests::test_nope", "metric:nope", "report:nope:a:capture_rate",
               "report:eval_lot_dev_containment:nope:capture_rate", "report:eval_lot_dev_containment:lot:stops",
               "kind:value", " rule:RULE_SEQ", "")
        for text in bad:
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    resolve_reference(text)
        self.assert_error("1.evidence", table_row(evidence="rule:RULE_SEQ;", evidence_note="n"))
        self.assert_error("1.evidence", table_row(evidence="rule:RULE_SEQ;rule:RULE_SEQ", evidence_note="n"))

    def test_t122_report_and_test_file_contents(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "reports").mkdir()
            (root / "tests").mkdir()
            good = ("section,method,capture_rate,value\nprovenance,generator_version,,1\nprovenance,seeds,,0-1\n"
                    "provenance,products,,5\nprovenance,config_sha256,,abc\n")

            def report(text):
                (root / "reports" / "r.csv").write_text(text, encoding="utf-8")

            report(good + "method,m,0.5,\n")
            self.assertEqual(resolve_reference("report:r:m:capture_rate", root).report[0], "0.5")
            report(good + "method,m,abc,\n")
            with self.assertRaisesRegex(ValueError, "소수 형식"):
                resolve_reference("report:r:m:capture_rate", root)
            report(good + "method,m,0.5,\nmethod,m,0.6,\n")
            with self.assertRaisesRegex(ValueError, "정확히 하나"):
                resolve_reference("report:r:m:capture_rate", root)
            report("section,method,capture_rate,value\nmethod,m,0.5,\n")
            with self.assertRaisesRegex(ValueError, "출처"):
                resolve_reference("report:r:m:capture_rate", root)
            report(good + "method,m\n")
            with self.assertRaisesRegex(ValueError, "칸이 없음"):
                resolve_reference("report:r:m:capture_rate", root)
            report(good + "method,m,,\n")
            self.assertEqual(resolve_reference("report:r:m:capture_rate", root).report[0], "")
            report(good.replace("capture_rate", "precision") + "method,m,0.5,\n")
            with self.assertRaisesRegex(ValueError, "없는 열"):
                resolve_reference("report:r:m:capture_rate", root)
            (root / "tests" / "test_x.py").write_text("def (:\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "구문 오류"):
                resolve_reference("test:tests/test_x.py::A::b", root)

    def test_t123_evidence_status(self):
        empty = {name: (0, 0) for name in METRICS}
        some = dict(empty, fault_stop_run=(1, 2))
        def references(*texts):
            return [resolve_reference(text) for text in texts]

        self.assertEqual(evidence_status("product", [], some), "근거 없음")
        self.assertEqual(evidence_status("product", references(TEST_REFERENCE), some), "근거 부족")
        self.assertEqual(evidence_status("product", references("metric:fault_stop_run"), some), "근거 부족")
        self.assertEqual(evidence_status("equipment", references("metric:fault_stop_run"), some), "연결됨")
        self.assertEqual(evidence_status("record", references("reason:SEQ_SKIP"), some), "연결됨")
        self.assertEqual(evidence_status("product", references(METRIC_REFERENCE), empty), "값 없음")
        self.assertEqual(evidence_status("record", references(METRIC_REFERENCE), some), "근거 부족")
        row = table_row(action="a", action_owner="o", action_goal="g", action_state="완료", control_before="b",
                        control_after="c", action_evidence=TEST_REFERENCE)
        current, _ = check_table([row], MODELS)["PF-01"]
        self.assertEqual(evidence_status("record", current, some), "근거 없음")

    def test_t124_scores(self):
        row = table_row(**full_action(post_severity="8", post_occurrence="2", post_detection="4"),
                        severity="8", occurrence="3", detection="4")
        check_table([row], MODELS)
        fields = scored_fields(row)
        self.assertEqual((fields["rpn"], fields["post_rpn"], fields["rpn_change"], fields["priority"],
                          fields["score_status"]), (96, 64, -32, "", "점수 입력"))
        other = scored_fields(table_row(severity="9", occurrence="1", detection="1"))
        self.assertEqual((other["rpn"], other["priority"]), (9, "우선"))
        waiting = scored_fields(table_row())
        self.assertEqual((waiting["rpn"], waiting["score_status"]), ("", "점수 대기"))


class EffectTests(unittest.TestCase):
    def test_t125_report_reference(self):
        reference = resolve_reference("report:eval_lot_dev_containment:since_restart:capture_rate")
        number, provenance, selection = reference.report
        self.assertEqual(number, "0.8525")
        self.assertEqual((provenance["generator_version"], provenance["seeds"]), ("1.3.0", "0-99"))
        self.assertEqual(selection, "기준 충족 방식 없음")
        self.assertEqual(effect_result(reference_value(reference, {}), ">=", "0.90"), "미충족")

    def test_t126_effect_uses_exact_values(self):
        self.assertEqual(effect_result(Fraction(2, 3), ">=", "0.6667"), "미충족")
        self.assertEqual(effect_result(Fraction(2, 3), "<=", "0.6667"), "충족")
        self.assertEqual(effect_result(None, ">=", "0.5"), "값 없음")


class CommandTests(unittest.TestCase):
    def test_t127_argument_errors_exit_2(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            for arguments in ((TABLE, "--config", PLAIN_CONFIG, "--seeds", "0-0", "--products", 5),
                              (TABLE, "--config", CONFIG, "--seeds", "x", "--products", 5),
                              (TABLE, "--config", CONFIG, "--seeds", "0-0", "--products", 0),
                              (folder / "none.csv", "--config", CONFIG, "--seeds", "0-0", "--products", 5)):
                self.assertEqual(run_cli(*arguments, cwd=folder).returncode, 2)
            self.assertFalse((folder / "reports").exists())

    def test_t113_t114_reports_are_reproducible(self):
        outputs = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as folder:
                folder = Path(folder)
                result = run_cli(TABLE, "--config", CONFIG, "--seeds", "0-1", "--products", 50, cwd=folder)
                self.assertEqual(result.returncode, 0, result.stderr)
                outputs.append({path.name: path.read_bytes() for path in (folder / "reports").iterdir()})
                report = read_report(folder / "reports" / "pfmea_lamp_report.csv")
                items = [row for row in report if row["section"] == "item"]
                self.assertEqual(len(items), 6)
                self.assertTrue(all(row["score_status"] == "점수 대기" and not row["rpn"] for row in items))
        self.assertEqual(set(outputs[0]), {"pfmea_lamp_report.csv", "pfmea_lamp_report.md"})
        self.assertEqual(outputs[0], outputs[1])


class AlternativeTests(unittest.TestCase):
    def test_t128_alternatives(self):
        report = run(TABLE, CONFIG, "0-1", 50)
        rows = [row for row in report if row["section"] == "alternative"]
        self.assertEqual(len(rows), 12)
        self.assertEqual({row["condition"] for row in rows}, {"current", "half", "none"})
        metrics = {row["reference"]: row for row in report if row["section"] == "metric"}
        for row in rows:
            if row["condition"] == "current":
                shared = metrics["metric:" + row["reference"]]
                self.assertEqual((row["numerator"], row["denominator"]), (shared["numerator"], shared["denominator"]))
        blocked = next(row for row in rows if row["condition"] == "none" and row["reference"] == "leak_defect_retest_pass")
        self.assertEqual((blocked["denominator"], blocked["value"]), (0, ""))


class SubmissionTests(unittest.TestCase):
    def test_t129_submitted_table(self):
        before = TABLE.read_bytes()
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            result = run_cli(TABLE, "--config", CONFIG, "--seeds", "0-29", "--products", 500, cwd=folder)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = read_report(folder / "reports" / "pfmea_lamp_report.csv")
            markdown = (folder / "reports" / "pfmea_lamp_report.md").read_text(encoding="utf-8")
        self.assertEqual(TABLE.read_bytes(), before)
        by_section = lambda name: [row for row in report if row["section"] == name]
        self.assertEqual(len(by_section("item")), 6)
        self.assertTrue(all(row["evidence_status"] == "연결됨" for row in by_section("item")))
        self.assertTrue(all(not row[column] for row in by_section("item")
                            for column in ("severity", "occurrence", "detection", "post_severity")))
        self.assertEqual(len(by_section("notice")), 4)
        self.assertEqual(len(by_section("metric")), 9)
        self.assertEqual(len(by_section("action")), 3)
        self.assertTrue(all(row["generator_version"] == "1.4.0" for row in by_section("metric")))
        for row in by_section("notice"):
            self.assertIn(row["text"], markdown)
        self.assertNotIn("AIAG", markdown)
        for reference in ("reason:SEQ_SKIP", "reason:RECIPE_UNKNOWN_STEP",
                          "test:tests/test_pfmea.py::AlternativeTests::test_t128_alternatives", "관측값: 0.8525"):
            self.assertIn(reference, markdown)
        self.assertFalse(any("AIAG" in value for row in report for value in row.values()))

    def test_table_file_reads_and_validates(self):
        rows = read_table(TABLE)
        self.assertEqual(sorted(check_table(rows, MODELS)), ["PF-0" + str(index) for index in range(1, 7)])


if __name__ == "__main__":
    unittest.main()

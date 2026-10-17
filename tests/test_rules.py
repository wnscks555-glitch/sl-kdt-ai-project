import copy
import csv
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from src.rules import Process


COMPLETE = "선택한 두 검사까지의 모의 흐름 완료"
RULE_IDS = {
    "RULE_SEQ",
    "RULE_INSP_PRE",
    "RULE_NOT_DONE",
    "RULE_FAIL_HOLD",
    "RULE_PRESERVE",
}
REPO_ROOT = Path(__file__).resolve().parents[1]


class ProcessRulesTests(unittest.TestCase):
    def setUp(self):
        self.process = Process()
        self.seq = 0

    def row(self, event, product_id="P", inspection="", result=""):
        self.seq += 1
        return {
            "seq": str(self.seq),
            "product_id": product_id,
            "event": event,
            "inspection": inspection,
            "result": result,
        }

    def apply(self, event, product_id="P", inspection="", result=""):
        return self.process.apply(self.row(event, product_id, inspection, result))

    def assembled(self, product_id="P"):
        for event in ("REGISTER", "PRE_ASSEMBLY", "MAIN_ASSEMBLY"):
            self.assertTrue(self.apply(event, product_id).accepted)

    def completed(self, product_id="P"):
        self.assembled(product_id)
        for inspection in ("LIGHT", "LEAK"):
            self.assertTrue(self.apply("INSPECT", product_id, inspection, "PASS").accepted)

    def assert_rejected_unchanged(self, row, rule_id):
        before = copy.deepcopy(self.process.products)
        decision = self.process.apply(row)
        self.assertFalse(decision.accepted)
        self.assertEqual(decision.rule_id, rule_id)
        self.assertTrue(decision.reason)
        self.assertEqual(self.process.products, before)
        return decision

    def test_t1_two_pass_results_complete_simulated_flow(self):
        self.assembled()
        self.assertTrue(self.apply("INSPECT", inspection="LIGHT", result="PASS").accepted)
        decision = self.apply("INSPECT", inspection="LEAK", result="PASS")
        self.assertTrue(decision.accepted)
        self.assertEqual(decision.rule_id, "RULE_FAIL_HOLD")
        self.assertEqual(decision.state, COMPLETE)
        product = self.process.products["P"]
        self.assertEqual(product.status, COMPLETE)
        self.assertEqual(product.inspections, {"LIGHT": "PASS", "LEAK": "PASS"})
        self.assertEqual(product.incomplete_reason, "")

    def test_t2_main_without_pre_is_rejected_and_registration_preserved(self):
        self.assertTrue(self.apply("REGISTER").accepted)
        decision = self.assert_rejected_unchanged(self.row("MAIN_ASSEMBLY"), "RULE_SEQ")
        self.assertEqual(decision.state, "등록")
        self.assertEqual(self.process.products["P"].stage, "REGISTER")
        self.assertEqual(self.process.products["P"].status, "등록")

    def test_t3_inspection_before_main_is_rejected_without_saving_result(self):
        self.assertTrue(self.apply("REGISTER").accepted)
        self.assertTrue(self.apply("PRE_ASSEMBLY").accepted)
        decision = self.assert_rejected_unchanged(
            self.row("INSPECT", inspection="LIGHT", result="PASS"), "RULE_INSP_PRE"
        )
        self.assertEqual(decision.state, "예비 조립")
        self.assertEqual(self.process.products["P"].inspections, {})

    def test_t4_missing_leak_keeps_inspection_pending(self):
        self.assembled()
        decision = self.apply("INSPECT", inspection="LIGHT", result="PASS")
        self.assertTrue(decision.accepted)
        self.assertEqual(decision.rule_id, "RULE_NOT_DONE")
        self.assertEqual(decision.state, "검사 대기")
        self.assertEqual(self.process.products["P"].incomplete_reason, "LEAK 미실시")

    def test_t5_leak_fail_holds_product(self):
        self.assembled()
        self.assertTrue(self.apply("INSPECT", inspection="LIGHT", result="PASS").accepted)
        decision = self.apply("INSPECT", inspection="LEAK", result="FAIL")
        self.assertTrue(decision.accepted)
        self.assertEqual(decision.rule_id, "RULE_FAIL_HOLD")
        self.assertEqual(decision.state, "보류")
        self.assertEqual(self.process.products["P"].incomplete_reason, "LEAK FAIL")

    def test_t6_later_pass_cannot_overwrite_fail_or_hold(self):
        self.assembled()
        self.apply("INSPECT", inspection="LIGHT", result="PASS")
        self.apply("INSPECT", inspection="LEAK", result="FAIL")
        decision = self.assert_rejected_unchanged(
            self.row("INSPECT", inspection="LEAK", result="PASS"), "RULE_PRESERVE"
        )
        self.assertEqual(decision.state, "보류")
        self.assertEqual(self.process.products["P"].inspections["LEAK"], "FAIL")

    def test_t7_later_fail_cannot_overwrite_pass_or_completion(self):
        self.completed()
        decision = self.assert_rejected_unchanged(
            self.row("INSPECT", inspection="LIGHT", result="FAIL"), "RULE_PRESERVE"
        )
        self.assertEqual(decision.state, COMPLETE)
        self.assertEqual(self.process.products["P"].inspections["LIGHT"], "PASS")

    def test_t8_duplicate_pre_assembly_preserves_entire_state(self):
        self.apply("REGISTER")
        self.apply("PRE_ASSEMBLY")
        decision = self.assert_rejected_unchanged(self.row("PRE_ASSEMBLY"), "RULE_PRESERVE")
        self.assertEqual(decision.state, "예비 조립")

    def test_t9_unregistered_and_invalid_result_preserve_all_products(self):
        self.completed("OTHER")
        decision = self.assert_rejected_unchanged(
            self.row("MAIN_ASSEMBLY", product_id="UNKNOWN"), "RULE_PRESERVE"
        )
        self.assertEqual(decision.state, "미등록")
        self.assertNotIn("UNKNOWN", self.process.products)
        self.assembled()
        self.assert_rejected_unchanged(
            self.row("INSPECT", inspection="LIGHT", result="OK"), "RULE_PRESERVE"
        )
        self.assertEqual(self.process.products["OTHER"].status, COMPLETE)
        self.assertEqual(self.process.products["P"].inspections, {})

    def test_preserve_invalid_values_and_duplicate_registration_or_main(self):
        self.assembled()
        cases = [
            {"seq": "0"},
            {"seq": "not-a-number"},
            {"product_id": ""},
            {"event": "UNKNOWN"},
            {"inspection": "UNKNOWN"},
            {"result": "OK"},
        ]
        for changes in cases:
            with self.subTest(changes=changes):
                row = self.row("INSPECT", inspection="LIGHT", result="PASS")
                row.update(changes)
                self.assert_rejected_unchanged(row, "RULE_PRESERVE")
        for event in ("REGISTER", "MAIN_ASSEMBLY"):
            with self.subTest(event=event):
                self.assert_rejected_unchanged(self.row(event), "RULE_PRESERVE")
        self.assert_rejected_unchanged(
            self.row("REGISTER", product_id="NEW", inspection="LIGHT", result="PASS"),
            "RULE_PRESERVE",
        )

    def test_fail_has_hold_priority_when_other_inspection_is_missing(self):
        self.assembled()
        decision = self.apply("INSPECT", inspection="LIGHT", result="FAIL")
        self.assertTrue(decision.accepted)
        self.assertEqual(decision.rule_id, "RULE_FAIL_HOLD")
        self.assertEqual(decision.state, "보류")
        self.assertIn("LIGHT FAIL", self.process.products["P"].incomplete_reason)
        self.assertIn("LEAK 미실시", self.process.products["P"].incomplete_reason)
        decision = self.apply("INSPECT", inspection="LEAK", result="PASS")
        self.assertTrue(decision.accepted)
        self.assertEqual(decision.rule_id, "RULE_FAIL_HOLD")
        self.assertEqual(decision.state, "보류")
        self.assertEqual(self.process.products["P"].incomplete_reason, "LIGHT FAIL")


class CommandLineTests(unittest.TestCase):
    def test_t10_identical_input_produces_identical_stdout_and_csv_bytes(self):
        sample = (REPO_ROOT / "data" / "sample_events.csv").resolve()
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT)
        env["PYTHONIOENCODING"] = "utf-8"
        snapshots = []
        with tempfile.TemporaryDirectory() as temporary:
            for run in ("first", "second"):
                cwd = Path(temporary) / run
                cwd.mkdir()
                result = subprocess.run(
                    ["py", "-m", "src.main", str(sample)],
                    cwd=cwd,
                    env=env,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
                reports = cwd / "reports"
                files = {path.name: path.read_bytes() for path in reports.glob("*.csv")}
                self.assertEqual(
                    set(files),
                    {
                        "sample_events_rows.csv",
                        "sample_events_products.csv",
                        "sample_events_rejections.csv",
                    },
                )
                for content in files.values():
                    self.assertTrue(content.startswith(b"\xef\xbb\xbf"))
                snapshots.append((result.stdout, files))
        self.assertEqual(snapshots[0], snapshots[1])
        output = snapshots[0][0].decode("utf-8")
        self.assertIn(COMPLETE, output)
        self.assertIn("RULE_PRESERVE", output)
        files = snapshots[0][1]
        rows = csv.DictReader(io.StringIO(files["sample_events_rows.csv"].decode("utf-8-sig")))
        self.assertEqual(
            rows.fieldnames,
            ["seq", "product_id", "input", "rule_id", "decision", "rejection_reason", "state"],
        )
        decisions = list(rows)
        with sample.open(encoding="utf-8-sig", newline="") as stream:
            expected_rows = list(csv.DictReader(stream))
        self.assertEqual([row["seq"] for row in decisions], [row["seq"] for row in expected_rows])
        self.assertEqual(len(decisions), len(expected_rows))
        self.assertIn("거절", {row["decision"] for row in decisions})
        products = csv.DictReader(io.StringIO(files["sample_events_products.csv"].decode("utf-8-sig")))
        self.assertEqual(products.fieldnames, ["product_id", "state", "incomplete_reason"])
        self.assertTrue(list(products))
        counts = csv.DictReader(io.StringIO(files["sample_events_rejections.csv"].decode("utf-8-sig")))
        self.assertEqual(counts.fieldnames, ["rule_id", "rejection_count"])
        counts_by_rule = {row["rule_id"]: int(row["rejection_count"]) for row in counts}
        self.assertEqual(set(counts_by_rule), RULE_IDS)
        self.assertEqual(counts_by_rule["RULE_NOT_DONE"], 0)
        self.assertEqual(counts_by_rule["RULE_FAIL_HOLD"], 0)
        self.assertEqual(
            sum(counts_by_rule.values()), sum(row["decision"] == "거절" for row in decisions)
        )


if __name__ == "__main__":
    unittest.main()

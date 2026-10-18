import copy
import csv
import hashlib
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from src.recipe import Inspection, ModelRecipe, RecipeError, load_recipe
from src.recipe_rules import RecipeProcess


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
DEFAULT_RECIPE = ROOT / "recipes" / "lamp_models.json"


class RecipeLoadingTests(unittest.TestCase):
    def test_t18_valid_models_and_original_content_digest(self):
        book = load_recipe(DEFAULT_RECIPE)
        self.assertEqual(book.models["A"].steps, ("P1", "P2", "P3", "P4", "P5"))
        self.assertEqual(
            [(item.id, item.after) for item in book.models["B"].inspections],
            [("LEAK", "P2"), ("LIGHT", "P4")],
        )
        self.assertEqual(book.sha256, hashlib.sha256(DEFAULT_RECIPE.read_bytes()).hexdigest())

    def test_t18_seven_expected_invalid_recipes_report_locations(self):
        cases = {
            "empty_steps.json": ("A.steps",),
            "duplicate_steps.json": ("A.steps[2]",),
            "duplicate_inspections.json": ("A.inspections[1].id",),
            "string_steps.json": ("A.steps",),
            "unknown_key.json": ("A.next",),
            "unknown_after.json": ("A.inspections[0].after",),
            "multiple_errors.json": ("A.steps", "A.next"),
        }
        for name, locations in cases.items():
            with self.subTest(name=name), self.assertRaises(RecipeError) as caught:
                load_recipe(FIXTURES / name)
            for location in locations:
                self.assertTrue(any(error.startswith(location + ":") for error in caught.exception.errors))

    def test_t18_structure_and_id_errors_are_all_reported(self):
        with self.assertRaises(RecipeError) as caught:
            load_recipe(FIXTURES / "invalid_structure.json")
        for location in (
            "bad", "bad.extra", "bad.steps[0]", "bad.steps[1]", "bad.steps[2]",
            "bad.inspections[0].id", "bad.inspections[0].after",
            "bad.inspections[0].next", "bad.inspections[1]", "B", "C.inspections",
            "D.steps", "D.inspections", "E.steps", "E.inspections", "F.inspections",
        ):
            with self.subTest(location=location):
                self.assertTrue(any(error.startswith(location + ":") for error in caught.exception.errors))

    def test_t18_invalid_json_root_and_missing_file(self):
        for name in ("invalid_json.json", "array_root.json", "empty_models.json", "missing.json"):
            with self.subTest(name=name), self.assertRaises(RecipeError) as caught:
                load_recipe(FIXTURES / name)
            self.assertTrue(all(error.startswith("$:") for error in caught.exception.errors))


class RecipeProcessTests(unittest.TestCase):
    def setUp(self):
        self.models = load_recipe(DEFAULT_RECIPE).models
        self.process = RecipeProcess(self.models)
        self.seq = 0
        self.register("OTHER", "B")
        self.accept("P1", "OTHER", rule_id="RULE_SEQ")

    def row(self, event, product_id="a", inspection="", result="", model=""):
        self.seq += 1
        return {
            "seq": str(self.seq), "product_id": product_id, "event": event,
            "inspection": inspection, "result": result, "model": model,
        }

    def accept(self, event, product_id="a", inspection="", result="", model="", rule_id=None):
        decision = self.process.apply(self.row(event, product_id, inspection, result, model))
        self.assertTrue(decision.accepted, decision)
        self.assertEqual(decision.reason, "")
        if rule_id is not None:
            self.assertEqual(decision.rule_id, rule_id)
        return decision

    def register(self, product_id="a", model="A"):
        decision = self.accept("REGISTER", product_id, model=model, rule_id="RULE_RECIPE")
        self.assertEqual(decision.state, "등록")
        return decision

    def steps(self, count, product_id="a"):
        for number in range(1, count + 1):
            self.accept("P" + str(number), product_id, rule_id="RULE_SEQ")

    def assert_rejected_unchanged(self, row, rule_id, reason=None):
        before = copy.deepcopy(self.process.products)
        decision = self.process.apply(row)
        self.assertFalse(decision.accepted)
        self.assertEqual(decision.rule_id, rule_id)
        self.assertTrue(decision.reason)
        if reason is not None:
            self.assertIn(reason, decision.reason)
        self.assertEqual(self.process.products, before)
        self.assertEqual(self.process.products["OTHER"].model, "B")
        self.assertEqual(self.process.products["OTHER"].completed_steps, 1)
        self.assertEqual(self.process.products["OTHER"].inspections, {})
        return decision

    def test_t11_model_a_completes_all_steps_and_required_inspections(self):
        self.register()
        self.assertEqual(self.process.products["a"].recipe, self.models["A"])
        self.steps(5)
        for inspection in ("LEAK", "LIGHT"):
            decision = self.accept("INSPECT", inspection=inspection, result="PASS", rule_id="RULE_NOT_DONE")
            self.assertEqual(decision.state, "검사 대기")
        decision = self.accept("INSPECT", inspection="FINAL", result="PASS", rule_id="RULE_FAIL_HOLD")
        self.assertEqual(decision.state, "레시피 모의 흐름 완료")
        product = self.process.products["a"]
        self.assertEqual(product.model, "A")
        self.assertEqual(product.completed_steps, 5)
        self.assertEqual(product.inspections, {"LEAK": "PASS", "LIGHT": "PASS", "FINAL": "PASS"})
        self.assertEqual(product.status, "레시피 모의 흐름 완료")
        self.assertEqual(product.incomplete_reason, "")

    def test_t12_interleaved_models_keep_independent_progress_and_inspections(self):
        self.register()
        self.register("b", "B")
        for event in ("P1", "P2", "P3", "P4"):
            self.accept(event, rule_id="RULE_SEQ")
            self.accept(event, "b", rule_id="RULE_SEQ")
        self.accept("INSPECT", "b", "LEAK", "PASS", rule_id="RULE_NOT_DONE")
        decision = self.accept("INSPECT", "b", "LIGHT", "PASS", rule_id="RULE_FAIL_HOLD")
        self.assertEqual(decision.state, "레시피 모의 흐름 완료")
        self.assertEqual(self.process.products["b"].completed_steps, 4)
        self.assertEqual(self.process.products["b"].inspections, {"LEAK": "PASS", "LIGHT": "PASS"})
        self.assertEqual(self.process.products["a"].status, "공정 진행 중(P4 완료)")
        self.assertEqual(self.process.products["a"].inspections, {})
        self.assertEqual(
            self.process.products["a"].incomplete_reason,
            "P5 미완료; LEAK 미실시; LIGHT 미실시; FINAL 미실시",
        )

    def test_t13_skipped_step_is_rejected_then_correct_next_step_is_accepted(self):
        self.register()
        self.accept("P1", rule_id="RULE_SEQ")
        decision = self.assert_rejected_unchanged(self.row("P3"), "RULE_SEQ", "P2 미완료")
        self.assertEqual(decision.state, "공정 진행 중(P1 완료)")
        self.assertEqual(self.process.products["a"].completed_steps, 1)
        self.accept("P2", rule_id="RULE_SEQ")
        self.assertEqual(self.process.products["a"].status, "공정 진행 중(P2 완료)")

    def test_t14_each_inspection_requires_its_own_after_step(self):
        self.register()
        self.steps(2)
        self.assert_rejected_unchanged(
            self.row("INSPECT", inspection="LEAK", result="PASS"), "RULE_INSP_PRE", "P3 미완료"
        )
        self.register("c")
        self.steps(4, "c")
        self.assert_rejected_unchanged(
            self.row("INSPECT", "c", "LIGHT", "PASS"), "RULE_INSP_PRE", "P5 미완료"
        )
        self.assertEqual(self.process.products["a"].inspections, {})
        self.assertEqual(self.process.products["c"].inspections, {})

    def test_t15_midprocess_pass_and_remaining_final_inspection(self):
        self.register()
        self.steps(3)
        decision = self.accept("INSPECT", inspection="LEAK", result="PASS", rule_id="RULE_NOT_DONE")
        self.assertEqual(decision.state, "공정 진행 중(P3 완료)")
        self.accept("P4", rule_id="RULE_SEQ")
        self.accept("P5", rule_id="RULE_SEQ")
        self.accept("INSPECT", inspection="LIGHT", result="PASS", rule_id="RULE_NOT_DONE")
        self.assertEqual(self.process.products["a"].status, "검사 대기")
        self.assertEqual(self.process.products["a"].incomplete_reason, "FINAL 미실시")

    def test_t16_fail_blocks_next_step_and_cannot_be_replaced_by_pass(self):
        self.register()
        self.steps(3)
        decision = self.accept("INSPECT", inspection="LEAK", result="FAIL", rule_id="RULE_FAIL_HOLD")
        self.assertEqual(decision.state, "보류")
        self.assert_rejected_unchanged(self.row("P4"), "RULE_FAIL_HOLD")
        self.assert_rejected_unchanged(
            self.row("INSPECT", inspection="LEAK", result="PASS"), "RULE_PRESERVE"
        )
        product = self.process.products["a"]
        self.assertEqual(product.completed_steps, 3)
        self.assertEqual(product.inspections, {"LEAK": "FAIL"})
        self.assertEqual(product.status, "보류")
        self.assertEqual(product.incomplete_reason, "P4 미완료; P5 미완료; LEAK FAIL; LIGHT 미실시; FINAL 미실시")

    def test_t16b_first_result_for_other_inspection_is_allowed_during_hold(self):
        self.register()
        self.steps(5)
        self.accept("INSPECT", inspection="LIGHT", result="FAIL", rule_id="RULE_FAIL_HOLD")
        decision = self.accept("INSPECT", inspection="FINAL", result="PASS", rule_id="RULE_FAIL_HOLD")
        self.assertEqual(decision.state, "보류")
        self.assertEqual(self.process.products["a"].inspections, {"LIGHT": "FAIL", "FINAL": "PASS"})
        self.assertEqual(self.process.products["a"].incomplete_reason, "LEAK 미실시; LIGHT FAIL")

    def test_t17_unknown_model_step_or_model_specific_inspection(self):
        decision = self.assert_rejected_unchanged(self.row("REGISTER", "c", model="C"), "RULE_RECIPE")
        self.assertEqual(decision.state, "미등록")
        self.assertNotIn("c", self.process.products)
        self.register()
        self.assert_rejected_unchanged(self.row("P6"), "RULE_RECIPE")
        self.register("b", "B")
        self.assert_rejected_unchanged(self.row("INSPECT", "b", "FINAL", "PASS"), "RULE_RECIPE")

    def test_t19_model_b_does_not_allow_model_a_fifth_step(self):
        self.register("b", "B")
        self.steps(4, "b")
        decision = self.assert_rejected_unchanged(self.row("P5", "b"), "RULE_RECIPE")
        self.assertEqual(decision.state, "검사 대기")
        self.assertEqual(self.process.products["b"].completed_steps, 4)

    def test_t20_missing_registration_model_and_model_on_other_events(self):
        self.assert_rejected_unchanged(self.row("REGISTER", "new"), "RULE_RECIPE")
        self.assertNotIn("new", self.process.products)
        self.register()
        self.assert_rejected_unchanged(self.row("P1", model="A"), "RULE_PRESERVE")
        self.steps(3)
        self.assert_rejected_unchanged(
            self.row("INSPECT", inspection="LEAK", result="PASS", model="A"), "RULE_PRESERVE"
        )

    def test_t22_reregistration_cannot_change_model_or_progress(self):
        self.register()
        self.steps(2)
        self.assert_rejected_unchanged(self.row("REGISTER", model="B"), "RULE_PRESERVE", "이미 등록된 제품")
        self.assertEqual(self.process.products["a"].model, "A")
        self.assertEqual(self.process.products["a"].completed_steps, 2)
        self.assertEqual(self.process.products["a"].status, "공정 진행 중(P2 완료)")

    def test_duplicate_or_earlier_steps_and_second_inspection_preserve_completion(self):
        self.register()
        self.steps(5)
        for inspection in ("LEAK", "LIGHT", "FINAL"):
            self.accept("INSPECT", inspection=inspection, result="PASS")
        for event in ("P1", "P5"):
            with self.subTest(event=event):
                self.assert_rejected_unchanged(self.row(event), "RULE_PRESERVE")
        decision = self.assert_rejected_unchanged(
            self.row("INSPECT", inspection="LIGHT", result="FAIL"), "RULE_PRESERVE"
        )
        self.assertEqual(decision.state, "레시피 모의 흐름 완료")
        self.assertEqual(self.process.products["a"].inspections["LIGHT"], "PASS")

    def test_invalid_columns_seq_product_result_and_blank_field_rules_precede_recipe_lookup(self):
        self.register()
        self.steps(3)
        invalid_rows = []
        for seq in ("0", "-1", "1.5", " 1", "１", ""):
            row = self.row("INSPECT", inspection="NOT_IN_RECIPE", result="PASS")
            row["seq"] = seq
            invalid_rows.append(row)
        for product_id in ("", "   "):
            invalid_rows.append(self.row("P6", product_id))
        for result in ("OK", "pass", "PASS ", ""):
            invalid_rows.append(self.row("INSPECT", inspection="NOT_IN_RECIPE", result=result))
        invalid_rows.extend([
            self.row("REGISTER", "new", inspection="LEAK", result="PASS", model="C"),
            self.row("P6", inspection="LEAK", result="PASS"),
            self.row("P6", "UNKNOWN", model="A"),
            self.row("INSPECT", inspection="", result="PASS"),
            self.row(""),
        ])
        missing_column = self.row("P6")
        del missing_column["model"]
        invalid_rows.append(missing_column)
        extra_column = self.row("P6")
        extra_column["extra"] = ""
        invalid_rows.append(extra_column)
        missing_value = self.row("P6")
        missing_value["model"] = None
        invalid_rows.append(missing_value)
        for row in invalid_rows:
            with self.subTest(row=row):
                self.assert_rejected_unchanged(row, "RULE_PRESERVE")

    def test_rule_priority_registration_then_unregistered_then_recipe_then_hold_or_sequence(self):
        self.register()
        self.assert_rejected_unchanged(self.row("REGISTER", model="C"), "RULE_PRESERVE")
        self.assert_rejected_unchanged(self.row("REGISTER"), "RULE_PRESERVE")
        self.assert_rejected_unchanged(self.row("P6", "UNKNOWN"), "RULE_PRESERVE")
        self.assert_rejected_unchanged(
            self.row("INSPECT", "UNKNOWN", "NOT_IN_RECIPE", "PASS"), "RULE_PRESERVE"
        )
        self.register("b", "B")
        self.steps(2, "b")
        self.accept("INSPECT", "b", "LEAK", "FAIL", rule_id="RULE_FAIL_HOLD")
        self.assert_rejected_unchanged(self.row("P5", "b"), "RULE_RECIPE")
        self.assert_rejected_unchanged(self.row("INSPECT", "b", "FINAL", "PASS"), "RULE_RECIPE")
        self.assert_rejected_unchanged(self.row("P1", "b"), "RULE_PRESERVE")
        self.assert_rejected_unchanged(self.row("P4", "b"), "RULE_FAIL_HOLD")
        self.assert_rejected_unchanged(self.row("INSPECT", "b", "LIGHT", "PASS"), "RULE_INSP_PRE", "P4 미완료")

    def test_recipe_identifiers_are_matched_without_case_or_whitespace_normalization(self):
        for model in ("a", " A", "A "):
            with self.subTest(model=model):
                self.assert_rejected_unchanged(self.row("REGISTER", "new", model=model), "RULE_RECIPE")
        self.register()
        for event in ("p1", " P1", "P1 "):
            with self.subTest(event=event):
                self.assert_rejected_unchanged(self.row(event), "RULE_RECIPE")
        self.steps(3)
        for inspection in ("leak", " LEAK", "LEAK "):
            with self.subTest(inspection=inspection):
                self.assert_rejected_unchanged(self.row("INSPECT", inspection=inspection, result="PASS"), "RULE_RECIPE")

    def test_seq_labels_do_not_reorder_or_deduplicate_physical_rows(self):
        for row, rule_id in (
            ({"seq": "20", "product_id": "a", "event": "REGISTER", "inspection": "", "result": "", "model": "A"}, "RULE_RECIPE"),
            ({"seq": "3", "product_id": "a", "event": "P1", "inspection": "", "result": "", "model": ""}, "RULE_SEQ"),
            ({"seq": "3", "product_id": "a", "event": "P2", "inspection": "", "result": "", "model": ""}, "RULE_SEQ"),
        ):
            decision = self.process.apply(row)
            self.assertTrue(decision.accepted, decision)
            self.assertEqual(decision.rule_id, rule_id)
        row = self.row("P4")
        row["seq"] = "2"
        self.assert_rejected_unchanged(row, "RULE_SEQ", "P3 미완료")
        self.assertEqual(self.process.products["a"].completed_steps, 2)

    def test_recipe_array_order_and_early_all_pass_do_not_require_numeric_step_names(self):
        models = dict(self.models)
        models["CUSTOM"] = ModelRecipe(("FINISH", "START"), (Inspection("CHECK", "FINISH"),))
        self.process = RecipeProcess(models)
        self.register("OTHER", "B")
        self.accept("P1", "OTHER", rule_id="RULE_SEQ")
        self.register("a", "CUSTOM")
        self.assert_rejected_unchanged(self.row("START"), "RULE_SEQ", "FINISH 미완료")
        self.accept("FINISH", rule_id="RULE_SEQ")
        decision = self.accept("INSPECT", inspection="CHECK", result="PASS", rule_id="RULE_NOT_DONE")
        self.assertEqual(decision.state, "공정 진행 중(FINISH 완료)")
        self.assertEqual(self.process.products["a"].incomplete_reason, "START 미완료")
        decision = self.accept("START", rule_id="RULE_SEQ")
        self.assertEqual(decision.state, "레시피 모의 흐름 완료")
        self.assertEqual(self.process.products["a"].incomplete_reason, "")


class RecipeCommandLineTests(unittest.TestCase):
    INPUT = (
        "seq,product_id,event,inspection,result,model\n"
        "1,b,REGISTER,,,B\n"
        "2,b,P1,,,\n"
        "3,b,P2,,,\n"
        "4,b,INSPECT,LEAK,PASS,\n"
    )

    def run_cli(self, cwd, source, recipe=DEFAULT_RECIPE):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        env["PYTHONIOENCODING"] = "utf-8"
        command = ["py", "-m", "src.main", str(source)]
        if recipe is not None:
            command.extend(["--recipe", str(recipe)])
        return subprocess.run(command, cwd=cwd, env=env, capture_output=True)

    @staticmethod
    def report_bytes(cwd):
        return {path.name: path.read_bytes() for path in (cwd / "reports").glob("*.csv")}

    @staticmethod
    def csv_rows(content):
        return list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))

    def test_t18_invalid_recipe_stops_before_missing_input_and_writes_no_reports(self):
        names = (
            "empty_steps.json", "duplicate_steps.json", "duplicate_inspections.json",
            "string_steps.json", "unknown_key.json", "unknown_after.json",
            "multiple_errors.json", "invalid_structure.json", "invalid_json.json",
            "array_root.json", "empty_models.json", "missing.json",
        )
        with tempfile.TemporaryDirectory() as temporary:
            cwd = Path(temporary)
            for name in names:
                with self.subTest(name=name):
                    result = self.run_cli(cwd, cwd / "missing.csv", FIXTURES / name)
                    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
                    self.assertFalse((cwd / "reports").exists())
                    self.assertNotIn("[행별 판정]".encode("utf-8"), result.stdout)
                    if name == "multiple_errors.json":
                        self.assertIn(b"A.steps:", result.stderr)
                        self.assertIn(b"A.next:", result.stderr)

    def test_t21_same_csv_and_recipe_repeat_byte_identically_and_after_changes_decision(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "events.csv"
            source.write_text(self.INPUT, encoding="utf-8")
            snapshots = []
            for name in ("first", "second"):
                cwd = base / name
                cwd.mkdir()
                result = self.run_cli(cwd, source)
                self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
                self.assertEqual(result.stderr, b"")
                snapshots.append((result.stdout, self.report_bytes(cwd)))
            self.assertEqual(snapshots[0], snapshots[1])
            repeated = self.run_cli(cwd, source)
            self.assertEqual(repeated.returncode, 0)
            self.assertEqual((repeated.stdout, self.report_bytes(cwd)), snapshots[0])
            stdout, reports = snapshots[0]
            self.assertEqual(set(reports), {"events_rows.csv", "events_products.csv", "events_rejections.csv"})
            heading = stdout.decode("utf-8").splitlines()[0]
            self.assertIn(DEFAULT_RECIPE.as_posix(), heading)
            self.assertIn(hashlib.sha256(DEFAULT_RECIPE.read_bytes()).hexdigest()[:12], heading)
            self.assertEqual(self.csv_rows(reports["events_rows.csv"])[-1]["decision"], "허용")
            self.assertEqual(self.csv_rows(reports["events_products.csv"]), [{
                "product_id": "b", "model": "B", "state": "공정 진행 중(P2 완료)",
                "incomplete_reason": "P3 미완료; P4 미완료; LIGHT 미실시",
            }])
            self.assertEqual(
                self.csv_rows(reports["events_rejections.csv"]),
                [{"rule_id": rule, "rejection_count": "0"} for rule in (
                    "RULE_RECIPE", "RULE_SEQ", "RULE_INSP_PRE", "RULE_NOT_DONE", "RULE_FAIL_HOLD", "RULE_PRESERVE"
                )],
            )
            changed = self.run_cli(cwd, source, FIXTURES / "leak_after_p3.json")
            self.assertEqual(changed.returncode, 0, changed.stderr.decode("utf-8"))
            changed_reports = self.report_bytes(cwd)
            last = self.csv_rows(changed_reports["events_rows.csv"])[-1]
            self.assertEqual(last["decision"], "거절")
            self.assertEqual(last["rule_id"], "RULE_INSP_PRE")
            self.assertEqual(last["rejection_reason"], "P3 미완료")
            self.assertEqual(self.csv_rows(changed_reports["events_products.csv"])[0]["incomplete_reason"],
                             "P3 미완료; P4 미완료; LEAK 미실시; LIGHT 미실시")

    def test_header_mode_mismatch_and_input_errors_exit_two_without_reports(self):
        with tempfile.TemporaryDirectory() as temporary:
            cwd = Path(temporary)
            source = cwd / "events.csv"
            source.write_text(self.INPUT, encoding="utf-8")
            for csv_path, recipe in (
                (source, None), (ROOT / "data" / "sample_events.csv", DEFAULT_RECIPE),
                (cwd / "missing.csv", DEFAULT_RECIPE),
            ):
                with self.subTest(csv_path=csv_path, recipe=recipe):
                    result = self.run_cli(cwd, csv_path, recipe)
                    self.assertEqual(result.returncode, 2)
                    self.assertFalse((cwd / "reports").exists())

    def test_csv_physical_order_and_malformed_rows_are_reported_without_state_changes(self):
        text = (
            "seq,product_id,event,inspection,result,model\n"
            "9,a,REGISTER,,,A\n"
            "2,a,P1,,,\n"
            "2,a,P2,,,\n"
            "1,a,P3,,,EXTRA,EXTRA\n"
            "1,a,P3,,\n"
        )
        with tempfile.TemporaryDirectory() as temporary:
            cwd = Path(temporary)
            source = cwd / "events.csv"
            source.write_text(text, encoding="utf-8")
            result = self.run_cli(cwd, source)
            self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
            reports = self.report_bytes(cwd)
            rows = self.csv_rows(reports["events_rows.csv"])
            self.assertEqual([row["seq"] for row in rows], ["9", "2", "2", "1", "1"])
            self.assertEqual([row["rule_id"] for row in rows[-2:]], ["RULE_PRESERVE", "RULE_PRESERVE"])
            self.assertEqual([row["state"] for row in rows[-2:]], ["공정 진행 중(P2 완료)"] * 2)
            self.assertEqual(self.csv_rows(reports["events_products.csv"])[0]["state"], "공정 진행 중(P2 완료)")

    def test_sample_v2_matches_expected_products_and_rejection_counts(self):
        remaining_a = "P3 미완료; P4 미완료; P5 미완료; LEAK 미실시; LIGHT 미실시; FINAL 미실시"
        remaining_p4 = "P5 미완료; LEAK 미실시; LIGHT 미실시; FINAL 미실시"
        registered_a = "P1 미완료; P2 미완료; " + remaining_a
        expected = {
            "T11": ("A", "레시피 모의 흐름 완료", ""),
            "T12_A": ("A", "공정 진행 중(P4 완료)", remaining_p4),
            "T12_B": ("B", "레시피 모의 흐름 완료", ""),
            "T13": ("A", "공정 진행 중(P2 완료)", remaining_a),
            "T14_LEAK": ("A", "공정 진행 중(P2 완료)", remaining_a),
            "T14_LIGHT": ("A", "공정 진행 중(P4 완료)", remaining_p4),
            "T15": ("A", "검사 대기", "FINAL 미실시"),
            "T16": ("A", "보류", "P4 미완료; P5 미완료; LEAK FAIL; LIGHT 미실시; FINAL 미실시"),
            "T16B": ("A", "보류", "LEAK 미실시; LIGHT FAIL"),
            "T17_A": ("A", "등록", registered_a),
            "T17_B": ("B", "등록", "P1 미완료; P2 미완료; P3 미완료; P4 미완료; LEAK 미실시; LIGHT 미실시"),
            "T19": ("B", "검사 대기", "LEAK 미실시; LIGHT 미실시"),
            "T20": ("A", "등록", registered_a),
            "T22": ("A", "공정 진행 중(P2 완료)", remaining_a),
        }
        with tempfile.TemporaryDirectory() as temporary:
            cwd = Path(temporary)
            result = self.run_cli(cwd, ROOT / "data" / "sample_events_v2.csv")
            self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
            reports = self.report_bytes(cwd)
            products = self.csv_rows(reports["sample_events_v2_products.csv"])
            self.assertEqual({row["product_id"]: (row["model"], row["state"], row["incomplete_reason"])
                              for row in products}, expected)
            rows = self.csv_rows(reports["sample_events_v2_rows.csv"])
            self.assertEqual(len(rows), 76)
            self.assertEqual(sum(row["decision"] == "허용" for row in rows), 64)
            self.assertEqual(self.csv_rows(reports["sample_events_v2_rejections.csv"]), [
                {"rule_id": "RULE_RECIPE", "rejection_count": "5"},
                {"rule_id": "RULE_SEQ", "rejection_count": "1"},
                {"rule_id": "RULE_INSP_PRE", "rejection_count": "2"},
                {"rule_id": "RULE_NOT_DONE", "rejection_count": "0"},
                {"rule_id": "RULE_FAIL_HOLD", "rejection_count": "1"},
                {"rule_id": "RULE_PRESERVE", "rejection_count": "3"},
            ])


if __name__ == "__main__":
    unittest.main()

import copy
import csv
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from src.recipe import RecipeError, load_recipe
from src.recipe_rules import RecipeProcess


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
RECIPE = ROOT / "recipes" / "lamp_models_retest.json"
STAGE_ONE = ROOT / "recipes" / "lamp_models.json"


def run_cli(directory, input_path, recipe_path):
    return subprocess.run(
        ["py", "-m", "src.main", str(input_path), "--recipe", str(recipe_path)],
        cwd=directory, capture_output=True,
        env={**os.environ, "PYTHONPATH": str(ROOT), "PYTHONIOENCODING": "utf-8"},
    )


class RetestRecipeTests(unittest.TestCase):
    def test_t31_default_recipe_only_adds_limits(self):
        original = json.loads(STAGE_ONE.read_text(encoding="utf-8-sig"))
        configured = json.loads(RECIPE.read_text(encoding="utf-8-sig"))
        self.assertEqual(configured, {key: {**value, "retest_limit": 2} for key, value in original.items()})
        book = load_recipe(RECIPE)
        self.assertTrue(book.retest_enabled)
        self.assertEqual([model.retest_limit for model in book.models.values()], [2, 2])
        self.assertFalse(load_recipe(STAGE_ONE).retest_enabled)

    def test_t31_invalid_fixtures_stop_before_events_and_reports(self):
        cases = {
            "retest_zero.json": ["A.retest_limit:"],
            "retest_string.json": ["A.retest_limit:"],
            "retest_bool.json": ["A.retest_limit:"],
            "retest_partial.json": ["B.retest_limit:"],
            "retest_reserved.json": ["A.steps[0]:"],
            "retest_multiple_errors.json": ["A.retest_limit:", "B.retest_limit:", "A.steps[0]:"],
        }
        for name, locations in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                result = run_cli(directory, "missing.csv", FIXTURES / name)
                self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
                for location in locations:
                    self.assertIn(location, result.stderr.decode("utf-8"))
                self.assertEqual(result.stdout, b"")
                self.assertFalse((Path(directory) / "reports").exists())

    def test_t31_integer_bounds_and_all_models_required(self):
        original = json.loads(STAGE_ONE.read_text(encoding="utf-8-sig"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "recipe.json"
            for value in (-1, 0, 6, "2", True, False, 2.0, None):
                with self.subTest(value=value):
                    data = {key: {**body, "retest_limit": value} for key, body in original.items()}
                    path.write_text(json.dumps(data), encoding="utf-8")
                    with self.assertRaises(RecipeError) as caught:
                        load_recipe(path)
                    self.assertTrue(any(error.startswith("A.retest_limit:") for error in caught.exception.errors))
                    self.assertTrue(any(error.startswith("B.retest_limit:") for error in caught.exception.errors))
            for value in (1, 5):
                with self.subTest(valid=value):
                    data = {key: {**body, "retest_limit": value} for key, body in original.items()}
                    path.write_text(json.dumps(data), encoding="utf-8")
                    self.assertTrue(load_recipe(path).retest_enabled)


class RetestProcessTests(unittest.TestCase):
    def setUp(self):
        self.process = RecipeProcess(load_recipe(RECIPE).models)
        self.seq = 0
        self.accept("REGISTER", product_id="OTHER", model="B")
        self.accept("P1", product_id="OTHER")

    def row(self, event, product_id="a", inspection="", result="", model=""):
        self.seq += 1
        return dict(seq=str(self.seq), product_id=product_id, event=event,
                    inspection=inspection, result=result, model=model)

    def accept(self, event, product_id="a", inspection="", result="", model="", rule_id=None):
        row = self.row(event, product_id, inspection, result, model)
        decision = self.process.apply(row)
        self.assertTrue(decision.accepted, decision)
        self.assertEqual(decision.reason, "")
        if rule_id is not None:
            self.assertEqual(decision.rule_id, rule_id)
        return decision

    def reject(self, row, rule_id, reason):
        before = copy.deepcopy(self.process.products)
        decision = self.process.apply(row)
        self.assertFalse(decision.accepted, decision)
        self.assertEqual(decision.rule_id, rule_id)
        self.assertIn(reason, decision.reason)
        self.assertEqual(self.process.products, before)
        return decision

    def register(self, product_id="a", model="A", steps=3):
        self.accept("REGISTER", product_id, model=model)
        for number in range(1, steps + 1):
            self.accept("P" + str(number), product_id)

    def held(self):
        self.register()
        return self.accept("INSPECT", inspection="LEAK", result="FAIL", rule_id="RULE_FAIL_HOLD")

    def request(self, inspection="LEAK"):
        return self.accept("RETEST_REQUEST", inspection=inspection, rule_id="RULE_RETEST")

    def retest(self, result, inspection="LEAK"):
        return self.accept("INSPECT", inspection=inspection, result=result, rule_id="RULE_RETEST")

    def scrap(self):
        self.held()
        for _ in range(2):
            self.request()
            decision = self.retest("FAIL")
        return decision

    def test_t23_request_keeps_hold_and_does_not_count_as_attempt(self):
        first = self.held()
        requested = self.request()
        product = self.process.products["a"]
        self.assertEqual(requested.state, "보류")
        self.assertEqual(product.inspections, {"LEAK": "FAIL"})
        self.assertEqual(product.retest_counts, {})
        self.assertEqual(product.open_requests, frozenset({"LEAK"}))
        self.assertIn("LEAK FAIL(재검사 요청됨)", product.incomplete_reason)
        self.assertEqual(product.history, "LEAK: FAIL@" + first.seq + " → 요청@" + requested.seq)
        self.reject(self.row("P4"), "RULE_FAIL_HOLD", "보류")

    def test_t24_pass_releases_hold_resumes_and_preserves_original_fail(self):
        first = self.held()
        request = self.request()
        result = self.retest("PASS")
        self.assertEqual(result.state, "공정 진행 중(P3 완료)")
        self.accept("P4")
        self.accept("P5")
        light = self.accept("INSPECT", inspection="LIGHT", result="PASS")
        final = self.accept("INSPECT", inspection="FINAL", result="PASS")
        product = self.process.products["a"]
        self.assertEqual(final.state, "레시피 모의 흐름 완료")
        self.assertEqual(product.incomplete_reason, "")
        self.assertFalse(product.open_requests)
        self.assertEqual(product.history, f"LEAK: FAIL@{first.seq} → 요청@{request.seq} → PASS@{result.seq}(재검사 1); LIGHT: PASS@{light.seq}; FINAL: PASS@{final.seq}")

    def test_t25_result_without_request_preserves_full_state(self):
        self.held()
        self.reject(self.row("INSPECT", inspection="LEAK", result="PASS"), "RULE_PRESERVE", "결과 이미 존재")

    def test_t26_failed_retest_consumes_request_and_second_pass_is_allowed(self):
        self.held()
        self.request()
        self.assertEqual(self.retest("FAIL").state, "보류")
        product = self.process.products["a"]
        self.assertFalse(product.open_requests)
        self.assertEqual(product.retest_counts, {"LEAK": 1})
        self.reject(self.row("INSPECT", inspection="LEAK", result="PASS"), "RULE_PRESERVE", "결과 이미 존재")
        self.request()
        self.retest("PASS")
        self.assertEqual(self.process.products["a"].retest_counts, {"LEAK": 2})
        self.assertEqual(self.process.products["a"].status, "공정 진행 중(P3 완료)")
        self.assertIn("(재검사 2)", self.process.products["a"].history)

    def test_t27_limit_fail_is_accepted_then_all_inputs_preserve_scrap(self):
        decision = self.scrap()
        product = self.process.products["a"]
        self.assertEqual(decision.state, "폐기")
        self.assertEqual(product.incomplete_reason, "LEAK 재검사 한도 2회 초과 FAIL로 폐기")
        self.assertEqual(product.retest_counts, {"LEAK": 2})
        self.assertFalse(product.open_requests)
        for row in (self.row("P4"), self.row("RETEST_REQUEST", inspection="LEAK"),
                    self.row("INSPECT", inspection="LIGHT", result="PASS")):
            self.reject(row, "RULE_RETEST", "폐기된 제품")
        self.assertIn("FAIL@" + decision.seq + "(재검사 2)", product.history)

    def test_t28_request_rejections_preserve_every_product(self):
        self.register()
        self.reject(self.row("RETEST_REQUEST", inspection="LEAK"), "RULE_RETEST", "미해결 FAIL 없음")
        self.accept("INSPECT", inspection="LEAK", result="PASS")
        self.reject(self.row("RETEST_REQUEST", inspection="LEAK"), "RULE_RETEST", "미해결 FAIL 없음")
        self.register("b", "B", steps=2)
        self.reject(self.row("RETEST_REQUEST", "b", inspection="FINAL"), "RULE_RECIPE", "없는 검사")
        self.reject(self.row("RETEST_REQUEST", "missing", inspection="LEAK"), "RULE_PRESERVE", "미등록")
        self.register("c", steps=3)
        self.accept("INSPECT", "c", inspection="LEAK", result="FAIL")
        self.accept("RETEST_REQUEST", "c", inspection="LEAK")
        self.reject(self.row("RETEST_REQUEST", "c", inspection="LEAK"), "RULE_RETEST", "이미 열린 재검사 요청")
        for fields in ({"result": "PASS"}, {"model": "A"}, {"inspection": ""}):
            row = self.row("RETEST_REQUEST", "c", inspection="LEAK")
            row.update(fields)
            self.reject(row, "RULE_PRESERVE", "")

    def test_t29_other_failed_inspection_keeps_hold_and_requests_are_independent(self):
        self.register(steps=5)
        self.accept("INSPECT", inspection="LEAK", result="PASS")
        self.accept("INSPECT", inspection="LIGHT", result="FAIL")
        self.accept("INSPECT", inspection="FINAL", result="FAIL")
        self.request("LIGHT")
        self.assertEqual(self.retest("PASS", "LIGHT").state, "보류")
        self.assertEqual(self.process.products["a"].incomplete_reason, "FINAL FAIL")
        self.request("FINAL")
        self.assertEqual(self.retest("PASS", "FINAL").state, "레시피 모의 흐름 완료")

    def test_t30_counters_are_per_inspection_and_limit_pass_never_scraps(self):
        self.held()
        self.request()
        self.retest("FAIL")
        self.request()
        self.retest("PASS")
        self.accept("P4")
        self.accept("P5")
        self.accept("INSPECT", inspection="LIGHT", result="FAIL")
        self.request("LIGHT")
        self.retest("PASS", "LIGHT")
        product = self.process.products["a"]
        self.assertEqual(product.status, "검사 대기")
        self.assertEqual(product.retest_counts, {"LEAK": 2, "LIGHT": 1})
        self.assertEqual(product.incomplete_reason, "FINAL 미실시")

    def test_priority_format_registration_scrap_recipe_and_inspection_timing(self):
        self.scrap()
        self.reject(self.row("P6", model="A"), "RULE_PRESERVE", "model")
        self.reject(self.row("REGISTER", model="UNKNOWN"), "RULE_PRESERVE", "이미 등록")
        self.reject(self.row("P6"), "RULE_RETEST", "폐기된 제품")
        self.reject(self.row("INSPECT", inspection="UNKNOWN", result="PASS"), "RULE_RETEST", "폐기된 제품")
        self.reject(self.row("RETEST_REQUEST", inspection="UNKNOWN"), "RULE_RETEST", "폐기된 제품")
        self.reject(self.row("INSPECT", inspection="LIGHT", result="WRONG"), "RULE_PRESERVE", "result")
        self.register("b", steps=1)
        self.reject(self.row("INSPECT", "b", inspection="LEAK", result="PASS"), "RULE_INSP_PRE", "P3 미완료")

    def test_parallel_requests_and_history_follow_recipe_and_physical_order(self):
        self.register(steps=5)
        final = self.accept("INSPECT", inspection="FINAL", result="FAIL")
        light = self.accept("INSPECT", inspection="LIGHT", result="FAIL")
        self.request("FINAL")
        self.request("LIGHT")
        self.assertEqual(self.process.products["a"].open_requests, frozenset({"FINAL", "LIGHT"}))
        row = self.row("INSPECT", inspection="FINAL", result="PASS")
        row["seq"] = "1"
        self.assertTrue(self.process.apply(row).accepted)
        self.retest("PASS", "LIGHT")
        history = self.process.products["a"].history
        self.assertTrue(history.startswith("LIGHT: FAIL@" + light.seq))
        self.assertIn("; FINAL: FAIL@" + final.seq, history)
        self.assertIn("PASS@1(재검사 1)", history)
        self.assertFalse(self.process.products["a"].open_requests)


class RetestReportTests(unittest.TestCase):
    def test_sample_t23_to_t30_reports_match_fixed_input(self):
        with tempfile.TemporaryDirectory() as directory:
            result = run_cli(directory, ROOT / "data" / "sample_events_retest.csv", RECIPE)
            self.assertEqual(result.returncode, 0, result.stderr)
            generated = Path(directory) / "reports"
            for suffix in ("rows", "products", "rejections"):
                name = "sample_events_retest_" + suffix + ".csv"
                self.assertEqual((generated / name).read_bytes(), (ROOT / "reports" / name).read_bytes())
            with (generated / "sample_events_retest_products.csv").open(encoding="utf-8-sig", newline="") as source:
                products = {row["product_id"]: row for row in csv.DictReader(source)}
            self.assertEqual({key: row["state"] for key, row in products.items()}, {
                "T23": "보류", "T24": "레시피 모의 흐름 완료", "T25": "보류",
                "T26": "공정 진행 중(P3 완료)", "T27": "폐기",
                "T28_NO_RESULT": "공정 진행 중(P3 완료)", "T28_PASS": "공정 진행 중(P3 완료)",
                "T28_OPEN": "보류", "T28_MODEL_B": "공정 진행 중(P2 완료)",
                "T28_FORMAT": "보류", "T29": "레시피 모의 흐름 완료", "T30": "검사 대기",
            })
            self.assertEqual(products["T27"]["incomplete_reason"], "LEAK 재검사 한도 2회 초과 FAIL로 폐기")
            self.assertIn("LEAK FAIL(재검사 요청됨)", products["T23"]["incomplete_reason"])
            self.assertIn("(재검사 2)", products["T26"]["history"])
            self.assertEqual(products["T30"]["incomplete_reason"], "FINAL 미실시")
            with (generated / "sample_events_retest_rows.csv").open(encoding="utf-8-sig", newline="") as source:
                rows = list(csv.DictReader(source))
            self.assertEqual(len(rows), 102)
            self.assertEqual(sum(row["decision"] == "허용" for row in rows), 90)
            with (generated / "sample_events_retest_rejections.csv").open(encoding="utf-8-sig", newline="") as source:
                counts = {row["rule_id"]: int(row["rejection_count"]) for row in csv.DictReader(source)}
            self.assertEqual(counts, {"RULE_RECIPE": 1, "RULE_SEQ": 0, "RULE_INSP_PRE": 0,
                                      "RULE_NOT_DONE": 0, "RULE_FAIL_HOLD": 1,
                                      "RULE_PRESERVE": 4, "RULE_RETEST": 6})

    def test_t32_stage_one_request_is_recipe_rejection_and_state_unchanged(self):
        process = RecipeProcess(load_recipe(STAGE_ONE).models)
        process.apply(dict(seq="1", product_id="a", event="REGISTER", inspection="", result="", model="A"))
        before = copy.deepcopy(process.products)
        decision = process.apply(dict(seq="2", product_id="a", event="RETEST_REQUEST", inspection="LEAK", result="", model=""))
        self.assertFalse(decision.accepted)
        self.assertEqual(decision.rule_id, "RULE_RECIPE")
        self.assertEqual(process.products, before)

    def test_t32_cli_history_seven_rules_and_byte_reproducibility(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "events.csv"
            source.write_text(
                "seq,product_id,event,inspection,result,model\n"
                "1,a,REGISTER,,,A\n2,a,P1,,,\n3,a,P2,,,\n4,a,P3,,,\n"
                "5,a,INSPECT,LEAK,FAIL,\n6,a,RETEST_REQUEST,LEAK,,\n"
                "7,a,INSPECT,LEAK,PASS,\n8,a,P4,,,\n9,a,P5,,,\n"
                "10,a,INSPECT,LIGHT,PASS,\n11,a,INSPECT,FINAL,PASS,\n"
                "12,a,INSPECT,LEAK,FAIL,\n13,a,RETEST_REQUEST,LEAK,,\n",
                encoding="utf-8",
            )
            first = run_cli(directory, source, RECIPE)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(first.stderr, b"")
            reports = {p.name: p.read_bytes() for p in (Path(directory) / "reports").glob("*.csv")}
            self.assertEqual(len(reports), 3)
            second = run_cli(directory, source, RECIPE)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(first.stdout, second.stdout)
            self.assertEqual(first.stderr, second.stderr)
            self.assertEqual(reports, {p.name: p.read_bytes() for p in (Path(directory) / "reports").glob("*.csv")})
            with tempfile.TemporaryDirectory() as other:
                third = run_cli(other, source, RECIPE)
                self.assertEqual(third.returncode, 0, third.stderr)
                self.assertEqual(first.stdout, third.stdout)
                self.assertEqual(reports, {p.name: p.read_bytes() for p in (Path(other) / "reports").glob("*.csv")})
            products = list(csv.DictReader(io.StringIO(reports["events_products.csv"].decode("utf-8-sig"))))
            self.assertEqual(list(products[0]), ["product_id", "model", "state", "incomplete_reason", "history"])
            self.assertEqual(products, [{
                "product_id": "a", "model": "A", "state": "레시피 모의 흐름 완료", "incomplete_reason": "",
                "history": "LEAK: FAIL@5 → 요청@6 → PASS@7(재검사 1); LIGHT: PASS@10; FINAL: PASS@11",
            }])
            self.assertIn("product_id | model | 최종 상태 | 미완료 이유 | history", first.stdout.decode("utf-8"))
            counts = list(csv.reader(io.StringIO(reports["events_rejections.csv"].decode("utf-8-sig"))))
            self.assertEqual(counts, [
                ["rule_id", "rejection_count"], ["RULE_RECIPE", "0"], ["RULE_SEQ", "0"],
                ["RULE_INSP_PRE", "0"], ["RULE_NOT_DONE", "0"], ["RULE_FAIL_HOLD", "0"],
                ["RULE_PRESERVE", "1"], ["RULE_RETEST", "1"],
            ])
            rows = list(csv.reader(io.StringIO(reports["events_rows.csv"].decode("utf-8-sig"))))
            self.assertEqual(rows[0], ["seq", "product_id", "input", "rule_id", "decision", "rejection_reason", "state"])
            self.assertEqual([rows[index][3] for index in (6, 7)], ["RULE_RETEST", "RULE_RETEST"])
            self.assertEqual(len(rows), 14)


if __name__ == "__main__":
    unittest.main()

import copy
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from src.equipment import EquipmentError, load_equipment
from src.recipe import load_recipe
from src.recipe_rules import RecipeProcess


ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "recipes" / "lamp_models_retest.json"
STAGE_ONE = ROOT / "recipes" / "lamp_models.json"
EQUIPMENT = ROOT / "recipes" / "equipment.json"
FIXTURES = ROOT / "tests" / "fixtures"


def run_cli(directory, input_path, recipe_path=RECIPE, equipment_path=EQUIPMENT):
    command = ["py", "-m", "src.main", str(input_path)]
    if recipe_path is not None:
        command += ["--recipe", str(recipe_path)]
    if equipment_path is not None:
        command += ["--equipment", str(equipment_path)]
    return subprocess.run(command, cwd=directory, capture_output=True,
                          env={**os.environ, "PYTHONPATH": str(ROOT), "PYTHONIOENCODING": "utf-8"})


class EquipmentFileTests(unittest.TestCase):
    def setUp(self):
        self.models = load_recipe(RECIPE).models

    def test_t40_default_file_and_raw_digest(self):
        book = load_equipment(EQUIPMENT, self.models)
        self.assertEqual((book.window, book.fails), (3, 2))
        self.assertEqual(list(book.equipment.items()), [
            ("LEAK-1", "LEAK"), ("LEAK-2", "LEAK"),
            ("LIGHT-1", "LIGHT"), ("FINAL-1", "FINAL"),
        ])
        self.assertEqual(book.sha256, hashlib.sha256(EQUIPMENT.read_bytes()).hexdigest())

    def test_t40_invalid_fixtures_exit_three_without_reports(self):
        cases = {
            "equipment_window_zero.json": ["stop_rule.window:"],
            "equipment_fails_exceeds.json": ["stop_rule.fails:"],
            "equipment_window_string.json": ["stop_rule.window:"],
            "equipment_unknown_keys.json": ["$.extra:", "stop_rule.extra:"],
            "equipment_empty.json": ["equipment:"],
            "equipment_unknown_inspection.json": ["equipment.LEAK-1:"],
            "equipment_multiple_errors.json": ["stop_rule.window:", "stop_rule.fails:", "equipment.bad id:", "equipment.X:"],
        }
        for name, locations in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                result = run_cli(directory, "missing.csv", equipment_path=FIXTURES / name)
                self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
                for location in locations:
                    self.assertIn(location, result.stderr.decode("utf-8"))
                self.assertEqual(result.stdout, b"")
                self.assertFalse((Path(directory) / "reports").exists())

    def test_t40_types_bounds_ids_and_missing_structure(self):
        valid = {"stop_rule": {"window": 3, "fails": 2}, "equipment": {"LEAK-1": "LEAK"}}
        invalid = [None, [], {}, {"equipment": {"LEAK-1": "LEAK"}},
                   {"stop_rule": None, "equipment": []}]
        for key in ("window", "fails"):
            values = (True, False, "3", 3.0, None, 0, -1, 21)
            for value in values:
                item = copy.deepcopy(valid)
                item["stop_rule"][key] = value
                invalid.append(item)
            item = copy.deepcopy(valid)
            del item["stop_rule"][key]
            invalid.append(item)
        for equipment in ({"leak-1": "LEAK"}, {"1LEAK": "LEAK"}, {"LEAK 1": "LEAK"},
                          {"X": []}, {"X": None}, {"X": "AIM"}, {}):
            invalid.append({**valid, "equipment": equipment})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "equipment.json"
            for data in invalid:
                with self.subTest(data=data):
                    path.write_text(json.dumps(data), encoding="utf-8")
                    with self.assertRaises(EquipmentError):
                        load_equipment(path, self.models)
            for window, fails in ((1, 1), (20, 20), (20, 1)):
                path.write_text(json.dumps({**valid, "stop_rule": {"window": window, "fails": fails}}), encoding="utf-8")
                self.assertEqual(load_equipment(path, self.models).window, window)
            # FINAL exists only in A; equipment is shared by all models.
            path.write_text(json.dumps({**valid, "equipment": {"FINAL_1": "FINAL"}}), encoding="utf-8")
            self.assertEqual(load_equipment(path, self.models).equipment, {"FINAL_1": "FINAL"})

    def test_t40_read_json_and_encoding_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "equipment.json"
            for content in (b"{", b"\xff"):
                path.write_bytes(content)
                with self.assertRaises(EquipmentError) as caught:
                    load_equipment(path, self.models)
                self.assertTrue(caught.exception.errors[0].startswith("$:"))
            with self.assertRaises(EquipmentError):
                load_equipment(Path(directory) / "missing.json", self.models)


class EquipmentProcessTests(unittest.TestCase):
    def setUp(self):
        self.models = load_recipe(RECIPE).models
        self.book = load_equipment(EQUIPMENT, self.models)
        self.process = RecipeProcess(self.models, self.book)
        self.seq = 0

    def row(self, event, product_id="a", inspection="", result="", model="", equipment=""):
        self.seq += 1
        return dict(seq=str(self.seq), product_id=product_id, event=event,
                    inspection=inspection, result=result, model=model, equipment=equipment)

    def accept(self, event, product_id="a", **fields):
        decision = self.process.apply(self.row(event, product_id, **fields))
        self.assertTrue(decision.accepted, decision)
        self.assertEqual(decision.reason, "")
        return decision

    def reject(self, row, rule_id, reason):
        before = copy.deepcopy((self.process.products, self.process.equipment))
        decision = self.process.apply(row)
        self.assertFalse(decision.accepted, decision)
        self.assertEqual(decision.rule_id, rule_id)
        self.assertIn(reason, decision.reason)
        self.assertEqual((self.process.products, self.process.equipment), before)
        return decision

    def register(self, product_id="a", model="A", steps=3):
        self.accept("REGISTER", product_id, model=model)
        for number in range(1, steps + 1):
            self.accept("P" + str(number), product_id)

    def inspect(self, result, product_id="a", equipment="LEAK-2"):
        return self.accept("INSPECT", product_id, inspection="LEAK", result=result, equipment=equipment)

    def stop_leak_two(self):
        decisions = []
        for product_id, result in (("p1", "FAIL"), ("p2", "PASS"), ("p3", "FAIL")):
            self.register(product_id)
            decisions.append(self.inspect(result, product_id))
        return decisions

    def test_t33_triggering_result_is_accepted_and_stops_only_its_equipment(self):
        decisions = self.stop_leak_two()
        state = self.process.equipment["LEAK-2"]
        self.assertEqual(state.state, "정지")
        self.assertEqual(state.stopped_at_seq, decisions[-1].seq)
        self.assertEqual((state.counted_results, state.fail_count), (3, 2))
        self.assertEqual([self.process.products[p].status for p in ("p1", "p2", "p3")],
                         ["보류", "공정 진행 중(P3 완료)", "보류"])
        self.assertEqual(self.process.equipment["LEAK-1"].state, "가동")

    def test_t34_stopped_reject_then_other_equipment_accepts(self):
        self.stop_leak_two()
        self.register("p4")
        self.reject(self.row("INSPECT", "p4", inspection="LEAK", result="PASS", equipment="LEAK-2"),
                    "RULE_EQUIP", "정지된 설비")
        self.assertEqual(self.process.products["p4"].inspections, {})
        self.inspect("PASS", "p4", "LEAK-1")
        self.assertEqual(self.process.products["p4"].inspections, {"LEAK": "PASS"})

    def test_t35_stopped_retest_keeps_request_then_other_equipment_releases_hold(self):
        self.register()
        self.inspect("FAIL")
        self.accept("RETEST_REQUEST", inspection="LEAK")
        for product_id, result in (("b", "PASS"), ("c", "FAIL")):
            self.register(product_id)
            self.inspect(result, product_id)
        self.reject(self.row("INSPECT", inspection="LEAK", result="PASS", equipment="LEAK-2"),
                    "RULE_EQUIP", "정지된 설비")
        product = self.process.products["a"]
        self.assertEqual(product.open_requests, frozenset({"LEAK"}))
        self.assertEqual(product.status, "보류")
        decision = self.inspect("PASS", equipment="LEAK-1")
        self.assertEqual(decision.rule_id, "RULE_RETEST")
        product = self.process.products["a"]
        self.assertFalse(product.open_requests)
        self.assertEqual(product.retest_counts, {"LEAK": 1})
        self.assertEqual(product.status, "공정 진행 중(P3 완료)")
        self.assertEqual(self.process.equipment["LEAK-1"].counted_results, 0)

    def test_t36_repeated_retest_fails_scrap_product_without_stopping_equipment(self):
        self.register()
        self.inspect("FAIL", equipment="LEAK-1")
        for _ in range(2):
            self.accept("RETEST_REQUEST", inspection="LEAK")
            self.inspect("FAIL", equipment="LEAK-1")
        self.assertEqual(self.process.products["a"].status, "폐기")
        state = self.process.equipment["LEAK-1"]
        self.assertEqual((state.counted_results, state.fail_count, state.state), (1, 1, "가동"))
        self.assertIsNone(state.stopped_at_seq)

    def test_t37_sliding_window_is_separate_from_cumulative_report_counts(self):
        for index, result in enumerate(("FAIL", "PASS", "PASS", "FAIL")):
            product_id = "p" + str(index)
            self.register(product_id)
            self.inspect(result, product_id, "LEAK-1")
        state = self.process.equipment["LEAK-1"]
        self.assertEqual((state.counted_results, state.fail_count, state.state), (4, 2, "가동"))
        self.assertIsNone(state.stopped_at_seq)
        self.register("trigger")
        last = self.inspect("FAIL", "trigger", "LEAK-1")
        self.assertEqual(self.process.equipment["LEAK-1"].stopped_at_seq, last.seq)

    def test_t38_equipment_and_format_rejections_preserve_all_state(self):
        self.register()
        for equipment, rule, reason in (("LEAK-9", "RULE_EQUIP", "등록되지 않은 설비"),
                                        ("LIGHT-1", "RULE_EQUIP", "검사 종류가 다른 설비"),
                                        ("", "RULE_PRESERVE", "equipment")):
            self.reject(self.row("INSPECT", inspection="LEAK", result="PASS", equipment=equipment), rule, reason)
        self.reject(self.row("P4", equipment="LEAK-1"), "RULE_PRESERVE", "equipment")
        self.reject(self.row("REGISTER", "b", model="B", equipment="LEAK-1"), "RULE_PRESERVE", "equipment")
        self.reject(self.row("RETEST_REQUEST", inspection="LEAK", equipment="LEAK-1"), "RULE_PRESERVE", "equipment")
        row = self.row("P4")
        del row["equipment"]
        self.reject(row, "RULE_PRESERVE", "열 수")

    def test_t39_rejected_early_result_never_counts_or_stops(self):
        self.register()
        self.inspect("FAIL")
        self.register("early", steps=1)
        self.reject(self.row("INSPECT", "early", inspection="LEAK", result="FAIL", equipment="LEAK-2"),
                    "RULE_INSP_PRE", "P3 미완료")
        self.assertEqual(self.process.equipment["LEAK-2"].state, "가동")
        for product_id, result in (("b", "PASS"), ("c", "FAIL")):
            self.register(product_id)
            last = self.inspect(result, product_id)
        state = self.process.equipment["LEAK-2"]
        self.assertEqual((state.counted_results, state.fail_count), (3, 2))
        self.assertEqual(state.stopped_at_seq, last.seq)

    def test_priority_format_registration_discard_recipe_equipment_timing_duplicate(self):
        self.stop_leak_two()
        self.register("early", steps=1)
        self.reject(self.row("INSPECT", "early", inspection="LEAK", result="PASS", equipment="LEAK-2"),
                    "RULE_EQUIP", "정지된 설비")
        self.reject(self.row("INSPECT", "missing", inspection="LEAK", result="PASS", equipment="LEAK-9"),
                    "RULE_PRESERVE", "미등록")
        self.reject(self.row("INSPECT", "p1", inspection="AIM", result="PASS", equipment="LEAK-9"),
                    "RULE_RECIPE", "없는 검사")
        self.reject(self.row("INSPECT", "p1", inspection="LEAK", result="PASS", equipment="LEAK-2"),
                    "RULE_EQUIP", "정지된 설비")
        self.register("scrap")
        self.inspect("FAIL", "scrap", "LEAK-1")
        for _ in range(2):
            self.accept("RETEST_REQUEST", "scrap", inspection="LEAK")
            self.inspect("FAIL", "scrap", "LEAK-1")
        self.reject(self.row("INSPECT", "scrap", inspection="AIM", result="PASS", equipment="LEAK-9"),
                    "RULE_RETEST", "폐기된 제품")
        self.reject(self.row("INSPECT", "scrap", inspection="LEAK", result="BAD", equipment="LEAK-2"),
                    "RULE_PRESERVE", "result")
        self.reject(self.row("REGISTER", "scrap", model="B"), "RULE_PRESERVE", "이미 등록")
        self.reject(self.row("INSPECT", "scrap", inspection="LEAK", result="PASS"),
                    "RULE_PRESERVE", "equipment")
        self.reject(self.row("INSPECT", "p2", inspection="LEAK", result="FAIL", equipment="LEAK-1"),
                    "RULE_PRESERVE", "결과 이미 존재")

    def test_partial_window_threshold_and_physical_order_not_seq_sorting(self):
        for product_id in ("a", "b"):
            self.register(product_id, model="B", steps=2)
            row = self.row("INSPECT", product_id, inspection="LEAK", result="FAIL", equipment="LEAK-1")
            row["seq"] = "9" if product_id == "a" else "1"
            self.assertTrue(self.process.apply(row).accepted)
        state = self.process.equipment["LEAK-1"]
        self.assertEqual((state.counted_results, state.state, state.stopped_at_seq), (2, "정지", "1"))

    def test_equipment_also_works_without_retest_mode(self):
        models = load_recipe(STAGE_ONE).models
        self.process = RecipeProcess(models, load_equipment(EQUIPMENT, models))
        self.stop_leak_two()
        self.register("p4")
        self.reject(self.row("INSPECT", "p4", inspection="LEAK", result="PASS", equipment="LEAK-2"),
                    "RULE_EQUIP", "정지된 설비")

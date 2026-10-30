import copy
import csv
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from src.equipment import EquipmentError, load_equipment
from src.generate import RESTART_GENERATOR_VERSION, generate
from src.recipe import load_recipe
from src.recipe_reports import build_recipe_reports
from src.recipe_rules import EQUIPMENT_INPUT_COLUMNS, RecipeProcess
from src.summary import build_analysis, build_summary
from src.trace import build_trace


ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "recipes" / "lamp_models_retest.json"
RESTART_EQUIPMENT = ROOT / "recipes" / "equipment_restart.json"
PLAIN_EQUIPMENT = ROOT / "recipes" / "equipment_generated.json"
RESTART_CONFIG = ROOT / "recipes" / "generator_restart.json"


def row(seq, product_id, name, inspection="", result="", model="", equipment=""):
    return dict(zip(EQUIPMENT_INPUT_COLUMNS, (str(seq), product_id, name, inspection, result, model, equipment)))


def prepared(products):
    rows = []
    for product_id in products:
        for name, model in (("REGISTER", "B"), ("P1", ""), ("P2", "")):
            rows.append(row(len(rows) + 1, product_id, name, model=model))
    return rows


def leak(seq, product_id, result, equipment="LEAK-1"):
    return row(seq, product_id, "INSPECT", "LEAK", result, equipment=equipment)


def restart(seq, result="NO_FAULT", equipment="LEAK-1", product_id="", inspection="", model=""):
    return row(seq, product_id, "EQUIP_RESTART", inspection, result, model, equipment)


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.models = load_recipe(RECIPE).models
        cls.book = load_equipment(RESTART_EQUIPMENT, cls.models)

    def setUp(self):
        self.process = RecipeProcess(self.models, self.book)
        self.seq = 0
        self.events = []

    def apply(self, *rows):
        decisions = []
        for item in rows:
            self.events.append(item)
            decisions.append(self.process.apply(item))
        return decisions

    def start(self, products="abcdef"):
        self.assertTrue(all(item.accepted for item in self.apply(*prepared(products))))

    def t52(self):
        self.start()
        return self.apply(leak(100, "a", "FAIL"), leak(101, "b", "FAIL"), leak(102, "c", "PASS"),
                          restart(103), leak(104, "c", "PASS"))

    def t53(self):
        self.t52()
        return self.apply(leak(105, "d", "FAIL"), leak(106, "e", "FAIL"))

    def state(self, name="LEAK-1"):
        return self.process.equipment[name]


class JudgeTests(Base):
    def test_t52_stop_restart_resume(self):
        first, second, rejected, restarted, resumed = self.t52()
        self.assertTrue(first.accepted and second.accepted)
        self.assertEqual((rejected.accepted, rejected.rule_id, rejected.reason), (False, "RULE_EQUIP", "정지된 설비"))
        self.assertEqual((restarted.accepted, restarted.rule_id, restarted.state), (True, "RULE_EQUIP", "설비 가동"))
        self.assertEqual(restarted.input_text, "EQUIP_RESTART NO_FAULT @LEAK-1")
        self.assertEqual(restarted.product_id, "")
        self.assertTrue(resumed.accepted)
        self.assertEqual(self.state().state, "가동")

    def test_t53_window_cleared_then_stops_again(self):
        self.t52()
        self.assertTrue(self.apply(leak(105, "d", "FAIL"))[0].accepted)
        self.assertEqual(self.state().state, "가동")
        self.apply(leak(106, "e", "FAIL"))
        state = self.state()
        self.assertEqual((state.state, state.stop_count, state.restart_count), ("정지", 2, 1))
        self.assertEqual((state.counted_results, state.fail_count), (5, 4))

    def test_t54_restart_on_running_equipment_keeps_window(self):
        self.start()
        self.apply(leak(100, "a", "FAIL"))
        before = copy.deepcopy(self.state())
        rejected = self.apply(restart(101))[0]
        self.assertEqual((rejected.accepted, rejected.rule_id, rejected.reason),
                         (False, "RULE_EQUIP", "가동 중인 설비 재가동"))
        self.assertEqual(self.state(), before)
        self.apply(leak(102, "b", "FAIL"))
        self.assertEqual(self.state().state, "정지")

    def test_t55_invalid_restart_rows_change_nothing(self):
        self.start()
        self.apply(leak(100, "a", "FAIL"), leak(101, "b", "FAIL"))
        cases = (
            (restart(102, equipment="LEAK-9"), "RULE_EQUIP", "등록되지 않은 설비"),
            (restart(102, product_id="a"), "RULE_PRESERVE", "EQUIP_RESTART의 product_id는 빈칸이어야 함"),
            (restart(102, result="OK"), "RULE_PRESERVE", "잘못된 재가동 결과 (FIXED 또는 NO_FAULT 필요)"),
            (restart(102, inspection="LEAK"), "RULE_PRESERVE", "EQUIP_RESTART의 inspection과 model은 빈칸이어야 함"),
            (restart(102, model="A"), "RULE_PRESERVE", "EQUIP_RESTART의 inspection과 model은 빈칸이어야 함"),
            (restart(102, equipment=""), "RULE_PRESERVE", "equipment가 비어 있음"),
        )
        for item, rule, reason in cases:
            with self.subTest(reason=reason):
                products, equipment = copy.deepcopy((self.process.products, self.process.equipment))
                decision = self.process.apply(item)
                self.assertEqual((decision.accepted, decision.rule_id, decision.reason), (False, rule, reason))
                self.assertEqual((self.process.products, self.process.equipment), (products, equipment))

    def test_t56_retest_waits_for_restart_and_product_state_is_untouched(self):
        self.start()
        self.apply(leak(100, "a", "FAIL"), leak(101, "b", "FAIL"), row(102, "a", "RETEST_REQUEST", "LEAK"))
        rejected = self.apply(leak(103, "a", "PASS"))[0]
        self.assertEqual((rejected.rule_id, rejected.reason), ("RULE_EQUIP", "정지된 설비"))
        self.assertIn("LEAK", self.process.products["a"].open_requests)
        self.apply(restart(104))
        self.assertEqual(self.process.products["a"].status, "보류")
        self.assertIn("LEAK", self.process.products["a"].open_requests)
        allowed = self.apply(leak(105, "a", "PASS"))[0]
        self.assertTrue(allowed.accepted)
        self.assertNotEqual(self.process.products["a"].status, "보류")
        self.assertEqual(self.process.products["b"].status, "보류")

    def test_t57_retest_fails_do_not_enter_window(self):
        self.t52()
        decisions = self.apply(row(105, "a", "RETEST_REQUEST", "LEAK"), leak(106, "a", "FAIL"),
                               row(107, "b", "RETEST_REQUEST", "LEAK"), leak(108, "b", "FAIL"))
        self.assertTrue(all(item.accepted for item in decisions))
        self.assertEqual(self.state().state, "가동")


class ModeTests(unittest.TestCase):
    def test_t58_without_flag_restart_row_is_old_rejection(self):
        models = load_recipe(RECIPE).models
        process = RecipeProcess(models, load_equipment(PLAIN_EQUIPMENT, models))
        before = copy.deepcopy(process.equipment)
        decision = process.apply(restart(1))
        self.assertEqual((decision.accepted, decision.rule_id, decision.reason),
                         (False, "RULE_PRESERVE", "product_id가 비어 있음"))
        self.assertEqual(process.equipment, before)

    def write_equipment(self, directory, flag):
        data = json.loads(RESTART_EQUIPMENT.read_text(encoding="utf-8"))
        data["restart_enabled"] = flag
        path = Path(directory) / "equipment.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_t58_bad_flag_or_reserved_step_exit_three(self):
        with tempfile.TemporaryDirectory() as directory:
            for flag in ("true", 1):
                with self.subTest(flag=flag):
                    result = self.cli(directory, self.write_equipment(directory, flag), RECIPE)
                    self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
                    self.assertIn("restart_enabled:", result.stderr.decode("utf-8"))
            recipe = json.loads(RECIPE.read_text(encoding="utf-8"))
            recipe["A"]["steps"].insert(0, "EQUIP_RESTART")
            recipe_path = Path(directory) / "recipe.json"
            recipe_path.write_text(json.dumps(recipe), encoding="utf-8")
            result = self.cli(directory, RESTART_EQUIPMENT, recipe_path)
            self.assertEqual(result.returncode, 3, result.stderr.decode("utf-8"))
            self.assertIn("A.steps:", result.stderr.decode("utf-8"))
            self.assertFalse((Path(directory) / "reports").exists())

    def cli(self, directory, equipment, recipe):
        return subprocess.run(["py", "-m", "src.main", "missing.csv", "--recipe", str(recipe), "--equipment", str(equipment)],
                              cwd=directory, capture_output=True,
                              env={**os.environ, "PYTHONPATH": str(ROOT), "PYTHONIOENCODING": "utf-8"})


class ReportTests(Base):
    def test_t59_summary_trace_and_equipment_report(self):
        self.t53()
        analysis = build_analysis(self.events, self.models, self.book)
        rows = build_summary(analysis)
        stops = {item["key"]: item for item in rows if item["section"] == "equipment_stops"}
        self.assertEqual(stops["LEAK-1#1"]["product_id"], "b")
        self.assertEqual(stops["LEAK-1#1"]["state"], "재가동")
        self.assertEqual(stops["LEAK-1#1"]["rejected_count"], 1)
        self.assertEqual(stops["LEAK-1#2"]["product_id"], "e")
        self.assertEqual(stops["LEAK-1#2"]["state"], "정지")
        self.assertEqual(stops["LEAK-1#2"]["rejected_count"], 0)
        self.assertEqual(stops["LIGHT-1"]["state"], "가동")
        restarts = [item for item in rows if item["section"] == "equipment_restarts"]
        self.assertEqual([(item["key"], item["state"]) for item in restarts], [("LEAK-1#1", "NO_FAULT")])
        self.assertNotIn("EQUIP_NOT_STOPPED", [item["key"] for item in rows if item["section"] == "input_error_pareto"])
        self.assertFalse([item for item in rows if item["section"] == "input_error_pareto"])
        trace = build_trace(analysis, "c")
        rejected = [item for item in trace if item["decision"] == "거절"]
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0]["stop_product_id"], "b")
        self.assertEqual(rejected[0]["cause_product_ids"], "a;b")
        with self.assertRaises(ValueError):
            build_trace(analysis, "")
        equipment = {item[0]: item for item in build_recipe_reports(self.events, self.models, self.book)[3]}
        self.assertEqual(equipment["LEAK-1"][-3:], (2, 1, "NO_FAULT"))

    def test_t59_restart_rejection_enters_input_pareto(self):
        self.start()
        self.apply(restart(100))
        rows = build_summary(build_analysis(self.events, self.models, self.book))
        self.assertEqual([item["key"] for item in rows if item["section"] == "input_error_pareto"], ["EQUIP_NOT_STOPPED"])

    def test_t59_later_stop_is_linked_to_its_own_rejection(self):
        self.t53()
        self.apply(leak(107, "f", "PASS"))
        analysis = build_analysis(self.events, self.models, self.book)
        rejected = [item for item in build_trace(analysis, "f") if item["decision"] == "거절"]
        self.assertEqual(rejected[0]["stop_product_id"], "e")
        self.assertEqual(rejected[0]["cause_product_ids"], "d;e")


class GeneratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.models = load_recipe(RECIPE).models
        cls.book = load_equipment(RESTART_EQUIPMENT, cls.models)

    def produce(self, directory, seed, products, name="gen.csv"):
        path = Path(directory) / name
        meta = generate(seed, products, path, RESTART_CONFIG)
        with path.open(encoding="utf-8-sig", newline="") as source:
            return meta, list(csv.DictReader(source)), path

    def test_t60_reproducible_and_all_normal_rows_allowed(self):
        for seed, products in ((42, 500), (7, 200)):
            with self.subTest(seed=seed), tempfile.TemporaryDirectory() as directory:
                meta, rows, first = self.produce(directory, seed, products, "one.csv")
                _, _, second = self.produce(directory, seed, products, "two.csv")
                self.assertEqual(first.read_bytes(), second.read_bytes())
                self.assertEqual(meta["generator_version"], RESTART_GENERATOR_VERSION)
                analysis = build_analysis(rows, self.models, self.book)
                restarts = [(row_, decision) for row_, decision in zip(analysis.events, analysis.decisions)
                            if row_["event"] == "EQUIP_RESTART"]
                self.assertTrue(restarts)
                self.assertTrue(all(decision.accepted for _, decision in restarts))
                rejected = sum(not decision.accepted for decision in analysis.decisions)
                self.assertEqual(rejected, sum(meta["injected_errors"].values()))

    def test_t60_rejected_rows_change_no_state(self):
        with tempfile.TemporaryDirectory() as directory:
            _, rows, _ = self.produce(directory, 7, 60)
        process = RecipeProcess(self.models, self.book)
        for item in rows:
            before = copy.deepcopy((process.products, process.equipment))
            decision = process.apply(item)
            if not decision.accepted:
                self.assertEqual((process.products, process.equipment), before)

    def test_t61_every_product_reaches_a_final_state(self):
        with tempfile.TemporaryDirectory() as directory:
            for seed in range(30):
                with self.subTest(seed=seed):
                    _, rows, _ = self.produce(directory, seed, 500)
                    analysis = build_analysis(rows, self.models, self.book)
                    states = {product.status for product in analysis.process.products.values()}
                    self.assertLessEqual(states, {"레시피 모의 흐름 완료", "보류", "폐기"})
                    fixed = [item for item in analysis.restarts if item.result == "FIXED"]
                    self.assertEqual([item.equipment for item in fixed], ["LEAK-2"])
                    open_stops = {}
                    for stop in analysis.stop_history:
                        open_stops[stop.equipment] = open_stops.get(stop.equipment, 0) + 1
                    for restart_item in analysis.restarts:
                        open_stops[restart_item.equipment] -= 1
                    self.assertTrue(all(count in (0, 1) for count in open_stops.values()))

    def test_restart_config_needs_restart_equipment(self):
        config = json.loads(RESTART_CONFIG.read_text(encoding="utf-8-sig"))
        config["equipment"] = str(PLAIN_EQUIPMENT)
        config["recipe"] = str(RECIPE)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaises(ValueError):
                generate(1, 5, Path(directory) / "gen.csv", path)


if __name__ == "__main__":
    unittest.main()

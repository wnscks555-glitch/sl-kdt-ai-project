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


class EquipmentReportTests(unittest.TestCase):
    def test_sample_t33_to_t39_reports_and_all_rejected_state_unchanged(self):
        sample = ROOT / "data" / "sample_events_equipment.csv"
        models = load_recipe(RECIPE).models
        process = RecipeProcess(models, load_equipment(EQUIPMENT, models))
        with sample.open(encoding="utf-8-sig", newline="") as source:
            events = list(csv.DictReader(source))
        rejected = []
        for row in events:
            before = copy.deepcopy((process.products, process.equipment))
            decision = process.apply(row)
            if not decision.accepted:
                self.assertEqual((process.products, process.equipment), before)
                rejected.append(decision.rule_id)
        self.assertEqual(len(events), 94)
        self.assertEqual(rejected, ["RULE_EQUIP", "RULE_EQUIP", "RULE_EQUIP", "RULE_EQUIP",
                                    "RULE_PRESERVE", "RULE_PRESERVE", "RULE_INSP_PRE"])
        self.assertEqual(process.products["T36"].status, "폐기")
        self.assertEqual(process.products["T33_T35_A"].retest_counts, {"LEAK": 1})
        self.assertEqual(process.products["T33_T35_A"].status, "공정 진행 중(P3 완료)")
        self.assertEqual(process.products["T34"].inspections, {"LEAK": "PASS"})
        self.assertEqual(process.products["T38"].inspections, {})
        self.assertEqual(process.products["T39_EARLY"].inspections, {})
        self.assertEqual((process.equipment["LEAK-1"].counted_results, process.equipment["LEAK-1"].fail_count), (12, 5))
        self.assertEqual((process.equipment["LEAK-2"].counted_results, process.equipment["LEAK-2"].fail_count), (3, 2))
        self.assertEqual([state.state for state in process.equipment.values()], ["정지", "정지", "가동", "가동"])
        with tempfile.TemporaryDirectory() as directory:
            result = run_cli(directory, sample)
            self.assertEqual(result.returncode, 0, result.stderr)
            for suffix in ("rows", "products", "rejections", "equipment"):
                name = "sample_events_equipment_" + suffix + ".csv"
                self.assertEqual((Path(directory) / "reports" / name).read_bytes(), (ROOT / "reports" / name).read_bytes())

    def write_input(self, directory):
        events = []

        def add(product_id, event, inspection="", result="", model="", equipment=""):
            events.append((str(len(events) + 1), product_id, event, inspection, result, model, equipment))

        for product_id, result in (("a", "FAIL"), ("b", "PASS"), ("c", "FAIL")):
            add(product_id, "REGISTER", model="A")
            for step in ("P1", "P2", "P3"):
                add(product_id, step)
            add(product_id, "INSPECT", "LEAK", result, equipment="LEAK-2")
            if product_id == "a":
                add("a", "RETEST_REQUEST", "LEAK")
        add("a", "INSPECT", "LEAK", "PASS", equipment="LEAK-2")
        add("a", "INSPECT", "LEAK", "PASS", equipment="LEAK-1")
        path = Path(directory) / "events.csv"
        with path.open("w", encoding="utf-8", newline="") as target:
            writer = csv.writer(target)
            writer.writerow(("seq", "product_id", "event", "inspection", "result", "model", "equipment"))
            writer.writerows(events)
        return path

    def test_t41_four_reports_history_equipment_order_and_byte_reproducibility(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as second:
            path = self.write_input(directory)
            first = run_cli(directory, path)
            self.assertEqual(first.returncode, 0, first.stderr.decode("utf-8"))
            reports = Path(directory) / "reports"
            before = {item.name: item.read_bytes() for item in reports.iterdir()}
            self.assertEqual(set(before), {"events_" + suffix + ".csv" for suffix in ("rows", "products", "rejections", "equipment")})
            again = run_cli(directory, path)
            other = run_cli(second, path)
            for result, output in ((again, reports), (other, Path(second) / "reports")):
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, first.stdout)
                self.assertEqual({item.name: item.read_bytes() for item in output.iterdir()}, before)
            stdout = first.stdout.decode("utf-8")
            self.assertIn("설비: " + EQUIPMENT.as_posix() + " | SHA-256: " + hashlib.sha256(EQUIPMENT.read_bytes()).hexdigest()[:12], stdout)
            self.assertIn("[설비별 최종 상태]", stdout)
            self.assertIn("INSPECT LEAK FAIL @LEAK-2", stdout)
            self.assertIn("LEAK: FAIL@5[LEAK-2] → 요청@6 → PASS@18[LEAK-1](재검사 1)", stdout)
            with (reports / "events_equipment.csv").open(encoding="utf-8-sig", newline="") as source:
                rows = list(csv.reader(source))
            self.assertEqual(rows, [
                ["equipment", "inspection", "counted_results", "fail_count", "state", "stopped_at_seq"],
                ["LEAK-1", "LEAK", "0", "0", "가동", ""],
                ["LEAK-2", "LEAK", "3", "2", "정지", "16"],
                ["LIGHT-1", "LIGHT", "0", "0", "가동", ""],
                ["FINAL-1", "FINAL", "0", "0", "가동", ""],
            ])
            with (reports / "events_rejections.csv").open(encoding="utf-8-sig", newline="") as source:
                counts = list(csv.reader(source))
            self.assertEqual([row[0] for row in counts[1:]], ["RULE_RECIPE", "RULE_SEQ", "RULE_INSP_PRE", "RULE_NOT_DONE", "RULE_FAIL_HOLD", "RULE_PRESERVE", "RULE_RETEST", "RULE_EQUIP"])
            self.assertEqual(counts[-1], ["RULE_EQUIP", "1"])
            self.assertTrue(all(value.startswith(b"\xef\xbb\xbf") for value in before.values()))

    def test_t41_option_dependency_and_mode_specific_headers(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_input(directory)
            cases = [(None, EQUIPMENT), (None, None), (RECIPE, None)]
            for recipe, equipment in cases:
                with self.subTest(recipe=recipe, equipment=equipment):
                    result = run_cli(directory, path, recipe, equipment)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertFalse((Path(directory) / "reports").exists())
            for header in ("seq,product_id,event,inspection,result", "seq,product_id,event,inspection,result,model",
                           "seq,product_id,event,inspection,result,equipment,model", "seq,product_id,event,inspection,result,model,equipment,extra"):
                path.write_text(header + "\n", encoding="utf-8")
                result = run_cli(directory, path)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("CSV 헤더", result.stderr.decode("utf-8"))
                self.assertFalse((Path(directory) / "reports").exists())

    def test_t41_without_equipment_all_nine_legacy_reports_unchanged(self):
        for name, recipe in (("sample_events", None), ("sample_events_v2", STAGE_ONE), ("sample_events_retest", RECIPE)):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                result = run_cli(directory, ROOT / "data" / (name + ".csv"), recipe, None)
                self.assertEqual(result.returncode, 0, result.stderr)
                output = Path(directory) / "reports"
                self.assertEqual(len(list(output.iterdir())), 3)
                for suffix in ("rows", "products", "rejections"):
                    path = name + "_" + suffix + ".csv"
                    self.assertEqual((output / path).read_bytes(), (ROOT / "reports" / path).read_bytes())
                self.assertNotIn("설비:", result.stdout.decode("utf-8"))

    def test_t41_equipment_with_stage_one_has_seven_rules_and_no_history(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.csv"
            path.write_text("seq,product_id,event,inspection,result,model,equipment\n1,a,REGISTER,,,A,\n", encoding="utf-8")
            result = run_cli(directory, path, STAGE_ONE)
            self.assertEqual(result.returncode, 0, result.stderr)
            reports = Path(directory) / "reports"
            with (reports / "events_rejections.csv").open(encoding="utf-8-sig", newline="") as source:
                rules = list(csv.reader(source))
            self.assertEqual(len(rules), 8)
            self.assertEqual(rules[-1], ["RULE_EQUIP", "0"])
            with (reports / "events_products.csv").open(encoding="utf-8-sig", newline="") as source:
                self.assertEqual(next(csv.reader(source)), ["product_id", "model", "state", "incomplete_reason"])

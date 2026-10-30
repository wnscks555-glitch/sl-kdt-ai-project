import copy
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from src.containment import build_containment, run_scopes
from src.equipment import load_equipment
from src.evaluate import (
    containment_metrics, containment_verdict, parse_rules, read_selection, select_method, evaluate_containment,
)
from src.generate import LOT_GENERATOR_VERSION, build_rows, generate, load_setup
from src.recipe import load_recipe
from src.recipe_rules import LOT_INPUT_COLUMNS, RecipeProcess
from src.summary import build_analysis


ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "recipes" / "lamp_models_retest.json"
LOT_EQUIPMENT = ROOT / "recipes" / "equipment_lot.json"
PLAIN_EQUIPMENT = ROOT / "recipes" / "equipment.json"
LOT_CONFIG = ROOT / "recipes" / "generator_lot.json"
CLUSTERED_CONFIG = ROOT / "recipes" / "generator_lot_clustered.json"
SAMPLE = ROOT / "data" / "sample_events_equipment.csv"


def row(seq, product_id, name, inspection="", result="", model="", equipment="", lot=""):
    return dict(zip(LOT_INPUT_COLUMNS, (str(seq), product_id, name, inspection, result, model, equipment, lot)))


def prepared(lots):
    rows = []
    for product_id, lot in lots.items():
        rows.append(row(len(rows) + 1, product_id, "REGISTER", model="B", lot=lot))
        rows.append(row(len(rows) + 1, product_id, "P1"))
        rows.append(row(len(rows) + 1, product_id, "P2"))
    return rows


def leak(seq, product_id, result, equipment="LEAK-1"):
    return row(seq, product_id, "INSPECT", "LEAK", result, equipment=equipment)


def restart(seq, equipment="LEAK-1", result="NO_FAULT", lot=""):
    return row(seq, "", "EQUIP_RESTART", result=result, equipment=equipment, lot=lot)


def cli(directory, *arguments, module="src.main"):
    return subprocess.run(["py", "-m", module, *arguments], cwd=directory, capture_output=True,
                          env={**os.environ, "PYTHONPATH": str(ROOT), "PYTHONIOENCODING": "utf-8"})


def rows_of(method_rows, key, method):
    return [item["product_id"] for item in method_rows if item["stop_key"] == key and item["method"] == method]


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.models = load_recipe(RECIPE).models
        cls.book = load_equipment(LOT_EQUIPMENT, cls.models)

    def analysis(self, events):
        return build_analysis(events, self.models, self.book)


class InputTests(Base):
    def test_t67_register_stores_lot(self):
        process = RecipeProcess(self.models, self.book)
        decision = process.apply(row(1, "z", "REGISTER", model="B", lot="L1"))
        self.assertTrue(decision.accepted)
        self.assertEqual(process.products["z"].lot, "L1")

    def test_t68_invalid_lot_rows_change_nothing(self):
        process = RecipeProcess(self.models, self.book)
        process.apply(row(1, "a", "REGISTER", model="B", lot="L1"))
        cases = (
            (row(2, "b", "REGISTER", model="B"), "lot이 비어 있거나 형식이 잘못됨"),
            (row(2, "b", "REGISTER", model="B", lot="l-1"), "lot이 비어 있거나 형식이 잘못됨"),
            (row(2, "a", "P1", lot="L1"), "REGISTER 이외의 lot은 빈칸이어야 함"),
            (restart(2, lot="L1"), "REGISTER 이외의 lot은 빈칸이어야 함"),
            (restart(2, result="OK", lot="L1"), "REGISTER 이외의 lot은 빈칸이어야 함"),
            (row(2, "a", "REGISTER", model="A", lot="L2"), "이미 등록된 제품"),
        )
        for item, reason in cases:
            with self.subTest(reason=reason):
                before = copy.deepcopy((process.products, process.equipment))
                decision = process.apply(item)
                self.assertEqual((decision.accepted, decision.rule_id, decision.reason), (False, "RULE_PRESERVE", reason))
                self.assertEqual((process.products, process.equipment), before)
        self.assertEqual(process.products["a"].lot, "L1")

    def test_t69_mode_and_header_combinations(self):
        data = json.loads(PLAIN_EQUIPMENT.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            arguments = ("--recipe", str(RECIPE), "--equipment")
            off = base / "off.json"
            off.write_text(json.dumps({**data, "lot_tracking": False}), encoding="utf-8")
            one, two = base / "one", base / "two"
            one.mkdir(), two.mkdir()
            self.assertEqual(cli(one, str(SAMPLE), *arguments, str(PLAIN_EQUIPMENT)).returncode, 0)
            self.assertEqual(cli(two, str(SAMPLE), *arguments, str(off)).returncode, 0)
            for path in sorted((one / "reports").iterdir()):
                self.assertEqual(path.read_bytes(), (two / "reports" / path.name).read_bytes(), path.name)

            eight = base / "eight.csv"
            eight.write_text(",".join(LOT_INPUT_COLUMNS) + "\n", encoding="utf-8")
            self.assertEqual(cli(base, str(eight), *arguments, str(PLAIN_EQUIPMENT)).returncode, 2)
            self.assertEqual(cli(base, str(SAMPLE), *arguments, str(LOT_EQUIPMENT)).returncode, 2)
            bad = base / "bad.json"
            bad.write_text(json.dumps({**data, "lot_tracking": 1}), encoding="utf-8")
            self.assertEqual(cli(base, str(SAMPLE), *arguments, str(bad)).returncode, 3)


class ScopeTests(Base):
    def t70(self, lots="LLLLLL"):
        names = "abcdef"
        events = prepared(dict(zip(names, lots)))
        for index, (product_id, result) in enumerate(zip(names, ("PASS",) * 4 + ("FAIL",) * 2)):
            events.append(leak(100 + index, product_id, result))
        return events

    def test_t70_methods(self):
        rows = build_containment(self.analysis(self.t70()))
        self.assertEqual(rows_of(rows, "LEAK-1#1", "window"), ["d"])
        for method in ("last_10", "last_20", "since_restart"):
            self.assertEqual(rows_of(rows, "LEAK-1#1", method), ["a", "b", "c", "d"])

    def test_t71_restart_splits_the_segment(self):
        events = self.t70() + prepared({"g": "M", "h": "M", "i": "M"})
        events += [restart(200), leak(201, "g", "PASS"), leak(202, "h", "FAIL"), leak(203, "i", "FAIL")]
        rows = build_containment(self.analysis(events))
        for method in ("window", "last_10", "last_20", "since_restart"):
            self.assertEqual(rows_of(rows, "LEAK-1#2", method), ["g"])
        self.assertEqual(rows_of(rows, "LEAK-1#1", "since_restart"), ["a", "b", "c", "d"])

    def test_t72_lot_scope_uses_fail_lots(self):
        rows = build_containment(self.analysis(self.t70(("L1", "L1", "L2", "L2", "L1", "L2"))))
        self.assertEqual(rows_of(rows, "LEAK-1#1", "lot"), ["a", "b", "c", "d"])

    def test_t73_lot_scope_can_be_empty(self):
        rows = build_containment(self.analysis(self.t70(("L9",) * 4 + ("L1", "L1"))))
        self.assertEqual(rows_of(rows, "LEAK-1#1", "lot"), [])
        self.assertEqual(rows_of(rows, "LEAK-1#1", "since_restart"), ["a", "b", "c", "d"])

    def test_t74_empty_and_mode_cases(self):
        events = prepared({"a": "L", "b": "L"}) + [leak(100, "a", "FAIL"), leak(101, "b", "FAIL")]
        self.assertEqual(build_containment(self.analysis(events)), [])
        self.assertEqual(build_containment(self.analysis(prepared({"a": "L"}) + [leak(100, "a", "PASS")])), [])
        with tempfile.TemporaryDirectory() as directory:
            result = cli(directory, str(SAMPLE), "--recipe", str(RECIPE), "--containment")
            self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
            result = cli(directory, str(SAMPLE), "--recipe", str(RECIPE), "--equipment", str(PLAIN_EQUIPMENT), "--containment")
            self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
            path = Path(directory) / "reports" / "sample_events_equipment_containment.csv"
            with path.open(encoding="utf-8-sig", newline="") as source:
                self.assertNotIn("lot", [item["method"] for item in csv.DictReader(source)])

    def twelve(self):
        ids = ["p" + str(index).zfill(2) for index in range(1, 13)]
        events = prepared({name: "L" for name in ids + ["x", "y"]})
        events += [leak(100 + index, name, "PASS") for index, name in enumerate(ids)]
        return ids, events + [leak(200, "x", "FAIL"), leak(201, "y", "FAIL")]

    def test_t75_last_n_counts_recent_inspections(self):
        ids, events = self.twelve()
        rows = build_containment(self.analysis(events))
        self.assertEqual(rows_of(rows, "LEAK-1#1", "last_10"), ids[4:])
        self.assertEqual(rows_of(rows, "LEAK-1#1", "last_20"), ids)
        self.assertEqual(rows_of(rows, "LEAK-1#1", "since_restart"), ids)

    def test_t76_retest_pass_excluded_and_other_hold_included(self):
        events = prepared({"a": "L", "b": "L", "c": "L", "d": "L"}) + [
            leak(100, "a", "FAIL"), row(101, "a", "RETEST_REQUEST", "LEAK"), leak(102, "a", "PASS", "LEAK-2"),
            leak(103, "b", "PASS", "LEAK-2"), row(104, "b", "P3"), row(105, "b", "P4"),
            row(106, "b", "INSPECT", "LIGHT", "FAIL", equipment="LIGHT-1"),
            leak(107, "c", "FAIL", "LEAK-2"), leak(108, "d", "FAIL", "LEAK-2"),
        ]
        rows = build_containment(self.analysis(events))
        scoped = [item for item in rows if item["stop_key"] == "LEAK-2#1" and item["method"] == "since_restart"]
        self.assertEqual([(item["product_id"], item["final_state"]) for item in scoped], [("b", "보류")])

    def test_t82_leaks_inside_and_outside_last_10(self):
        _, events = self.twelve()
        scopes = run_scopes(self.analysis(events))
        result = containment_metrics([({"p01", "p12"}, scopes)])
        self.assertEqual(result["last_10"]["capture_rate"], 0.5)
        self.assertEqual(result["last_10"]["mean_residual"], 1)
        self.assertEqual(result["since_restart"]["capture_rate"], 1)

    def test_t86_only_allowed_restart_of_same_equipment_splits(self):
        events = prepared({name: "L" for name in "abcdefg"}) + [
            leak(100, "e", "FAIL", "LEAK-2"), leak(101, "f", "FAIL", "LEAK-2"),
            leak(102, "a", "PASS"), restart(103, "LEAK-2"), restart(104, "LEAK-1"),
            leak(105, "b", "PASS"), leak(106, "c", "FAIL"), leak(107, "d", "FAIL"),
        ]
        analysis = self.analysis(events)
        restarts = [item for item in analysis.decisions if item.input_text.startswith("EQUIP_RESTART")]
        self.assertEqual([item.accepted for item in restarts], [True, False])
        rows = build_containment(analysis)
        self.assertEqual(rows_of(rows, "LEAK-1#1", "since_restart"), ["a", "b"])


class MetricTests(unittest.TestCase):
    def test_t77_totals_not_mean_of_run_ratios(self):
        first = set(range(1, 10))
        result = containment_metrics([(first, {"window": first}), ({"x"}, {"window": set()})])["window"]
        self.assertEqual(float(result["capture_rate"]), 0.9)
        self.assertEqual(float(result["mean_residual"]), 0.5)

    def test_t78_precision_quarantine_residual(self):
        result = containment_metrics([({"p", "q", "r"}, {"lot": {"p", "q", "s", "t"}})])["lot"]
        self.assertEqual(round(float(result["capture_rate"]), 4), 0.6667)
        self.assertEqual(float(result["precision"]), 0.5)
        self.assertEqual(float(result["mean_quarantine"]), 4)
        self.assertEqual(float(result["mean_residual"]), 1)

    def item(self, capture, quarantine):
        from fractions import Fraction
        return {"capture_rate": Fraction(*capture), "mean_quarantine": Fraction(quarantine)}

    def test_t79_selection(self):
        pick = lambda methods, leaks=100, runs=50: select_method(methods, leaks, runs)
        self.assertEqual(pick({"window": self.item((8999, 10000), 1), "since_restart": self.item((9, 10), 50)})[0],
                         "since_restart")
        self.assertEqual(pick({"last_10": self.item((9, 10), 5), "since_restart": self.item((1, 1), 50)})[0], "last_10")
        self.assertEqual(pick({"last_10": self.item((1, 1), 5), "window": self.item((1, 1), 5)})[0], "window")
        self.assertEqual(pick({"window": self.item((1, 2), 5)}), (None, "기준 충족 방식 없음"))
        self.assertEqual(pick({"window": self.item((1, 1), 5)}, 29, 50), (None, "평가 표본 부족"))
        self.assertEqual(pick({"window": self.item((1, 1), 5)}, 100, 19), (None, "평가 표본 부족"))

    def test_t80_holdout_verdict(self):
        self.assertEqual(containment_verdict(self.item((91, 100), 5), 100, 50), "확인")
        self.assertEqual(containment_verdict(self.item((89, 100), 5), 100, 50), "미확인")
        self.assertEqual(containment_verdict({"capture_rate": None}, 0, 0), "미확인")
        self.assertEqual(containment_verdict(self.item((91, 100), 5), 100, 19), "미확인")


class GeneratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.models = load_recipe(RECIPE).models
        cls.book = load_equipment(LOT_EQUIPMENT, cls.models)

    def test_t81_reproducible_and_truth_stays_out_of_csv(self):
        for seed, products in ((42, 500), (7, 200)):
            with self.subTest(seed=seed), tempfile.TemporaryDirectory() as directory:
                # 같은 이름으로 따로 생성·판정해 CSV, meta, 판정 보고서 묶음 전체를 바이트 비교한다.
                snapshots = []
                for name in ("one", "two"):
                    working = Path(directory) / name
                    working.mkdir()
                    output = working / "gen.csv"
                    meta = generate(seed, products, output, LOT_CONFIG)
                    result = cli(working, str(output), "--recipe", str(RECIPE), "--equipment", str(LOT_EQUIPMENT),
                                 "--summary", "--containment")
                    self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
                    snapshots.append({path.relative_to(working).as_posix(): path.read_bytes()
                                      for path in working.rglob("*") if path.is_file()})
                self.assertIn("gen.csv.meta.json", snapshots[0])
                self.assertIn("reports/gen_containment.csv", snapshots[0])
                self.assertEqual(snapshots[0], snapshots[1])
                one = Path(directory) / "one" / "gen.csv"
                self.assertEqual(meta["generator_version"], LOT_GENERATOR_VERSION)
                self.assertEqual(meta["lot_size"], 20)
                self.assertLessEqual(set(meta["leaked_products"]), set(meta["defective_products"]))
                with one.open(encoding="utf-8-sig", newline="") as source:
                    reader = csv.DictReader(source)
                    rows = list(reader)
                self.assertEqual(tuple(reader.fieldnames), LOT_INPUT_COLUMNS)
                analysis = build_analysis(rows, self.models, self.book)
                self.assertEqual(sum(not item.accepted for item in analysis.decisions), sum(meta["injected_errors"].values()))

    def test_t81_seeds_produce_leaks(self):
        config, _, recipe, book = load_setup(LOT_CONFIG)
        self.assertGreater(sum(len(build_rows(seed, 500, config, recipe.models, book)[0].leaked_products)
                               for seed in range(30)), 0)

    def defect_lot_share(self, path):
        config, _, recipe, book = load_setup(path)
        defective, lots = 0, set()
        for seed in range(30):
            generator = build_rows(seed, 500, config, recipe.models, book)[0]
            defective += len(generator.defective_products)
            lots |= {(seed, (int(item[4:]) - 1) // 20) for item in generator.defective_products}
        return defective / (30 * 500), len(lots) / (30 * 25)

    def test_t83_clustered_defects(self):
        rate, share = self.defect_lot_share(CLUSTERED_CONFIG)
        self.assertTrue(0.03 <= rate <= 0.07, rate)
        self.assertLessEqual(share, 0.50)
        self.assertLess(share, self.defect_lot_share(LOT_CONFIG)[1])

    def test_t87_invalid_settings(self):
        config = json.loads(LOT_CONFIG.read_text(encoding="utf-8-sig"))
        config.update(recipe=str(RECIPE), equipment=str(LOT_EQUIPMENT))
        cases = (
            {"lot_size": 0}, {"lot_size": True}, {"faulty_detection_loss": {"LEAK-2": 1.5}},
            {"faulty_detection_loss": {"LEAK-1": 0.5}}, {"lot_size": None},
            {"defective_lot_probability": 0.25}, {"equipment": str(ROOT / "recipes" / "equipment_restart.json")},
        )
        for change in cases:
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                data = {**config, **change}
                if data["lot_size"] is None:
                    del data["lot_size"]
                path = Path(directory) / "config.json"
                path.write_text(json.dumps(data), encoding="utf-8")
                output = Path(directory) / "gen.csv"
                result = cli(directory, "--seed", "1", "--products", "5", "--config", str(path), "--out", str(output),
                             module="src.generate")
                self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
                self.assertFalse(output.exists())

    def test_t87_huge_integer_probability_is_a_setting_error(self):
        config = json.loads(LOT_CONFIG.read_text(encoding="utf-8-sig"))
        config.update(recipe=str(RECIPE), equipment=str(LOT_EQUIPMENT))
        huge = 10 ** 400
        cases = (
            {"faulty_detection_loss": {"LEAK-2": huge}},
            {"defective_lot_probability": huge, "defective_in_lot_probability": 0.5},
        )
        for change in cases:
            with self.subTest(change=sorted(change)), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "config.json"
                path.write_text(json.dumps({**config, **change}), encoding="utf-8")
                output = Path(directory) / "gen.csv"
                result = cli(directory, "--seed", "1", "--products", "5", "--config", str(path), "--out", str(output),
                             module="src.generate")
                self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
                self.assertFalse(output.exists())
                result = cli(directory, "--containment", "--config", str(path), "--rules", "3:2", "--seeds", "0-1",
                             "--products", "5", "--out", "bad", module="src.evaluate")
                self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
                self.assertFalse((Path(directory) / "reports").exists())


class MetaTests(unittest.TestCase):
    def test_t88_leaked_products_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "gen.csv"
            meta = generate(1, 30, path, LOT_CONFIG)
            base = {**meta, "defective_products": ["GEN_0001"], "leaked_products": ["GEN_0001"]}
            cases = (
                {"leaked_products": [""]}, {"leaked_products": ["GEN_0001", "GEN_0001"]},
                {"leaked_products": ["GEN_0002"]}, {"defective_products": None},
                {"defective_products": ["GEN_9999"], "leaked_products": ["GEN_9999"]},
            )
            arguments = (str(path), "--recipe", str(RECIPE), "--equipment", str(LOT_EQUIPMENT), "--summary")
            for change in cases:
                with self.subTest(change=change):
                    data = {**base, **change}
                    if data["defective_products"] is None:
                        del data["defective_products"]
                    Path(str(path) + ".meta.json").write_text(json.dumps(data), encoding="utf-8")
                    result = cli(directory, *arguments)
                    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))


class CommandTests(unittest.TestCase):
    base = ("--containment", "--seeds", "0-1", "--products", "40")

    def test_t84_bad_commands_exit_two_without_reports(self):
        config = json.loads(LOT_CONFIG.read_text(encoding="utf-8-sig"))
        config.update(recipe=str(RECIPE), equipment=str(LOT_EQUIPMENT),
                      faulty_equipment={"LEAK-1": 0.1, "LEAK-2": 0.1})
        with tempfile.TemporaryDirectory() as directory:
            two = Path(directory) / "two.json"
            two.write_text(json.dumps(config), encoding="utf-8")
            restart_config = ROOT / "recipes" / "generator_restart.json"
            cases = (
                ("--config", str(LOT_CONFIG), "--rules", "3:2,5:2"), ("--config", str(LOT_CONFIG), "--rules", "5:2"),
                ("--config", str(restart_config), "--rules", "3:2"), ("--config", str(two), "--rules", "3:2"),
                ("--config", str(LOT_CONFIG), "--rules", "3:2", "--holdout"),
            )
            for case in cases:
                with self.subTest(case=case):
                    result = cli(directory, *self.base, *case, "--out", "bad", module="src.evaluate")
                    self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8"))
                    self.assertFalse((Path(directory) / "reports").exists())

    def test_t85_same_command_same_report(self):
        arguments = (*self.base, "--config", str(LOT_CONFIG), "--rules", "3:2")
        with tempfile.TemporaryDirectory() as directory:
            for name in ("one", "two"):
                self.assertEqual(cli(directory, *arguments, "--out", name, module="src.evaluate").returncode, 0)
            reports = Path(directory) / "reports"
            one = (reports / "one_containment.csv").read_bytes()
            self.assertEqual(one, (reports / "two_containment.csv").read_bytes())
            self.assertIn("config_sha256", one.decode("utf-8-sig"))

    def report(self, directory, selection_rows, sha):
        path = Path(directory) / "dev.csv"
        with path.open("w", encoding="utf-8-sig", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=("section", "method", "value"))
            writer.writeheader()
            writer.writerow({"section": "provenance", "method": "config_sha256", "value": sha})
            writer.writerows(selection_rows)
        return path

    def test_t80_selection_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            chosen = [{"section": "selection", "method": "last_10", "value": "선택"}]
            self.assertEqual(read_selection(self.report(directory, chosen, "abc"), "abc"), "last_10")
            empty = [{"section": "selection", "method": "", "value": "평가 표본 부족"}]
            self.assertIsNone(read_selection(self.report(directory, empty, "abc"), "abc"))
            with self.assertRaises(ValueError):
                read_selection(self.report(directory, chosen, "abc"), "other")
            with self.assertRaises(ValueError):
                read_selection(self.report(directory, [], "abc"), "abc")

    def test_t80_no_selection_exits_zero(self):
        arguments = ("--containment", "--config", str(LOT_CONFIG), "--rules", "3:2", "--products", "40")
        with tempfile.TemporaryDirectory() as directory:
            result = cli(directory, *arguments, "--seeds", "0-1", "--out", "dev", module="src.evaluate")
            self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
            dev = Path(directory) / "reports" / "dev_containment.csv"
            self.assertIn("평가 표본 부족", dev.read_text(encoding="utf-8-sig"))
            result = cli(directory, *arguments, "--seeds", "1000-1001", "--out", "hold", "--holdout",
                         "--selected-from", str(dev), module="src.evaluate")
            self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
            text = (Path(directory) / "reports" / "hold_containment.csv").read_text(encoding="utf-8-sig")
            self.assertIn("검증할 선택 없음", text)
            self.assertNotIn("selection", text)

    def test_t80_runs_without_stops_keep_every_method(self):
        config = json.loads(LOT_CONFIG.read_text(encoding="utf-8-sig"))
        config.update(recipe=str(RECIPE), equipment=str(LOT_EQUIPMENT), error_rate=0, normal_fail_probability=0,
                      defective_product_probability=0, faulty_equipment={"LEAK-2": 0})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            arguments = ("--containment", "--config", str(path), "--rules", "3:2", "--products", "40")
            result = cli(directory, *arguments, "--seeds", "0-1", "--out", "dev", module="src.evaluate")
            self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
            with (Path(directory) / "reports" / "dev_containment.csv").open(encoding="utf-8-sig", newline="") as source:
                rows = [item for item in csv.DictReader(source) if item["section"] == "method"]
            self.assertEqual([item["method"] for item in rows], ["window", "last_10", "last_20", "lot", "since_restart"])
            for item in rows:
                self.assertEqual((item["runs"], item["leak_runs"], item["leaks"], item["stops"]), ("2", "0", "0", "0"))
                self.assertEqual((item["capture_rate"], item["precision"], item["mean_quarantine"], item["mean_residual"]),
                                 ("", "", "0.00", "0.00"))

            sha = hashlib.sha256(path.read_bytes()).hexdigest()
            chosen = self.report(directory, [{"section": "selection", "method": "last_10", "value": "선택"}], sha)
            result = cli(directory, *arguments, "--seeds", "1000-1001", "--out", "hold", "--holdout",
                         "--selected-from", str(chosen), module="src.evaluate")
            self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
            with (Path(directory) / "reports" / "hold_containment.csv").open(encoding="utf-8-sig", newline="") as source:
                verdict = [item for item in csv.DictReader(source) if item["section"] == "holdout_verdict"]
            self.assertEqual([(item["method"], item["value"]) for item in verdict], [("last_10", "미확인")])


if __name__ == "__main__":
    unittest.main()

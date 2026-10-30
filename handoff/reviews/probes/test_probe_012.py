"""Review 012: independent adversarial probes; production files are never changed.

Run: py -m unittest handoff/reviews/probes/test_probe_012.py
All CLI outputs and generated fixtures live inside TemporaryDirectory.
The CLI uses sys.executable so it uses the same interpreter as the test runner.
"""

import copy
import csv
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from src.containment import METHODS, build_containment, run_scopes
from src.equipment import load_equipment
from src.evaluate import CONTAINMENT_COLUMNS
from src.generate import Generator, build_rows, generate, load_setup
from src.recipe import load_recipe
from src.recipe_rules import LOT_INPUT_COLUMNS, RecipeProcess
from src.summary import build_analysis

ROOT = Path(__file__).resolve().parents[3]
BASE = "d12e92e48c9cfc0bc716d54a39d169120ca581f8"
RECIPE = ROOT / "recipes/lamp_models_retest.json"
EQUIPMENT = ROOT / "recipes/equipment_lot.json"
CONFIG = ROOT / "recipes/generator_lot.json"


def row(pid, event, seq=1, inspection="", result="", model="", equipment="", lot=""):
    return dict(zip(LOT_INPUT_COLUMNS, (str(seq), pid, event, inspection, result, model, equipment, lot)))


def prepare(*ids):
    return [r for pid in ids for r in (
        row(pid, "REGISTER", model="B", lot="L1"), row(pid, "P1"), row(pid, "P2"))]


def inspect(pid, result, seq=1):
    return row(pid, "INSPECT", seq, "LEAK", result, equipment="LEAK-1")


def cli(directory, module, *args):
    return subprocess.run(
        [sys.executable, "-m", module, *map(str, args)], cwd=directory,
        env={**os.environ, "PYTHONPATH": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1",
             "PYTHONIOENCODING": "utf-8"}, capture_output=True, text=True, encoding="utf-8", timeout=240,
    )


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def config_fixture(directory, **changes):
    data = json.loads(CONFIG.read_text(encoding="utf-8-sig"))
    data.update(recipe=str(RECIPE), equipment=str(EQUIPMENT))
    data.update(changes)
    path = Path(directory) / "config.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


class AdversarialProbes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.models = load_recipe(RECIPE).models
        cls.book = load_equipment(EQUIPMENT, cls.models)

    def test_p01_structure_seq_lot_priority_and_recovery(self):
        """Combined errors, rejected registration, then valid registration of the same ID."""
        process = RecipeProcess(self.models, self.book)
        bad = row("p", "REGISTER", seq=0, model="UNKNOWN", lot="lower")
        cases = [(dict(bad, extra=""), "CSV 열 수 또는 값 누락"),
                 (bad, "seq는 양의 정수여야 함"),
                 (dict(bad, seq="1"), "lot이 비어 있거나 형식이 잘못됨")]
        for candidate, reason in cases:
            before = copy.deepcopy((process.products, process.equipment))
            decision = process.apply(candidate)
            self.assertEqual((decision.accepted, decision.reason), (False, reason))
            self.assertEqual((process.products, process.equipment), before)
        self.assertTrue(process.apply(row("p", "REGISTER", model="B", lot="L1")).accepted)
        for lot in (" L1", "L1 ", "L1\n", "l1", "Ｌ1"):
            before = copy.deepcopy((process.products, process.equipment))
            decision = process.apply(row("p", "REGISTER", model="B", lot=lot))
            self.assertEqual(decision.reason, "lot이 비어 있거나 형식이 잘못됨")
            self.assertEqual((process.products, process.equipment), before)
        self.assertTrue(process.apply(row("p", "P1")).accepted)
        self.assertEqual(process.products["p"].lot, "L1")

    def test_p02_physical_order_rejections_and_future_rows(self):
        """Decreasing/duplicate seq plus rejected PASS and accepted PASS after a restart."""
        events = prepare("a", "b", "c", "d", "e", "f") + [
            inspect("a", "PASS", 900),
            dict(inspect("b", "PASS", 800), lot="WRONG"),
            inspect("b", "PASS", 3), inspect("c", "FAIL", 3), inspect("d", "FAIL", 2),
            inspect("e", "PASS", 1),
            row("", "EQUIP_RESTART", result="NO_FAULT", equipment="LEAK-1"),
            inspect("f", "PASS", 1),
        ]
        analysis = build_analysis(events, self.models, self.book)
        before = copy.deepcopy((analysis.process.products, analysis.process.equipment,
                                analysis.events, analysis.stop_history, analysis.restarts))
        rows = build_containment(analysis)
        self.assertEqual((analysis.process.products, analysis.process.equipment,
                          analysis.events, analysis.stop_history, analysis.restarts), before)
        chosen = [r for r in rows if r["method"] == "since_restart"]
        self.assertEqual([(r["product_id"], r["seq"]) for r in chosen], [("a", "900"), ("b", "3")])
        self.assertEqual([r["row_index"] for r in chosen], [19, 21])
        self.assertFalse(analysis.decisions[19].accepted)
        self.assertFalse(analysis.decisions[23].accepted)
        self.assertTrue(analysis.decisions[-1].accepted)

    def test_p03_lot_without_restart_or_retest(self):
        """Lot tracking is independent of both earlier optional modes."""
        models = load_recipe(ROOT / "recipes/lamp_models.json").models
        book = replace(self.book, restart_enabled=False)
        analysis = build_analysis(prepare("a", "b", "c") + [
            inspect("a", "PASS"), inspect("b", "FAIL"), inspect("c", "FAIL")], models, book)
        self.assertTrue(all(d.accepted for d in analysis.decisions))
        self.assertEqual(run_scopes(analysis), {method: {"a"} for method in METHODS})
        self.assertEqual(analysis.process.products["a"].lot, "L1")

    def test_p04_no_stop_development_has_all_zero_metrics(self):
        """No stops still means five empty C sets, not absence of the methods."""
        with tempfile.TemporaryDirectory() as directory:
            config = config_fixture(directory, error_rate=0, normal_fail_probability=0,
                                    defective_product_probability=0, faulty_equipment={"LEAK-2": 0})
            result = cli(directory, "src.evaluate", "--containment", "--config", config,
                         "--seeds", "0-1", "--products", "40", "--rules", "3:2", "--out", "zero")
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = read_csv(Path(directory) / "reports/zero_containment.csv")
            metrics = [r for r in rows if r["section"] == "method"]
            self.assertEqual([r["method"] for r in metrics], list(METHODS), repr(rows))
            for r in metrics:
                self.assertEqual((r["runs"], r["leak_runs"], r["leaks"], r["stops"]), ("2", "0", "0", "0"))
                self.assertEqual((r["capture_rate"], r["precision"], r["mean_quarantine"], r["mean_residual"]),
                                 ("", "", "0.00", "0.00"))

    def test_p05_selected_holdout_without_stops_is_unconfirmed(self):
        """A valid selection followed by zero events must say unconfirmed, not error."""
        # Uses the ordinary supplied config. A 1-product holdout may have no stop.
        # The selection reader's contract is a selection row plus matching config SHA.
        with tempfile.TemporaryDirectory() as directory:
            selection = Path(directory) / "dev.csv"
            blank = dict.fromkeys(CONTAINMENT_COLUMNS, "")
            with selection.open("w", encoding="utf-8-sig", newline="") as target:
                writer = csv.DictWriter(target, fieldnames=CONTAINMENT_COLUMNS)
                writer.writeheader()
                writer.writerow({**blank, "section": "provenance", "method": "config_sha256",
                                 "value": hashlib.sha256(CONFIG.read_bytes()).hexdigest()})
                writer.writerow({**blank, "section": "selection", "method": "last_10", "value": "선택"})
            result = cli(directory, "src.evaluate", "--containment", "--holdout", "--config", CONFIG,
                         "--selected-from", selection, "--seeds", "1000-1000", "--products", "1",
                         "--rules", "3:2", "--out", "hold")
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = read_csv(Path(directory) / "reports/hold_containment.csv")
            verdict = [r for r in rows if r["section"] == "holdout_verdict"]
            self.assertEqual([(r["method"], r["value"]) for r in verdict], [("last_10", "미확인")])

    def test_p06_huge_integer_probability_is_a_clean_configuration_error(self):
        """Valid JSON integer outside [0,1] must exit 2, just like 1.5 or NaN."""
        with tempfile.TemporaryDirectory() as directory:
            config = config_fixture(directory, faulty_detection_loss={"LEAK-2": 10 ** 400})
            for module, args in (
                ("src.generate", ("--out", Path(directory) / "bad.csv", "--seed", "1")),
                ("src.evaluate", ("--containment", "--seeds", "0-0", "--rules", "3:2", "--out", "bad")),
            ):
                with self.subTest(module=module):
                    result = cli(directory, module, "--config", config, "--products", "40", *args)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertNotIn("Traceback", result.stderr)
                    self.assertFalse((Path(directory) / "bad.csv").exists())
                    self.assertFalse((Path(directory) / "reports").exists())

    def test_p07_loss_applies_to_retests_and_stops_after_repair(self):
        config, _, recipe, book = load_setup(CONFIG)
        for repaired, expected in ((False, "PASS"), (True, "FAIL")):
            with self.subTest(repaired=repaired):
                gen = Generator(1, config, recipe.models, book)
                gen.choose_equipment = lambda inspection, avoid="": "LEAK-2"
                if repaired:
                    gen.repaired.add("LEAK-2")
                # Defective draw, first FAIL (<.45), request (<.70), retest .50.
                with patch.object(gen.rng, "random", side_effect=[0, .40, 0, .50]):
                    flow = gen.product("p", "B", 1)
                    results = []
                    while len(results) < 2:
                        item, _ = next(flow)
                        if item["event"] == "INSPECT":
                            results.append(item["result"])
                self.assertEqual(results, ["FAIL", expected])
                self.assertEqual(gen.leaked_products, [])

    def test_p08_no_stop_leaks_remain_in_the_denominator(self):
        """Since-restart cannot catch a leak on equipment that never stops."""
        config, _, recipe, book = load_setup(CONFIG)
        generator, _, rows, _ = build_rows(15, 500, config, recipe.models, book)
        analysis = build_analysis(rows, recipe.models, book)
        missing = set(generator.leaked_products) - run_scopes(analysis)["since_restart"]
        self.assertEqual(len(missing), 7)
        self.assertNotIn("LEAK-2", {stop.equipment for stop in analysis.stop_history})
        self.assertTrue(all(any(r.product_id == pid and r.equipment == "LEAK-2" and r.result == "PASS"
                                for r in analysis.first_inspections) for pid in missing))


class PreservationChecks(unittest.TestCase):
    def assert_success(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)

    def compare_reports(self, directory):
        paths = sorted((Path(directory) / "reports").glob("*.csv"))
        self.assertTrue(paths)
        for path in paths:
            self.assertEqual(path.read_bytes(), (ROOT / "reports" / path.name).read_bytes(), path.name)
        return len(paths)

    def test_p09_protected_tracked_files_unchanged(self):
        paths = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", BASE,
                                         "tests", "src/rules.py", "recipes", "data", "reports"], cwd=ROOT,
                                        text=True, encoding="utf-8").splitlines()
        changed = subprocess.check_output(["git", "diff", "--name-only", BASE, "--", *paths], cwd=ROOT,
                                          text=True, encoding="utf-8")
        self.assertEqual(changed, "")
        print("P09 protected tracked files unchanged:", len(paths))

    def test_p10_old_samples_and_seed42_reports_are_byte_identical(self):
        with tempfile.TemporaryDirectory() as directory:
            for name, recipe, equipment in (
                ("sample_events", None, None), ("sample_events_v2", "lamp_models.json", None),
                ("sample_events_retest", "lamp_models_retest.json", None),
                ("sample_events_equipment", "lamp_models_retest.json", "equipment.json"),
                ("sample_events_restart", "lamp_models_retest.json", "equipment_restart.json"),
            ):
                args = [ROOT / "data" / (name + ".csv")]
                if recipe:
                    args += ["--recipe", ROOT / "recipes" / recipe]
                if equipment:
                    args += ["--equipment", ROOT / "recipes" / equipment]
                if name == "sample_events_restart":
                    args += ["--summary", "--trace", "f"]
                self.assert_success(cli(directory, "src.main", *args))
            generated = Path(directory) / "gen_seed42.csv"
            generate(42, 500, generated, ROOT / "recipes/generator.json")
            for suffix in ("", ".meta.json"):
                self.assertEqual(Path(str(generated) + suffix).read_bytes(),
                                 (ROOT / "data/generated" / ("gen_seed42.csv" + suffix)).read_bytes())
            self.assert_success(cli(directory, "src.main", generated, "--recipe", RECIPE,
                                    "--equipment", ROOT / "recipes/equipment_generated.json", "--summary",
                                    "--trace", "GEN_0005", "--trace", "GEN_0030"))
            print("P10 old sample/seed42 reports byte-identical:", self.compare_reports(directory), "; CSV/meta: 2")

    def test_p11_old_evaluation_reports_are_byte_identical(self):
        with tempfile.TemporaryDirectory() as directory:
            for out, config, seeds, rules, extra in (
                ("eval_dev", "generator_restart.json", "0-99", "3:2,5:2,5:3,10:3,10:4,20:4", ()),
                ("eval_holdout", "generator_restart.json", "1000-1099", "3:2", ("--holdout",)),
                ("eval_baseline", "generator.json", "0-99", "3:2", ("--holdout",)),
            ):
                self.assert_success(cli(directory, "src.evaluate", "--config", ROOT / "recipes" / config,
                                        "--seeds", seeds, "--rules", rules, "--out", out, *extra))
            print("P11 old evaluation reports byte-identical:", self.compare_reports(directory))

    def test_p12_submitted_lot_evaluation_and_sample_reports_reproduce(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assert_success(cli(directory, "src.main", ROOT / "data/sample_events_lot.csv", "--recipe", RECIPE,
                                    "--equipment", EQUIPMENT, "--summary", "--containment"))
            for setting in ("lot", "lot_clustered"):
                config = ROOT / "recipes" / ("generator_" + setting + ".json")
                dev = "eval_" + setting + "_dev"
                self.assert_success(cli(directory, "src.evaluate", "--containment", "--config", config,
                                        "--seeds", "0-99", "--rules", "3:2", "--out", dev))
                self.assert_success(cli(directory, "src.evaluate", "--containment", "--config", config,
                                        "--seeds", "1000-1099", "--rules", "3:2", "--out",
                                        "eval_" + setting + "_holdout", "--holdout", "--selected-from",
                                        Path(directory) / "reports" / (dev + "_containment.csv")))
            print("P12 submitted lot reports byte-identical:", self.compare_reports(directory))

    def test_p13_t81_meta_and_full_reports_reproduce(self):
        for seed, products in ((42, 500), (7, 200)):
            with self.subTest(seed=seed), tempfile.TemporaryDirectory() as directory:
                snapshots = []
                for repeat in ("a", "b"):
                    working = Path(directory) / repeat
                    working.mkdir()
                    output = working / "generated.csv"
                    generate(seed, products, output, CONFIG)
                    self.assert_success(cli(working, "src.main", output, "--recipe", RECIPE,
                                            "--equipment", EQUIPMENT, "--summary", "--containment"))
                    snapshots.append({p.relative_to(working).as_posix(): p.read_bytes()
                                      for p in working.rglob("*") if p.is_file()})
                self.assertEqual(snapshots[0], snapshots[1])
                self.assertEqual(len(snapshots[0]), 8)
        print("P13 T81 CSV/meta/6 reports reproduce: seeds 42/500 and 7/200")


if __name__ == "__main__":
    unittest.main()

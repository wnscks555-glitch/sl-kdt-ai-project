"""Review 013: focused adversarial checks and required preservation checks.

Run: py -m unittest handoff/reviews/probes/test_probe_013.py
Generated files are confined to TemporaryDirectory; no prior probe is imported.
"""
import copy
import csv
from dataclasses import replace
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from src.containment import METHODS, build_containment, run_scopes
from src.equipment import load_equipment
from src.evaluate import containment_metrics
from src.generate import check_lot_config, generate, load_setup
from src.recipe import load_recipe
from src.recipe_rules import LOT_INPUT_COLUMNS
from src.summary import build_analysis

ROOT = Path(__file__).resolve().parents[3]
BASE = "d12e92e48c9cfc0bc716d54a39d169120ca581f8"
RECIPE = ROOT / "recipes/lamp_models_retest.json"
EQUIPMENT = ROOT / "recipes/equipment_lot.json"
CONFIG = ROOT / "recipes/generator_lot.json"


def cli(directory, module, *args):
    return subprocess.run(
        [sys.executable, "-m", module, *map(str, args)], cwd=directory,
        env={**os.environ, "PYTHONPATH": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1",
             "PYTHONIOENCODING": "utf-8"}, capture_output=True, text=True,
        encoding="utf-8", timeout=300)


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def fixture(directory, **changes):
    data = json.loads(CONFIG.read_text(encoding="utf-8-sig"))
    data.update(recipe=str(RECIPE), equipment=str(EQUIPMENT))
    data.update(changes)
    path = Path(directory) / "config.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def event(pid, name, result="", lot="", model="", seq=1):
    return dict(zip(LOT_INPUT_COLUMNS, (str(seq), pid, name,
                    "LEAK" if name == "INSPECT" else "", result, model,
                    "LEAK-1" if name == "INSPECT" else "", lot)))


def prepared(*ids):
    return [item for pid in ids for item in (
        event(pid, "REGISTER", lot="L1", model="B"), event(pid, "P1"), event(pid, "P2"))]


class FocusedProbes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.models = load_recipe(RECIPE).models
        cls.book = load_equipment(EQUIPMENT, cls.models)

    def success(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_p01_empty_scopes_mode_combinations(self):
        for lot in (False, True):
            for restart in (False, True):
                with self.subTest(lot=lot, restart=restart):
                    book = replace(self.book, lot_tracking=lot, restart_enabled=restart)
                    analysis = build_analysis([], self.models, book)
                    result = run_scopes(analysis)
                    expected = [m for m in METHODS if lot or m != "lot"]
                    self.assertEqual(list(result), expected)
                    self.assertTrue(all(value == set() for value in result.values()))
                    self.assertEqual(build_containment(analysis), [])
                    # The empty sets must not share storage across methods or calls.
                    result["window"].add("sentinel")
                    self.assertTrue(all(not result[m] for m in expected if m != "window"))
                    self.assertTrue(all(not s for s in run_scopes(analysis).values()))
        print("P01: four lot/restart combinations; independent empty sets; no report rows")

    def test_p02_no_stop_with_actual_leaks_retains_denominator(self):
        with tempfile.TemporaryDirectory() as directory:
            config = fixture(directory, error_rate=0, defective_product_probability=1,
                             defective_fail_probability=0, normal_fail_probability=0,
                             faulty_equipment={"LEAK-2": 0})
            self.success(cli(directory, "src.evaluate", "--containment", "--config", config,
                             "--rules", "3:2", "--seeds", "0-1", "--products", "12", "--out", "dev"))
            rows = read_csv(Path(directory) / "reports/dev_containment.csv")
            methods = [r for r in rows if r["section"] == "method"]
            self.assertEqual([r["method"] for r in methods], list(METHODS))
            for row in methods:
                self.assertGreater(int(row["leaks"]), 0)
                self.assertEqual((row["runs"], row["leak_runs"], row["stops"]), ("2", "2", "0"))
                self.assertEqual((row["capture_rate"], row["precision"], row["mean_quarantine"]),
                                 ("0.0000", "", "0.00"))
                self.assertEqual(Fraction(row["mean_residual"]), Fraction(int(row["leaks"]), 2))
            print("P02: no stops, leaks=" + methods[0]["leaks"] + "; capture=0.0000; residual=" + methods[0]["mean_residual"])

    def test_p03_every_selected_method_without_stops(self):
        with tempfile.TemporaryDirectory() as directory:
            config = fixture(directory, error_rate=0, defective_product_probability=0,
                             normal_fail_probability=0, faulty_equipment={"LEAK-2": 0})
            chosen = Path(directory) / "selection.csv"
            sha = hashlib.sha256(config.read_bytes()).hexdigest()
            for method in METHODS:
                with self.subTest(method=method):
                    with chosen.open("w", encoding="utf-8-sig", newline="") as target:
                        writer = csv.DictWriter(target, fieldnames=("section", "method", "value"))
                        writer.writeheader()
                        writer.writerows([{"section": "provenance", "method": "config_sha256", "value": sha},
                                          {"section": "selection", "method": method, "value": "선택"}])
                    self.success(cli(directory, "src.evaluate", "--containment", "--config", config,
                                     "--rules", "3:2", "--seeds", "1000-1000", "--products", "1",
                                     "--out", method, "--holdout", "--selected-from", chosen))
                    rows = read_csv(Path(directory) / "reports" / (method + "_containment.csv"))
                    self.assertEqual([r["method"] for r in rows if r["section"] == "method"], list(METHODS))
                    self.assertEqual([(r["method"], r["value"]) for r in rows if r["section"] == "holdout_verdict"],
                                     [(method, "미확인")])
                    self.assertFalse(any(r["section"] == "selection" for r in rows))
            print("P03: all five selected methods exit 0 / unconfirmed; no reselection")

    def test_p04_mixed_runs_rejection_and_scope_purity(self):
        rows = prepared("a", "b", "c") + [event("a", "INSPECT", "PASS"),
                event("b", "INSPECT", "FAIL"), event("c", "INSPECT", "FAIL")]
        stopped = build_analysis(rows, self.models, self.book)
        no_stop_rows = prepared("d") + [event("d", "INSPECT", "FAIL", lot="bad"),
                                       event("d", "INSPECT", "PASS")]
        no_stop = build_analysis(no_stop_rows, self.models, self.book)
        self.assertEqual([d.accepted for d in no_stop.decisions[-2:]], [False, True])
        before = copy.deepcopy((no_stop.process.products, no_stop.process.equipment))
        empty = run_scopes(no_stop)
        self.assertEqual((no_stop.process.products, no_stop.process.equipment), before)
        result = containment_metrics([({"a"}, run_scopes(stopped)), ({"d"}, empty)])
        for method in METHODS:
            self.assertEqual(result[method]["capture_rate"], Fraction(1, 2))
            self.assertEqual(result[method]["mean_quarantine"], Fraction(1, 2))
            self.assertEqual(result[method]["mean_residual"], Fraction(1, 2))
        print("P04: rejected FAIL does not stop; mixed runs capture/quarantine/residual=1/2; state unchanged")

    def test_p05_huge_signed_integers_in_all_three_probabilities(self):
        for key in ("faulty_detection_loss", "defective_lot_probability", "defective_in_lot_probability"):
            for value in (10 ** 400, -(10 ** 400)):
                with self.subTest(key=key, positive=value > 0), tempfile.TemporaryDirectory() as directory:
                    changes = {"defective_lot_probability": 0.25, "defective_in_lot_probability": 0.2}
                    changes[key] = {"LEAK-2": value} if key == "faulty_detection_loss" else value
                    config = fixture(directory, **changes)
                    results = [cli(directory, "src.generate", "--config", config, "--seed", "0",
                                   "--products", "5", "--out", "gen.csv"),
                               cli(directory, "src.evaluate", "--containment", "--config", config,
                                   "--rules", "3:2", "--seeds", "0-0", "--products", "5", "--out", "bad")]
                    for result in results:
                        self.assertEqual(result.returncode, 2, result.stderr)
                        self.assertNotIn("Traceback", result.stderr)
                    self.assertEqual({p.name for p in Path(directory).iterdir()}, {"config.json"})
        print("P05: +/- 10**400 in all three probability fields; 12 CLI errors exit 2; no output")

    def test_p06_nonfinite_types_and_nearest_valid_boundaries(self):
        config, _, _, book = load_setup(CONFIG)
        keys = ("faulty_detection_loss", "defective_lot_probability", "defective_in_lot_probability")
        invalid = (math.nan, math.inf, -math.inf, True, False, None, "0.5", [], {},
                   math.nextafter(0.0, -math.inf), math.nextafter(1.0, math.inf))
        valid = (0, 1, -0.0, math.nextafter(0.0, 1.0), math.nextafter(1.0, 0.0))
        for key in keys:
            for value in (*invalid, *valid):
                with self.subTest(key=key, value=repr(value)):
                    candidate = {**config, "defective_lot_probability": 0.25, "defective_in_lot_probability": 0.2}
                    candidate[key] = {"LEAK-2": value} if key == "faulty_detection_loss" else value
                    if any(value is item for item in invalid):
                        with self.assertRaises(ValueError):
                            check_lot_config(candidate, book)
                    else:
                        check_lot_config(candidate, book)
        print("P06: 33 invalid type/nonfinite/outside-boundary cases rejected; 15 valid boundary cases accepted")

    def test_p07_rejected_configuration_then_valid_run_same_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            config = fixture(directory, faulty_detection_loss={"LEAK-2": -(10 ** 400)})
            args = ("--config", config, "--seed", "7", "--products", "20", "--out", "gen.csv")
            bad = cli(directory, "src.generate", *args)
            self.assertEqual(bad.returncode, 2, bad.stderr)
            config = fixture(directory, error_rate=0)
            self.success(cli(directory, "src.generate", *args))
            self.success(cli(directory, "src.main", Path(directory) / "gen.csv", "--recipe", RECIPE,
                             "--equipment", EQUIPMENT, "--summary", "--containment"))
            rows = read_csv(Path(directory) / "reports/gen_rejections.csv")
            self.assertEqual(len(rows), 8)
            self.assertTrue(all(row["rejection_count"] == "0" for row in rows), rows)
            self.assertEqual(json.loads((Path(directory) / "gen.csv.meta.json").read_text(encoding="utf-8"))["generator_version"], "1.3.0")
            print("P07: rejected config leaves no partial output; corrected config generates and judges successfully")


class PreservationChecks(unittest.TestCase):
    def success(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)

    def compare_reports(self, directory, expected):
        paths = sorted((Path(directory) / "reports").glob("*.csv"))
        self.assertEqual(len(paths), expected)
        for path in paths:
            self.assertEqual(path.read_bytes(), (ROOT / "reports" / path.name).read_bytes(), path.name)
        return len(paths)

    def test_p08_protected_tracked_files_unchanged(self):
        paths = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", BASE,
                                         "tests", "src/rules.py", "recipes", "data", "reports"], cwd=ROOT,
                                        text=True, encoding="utf-8").splitlines()
        changes = subprocess.check_output(["git", "diff", "--name-only", BASE, "--", *paths], cwd=ROOT,
                                          text=True, encoding="utf-8")
        self.assertEqual(changes, "")
        print("P08: protected pre-stage6 tracked files unchanged:", len(paths))

    def test_p09_previous_modes_samples_and_seed42_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            for name, recipe, equipment in (
                ("sample_events", None, None), ("sample_events_v2", "lamp_models.json", None),
                ("sample_events_retest", "lamp_models_retest.json", None),
                ("sample_events_equipment", "lamp_models_retest.json", "equipment.json"),
                ("sample_events_restart", "lamp_models_retest.json", "equipment_restart.json")):
                args = [ROOT / "data" / (name + ".csv")]
                if recipe:
                    args += ["--recipe", ROOT / "recipes" / recipe]
                if equipment:
                    args += ["--equipment", ROOT / "recipes" / equipment]
                if name == "sample_events_restart":
                    args += ["--summary", "--trace", "f"]
                self.success(cli(directory, "src.main", *args))
            generated = Path(directory) / "gen_seed42.csv"
            generate(42, 500, generated, ROOT / "recipes/generator.json")
            for suffix in ("", ".meta.json"):
                self.assertEqual(Path(str(generated) + suffix).read_bytes(),
                                 (ROOT / "data/generated" / ("gen_seed42.csv" + suffix)).read_bytes())
            self.success(cli(directory, "src.main", generated, "--recipe", RECIPE,
                             "--equipment", ROOT / "recipes/equipment_generated.json", "--summary",
                             "--trace", "GEN_0005", "--trace", "GEN_0030"))
            print("P09: existing reports byte-identical:", self.compare_reports(directory, 26), "; CSV/meta: 2")

    def test_p10_previous_evaluation_report_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            for out, config, seeds, rules, extra in (
                ("eval_dev", "generator_restart.json", "0-99", "3:2,5:2,5:3,10:3,10:4,20:4", ()),
                ("eval_holdout", "generator_restart.json", "1000-1099", "3:2", ("--holdout",)),
                ("eval_baseline", "generator.json", "0-99", "3:2", ("--holdout",))):
                self.success(cli(directory, "src.evaluate", "--config", ROOT / "recipes" / config,
                                 "--seeds", seeds, "--rules", rules, "--out", out, *extra))
                print("P10 completed:", out, flush=True)
            print("P10: previous evaluation reports byte-identical:", self.compare_reports(directory, 6))

    def test_p11_current_lot_evaluations_and_sample_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            self.success(cli(directory, "src.main", ROOT / "data/sample_events_lot.csv", "--recipe", RECIPE,
                             "--equipment", EQUIPMENT, "--summary", "--containment"))
            for setting in ("lot", "lot_clustered"):
                config = ROOT / "recipes" / ("generator_" + setting + ".json")
                dev = "eval_" + setting + "_dev"
                self.success(cli(directory, "src.evaluate", "--containment", "--config", config,
                                 "--seeds", "0-99", "--rules", "3:2", "--out", dev))
                self.success(cli(directory, "src.evaluate", "--containment", "--config", config,
                                 "--seeds", "1000-1099", "--rules", "3:2", "--out",
                                 "eval_" + setting + "_holdout", "--holdout", "--selected-from",
                                 Path(directory) / "reports" / (dev + "_containment.csv")))
                print("P11 completed:", setting, flush=True)
            print("P11: current sample/evaluation reports byte-identical:", self.compare_reports(directory, 10))


if __name__ == "__main__":
    unittest.main()

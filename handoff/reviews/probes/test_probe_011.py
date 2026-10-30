"""Review 011: focused recheck probes; generated files stay in tempfile.

The optional bootstrap uses the existing interpreter under a temporary py.exe
name when the Windows launcher cannot discover installed Python. No installation,
registry edit, original test edit, or previous probe execution is performed.
"""

import copy
import csv
from dataclasses import replace
from fractions import Fraction
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.dont_write_bytecode = True
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.evaluate import aggregate, evaluate, rule_rows, run_metrics, run_rows
from src.generate import Generator, build_rows, generate, load_setup
from src.recipe_rules import EQUIPMENT_INPUT_COLUMNS, RecipeProcess
from src.summary import build_analysis

BASE = "2bed3d6083149355195b1648b6477dea715c694d"
LEGACY = "400081f9735cc584ac5299e72c75a7515fca57d9"
CONFIG = ROOT / "recipes/generator_restart.json"
PLAIN_CONFIG = ROOT / "recipes/generator.json"
RECIPE = ROOT / "recipes/lamp_models_retest.json"


def bootstrap_unittest(arguments):
    """Execute py -m unittest with an existing runtime, in a temporary PATH."""
    with tempfile.TemporaryDirectory(prefix="review011-runtime-") as directory:
        target = Path(directory)
        shutil.copy2(sys.executable, target / "py.exe")
        dll = "python%d%d.dll" % sys.version_info[:2]
        shutil.copy2(Path(sys.base_prefix) / dll, target / dll)
        env = {**os.environ, "PYTHONHOME": sys.base_prefix,
               "PATH": str(target) + os.pathsep + sys.base_prefix + os.pathsep + os.environ.get("PATH", ""),
               "PYTHONPATH": str(ROOT), "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
        print("Temporary py.exe alias -> " + sys.executable, flush=True)
        print("Command: py " + " ".join(arguments), flush=True)
        # Explicit path avoids Windows CreateProcess resolving the original launcher.
        return subprocess.run([str(target / "py.exe"), *arguments], cwd=ROOT, env=env).returncode


def row(pid, name, inspection="", result="", model="", equipment=""):
    return dict(zip(EQUIPMENT_INPUT_COLUMNS, ("1", pid, name, inspection, result, model, equipment)))


def prepared(names):
    return [row(pid, name, model=model) for pid in names
            for name, model in (("REGISTER", "B"), ("P1", ""), ("P2", ""))]


def leak(pid, result="FAIL", equipment="LEAK-1"):
    return row(pid, "INSPECT", "LEAK", result, equipment=equipment)


def cli(directory, module, *arguments):
    return subprocess.run([sys.executable, "-m", module, *map(str, arguments)], cwd=directory,
                          capture_output=True, timeout=30,
                          env={**os.environ, "PYTHONPATH": str(ROOT), "PYTHONIOENCODING": "utf-8",
                               "PYTHONDONTWRITEBYTECODE": "1"})


def load_legacy_generator():
    source = subprocess.check_output(["git", "show", LEGACY + ":src/generate.py"], cwd=ROOT).decode("utf-8")
    module = types.ModuleType("src._review011_legacy")
    module.__package__ = "src"
    module.__file__ = str(ROOT / "src/generate.py")
    exec(compile(source, module.__file__, "exec"), module.__dict__)
    return module.Generator


class Probe011(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config, _, cls.recipe, cls.book = load_setup(CONFIG)

    def config_file(self, directory, restart=True, **changes):
        config = copy.deepcopy(self.config)
        config.update(recipe=str(RECIPE), equipment=str(directory / "equipment.json"), **changes)
        if not restart:
            config.pop("restart")
        equipment = json.loads((ROOT / "recipes/equipment_restart.json").read_text(encoding="utf-8-sig"))
        equipment["restart_enabled"] = restart
        (directory / "equipment.json").write_text(json.dumps(equipment), encoding="utf-8")
        path = directory / "config.json"
        path.write_text(json.dumps(config), encoding="utf-8")
        return path, equipment

    def test_p01_ordinary_restart_step_at_three_positions_matches_legacy(self):
        legacy = load_legacy_generator()
        config, _, recipe, book = load_setup(PLAIN_CONFIG)
        cases = 0
        for position in (0, 2, -1):
            models = {}
            for name, model in recipe.models.items():
                steps = list(model.steps)
                steps.insert(len(steps) if position == -1 else position, "EQUIP_RESTART")
                models[name] = replace(model, steps=tuple(steps))
            for seed in (7, 42):
                with self.subTest(position=position, seed=seed):
                    old, new = legacy(seed, config, models, book), Generator(seed, config, models, book)
                    old_normal, new_normal = old.normal_events(60), new.normal_events(60)
                    self.assertEqual(new_normal, old_normal)
                    self.assertEqual(new.inject_errors(new_normal), old.inject_errors(old_normal))
                    self.assertEqual(new.rng.getstate(), old.rng.getstate())
                    cases += 1
        print("P01: 6 legacy-name cases, normal/final rows, counts and RNG state identical", flush=True)

    def test_p02_missing_equipment_in_disabled_mode_preserves_legacy(self):
        legacy = load_legacy_generator()
        config, _, recipe, book = load_setup(PLAIN_CONFIG)
        config.update(error_rate=0, normal_fail_probability=0, defective_product_probability=0, faulty_equipment={})
        book = replace(book, equipment={"LEAK-1": "LEAK"}, restart_enabled=False)
        old, new = legacy(0, config, recipe.models, book), Generator(0, config, recipe.models, book)
        old_normal, new_normal = old.normal_events(4), new.normal_events(4)
        self.assertEqual(new_normal, old_normal)
        self.assertEqual(new.inject_errors(new_normal), old.inject_errors(old_normal))
        self.assertTrue(new_normal)
        print("P02: absent inspection equipment, restart disabled: legacy rows preserved", flush=True)

    def test_p03_missing_equipment_both_clis_exit_two_without_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            path, equipment = self.config_file(directory, error_rate=0, normal_fail_probability=0,
                                               defective_product_probability=0, faulty_equipment={})
            equipment["equipment"] = {"LEAK-1": "LEAK"}
            (directory / "equipment.json").write_text(json.dumps(equipment), encoding="utf-8")
            for module, args in (("src.generate", ("--seed", "0", "--out", directory / "events.csv")),
                                 ("src.evaluate", ("--seeds", "0-0", "--rules", "3:2", "--out", "missing"))):
                result = cli(directory, module, "--config", path, "--products", "2", *args)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("설비 파일에 없어", result.stderr.decode("utf-8"))
                self.assertNotIn("Traceback", result.stderr.decode("utf-8"))
            self.assertFalse((directory / "reports").exists())
            self.assertFalse((directory / "events.csv").exists())
            self.assertFalse((directory / "events.csv.meta.json").exists())
        print("P03: missing LIGHT equipment: generate/evaluate exit 2, no generated files", flush=True)

    def test_p04_existing_stopped_equipment_waits_and_recovers_at_delay_boundaries(self):
        for delay in (0, 1, 100):
            with self.subTest(delay=delay):
                config = copy.deepcopy(self.config)
                config.update(error_rate=0, normal_fail_probability=0, defective_product_probability=0,
                              retest_probability=1, faulty_equipment={"LEAK-1": 1}, restart={"delay_rows": delay})
                book = replace(self.book, window=1, fails=1,
                               equipment={"LEAK-1": "LEAK", "LIGHT-1": "LIGHT", "FINAL-1": "FINAL"})
                generator, normal, rows, _ = build_rows(4, 5, config, self.recipe.models, book)
                analysis = build_analysis(rows, self.recipe.models, book)
                self.assertTrue(all(item.accepted for item in analysis.decisions))
                self.assertEqual(len(analysis.restarts), 1)
                self.assertEqual(analysis.restarts[0].result, "FIXED")
                self.assertEqual(len(analysis.process.products), 5)
                self.assertTrue(all(p.status == "레시피 모의 흐름 완료" for p in analysis.process.products.values()))
                self.assertEqual(rows, normal)
                self.assertFalse(generator.pending_restarts)
        print("P04: delay 0/1/100, existing stopped equipment recovers, 5/5 products complete", flush=True)

    def test_p05_held_metric_excludes_discarded_completed_and_waiting(self):
        book = replace(self.book, window=20, fails=20)
        events = prepared("abcde") + [leak("a"), leak("b"), leak("c"),
                  row("c", "RETEST_REQUEST", "LEAK"), leak("c"),
                  row("c", "RETEST_REQUEST", "LEAK"), leak("c"),
                  leak("d", "PASS"), row("d", "P3"), row("d", "P4"),
                  row("d", "INSPECT", "LIGHT", "PASS", equipment="LIGHT-1")]
        analysis = build_analysis(events, self.recipe.models, book)
        self.assertTrue(all(d.accepted for d in analysis.decisions))
        run = run_metrics(analysis, set(), {"b", "c"})
        self.assertEqual((run.unfinished, run.held, run.normal_held, run.defective_completed), (4, 2, 1, 0))
        empty = run_metrics(build_analysis([], self.recipe.models, book), set(), set())
        metrics = aggregate([run, empty], 0)
        self.assertEqual((metrics["mean_held"], metrics["mean_normal_held"]), (1, Fraction(1, 2)))
        self.assertIsNone(metrics["detection_rate"])
        rendered = rule_rows({(3, 2): metrics}, {}, True)[-1]
        self.assertEqual((rendered["mean_held"], rendered["mean_normal_held"]), ("1.00", "0.50"))
        self.assertEqual([item["held"] for item in run_rows({(3, 2): [run, empty]}, [0, 1])], [2, 0])
        print("P05: mixed states -> unfinished/held/normal_held=4/2/1; means=1.00/0.50", flush=True)

    def test_p06_bad_case_then_valid_then_duplicate_restart_preserves_held(self):
        process = RecipeProcess(self.recipe.models, self.book)
        prefix = prepared("abc") + [leak("a"), leak("b")]
        for event in prefix:
            self.assertTrue(process.apply(event).accepted)
        invalid = row("", "EQUIP_RESTART", result="fixed", equipment="LEAK-1")
        before = copy.deepcopy((process.products, process.equipment))
        self.assertFalse(process.apply(invalid).accepted)
        self.assertEqual(before, (process.products, process.equipment))
        valid = {**invalid, "result": "FIXED"}
        self.assertTrue(process.apply(valid).accepted)
        before = copy.deepcopy((process.products, process.equipment))
        self.assertFalse(process.apply(valid).accepted)
        self.assertEqual(before, (process.products, process.equipment))
        events = prefix + [invalid, valid, valid, leak("c", "PASS")]
        run = run_metrics(build_analysis(events, self.recipe.models, self.book), {"LEAK-1"}, {"b"})
        self.assertEqual((run.held, run.normal_held), (2, 1))
        self.assertEqual((run.true_stops, run.false_stops, run.detected), (1, 0, 1))
        print("P06: lowercase and duplicate restarts rejected without mutation; held remains 2/1", flush=True)

    def test_p07_multiple_faults_rejected_in_both_modes_even_at_zero_probability(self):
        for enabled in (False, True):
            with self.subTest(enabled=enabled), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                path, _ = self.config_file(directory, restart=enabled, error_rate=0,
                                           faulty_equipment={"LEAK-2": 0, "LEAK-3": 0})
                result = cli(directory, "src.evaluate", "--config", path, "--seeds", "0-0",
                             "--rules", "3:2", "--products", "2", "--out", "multiple")
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("여러 대", result.stderr.decode("utf-8"))
                self.assertFalse((directory / "reports").exists())
        print("P07: two declared faults at p=0 rejected in both modes, exit 2/no reports", flush=True)

    def test_p08_empty_fault_set_and_single_fault_undetected(self):
        for faults in ({}, {"LEAK-2": 0}):
            with self.subTest(faults=faults), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                path, _ = self.config_file(directory, faulty_equipment=faults, error_rate=0,
                                           normal_fail_probability=0, defective_product_probability=0)
                runs, metrics, _ = evaluate(path, range(2), [(3, 2)], 3)
                actual = metrics[3, 2]
                self.assertEqual(actual["detection_rate"], Fraction(0) if faults else None)
                self.assertIsNone(actual["mean_delay"])
                self.assertEqual(actual["mean_held"], 0)
                self.assertEqual([item.held for item in runs[3, 2]], [0, 0])
                result = rule_rows(metrics, {}, False)
                self.assertEqual(result[-1]["value"], "기준 충족 규칙 없음")
        print("P08: zero faults -> blank rate; one undetected fault -> 0; held=0/no selection", flush=True)

    def test_p09_delay_unit_matches_approved_normal_rows_after_error_insertion(self):
        _, normal, rows, _ = build_rows(42, 500, self.config, self.recipe.models, self.book)
        gaps = []
        for label, events in (("normal", normal), ("final", rows)):
            analysis = build_analysis(events, self.recipe.models, self.book)
            self.assertTrue(analysis.restarts)
            current = []
            for resumed in analysis.restarts:
                stop = analysis.stop_at(resumed.equipment, resumed.row_index)
                current.append(resumed.row_index - stop.row_index - 1)
            gaps.append(current)
        self.assertEqual(gaps[0], [30, 30, 30])
        self.assertEqual(gaps[1], [31, 32, 32])
        print("P09: approved normal-row gaps=%r; final-CSV gaps=%r" % tuple(gaps), flush=True)

    def test_p10_existing_samples_and_seed42_reports_are_byte_identical(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            for stem, options in (
                ("sample_events", ()),
                ("sample_events_v2", ("--recipe", ROOT / "recipes/lamp_models.json")),
                ("sample_events_retest", ("--recipe", RECIPE)),
                ("sample_events_equipment", ("--recipe", RECIPE, "--equipment", ROOT / "recipes/equipment.json")),
            ):
                result = cli(directory, "src.main", ROOT / "data" / (stem + ".csv"), *options)
                self.assertEqual(result.returncode, 0, result.stderr)
            generated = directory / "gen_seed42.csv"
            generate(42, 500, generated, PLAIN_CONFIG)
            for suffix in ("", ".meta.json"):
                self.assertEqual(Path(str(generated) + suffix).read_bytes(),
                                 (ROOT / "data/generated" / ("gen_seed42.csv" + suffix)).read_bytes())
            result = cli(directory, "src.main", generated, "--recipe", RECIPE,
                         "--equipment", ROOT / "recipes/equipment_generated.json", "--summary",
                         "--trace", "GEN_0005", "--trace", "GEN_0030")
            self.assertEqual(result.returncode, 0, result.stderr)
            reports = list((directory / "reports").iterdir())
            self.assertEqual(len(reports), 20)
            for report in reports:
                self.assertEqual(report.read_bytes(), (ROOT / "reports" / report.name).read_bytes(), report.name)
        print("P10: 20 reports plus seed42 CSV/meta byte-identical to checkout", flush=True)

    def test_p11_evaluation_reports_preserve_old_cells_and_reaggregate_new_held(self):
        total = 0
        for stem in ("eval_dev", "eval_holdout", "eval_baseline"):
            current = {}
            for suffix in ("runs", "rules"):
                relative = "reports/" + stem + "_" + suffix + ".csv"
                original = subprocess.check_output(["git", "show", BASE + ":" + relative], cwd=ROOT)
                old = list(csv.DictReader(io.StringIO(original.decode("utf-8-sig"))))
                new = list(csv.DictReader(io.StringIO((ROOT / relative).read_text(encoding="utf-8-sig"))))
                self.assertEqual(len(new), len(old))
                for old_row, new_row in zip(old, new):
                    self.assertEqual({key: new_row[key] for key in old_row}, old_row)
                current[suffix] = new
            by_rule = {}
            for run in current["runs"]:
                by_rule.setdefault(run["rule"], []).append(run)
                self.assertLessEqual(int(run["normal_held"]), int(run["held"]))
                self.assertLessEqual(int(run["held"]), int(run["unfinished"]))
            for rule in current["rules"]:
                if rule["section"] != "rule":
                    continue
                entries = by_rule[rule["rule"]]
                from decimal import Decimal, ROUND_HALF_UP
                mean = Decimal(sum(int(item["held"]) for item in entries)) / len(entries)
                self.assertEqual(rule["mean_held"], format(mean.quantize(Decimal(".01"), rounding=ROUND_HALF_UP), ".2f"))
            total += len(current["runs"])
        print("P11: 800 stored runs: all old cells preserved; held bounds/means agree", flush=True)


if __name__ == "__main__":
    unittest.main()

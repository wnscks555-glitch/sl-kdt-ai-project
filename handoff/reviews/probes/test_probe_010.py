"""Review 010 probes. All generated output stays in TemporaryDirectory.

Normal invocation: py -m unittest handoff/reviews/probes/test_probe_010.py
bootstrap_unittest uses the existing runtime if the Windows launcher cannot find it.
It does not install Python, change the registry, or change existing tests.
"""

import copy
import csv
from dataclasses import replace
from fractions import Fraction
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
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True

from src.equipment import load_equipment
from src.evaluate import aggregate, run_metrics, select_rule
from src.generate import Generator, build_rows, generate, load_setup
from src.recipe import load_recipe
from src.recipe_rules import EQUIPMENT_INPUT_COLUMNS, RecipeProcess
from src.summary import build_analysis, build_summary
from src.trace import build_trace

RECIPE = ROOT / "recipes/lamp_models_retest.json"
CONFIG = ROOT / "recipes/generator_restart.json"
EQUIPMENT = ROOT / "recipes/equipment_restart.json"
BASE = "400081f9735cc584ac5299e72c75a7515fca57d9"


def bootstrap_unittest(arguments):
    """Run the requested py command using a temporary alias of this interpreter."""
    with tempfile.TemporaryDirectory(prefix="review010-runtime-") as directory:
        target = Path(directory)
        shutil.copy2(sys.executable, target / "py.exe")
        dll = "python%d%d.dll" % sys.version_info[:2]
        shutil.copy2(Path(sys.base_prefix) / dll, target / dll)
        env = {**os.environ, "PYTHONHOME": sys.base_prefix,
               "PATH": str(target) + os.pathsep + sys.base_prefix + os.pathsep + os.environ.get("PATH", ""),
               "PYTHONPATH": str(ROOT), "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
        print("Temporary py.exe alias -> " + sys.executable, flush=True)
        print("Command: py " + " ".join(arguments), flush=True)
        result = subprocess.run([str(target / "py.exe"), *arguments], cwd=ROOT, env=env)
        return result.returncode


def row(seq, pid, event, inspection="", result="", model="", equipment=""):
    return dict(zip(EQUIPMENT_INPUT_COLUMNS, (str(seq), pid, event, inspection, result, model, equipment)))


def prepared(names):
    result = []
    for pid in names:
        for event, model in (("REGISTER", "B"), ("P1", ""), ("P2", "")):
            result.append(row(len(result) + 1, pid, event, model=model))
    return result


def leak(seq, pid, result="FAIL", equipment="LEAK-1"):
    return row(seq, pid, "INSPECT", "LEAK", result, equipment=equipment)


def restart(seq, equipment="LEAK-1", result="NO_FAULT", **kw):
    return row(seq, kw.pop("pid", ""), "EQUIP_RESTART", result=result, equipment=equipment, **kw)


def cli(directory, module, *arguments, timeout=20):
    return subprocess.run([sys.executable, "-m", module, *map(str, arguments)], cwd=directory,
                          capture_output=True, timeout=timeout,
                          env={**os.environ, "PYTHONPATH": str(ROOT), "PYTHONIOENCODING": "utf-8",
                               "PYTHONDONTWRITEBYTECODE": "1"})


class Probe010(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.models = load_recipe(RECIPE).models
        cls.book = load_equipment(EQUIPMENT, cls.models)

    def test_p01_overlapping_format_errors_then_valid_restart(self):
        process = RecipeProcess(self.models, self.book)
        for item in prepared("abc") + [leak(1, "a"), leak(1, "b")]:
            self.assertTrue(process.apply(item).accepted)
        bad = restart(0, equipment="MISSING", result="fixed", pid="a", inspection="LEAK")
        for expected, key, value in (
            ("seq는 양의 정수여야 함", "seq", "1"),
            ("EQUIP_RESTART의 product_id는 빈칸이어야 함", "product_id", ""),
            ("EQUIP_RESTART의 inspection과 model은 빈칸이어야 함", "inspection", ""),
            ("잘못된 재가동 결과 (FIXED 또는 NO_FAULT 필요)", "result", "FIXED"),
            ("등록되지 않은 설비", "equipment", "LEAK-1"),
        ):
            before = copy.deepcopy((process.products, process.equipment))
            decision = process.apply(bad)
            self.assertFalse(decision.accepted)
            self.assertEqual(decision.reason, expected)
            self.assertEqual((process.products, process.equipment), before)
            bad[key] = value
        self.assertTrue(process.apply(bad).accepted)
        before = copy.deepcopy((process.products, process.equipment))
        self.assertEqual(process.apply(bad).reason, "가동 중인 설비 재가동")
        self.assertEqual((process.products, process.equipment), before)
        self.assertTrue(process.apply(leak(1, "c", "PASS")).accepted)

    def test_p02_duplicate_nonmonotonic_seq_links_physical_stop(self):
        events = prepared("abcdef") + [leak(90, "a"), leak(2, "b"), leak(2, "c", "PASS"),
                  restart(1), leak(90, "d"), leak(2, "e"), leak(1, "f", "PASS"), restart(1)]
        analysis = build_analysis(events, self.models, self.book)
        self.assertEqual(len(analysis.stop_history), 2)
        self.assertIs(analysis.stops["LEAK-1"], analysis.stop_history[0])
        for pid, causes in (("c", "a;b"), ("f", "d;e")):
            rejection = [x for x in build_trace(analysis, pid) if x["decision"] == "거절"]
            self.assertEqual([x["cause_product_ids"] for x in rejection], [causes])
        stops = [x for x in build_summary(analysis) if x["section"] == "equipment_stops" and "#" in x["key"]]
        self.assertEqual([x["rejected_count"] for x in stops], [1, 1])
        self.assertEqual([x["state"] for x in stops], ["재가동", "재가동"])

    def test_p03_restart_disabled_case_and_blank_values(self):
        for enabled in (False, True):
            process = RecipeProcess(self.models, replace(self.book, restart_enabled=enabled))
            for event, result, equipment in (("equip_restart", "FIXED", "LEAK-1"),
                                             ("EQUIP_RESTART", "fixed", "LEAK-1"),
                                             ("EQUIP_RESTART", "FIXED", "leak-1"),
                                             ("EQUIP_RESTART", "", "")):
                before = copy.deepcopy((process.products, process.equipment))
                decision = process.apply(row(1, "", event, result=result, equipment=equipment))
                self.assertFalse(decision.accepted)
                self.assertEqual((process.products, process.equipment), before)
                if not enabled or event != "EQUIP_RESTART":
                    self.assertEqual(decision.reason, "product_id가 비어 있음")

    def test_p04_zero_delay_and_single_fail_threshold(self):
        config, _, recipe, book = load_setup(CONFIG)
        config = copy.deepcopy(config)
        config.update(normal_fail_probability=0, defective_product_probability=0, error_rate=0)
        config["faulty_equipment"] = {"LEAK-2": 1}
        config["restart"] = {"delay_rows": 0}
        book = replace(book, window=1, fails=1)
        generator = Generator(42, config, recipe.models, book)
        events = generator.normal_events(10)
        analysis = build_analysis(events, recipe.models, book)
        self.assertTrue(all(d.accepted for d in analysis.decisions))
        self.assertEqual(len(analysis.stop_history), 1)
        self.assertEqual(len(analysis.restarts), 1)
        self.assertEqual(analysis.restarts[0].row_index, analysis.stop_history[0].row_index + 1)
        self.assertEqual(analysis.restarts[0].result, "FIXED")
        self.assertFalse(generator.pending_restarts)

    def test_p05_missing_inspection_equipment_must_terminate(self):
        # Equipment loader accepts a subset. Waiting cannot make a missing machine appear.
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            config = json.loads(CONFIG.read_text(encoding="utf-8-sig"))
            config.update(recipe=str(RECIPE), equipment=str(directory / "equipment.json"), error_rate=0,
                          normal_fail_probability=0, defective_product_probability=0,
                          faulty_equipment={})
            equipment = json.loads(EQUIPMENT.read_text(encoding="utf-8-sig"))
            equipment["equipment"] = {"LEAK-1": "LEAK"}
            (directory / "equipment.json").write_text(json.dumps(equipment), encoding="utf-8")
            (directory / "config.json").write_text(json.dumps(config), encoding="utf-8")
            self.assertEqual(load_equipment(directory / "equipment.json", self.models).equipment, {"LEAK-1": "LEAK"})
            try:
                result = cli(directory, "src.evaluate", "--config", directory / "config.json",
                             "--products", "2", "--seeds", "0-0", "--rules", "3:2", "--out", "missing", timeout=4)
            except subprocess.TimeoutExpired:
                self.fail("Valid equipment subset leaves generator waiting forever without any pending restart (4 s timeout)")
            self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8", "replace"))
            self.assertFalse((directory / "reports").exists())

    def test_p06_multiple_faults_detection_rate_is_per_run(self):
        events = prepared("ab") + [leak(20, "a", equipment="LEAK-2"), leak(21, "b", equipment="LEAK-2")]
        metrics = run_metrics(build_analysis(events, self.models, self.book), {"LEAK-2", "LEAK-3"}, set())
        actual = aggregate([metrics], 2)["detection_rate"]
        self.assertEqual(actual, 1, "One of one runs detected faulty equipment; spec denominator is runs, not equipment-runs")

    def test_p07_legacy_step_named_restart_preserves_generation(self):
        source = subprocess.check_output(["git", "show", BASE + ":src/generate.py"], cwd=ROOT).decode("utf-8")
        legacy = types.ModuleType("src._probe010_baseline_generate")
        legacy.__package__ = "src"
        legacy.__file__ = str(ROOT / "src/generate.py")
        exec(compile(source, legacy.__file__, "exec"), legacy.__dict__)
        config, _, recipe, book = load_setup(ROOT / "recipes/generator.json")
        models = {name: replace(model, steps=("EQUIP_RESTART",) + model.steps) for name, model in recipe.models.items()}
        with tempfile.TemporaryDirectory() as directory:
            data = json.loads(RECIPE.read_text(encoding="utf-8-sig"))
            for model in data.values():
                model["steps"].insert(0, "EQUIP_RESTART")
            path = Path(directory) / "recipe.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            self.assertEqual(load_recipe(path).models, models)
        old = legacy.Generator(42, config, models, book)
        new = Generator(42, config, models, book)
        old_normal, new_normal = old.normal_events(60), new.normal_events(60)
        self.assertEqual(new_normal, old_normal)
        old_rows, old_counts = old.inject_errors(old_normal)
        new_rows, new_counts = new.inject_errors(new_normal)
        self.assertEqual(new_counts, old_counts)
        mismatch = next((i for i, pair in enumerate(zip(old_rows, new_rows), 1) if pair[0] != pair[1]), None)
        self.assertIsNone(mismatch, "Restart disabled, valid legacy process ID changes generated CSV at row %s" % mismatch)

    def test_p08_selection_uses_unrounded_boundary_values(self):
        def m(detection, delay, false):
            return dict(detection_rate=Fraction(detection), mean_delay=Fraction(delay),
                        mean_false_stops=Fraction(false), unfinished_median=Fraction(20))
        self.assertEqual(select_rule({(3, 2): m("0.94999", "9", "0"),
                                      (5, 2): m("0.95", "10", "1")}), (5, 2))
        self.assertEqual(select_rule({(3, 2): m("1", "10.00001", "0"),
                                      (5, 2): m("1", "10", "1")}), (5, 2))
        self.assertEqual(select_rule({(3, 2): m("1", "9", "1.004"),
                                      (5, 2): m("1", "9", "1.003")}), (5, 2))

    def test_p09_existing_samples_seed42_and_reports_identical(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            for stem, options in (
                ("sample_events", ()),
                ("sample_events_v2", ("--recipe", ROOT / "recipes/lamp_models.json")),
                ("sample_events_retest", ("--recipe", RECIPE)),
                ("sample_events_equipment", ("--recipe", RECIPE, "--equipment", ROOT / "recipes/equipment.json")),
            ):
                result = cli(directory, "src.main", ROOT / "data" / (stem + ".csv"), *options)
                self.assertEqual(result.returncode, 0, result.stderr)
            generated = directory / "gen_seed42.csv"
            generate(42, 500, generated, ROOT / "recipes/generator.json")
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
                with self.subTest(report=report.name):
                    self.assertEqual(report.read_bytes(), (ROOT / "reports" / report.name).read_bytes())
            print("P09: 20 reports + seed42 CSV/meta byte-identical", flush=True)

    def test_p10_restart_csv_meta_and_reports_reproducible(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            for seed, products in ((42, 500), (7, 200)):
                snapshots = []
                for iteration in (1, 2):
                    work = directory / (str(seed) + "-" + str(iteration))
                    work.mkdir()
                    output = work / "events.csv"
                    generate(seed, products, output, CONFIG)
                    result = cli(work, "src.main", output, "--recipe", RECIPE, "--equipment", EQUIPMENT,
                                 "--summary", "--trace", "GEN_0001")
                    self.assertEqual(result.returncode, 0, result.stderr)
                    snapshots.append({p.relative_to(work).as_posix(): p.read_bytes() for p in work.rglob("*") if p.is_file()})
                self.assertEqual(snapshots[0], snapshots[1])
                print("P10: seed=%d products=%d CSV/meta/6 reports byte-identical" % (seed, products), flush=True)

    def test_p11_t63_total_held_average_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            result = cli(directory, "src.evaluate", "--config", ROOT / "recipes/generator.json",
                         "--seeds", "0-29", "--rules", "3:2", "--out", "baseline", timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            text = result.stdout.decode("utf-8")
            self.assertIn("8.50", text)
            self.assertIn("13.73", text, "T63 requires both total held mean 13.73 and normal held mean 8.50")

    def test_p12_delay_rows_after_error_insertion(self):
        config, _, recipe, book = load_setup(CONFIG)
        generator = Generator(42, config, recipe.models, book)
        normal = generator.normal_events(500)
        rows, _ = generator.inject_errors(normal)
        analysis = build_analysis(rows, recipe.models, book)
        gaps = []
        for resumed in analysis.restarts:
            stop = analysis.stop_at(resumed.equipment, resumed.row_index)
            intervening = resumed.row_index - stop.row_index - 1
            gaps.append((resumed.equipment, stop.row_index, resumed.row_index, intervening))
        self.assertTrue(gaps)
        print("P12 final CSV stop/restart/intervening rows:", gaps, flush=True)
        # The published definition says rows, with no exclusion for rejected injected rows.
        self.assertTrue(all(gap[3] <= config["restart"]["delay_rows"] for gap in gaps),
                        "A due restart must precede the next product row; error insertion delays it: %r" % gaps)

    def test_p13_full_sized_restart_rejections_preserve_all_state(self):
        config, _, recipe, book = load_setup(CONFIG)
        for seed, products in ((42, 500), (7, 200)):
            _, _, rows, counts = build_rows(seed, products, config, recipe.models, book)
            expected = build_analysis(rows, recipe.models, book).decisions
            process = RecipeProcess(recipe.models, book)
            rejected = 0
            for event, decision in zip(rows, expected):
                before = copy.deepcopy((process.products, process.equipment)) if not decision.accepted else None
                actual = process.apply(event)
                self.assertEqual(actual, decision)
                if not actual.accepted:
                    self.assertEqual((process.products, process.equipment), before)
                    rejected += 1
            self.assertGreater(rejected, 0)
            self.assertEqual(rejected, sum(counts.values()))
            print("P13: seed=%d products=%d all %d rows replayed, %d rejected full states unchanged" %
                  (seed, products, len(rows), rejected), flush=True)


if __name__ == "__main__":
    unittest.main()

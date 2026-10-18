import hashlib
import copy
from collections import Counter
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

from src.generate import GENERATOR_VERSION, generate
from src.equipment import load_equipment
from src.main import read_events
from src.recipe import load_recipe
from src.recipe_rules import EQUIPMENT_INPUT_COLUMNS, RecipeProcess
from src.summary import build_analysis, build_summary


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "recipes/generator.json"


class GeneratorTests(unittest.TestCase):
    def test_t42_same_seed_csv_meta_and_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            a, b = Path(directory) / "a.csv", Path(directory) / "b.csv"
            first = generate(42, 500, a, CONFIG)
            generate(42, 500, b, CONFIG)
            self.assertEqual(a.read_bytes(), b.read_bytes())
            self.assertEqual(Path(str(a) + ".meta.json").read_bytes(),
                             Path(str(b) + ".meta.json").read_bytes())
            self.assertEqual((first["seed"], first["products"], first["generator_version"]),
                             (42, 500, GENERATOR_VERSION))
            for key, path in (("config", CONFIG), ("recipe", ROOT / "recipes/lamp_models_retest.json"),
                              ("equipment", ROOT / "recipes/equipment_generated.json")):
                self.assertEqual(first["sha256"][key], hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(first["rows"], first["normal_rows"] + sum(first["injected_errors"].values()))
            counts = list(first["injected_errors"].values())
            self.assertLessEqual(max(counts) - min(counts), 1)
            self.assertEqual(sum(counts), int(first["normal_rows"] * 0.03))

    def test_t43_different_seed_changes_csv(self):
        with tempfile.TemporaryDirectory() as directory:
            a, b = Path(directory) / "a.csv", Path(directory) / "b.csv"
            generate(42, 500, a, CONFIG)
            generate(43, 500, b, CONFIG)
            self.assertNotEqual(a.read_bytes(), b.read_bytes())


class GeneratedInvariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        cls.models = load_recipe(ROOT / "recipes/lamp_models_retest.json").models
        cls.equipment_book = load_equipment(ROOT / "recipes/equipment_generated.json", cls.models)
        cls.cases = {}
        for seed, products in ((42, 500), (7, 200)):
            folder = Path(cls.directory.name) / str(seed)
            folder.mkdir()
            path = folder / "events.csv"
            start = time.perf_counter()
            meta = generate(seed, products, path, CONFIG)
            generated = time.perf_counter() - start
            events = read_events(path, EQUIPMENT_INPUT_COLUMNS)
            start = time.perf_counter()
            analysis = build_analysis(events, cls.models, cls.equipment_book)
            judged = time.perf_counter() - start
            cls.cases[seed] = (path, meta, analysis)
            print(f"T44 seed={seed} products={products} generation_seconds={generated:.6f} "
                  f"judgment_analysis_seconds={judged:.6f}")

    def test_t44_csv_meta_and_six_reports_repeat_for_both_seeds(self):
        for seed, (path, meta, _) in self.cases.items():
            with self.subTest(seed=seed), tempfile.TemporaryDirectory() as directory:
                second = Path(directory) / "events.csv"
                generate(seed, meta["products"], second, CONFIG)
                self.assertEqual(path.read_bytes(), second.read_bytes())
                self.assertEqual(Path(str(path) + ".meta.json").read_bytes(),
                                 Path(str(second) + ".meta.json").read_bytes())
                results = []
                for source in (path, second):
                    run = subprocess.run(
                        ["py", "-m", "src.main", str(source), "--recipe",
                         str(ROOT / "recipes/lamp_models_retest.json"), "--equipment",
                         str(ROOT / "recipes/equipment_generated.json"), "--summary", "--trace", "GEN_0001"],
                        cwd=source.parent, capture_output=True,
                        env={**os.environ, "PYTHONPATH": str(ROOT), "PYTHONIOENCODING": "utf-8"})
                    self.assertEqual(run.returncode, 0, run.stderr.decode("utf-8"))
                    results.append({item.name: item.read_bytes() for item in (source.parent / "reports").iterdir()})
                self.assertEqual(len(results[0]), 6)
                self.assertEqual(results[0], results[1])

    def test_t44_completed_products_have_every_step_and_current_pass(self):
        for seed, (_, _, analysis) in self.cases.items():
            with self.subTest(seed=seed):
                for product in analysis.process.products.values():
                    if product.status == "레시피 모의 흐름 완료":
                        self.assertEqual(product.completed_steps, len(product.recipe.steps))
                        self.assertTrue(all(product.inspections.get(item.id) == "PASS"
                                            for item in product.recipe.inspections))

    def test_t44_no_accepted_events_after_discard_or_equipment_stop(self):
        for seed, (_, _, analysis) in self.cases.items():
            discarded = {}
            for index, (event, decision) in enumerate(zip(analysis.events, analysis.decisions), 1):
                with self.subTest(seed=seed, row=index):
                    if decision.product_id in discarded:
                        self.assertFalse(decision.accepted)
                    stop = analysis.stops.get(event.get("equipment"))
                    if stop is not None and index > stop.row_index:
                        self.assertFalse(decision.accepted)
                    if decision.accepted and decision.state == "폐기":
                        discarded[decision.product_id] = index

    def test_t44_rejected_rows_equal_rules_and_summary_partition(self):
        for seed, (_, meta, analysis) in self.cases.items():
            with self.subTest(seed=seed):
                rows = build_summary(analysis, meta)
                rejected = sum(not decision.accepted for decision in analysis.decisions)
                rules = Counter(decision.rule_id for decision in analysis.decisions if not decision.accepted)
                self.assertEqual(rejected, sum(rules.values()))
                totals = {row["key"]: row["value"] for row in rows if row["section"] == "rejection_totals"}
                errors = sum(row["count"] for row in rows if row["section"] == "input_error_pareto")
                self.assertEqual(rejected, errors + totals["equipment_stopped"] + totals["other_rejections"])
                self.assertEqual(rejected, totals["rule_rejections"])
                self.assertEqual(rules, {row["key"]: row["count"] for row in rows if row["section"] == "rule_rejections"})
                self.assertEqual({row["key"]: row["count"] for row in rows if row["section"] == "input_error_pareto"},
                                 meta["injected_errors"])

    def test_t44_rejections_preserve_all_products_and_equipment_for_both_seeds(self):
        for seed, (_, _, analysis) in self.cases.items():
            start = time.perf_counter()
            process = RecipeProcess(self.models, self.equipment_book)
            rejected = 0
            for event in analysis.events:
                before = copy.deepcopy(process)
                decision = process.apply(event)
                if not decision.accepted:
                    rejected += 1
                    self.assertEqual(process.products, before.products)
                    self.assertEqual(process.equipment, before.equipment)
            self.assertGreater(rejected, 0)
            print(f"T44 seed={seed} all_rows_deepcopy_invariant_seconds={time.perf_counter() - start:.6f}")

    def test_t44_seed42_nonempty_completion_hold_discard_stop_and_five_errors(self):
        _, meta, analysis = self.cases[42]
        states = Counter(product.status for product in analysis.process.products.values())
        requirements = {
            "completed": states["레시피 모의 흐름 완료"], "held": states["보류"], "discarded": states["폐기"],
            "stopped_equipment": len(analysis.stops), **meta["injected_errors"],
        }
        # 명세의 빈 검증 조건은 확률 결과가 0이어도 약화하거나 skip하지 않는다.
        for requirement, count in requirements.items():
            with self.subTest(requirement=requirement):
                self.assertGreater(count, 0, "명세 이견: seed42 빈 검증 조건 미충족: " + requirement)

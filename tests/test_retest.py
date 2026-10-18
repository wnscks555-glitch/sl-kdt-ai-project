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


if __name__ == "__main__":
    unittest.main()

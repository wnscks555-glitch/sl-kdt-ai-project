import hashlib
from pathlib import Path
import unittest

from src.recipe import RecipeError, load_recipe


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
DEFAULT_RECIPE = ROOT / "recipes" / "lamp_models.json"


class RecipeLoadingTests(unittest.TestCase):
    def test_t18_valid_models_and_original_content_digest(self):
        book = load_recipe(DEFAULT_RECIPE)
        self.assertEqual(book.models["A"].steps, ("P1", "P2", "P3", "P4", "P5"))
        self.assertEqual(
            [(item.id, item.after) for item in book.models["B"].inspections],
            [("LEAK", "P2"), ("LIGHT", "P4")],
        )
        self.assertEqual(book.sha256, hashlib.sha256(DEFAULT_RECIPE.read_bytes()).hexdigest())

    def test_t18_seven_expected_invalid_recipes_report_locations(self):
        cases = {
            "empty_steps.json": ("A.steps",),
            "duplicate_steps.json": ("A.steps[2]",),
            "duplicate_inspections.json": ("A.inspections[1].id",),
            "string_steps.json": ("A.steps",),
            "unknown_key.json": ("A.next",),
            "unknown_after.json": ("A.inspections[0].after",),
            "multiple_errors.json": ("A.steps", "A.next"),
        }
        for name, locations in cases.items():
            with self.subTest(name=name), self.assertRaises(RecipeError) as caught:
                load_recipe(FIXTURES / name)
            for location in locations:
                self.assertTrue(any(error.startswith(location + ":") for error in caught.exception.errors))

    def test_t18_structure_and_id_errors_are_all_reported(self):
        with self.assertRaises(RecipeError) as caught:
            load_recipe(FIXTURES / "invalid_structure.json")
        for location in (
            "bad", "bad.extra", "bad.steps[0]", "bad.steps[1]", "bad.steps[2]",
            "bad.inspections[0].id", "bad.inspections[0].after",
            "bad.inspections[0].next", "bad.inspections[1]", "B", "C.inspections",
            "D.steps", "D.inspections", "E.steps", "E.inspections", "F.inspections",
        ):
            with self.subTest(location=location):
                self.assertTrue(any(error.startswith(location + ":") for error in caught.exception.errors))

    def test_t18_invalid_json_root_and_missing_file(self):
        for name in ("invalid_json.json", "array_root.json", "empty_models.json", "missing.json"):
            with self.subTest(name=name), self.assertRaises(RecipeError) as caught:
                load_recipe(FIXTURES / name)
            self.assertTrue(all(error.startswith("$:") for error in caught.exception.errors))


if __name__ == "__main__":
    unittest.main()

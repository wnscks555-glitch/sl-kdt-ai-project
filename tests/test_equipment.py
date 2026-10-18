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

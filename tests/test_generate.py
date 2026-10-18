import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from src.generate import GENERATOR_VERSION, generate


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

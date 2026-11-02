"""Review 028: targeted probes; all generated output stays in TemporaryDirectory."""
import copy
import csv
from dataclasses import replace
from fractions import Fraction
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
import unittest

from src import line, replay, secom, sizing

ROOT = Path(__file__).resolve().parents[3]
BASE = "0a0be8842d289bede5286359b3b5d090783f2e36"
SIZING_OUTPUTS = ("sizing_lamp_curve.csv", "sizing_lamp_spec.csv", "sizing_lamp_sheet.md")
SECOM_OUTPUTS = ("check_features.csv", "check_summary.csv", "check.md")


def cli(folder, module, *args):
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1",
               PYTHONIOENCODING="utf-8", PYTHONHASHSEED="23")
    return subprocess.run([sys.executable, "-m", module, *map(str, args)], cwd=folder,
                          env=env, capture_output=True, text=True, encoding="utf-8")


def snapshot(folder):
    return {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in Path(folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts}


def write_rows(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def secom_case(folder, labels=None):
    folder = Path(folder)
    (folder / "recipes").mkdir(exist_ok=True)
    (folder / "reports").mkdir(exist_ok=True)
    values = [str(10 + (i % 7) * .1) for i in range(80)]
    labels = labels or [-1] * 80
    raw = ("\n".join(values) + "\n").encode()
    lab = ("\n".join('%d "01/07/2008 %02d:%02d:00"' % (label, i // 60, i % 60)
                     for i, label in enumerate(labels)) + "\n").encode()
    (folder / "recipes" / "data.txt").write_bytes(raw)
    (folder / "recipes" / "labels.txt").write_bytes(lab)
    config = json.loads((ROOT / "recipes/secom_check.json").read_text(encoding="utf-8"))
    config.update(data="data.txt", labels="labels.txt", data_sha256=hashlib.sha256(raw).hexdigest(),
                  labels_sha256=hashlib.sha256(lab).hexdigest(), anomaly=str(ROOT / "recipes/anomaly_lamp.json"))
    path = folder / "recipes/check.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path, config


class Probe028(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protected = {name: snapshot(ROOT / name) for name in ("src", "tests", "recipes", "reports", "data")}
        cls.work = tempfile.TemporaryDirectory()
        cls.sample = Path(cls.work.name)
        shutil.copytree(ROOT / "recipes", cls.sample / "recipes")
        result = cli(cls.sample, "src.line", "recipes/line_lamp.json", "--seeds", "0-1",
                     "--holdout-seeds", "1000-1001", "--products", "200")
        if result.returncode:
            raise AssertionError(result.stderr)
        shutil.copyfile(ROOT / "reports/msa_lamp_guard.csv", cls.sample / "reports/msa_lamp_guard.csv")
        result = cli(cls.sample, "src.sizing", "recipes/sizing_lamp.json")
        if result.returncode:
            raise AssertionError(result.stderr)

    @classmethod
    def tearDownClass(cls):
        actual = {name: snapshot(ROOT / name) for name in cls.protected}
        if actual != cls.protected:
            raise AssertionError("Repository protected content changed")
        print("PRESERVATION repository protected files=%d unchanged" % sum(map(len, actual.values())))
        cls.work.cleanup()

    def copy_sample(self, folder):
        shutil.copytree(self.sample / "recipes", Path(folder) / "recipes")
        shutil.copytree(self.sample / "reports", Path(folder) / "reports")

    def test_p01_sizing_malformed_then_valid(self):
        with tempfile.TemporaryDirectory() as folder:
            self.copy_sample(folder)
            path = Path(folder) / "recipes/sizing_lamp.json"
            original = path.read_bytes()
            before = snapshot(Path(folder) / "reports")
            for raw in (b'{"line":', b'{"line":"a",}', b'', b'\xff'):
                with self.subTest(raw=raw):
                    path.write_bytes(raw)
                    result = cli(folder, "src.sizing", "recipes/sizing_lamp.json")
                    print("P01 invalid=%r exit=%d" % (raw, result.returncode))
                    self.assertEqual(result.returncode, 3, result.stderr)
                    self.assertEqual(before, snapshot(Path(folder) / "reports"))
            path.write_bytes(original)
            result = cli(folder, "src.sizing", "recipes/sizing_lamp.json")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(before, snapshot(Path(folder) / "reports"))
            print("P01 restored valid input: exit=0, all reports identical")

    def test_p02_gauge_invalid_counts_and_inclusive_boundaries(self):
        rows = sizing.read_rows(ROOT / "reports/msa_lamp_guard.csv")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "gauges.csv"
            for field, denominator in (("false_rejects", "true_good"), ("false_accepts", "true_defects")):
                for value in (-1, int(next(r for r in rows if r["section"] == "holdout")[denominator]) + 1):
                    changed = copy.deepcopy(rows)
                    next(r for r in changed if r["section"] == "holdout")[field] = str(value)
                    write_rows(path, changed)
                    with self.assertRaises(ValueError):
                        sizing.read_gauges(path)
                for value in (0, 1):
                    changed = copy.deepcopy(rows)
                    row = next(r for r in changed if r["section"] == "holdout")
                    row[field] = str(int(row[denominator]) * value)
                    write_rows(path, changed)
                    item = sizing.read_gauges(path)[0]
                    self.assertEqual(item[2 if field == "false_rejects" else 3], value)
            print("P02 four impossible counts refused; four inclusive boundary ratios valid")

    def test_p03_sizing_direct_alias_and_hardlink_inputs(self):
        for key, source, name in (("guard_report", "msa_lamp_guard.csv", "sizing_lamp_spec.csv"),
                                  ("line_report", "line_lamp_compare.csv", "sizing_lamp_curve.csv"),
                                  ("balance_report", "line_lamp_balance.csv", "sizing_lamp_sheet.md")):
            for hardlink in (False, True):
                with self.subTest(key=key, hardlink=hardlink), tempfile.TemporaryDirectory() as folder:
                    root = Path(folder)
                    self.copy_sample(root)
                    config = root / "recipes/sizing_lamp.json"
                    settings = json.loads(config.read_text(encoding="utf-8"))
                    output = root / "reports" / name
                    if hardlink:
                        # A new directory entry, no deletion or change of the existing input.
                        alias = root / "reports" / ("alias_" + source)
                        os.link(output, alias)
                        alias.write_bytes((root / "reports" / source).read_bytes())
                        settings[key] = "../reports/" + alias.name
                    else:
                        output.write_bytes((root / "reports" / source).read_bytes())
                        settings[key] = "../reports/./" + name
                    config.write_text(json.dumps(settings), encoding="utf-8")
                    before = snapshot(root / "reports")
                    result = cli(root, "src.sizing", config)
                    print("P03 %s hardlink=%s exit=%d" % (key, hardlink, result.returncode))
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertEqual(before, snapshot(root / "reports"))

    def test_p04_sizing_indirect_generator_collision(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.copy_sample(root)
            line_path = root / "recipes/line_lamp.json"
            raw = json.loads(line_path.read_text(encoding="utf-8"))
            generator = json.loads((root / "recipes/generator_measured.json").read_text(encoding="utf-8"))
            generator.update(recipe="../recipes/lamp_models_measured.json", equipment="../recipes/equipment_measured.json")
            victim = root / "reports/sizing_lamp_sheet.md"
            victim.write_text(json.dumps(generator), encoding="utf-8")
            raw["generator"] = "../reports/sizing_lamp_sheet.md"
            line_path.write_text(json.dumps(raw), encoding="utf-8")
            before = victim.read_bytes()
            result = cli(root, "src.sizing", "recipes/sizing_lamp.json")
            print("P04 indirect generator exit=%d preserved=%s" % (result.returncode, victim.read_bytes() == before))
            self.assertEqual(result.returncode, 2, "Indirect input must not be overwritten")
            self.assertEqual(victim.read_bytes(), before)

    def test_p05_t281_detects_tampered_joint_rows(self):
        spec = importlib.util.spec_from_file_location("review028_sizing_tests", ROOT / "tests/test_sizing.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        rows = sizing.read_rows(self.sample / "reports/sizing_lamp_spec.csv")
        for field, bad in (("good_uph", "0.0000"), ("holdout_good_uph", "999999.0000"), ("value", "동시 충족")):
            case = module.RunTests("test_t281_joint_matches_a_direct_run")
            case.root = self.sample
            case.rows = copy.deepcopy(rows)
            next(row for row in case.rows if row["section"] == "joint")[field] = bad
            try:
                with self.assertRaises(AssertionError):
                    case.test_t281_joint_matches_a_direct_run()
            finally:
                case.doCleanups()
                os.chdir(ROOT)
        print("P05 actual revised T281 rejects each of three corrupted joint fields")

    def test_p06_secom_output_hardlink_cannot_destroy_raw_input(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            config, _ = secom_case(root)
            source = root / "recipes/data.txt"
            os.link(source, root / "reports/check_features.csv")
            before = source.read_bytes()
            result = cli(root, "src.secom", config)
            print("P06 data hardlink exit=%d preserved=%s" % (result.returncode, source.read_bytes() == before))
            self.assertEqual(result.returncode, 2, "Same underlying input file must be refused")
            self.assertEqual(source.read_bytes(), before)

    def test_p07_secom_no_eligible_phase(self):
        for labels in ([1] * 80, [1] * 40 + [-1] * 40, [-1] * 40 + [1] * 40):
            with self.subTest(first_good=labels[:40].count(-1), later_good=labels[40:].count(-1)):
                with tempfile.TemporaryDirectory() as folder:
                    config, _ = secom_case(folder, labels)
                    result = cli(folder, "src.secom", config)
                    tail = result.stderr.strip().splitlines()[-1:]
                    print("P07 phase good=%d/%d exit=%d stderr=%s" % (
                        labels[:40].count(-1), labels[40:].count(-1), result.returncode, tail))
                    self.assertNotIn("Traceback", result.stderr, "Valid labels with no eligible phase must be handled")
                    self.assertIn(result.returncode, (0, 2))

    def test_p08_secom_missing_failed_rows_do_not_update_ewma(self):
        with tempfile.TemporaryDirectory() as folder:
            config, _ = secom_case(folder)
            settings = secom.load_settings(config)
            data = "\n".join(["9", "11"] * 20 + ["NaN", "999", "15", "NaN", "9"])
            labels = "\n".join('%d "01/07/2008 00:%02d:00"' % (1 if i == 41 else -1, i)
                               for i in range(45))
            rows = secom.read_rows(data, labels)
            settings = replace(settings, phase1_share=Fraction(8, 9))
            split, features = secom.feature_rows(rows, settings)
            item = features[0]
            self.assertEqual((split, item["n1"], item["n2"], item["selected"]), (40, 40, 2, 1))
            _, expected_i, expected_e = secom.chart_rates([9., 11.] * 20, [15., 9.], settings)
            self.assertEqual((item["_i"], item["_e"]), (expected_i, expected_e))
            print("P08 missing/failed values excluded; phase2 count=2; I and EWMA independent oracle match")

    def test_p09_replay_parallel_skip_stop_and_empty_service(self):
        rng = random.Random(28)
        for case in range(25):
            stations = [line.SimStation("S1", 2, {"A": 3, "B": 0}),
                        line.SimStation("S2", 1, {"A": 7, "B": 2}, "X"),
                        line.SimStation("S3", 2, {"A": 1, "B": 4})]
            routes = [line.Route(str(i), rng.choice(("A", "B")), {"X": rng.randrange(3)},
                                 completed=bool(i % 3), defective=not bool(i % 4),
                                 stops=frozenset({"X"}) if i % 5 == 0 else frozenset()) for i in range(15)]
            before = copy.deepcopy((stations, routes))
            plain = line.simulate(stations, routes, case % 3, case * 3)
            traced, events = replay.record(stations, routes, case % 3, case * 3)
            self.assertEqual(replay.outcome(plain), replay.outcome(traced))
            self.assertEqual((stations, routes), before)
            self.assertEqual(sum(e[1] == "leave" for e in events), len(routes))
        # No station has positive service for this model: leave is the sole event at t=0.
        result, events = replay.record([line.SimStation("skip", 1, {"A": 0})], [line.Route("z", "A")], 0, 99)
        self.assertEqual((result.end, [e[1] for e in events]), (0, ["leave"]))
        print("P09 25 parallel/skip/retest/repair combinations and all-zero service: callback invariant")

    def test_p10_git_preservation_and_default_regeneration(self):
        def git(*args):
            return subprocess.check_output(["git", *args], cwd=ROOT)
        def blobs(ref, directory):
            rows = git("ls-tree", "-r", ref, "--", directory).decode("utf-8").splitlines()
            return {row.split("\t", 1)[1]: row.split("\t", 1)[0].split()[2] for row in rows}
        old = blobs(BASE, "reports")
        current = blobs("HEAD", "reports")
        self.assertTrue(all(current.get(name) == digest for name, digest in old.items()))
        changed = git("diff", "--name-only", BASE + "..HEAD", "--", "tests").decode().splitlines()
        old_tests = blobs(BASE, "tests")
        self.assertEqual([name for name in changed if name in old_tests], ["tests/test_sizing.py"])
        # At the new-feature commit, every already existing test was preserved verbatim.
        self.assertEqual(git("diff", "--name-only", "f7223a6..HEAD", "--", *old_tests), b"")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "reports").mkdir()
            rows = sizing.read_rows(ROOT / "reports/line_lamp_compare.csv")
            dev = next(row for row in rows if row["section"] == "development")
            held = next(row for row in rows if row["section"] == "holdout")
            result = cli(root, "src.line", ROOT / "recipes/line_lamp.json", "--seeds", dev["seeds"],
                         "--holdout-seeds", held["seeds"], "--products", dev["products"])
            self.assertEqual(result.returncode, 0, result.stderr)
            generated = list((root / "reports").iterdir())
            for path in generated:
                self.assertEqual(path.read_bytes(), (ROOT / "reports" / path.name).read_bytes(), path.name)
            result = cli(root, "src.replay", ROOT / "recipes/line_replay.json", "--out", "reports/line_replay.html",
                         "--root", root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((root / "reports/line_replay.html").read_bytes(), (ROOT / "reports/line_replay.html").read_bytes())
            before = snapshot(root / "reports")
            result = cli(root, "src.secom", ROOT / "recipes/secom_check.json")
            self.assertEqual(result.returncode, 0, result.stderr)
            for name in ("secom_check_features.csv", "secom_check_summary.csv", "secom_check.md"):
                self.assertEqual((root / "reports" / name).read_bytes(), (ROOT / "reports" / name).read_bytes(), name)
            self.assertTrue(all(snapshot(root / "reports")[name] == digest for name, digest in before.items()))
        print("P10 old report blobs=%d unchanged; new-feature commit preserves old tests; line reports=%d regenerated identical; replay and SECOM submitted reports identical" % (len(old), len(generated)))


if __name__ == "__main__":
    unittest.main()

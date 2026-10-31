"""Review 027 delta probes. Generated inputs/outputs stay in temporary directories."""

import csv
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest

from src import line, sizing


ROOT = Path(__file__).resolve().parents[3]
BASE = "580214e0e33c98493a991c743c07ea87230e51a5"
ENV = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
OUTPUTS = ("sizing_lamp_curve.csv", "sizing_lamp_spec.csv", "sizing_lamp_sheet.md")


def read_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def save_rows(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def snapshot():
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in ("src", "tests", "recipes", "reports", "data")
            for p in (ROOT / folder).rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"}


def cli(root, module, *args, seed="0"):
    return subprocess.run([sys.executable, "-B", "-m", module, *map(str, args)], cwd=root,
                          env=dict(ENV, PYTHONHASHSEED=seed), capture_output=True, encoding="utf-8", timeout=300)


class Probe027(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before = snapshot()
        cls.fixture = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.fixture.cleanup)
        cls.small = Path(cls.fixture.name)
        shutil.copytree(ROOT / "recipes", cls.small / "recipes")
        result = cli(cls.small, "src.line", "recipes/line_lamp.json", "--seeds", "0-1",
                     "--holdout-seeds", "1000-1001", "--products", "200")
        if result.returncode:
            raise AssertionError(result.stderr)
        shutil.copyfile(ROOT / "reports/msa_lamp_guard.csv", cls.small / "reports/msa_lamp_guard.csv")

    @classmethod
    def tearDownClass(cls):
        if cls.before != snapshot():
            raise AssertionError("Protected repository files changed")
        print("PRESERVATION protected files=%d unchanged" % len(cls.before), flush=True)

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        shutil.copytree(ROOT / "reports", self.root / "reports")
        shutil.copytree(ROOT / "recipes", self.root / "recipes")

    def small_inputs(self):
        for path in (self.small / "reports").iterdir():
            shutil.copyfile(path, self.root / "reports" / path.name)

    def edit_settings(self, **changes):
        path = self.root / "recipes/sizing_lamp.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data.update(changes)
        path.write_text(json.dumps(data), encoding="utf-8")

    def dashboard_refused(self):
        output = self.root / "reports/dashboard.html"
        output.write_bytes(b"previous HTML")
        result = cli(self.root, "src.dashboard", "--root", self.root, "--out", "reports/dashboard.html")
        preserved = output.read_bytes() == b"previous HTML"
        print("dashboard exit=%d preserved=%s stderr=%s" %
              (result.returncode, preserved, result.stderr.strip()), flush=True)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertTrue(preserved)

    def test_p01_r26_scope_and_single_product_omissions(self):
        path = self.root / "reports/incident_lamp_suspects.csv"
        original = read_rows(path)
        for scope, product in (("last_50", None), ("last_20", "195")):
            with self.subTest(scope=scope, product=product):
                save_rows(path, [row for row in original if not
                                (row["incident_id"] == "cusum-3" and row["scope"] == scope and
                                 (product is None or row["product"] == product))])
                self.dashboard_refused()
        print("P01 previous R26-M1 omissions refused", flush=True)

    def test_p02_duplicate_and_equal_size_wrong_product(self):
        path = self.root / "reports/incident_lamp_suspects.csv"
        original = read_rows(path)
        index = next(i for i, row in enumerate(original)
                     if row["incident_id"] == "cusum-3" and row["scope"] == "last_20")
        for duplicate in (True, False):
            with self.subTest(duplicate=duplicate):
                rows = [dict(row) for row in original]
                if duplicate:
                    rows.insert(index, dict(rows[index]))
                else:
                    rows[index]["product"] = "187"  # same count; required range is 188..207
                save_rows(path, rows)
                self.dashboard_refused()
        print("P02 duplicate/wrong boundary product refused", flush=True)

    def test_p03_refusal_then_normal_dashboard(self):
        path = self.root / "reports/incident_lamp_compare.csv"
        original = path.read_bytes()
        rows = read_rows(path)
        row = next(row for row in rows if row["section"] == "story_scope" and
                   row["method"] == "cusum" and row["scope"] == "last_20")
        row["scope_start"] = "189"  # scope_size remains 20
        save_rows(path, rows)
        self.dashboard_refused()
        path.write_bytes(original)
        for seed in ("0", "29"):
            result = cli(self.root, "src.dashboard", "--root", self.root, "--out", "reports/dashboard.html", seed=seed)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((self.root / "reports/dashboard.html").read_bytes(),
                             (ROOT / "reports/dashboard.html").read_bytes())
        print("P03 rejected inconsistent start; restored dashboard byte-identical twice", flush=True)

    def test_p04_malformed_settings_exit_three(self):
        path = self.root / "recipes/sizing_lamp.json"
        for text in ('{"line":', '{"line": "line_lamp.json",}', ""):
            with self.subTest(text=text):
                path.write_text(text, encoding="utf-8")
                before = {p: (self.root / "reports" / p).read_bytes() for p in OUTPUTS}
                result = cli(self.root, "src.sizing", "recipes/sizing_lamp.json")
                print("P04 malformed=%r exit=%d stderr=%s" %
                      (text, result.returncode, result.stderr.strip()), flush=True)
                self.assertEqual({p: (self.root / "reports" / p).read_bytes() for p in OUTPUTS}, before)
                self.assertEqual(result.returncode, 3, "Malformed configuration must use configuration exit code")

    def test_p05_impossible_gauge_counts(self):
        self.small_inputs()
        path = self.root / "reports/msa_lamp_guard.csv"
        original = read_rows(path)
        first = next(row for row in original if row["section"] == "holdout")
        cases = (("false_rejects", "-1"), ("false_rejects", str(int(first["true_good"]) + 1)),
                 ("false_accepts", "-1"), ("false_accepts", str(int(first["true_defects"]) + 1)))
        for key, value in cases:
            with self.subTest(key=key, value=value):
                rows = [dict(row) for row in original]
                next(row for row in rows if row["section"] == "holdout")[key] = value
                save_rows(path, rows)
                result = cli(self.root, "src.sizing", "recipes/sizing_lamp.json")
                gauge = next(row for row in read_rows(self.root / "reports/sizing_lamp_spec.csv")
                             if row["section"] == "gauge")
                print("P05 %s=%s exit=%d reject=%s accept=%s verdict=%s" %
                      (key, value, result.returncode, gauge["false_reject"], gauge["false_accept"], gauge["value"]),
                      flush=True)
                self.assertEqual(result.returncode, 2, "Impossible observation counts must be refused")

    def test_p06_output_cannot_overwrite_input_report(self):
        self.small_inputs()
        for key, source, output in (("guard_report", "msa_lamp_guard.csv", "sizing_lamp_spec.csv"),
                                    ("line_report", "line_lamp_compare.csv", "sizing_lamp_curve.csv")):
            with self.subTest(key=key):
                target = self.root / "reports" / output
                shutil.copyfile(self.root / "reports" / source, target)
                before = target.read_bytes()
                changes = dict(line_report="../reports/line_lamp_compare.csv", guard_report="../reports/msa_lamp_guard.csv")
                changes[key] = "../reports/" + output
                self.edit_settings(**changes)
                result = cli(self.root, "src.sizing", "recipes/sizing_lamp.json")
                print("P06 input/output collision=%s exit=%d preserved=%s" %
                      (key, result.returncode, target.read_bytes() == before), flush=True)
                self.assertEqual(target.read_bytes(), before, "Existing input report was overwritten")

    def test_p07_adjacent_ms_grids_and_joint_oracle(self):
        stations = [line.SimStation("S1", 1, {"A": 1001, "B": 0}, "X"),
                    line.SimStation("S2", 1, {"A": 2000, "B": 2000}, "Y")]
        routes = [[line.Route("a", "A", {"X": 2, "Y": 1}, stops=frozenset({"X"})),
                   line.Route("b", "B", {"Y": 1}), line.Route("c", "A", {"X": 1, "Y": 1})]]
        extras = [sizing.extra_time(k, 1) for k in ("1", "1.001", "1.999")]
        self.assertEqual(extras, [0, 0, 0])
        rates = [sizing.good_rate(sizing.stretch(stations, "X", extra), routes, 1, 333) for extra in extras]
        self.assertEqual(len(set(rates)), 1)
        joint = sizing.stretch(sizing.stretch(stations, "X", 1), "Y", 200)
        manual = [line.SimStation("S1", 1, {"A": 1002, "B": 0}, "X"),
                  line.SimStation("S2", 1, {"A": 2200, "B": 2200}, "Y")]
        self.assertEqual(joint, manual)
        self.assertEqual(sizing.good_rate(joint, routes, 1, sizing.repair_time("1.5", 333)),
                         line.uph(3, line.simulate(manual, routes[0], 1, 499).end))
        self.assertEqual(stations[0].times, {"A": 1001, "B": 0})
        print("P07 equal-ms grids, skip, retest and joint integer-ms oracle match", flush=True)

    def test_p08_full_default_sizing_reproduction(self):
        inputs = {p.name: p.read_bytes() for p in (self.root / "reports").iterdir() if p.name not in OUTPUTS}
        result = cli(self.root, "src.sizing", "recipes/sizing_lamp.json", seed="19")
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in OUTPUTS:
            self.assertEqual((self.root / "reports" / name).read_bytes(), (ROOT / "reports" / name).read_bytes(), name)
        for name, data in inputs.items():
            self.assertEqual((self.root / "reports" / name).read_bytes(), data, name)
        print("P08 full default three sizing reports byte-identical; prior reports unchanged", flush=True)

    def test_p09_frozen_git_files_and_legacy_regeneration(self):
        def tree(ref):
            raw = subprocess.check_output(["git", "ls-tree", "-r", ref, "--", "src", "tests", "recipes", "data", "reports"],
                                          cwd=ROOT, encoding="utf-8")
            return {name: meta.split()[2] for meta, name in (row.split("\t", 1) for row in raw.splitlines())}
        before, after = tree(BASE), tree("HEAD")
        changed = {name for name, sha in before.items() if after.get(name) != sha}
        self.assertEqual(changed, {"src/dashboard.py", "tests/test_dashboard.py"})
        # The old dashboard test body is intact; only new regression tests were inserted.
        diff = subprocess.check_output(["git", "diff", "--unified=0", BASE, "HEAD", "--", "tests/test_dashboard.py"],
                                       cwd=ROOT, encoding="utf-8")
        self.assertFalse(any(row.startswith("-") and not row.startswith("---") for row in diff.splitlines()))
        stage16 = subprocess.check_output(["git", "diff", "--name-only", "37192df", "HEAD", "--", "src", "tests", "recipes", "reports"],
                                          cwd=ROOT, encoding="utf-8").splitlines()
        self.assertTrue(all(name not in before for name in stage16))
        cases = (("sample_events.csv", ()),
                 ("sample_events_v2.csv", ("--recipe", "recipes/lamp_models.json")),
                 ("sample_events_retest.csv", ("--recipe", "recipes/lamp_models_retest.json")),
                 ("sample_events_equipment.csv", ("--recipe", "recipes/lamp_models_retest.json", "--equipment", "recipes/equipment.json")),
                 ("sample_events_restart.csv", ("--recipe", "recipes/lamp_models_retest.json", "--equipment", "recipes/equipment_restart.json", "--summary", "--trace", "f")),
                 ("sample_events_lot.csv", ("--recipe", "recipes/lamp_models_retest.json", "--equipment", "recipes/equipment_lot.json", "--summary", "--containment")),
                 ("sample_events_measured.csv", ("--recipe", "recipes/lamp_models_measured.json", "--equipment", "recipes/equipment_measured.json", "--summary", "--trace", "c", "--capability")))
        legacy = self.root / "legacy"
        legacy.mkdir()
        shutil.copytree(ROOT / "data", legacy / "data")
        shutil.copytree(ROOT / "recipes", legacy / "recipes")
        count = 0
        for filename, args in cases:
            source = legacy / "data" / filename
            self.assertTrue(source.exists(), filename)
            result = cli(legacy, "src.main", str(source.relative_to(legacy)), *args)
            self.assertEqual(result.returncode, 0, result.stderr)
            generated = list((legacy / "reports").glob(source.stem + "_*.csv"))
            self.assertGreaterEqual(len(generated), 3, filename)
            for path in generated:
                self.assertEqual(path.read_bytes(), (ROOT / "reports" / path.name).read_bytes(), path.name)
                count += 1
        self.assertGreaterEqual(count, 12)
        old_reports = sum(name.startswith("reports/") for name in before)
        print("P09 prior report blobs=%d unchanged; legacy reports regenerated=%d; old test bodies intact" %
              (old_reports, count), flush=True)

    def test_p10_joint_requirement_test_rejects_fabricated_result(self):
        # Invoke only this assertion method, without running its suite/setup or editing its file.
        module = runpy.run_path(str(ROOT / "tests/test_sizing.py"), run_name="probe027_test_definitions")
        case = module["RunTests"]("test_t281_joint_is_worse_than_each_limit")
        case.rows = read_rows(ROOT / "reports/sizing_lamp_spec.csv")
        joint = next(row for row in case.rows if row["section"] == "joint")
        joint.update(good_uph="0.0000", holdout_good_uph="999999.0000", value="동시 충족")
        try:
            case.test_t281_joint_is_worse_than_each_limit()
        except AssertionError:
            print("P10 T281 assertion rejects fabricated joint output", flush=True)
            return
        print("P10 T281 assertion accepts fabricated good_uph=0, holdout=999999, verdict=동시 충족", flush=True)
        self.fail("T281 assertion must verify actual combined conditions/results rather than an inequality alone")


if __name__ == "__main__":
    unittest.main()

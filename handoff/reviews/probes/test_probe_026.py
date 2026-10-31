"""Review 026: focused delta probes; all generated files stay in TemporaryDirectory."""

import csv
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

from src import anomaly, dashboard


ROOT = Path(__file__).resolve().parents[3]
BASE = "9fe96d4f8774c24c4bcc8b503b35f0695343b11f"
ENV = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")


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


class Probe026(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before = snapshot()

    @classmethod
    def tearDownClass(cls):
        if cls.before != snapshot():
            raise AssertionError("Protected repository files changed during probes")
        print("PRESERVATION original source/tests/recipes/reports/data files=%d unchanged" % len(cls.before), flush=True)

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.reports = self.root / "reports"
        self.reports.mkdir()
        for name in (*dashboard.INPUTS, *dashboard.TEXT_INPUTS,
                     *("plc_station_%s.csv" % s for s in dashboard.SCENARIOS)):
            shutil.copyfile(ROOT / "reports" / name, self.reports / name)
        shutil.copytree(ROOT / "recipes", self.root / "recipes")

    def cli(self, module, *args):
        return subprocess.run([sys.executable, "-B", "-m", module, *map(str, args)],
                              cwd=self.root, env=ENV, capture_output=True, encoding="utf-8", timeout=240)

    def upstream(self, module, *args):
        result = self.cli(module, *args)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def edit(self, name, **changes):
        path = self.root / "recipes" / name
        data = json.loads(path.read_text(encoding="utf-8"))
        data.update(changes)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def shown(self):
        result = self.cli("src.dashboard", "--root", self.root, "--out", "reports/dashboard.html")
        self.assertEqual(result.returncode, 0, result.stderr)
        return (self.reports / "dashboard.html").read_text(encoding="utf-8")

    def refused(self):
        output = self.reports / "dashboard.html"
        output.write_bytes(b"previous")
        result = self.cli("src.dashboard", "--root", self.root, "--out", "reports/dashboard.html")
        print("refusal actual_exit=%d previous_preserved=%s stderr=%s" %
              (result.returncode, output.read_bytes() == b"previous", result.stderr.strip()), flush=True)
        if result.returncode == 0:
            page = html.unescape(output.read_text(encoding="utf-8"))
            chain = next(row for row in re.findall(r"<tr>.*?</tr>", page) if "<td>cusum-3</td>" in row)
            print("accepted incomplete chain: " + chain, flush=True)
        self.assertEqual(result.returncode, 2, "Incomplete true-stop links must be refused")
        self.assertEqual(output.read_bytes(), b"previous")

    def test_p01_actual_degenerate_msa(self):
        self.edit("generator_measured.json", process_cpk=1e6)
        self.edit("msa_lamp.json", products=12, dev_seeds="7-7", holdout_seeds="1007-1007")
        self.upstream("src.msa", "recipes/msa_lamp.json")
        rows = read_rows(self.reports / "msa_lamp_grr.csv")
        self.assertEqual({r["pct_grr"] for r in rows}, {""})
        page = self.shown()
        self.assertIn("계산 가능한 %GRR이 없어", page)
        self.assertIn("판정 불가", page)
        print("P01 actual MSA exit=0 blank_GRR=%d dashboard=0" % len(rows), flush=True)

    def test_p02_mixed_blank_and_zero_grr(self):
        path = self.reports / "msa_lamp_grr.csv"
        rows = read_rows(path)
        rows[0].update(pct_grr="", ndc="", verdict="판정 불가")
        rows[1]["pct_grr"] = "0.0000"
        save_rows(path, rows)
        page = self.shown()
        self.assertIn("good %GRR 계산 불가", page)
        self.assertIn("marginal %GRR 0.0000", page)
        self.assertIn("marginal %GRR: 0.0000", page)
        self.assertNotIn("good %GRR:", page)
        print("P02 mixed blank/zero/nonzero GRR preserves rows and skips only blank bar", flush=True)

    def test_p03_actual_no_threshold_pipeline(self):
        self.edit("anomaly_lamp.json", shifts=[0.01, 0.02, 0.03], false_limit=1e-9,
                  min_detection=1.0, min_shift_detection=1.0, iterations=50,
                  splits={"train": {"seed_start": 0, "count": 30},
                          "validation": {"seed_start": 1000, "count": 12},
                          "holdout": {"seed_start": 2000, "count": 12}})
        self.upstream("src.anomaly", "recipes/anomaly_lamp.json")
        self.upstream("src.spc", "recipes/spc_lamp.json")
        replay = read_rows(self.reports / "anomaly_lamp_replay.csv")
        self.assertEqual({r["status"] for r in replay}, {"임계값 없음"})
        self.assertEqual({r["alarm"] for r in replay}, {""})
        page = self.shown()
        self.assertIn("재생 상태 임계값 없음", page)
        self.assertIn("임계값이 없어 수치가 빈칸인 방법", page)
        print("P03 actual anomaly -> SPC -> dashboard exit=0; missing thresholds shown", flush=True)

    def test_p04_real_missed_replay_then_missing_model_then_recovery(self):
        settings = anomaly.load_settings(ROOT / "recipes/anomaly_lamp.json")
        values = {(r["section"], r["name"]): r["value"]
                  for r in read_rows(ROOT / "reports/anomaly_lamp_model.csv")}
        model = anomaly.Model(*[[float(values[section, name]) for name in anomaly.FEATURES]
                                for section in ("mean", "scale", "weight")],
                              float(values["bias", "bias"]), float(values["fit", "gradient_norm"]), 1, 1)
        scenario = anomaly.build_split(settings.splits["holdout"], settings, anomaly.load_process(settings))[1]
        threshold = max(anomaly.logistic_scores(scenario, model)) + 1
        replay = anomaly.replay_rows(scenario, model, threshold, settings)
        self.assertTrue(replay)
        self.assertEqual({r["status"] for r in replay}, {"missed"})
        self.assertFalse(any(str(r["alarm"]) == "1" for r in replay))
        save_rows(self.reports / "anomaly_lamp_replay.csv", replay)
        self.assertIn("재생 상태 missed", self.shown())
        path = self.reports / "anomaly_lamp_model.csv"
        original = path.read_bytes()
        save_rows(path, [r for r in read_rows(path) if r["section"] != "bias"])
        self.refused()
        path.write_bytes(original)
        self.assertIn("재생 상태 missed", self.shown())
        print("P04 generated missed replay accepted; missing bias refused; recovery accepted", flush=True)

    def test_p05_missing_true_stop_links_and_recovery(self):
        path = self.reports / "incident_lamp_pfmea.md"
        original = path.read_bytes()
        text = original.decode("utf-8-sig")
        for token in ("cusum-3", "| PF-06 | 유출품이 후보 목록에서 누락 | cusum-3"):
            with self.subTest(token=token):
                path.write_text("\n".join(s for s in text.splitlines() if token not in s), encoding="utf-8")
                self.refused()
                path.write_bytes(original)
                self.shown()
        scope_path = self.reports / "incident_lamp_suspects.csv"
        save_rows(scope_path, [r for r in read_rows(scope_path) if r["incident_id"] != "cusum-3"])
        self.refused()
        print("P05 whole/one-PFMEA/whole-suspect omissions refused; restored input succeeds", flush=True)

    def test_p06_one_entire_scope_missing(self):
        path = self.reports / "incident_lamp_suspects.csv"
        rows = read_rows(path)
        removed = [r for r in rows if r["incident_id"] == "cusum-3" and r["scope"] == "last_50"]
        self.assertEqual(len(removed), 50)
        expected = next(r for r in read_rows(self.reports / "incident_lamp_compare.csv")
                        if r["section"] == "story_scope" and r["method"] == "cusum" and r["scope"] == "last_50")
        self.assertEqual(expected["scope_size"], "50")
        save_rows(path, [r for r in rows if r not in removed])
        print("P06 input missing cusum-3 last_50=50 rows, compare still requires scope_size=50", flush=True)
        self.refused()

    def test_p07_one_scope_product_missing(self):
        path = self.reports / "incident_lamp_suspects.csv"
        rows = read_rows(path)
        victim = next(r for r in rows if r["incident_id"] == "cusum-3" and r["scope"] == "last_20")
        rows.remove(victim)
        save_rows(path, rows)
        print("P07 input missing one cusum-3 last_20 product; compare requires 20, actual rows=19", flush=True)
        self.refused()

    def test_p08_pfmea_pipe_in_failure_mode_and_early_link_refusal(self):
        path = self.reports / "incident_lamp_pfmea.md"
        original = path.read_text(encoding="utf-8-sig")
        path.write_text(original.replace("측정 평균이 위로 이동", "측정 | 평균이 위로 이동"), encoding="utf-8")
        page = html.unescape(self.shown())
        self.assertIn("해당 없음: 고장 전 오경보", page)
        self.assertIn("해당 없음: 수리 뒤 오경보", page)
        self.assertIn("PF-02, PF-06", page)
        with path.open("a", encoding="utf-8") as target:
            target.write("| PF-02 | 측정 평균 | cusum-1 | 임의 연결 |\n")
        self.refused()
        print("P08 failure-mode pipe accepted; false-stop link refused; both reasons shown", flush=True)

    def test_p09_line_no_selection_and_no_balance(self):
        original = (self.root / "recipes/line_lamp.json").read_bytes()
        self.edit("line_lamp.json", floor={"length_mm": 1000, "width_mm": 7000,
                  "aisle_mm": 1000, "pitch_mm": 300, "gap_mm": 200})
        arguments = ("recipes/line_lamp.json", "--seeds", "0-0", "--holdout-seeds", "1000-1000", "--products", "20")
        self.upstream("src.line", *arguments)
        self.assertFalse(any(r["section"] == "holdout" for r in read_rows(self.reports / "line_lamp_compare.csv")))
        self.assertIn("기준 충족 조합 없음", self.shown())
        (self.root / "recipes/line_lamp.json").write_bytes(original)
        self.edit("line_lamp.json", demand_units=100000000)
        self.upstream("src.line", *arguments)
        self.assertFalse(any(r["section"] == "development" for r in read_rows(self.reports / "line_lamp_compare.csv")))
        (self.reports / "line_lamp_layout.svg").write_text("<svg><script>bad()</script></svg>", encoding="utf-8")
        page = self.shown()
        self.assertIn("선택 조합 없음", page)
        self.assertNotIn("bad()", page)
        self.assertNotIn('class="scroll plate"', page)
        print("P09 actual line outputs: no selection and no balance accepted; stale SVG excluded", flush=True)

    def test_p10_frozen_files_and_legacy_reports(self):
        changed = subprocess.check_output(["git", "diff", "--name-only", BASE + "..HEAD"], cwd=ROOT).decode().splitlines()
        protected_changes = [p for p in changed if p.startswith(("src/", "tests/", "recipes/", "data/", "reports/"))]
        self.assertEqual(sorted(protected_changes), ["reports/dashboard.html", "src/dashboard.py", "tests/test_dashboard.py"])
        historical = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", BASE, "--", "reports", "tests"], cwd=ROOT).decode().splitlines()
        count = 0
        for name in historical:
            if name in ("reports/dashboard.html", "tests/test_dashboard.py"):
                continue
            # Git blobs use LF; this checkout's CSVs use CRLF. Compare commits as raw
            # blobs, then separately verify the worktree and regenerated raw bytes.
            previous = subprocess.check_output(["git", "show", BASE + ":" + name], cwd=ROOT)
            current = subprocess.check_output(["git", "show", "HEAD:" + name], cwd=ROOT)
            self.assertEqual(current, previous, name)
            count += 1
        self.assertEqual(subprocess.run(["git", "diff", "--quiet", "HEAD", "--", "src", "tests", "recipes", "data", "reports"], cwd=ROOT).returncode, 0)
        cases = [
            ("sample_events", []),
            ("sample_events_v2", ["--recipe", "lamp_models.json"]),
            ("sample_events_retest", ["--recipe", "lamp_models_retest.json"]),
            ("sample_events_equipment", ["--recipe", "lamp_models_retest.json", "--equipment", "equipment.json"]),
            ("sample_events_restart", ["--recipe", "lamp_models_retest.json", "--equipment", "equipment_restart.json", "--summary", "--trace", "f"]),
            ("sample_events_lot", ["--recipe", "lamp_models_retest.json", "--equipment", "equipment_lot.json", "--summary", "--containment"]),
            ("sample_events_measured", ["--recipe", "lamp_models_measured.json", "--equipment", "equipment_measured.json", "--summary", "--trace", "c", "--capability"]),
        ]
        reports = 0
        for stem, arguments in cases:
            resolved = [str(ROOT / "recipes" / v) if v.endswith(".json") else v for v in arguments]
            self.upstream("src.main", ROOT / "data" / (stem + ".csv"), *resolved)
            for generated in self.reports.glob(stem + "_*.csv"):
                self.assertEqual(generated.read_bytes(), (ROOT / "reports" / generated.name).read_bytes(), generated.name)
                reports += 1
        print("P10 baseline report/test blobs=%d byte-identical; legacy regenerated reports=%d byte-identical" % (count, reports), flush=True)

    def test_p11_dashboard_repeatability_and_input_preservation(self):
        initial = {p.name: p.read_bytes() for p in self.reports.iterdir()}
        self.shown()
        output = (self.reports / "dashboard.html").read_bytes()
        self.assertEqual(output, (ROOT / "reports/dashboard.html").read_bytes())
        self.shown()
        self.assertEqual(output, (self.reports / "dashboard.html").read_bytes())
        self.assertLess(len(output), dashboard.MAX_BYTES)
        for name, value in initial.items():
            self.assertEqual((self.reports / name).read_bytes(), value, name)
        print("P11 dashboard bytes=%d repeated/submitted equal; all input bytes unchanged" % len(output), flush=True)


if __name__ == "__main__":
    unittest.main()

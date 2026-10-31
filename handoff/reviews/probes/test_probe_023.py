"""Review 023: diff-focused probes; generated reports stay in tempfile directories."""

import ast
import csv
from decimal import Decimal, localcontext
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace

from src import anomaly, dashboard, incident, spc


ROOT = Path(__file__).resolve().parents[3]
BASE = "adfbb7fdeced951b5e3eb109f603b29c98267bbb"
ENV = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def cli(module, folder, *args):
    return subprocess.run([sys.executable, "-B", "-m", module, *map(str, args)], cwd=folder, env=ENV,
                          capture_output=True, text=True, encoding="utf-8")


def copy_inputs(folder):
    reports = Path(folder) / "reports"
    reports.mkdir()
    names = list(dashboard.INPUTS) + list(dashboard.TEXT_INPUTS)
    names += ["plc_station_%s.csv" % name for name in dashboard.SCENARIOS]
    for name in names:
        shutil.copyfile(ROOT / "reports" / name, reports / name)
    return reports


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        return reader.fieldnames, list(reader)


def write_csv(path, fields, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def dashboard_cli(folder):
    return cli("src.dashboard", folder, "--root", folder, "--out", "reports/dashboard.html")


class StaticCells(HTMLParser):
    """Collect actual table cells, excluding SVG coordinates, title text and JSON."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.section = None
        self.cell = None
        self.cells = {}

    def handle_starttag(self, tag, attrs):
        if tag == "section":
            self.section = dict(attrs).get("id")
        if tag == "td":
            self.cell = []

    def handle_data(self, value):
        if self.cell is not None:
            self.cell.append(value)

    def handle_endtag(self, tag):
        if tag == "td" and self.cell is not None:
            self.cells.setdefault(self.section, []).append("".join(self.cell))
            self.cell = None
        if tag == "section":
            self.section = None


class Probe023(unittest.TestCase):
    def test_p01_small_lambda_independent_formula_and_endpoints(self):
        limits = spc.Limits(0, 2.326, 1, 1.342, -1.342, 4.917, .4474, 10)
        outcomes = []
        for weight in (5e-324, 1e-200, 1e-20, .2, 1.0):
            chart = spc.Ewma(limits, spc.Tuning(weight, 3, .5, 5))
            with localcontext() as context:
                context.prec = 750
                w = Decimal.from_float(weight)
                value = Decimal(0)
                for index in range(12):
                    value = w * Decimal.from_float(.1) + (1 - w) * value
                    bound = 3 * (w / (2 - w) * (1 - (1 - w) ** (2 * (index + 1)))).sqrt()
                    self.assertEqual(chart.update(.1), abs(value) > bound)
                    self.assertGreater(chart.limit, 0)
                outcomes.append((weight, chart.limit, float(bound)))
                self.assertLessEqual(abs(chart.limit - float(bound)), max(5e-324, float(bound) * 1e-14))
        print("P01 lambda/actual/Decimal limit:", outcomes, flush=True)

    def test_p02_limits_duplicate_orders_identical_and_recovery(self):
        fields, rows = read_csv(ROOT / "reports/spc_lamp_methods.csv")
        index = next(i for i, row in enumerate(rows) if row["section"] == "limits" and row["name"] == "sigma_hat")
        good = rows[index]
        bad = dict(good, value="999.0")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "limits.csv"
            for pair in ((bad, good), (good, bad), (good, good)):
                write_csv(path, fields, rows[:index] + list(pair) + rows[index + 1:])
                with self.assertRaisesRegex(ValueError, "같은 행"):
                    spc.load_limits(path)
            write_csv(path, fields, rows)
            self.assertEqual(spc.load_limits(path)["sigma_hat"], good["value"])
        print("P02 contradictory both orders + identical duplicate refused; valid accepted", flush=True)

    def test_p03_replay_range_window_and_valid_after_refusal(self):
        scenario = SimpleNamespace(seed=7, values=["a", "b", "c"])
        fields = ["t", "seed", "value", "window_values"]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "replay.csv"
            for row in (dict(t=3, seed=7, value="c", window_values="c"),
                        dict(t=-1, seed=7, value="c", window_values="c"),
                        dict(t=0, seed=7, value="a", window_values="b a"),
                        dict(t=0, seed=7, value="a", window_values="")):
                write_csv(path, fields, [row])
                with self.assertRaises(ValueError):
                    spc.check_replay(path, scenario)
            write_csv(path, fields, [dict(t=2, seed=7, value="c", window_values="a b c")])
            spc.check_replay(path, scenario)
        print("P03 t=length, negative, oversized/empty window refused; valid accepted", flush=True)

    def test_p04_product_range_boundaries_and_bool(self):
        raw = json.loads((ROOT / "recipes/incident_lamp.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "incident.json"
            for products in (65536, 100000, True):
                path.write_text(json.dumps(dict(raw, products=products)), encoding="utf-8")
                with self.assertRaises(incident.IncidentError):
                    incident.load_settings(path)
            for products in (1, 65535):
                path.write_text(json.dumps(dict(raw, products=products, onset_product=1)), encoding="utf-8")
                self.assertEqual(incident.load_settings(path).products, products)
        print("P04 products 65536/100000/bool refused; 1/65535 accepted", flush=True)

    def test_p05_svg_mixed_case_external_reference_and_atomic_refusal(self):
        results = []
        for function in ("URL", "uRl"):
            with tempfile.TemporaryDirectory() as folder:
                reports = copy_inputs(folder)
                old = reports / "dashboard.html"
                old.write_bytes(b"previous")
                payload = '<svg xmlns="http://www.w3.org/2000/svg"><rect width="20" height="20" fill="%s(//example.invalid/p.svg#p)"/></svg>' % function
                (reports / "line_lamp_layout.svg").write_text(payload, encoding="utf-8")
                result = dashboard_cli(folder)
                results.append((function, result.returncode, old.read_bytes() == b"previous"))
        print("P05 function/exit/old-preserved:", results, flush=True)
        self.assertEqual(results, [("URL", 2, True), ("uRl", 2, True)])

    def test_p06_second_alarm_mismatch_is_not_ignored(self):
        with tempfile.TemporaryDirectory() as folder:
            reports = copy_inputs(folder)
            path = reports / "anomaly_lamp_replay.csv"
            fields, rows = read_csv(path)
            alarm = next(row for row in rows if row["alarm"] == "1")
            rows.append(dict(alarm, t=str(int(alarm["t"]) + 1), z="99.0000000000"))
            write_csv(path, fields, rows)
            old = reports / "dashboard.html"
            old.write_bytes(b"previous")
            result = dashboard_cli(folder)
            print("P06 second alarm z=99 exit/old-preserved:", result.returncode,
                  old.read_bytes() == b"previous", flush=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(old.read_bytes(), b"previous")

    def test_p07_nan_cannot_satisfy_contribution_equality(self):
        with tempfile.TemporaryDirectory() as folder:
            reports = copy_inputs(folder)
            path = reports / "anomaly_lamp_replay.csv"
            fields, rows = read_csv(path)
            next(row for row in rows if row["alarm"] == "1")["z"] = "nan"
            write_csv(path, fields, rows)
            result = dashboard_cli(folder)
            print("P07 alarm z=nan exit:", result.returncode, flush=True)
            self.assertEqual(result.returncode, 2)
            self.assertFalse((reports / "dashboard.html").exists())

    def test_p08_pfmea_evidence_and_observation_are_static_cells(self):
        with tempfile.TemporaryDirectory() as folder:
            reports = copy_inputs(folder)
            path = reports / "pfmea_lamp_report.csv"
            fields, rows = read_csv(path)
            row = next(row for row in rows if row["section"] == "evidence" and row["id"] == "PF-01")
            row.update(reference="metric:probe_023_reference", value="0.123456789023")
            write_csv(path, fields, rows)
            result = dashboard_cli(folder)
            self.assertEqual(result.returncode, 0, result.stderr)
            page = StaticCells()
            page.feed((reports / "dashboard.html").read_text(encoding="utf-8"))
            found = [value in page.cells["pfmea"] for value in (row["reference"], row["value"])]
            print("P08 PF-01 evidence reference/value in PFMEA table:", found, flush=True)
            self.assertEqual(found, [True, True])

    def test_p09_chart_values_have_static_numeric_table(self):
        with tempfile.TemporaryDirectory() as folder:
            reports = copy_inputs(folder)
            path = reports / "spc_lamp_chart.csv"
            fields, rows = read_csv(path)
            rows[15]["c_plus"] = "876.543219023"
            write_csv(path, fields, rows)
            result = dashboard_cli(folder)
            self.assertEqual(result.returncode, 0, result.stderr)
            page = StaticCells()
            page.feed((reports / "dashboard.html").read_text(encoding="utf-8"))
            present = rows[15]["c_plus"] in page.cells["detect"]
            print("P09 CUSUM source value in static detect table:", present, flush=True)
            self.assertTrue(present)

    def test_p10_all_insufficient_capability_is_displayable(self):
        with tempfile.TemporaryDirectory() as folder:
            reports = copy_inputs(folder)
            path = reports / "gen_measured_seed42_capability.csv"
            fields, rows = read_csv(path)
            for row in rows:
                if row["section"] == "capability":
                    row.update(n="1", cpk="", ppk="", status="표본 부족")
            write_csv(path, fields, rows)
            result = dashboard_cli(folder)
            print("P10 all n=1/blank Cpk/Ppk exit/stderr:", result.returncode, result.stderr.strip(), flush=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("표본 부족", (reports / "dashboard.html").read_text(encoding="utf-8"))

    def test_p11_escape_recovery_determinism_and_readonly_inputs(self):
        data = {"x": '</script><!--<script>&\u2028\u2029"'}
        self.assertEqual(json.loads(dashboard.safe_json(data)), data)
        for mark in ("<", ">", "&", "\u2028", "\u2029"):
            self.assertNotIn(mark, dashboard.safe_json(data))
        outputs = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as folder:
                reports = copy_inputs(folder)
                before = {path.name: path.read_bytes() for path in reports.iterdir()}
                for target in ("reports/../outside.html", "reports/sub/a.html", "reports/anomaly_lamp_methods.csv"):
                    result = cli("src.dashboard", folder, "--root", folder, "--out", target)
                    self.assertEqual(result.returncode, 2)
                result = dashboard_cli(folder)
                self.assertEqual(result.returncode, 0, result.stderr)
                outputs.append((reports / "dashboard.html").read_bytes())
                self.assertEqual(before, {name: (reports / name).read_bytes() for name in before})
        self.assertEqual(*outputs)
        self.assertEqual(outputs[0], (ROOT / "reports/dashboard.html").read_bytes())
        print("P11 rejected paths then valid; JSON roundtrip; inputs unchanged:", len(before),
              "; two roots/stored HTML identical", flush=True)

    def test_p12_preserved_tests_artifacts_and_reproduced_reports(self):
        def methods(source):
            tree = ast.parse(source)
            return {(node.name, child.name): ast.dump(child, include_attributes=False)
                    for node in tree.body if isinstance(node, ast.ClassDef)
                    for child in node.body if isinstance(child, ast.FunctionDef) and child.name.startswith("test")}

        total, changed = 0, []
        for name in git("ls-tree", "-r", "--name-only", BASE, "tests").decode().splitlines():
            if not name.endswith(".py"):
                continue
            before = methods(git("show", BASE + ":" + name).decode("utf-8-sig"))
            after = methods((ROOT / name).read_text(encoding="utf-8-sig"))
            total += len(before)
            changed.extend((name, *key) for key in before if before[key] != after.get(key))
        self.assertEqual(changed, [("tests/test_incident.py", "ConfigTests", "test_t233_invalid_values")])
        self.assertEqual(git("diff", "--name-only", "3fe0761..HEAD", "tests").decode().splitlines(),
                         ["tests/test_dashboard.py"])
        artifacts = git("ls-tree", "-r", "--name-only", BASE, "recipes", "reports", "data").decode().splitlines()
        differences = [name for name in artifacts if git("show", BASE + ":" + name) != git("show", "HEAD:" + name)]
        self.assertEqual(differences, [])
        watched = [path for directory in ("reports", "recipes", "data")
                   for path in (ROOT / directory).rglob("*") if path.is_file()]
        before = {path: path.read_bytes() for path in watched}
        for module, config, args, count in (("src.station", "plc_station.json", ("--scenario", "all"), 16),
                                            ("src.incident", "incident_lamp.json", (), 5)):
            with tempfile.TemporaryDirectory() as folder:
                result = cli(module, folder, ROOT / "recipes" / config, *args)
                self.assertEqual(result.returncode, 0, result.stderr)
                produced = list((Path(folder) / "reports").iterdir())
                self.assertEqual(len(produced), count)
                for path in produced:
                    self.assertEqual(path.read_bytes(), (ROOT / "reports" / path.name).read_bytes(), path.name)
                print("P12 reproduced byte-identical", module, count, flush=True)
        config = spc.load_settings(ROOT / "recipes/spc_lamp.json")
        settings = anomaly.load_settings(config.anomaly)
        process = anomaly.load_process(settings)
        normals = [anomaly.build_scenario(seed, 0, settings, process)
                   for index, seed in enumerate(settings.splits["train"])
                   if anomaly.assignment(index, settings.shifts) == 0]
        limits = spc.estimate(spc.training_series(normals, process))
        seed = settings.splits["holdout"][1]
        scenario = anomaly.build_scenario(seed, anomaly.assignment(1, settings.shifts), settings, process)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "chart.csv"
            spc._write_csv(path, spc.CHART_COLUMNS, spc.chart_rows(scenario, limits, config.tuning, process))
            self.assertEqual(path.read_bytes(), (ROOT / "reports/spc_lamp_chart.csv").read_bytes())
        print("P12 regenerated SPC chart 400 rows byte-identical", flush=True)
        self.assertEqual(before, {path: path.read_bytes() for path in watched})
        print("P12 base tests/artifacts/changed test:", total, len(artifacts), changed,
              "; watched raw files unchanged:", len(watched), flush=True)

    def test_p13_documented_input_manifest_is_sufficient(self):
        with tempfile.TemporaryDirectory() as folder:
            reports = Path(folder) / "reports"
            reports.mkdir()
            names = list(dashboard.INPUTS) + ["line_lamp_layout.svg"]
            names += ["plc_station_%s.csv" % name for name in dashboard.SCENARIOS]
            for name in names:
                shutil.copyfile(ROOT / "reports" / name, reports / name)
            result = dashboard_cli(folder)
            print("P13 documented manifest only exit/stderr:", result.returncode, result.stderr.strip(), flush=True)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()

"""Review 024: focused dashboard regressions; output only in temporary folders."""

import ast
import csv
from decimal import Decimal, localcontext
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

from src import dashboard


ROOT = Path(__file__).resolve().parents[3]
BASE = "64188b7b77da14203cd3e48dca1d71843deb914c"
PRE_DASHBOARD = "3fe0761"
OLD = b"existing dashboard - preserve on refusal\n"
NAMES = (list(dashboard.INPUTS) + list(dashboard.TEXT_INPUTS)
         + ["plc_station_%s.csv" % name for name in dashboard.SCENARIOS])


def copy_inputs(folder):
    reports = Path(folder) / "reports"
    reports.mkdir()
    for name in NAMES:
        shutil.copyfile(ROOT / "reports" / name, reports / name)
    (reports / "dashboard.html").write_bytes(OLD)
    return reports


def read_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        return list(reader.fieldnames), list(reader)


def write_rows(path, fields, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def cli(folder):
    return subprocess.run(
        [sys.executable, "-B", "-m", "src.dashboard", "--root", str(folder),
         "--out", "reports/dashboard.html"], cwd=ROOT,
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8"),
        capture_output=True, text=True, encoding="utf-8",
    )


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def section(text, name):
    return text.split('<section id="%s">' % name, 1)[1].split("</section>", 1)[0]


class Cells(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.current = None
        self.cells = []

    def handle_starttag(self, tag, attrs):
        if tag == "td":
            self.current = ""

    def handle_data(self, data):
        if self.current is not None:
            self.current += data

    def handle_endtag(self, tag):
        if tag == "td" and self.current is not None:
            self.cells.append(self.current)
            self.current = None


def cells(text):
    result = Cells()
    result.feed(text)
    return result.cells


class Probe024(unittest.TestCase):
    def assert_refused(self, folder, reports):
        result = cli(folder)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual((reports / "dashboard.html").read_bytes(), OLD)
        return result

    def test_p01_svg_case_missing_id_then_valid_reference(self):
        with tempfile.TemporaryDirectory() as folder:
            reports = copy_inputs(folder)
            path = reports / "line_lamp_layout.svg"
            original = path.read_bytes()
            for value in ("URL(//example.invalid/x.svg#p)", "uRl(//example.invalid/x.svg#p)",
                          "URL(#missing)", "url(#missing)"):
                with self.subTest(value=value):
                    path.write_text('<svg xmlns="http://www.w3.org/2000/svg">'
                                    '<rect fill="%s"/></svg>' % value, encoding="utf-8")
                    self.assert_refused(folder, reports)
            path.write_bytes(original)
            result = cli(folder)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("url(#arrow)", (reports / "dashboard.html").read_text(encoding="utf-8"))
        print("P01 four SVG case/reference refusals preserve old HTML; valid recovery exit=0", flush=True)

    def test_p02_multiple_alarms_order_and_late_mismatch(self):
        with tempfile.TemporaryDirectory() as folder:
            reports = copy_inputs(folder)
            path = reports / "anomaly_lamp_replay.csv"
            fields, rows = read_rows(path)
            alarm = next(row for row in rows if row["alarm"] == "1")
            normal = [row for row in rows if row["alarm"] != "1"]
            second = dict(alarm, t="9024")
            for pair in ([alarm, second], [second, alarm]):
                write_rows(path, fields, normal + pair)
                result = cli(folder)
                self.assertEqual(result.returncode, 0, result.stderr)
                body = section((reports / "dashboard.html").read_text(encoding="utf-8"), "detect")
                self.assertEqual(body.count("의 b + Σ w_j s_j"), 2)
                self.assertIn("경보 측정 t=9024", body)
            for pair in ([alarm, dict(second, z="99")], [dict(second, z="99"), alarm]):
                (reports / "dashboard.html").write_bytes(OLD)
                write_rows(path, fields, normal + pair)
                self.assert_refused(folder, reports)
        print("P02 both valid alarm orders display 2 tables; either mismatch order exit=2/old preserved", flush=True)

    def test_p03_nonfinite_inputs_then_valid_recovery(self):
        with tempfile.TemporaryDirectory() as folder:
            reports = copy_inputs(folder)
            model_path = reports / "anomaly_lamp_model.csv"
            replay_path = reports / "anomaly_lamp_replay.csv"
            model_fields, model = read_rows(model_path)
            replay_fields, replay = read_rows(replay_path)
            cases = 0
            for value in ("NaN", "inf", "-Infinity"):
                for target in ("bias", "weight", "feature", "z"):
                    changed_model = [dict(row) for row in model]
                    changed_replay = [dict(row) for row in replay]
                    if target in ("bias", "weight"):
                        next(row for row in changed_model if row["section"] == target)["value"] = value
                    else:
                        next(row for row in changed_replay if row["alarm"] == "1")[
                            "s_mean" if target == "feature" else "z"] = value
                    write_rows(model_path, model_fields, changed_model)
                    write_rows(replay_path, replay_fields, changed_replay)
                    with self.subTest(value=value, target=target):
                        self.assert_refused(folder, reports)
                    cases += 1
            write_rows(model_path, model_fields, model)
            write_rows(replay_path, replay_fields, replay)
            self.assertEqual(cli(folder).returncode, 0)
        print("P03 %d nonfinite input cases exit=2/old preserved; valid recovery exit=0" % cases, flush=True)

    def test_p04_finite_inputs_product_overflow_must_not_match_z(self):
        with tempfile.TemporaryDirectory() as folder:
            reports = copy_inputs(folder)
            path = reports / "anomaly_lamp_model.csv"
            fields, model = read_rows(path)
            for row in model:
                if row["section"] == "weight":
                    row["value"] = {"mean": "1e308", "sd": "-1e308"}.get(row["name"], "0")
                elif row["section"] == "bias":
                    row["value"] = "0"
            write_rows(path, fields, model)
            path = reports / "anomaly_lamp_replay.csv"
            fields, replay = read_rows(path)
            for row in replay:
                if row["alarm"] == "1":
                    for feature in dashboard.FEATURES:
                        row["s_" + feature] = "2" if feature in ("mean", "sd") else "0"
                    row["z"] = "1"  # Exact independent sum: 2e308 - 2e308 = 0, not 1.
            write_rows(path, fields, replay)
            alarm = next(row for row in replay if row["alarm"] == "1")
            with localcontext() as context:
                context.prec = 350
                exact = sum(Decimal(row["value"]) * Decimal(alarm["s_" + row["name"]])
                            for row in model if row["section"] == "weight")
            self.assertEqual(exact, Decimal(0))
            self.assertNotEqual(exact, Decimal(alarm["z"]))
            result = cli(folder)
            output = (reports / "dashboard.html").read_bytes()
            text = output.decode("utf-8")
            print("P04 finite input overflow exit=%s; inf/-inf cells=%s/%s; old_preserved=%s"
                  % (result.returncode, "<td>inf</td>" in text, "<td>-inf</td>" in text, output == OLD), flush=True)
            print("P04 independent Decimal sum=%s; report z=%s" % (exact, alarm["z"]), flush=True)
            self.assertEqual(result.returncode, 2, "nonfinite arithmetic incorrectly accepted as z=1")
            self.assertEqual(output, OLD)

    def test_p05_pfmea_duplicate_escaped_blank_and_zero_evidence(self):
        payload = 'metric:<script>024</script>&"\u2028'
        scope = 'LEAK & "024"'
        with tempfile.TemporaryDirectory() as folder:
            reports = copy_inputs(folder)
            path = reports / "pfmea_lamp_report.csv"
            fields, rows = read_rows(path)
            evidence = next(row for row in rows if row["section"] == "evidence")
            evidence.update(reference=payload, scope=scope, numerator="0", denominator="024", value="0.000024")
            rows.append(dict(evidence, reference="metric:024-empty", value="", numerator="", denominator=""))
            write_rows(path, fields, list(reversed(rows)))
            result = cli(folder)
            self.assertEqual(result.returncode, 0, result.stderr)
            text = (reports / "dashboard.html").read_text(encoding="utf-8")
            content = section(text, "pfmea")
            values = cells(content)
            for value in (payload, scope, "0", "024", "0.000024", "metric:024-empty"):
                self.assertIn(value, values)
            self.assertNotIn("<script>024</script>", text)
            for row in rows:
                if row["section"] == "item":
                    self.assertEqual((row["severity"], row["occurrence"], row["detection"]), ("", "", ""))
        print("P05 reversed/duplicate PFMEA ID evidence, markup, empty and zero: all exact static cells, escaped", flush=True)

    def test_p06_chart_middle_row_and_shift_values_static(self):
        with tempfile.TemporaryDirectory() as folder:
            reports = copy_inputs(folder)
            path = reports / "spc_lamp_chart.csv"
            fields, rows = read_rows(path)
            middle = rows[len(rows) // 2]
            changed = {name: str(24 + index) + ".024024024" for index, name in enumerate(
                ("value", "z", "ewma_limit", "c_plus", "c_minus", "xbar", "range"))}
            middle.update(changed)
            write_rows(path, fields, rows)
            shift_values = []
            for filename in ("spc_lamp_methods.csv", "anomaly_lamp_methods.csv"):
                path = reports / filename
                fields, rows = read_rows(path)
                for row in rows:
                    if row["section"] == "holdout_shift":
                        row["detection_rate"] = "0.024024%03d" % len(shift_values)
                        shift_values.append(row["detection_rate"])
                write_rows(path, fields, rows)
            result = cli(folder)
            self.assertEqual(result.returncode, 0, result.stderr)
            values = cells(section((reports / "dashboard.html").read_text(encoding="utf-8"), "detect"))
            for value in list(changed.values()) + shift_values:
                self.assertIn(value, values)
        print("P06 7 middle-row chart strings and %d shift strings occur in static cells" % len(shift_values), flush=True)

    def test_p07_new_required_columns_fail_before_write_then_recover(self):
        with tempfile.TemporaryDirectory() as folder:
            reports = copy_inputs(folder)
            count = 0
            for filename, columns in (
                ("msa_lamp_guard.csv", ("lower", "upper")),
                ("spc_lamp_chart.csv", ("value", "xbar", "range")),
                ("pfmea_lamp_report.csv", ("reference", "scope", "numerator", "denominator", "value")),
            ):
                path = reports / filename
                original = path.read_bytes()
                fields, rows = read_rows(path)
                for column in columns:
                    write_rows(path, [name for name in fields if name != column],
                               [{name: value for name, value in row.items() if name != column} for row in rows])
                    with self.subTest(filename=filename, column=column):
                        result = self.assert_refused(folder, reports)
                        self.assertIn(column, result.stderr)
                    count += 1
                path.write_bytes(original)
            self.assertEqual(cli(folder).returncode, 0)
        print("P07 %d newly required missing columns exit=2/old preserved; recovery exit=0" % count, flush=True)

    def test_p08_all_short_and_mixed_short_capability(self):
        with tempfile.TemporaryDirectory() as folder:
            reports = copy_inputs(folder)
            path = reports / "gen_measured_seed42_capability.csv"
            fields, rows = read_rows(path)
            cap = [row for row in rows if row["section"] == "capability"]
            for row in cap:
                row.update(n="1", cpk="", ppk="", status="표본 부족")
            write_rows(path, fields, rows)
            result = cli(folder)
            self.assertEqual(result.returncode, 0, result.stderr)
            text = (reports / "dashboard.html").read_text(encoding="utf-8")
            self.assertIn("유효한 Cpk 없음", section(text, "overview"))
            self.assertEqual(section(text, "measure").count("<td>표본 부족</td>"), len(cap))
            cap[-1].update(n="125", cpk="0.024024024", ppk="0.123024024", status="算定024")
            write_rows(path, fields, list(reversed(rows)))
            result = cli(folder)
            self.assertEqual(result.returncode, 0, result.stderr)
            text = (reports / "dashboard.html").read_text(encoding="utf-8")
            self.assertIn("0.024024024", section(text, "overview"))
            self.assertNotIn("유효한 Cpk 없음", section(text, "overview"))
            self.assertIn("0.123024024", cells(section(text, "measure")))
        print("P08 all %d short samples display; mixed/reversed rows retain sole Cpk/Ppk" % len(cap), flush=True)

    def test_p09_manifest_determinism_inputs_and_stored_dashboard(self):
        current = (ROOT / "handoff/tasks.md").read_text(encoding="utf-8").split("# v2 14단계 명세", 1)[0]
        names = re.findall(r"`reports/([^`]+)`", current.split("## 입력", 1)[1].split("## 화면", 1)[0])
        names = [expanded for name in names for expanded in (
            ["plc_station_%s.csv" % item for item in dashboard.SCENARIOS]
            if name == "plc_station_<scenario>.csv" else [name])]
        self.assertEqual(set(names), set(NAMES))
        outputs = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as folder:
                reports = copy_inputs(folder)
                before = {name: (reports / name).read_bytes() for name in names}
                result = cli(folder)
                self.assertEqual(result.returncode, 0, result.stderr)
                outputs.append((reports / "dashboard.html").read_bytes())
                self.assertEqual(before, {name: (reports / name).read_bytes() for name in names})
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(outputs[0], (ROOT / "reports/dashboard.html").read_bytes())
        self.assertLessEqual(len(outputs[0]), dashboard.MAX_BYTES)
        print("P09 manifest %d files sufficient/unchanged; two roots and stored HTML byte-identical (%d bytes)"
              % (len(names), len(outputs[0])), flush=True)

    def test_p10_preserved_blobs_and_test_bodies(self):
        names = git("ls-tree", "-r", "--name-only", PRE_DASHBOARD,
                    "src", "tests", "recipes", "data", "reports").decode().splitlines()
        changed = [name for name in names if git("show", PRE_DASHBOARD + ":" + name)
                   != git("show", "HEAD:" + name)]
        self.assertEqual(changed, [], "pre-dashboard stages must stay byte-identical")
        artifacts = [name for name in names if name.startswith(("recipes/", "data/", "reports/"))]

        def methods(source):
            return {(node.name, child.name): ast.dump(child, include_attributes=False)
                    for node in ast.parse(source).body if isinstance(node, ast.ClassDef)
                    for child in node.body if isinstance(child, ast.FunctionDef) and child.name.startswith("test")}

        changed_methods = []
        total = 0
        for name in git("ls-tree", "-r", "--name-only", BASE, "tests").decode().splitlines():
            if name.endswith(".py"):
                before = methods(git("show", BASE + ":" + name).decode("utf-8-sig"))
                after = methods((ROOT / name).read_text(encoding="utf-8-sig"))
                total += len(before)
                changed_methods += [(name, *key) for key in before if before[key] != after.get(key)]
        self.assertEqual(changed_methods, [
            ("tests/test_dashboard.py", "PageTests", "test_t241_blank_scores"),
            ("tests/test_dashboard.py", "RefusalTests", "test_t242_svg_rules"),
        ])
        print("P10 pre-dashboard preserved blobs=%d (artifacts=%d); prior review test bodies=%d, only changed=%s"
              % (len(names), len(artifacts), total, changed_methods), flush=True)


if __name__ == "__main__":
    unittest.main()

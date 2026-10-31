import csv
from fractions import Fraction
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from src.line import Route, SimStation, show, simulate
from src.sizing import (
    FIRST_FAIL, NO_FAIL, OVER, WITHIN, SizingError, allowed_reject, extra_time, first_limit, gauge_status, load_settings,
    read_gauges, repair_time, route_digest, stretch,
)


ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "reports" / "msa_lamp_guard.csv"
LINE_ARGS = ("--seeds", "0-1", "--holdout-seeds", "1000-1001", "--products", "200")
OUTPUTS = ("sizing_lamp_curve.csv", "sizing_lamp_spec.csv", "sizing_lamp_sheet.md")
GRIDS = {"line": "line_lamp.json", "line_report": "a.csv", "balance_report": "b.csv", "guard_report": "c.csv",
         "test_multipliers": ["1", "1.5"], "repair_multipliers": ["1", "2"]}


def run_module(root, *arguments, seed="0"):
    environment = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1",
                       PYTHONHASHSEED=seed)
    return subprocess.run([sys.executable, "-m", *arguments], cwd=str(root), env=environment, capture_output=True,
                          text=True, encoding="utf-8")


def spec_rows(root):
    with (Path(root) / "reports" / "sizing_lamp_spec.csv").open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def write_csv(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


class FormulaTests(unittest.TestCase):
    def test_t267_allowed_reject(self):
        self.assertEqual(allowed_reject(Fraction(180), Fraction(200)), Fraction(1, 10))
        self.assertEqual(allowed_reject(Fraction(180), Fraction(180)), 0)
        self.assertIsNone(allowed_reject(Fraction(180), Fraction(179)))

    def test_t268_later_pass_is_ignored(self):
        self.assertEqual(first_limit([True, True, False, True]), (1, FIRST_FAIL))

    def test_t269_grid_end_and_failed_baseline(self):
        self.assertEqual(first_limit([True, True, True]), (2, NO_FAIL))
        with self.assertRaises(ValueError):
            first_limit([False, True])

    def test_t270_only_positive_times_of_one_machine(self):
        leak = SimStation("S1", 1, {"A": 3000, "B": 0}, "LEAK")
        other = SimStation("S2", 1, {"A": 5000, "B": 5000}, "LIGHT")
        result = stretch([leak, other], "LEAK", extra_time("1.5", 2000))
        self.assertEqual(result[0].times, {"A": 4000, "B": 0})
        self.assertIs(result[1], other)
        self.assertEqual(leak.times, {"A": 3000, "B": 0})

    def test_t270_retest_stretches_every_attempt(self):
        station = [SimStation("S1", 1, {"A": 10000}, "X")]
        items = [Route("a", "A", {"X": 2})]
        self.assertEqual(simulate(station, items, 0, 0).end, 20000)
        self.assertEqual(simulate(stretch(station, "X", 1000), items, 0, 0).end, 22000)

    def test_t270_skip_stays_a_skip(self):
        stations = [SimStation("S1", 1, {"B": 1000}), SimStation("S2", 1, {"B": 0}, "X")]
        result = simulate(stretch(stations, "X", 5000), [Route("a", "B")], 0, 0)
        self.assertEqual((result.end, result.work["S2"]), (1000, 0))

    def test_t271_repair_delay(self):
        station = [SimStation("S1", 1, {"A": 10000}, "X")]
        items = [Route("a", "A", {"X": 1}, stops=frozenset({"X"})), Route("b", "A", {"X": 1})]
        self.assertEqual(repair_time("2", 100000), 200000)
        self.assertEqual(simulate(station, items, 0, 100000).end, 120000)
        self.assertEqual(simulate(station, items, 0, repair_time("2", 100000)).end, 220000)
        self.assertEqual(simulate(station, items, 0, 0).end, 20000)
        self.assertEqual(simulate(station, items[:1], 0, repair_time("2", 100000)).end, 10000)
        pair = [SimStation("S1", 2, {"A": 10000}, "X")]
        three = [Route("a", "A", {"X": 1}, stops=frozenset({"X"})), Route("b", "A", {"X": 1}), Route("c", "A", {"X": 1})]
        self.assertEqual(simulate(pair, three, 0, repair_time("2", 100000)).end, 20000)

    def test_t280_increment_is_floored_and_applied(self):
        self.assertEqual([extra_time("1.5", test) for test in (0, 1, 1000)], [0, 0, 500])
        self.assertEqual(extra_time("1.1", 1000), 100)
        self.assertEqual(extra_time("1.001", 100), extra_time("1.002", 100))
        self.assertEqual(repair_time("1.0005", 1000), 1000)

    def test_t276_gauge_comparison(self):
        allowed = Fraction(1, 1000)
        self.assertEqual(gauge_status(Fraction(1, 2000), allowed), WITHIN)
        self.assertEqual(gauge_status(allowed, allowed), WITHIN)
        self.assertEqual(gauge_status(Fraction(2, 1000), allowed), OVER)

    def test_t276_exact_counts_decide_when_display_is_the_same(self):
        below, above = Fraction(99, 100000), Fraction(101, 100000)
        self.assertEqual(show(below), show(above))
        self.assertEqual(gauge_status(below, Fraction(1, 1000)), WITHIN)
        self.assertEqual(gauge_status(above, Fraction(1, 1000)), OVER)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "guard.csv"
            rows = read_csv(GUARD)
            first = next(row for row in rows if row["section"] == "holdout")
            first.update(false_rejects="1", true_good="1000001")
            write_csv(path, rows)
            self.assertEqual(read_gauges(path)[0][2], Fraction(1, 1000001))

    def test_route_digest_ignores_set_order(self):
        one = [[Route("a", "A", {"X": 1, "Y": 2}, stops=frozenset({"X", "Y"}))]]
        two = [[Route("a", "A", {"Y": 2, "X": 1}, stops=frozenset({"Y", "X"}))]]
        self.assertEqual(route_digest(one), route_digest(two))


class SettingsTests(unittest.TestCase):
    def refused(self, data):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sizing.json"
            path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
            with self.assertRaises(SizingError):
                load_settings(path)

    def test_t275_bad_settings(self):
        changes = [("test_multipliers", ["2", "3"]), ("test_multipliers", ["1", "1"]), ("repair_multipliers", ["1", "0.5"]),
                   ("test_multipliers", []), ("test_multipliers", [True]), ("repair_multipliers", [1, 2]),
                   ("test_multipliers", ["1", "x"]), ("line", 3), ("guard_report", "")]
        for key, value in changes:
            with self.subTest(key=key, value=value):
                self.refused(dict(GRIDS, **{key: value}))
        self.refused({key: value for key, value in GRIDS.items() if key != "line"})
        self.refused(dict(GRIDS, extra=1))
        self.refused(json.dumps(GRIDS).replace('"1.5"', "NaN"))
        self.refused(json.dumps(GRIDS).replace('"line_lamp.json"', "NaN"))

    def test_shipped_settings_load(self):
        settings = load_settings(ROOT / "recipes" / "sizing_lamp.json")
        self.assertEqual(settings.test_multipliers[0], "1")
        self.assertEqual(settings.repair_multipliers[-1], "5")


class RunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.root = Path(cls.folder.name)
        shutil.copytree(ROOT / "recipes", cls.root / "recipes")
        result = run_module(cls.root, "src.line", "recipes/line_lamp.json", *LINE_ARGS)
        assert result.returncode == 0, result.stderr
        shutil.copyfile(GUARD, cls.root / "reports" / "msa_lamp_guard.csv")
        result = run_module(cls.root, "src.sizing", "recipes/sizing_lamp.json")
        assert result.returncode == 0, result.stderr
        cls.rows = spec_rows(cls.root)

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def setUp(self):
        self.work = tempfile.TemporaryDirectory()
        self.addCleanup(self.work.cleanup)
        self.copy = Path(self.work.name)
        shutil.copytree(self.root / "recipes", self.copy / "recipes")
        shutil.copytree(self.root / "reports", self.copy / "reports")
        for name in OUTPUTS:
            (self.copy / "reports" / name).unlink()

    def refused(self):
        result = run_module(self.copy, "src.sizing", "recipes/sizing_lamp.json")
        self.assertEqual(result.returncode, 2, result.stderr)
        for name in OUTPUTS:
            self.assertFalse((self.copy / "reports" / name).exists(), name)

    def change(self, name, edit):
        path = self.copy / "reports" / name
        rows = read_csv(path)
        write_csv(path, edit(rows))

    def test_t272_changed_uph_refused(self):
        def edit(rows):
            row = next(item for item in rows if item["section"] == "development")
            row["good_uph"] = show(Fraction(row["good_uph"]) + Fraction(1, 1000))
            return rows
        self.change("line_lamp_compare.csv", edit)
        self.refused()

    def test_t272_duplicate_development_row_refused(self):
        def edit(rows):
            row = next(item for item in rows if item["section"] == "development")
            return [dict(row)] + rows
        self.change("line_lamp_compare.csv", edit)
        self.refused()

    def test_t272_missing_development_row_refused(self):
        def edit(rows):
            row = next(item for item in rows if item["section"] == "development")
            return [item for item in rows if item is not row]
        self.change("line_lamp_compare.csv", edit)
        self.refused()

    def test_t272_missing_spec_row_refused(self):
        self.change("line_lamp_balance.csv", lambda rows: [row for row in rows if row["section"] != "spec"])
        self.refused()

    def test_t273_no_combo_refused(self):
        def edit(rows):
            for row in rows:
                if row["section"] == "selection":
                    row.update(combo="", value="기준 충족 조합 없음 / 검증할 선택 없음")
            return [row for row in rows if row["section"] != "holdout"]
        self.change("line_lamp_compare.csv", edit)
        self.refused()

    def test_t273_no_balance_refused(self):
        self.change("line_lamp_compare.csv", lambda rows: [row for row in rows if row["section"] in ("notice", "selection")])
        self.change("line_lamp_compare.csv", lambda rows: [dict(row, combo="") for row in rows])
        self.refused()

    def test_t274a_holdout_text_alone_refused(self):
        def edit(rows):
            next(row for row in rows if row["section"] == "holdout")["seeds"] = "1002-1003"
            return rows
        self.change("line_lamp_compare.csv", edit)
        self.refused()

    def test_t274b_new_holdout_keeps_development(self):
        result = run_module(self.copy, "src.line", "recipes/line_lamp.json", "--seeds", "0-1", "--holdout-seeds", "1002-1003",
                            "--products", "200")
        self.assertEqual(result.returncode, 0, result.stderr)
        result = run_module(self.copy, "src.sizing", "recipes/sizing_lamp.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        changed = spec_rows(self.copy)
        keys = ("machine", "limit_seconds", "multiplier", "limit_kind", "good_uph")
        for section in ("test", "repair"):
            self.assertEqual([[row[key] for key in keys] for row in changed if row["section"] == section],
                             [[row[key] for key in keys] for row in self.rows if row["section"] == section])
        before = next(row for row in self.rows if row["section"] == "baseline")
        after = next(row for row in changed if row["section"] == "baseline")
        self.assertEqual(before["good_uph"], after["good_uph"])
        self.assertNotEqual(before["holdout_good_uph"], after["holdout_good_uph"])

    def test_t277_guard_shapes_refused(self):
        def short(rows):
            first = next(row for row in rows if row["section"] == "holdout")
            return [row for row in rows if row is not first]

        def blank(rows):
            next(row for row in rows if row["section"] == "holdout")["false_rejects"] = ""
            return rows

        def zero(rows):
            next(row for row in rows if row["section"] == "holdout")["true_good"] = "0"
            return rows
        original = (self.copy / "reports" / "msa_lamp_guard.csv").read_bytes()
        for edit in (short, blank, zero):
            with self.subTest(edit=edit.__name__):
                (self.copy / "reports" / "msa_lamp_guard.csv").write_bytes(original)
                self.change("msa_lamp_guard.csv", edit)
                self.refused()

    def test_t278_repeat_is_identical(self):
        inputs = {path.name: path.read_bytes() for path in (self.copy / "reports").iterdir()}
        result = run_module(self.copy, "src.sizing", "recipes/sizing_lamp.json", seed="7")
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in OUTPUTS:
            self.assertEqual((self.copy / "reports" / name).read_bytes(), (self.root / "reports" / name).read_bytes(), name)
        for name, data in inputs.items():
            self.assertEqual((self.copy / "reports" / name).read_bytes(), data, name)

    def test_t279_sheet_text(self):
        text = (self.root / "reports" / "sizing_lamp_sheet.md").read_text(encoding="utf-8")
        for phrase in ("가상", "동시 허용 사양이 아니다", "실측 사이클과 시간 구성", "검사 성능과 시간의 관계", "정지·복구 기록",
                       "동시 조건 검증"):
            self.assertIn(phrase, text)
        for phrase in ("구매 사양", "설비 선정"):
            self.assertNotIn(phrase, text)

    def test_t281_joint_is_worse_than_each_limit(self):
        joint = next(row for row in self.rows if row["section"] == "joint")
        limits = [Fraction(row["good_uph"]) for row in self.rows if row["section"] in ("test", "repair")]
        self.assertLessEqual(Fraction(joint["good_uph"]), min(limits))
        self.assertIn(joint["value"], ("동시 충족", "동시 미충족"))

    def test_curve_covers_the_grid_and_limit_is_before_first_failure(self):
        curve = read_csv(self.root / "reports" / "sizing_lamp_curve.csv")
        self.assertEqual(len(curve), 3 * 10 + 8)
        for row in self.rows:
            if row["section"] not in ("test", "repair"):
                continue
            series = [item for item in curve if item["machine"] == row["machine"]]
            index = next((position for position, item in enumerate(series) if item["meets"] == "0"), len(series)) - 1
            self.assertEqual(series[index]["multiplier"], row["multiplier"])
            self.assertEqual(series[index]["value_seconds"], row["limit_seconds"])

    def test_notices_and_baseline_digests(self):
        notices = [row["value"] for row in self.rows if row["section"] == "notice"]
        self.assertEqual(len(notices), 5)
        baseline = next(row for row in self.rows if row["section"] == "baseline")
        for key in ("target_uph=", "line=", "dev_routes=", "holdout_routes="):
            self.assertIn(key, baseline["value"])


if __name__ == "__main__":
    unittest.main()

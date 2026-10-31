"""Review 021: focused probes; all generated outputs use tempfile directories."""

import ast
import csv
from decimal import Decimal, localcontext
from fractions import Fraction
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from src import anomaly, msa, spc


ROOT = Path(__file__).resolve().parents[3]
BASE = "5d46efe9975be42e18fb5b99ceda726e55984c88"
UNIT = spc.Limits(0.0, 2.326, 1.0, 3.0, -3.0, 10.0, 1.0, 2)
TUNING = spc.Tuning(0.2, 3, 0.5, 1.5)


def raw(name):
    return json.loads((ROOT / "recipes" / name).read_text(encoding="utf-8-sig"))


def dump(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def cli(module, *args, cwd):
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run([sys.executable, "-B", "-m", module, *map(str, args)], cwd=cwd, env=env,
                          capture_output=True, encoding="utf-8", timeout=240)


def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def write_rows(path, records):
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=tuple(records[0]))
        writer.writeheader()
        writer.writerows(records)


def generator(folder, **changes):
    data = raw("generator_measured.json")
    data.update(recipe=str(ROOT / "recipes/lamp_models_measured.json"),
                equipment=str(ROOT / "recipes/equipment_measured.json"))
    data.update(changes)
    return dump(Path(folder) / "generator.json", data)


def msa_config(folder, **changes):
    data = raw("msa_lamp.json")
    data.update(generator=str(ROOT / "recipes/generator_measured.json"), parts=2, operators=2, trials=2,
                products=30, dev_seeds="0-0", holdout_seeds="100-100", gauges={"good": data["gauges"]["good"]})
    data.update(changes)
    return dump(Path(folder) / "msa.json", data)


def prepare(folder, **changes):
    data = raw("anomaly_lamp.json")
    data.update(generator=str(ROOT / "recipes/generator_measured.json"), length=40, window=4,
                onset_min=12, onset_max=25, iterations=2,
                splits={name: {"seed_start": start, "count": 12}
                        for name, start in zip(anomaly.SPLITS, (0, 100, 200))})
    data.update(changes)
    anomaly_path = dump(Path(folder) / "anomaly.json", data)
    result = cli("src.anomaly", anomaly_path, cwd=folder)
    if result.returncode:
        raise AssertionError(result.stderr)
    config = raw("spc_lamp.json")
    config.update(anomaly="anomaly.json", anomaly_report="reports/anomaly_methods.csv",
                  anomaly_model="reports/anomaly_model.csv")
    return dump(Path(folder) / "spc.json", config)


class Probe021(unittest.TestCase):
    def test_p01_exact_guards_at_negative_bounds_and_tiny_width(self):
        tiny = "0." + "0" * 34 + "1"
        for lower, upper, expected in (("7", "13", ("7.001", "12.999")),
                                       ("-13", "-7", ("-12.999", "-7.001")),
                                       ("-3", "3", ("-2.999", "2.999"))):
            self.assertEqual(tuple(map(str, msa.acceptance_limits(lower, upper, tiny, 0.1))), expected)
        self.assertIsNone(msa.acceptance_limits("7", "13", "1" + "0" * 40, 0.1))
        self.assertEqual(msa.acceptance_limits("7", "13", "0", 0.1), (Decimal("7"), Decimal("13")))
        print("P01 tiny/negative/huge/zero guards: correct", flush=True)

    def test_p02_fixed_msa_extremes_complete_cli(self):
        for case in ("large_guard", "large_cpk"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as folder:
                changes = ({"guard_multipliers": ["1" + "0" * 40]} if case == "large_guard"
                           else {"generator": str(generator(folder, process_cpk=1e200))})
                result = cli("src.msa", msa_config(folder, **changes), cwd=folder)
                self.assertEqual(result.returncode, 0, result.stderr)
                reports = Path(folder) / "reports"
                self.assertEqual(len(list(reports.glob("msa_*.csv"))), 3)
                if case == "large_guard":
                    dev = next(row for row in rows(reports / "msa_guard.csv") if row["section"] == "development")
                    self.assertEqual(dev["status"], msa.NO_GUARD)
                else:
                    self.assertEqual(Decimal(rows(reports / "msa_grr.csv")[0]["cpk_obs"]), Decimal("1e200"))
                print("P02 %s: exit=0, reports=3" % case, flush=True)

    def test_p03_observed_cpk_across_scales_and_display_ties(self):
        for sigma in (1e-200, 1.0, 1e100):
            cpk = 1 / sigma
            for ratio in (0, 0.5, 2):
                value = msa.observed_cpk(cpk, sigma, ratio * sigma)
                self.assertAlmostEqual(value / cpk, 1 / math.hypot(1, ratio))
        self.assertEqual(msa._text(1.23445), "1.2345")
        self.assertEqual(msa._text(-1.23445), "-1.2345")
        print("P03 scale and signed HALF_UP: correct", flush=True)

    def test_p04_tiny_valid_ewma_lambda_keeps_positive_limit(self):
        tuning = spc.Tuning(1e-20, 3, 0.5, 1.5)
        with tempfile.TemporaryDirectory() as folder:
            config = raw("spc_lamp.json")
            config["ewma_lambda"] = tuning.ewma_lambda
            loaded = spc.load_settings(dump(Path(folder) / "spc.json", config))
            self.assertEqual(loaded.tuning.ewma_lambda, tuning.ewma_lambda)
        with localcontext() as context:
            context.prec = 90
            weight = Decimal("1e-20")
            z = Decimal(0)
            for t in range(12):
                z = weight * Decimal("0.1") + (1 - weight) * z
                limit = 3 * (weight / (2 - weight) * (1 - (1 - weight) ** (2 * (t + 1)))).sqrt()
                self.assertLess(z, limit)  # Independent high-precision oracle: no crossing at any t.
        chart = spc.Ewma(UNIT, tuning)
        actual = spc.first_alarm(chart, [0.1] * 12, 9)
        stable_limit = 3 * math.sqrt(tuning.ewma_lambda / (2 - tuning.ewma_lambda)
                                     * -math.expm1(2 * (chart.index + 1) * math.log1p(-tuning.ewma_lambda)))
        print("P04 alarm=%r limit=%r expected_no_alarm stable_limit=%r" %
              (actual, chart.limit, stable_limit), flush=True)
        self.assertIsNone(actual, "Valid lambda collapses the EWMA limit to zero")

    def test_p05_prewarm_and_joint_rules_at_offgrid_start(self):
        limits = spc.Limits(0, 2.326, 1, 10, -10, 1, 1, 8)
        values = [2.5] * 10 + [0.5, 1.5, 2.5, 3.5, 4.5]
        alarm, active = spc.subgroup_alarm(values, limits, 10, True)
        self.assertEqual((alarm, active), (14, ["range", "run_2of3"]))
        counts = spc.count_triggers([active])
        self.assertEqual((counts["range"], counts["run_2of3"], counts["joint"]), (1, 0, 1))
        self.assertEqual(spc.first_alarm(spc.Cusum(UNIT, TUNING), [0, 0, -1, -2], 0), 3)
        chart = spc.Cusum(UNIT, TUNING)
        for value in (0, 0, -1, -2):
            chart.update(value)
        self.assertEqual(chart.change_point(), 2)
        print("P05 prewarm, range/run priority and lower CUSUM: correct", flush=True)

    def test_p06_decision_denominator_exhaustive_offgrid_intervals(self):
        for first in range(2, 15):
            for last in range(0, 31):
                expected = sum(t % 5 == 4 for t in range(first, last + 1))
                self.assertEqual(spc.decision_count("xbar_we", first, last), expected)
        outcomes = [(0, None, 14), (1, 13, None), (1, 18, 14)]
        self.assertEqual(spc.false_per_1000_decisions("xbar_r", outcomes, 40, 10), Fraction(2000, 2))
        print("P06 403 offgrid intervals and pre-onset exposure: correct", flush=True)

    def test_p07_conflicting_duplicate_reference_rows_must_not_be_hidden(self):
        with tempfile.TemporaryDirectory() as folder:
            config = prepare(folder)
            path = Path(folder) / "reports/anomaly_methods.csv"
            records = rows(path)
            original = next(row for row in records if row["section"] == "validation" and row["method"] == "rule_3_2")
            wrong = dict(original, mean_delay_cost="999.0000")
            records.insert(0, wrong)  # Last-wins dict currently hides the conflicting row.
            write_rows(path, records)
            first = cli("src.spc", config, cwd=folder)
            write_rows(path, records[1:] + [wrong])
            second = cli("src.spc", config, cwd=folder)
            actual = (first.returncode, second.returncode)
            print("P07 conflicting reference duplicate order exits=%r" % (actual,), flush=True)
            self.assertEqual(actual, (2, 2), first.stderr + second.stderr)

    def test_p08_rule_metrics_collision_does_not_prove_same_measurements(self):
        with tempfile.TemporaryDirectory() as folder:
            gen = generator(folder, process_cpk=5, defective_product_probability=0)
            config = prepare(folder, generator=str(gen))
            settings = anomaly.load_settings(Path(folder) / "anomaly.json")
            before_process = anomaly.load_process(settings)
            before = anomaly.build_split(settings.splits["validation"], settings, before_process)
            generator(folder, process_cpk=6, defective_product_probability=0)
            after_process = anomaly.load_process(settings)
            after = anomaly.build_split(settings.splits["validation"], settings, after_process)
            self.assertNotEqual([s.values for s in before], [s.values for s in after])
            self.assertEqual(anomaly.rule_outcomes(before, settings), anomaly.rule_outcomes(after, settings))
            result = cli("src.spc", config, cwd=folder)
            print("P08 different_measurements=True identical_rule_outcomes=True exit=%d" % result.returncode,
                  flush=True)
            self.assertEqual(result.returncode, 2, result.stderr)

    def test_p09_invalid_config_then_valid_input(self):
        with tempfile.TemporaryDirectory() as folder:
            config = prepare(folder)
            good = json.loads(config.read_text(encoding="utf-8"))
            for bad in ([], dict(good, ewma_lambda=True), dict(good, cusum_h=float("nan")),
                        {key: value for key, value in good.items() if key != "anomaly_model"}):
                dump(config, bad)
                result = cli("src.spc", config, cwd=folder)
                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertFalse((Path(folder) / "reports/spc_methods.csv").exists())
            dump(config, good)
            result = cli("src.spc", config, cwd=folder)
            self.assertEqual(result.returncode, 0, result.stderr)
            print("P09 structural/bool/NaN/missing refusal followed by valid run: correct", flush=True)

    def test_p10_original_tests_and_artifacts_preserved(self):
        def git(*args):
            return subprocess.check_output(["git", *args], cwd=ROOT, stderr=subprocess.PIPE)

        def bodies(text):
            found = {}
            def visit(node, prefix=()):
                for child in ast.iter_child_nodes(node):
                    if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                        key = prefix + (child.name,)
                        if child.name.startswith("test_"):
                            found[key] = ast.dump(child, include_attributes=False)
                        visit(child, key)
                    else:
                        visit(child, prefix)
            visit(ast.parse(text))
            return found

        count = 0
        for name in git("ls-tree", "-r", "--name-only", BASE, "tests").decode().splitlines():
            if name.endswith(".py"):
                before = bodies(git("show", BASE + ":" + name).decode("utf-8-sig"))
                after = bodies((ROOT / name).read_text(encoding="utf-8-sig"))
                for key, value in before.items():
                    self.assertEqual(after.get(key), value, name + ":" + ".".join(key))
                    count += 1
        artifacts = git("ls-tree", "-r", "--name-only", BASE, "reports", "recipes", "data").decode().splitlines()
        for name in artifacts:
            self.assertEqual(git("hash-object", name).strip(), git("rev-parse", BASE + ":" + name).strip(), name)
        print("P10 original_test_bodies=%d unchanged_git_artifacts=%d" % (count, len(artifacts)), flush=True)

    def test_p11_default_msa_and_spc_report_bytes_and_repeat(self):
        reference_before = {path: path.read_bytes() for path in (ROOT / "reports").glob("anomaly_lamp_*.csv")}
        for module, config_name in (("src.msa", "msa_lamp.json"), ("src.spc", "spc_lamp.json")):
            with self.subTest(module=module), tempfile.TemporaryDirectory() as folder:
                result = cli(module, ROOT / "recipes" / config_name, cwd=folder)
                self.assertEqual(result.returncode, 0, result.stderr)
                generated = sorted((Path(folder) / "reports").glob("*.csv"))
                self.assertEqual(len(generated), 3 if module == "src.msa" else 2)
                for path in generated:
                    self.assertEqual(path.read_bytes(), (ROOT / "reports" / path.name).read_bytes(), path.name)
                print("P11 %s stored_bytes_equal=%d" % (module, len(generated)), flush=True)
                if module == "src.spc":
                    with tempfile.TemporaryDirectory() as second:
                        repeated = cli(module, ROOT / "recipes" / config_name, cwd=second)
                        self.assertEqual(repeated.returncode, 0, repeated.stderr)
                        for path in generated:
                            self.assertEqual(path.read_bytes(), (Path(second) / "reports" / path.name).read_bytes())
        for path, content in reference_before.items():
            self.assertEqual(path.read_bytes(), content, str(path))
        print("P11 anomaly input reports raw bytes unchanged; SPC repeat identical", flush=True)

    def test_p12_legacy_sample_reports_regenerate_unchanged(self):
        cases = (("sample_events", ()), ("sample_events_v2", ("--recipe", ROOT / "recipes/lamp_models.json")),
                 ("sample_events_retest", ("--recipe", ROOT / "recipes/lamp_models_retest.json")),
                 ("sample_events_equipment", ("--recipe", ROOT / "recipes/lamp_models_retest.json", "--equipment",
                                              ROOT / "recipes/equipment.json")))
        for stem, args in cases:
            with self.subTest(stem=stem), tempfile.TemporaryDirectory() as folder:
                result = cli("src.main", ROOT / "data" / (stem + ".csv"), *args, cwd=folder)
                self.assertEqual(result.returncode, 0, result.stderr)
                generated = list((Path(folder) / "reports").glob("*.csv"))
                self.assertEqual(len(generated), 4 if stem.endswith("equipment") else 3)
                for path in generated:
                    self.assertEqual(path.read_bytes(), (ROOT / "reports" / path.name).read_bytes(), path.name)
                print("P12 %s raw_bytes_equal=%d" % (stem, len(generated)), flush=True)


if __name__ == "__main__":
    unittest.main()

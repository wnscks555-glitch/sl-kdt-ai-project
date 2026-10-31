"""Review 020: diff-focused probes; outputs stay in temporary directories."""

import ast
import copy
import csv
from dataclasses import replace
from decimal import Decimal, ROUND_HALF_UP, localcontext
from fractions import Fraction
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest

from src import anomaly, line, modbus, msa, plc, station
from src.generate import check_measured_config, load_setup
from tests.test_plc import Rig


ROOT = Path(__file__).resolve().parents[3]
BASE = "4955767cc1a88ea7efc25703133878309a06e022"
RAW = json.loads((ROOT / "recipes/msa_lamp.json").read_text(encoding="utf-8"))


def dump(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def cli(module, *args, cwd):
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run([sys.executable, "-m", module, *map(str, args)], cwd=cwd, env=env,
                          capture_output=True, encoding="utf-8", timeout=240)


def small_config(folder, **changes):
    raw = copy.deepcopy(RAW)
    raw.update(generator=str(ROOT / "recipes/generator_measured.json"), parts=2, operators=2, trials=2,
               products=30, dev_seeds="0-0", holdout_seeds="100-100", gauges={"good": RAW["gauges"]["good"]})
    raw.update(changes)
    return dump(Path(folder) / "msa.json", raw)


def custom_generator(folder, **changes):
    raw = json.loads((ROOT / "recipes/generator_measured.json").read_text(encoding="utf-8"))
    raw.update(recipe=str(ROOT / "recipes/lamp_models_measured.json"),
               equipment=str(ROOT / "recipes/equipment_measured.json"))
    raw.update(changes)
    return dump(Path(folder) / "generator.json", raw)


class ReplyServer:
    def __init__(self, gaps):
        self.gaps = gaps
        self.listener = socket.socket()
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen()
        self.port = self.listener.getsockname()[1]
        self.thread = threading.Thread(target=self.serve, daemon=True)
        self.thread.start()

    def serve(self):
        connection, _ = self.listener.accept()
        with connection:
            connection.settimeout(2)
            try:
                for gap in self.gaps:
                    request = connection.recv(1024)
                    reply = request[:4] + struct.pack(">H", 5) + b"\x01\x03\x02\x00\x07"
                    for byte in reply:
                        time.sleep(gap)
                        connection.sendall(bytes([byte]))
            except OSError:
                pass

    def close(self):
        self.thread.join(3)
        self.listener.close()


class Probe020(unittest.TestCase):
    def test_p01_numeric_specs_across_all_three_loaders(self):
        with tempfile.TemporaryDirectory() as folder:
            raw = json.loads((ROOT / "recipes/lamp_models_measured.json").read_text(encoding="utf-8"))
            for item in raw["B"]["inspections"]:
                item.update(lsl="7", usl="13")
            recipe = dump(Path(folder) / "recipe.json", raw)
            generator = custom_generator(folder, recipe=str(recipe))
            setup = load_setup(generator)
            self.assertTrue(check_measured_config(setup[0], setup[2].models, setup[3]))
            settings = replace(anomaly.load_settings(ROOT / "recipes/anomaly_lamp.json"), generator=generator)
            process = anomaly.load_process(settings)
            config = replace(station.load_station(ROOT / "recipes/plc_station.json"), generator=generator)
            values, item = station.load_values(config, 42, 12)
            self.assertEqual(len(values), 12)
            self.assertEqual(Decimal(item.lsl), Decimal(process.item.lsl))
            msa_settings = msa.load_settings(small_config(folder, generator=str(generator)))
            self.assertEqual(msa.load_process(msa_settings).item, process.item)

    def test_p02_long_line_cli_and_signed_half_boundaries(self):
        samples = [Fraction("123456789012345678901234567890.12345"), Fraction(-1, 20000),
                   Fraction(1, 20000), Fraction(1, 3), Fraction(-1, 3)]
        with localcontext() as context:
            context.prec = 100
            for value in samples:
                expected = format((Decimal(value.numerator) / Decimal(value.denominator)).quantize(
                    Decimal(".0001"), rounding=ROUND_HALF_UP), ".4f")
                self.assertEqual(line.show(value), expected)
        with tempfile.TemporaryDirectory() as folder:
            raw = json.loads((ROOT / "recipes/line_lamp.json").read_text(encoding="utf-8"))
            raw.update(generator=str(ROOT / "recipes/generator_measured.json"),
                       period_seconds="123456789012345678901234567890.123")
            result = cli("src.line", dump(Path(folder) / "line.json", raw), "--seeds", "0-0",
                         "--holdout-seeds", "1000-1000", "--products", "1", cwd=folder)
            self.assertEqual(result.returncode, 0, result.stderr)
            text = (Path(folder) / "reports/line_balance.csv").read_text(encoding="utf-8-sig")
            self.assertIn("123456789012345678901234564890.1230", text)

    def test_p03_rejections_are_per_measurement_and_keep_state(self):
        rig = Rig()
        rig.reach(plc.WAIT_JUDGE)
        events = []
        for pair in ((9, 1), (1, 3), (0, 0), (9, 1), (1, 3), (9, 1)):
            rig.judge(*pair)
            self.assertEqual(rig.scan(), plc.WAIT_JUDGE)
            events.extend(rig.plc.events)
            self.assertEqual((rig.plc.verdict, rig.plc.processed), (0, 0))
        self.assertEqual(len(events), 2)
        rig.judge(1, 1)
        self.assertEqual(rig.scan(), plc.UNCLAMP)
        rig.set(clamp_closed=False, clamp_open=True)
        self.assertEqual(rig.scan(), plc.DISCHARGE)
        rig.set(part_present=False)
        self.assertEqual(rig.scan(), plc.IDLE)
        rig.set(measure_done=False)
        rig.reach(plc.WAIT_JUDGE)
        rig.judge(9, 1)
        self.assertEqual(rig.scan(), plc.WAIT_JUDGE)
        self.assertEqual(len(rig.plc.events), 1)
        self.assertEqual(rig.plc.processed, 1)

    def test_p04_fragmented_reply_exceeds_total_deadline(self):
        server = ReplyServer([0.04])
        client = modbus.ModbusClient(server.port, timeout=0.2)
        try:
            start = time.monotonic()
            with self.assertRaises(modbus.ModbusTimeout):
                client.read_registers(modbus.READ_HOLDING, 0, 1)
            self.assertTrue(client.closed)
            self.assertLess(time.monotonic() - start, 0.8)
        finally:
            client.close()
            server.close()

    def test_p05_deadline_restarts_for_each_request(self):
        server = ReplyServer([0.015, 0.015])
        client = modbus.ModbusClient(server.port, timeout=0.5)
        try:
            self.assertEqual(client.read_registers(modbus.READ_HOLDING, 0, 1), [7])
            time.sleep(0.55)
            self.assertEqual(client.read_registers(modbus.READ_HOLDING, 0, 1), [7])
        finally:
            client.close()
            server.close()

    def test_p06_positive_subprecision_guard_still_rounds_inward(self):
        multiplier = "0." + "0" * 34 + "1"
        actual = msa.acceptance_limits("7", "13", multiplier, 0.1)
        self.assertEqual(actual, (Decimal("7.001"), Decimal("12.999")), repr(actual))

    def test_p07_large_valid_guard_is_unavailable_not_crash(self):
        with tempfile.TemporaryDirectory() as folder:
            result = cli("src.msa", small_config(folder, guard_multipliers=["1" + "0" * 40]), cwd=folder)
            self.assertEqual(result.returncode, 0, result.stderr)
            with (Path(folder) / "reports/msa_guard.csv").open(encoding="utf-8-sig", newline="") as source:
                rows = list(csv.DictReader(source))
            self.assertEqual(next(row for row in rows if row["section"] == "development")["status"], msa.NO_GUARD)
            self.assertEqual(next(row for row in rows if row["section"] == "holdout")["value"], msa.NOT_VERIFIED)

    def test_p08_structural_rejections_create_no_reports(self):
        for changes in ({"gauges": {"good": None}}, {"gauges": {"good": []}},
                        {"gauges": {"good\n": RAW["gauges"]["good"]}},
                        {"guard_multipliers": ["0", "00.000"]}, {"holdout_seeds": "0-0"},
                        {"max_false_accept": True}, {"inspection": " "}):
            with self.subTest(changes=changes), tempfile.TemporaryDirectory() as folder:
                result = cli("src.msa", small_config(folder, **changes), cwd=folder)
                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertFalse((Path(folder) / "reports").exists())

    def test_p09_valid_large_process_cpk_completes_reports(self):
        with tempfile.TemporaryDirectory() as folder:
            generator = custom_generator(folder, process_cpk=1e200)
            setup = load_setup(generator)
            self.assertTrue(check_measured_config(setup[0], setup[2].models, setup[3]))
            result = cli("src.msa", small_config(folder, generator=str(generator)), cwd=folder)
            self.assertEqual(result.returncode, 0, result.stderr)
            with (Path(folder) / "reports/msa_grr.csv").open(encoding="utf-8-sig", newline="") as source:
                row = next(csv.DictReader(source))
            self.assertEqual(Decimal(row["cpk_obs"]), Decimal("1e200"))
            self.assertEqual((row["pct_grr"], row["ndc"], row["ndc_ok"]), ("", "", ""))

    def test_p10_fraction_anova_shift_and_scale_invariance(self):
        original = [[["1", "2", "4"], ["0", "3", "4"]],
                    [["5", "4", "7"], ["9", "6", "5"]],
                    [["8", "9", "10"], ["9", "11", "8"]]]
        altered = [[[str(Fraction(value) * 3 + 1000000) for value in cell] for cell in row] for row in original]
        first, second = msa.anova(original), msa.anova(altered)
        for name in ("ss_part", "ss_op", "ss_int", "ss_e", "var_e", "var_op", "var_int", "var_part"):
            self.assertEqual(getattr(second, name), 9 * getattr(first, name))
        self.assertEqual(first.pooled, second.pooled)
        self.assertEqual(msa.verdict(msa.percent_grr(first)), msa.verdict(msa.percent_grr(second)))
        values = [Fraction(value) for row in original for cell in row for value in cell]
        mean = sum(values) / len(values)
        self.assertEqual(first.ss_part + first.ss_op + first.ss_int + first.ss_e,
                         sum((value - mean) ** 2 for value in values))

    def test_p11_holdout_cannot_reselect_guard(self):
        process = anomaly.load_process(msa.load_settings(ROOT / "recipes/msa_lamp.json"))
        with tempfile.TemporaryDirectory() as folder:
            settings = msa.load_settings(small_config(folder, products=500, max_false_accept=1))
        other = replace(settings, holdout_seeds=range(700, 703))
        gauge = settings.gauges["good"]
        first = msa.guard_gauge("good", gauge, 0.1, settings, process)
        second = msa.guard_gauge("good", gauge, 0.1, other, process)
        for section in ("development", "selection"):
            self.assertEqual([row for row in first if row["section"] == section],
                             [row for row in second if row["section"] == section])
        self.assertNotEqual([row for row in first if row["section"] == "holdout"],
                            [row for row in second if row["section"] == "holdout"])

    def test_p12_original_test_bodies_and_committed_artifacts_unchanged(self):
        paths = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", BASE, "tests"], cwd=ROOT).decode().splitlines()
        count = 0
        for name in paths:
            if not name.endswith(".py"):
                continue
            old = subprocess.check_output(["git", "show", BASE + ":" + name], cwd=ROOT).decode("utf-8-sig")
            current = (ROOT / name).read_text(encoding="utf-8-sig")
            def bodies(text):
                tree = ast.parse(text)
                return {node.name: ast.dump(node, include_attributes=False) for node in ast.walk(tree)
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")}
            before, after = bodies(old), bodies(current)
            for key, value in before.items():
                self.assertEqual(after.get(key), value, name + ":" + key)
                count += 1
        artifacts = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", BASE, "reports", "recipes", "data"], cwd=ROOT).decode().splitlines()
        for name in artifacts:
            # Existing files mix LF/CRLF; compare Git's normalized object hashes.
            old = subprocess.check_output(["git", "rev-parse", BASE + ":" + name], cwd=ROOT).strip()
            current = subprocess.check_output(["git", "hash-object", name], cwd=ROOT, stderr=subprocess.PIPE).strip()
            self.assertEqual(current, old, name)
        print("P12 original_test_bodies=%d git_unchanged_artifacts=%d" % (count, len(artifacts)), flush=True)

    def test_p13_regenerate_affected_reports_and_new_msa_reports(self):
        cases = [
            ("src.line", (ROOT / "recipes/line_lamp.json", "--seeds", "0-29", "--holdout-seeds", "1000-1029", "--products", "500")),
            ("src.station", (ROOT / "recipes/plc_station.json", "--scenario", "all")),
            ("src.anomaly", (ROOT / "recipes/anomaly_lamp.json",)),
            ("src.msa", (ROOT / "recipes/msa_lamp.json",)),
        ]
        for module, arguments in cases:
            with self.subTest(module=module), tempfile.TemporaryDirectory() as folder:
                result = cli(module, *arguments, cwd=folder)
                self.assertEqual(result.returncode, 0, result.stderr)
                reports = sorted((Path(folder) / "reports").iterdir())
                self.assertTrue(reports)
                for path in reports:
                    self.assertEqual(path.read_bytes(), (ROOT / "reports" / path.name).read_bytes(), path.name)
                print("P13 %s regenerated_equal=%d" % (module, len(reports)), flush=True)

    def test_p14_observed_cpk_with_nonzero_subsquare_sigma(self):
        # Both inputs are nonzero finite numbers; squaring underflows to zero.
        cpk = 1e200
        sigma = 6 / (6 * cpk)  # The valid generator used in P09, limits 7..13.
        self.assertEqual(msa.observed_cpk(cpk, sigma, 0.0), cpk)


if __name__ == "__main__":
    unittest.main()

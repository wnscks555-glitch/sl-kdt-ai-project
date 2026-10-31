"""Review 022 probes. Only temporary directories receive generated product reports."""

import ast
import csv
from decimal import Decimal, localcontext
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock

from src import anomaly, incident, spc
from src.modbus import PC_STOP_COIL
from src.plc import ALARM, CLAMP, PUBLISH
from tests.test_incident import STATION, flow_of, write_config
from tests.test_plc import Rig
from tests.test_spc import prepare, UNIT_LIMITS


ROOT = Path(__file__).resolve().parents[3]
BASE = "401f45ae19b53e44cecf9f187868dbc162b04faa"
ENV = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")


def cli(module, config, folder, *args):
    return subprocess.run([sys.executable, "-B", "-m", module, str(config), *args], cwd=folder,
                          env=ENV, capture_output=True, text=True, encoding="utf-8")


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        return reader.fieldnames, list(reader)


def write_csv(path, columns, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


class Probe022(unittest.TestCase):
    def test_p01_ewma_smaller_lambda_and_endpoints(self):
        observed = []
        for weight in (1e-20, 1e-200, 5e-324, 1.0):
            with tempfile.TemporaryDirectory() as folder:
                data = json.loads((ROOT / "recipes/spc_lamp.json").read_text(encoding="utf-8"))
                data["ewma_lambda"] = weight
                config = Path(folder) / "spc.json"
                config.write_text(json.dumps(data), encoding="utf-8")
                self.assertEqual(spc.load_settings(config).tuning.ewma_lambda, weight)
            chart = spc.Ewma(UNIT_LIMITS, spc.Tuning(weight, 3, .5, 5))
            with localcontext() as context:
                context.prec = 750
                w = Decimal.from_float(weight)
                value, expected_alarm = Decimal(0), None
                actual_alarm = None
                for t in range(12):
                    value = w * Decimal.from_float(.1) + (1 - w) * value
                    limit = 3 * (w / (2 - w) * (1 - (1 - w) ** (2 * (t + 1)))).sqrt()
                    if t >= 9 and abs(value) > limit and expected_alarm is None:
                        expected_alarm = t
                    hit = chart.update(.1)
                    if t >= 9 and hit and actual_alarm is None:
                        actual_alarm = t
            observed.append((weight, actual_alarm, expected_alarm, chart.limit, float(limit)))
        print("P01 weight/alarm/expected/limit/expected_limit:", observed, flush=True)
        self.assertTrue(all(actual == expected and limit > 0
                            for _, actual, expected, limit, _ in observed), observed)

    def test_p02_reference_and_model_duplicate_orders_then_valid(self):
        columns, rows = read_csv(ROOT / "reports/anomaly_lamp_methods.csv")
        target = next(row for row in rows if row["section"] == "validation" and row["method"] == "rule_3_2")
        base = anomaly.load_settings(ROOT / "recipes/anomaly_lamp.json")
        outcomes = []
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "methods.csv"
            for first in (True, False):
                bad = dict(target, mean_delay_cost="999.0000")
                sequence = ([bad] + rows) if first else (rows + [bad])
                write_csv(path, columns, sequence)
                with self.assertRaises(ValueError):
                    spc.load_reference(path)
                outcomes.append("refused")
            write_csv(path, columns, rows)
            self.assertTrue(spc.load_reference(path))
            columns, rows = read_csv(ROOT / "reports/anomaly_lamp_model.csv")
            target = next(row for row in rows if row["section"] == "setting" and row["name"] == "window")
            for duplicate in (dict(target), dict(target, value="11")):
                write_csv(path, columns, rows + [duplicate])
                with self.assertRaises(ValueError):
                    spc.check_model(path, base)
                outcomes.append("refused")
            write_csv(path, columns, rows)
            spc.check_model(path, base)
        print("P02 duplicate orders/model identical+conflicting:", outcomes, "; subsequent valid accepted", flush=True)

    def test_p03_changed_measurements_with_identical_rule_metrics(self):
        with tempfile.TemporaryDirectory() as folder:
            generator = json.loads((ROOT / "recipes/generator_measured.json").read_text(encoding="utf-8"))
            generator.update(defective_product_probability=0, process_cpk=5)
            for key in ("recipe", "equipment"):
                if key in generator and isinstance(generator[key], str):
                    generator[key] = str(ROOT / "recipes" / generator[key])
            source = Path(folder) / "generator.json"
            source.write_text(json.dumps(generator), encoding="utf-8")
            config = prepare(folder, generator=str(source))
            base = anomaly.load_settings(Path(folder) / "anomaly.json")
            old = anomaly.build_split(base.splits["validation"], base, anomaly.load_process(base))
            generator["process_cpk"] = 6
            source.write_text(json.dumps(generator), encoding="utf-8")
            new = anomaly.build_split(base.splits["validation"], base, anomaly.load_process(base))
            self.assertNotEqual([x.values for x in old], [x.values for x in new])
            self.assertEqual(anomaly.rule_outcomes(old, base), anomaly.rule_outcomes(new, base))
            result = cli("src.spc", config, folder)
            print("P03 changed values/same rule: exit=", result.returncode, result.stderr.strip(), flush=True)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertFalse((Path(folder) / "reports/spc_methods.csv").exists())

    def test_p04_replay_out_of_range_is_controlled_refusal(self):
        with tempfile.TemporaryDirectory() as folder:
            config = prepare(folder)
            path = Path(folder) / "reports/anomaly_replay.csv"
            columns, rows = read_csv(path)
            rows[0]["t"] = "120"
            write_csv(path, columns, rows)
            result = cli("src.spc", config, folder)
            print("P04 out-of-range replay: exit=", result.returncode, result.stderr.strip(), flush=True)
            self.assertFalse((Path(folder) / "reports/spc_methods.csv").exists())
            self.assertEqual(result.returncode, 2, result.stderr)

    def test_p05_incident_conflicting_limits_either_order(self):
        config = spc.load_settings(ROOT / "recipes/spc_lamp.json")
        base = anomaly.load_settings(config.anomaly)
        process = anomaly.load_process(base)
        columns, rows = read_csv(ROOT / "reports/spc_lamp_methods.csv")
        target = next(row for row in rows if row["section"] == "limits" and row["name"] == "sigma_hat")
        outcomes = []
        with tempfile.TemporaryDirectory() as folder:
            for first in (True, False):
                path = Path(folder) / "limits.csv"
                bad = dict(target, value="999.0")
                write_csv(path, columns, ([bad] + rows) if first else (rows + [bad]))
                settings = incident.load_settings(write_config(folder, spc_report=str(path)))
                try:
                    incident.checked_limits(settings, config, base, process)
                except ValueError:
                    outcomes.append("refused")
                else:
                    outcomes.append("accepted")
        print("P05 contradictory limits bad-first/bad-last:", outcomes, flush=True)
        self.assertEqual(outcomes, ["refused", "refused"])

    def test_p06_measure_id_rollover_within_allowed_products(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = incident.load_settings(write_config(folder, products=65536, onset_product=65536))
            self.assertEqual(settings.products, 65536)
        flow = flow_of(set(), products=65536, onset=65535)
        rig = Rig()
        rig.plc.measure_id = 65534
        plant = Mock(product=65534)
        client = Mock()
        pc = incident.StoryPc(client, plant, flow, 1, [])
        outcomes = []
        for product in (65534, 65535):
            plant.product = product
            rig.plc.state, rig.plc.value = PUBLISH, "10.000"
            rig.plc._publish()
            rig.plc._write()
            try:
                pc._judge(rig.table.input_registers)
            except ValueError as error:
                outcomes.append((product, rig.plc.measure_id, str(error)))
            else:
                outcomes.append((product, rig.plc.measure_id, "accepted"))
        print("P06 product/measurement-ID/result:", outcomes, flush=True)
        self.assertEqual([x[2] for x in outcomes], ["accepted", "accepted"], outcomes)

    def test_p07_repeated_early_true_repair_and_last_stop_socket(self):
        products, onset, stops = 14, 5, {0, 1, 5, 6, 13}
        live = flow_of(stops, products=products, onset=onset)
        story = incident.run_story(STATION, live, products, 1, 2000)
        memory = incident.run_memory(flow_of(stops, products=products, onset=onset), products)
        self.assertEqual(live.values, memory.values)
        self.assertEqual(live.disposition, memory.disposition)
        self.assertEqual([stop.product for stop in live.stops], sorted(stops))
        self.assertEqual(live.values[4], live.fault[4])
        self.assertEqual(live.values[6], live.normal[6])
        self.assertEqual(story.ok_count + story.ng_count + live.count("aborted"), products)
        self.assertEqual([event["event"] for event in story.events][-2:], ["restart", "finish"])
        self.assertEqual(incident.true_stop(live.stops, onset).number, 3)
        print("P07 early x2, true stop, post-repair x2 including final product: socket=memory; counts=14", flush=True)

    def test_p08_pc_stop_priority_and_alarm_code_retention(self):
        outcomes = []
        for signals, expected in (({"guard_closed": False}, 22),
                                  ({"clamp_open": True, "clamp_closed": True}, 24),
                                  ({"measure_done": True}, 25)):
            rig = Rig()
            rig.reach(CLAMP)
            rig.table.coils[PC_STOP_COIL] = True
            rig.set(**signals)
            rig.scan()
            self.assertEqual(rig.plc.alarm, expected)
            rig.table.coils[PC_STOP_COIL] = False
            rig.scan()
            self.assertEqual(rig.plc.alarm, expected)
            self.assertEqual(rig.plc.state, ALARM)
            outcomes.append(expected)
        print("P08 simultaneous alarm priority then stop-clear retains codes:", outcomes, flush=True)

    def test_p09_malformed_lists_then_valid_single_product(self):
        with tempfile.TemporaryDirectory() as folder:
            for changes in ({"methods": [[]]}, {"scopes": [None]}, {"pfmea_links": [False]},
                            {"methods": ["CUSUM"]}, {"methods": ["cusum", "cusum"]}):
                result = cli("src.incident", write_config(folder, **changes), folder)
                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertFalse((Path(folder) / "reports").exists())
            result = cli("src.incident", write_config(folder, products=1, onset_product=1,
                                                      repair_cycles=1, methods=["rule_3_2"], scopes=["last_20"]), folder)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(list((Path(folder) / "reports").iterdir())), 5)
        print("P09 five malformed list/case/duplicate inputs refused; next single-product CLI succeeds", flush=True)

    def test_p10_preserved_test_bodies_and_artifact_contents(self):
        def methods(source):
            tree = ast.parse(source)
            return {(node.name, item.name): ast.dump(item, include_attributes=False)
                    for node in tree.body if isinstance(node, ast.ClassDef)
                    for item in node.body if isinstance(item, ast.FunctionDef) and item.name.startswith("test_")}
        changed, total = [], 0
        test_paths = git("ls-tree", "-r", "--name-only", BASE, "tests").decode().splitlines()
        for name in test_paths:
            if not name.endswith(".py"):
                continue
            old, new = methods(git("show", BASE + ":" + name).decode("utf-8-sig")), methods((ROOT / name).read_text(encoding="utf-8-sig"))
            for key, body in old.items():
                total += 1
                if new.get(key) != body:
                    changed.append((name, *key))
        allowed = [("tests/test_spc.py", "ReportTests", "test_section_sizes"),
                   ("tests/test_spc.py", "ReportTests", "test_t255_provenance")]
        self.assertEqual(changed, allowed)
        changed14 = git("diff", "--name-only", "94d8ab4..HEAD", "tests").decode().splitlines()
        self.assertEqual(changed14, ["tests/test_incident.py"])
        artifacts = git("ls-tree", "-r", "--name-only", BASE, "recipes", "reports", "data").decode().splitlines()
        differences = [name for name in artifacts if git("show", BASE + ":" + name) != git("show", "HEAD:" + name)]
        self.assertEqual(differences, ["recipes/spc_lamp.json", "reports/spc_lamp_methods.csv"])
        print("P10 existing_tests=", total, "changed_bodies=", changed,
              "artifacts=", len(artifacts), "documented_SPC_differences=", differences, flush=True)

    def test_p11_station_and_default_incident_reports_raw_bytes(self):
        watched = [path for directory in ("reports", "recipes", "data") for path in (ROOT / directory).rglob("*") if path.is_file()]
        before = {path: path.read_bytes() for path in watched}
        for module, config, args, count in (("src.station", "plc_station.json", ("--scenario", "all"), 16),
                                            ("src.incident", "incident_lamp.json", (), 5)):
            with tempfile.TemporaryDirectory() as folder:
                result = cli(module, ROOT / "recipes" / config, folder, *args)
                self.assertEqual(result.returncode, 0, result.stderr)
                produced = list((Path(folder) / "reports").iterdir())
                self.assertEqual(len(produced), count)
                for path in produced:
                    self.assertEqual(path.read_bytes(), (ROOT / "reports" / path.name).read_bytes(), path.name)
                print("P11", module, "stored raw bytes equal:", count, flush=True)
        self.assertEqual(before, {path: path.read_bytes() for path in watched})
        print("P11 all existing reports/config/data raw bytes unchanged by execution:", len(watched), flush=True)


if __name__ == "__main__":
    unittest.main()

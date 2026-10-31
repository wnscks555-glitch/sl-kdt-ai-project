"""Review 018: independent diff-focused probes; all generated files use tempfile.

Run: py -m unittest handoff/reviews/probes/test_probe_018.py
No earlier probe or existing test module is imported/executed.
Assertions retain the required behavior when a defect is found.
"""
import ast
import copy
import csv
from dataclasses import replace
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import random
import struct
import subprocess
import sys
import tempfile
import unittest

from src import anomaly as a
from src.generate import Generator, load_setup
from src.modbus import ModbusServer, Table, RELEASE_COIL, RESET_COIL
from src.plc import ALARM, IDLE, INPUTS, WAIT_JUDGE, Plc, Timing
from src.station import load_station, load_values

ROOT = Path(__file__).resolve().parents[3]
BASE = '63af1957fe73225c1cf8cb8ab4fe8051a6e4e3c9'
RAW = json.loads((ROOT / 'recipes/anomaly_lamp.json').read_text(encoding='utf-8'))
SETTINGS = a.load_settings(ROOT / 'recipes/anomaly_lamp.json')
PROCESS = a.load_process(SETTINGS)


def git(*args, binary=False):
    return subprocess.check_output(['git', *args], cwd=ROOT,
                                   **({} if binary else {'text': True, 'encoding': 'utf-8'}))


def config(folder, **changes):
    data = copy.deepcopy(RAW)
    data.update(generator=str(ROOT / 'recipes/generator_measured.json'), length=35,
                window=4, onset_min=10, onset_max=20, iterations=4,
                splits={name: {'seed_start': start, 'count': 6}
                        for name, start in zip(a.SPLITS, (0, 100, 200))})
    data.update(changes)
    path = Path(folder) / 'anomaly.json'
    path.write_text(json.dumps(data), encoding='utf-8')
    return path


def cli(folder, module, *args):
    return subprocess.run([sys.executable, '-m', module, *map(str, args)], cwd=folder,
                          env={**os.environ, 'PYTHONPATH': str(ROOT),
                               'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONIOENCODING': 'utf-8'},
                          capture_output=True, text=True, encoding='utf-8', timeout=90)


def packet(tid, value, protocol=0):
    return struct.pack('>HHHBBHH', tid, protocol, 6, 1, 6, 0, value)


class Connection:
    def __init__(self, chunks):
        self.chunks, self.replies = iter(chunks), []

    def recv(self, size):
        return next(self.chunks, b'')

    def sendall(self, value):
        self.replies.append(value)


class DiffProbes(unittest.TestCase):
    maxDiff = 1400

    def test_p01_reset_rejected_then_valid_then_new_publish(self):
        table = Table()
        plc = Plc(table, Timing(10, dict(check_scans=30, clamp_scans=20, measure_scans=50,
                                        judge_scans=30, unclamp_scans=20, discharge_scans=30)))

        def scan(value='', **signals):
            for name, signal in signals.items():
                table.discrete[INPUTS.index(name)] = signal
            table.holding[0] = (table.holding[0] + 1) % 65536
            return plc.scan(value)

        scan(clamp_open=True, guard_closed=True, part_present=True)
        scan(seated=True, direction_ok=True)
        scan(clamp_open=False, clamp_closed=True)
        scan('-1.250', measure_done=True)
        scan(measure_done=False)
        self.assertEqual(plc.state, WAIT_JUDGE)
        old = list(table.input_registers[3:5])
        scan(guard_closed=False)
        table.coils[RESET_COIL] = True
        scan(guard_closed=True)
        self.assertEqual(plc.state, ALARM)
        self.assertEqual(table.input_registers[3:5], old)
        table.coils[RESET_COIL] = False
        table.coils[RELEASE_COIL] = True
        scan()
        scan(clamp_closed=False, clamp_open=True, part_present=False, seated=False, direction_ok=False)
        table.coils[RESET_COIL] = True
        scan()
        self.assertEqual((plc.state, plc.measure_id, plc.processed), (IDLE, 1, 0))
        self.assertEqual(table.input_registers[3:5], [0, 0])
        self.assertEqual((table.coils[RESET_COIL], table.coils[RELEASE_COIL]), (True, True))
        scan(part_present=True)
        scan(seated=True, direction_ok=True)
        scan(clamp_open=False, clamp_closed=True)
        scan('2.500', measure_done=True)
        scan(measure_done=False)
        self.assertEqual((plc.state, plc.measure_id, table.input_registers[3:5]), (WAIT_JUDGE, 2, [0, 2500]))
        print('P01: rejected reset preserves words; accepted reset clears words, keeps ID/count/coils; next ID=2')

    def test_p02_valid_prefix_all_byte_splits_and_bad_suffix(self):
        good = packet(1, 7) + packet(2, 9)
        stream = good + packet(3, 99, protocol=1) + packet(4, 88)
        results = []
        for cut in range(1, len(stream)):
            table = Table()
            # Bind only the table used by the actual server loop; no listener or thread is needed.
            server = type('Server', (), {'table': table})()
            connection = Connection((stream[:cut], stream[cut:]))
            ModbusServer._serve(server, connection)
            results.append((table.holding[0], len(connection.replies)))
            self.assertEqual(b''.join(connection.replies), good)
        self.assertEqual(set(results), {(9, 2)})
        print('P02: all %d two-chunk splits preserve both valid writes; no post-damage write' % len(results))

    def test_p03_actual_generator_order_past_9999(self):
        station = load_station(ROOT / 'recipes/plc_station.json')
        setup, _, recipe, book = load_setup(station.generator)
        first = {}
        for row in Generator(0, setup, recipe.models, book).normal_events(10001):
            if row['event'] == 'INSPECT' and row['inspection'] == station.inspection:
                first.setdefault(row['product_id'], row['value'])
        expected = [first['GEN_' + str(number).zfill(4)] for number in range(1, 10002)]
        actual, _ = load_values(station, 0, 10001)
        self.assertEqual(actual, expected)
        print('P03: all 10001 first measurements retain numeric product identity')

    def test_p04_nested_wrong_types_rejected_then_valid(self):
        cases = [dict(shifts=[1, True]), dict(shifts=[1, 1.0]), dict(shifts=[None]),
                 dict(splits=[]), dict(splits={name: None for name in a.SPLITS}),
                 dict(inspection=''), dict(ewma_lambda=False), dict(min_detection=float('inf'))]
        for changes in cases:
            with tempfile.TemporaryDirectory() as folder:
                result = cli(folder, 'src.anomaly', config(folder, **changes))
                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertNotIn('Traceback', result.stderr)
                self.assertFalse((Path(folder) / 'reports').exists())
                valid = cli(folder, 'src.anomaly', config(folder))
                self.assertEqual(valid.returncode, 0, valid.stderr)
        print('P04: 8 nested/type/bool/duplicate errors exit 3; each following valid run succeeds')

    def test_p05_huge_out_of_range_integer_is_config_error(self):
        with tempfile.TemporaryDirectory() as folder:
            result = cli(folder, 'src.anomaly', config(folder, min_detection=10 ** 400))
            print('P05: min_detection=10**400: exit=%s; overflow=%s' %
                  (result.returncode, 'OverflowError' in result.stderr))
            self.assertFalse((Path(folder) / 'reports').exists())
            self.assertEqual(result.returncode, 3, result.stderr)
            self.assertNotIn('Traceback', result.stderr)

    def test_p06_generator_other_rule_does_not_relabel_baseline(self):
        with tempfile.TemporaryDirectory() as folder:
            generator = json.loads((ROOT / 'recipes/generator_measured.json').read_text(encoding='utf-8'))
            book = json.loads((ROOT / 'recipes/equipment_measured.json').read_text(encoding='utf-8'))
            book['stop_rule'] = {'window': 5, 'fails': 3}
            equipment = Path(folder) / 'equipment.json'
            equipment.write_text(json.dumps(book), encoding='utf-8')
            generator['equipment'] = str(equipment)
            generator['recipe'] = str(ROOT / 'recipes/lamp_models_measured.json')
            genpath = Path(folder) / 'generator.json'
            genpath.write_text(json.dumps(generator), encoding='utf-8')
            settings = a.load_settings(config(folder, generator=str(genpath)))
            process = a.load_process(settings)
            fails = [False] * 9 + [True, True] + [False] * 24
            scenario = a.Scenario(1, 1.0, 10, [], fails, [], [])
            actual = a.rule_outcomes([scenario], process, settings)[0][2]
            expected = a.first_rule_alarm(fails, 3, 2, settings.window - 1)
            print('P06: generator=5:3, method=rule_3_2; actual alarm=%r expected=%r' % (actual, expected))
            self.assertEqual(actual, expected, 'The named 3:2 method must not silently become 5:3')

    def test_p07_near_onset_early_replay_spec_disagreement(self):
        settings = replace(SETTINGS, window=2, length=30)
        features = [(0.0,) * 6] * 29
        features[18] = (1.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        scenario = a.Scenario(2001, 1.0, 20, ['10.000'] * 30, [False] * 30, [0.0] * 30, features)
        model = a.Model([0.0] * 6, [1.0] * 6, [10.0] + [0.0] * 5, -5.0, 0.0, 1, 1)
        rows = a.replay_rows(scenario, model, 5000, settings)
        print('P07: onset=20 first alarm=19; early replay t=%r; formula says 15..19, prose says one row' %
              [row['t'] for row in rows])
        self.assertEqual({row['status'] for row in rows}, {'early'})
        self.assertEqual([row['t'] for row in rows], [19], 'Spec prose says an early alarm leaves one row')

    def test_p08_peak_search_matches_exhaustive_edge_grids(self):
        settings = replace(SETTINGS, length=8, window=2, false_limit=1000,
                           min_detection=0, min_shift_detection=0)
        rng = random.Random(18)
        for trial in range(60):
            traces = [a.trace_of(a.Scenario(i, i % 2, 4 if i % 2 else None, [], [], [], []),
                                 [rng.randint(-4, 4) for _ in range(7)], 2) for i in range(8)]
            fast, count = a.choose_threshold(traces, settings)
            values = sorted(set().union(*(trace.values for trace in traces)))
            slow = a.select_threshold([(h, a.measure_alarms(
                [(trace.shift, trace.onset, trace.first_alarm(h)) for trace in traces], 8, 2))
                for h in values + [max(values) + 1]], settings)
            self.assertEqual(count, len(values) + 1)
            self.assertEqual(fast, slow)
        print('P08: 60 negative/duplicate/tie score grids match exhaustive candidate evaluation')

    def test_p09_two_shifts_boundary_labels_no_selection(self):
        with tempfile.TemporaryDirectory() as folder:
            path = config(folder, length=6, window=2, onset_min=2, onset_max=2,
                          shifts=[0.5, 2.0], splits={name: {'seed_start': start, 'count': 4}
                                                  for name, start in zip(a.SPLITS, (0, 4, 8))})
            settings = a.load_settings(path)
            splits = {name: a.build_split(seeds, settings, PROCESS) for name, seeds in settings.splits.items()}
            self.assertEqual([s.shift for s in splits['train']], [0, 0.5, 0, 2.0])
            _, labels = a.training_rows(splits['train'], 2)
            self.assertEqual(sum(labels), 8)
            model = a.fit_model(splits['train'], settings)
            # Force every method to fail validation while keeping comparison/reporting paths real.
            impossible = replace(settings, false_limit=1e-12, min_detection=1.0, min_shift_detection=1.0)
            for name in ('validation', 'holdout'):
                for scenario in splits[name]:
                    scenario.features = [(0.0,) * 6] * 5
                    scenario.fails = [False] * 6
            rows, selected, outcome, threshold, _ = a.compare(splits, model, PROCESS, impossible)
            self.assertIsNone(selected)
            self.assertEqual(outcome, a.NO_SELECTION)
            self.assertIsNone(threshold)
            blank = [row for row in rows if row['value'] == a.NO_THRESHOLD]
            self.assertEqual(len(blank), 4)
            self.assertTrue(all(row['detection_rate'] == '' for row in blank))
        print('P09: 2 shifts and touching seed ranges accepted; boundary labels correct; no method is reselected')

    def test_p10_integrated_validation_change_cannot_retrain(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = a.load_settings(config(folder))
            splits = {name: a.build_split(seeds, settings, PROCESS) for name, seeds in settings.splits.items()}
            first = a.fit_model(splits['train'], settings)
            first_rows = a.compare(splits, first, PROCESS, settings)[0]
            for scenario in splits['validation']:
                scenario.features = [tuple(value + 100 for value in row) for row in scenario.features]
            second = a.fit_model(splits['train'], settings)
            second_rows = a.compare(splits, second, PROCESS, settings)[0]
            self.assertEqual(first, second)
            self.assertNotEqual(first_rows, second_rows)
        print('P10: changed validation is actually consumed by compare; model and training standardizer unchanged')

    def test_p11_protected_predecessor_files_and_original_assertions(self):
        paths = git('ls-tree', '-r', '--name-only', BASE, '--', 'src', 'tests', 'recipes', 'data', 'reports').splitlines()
        allowed = {'src/modbus.py', 'src/plc.py', 'src/station.py',
                   'tests/test_modbus.py', 'tests/test_plc.py', 'tests/test_station.py'}
        equal = 0
        for path in paths:
            if path not in allowed:
                self.assertEqual(git('show', BASE + ':' + path, binary=True),
                                 git('show', 'HEAD:' + path, binary=True), path)
                equal += 1
        # All stage-11 predecessor files are unchanged after the review-017 fix commit.
        self.assertEqual(git('diff', '--name-only', 'a70f499..HEAD', '--', *paths).strip(), '')
        for path in ('tests/test_modbus.py', 'tests/test_station.py', 'tests/test_plc.py'):
            old_tree = ast.parse(git('show', BASE + ':' + path))
            new_tree = ast.parse((ROOT / path).read_text(encoding='utf-8'))
            old_classes = {node.name: node for node in old_tree.body if isinstance(node, ast.ClassDef)}
            new_classes = {node.name: node for node in new_tree.body if isinstance(node, ast.ClassDef)}
            for cname, klass in old_classes.items():
                new_methods = {node.name: node for node in new_classes[cname].body if isinstance(node, ast.FunctionDef)}
                for method in (node for node in klass.body if isinstance(node, ast.FunctionDef)):
                    name = method.name
                    if name == 'test_t158_measure_id_is_kept':
                        replacement = new_methods['test_t158_measure_id_is_kept_and_published_value_is_cleared']
                        old_assertions = [ast.dump(n) for n in ast.walk(method) if isinstance(n, ast.Call)
                                          and isinstance(n.func, ast.Attribute) and n.func.attr.startswith('assert')]
                        new_assertions = [ast.dump(n) for n in ast.walk(replacement) if isinstance(n, ast.Call)
                                          and isinstance(n.func, ast.Attribute) and n.func.attr.startswith('assert')]
                        self.assertTrue(all(value in new_assertions for value in old_assertions))
                    else:
                        self.assertEqual(ast.dump(method), ast.dump(new_methods[name]), path + ':' + name)
        print('P11: %d old protected blobs identical; all %d predecessor paths unchanged by stage 11; old test assertions retained' %
              (equal, len(paths)))

    def test_p12_stage10_all_reports_replay_identically(self):
        with tempfile.TemporaryDirectory() as folder:
            result = cli(folder, 'src.station', ROOT / 'recipes/plc_station.json', '--scenario', 'all')
            self.assertEqual(result.returncode, 0, result.stderr)
            paths = sorted((Path(folder) / 'reports').glob('*.csv'))
            self.assertEqual(len(paths), 16)
            for path in paths:
                self.assertEqual(path.read_bytes(), (ROOT / 'reports' / path.name).read_bytes(), path.name)
        print('P12: all 8 actual-socket station scenarios reproduce all 16 submitted reports byte-for-byte')

    def test_p13_small_run_repeatability_and_existing_file_hashes(self):
        paths = [ROOT / path for path in git('ls-tree', '-r', '--name-only', 'HEAD', '--', 'recipes', 'data', 'reports').splitlines()]
        before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
        outputs = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as folder:
                result = cli(folder, 'src.anomaly', config(folder))
                self.assertEqual(result.returncode, 0, result.stderr)
                written = sorted((Path(folder) / 'reports').glob('*'))
                self.assertEqual(len(written), 3)
                outputs.append([path.read_bytes() for path in written])
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(before, {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths})
        print('P13: small runs repeat all 3 reports byte-for-byte; %d existing files retain SHA-256' % len(paths))

    def test_p14_default_artifacts_recomputed_with_submitted_coefficients(self):
        with (ROOT / 'reports/anomaly_lamp_model.csv').open(encoding='utf-8-sig', newline='') as source:
            saved = {(r['section'], r['name']): r['value'] for r in csv.DictReader(source)}
        vector = lambda section: [float(saved[section, name]) for name in a.FEATURES]
        model = a.Model(vector('mean'), vector('scale'), vector('weight'), float(saved['bias', 'bias']),
                        float(saved['fit', 'gradient_norm']), int(saved['windows', 'positive']),
                        int(saved['windows', 'negative']))
        splits = {name: a.build_split(seeds, SETTINGS, PROCESS) for name, seeds in SETTINGS.splits.items()}
        train, labels = a.training_rows(splits['train'], SETTINGS.window)
        self.assertEqual(a.standardizer(train), (model.means, model.scales))
        self.assertEqual((sum(labels), len(labels) - sum(labels)), (model.positive, model.negative))
        scaled = [a.standardize(row, model.means, model.scales) for row in train]
        gradient, bias = a._gradient(list(zip(*scaled)), labels, model.weights, model.bias, SETTINGS.l2)
        self.assertAlmostEqual(math.hypot(*gradient, bias), model.norm, places=12)
        rows, selected, outcome, threshold, counts = a.compare(splits, model, PROCESS, SETTINGS)
        replay = a.replay_rows(splits['holdout'][1], model, threshold, SETTINGS)
        with tempfile.TemporaryDirectory() as folder:
            for suffix, columns, content in [('methods', a.METHOD_COLUMNS, rows),
                                              ('model', a.MODEL_COLUMNS, a.model_rows(SETTINGS, model, threshold, counts)),
                                              ('replay', a.REPLAY_COLUMNS, replay)]:
                path = Path(folder) / (suffix + '.csv')
                a._write_csv(path, columns, content)
                self.assertEqual(path.read_bytes(), (ROOT / 'reports' / ('anomaly_lamp_' + suffix + '.csv')).read_bytes())
        self.assertEqual((selected, outcome, threshold), ('logistic', '확인', 9675))
        print('P14: default 780 scenarios, training scaling/labels/final gradient and all 3 artifacts verified with saved coefficients; optimization not rerun')


if __name__ == '__main__':
    unittest.main()

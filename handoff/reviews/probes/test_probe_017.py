"""Review 017: diff-focused independent probes; only temporary output folders.

Run: py -m unittest handoff/reviews/probes/test_probe_017.py
No prior probe module or existing test suite is imported or executed.
Confirmed defects retain failing assertions of the specified behavior.
"""
import ast
import copy
from dataclasses import replace
from fractions import Fraction
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

from src.generate import Generator, generate, load_setup
from src.line import (
    LineError, Route, _seconds, compare, load_line, optimal_balance, product_routes,
)
from src.modbus import (
    ModbusServer, Table, ValueConversionError, handle_pdu, restore_value, to_words,
)
from src.plc import (
    ALARM, CHECK, CLAMP, IDLE, INPUTS, MEASURE, OUTPUTS, PUBLISH, UNCLAMP, WAIT_JUDGE, Plc, Timing,
)
from src.station import load_station, load_values


ROOT = Path(__file__).resolve().parents[3]
BASE = '18f3244e586c66efb060a200748ebf33f401b104'
STAGE10_BASE = '64c6d1e'
CONFIG = ROOT / 'recipes/generator_measured.json'
LINE_FILE = ROOT / 'recipes/line_lamp.json'
STATION_FILE = ROOT / 'recipes/plc_station.json'
RAW_LINE = json.loads(LINE_FILE.read_text(encoding='utf-8-sig'))
SETUP, _, RECIPE, BOOK = load_setup(CONFIG)
LINE = load_line(LINE_FILE, RECIPE.models)
TIMEOUTS = dict(check_scans=30, clamp_scans=20, measure_scans=50,
                judge_scans=30, unclamp_scans=20, discharge_scans=30)


def cli(folder, module, *args):
    return subprocess.run(
        [sys.executable, '-m', module, *map(str, args)], cwd=folder,
        env={**os.environ, 'PYTHONPATH': str(ROOT), 'PYTHONIOENCODING': 'utf-8',
             'PYTHONDONTWRITEBYTECODE': '1'},
        capture_output=True, text=True, encoding='utf-8', timeout=300)


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True, encoding='utf-8')


def frame(transaction, pdu, protocol=0, unit=1):
    return struct.pack('>HHHB', transaction, protocol, len(pdu) + 1, unit) + pdu


class Rig:
    def __init__(self):
        self.table = Table()
        self.plc = Plc(self.table, Timing(10, dict(TIMEOUTS)))
        self.set(clamp_open=True, guard_closed=True)

    def set(self, **signals):
        with self.table.lock:
            for key, value in signals.items():
                self.table.discrete[INPUTS.index(key)] = value

    def scan(self, value='', beat=True, hook=None):
        if beat:
            self.table.holding[0] = (self.table.holding[0] + 1) % 65536
        return self.plc.scan(value, after_snapshot=hook)

    def reach_wait(self):
        for signals, value in [
            (dict(part_present=True), ''),
            (dict(seated=True, direction_ok=True), ''),
            (dict(clamp_closed=True, clamp_open=False), ''),
            (dict(measure_done=True), '10.250'),
            (dict(measure_done=False), ''),
        ]:
            self.set(**signals)
            self.scan(value)
        assert self.plc.state == WAIT_JUDGE


class ChunkConnection:
    """A deterministic socket boundary: same byte stream, controlled recv chunks."""
    def __init__(self, chunks):
        self.chunks = iter(chunks)
        self.replies = []

    def recv(self, size):
        return next(self.chunks, b'')

    def sendall(self, data):
        self.replies.append(data)


class DiffProbes(unittest.TestCase):
    maxDiff = 1200

    def success(self, result):
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_p01_r16_h1_structure_errors_and_following_valid_input(self):
        variants = [[], None, {}, dict(RAW_LINE, generator=1), dict(RAW_LINE, generator=' ')]
        for step in ([], {}, None, True):
            bad = copy.deepcopy(RAW_LINE)
            bad['generator'] = str(CONFIG)
            bad['elements'][0]['step'] = step
            variants.append(bad)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'input.json'
            for index, data in enumerate(variants):
                with self.subTest(index=index):
                    path.write_text(json.dumps(data), encoding='utf-8')
                    result = cli(folder, 'src.line', path, '--seeds', '0-0', '--holdout-seeds', '1-1', '--products', 2)
                    self.assertEqual(result.returncode, 3, result.stderr)
                    self.assertIn('$', result.stderr)
                    self.assertNotIn('Traceback', result.stderr)
                    self.assertFalse((Path(folder) / 'reports').exists())
            self.success(cli(folder, 'src.line', LINE_FILE, '--seeds', '0-0', '--holdout-seeds', '1-1', '--products', 2))
        print('P01: 9 malformed variants exit 3; no reports; next valid run succeeds', flush=True)

    def test_p02_r16_m1_duplicate_edge_rejected_then_original_balances(self):
        bad = copy.deepcopy(RAW_LINE)
        bad['elements'][1]['predecessors'] = ['P1-1', 'P1-1']
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'line.json'
            path.write_text(json.dumps(bad), encoding='utf-8')
            with self.assertRaisesRegex(LineError, 'predecessors.*중복'):
                load_line(path, RECIPE.models)
        best = optimal_balance(LINE.elements, {'A': Fraction(1, 2), 'B': Fraction(1, 2)}, LINE.net, LINE.demand)
        self.assertIsNotNone(best)
        self.assertEqual(len(best.stations), 8)
        print('P02: duplicate edge rejected at its location; original optimal has 8 stations', flush=True)

    def test_p03_r16_h2_canonical_tie_survives_all_key_permutations(self):
        import itertools
        line = replace(LINE, period=47_560_020 + LINE.planned_stop)
        best = optimal_balance(line.elements, {'A': Fraction(1, 2), 'B': Fraction(1, 2)}, line.net, line.demand)
        pairs = [(2, 2), (2, 2), (2, 1), (2, 1), (2, 2), (1, 1), (1, 2), (2, 2),
                 (1, 2), (1, 1), (2, 1), (1, 1), (2, 2), (2, 1), (2, 2), (2, 2),
                 (1, 2), (2, 2), (1, 2), (1, 2)]
        routes = [[Route(str(index), 'A', {'LEAK': 1, 'LIGHT': light, 'FINAL': final})
                   for index, (light, final) in enumerate(pairs)]]
        for names in itertools.permutations(('LEAK', 'LIGHT', 'FINAL')):
            changed = replace(line, machines={name: line.machines[name] for name in names})
            rows, chosen, results, _ = compare(changed, best, '0-0', '1-1', 20, routes, routes)
            self.assertEqual(chosen, (2, 1, 2), names)
            self.assertEqual(tuple(results[chosen][0][name] for name in ('LEAK', 'LIGHT', 'FINAL')), (2, 1, 2))
            self.assertEqual(next(row['combo'] for row in rows if row['section'] == 'selection'), '2-1-2')
        print('P03: all 6 machine-key permutations select and label LEAK/LIGHT/FINAL=2-1-2', flush=True)

    def test_p04_r16_h3_real_routes_cross_10000_in_numeric_order(self):
        routes = product_routes(SETUP, RECIPE, BOOK, 0, 10001)
        self.assertEqual([int(route.product_id[4:]) for route in routes], list(range(1, 10002)))
        print('P04: real generated routes 1..10001 remain in numeric order', flush=True)

    def test_p05_r16_h4_exact_seconds_extended_boundaries(self):
        cases = {'0': 0, '000.001': 1, '1.01': 1010,
                 '123456789012345678901234567890.123': 123456789012345678901234567890123,
                 '9' * 120 + '.999': int('9' * 123)}
        for value, expected in cases.items():
            errors = []
            self.assertEqual(_seconds(value, '$.seconds', errors), expected)
            self.assertEqual(errors, [])
        print('P05: zero, leading zeros, fractional and 123-digit milliseconds remain exact', flush=True)

    def test_p06_r16_m2_no_balance_announces_only_actual_outputs(self):
        data = dict(RAW_LINE, generator=str(CONFIG), demand_units=2600)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'tight.json'
            path.write_text(json.dumps(data), encoding='utf-8')
            result = cli(folder, 'src.line', path, '--seeds', '0-0', '--holdout-seeds', '1-1', '--products', 2)
            self.success(result)
            self.assertIn('배치 불가', result.stdout)
            self.assertNotIn('layout.svg', result.stdout)
            self.assertEqual(sorted(item.name for item in (Path(folder) / 'reports').iterdir()),
                             ['tight_balance.csv', 'tight_compare.csv'])
        print('P06: infeasible balance announces exactly the 2 CSV files actually written', flush=True)

    def test_p07_reset_clears_published_words_but_keeps_id_and_count(self):
        rig = Rig()
        rig.reach_wait()
        rig.set(guard_closed=False)
        self.assertEqual(rig.scan(), ALARM)
        rig.table.coils[9] = True
        rig.scan()
        rig.table.coils[9] = False
        rig.set(guard_closed=True, clamp_closed=False, clamp_open=True, part_present=False,
                seated=False, direction_ok=False)
        rig.table.holding[1:3] = [7, 2]
        rig.table.coils[8] = True
        self.assertEqual(rig.scan(), IDLE)
        actual = rig.table.input_registers[3:5]
        print('P07: after accepted reset state=IDLE; value=%r; words=%r; measure_id=%d' %
              (rig.plc.value, actual, rig.plc.measure_id), flush=True)
        self.assertEqual(rig.table.holding[1:3], [0, 0])
        self.assertEqual((rig.plc.measure_id, rig.plc.processed), (1, 0))
        self.assertTrue(rig.table.coils[8])
        self.assertFalse(rig.plc.release_latch)
        self.assertIn('aborted', rig.plc.events)
        self.assertEqual(actual, [0, 0], 'Recovery must clear the published measurement as well as the internal string')

    def test_p08_valid_prefix_not_lost_when_bad_frame_is_coalesced(self):
        valid = frame(1, struct.pack('>BHH', 6, 0, 7))
        invalid = frame(2, struct.pack('>BHH', 3, 0, 1), protocol=1)
        results = []
        for chunks in ([valid, invalid], [valid + invalid], [valid + invalid[:5], invalid[5:]]):
            table = Table()
            connection = ChunkConnection(chunks)
            server = ModbusServer.__new__(ModbusServer)
            server.table = table
            server._serve(connection)
            results.append((table.holding[0], len(connection.replies)))
        print('P08: identical bytes, 3 recv segmentations -> (heartbeat, replies)=%r' % results, flush=True)
        self.assertEqual(results, [(7, 1)] * 3, 'A later damaged frame must not erase a preceding complete valid request')

    def test_p09_station_values_follow_numeric_product_order_past_9999(self):
        station = load_station(STATION_FILE)
        first = {}
        for row in Generator(0, SETUP, RECIPE.models, BOOK).normal_events(10001):
            if row['inspection'] == 'LEAK' and row['value']:
                first.setdefault(row['product_id'], row['value'])
        # normal_events interleaves models. Use the adapter's documented product
        # order, rather than assuming inspection occurrence order is numeric.
        expected = [first[key] for key in sorted(first, key=lambda key: int(key[4:]))]
        actual, _ = load_values(station, 0, 10001)
        difference = next((i for i, pair in enumerate(zip(actual, expected), 1) if pair[0] != pair[1]), None)
        print('P09: first wrong station measurement position=%r; actual/expected around 1001=%r/%r' %
              (difference, actual[998:1004], expected[998:1004]), flush=True)
        self.assertEqual(actual, expected, 'LEAK first measurements must retain numeric product order across 9999/10000')

    def test_p10_invalid_fc16_does_not_change_pair_then_valid_pair_is_accepted(self):
        rig = Rig()
        rig.reach_wait()
        rig.table.holding[1:3] = [9, 1]
        invalid = struct.pack('>BHHBHH', 0x10, 0, 2, 4, 1, 2)
        self.assertEqual(handle_pdu(invalid, rig.table), bytes.fromhex('90 02'))
        self.assertEqual(rig.table.holding[1:3], [9, 1])
        self.assertEqual(rig.scan(), WAIT_JUDGE)
        self.assertEqual(rig.plc.events, ['판정 거절: ID 불일치'])
        good = struct.pack('>BHHBHH', 0x10, 1, 2, 4, 1, 2)
        self.assertEqual(handle_pdu(good, rig.table), good[:5])
        self.assertEqual(rig.scan(), UNCLAMP)
        self.assertEqual(rig.plc.events, ['판정 접수'])
        self.assertEqual(rig.plc.verdict, 2)
        print('P10: invalid FC16 leaves old pair; rejection followed by valid FAIL pair accepts once', flush=True)

    def test_p11_judge_and_input_changes_after_snapshot_wait_until_next_scan(self):
        rig = Rig()
        rig.reach_wait()
        def change():
            rig.table.holding[1:3] = [1, 1]
            rig.set(clamp_closed=False, clamp_open=True)
        self.assertEqual(rig.scan(hook=change), WAIT_JUDGE)
        self.assertTrue(rig.plc.outputs['clamp_cmd'])
        self.assertEqual(rig.scan(), UNCLAMP)
        self.assertFalse(rig.plc.outputs['gate_ok'])
        print('P11: post-snapshot judge/input changes ignored now and accepted next scan; one transition', flush=True)

    def test_p12_bad_judge_at_expiry_and_valid_judge_at_expiry(self):
        for valid in (False, True):
            rig = Rig()
            rig.reach_wait()
            for _ in range(30):
                self.assertEqual(rig.scan(), WAIT_JUDGE)
            rig.table.holding[1:3] = [1 if valid else 2, 1]
            state = rig.scan()
            self.assertEqual(state, UNCLAMP if valid else ALARM)
            self.assertEqual(rig.plc.alarm, 0 if valid else 14)
            self.assertFalse(rig.plc.outputs['gate_ok'])
        print('P12: valid judge wins at expiry; invalid judge is rejected then alarm 14 in same scan', flush=True)

    def test_p13_expired_heartbeat_failed_reset_requires_new_edge(self):
        rig = Rig()
        rig.set(guard_closed=False)
        rig.scan()
        rig.set(guard_closed=True)
        for _ in range(11):
            rig.scan(beat=False)
        rig.table.coils[8] = True
        self.assertEqual(rig.scan(beat=False), ALARM)
        self.assertEqual(rig.scan(), ALARM)
        rig.table.coils[8] = False
        rig.scan()
        rig.table.coils[8] = True
        self.assertEqual(rig.scan(), IDLE)
        print('P13: failed reset edge consumed while heartbeat stale; recovery needs a fresh edge', flush=True)

    def test_p14_adapter_exact_values_and_bad_precision_followed_by_valid(self):
        for value in ('0', '-0.000', '000000000000000000000000001.230', '2147483.64700000000000000000000'):
            words = to_words(value)
            from decimal import Decimal
            self.assertEqual(Decimal(restore_value(*words)), Decimal(value))
        for value in ('1.00000000000000000000000000001', '-2147483.648000000000000000001', '1E0', ''):
            with self.assertRaises(ValueConversionError):
                to_words(value)
            self.assertEqual(to_words('1.2300'), (0, 1230))
        print('P14: 30-digit exact values round-trip; nonintegral/invalid values rejected; next valid value exact', flush=True)

    def test_p15_existing_blobs_and_original_test_bodies_preserved(self):
        roots = ('src', 'tests', 'recipes', 'data', 'reports')
        old = set(git('ls-tree', '-r', '--name-only', BASE, '--', *roots).splitlines())
        changed = set(git('diff', '--name-only', BASE, '--', *roots).splitlines()) & old
        self.assertEqual(changed, {'src/line.py', 'tests/test_line.py'})
        stage10_old = set(git('ls-tree', '-r', '--name-only', STAGE10_BASE, '--', *roots).splitlines())
        self.assertFalse(set(git('diff', '--name-only', STAGE10_BASE, '--', *roots).splitlines()) & stage10_old)
        previous = ast.parse(git('show', BASE + ':tests/test_line.py'))
        current = ast.parse((ROOT / 'tests/test_line.py').read_text(encoding='utf-8-sig'))
        def methods(tree):
            return {(cls.name, node.name): ast.dump(node, include_attributes=False)
                    for cls in tree.body if isinstance(cls, ast.ClassDef)
                    for node in cls.body if isinstance(node, ast.FunctionDef)}
        before, after = methods(previous), methods(current)
        for key, body in before.items():
            self.assertEqual(after[key], body, key)
        reports = sum(name.startswith('reports/') for name in old)
        print('P15: %d protected old files identical; %d old reports identical; %d original line test methods unchanged; '
              'all %d stage-10 predecessor files unchanged' % (len(old) - 2, reports, len(before), len(stage10_old)), flush=True)

    def test_p16_legacy_samples_and_generated_reports_replay(self):
        with tempfile.TemporaryDirectory() as folder:
            for name, recipe, equipment, extra in (
                ('sample_events', None, None, ()),
                ('sample_events_v2', 'lamp_models.json', None, ()),
                ('sample_events_retest', 'lamp_models_retest.json', None, ()),
                ('sample_events_equipment', 'lamp_models_retest.json', 'equipment.json', ()),
                ('sample_events_restart', 'lamp_models_retest.json', 'equipment_restart.json', ('--summary', '--trace', 'f')),
                ('sample_events_lot', 'lamp_models_retest.json', 'equipment_lot.json', ('--summary', '--containment')),
                ('sample_events_measured', 'lamp_models_measured.json', 'equipment_measured.json', ('--summary', '--capability', '--trace', 'c'))):
                args = [ROOT / 'data' / (name + '.csv')]
                if recipe:
                    args += ['--recipe', ROOT / 'recipes' / recipe]
                if equipment:
                    args += ['--equipment', ROOT / 'recipes' / equipment]
                self.success(cli(folder, 'src.main', *args, *extra))
            for name, config, equipment, extra in (
                ('gen_seed42', 'generator.json', 'equipment_generated.json', ('--trace', 'GEN_0030')),
                ('gen_measured_seed42', 'generator_measured.json', 'equipment_measured.json', ('--capability', '--containment'))):
                source = Path(folder) / (name + '.csv')
                generate(42, 500, source, ROOT / 'recipes' / config)
                for suffix in ('', '.meta.json'):
                    self.assertEqual(Path(str(source) + suffix).read_bytes(),
                                     (ROOT / 'data/generated' / (source.name + suffix)).read_bytes())
                recipe = 'lamp_models_measured.json' if 'measured' in name else 'lamp_models_retest.json'
                self.success(cli(folder, 'src.main', source, '--recipe', ROOT / 'recipes' / recipe, '--equipment',
                                 ROOT / 'recipes' / equipment, '--summary', '--trace', 'GEN_0005', *extra))
            expected = [p for p in (ROOT / 'reports').glob('*.csv')
                        if not p.name.startswith(('eval_', 'pfmea_', 'line_', 'plc_station_'))]
            for path in expected:
                self.assertEqual((Path(folder) / 'reports' / path.name).read_bytes(), path.read_bytes(), path.name)
        print('P16: %d legacy reports and 4 generated CSV/meta files replay byte-identically' % len(expected), flush=True)

    def test_p17_pfmea_and_line_submitted_artifacts_replay(self):
        with tempfile.TemporaryDirectory() as folder:
            self.success(cli(folder, 'src.pfmea', ROOT / 'data/pfmea_lamp.csv', '--config', CONFIG,
                             '--seeds', '0-29', '--products', 500))
            self.success(cli(folder, 'src.line', LINE_FILE, '--seeds', '0-29', '--holdout-seeds', '1000-1029', '--products', 500))
            names = ('pfmea_lamp_report.csv', 'pfmea_lamp_report.md',
                     'line_lamp_balance.csv', 'line_lamp_compare.csv', 'line_lamp_layout.svg')
            for name in names:
                self.assertEqual((Path(folder) / 'reports' / name).read_bytes(), (ROOT / 'reports' / name).read_bytes(), name)
        print('P17: PFMEA 2 and line 3 submitted artifacts replay byte-identically after R16 fixes', flush=True)

    def test_p18_station_scenarios_repeat_and_match_submitted_artifacts(self):
        collected = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as folder:
                result = cli(folder, 'src.station', STATION_FILE, '--scenario', 'all')
                self.success(result)
                self.assertIn('normal | 20 | 19 | 1 | 0 |', result.stdout)
                for name, code in (('seat_ng', 11), ('clamp_stuck', 12), ('judge_lost', 14),
                                   ('pc_silent', 21), ('disconnect', 21), ('guard_open', 22), ('stale_judge', 14)):
                    self.assertIn('%s | 4 | 4 | 0 | %d |' % (name, code), result.stdout)
                contents = {p.name: p.read_bytes() for p in (Path(folder) / 'reports').iterdir()}
                self.assertEqual(len(contents), 16)
                for name, data in contents.items():
                    self.assertEqual(data, (ROOT / 'reports' / name).read_bytes(), name)
                collected.append(contents)
        self.assertEqual(collected[0], collected[1])
        print('P18: all 8 scenarios repeat across 2 folders and all 16 reports match submitted bytes', flush=True)


if __name__ == '__main__':
    unittest.main()

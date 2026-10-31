"""Review 016: independent, diff-focused probes; all outputs use temporary folders.

Run: py -m unittest handoff/reviews/probes/test_probe_016.py
Assertions retain required behavior so confirmed defects remain visible failures.
No previous probe module is imported or executed.
"""
import copy
import csv
from dataclasses import replace
from fractions import Fraction
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from src.generate import generate, load_setup
from src.line import (
    LineError, Route, SimStation, _seconds, area_of, compare, cycle_limits,
    heuristic_balance, load_line, optimal_balance, product_routes, simulate, uph,
)
from src.pfmea import (
    INPUT_COLUMNS, METRICS, PfmeaError, build_markdown, build_report, check_table,
    resolve_reference,
)

ROOT = Path(__file__).resolve().parents[3]
BASE = '1c976f9797bc7782faf977e65ee0fceb3cee75d5'
STAGE9_BASE = 'ee0ecb2'
CONFIG = ROOT / 'recipes/generator_measured.json'
LINE_FILE = ROOT / 'recipes/line_lamp.json'
CONFIG_DATA, _, RECIPE, BOOK = load_setup(CONFIG)
RAW = json.loads(LINE_FILE.read_text(encoding='utf-8-sig'))
LINE = load_line(LINE_FILE, RECIPE.models)
RATIOS = {'A': Fraction(1, 2), 'B': Fraction(1, 2)}


def cli(folder, module, *args):
    return subprocess.run(
        [sys.executable, '-m', module, *map(str, args)], cwd=folder,
        env={**os.environ, 'PYTHONPATH': str(ROOT), 'PYTHONIOENCODING': 'utf-8',
             'PYTHONDONTWRITEBYTECODE': '1'},
        capture_output=True, text=True, encoding='utf-8', timeout=300)


def row(**fields):
    result = dict.fromkeys(INPUT_COLUMNS, '')
    result.update(id='PF-01', failure_type='record', process_step='ALL',
                  function_requirement='function', failure_mode='mode', effect='effect',
                  cause='cause', prevention_control='없음', detection_control='없음')
    result.update(fields)
    return result


def external_report(root, header='capture_rate', method='method,m,0.314159,\n'):
    (root / 'reports').mkdir(exist_ok=True)
    text = ('section,method,' + header + ',value\n'
            'provenance,generator_version,,1.3.0\nprovenance,seeds,,4-5\n'
            'provenance,products,,17\nprovenance,config_sha256,,abc\n' + method)
    (root / 'reports/probe.csv').write_text(text, encoding='utf-8')


def balance(line=LINE):
    return optimal_balance(line.elements, RATIOS, line.net, line.demand)


class DiffProbes(unittest.TestCase):
    maxDiff = 1600

    def success(self, result):
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_p01_prior_h3_absent_short_blank_and_recovery(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cases = [('precision', 'method,m,0.5,\n', '없는 열'),
                     ('capture_rate', 'method,m\n', '칸이 없음')]
            for header, method, message in cases:
                with self.subTest(header=header, method=method):
                    external_report(root, header, method)
                    with self.assertRaisesRegex(ValueError, message):
                        resolve_reference('report:probe:m:capture_rate', root)
                    with self.assertRaisesRegex(PfmeaError, '1.evidence'):
                        check_table([row(failure_type='product', evidence='report:probe:m:capture_rate',
                                         evidence_note='note')], RECIPE.models, root)
            external_report(root, method='method,m,,\n')
            self.assertEqual(resolve_reference('report:probe:m:capture_rate', root).report[0], '')
            external_report(root)
            self.assertEqual(resolve_reference('report:probe:m:capture_rate', root).report[0], '0.314159')
        print('P01: missing column/short row rejected; blank retained; following numeric reference accepted', flush=True)

    def test_p02_prior_m2_multiple_items_and_external_value(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            external_report(root)
            items = [row(evidence='reason:SEQ_SKIP', evidence_note='note', action='action',
                         action_owner='owner', action_goal='goal', action_state='완료',
                         control_before='before', control_after='after',
                         action_evidence='reason:RECIPE_UNKNOWN_STEP'),
                     row(id='PF-02', failure_type='product', evidence='report:probe:m:capture_rate',
                         evidence_note='external', action='action', action_owner='owner', action_goal='goal',
                         action_state='효과 확인', control_before='before', control_after='after',
                         action_evidence='rule:RULE_SEQ', residual_risk='risk',
                         success_reference='report:probe:m:capture_rate', success_op='>=', success_value='0.4')]
            refs = check_table(items, RECIPE.models, root)
            report = build_report(items, refs, {name: (0, 0) for name in METRICS}, {}, [], {})
            markdown = build_markdown(report)
            for text in ('reason:SEQ_SKIP', 'reason:RECIPE_UNKNOWN_STEP', 'rule:RULE_SEQ',
                         '관측값: 0.314159', '효과 판정: 미충족'):
                self.assertIn(text, markdown)
            self.assertNotIn('관측값:', markdown.split('## PF-02')[0])
        print('P02: current/action references and external observation retained under the correct item', flush=True)

    def test_p03_malformed_line_input_must_exit_3(self):
        cases = []
        missing = copy.deepcopy(RAW)
        del missing['generator']
        cases.append(('missing generator', missing))
        cases.append(('top-level array', []))
        number = copy.deepcopy(RAW)
        number['generator'] = 7
        cases.append(('numeric generator path', number))
        step = copy.deepcopy(RAW)
        step['elements'][0]['step'] = []
        step['generator'] = str(CONFIG)
        cases.append(('array step', step))
        for label, data in cases:
            with self.subTest(case=label), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / 'invalid.json'
                path.write_text(json.dumps(data), encoding='utf-8')
                result = cli(folder, 'src.line', path, '--seeds', '0-0', '--holdout-seeds', '1-1', '--products', 1)
                print('P03 ' + label + ': exit=' + str(result.returncode) + '; traceback='
                      + str('Traceback' in result.stderr) + '; reports=' + str((Path(folder) / 'reports').exists()), flush=True)
                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertNotIn('Traceback', result.stderr)
                self.assertFalse((Path(folder) / 'reports').exists())

    def test_p04_duplicate_predecessor_does_not_destroy_feasible_balance(self):
        data = copy.deepcopy(RAW)
        data['elements'][1]['predecessors'] = ['P1-1', 'P1-1']
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'line.json'
            path.write_text(json.dumps(data), encoding='utf-8')
            try:
                line = load_line(path, RECIPE.models)
            except LineError:
                # Rejecting the duplicate explicitly is also a coherent input policy.
                return
        best = balance(line)
        greedy = heuristic_balance(line.elements, RATIOS, line.net, line.demand)
        print('P04: duplicate accepted; optimal=' + str(best) + '; heuristic stations='
              + str(len(greedy.stations)), flush=True)
        self.assertEqual(best, balance(), 'An accepted repeated edge must not change its dependency set')

    def test_p05_machine_key_order_must_not_change_canonical_tie_break(self):
        line = replace(LINE, period=47_560_020 + LINE.planned_stop)
        best = balance(line)
        pairs = [(2, 2), (2, 2), (2, 1), (2, 1), (2, 2), (1, 1), (1, 2), (2, 2),
                 (1, 2), (1, 1), (2, 1), (1, 1), (2, 2), (2, 1), (2, 2), (2, 2),
                 (1, 2), (2, 2), (1, 2), (1, 2)]
        routes = [[Route(str(i), 'A', {'LEAK': 1, 'LIGHT': light, 'FINAL': final})
                   for i, (light, final) in enumerate(pairs)]]
        selections = []
        for names in (('LEAK', 'LIGHT', 'FINAL'), ('FINAL', 'LIGHT', 'LEAK')):
            changed = replace(line, machines={name: line.machines[name] for name in names})
            rows, selected, results, _ = compare(changed, best, '0-0', '1-1', 20, routes, routes)
            choice = results[selected][0]
            canonical = tuple(choice[name] for name in ('LEAK', 'LIGHT', 'FINAL'))
            selections.append(canonical)
            print('P05: key order=' + str(names) + '; chosen LEAK/LIGHT/FINAL=' + str(canonical)
                  + '; area=' + str(area_of(changed, choice)), flush=True)
            if names[0] == 'LEAK':
                tied = [r for r in rows if r['section'] == 'development' and r['combo'] in ('2-1-2', '2-2-1')]
                self.assertEqual(len(tied), 2)
                self.assertTrue(all(r['reject_reason'] == '' for r in tied))
                self.assertEqual(tied[0]['area_mm2'], tied[1]['area_mm2'])
        self.assertEqual(selections, [(2, 1, 2), (2, 1, 2)])

    def test_p06_product_number_boundary_9999_10000(self):
        routes = product_routes(CONFIG_DATA, RECIPE, BOOK, 0, 10001)
        numbers = [int(route.product_id.removeprefix('GEN_')) for route in routes]
        first = next((i for i, value in enumerate(numbers, 1) if value != i), None)
        print('P06: routes=' + str(len(routes)) + '; first mismatch at position=' + str(first)
              + '; actual slice=' + str(numbers[997:1005]), flush=True)
        self.assertEqual(len(numbers), 10001)
        self.assertIsNone(first, 'Input order must follow product number across the four-digit boundary')

    def test_p07_long_valid_seconds_are_exact_integer_milliseconds(self):
        text = '123456789012345678901234567890.123'
        errors = []
        actual = _seconds(text, '$.period_seconds', errors, True)
        expected = int(text.replace('.', ''))
        print('P07: expected_ms=' + str(expected) + '; actual_ms=' + str(actual) + '; errors=' + str(errors), flush=True)
        self.assertEqual(errors, [])
        self.assertEqual(actual, expected)

    def test_p08_no_balance_cli_reports_only_files_actually_saved(self):
        data = copy.deepcopy(RAW)
        data.update(generator=str(CONFIG), demand_units=2600)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'line.json'
            path.write_text(json.dumps(data), encoding='utf-8')
            result = cli(folder, 'src.line', path, '--seeds', '0-0', '--holdout-seeds', '1-1', '--products', 1)
            self.success(result)
            names = sorted(p.name for p in (Path(folder) / 'reports').iterdir())
            print('P08: files=' + str(names) + '; stdout=' + repr(result.stdout), flush=True)
            self.assertIn('배치 불가', result.stdout)
            self.assertEqual(names, ['line_balance.csv', 'line_compare.csv'])
            self.assertNotIn('line_layout.svg', result.stdout, 'The no-SVG branch must not announce a saved SVG')

    def test_p09_blocked_release_starts_each_server_repair(self):
        stations = [SimStation('X', 2, {'A': 10000}, 'X'), SimStation('M', 1, {'A': 5000})]
        routes = [Route('1', 'A', {'X': 1}, stops=frozenset({'X'})),
                  Route('2', 'A', {'X': 1}, stops=frozenset({'X'})), Route('3', 'A', {'X': 1})]
        result = simulate(stations, routes, 0, 100000)
        self.assertEqual((result.end, result.blocked['X'], result.repair['X']), (125000, 5000, 200000))
        self.assertEqual((result.work['X'], result.work['M'], result.good), (30000, 15000, 3))
        print('P09: blocked release at 15s delays server-2 repair; end=125s, blocking=5s, repair=200s', flush=True)

    def test_p10_zero_work_first_station_and_zero_visits(self):
        stations = [SimStation('skip', 1, {'A': 1000, 'B': 0}), SimStation('M', 1, {'A': 1000, 'B': 2000})]
        result = simulate(stations, [Route('1', 'B'), Route('2', 'A')], 0, 0)
        self.assertEqual((result.end, result.work['skip'], result.work['M'], result.blocked['skip']),
                         (3000, 1000, 3000, 1000))
        self.assertIsNone(cycle_limits(Fraction(10000, 3), 2, Fraction(0), Fraction(0)))
        print('P10: B bypasses first station; A blocks there 1s; absent inspection has no limit', flush=True)

    def test_p11_t143_arithmetic_disagreement(self):
        result = simulate([SimStation('M', 1, {'A': 10000})],
                          [Route('1', 'A', defective=True), Route('2', 'A')], 0, 0)
        self.assertEqual((result.end, result.passed, result.good, result.escaped), (20000, 2, 1, 1))
        self.assertEqual((uph(result.passed, result.end), uph(result.good, result.end)), (360, 180))
        print('P11: T143 formula supports Claude: end=20s, pass_uph=360, good_uph=180, escaped=1', flush=True)

    def test_p12_preserved_blobs_and_stage9_boundary(self):
        names = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', BASE, '--',
                                         'src', 'tests', 'recipes', 'data', 'reports'], cwd=ROOT,
                                        text=True, encoding='utf-8').splitlines()
        exceptions = {'src/pfmea.py', 'tests/test_pfmea.py', 'reports/pfmea_lamp_report.md'}
        protected = [name for name in names if name not in exceptions]
        for name in protected:
            expected = subprocess.check_output(['git', 'rev-parse', BASE + ':' + name], cwd=ROOT, text=True).strip()
            actual = subprocess.check_output(['git', 'hash-object', '--', name], cwd=ROOT, text=True).strip()
            self.assertEqual(actual, expected, name)
        old_names = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', STAGE9_BASE, '--',
                                            'src', 'tests', 'recipes', 'data', 'reports'], cwd=ROOT,
                                           text=True, encoding='utf-8').splitlines()
        for name in old_names:
            expected = subprocess.check_output(['git', 'rev-parse', STAGE9_BASE + ':' + name], cwd=ROOT, text=True).strip()
            actual = subprocess.check_output(['git', 'hash-object', '--', name], cwd=ROOT, text=True).strip()
            self.assertEqual(actual, expected, name)
        diff = subprocess.check_output(['git', 'diff', '--numstat', BASE + '..' + STAGE9_BASE, '--',
                                        'tests/test_pfmea.py'], cwd=ROOT, text=True)
        self.assertEqual(diff.split()[:2], ['11', '0'])
        print('P12: base protected blobs=' + str(len(protected)) + '; old reports protected='
              + str(sum(n.startswith('reports/') for n in protected))
              + '; all stage-9 predecessor blobs=' + str(len(old_names))
              + '; PFMEA regression tests additions=11/deletions=0', flush=True)

    def test_p13_prior_sample_and_generated_reports_replay(self):
        with tempfile.TemporaryDirectory() as folder:
            for name, recipe, equipment, extra in (
                ('sample_events', None, None, ()),
                ('sample_events_v2', 'lamp_models.json', None, ()),
                ('sample_events_retest', 'lamp_models_retest.json', None, ()),
                ('sample_events_equipment', 'lamp_models_retest.json', 'equipment.json', ()),
                ('sample_events_restart', 'lamp_models_retest.json', 'equipment_restart.json', ('--summary', '--trace', 'f')),
                ('sample_events_lot', 'lamp_models_retest.json', 'equipment_lot.json', ('--summary', '--containment')),
                ('sample_events_measured', 'lamp_models_measured.json', 'equipment_measured.json',
                 ('--summary', '--capability', '--trace', 'c'))):
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
                        if not p.name.startswith(('eval_', 'pfmea_', 'line_'))]
            for path in expected:
                self.assertEqual((Path(folder) / 'reports' / path.name).read_bytes(), path.read_bytes(), path.name)
        print('P13: legacy report replays byte-identical=' + str(len(expected)) + '; generated CSV/meta=4', flush=True)

    def test_p14_pfmea_submitted_artifacts_after_fixes(self):
        table = ROOT / 'data/pfmea_lamp.csv'
        before = table.read_bytes()
        with tempfile.TemporaryDirectory() as folder:
            self.success(cli(folder, 'src.pfmea', table, '--config', CONFIG, '--seeds', '0-29', '--products', 500))
            for name in ('pfmea_lamp_report.csv', 'pfmea_lamp_report.md'):
                self.assertEqual((Path(folder) / 'reports' / name).read_bytes(), (ROOT / 'reports' / name).read_bytes())
        self.assertEqual(table.read_bytes(), before)
        print('P14: corrected PFMEA CSV/Markdown match a fresh full submitted-input replay; table unchanged', flush=True)

    def test_p15_line_submitted_artifacts(self):
        with tempfile.TemporaryDirectory() as folder:
            result = cli(folder, 'src.line', LINE_FILE, '--seeds', '0-29', '--holdout-seeds', '1000-1029', '--products', 500)
            self.success(result)
            for name in ('line_lamp_balance.csv', 'line_lamp_compare.csv', 'line_lamp_layout.svg'):
                self.assertEqual((Path(folder) / 'reports' / name).read_bytes(), (ROOT / 'reports' / name).read_bytes(), name)
        print('P15: submitted line CSV/CSV/SVG match a fresh full submitted-input replay', flush=True)

    def test_p16_line_repeat_and_rejected_input_recovery(self):
        outputs = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as folder:
                bad = copy.deepcopy(RAW)
                bad.update(generator=str(CONFIG), buffer_units=True)
                path = Path(folder) / 'invalid.json'
                path.write_text(json.dumps(bad), encoding='utf-8')
                rejected = cli(folder, 'src.line', path, '--seeds', '0-0', '--holdout-seeds', '1-1', '--products', 3)
                self.assertEqual(rejected.returncode, 3, rejected.stderr)
                self.assertFalse((Path(folder) / 'reports').exists())
                self.success(cli(folder, 'src.line', LINE_FILE, '--seeds', '0-0', '--holdout-seeds', '1-1', '--products', 3))
                outputs.append({p.name: p.read_bytes() for p in (Path(folder) / 'reports').iterdir()})
        self.assertEqual(outputs[0], outputs[1])
        print('P16: boolean count rejected without reports; following valid run reproducible across 2 folders', flush=True)


if __name__ == '__main__':
    unittest.main()

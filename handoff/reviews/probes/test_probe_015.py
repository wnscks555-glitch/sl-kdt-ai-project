"""Review 015: diff-focused adversarial checks and preservation replays.

Run: py -m unittest handoff/reviews/probes/test_probe_015.py
Assertions describe required behavior; discovered defects remain failures.
All generated artifacts stay in TemporaryDirectory; no prior probe is imported.
"""
import copy
import csv
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from src.generate import confirm_value, generate, load_setup
from src.pfmea import (INPUT_COLUMNS, METRICS, PfmeaError, build_markdown,
                       build_report, check_table, collect, evidence_status,
                       read_table, run, run_counts)
from src.recipe_rules import input_columns
from src.summary import build_analysis

ROOT = Path(__file__).resolve().parents[3]
BASE = '3d3b2fd83a69b667b1d22ba9856015ed2aea5879'
CONFIG = ROOT / 'recipes/generator_measured.json'
RECIPE = ROOT / 'recipes/lamp_models_measured.json'
EQUIPMENT = ROOT / 'recipes/equipment_measured.json'
TABLE = ROOT / 'data/pfmea_lamp.csv'
CONFIG_DATA, _, RECIPE_BOOK, BOOK = load_setup(CONFIG)
MODELS = RECIPE_BOOK.models


def cli(folder, module, *args):
    return subprocess.run([sys.executable, '-m', module, *map(str, args)], cwd=folder,
                          env={**os.environ, 'PYTHONPATH': str(ROOT), 'PYTHONIOENCODING': 'utf-8',
                               'PYTHONDONTWRITEBYTECODE': '1'},
                          capture_output=True, text=True, encoding='utf-8', timeout=300)


def table_row(**fields):
    row = dict.fromkeys(INPUT_COLUMNS, '')
    row.update(id='PF-01', failure_type='record', process_step='ALL', function_requirement='f',
               failure_mode='m', effect='e', cause='c', prevention_control='없음', detection_control='없음')
    row.update(fields)
    return row


def write_table(path, rows):
    with path.open('w', encoding='utf-8-sig', newline='') as target:
        writer = csv.DictWriter(target, fieldnames=INPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def config_file(folder, **changes):
    config = dict(CONFIG_DATA, recipe=str(RECIPE), equipment=str(EQUIPMENT), **changes)
    path = Path(folder) / 'config.json'
    path.write_text(json.dumps(config), encoding='utf-8')
    return path


def report_file(root, column='capture_rate', number='0.314159'):
    (root / 'reports').mkdir(exist_ok=True)
    text = ('section,method,' + column + ',value\n'
            'provenance,generator_version,,1.3.0\nprovenance,seeds,,4-5\n'
            'provenance,products,,17\nprovenance,config_sha256,,abc\n'
            'selection,,,probe-selection\nmethod,m,' + number + ',\n')
    (root / 'reports/probe.csv').write_text(text, encoding='utf-8')


def metric_report(rows, root=ROOT):
    refs = check_table(rows, MODELS, root)
    return build_report(rows, refs, {name: (0, 0) for name in METRICS}, {}, [], {})


class DiffProbes(unittest.TestCase):
    def success(self, result):
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_p01_h1_integer_shift_sum(self):
        with tempfile.TemporaryDirectory() as folder:
            config = config_file(folder, process_cpk=0.1, defect_shift_sigma=10**308,
                                 fault_shift_sigma={'LEAK-2': 10**308})
            out = Path(folder) / 'out.csv'
            result = cli(folder, 'src.generate', '--config', config, '--out', out, '--products', 20)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn('분포가 유한하지 않음', result.stderr)
            self.assertNotIn('Traceback', result.stderr)
            self.assertFalse(out.exists())
            self.assertFalse(Path(str(out) + '.meta.json').exists())
            print('P01: integer shift overflow => exit 2; CSV/meta absent', flush=True)

    def test_p02_h2_finite_huge_sample(self):
        with tempfile.TemporaryDirectory() as folder:
            config = config_file(folder, process_cpk=1e-307, error_rate=0)
            out = Path(folder) / 'out.csv'
            result = cli(folder, 'src.generate', '--config', config, '--out', out,
                         '--seed', 42, '--products', 20)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn('자릿수 상한', result.stderr)
            self.assertNotIn('Traceback', result.stderr)
            self.assertFalse(out.exists())
            self.assertFalse(Path(str(out) + '.meta.json').exists())
            print('P02: huge finite sample => exit 2; CSV/meta absent', flush=True)

    def test_p03_m1_independent_cases_and_targeted_t108(self):
        spec = importlib.util.spec_from_file_location('review015_measurement', ROOT / 'tests/test_measurement.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        case = module.GeneratorTests('test_t108_config_errors_exit_2_without_files')
        with tempfile.TemporaryDirectory() as folder:
            first = case.setup_paths(folder, 'zero', config={'process_cpk': 0})
            second = case.setup_paths(folder, 'negative', config={'fault_shift_sigma': {'LEAK-2': -1}})
            self.assertNotEqual(first, second)
            self.assertEqual(json.loads(first.read_text(encoding='utf-8'))['process_cpk'], 0)
            self.assertEqual(json.loads(second.read_text(encoding='utf-8'))['process_cpk'], 1.33)
        result = unittest.TestResult()
        case.run(result)
        self.assertTrue(result.wasSuccessful(), repr(result.errors + result.failures))
        print('P03: independent files retained; targeted T108 (14 config cases + evaluation) passed', flush=True)

    def test_p04_rounding_and_digit_guard_edges(self):
        for number, expected in ((1e-300, '0.000'), (-1e-300, '0.000'),
                                 (0.0005, '0.001'), (-0.0005, '-0.001'), (1e26, '1' + '0'*26 + '.000')):
            self.assertEqual(confirm_value(number), expected)
        for number in (1e27, -1e27, 1e100, -1e308):
            with self.assertRaisesRegex(ValueError, '자릿수 상한'):
                confirm_value(number)
        print('P04: half-up, signed zero, 30-digit boundary and huge negatives passed', flush=True)

    def test_p05_reference_rejection_precedes_generation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'table.csv'
            for evidence in ('rule:rule_seq', 'rule:RULE_SEQ;rule:RULE_SEQ',
                             'rule:RULE_SEQ;', ' rule:RULE_SEQ', 'rule:RULE_SEQ '):
                row = table_row(evidence=evidence, evidence_note='note')
                before = copy.deepcopy(row)
                write_table(path, [row])
                with patch('src.pfmea.collect') as generation:
                    with self.assertRaisesRegex(PfmeaError, '1.evidence'):
                        run(path, CONFIG, '0-0', 1)
                    generation.assert_not_called()
                self.assertEqual(row, before)
            self.assertIn('PF-01', check_table([table_row(evidence='rule:RULE_SEQ', evidence_note='note')], MODELS))
            self.assertFalse((Path(folder) / 'reports').exists())
        print('P05: five invalid case/duplicate/empty/whitespace refs rejected before generation; next valid row accepted', flush=True)

    def test_p06_zero_faults_and_injection_independence(self):
        changed = dict(CONFIG_DATA, fault_shift_sigma={}, defective_product_probability=0,
                       retest_probability=0, error_rate=1)
        counts, detail = collect(changed, RECIPE_BOOK, BOOK, range(7, 9), 1)
        self.assertEqual(counts['normal_reject'][1], 2)
        self.assertEqual(counts['defect_escape'][1], 0)
        self.assertEqual([counts[name][1] for name in ('fault_stop_run', 'fault_no_stop_run', 'fault_stop_delay')], [0, 0, 0])
        self.assertEqual(detail, {})
        self.assertGreater(counts['normal_stop_rate'][1], 0)
        print('P06: 2 seeds x 1 product; no faults/defects; error_rate=1 does not invoke injection', flush=True)

    def test_p07_rejected_retest_restart_and_unobserved_fault_pair(self):
        rows = []
        def add(pid, event, **fields):
            row = dict.fromkeys(input_columns(BOOK, True), '')
            row.update(seq='1', product_id=pid, event=event, **fields)
            rows.append(row)
        for pid in 'abc':
            add(pid, 'REGISTER', model='B')
            add(pid, 'P1')
            add(pid, 'P2')
        for pid in 'ab':
            add(pid, 'INSPECT', inspection='LEAK', equipment='LEAK-1', value='14')
        add('a', 'RETEST_REQUEST', inspection='LEAK')
        add('a', 'INSPECT', inspection='LEAK', equipment='LEAK-1', value='10')
        add('a', 'INSPECT', inspection='LEAK', equipment='LEAK-2', value='10')
        add('', 'EQUIP_RESTART', equipment='LEAK-1', result='FIXED')
        add('c', 'INSPECT', inspection='LEAK', equipment='LEAK-1', value='10')
        analysis = build_analysis(rows, MODELS, BOOK)
        self.assertEqual(sum(not d.accepted for d in analysis.decisions), 1)
        counts, detail = run_counts(analysis, {'a'}, ['LEAK-1', 'FINAL-2'])
        self.assertEqual(counts['fault_stop_run'], (1, 2))
        self.assertEqual(counts['fault_no_stop_run'], (1, 2))
        self.assertEqual(counts['fault_stop_delay'], (2, 1))
        self.assertEqual(counts['normal_stop_rate'], (0, 0))
        self.assertEqual(counts['leak_defect_retest_pass'], (1, 1))
        self.assertEqual(detail['FINAL-2'], (0, 1))
        print('P07: repeated seq; rejected retest excluded; repaired faulty measurements excluded; unseen fault pair retained', flush=True)

    def test_p08_missing_report_column_is_not_a_blank_value(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            report_file(root, column='precision', number='0.5')
            row = table_row(failure_type='product', evidence='report:probe:m:capture_rate', evidence_note='note')
            try:
                refs = check_table([row], MODELS, root)
            except PfmeaError as error:
                self.assertIn('1.evidence', str(error))
            else:
                status = evidence_status('product', refs['PF-01'][0], {})
                self.fail('missing capture_rate column accepted; evidence_status=' + status)

    def test_p09_markdown_retains_current_and_action_evidence(self):
        row = table_row(evidence='reason:SEQ_SKIP', evidence_note='note', action='action', action_owner='owner',
                        action_goal='goal', action_state='완료', control_before='T1', control_after='T2',
                        action_evidence='reason:RECIPE_UNKNOWN_STEP')
        markdown = build_markdown(metric_report([row]))
        missing = [reference for reference in (row['evidence'], row['action_evidence']) if reference not in markdown]
        self.assertEqual(missing, [], 'Markdown dropped evidence references')

    def test_p10_markdown_retains_external_observation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            report_file(root)
            row = table_row(failure_type='product', evidence='report:probe:m:capture_rate', evidence_note='note',
                            action='action', action_owner='owner', action_goal='goal', action_state='효과 확인',
                            control_before='T1', control_after='T2', success_reference='report:probe:m:capture_rate',
                            success_op='>=', success_value='0.4', action_evidence='rule:RULE_SEQ', residual_risk='risk')
            report = metric_report([row], root)
            action = next(item for item in report if item['section'] == 'action')
            self.assertEqual(action['value'], '0.314159')
            self.assertEqual(action['effect_result'], '미충족')
            self.assertIn('0.314159', build_markdown(report), 'external observed value absent from Markdown')

    def test_p11_protected_files_and_old_test_bodies(self):
        names = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', BASE, '--',
                                         'tests', 'src/rules.py', 'recipes', 'data', 'reports'],
                                        cwd=ROOT, text=True, encoding='utf-8').splitlines()
        protected = [name for name in names if name != 'tests/test_measurement.py']
        for name in protected:
            expected = subprocess.check_output(['git', 'rev-parse', BASE + ':' + name], cwd=ROOT, text=True).strip()
            actual = subprocess.check_output(['git', 'hash-object', '--', name], cwd=ROOT, text=True).strip()
            self.assertEqual(actual, expected, name)
        import ast
        def methods(text):
            tree = ast.parse(text)
            return {(node.name, method.name): ast.dump(method) for node in tree.body if isinstance(node, ast.ClassDef)
                    for method in node.body if isinstance(method, ast.FunctionDef)}
        old = subprocess.check_output(['git', 'show', BASE + ':tests/test_measurement.py'], cwd=ROOT,
                                      text=True, encoding='utf-8')
        old_methods, current = methods(old), methods((ROOT / 'tests/test_measurement.py').read_text(encoding='utf-8'))
        allowed = {('GeneratorTests', name) for name in ('setup_paths', 'recipe_with', 'test_t108_config_errors_exit_2_without_files')}
        for key, body in old_methods.items():
            if key not in allowed:
                self.assertEqual(current.get(key), body, str(key))
        stage8_changes = subprocess.check_output(['git', 'diff', '--name-only', '885abbf..HEAD', '--', 'tests'],
                                                  cwd=ROOT, text=True).splitlines()
        self.assertEqual(stage8_changes, ['tests/test_pfmea.py'])
        print('P11: protected blobs=' + str(len(protected)) + '; old reports=' + str(sum(n.startswith('reports/') for n in names))
              + '; 7a methods preserved except requested M1 fix; stage 8 adds only test_pfmea.py', flush=True)

    def compare_reports(self, folder, names):
        for name in names:
            self.assertEqual((Path(folder) / 'reports' / name).read_bytes(), (ROOT / 'reports' / name).read_bytes(), name)
        return len(names)

    def test_p12_samples_and_generated_report_preservation(self):
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
                recipe = RECIPE if 'measured' in name else ROOT / 'recipes/lamp_models_retest.json'
                self.success(cli(folder, 'src.main', source, '--recipe', recipe, '--equipment',
                                 ROOT / 'recipes' / equipment, '--summary', '--trace', 'GEN_0005', *extra))
            expected = [p.name for p in (ROOT / 'reports').glob('*.csv') if not p.name.startswith(('eval_', 'pfmea_'))]
            print('P12: replayed reports byte-identical=' + str(self.compare_reports(folder, expected)) + '; generated CSV/meta=4', flush=True)

    def test_p13_evaluation_report_preservation(self):
        with tempfile.TemporaryDirectory() as folder:
            for out, config, seeds, rules, extra in (
                ('eval_dev', 'generator_restart.json', '0-99', '3:2,5:2,5:3,10:3,10:4,20:4', ()),
                ('eval_holdout', 'generator_restart.json', '1000-1099', '3:2', ('--holdout',)),
                ('eval_baseline', 'generator.json', '0-99', '3:2', ('--holdout',))):
                self.success(cli(folder, 'src.evaluate', '--config', ROOT / 'recipes' / config,
                                 '--seeds', seeds, '--rules', rules, '--out', out, *extra))
                print('P13 replayed: ' + out, flush=True)
            for setting in ('lot', 'lot_clustered'):
                config = ROOT / 'recipes' / ('generator_' + setting + '.json')
                dev = 'eval_' + setting + '_dev'
                self.success(cli(folder, 'src.evaluate', '--containment', '--config', config,
                                 '--seeds', '0-99', '--rules', '3:2', '--out', dev))
                self.success(cli(folder, 'src.evaluate', '--containment', '--config', config,
                                 '--seeds', '1000-1099', '--rules', '3:2', '--out',
                                 'eval_' + setting + '_holdout', '--holdout', '--selected-from',
                                 Path(folder) / 'reports' / (dev + '_containment.csv')))
                print('P13 replayed: ' + setting, flush=True)
            expected = [p.name for p in (ROOT / 'reports').glob('eval_*.csv')]
            print('P13: evaluation reports byte-identical=' + str(self.compare_reports(folder, expected)), flush=True)

    def test_p14_submitted_pfmea_replay_and_determinism(self):
        before = TABLE.read_bytes()
        outputs = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as folder:
                self.success(cli(folder, 'src.pfmea', TABLE, '--config', CONFIG, '--seeds', '0-29', '--products', 500))
                outputs.append({path.name: path.read_bytes() for path in (Path(folder) / 'reports').iterdir()})
        self.assertEqual(outputs[0], outputs[1])
        for name, content in outputs[0].items():
            self.assertEqual(content, (ROOT / 'reports' / name).read_bytes(), name)
        self.assertEqual(TABLE.read_bytes(), before)
        print('P14: submitted PFMEA CSV/Markdown match two independent replays; input unchanged', flush=True)


if __name__ == '__main__':
    unittest.main()

"""Review 014 adversarial and preservation checks; outputs stay in tempfile.

Run: py -m unittest handoff/reviews/probes/test_probe_014.py
Failures intentionally retain the required behavior, not the current defect.
"""
import copy
import csv
from dataclasses import replace
from decimal import Decimal
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from src.capability import build_capability, capability, show
from src.equipment import load_equipment
from src.generate import generate, load_setup
from src.recipe import RecipeError, load_recipe
from src.recipe_rules import RecipeProcess, input_columns
from src.summary import build_analysis
from src.trace import build_trace

ROOT = Path(__file__).resolve().parents[3]
BASE = 'dc7f523e1a529f2c1d270bbe8a3e1daf651eb701'
RECIPE = ROOT / 'recipes/lamp_models_measured.json'
EQUIPMENT = ROOT / 'recipes/equipment_measured.json'
CONFIG = ROOT / 'recipes/generator_measured.json'
MODELS = load_recipe(RECIPE).models
BOOK = load_equipment(EQUIPMENT, MODELS)


def cli(folder, module, *args):
    return subprocess.run([sys.executable, '-m', module, *map(str, args)], cwd=folder,
                          env={**os.environ, 'PYTHONPATH': str(ROOT), 'PYTHONIOENCODING': 'utf-8',
                               'PYTHONDONTWRITEBYTECODE': '1'},
                          capture_output=True, text=True, encoding='utf-8', timeout=300)


def row(pid, event, value='', equipment='', inspection='', result='', model='', seq='1', book=BOOK):
    item = dict.fromkeys(input_columns(book, True), '')
    item.update(seq=str(seq), product_id=pid, event=event, value=value, equipment=equipment,
                inspection=inspection, result=result, model=model)
    if book.lot_tracking and event == 'REGISTER':
        item['lot'] = 'LOT-1'
    return item


def prepared(pid, book=BOOK):
    return [row(pid, 'REGISTER', model='B', book=book), row(pid, 'P1', book=book),
            row(pid, 'P2', book=book)]


def measure(pid, value, equipment='LEAK-1', book=BOOK):
    return row(pid, 'INSPECT', value=value, equipment=equipment, inspection='LEAK', book=book)


def config_file(folder, changes):
    data = json.loads(CONFIG.read_text(encoding='utf-8-sig'))
    data.update(recipe=str(RECIPE), equipment=str(EQUIPMENT))
    data.update(changes)
    target = Path(folder) / 'config.json'
    target.write_text(json.dumps(data), encoding='utf-8')
    return target


class AdversarialTests(unittest.TestCase):
    def test_p01_duplicate_and_case_rejections_do_not_consume_request(self):
        process = RecipeProcess(MODELS, BOOK)
        for item in prepared('p'):
            self.assertTrue(process.apply(item).accepted)
        self.assertEqual(process.apply(measure('p', '14.000')).result, 'FAIL')
        self.assertTrue(process.apply(row('p', 'RETEST_REQUEST', inspection='LEAK')).accepted)
        before = copy.deepcopy((process.products, process.equipment))
        for event in (measure('p', '-0.000', 'leak-1'), measure('p', '1.0' + '0' * 29),
                      row('p', 'inspect', value='10', equipment='LEAK-1', inspection='LEAK')):
            original = copy.deepcopy(event)
            decision = process.apply(event)
            self.assertFalse(decision.accepted)
            self.assertEqual(decision.result, '')
            self.assertEqual((process.products, process.equipment), before)
            self.assertEqual(event, original)
        decision = process.apply(measure('p', '00010.0000', 'LEAK-2'))
        self.assertTrue(decision.accepted)
        self.assertEqual((decision.result, decision.value), ('PASS', '00010.0000'))
        self.assertEqual(process.products['p'].retest_counts, {'LEAK': 1})
        self.assertEqual(process.equipment['LEAK-2'].counted_results, 0)
        print('P01: three overlapping invalid inputs preserve all state and request; raw-value retest PASS')

    def test_p02_lot_restart_priority_and_rejected_restart(self):
        book = replace(BOOK, lot_tracking=True)
        process = RecipeProcess(MODELS, book)
        for pid in ('a', 'b'):
            for event in prepared(pid, book):
                self.assertTrue(process.apply(event).accepted)
            self.assertTrue(process.apply(measure(pid, '14', book=book)).accepted)
        before = copy.deepcopy((process.products, process.equipment))
        event = row('', 'EQUIP_RESTART', value='10', result='FIXED', equipment='LEAK-1', book=book)
        event['lot'] = 'L'
        self.assertEqual(process.apply(event).reason, 'REGISTER 이외의 lot은 빈칸이어야 함')
        event['lot'] = ''
        self.assertEqual(process.apply(event).reason, 'INSPECT 이외의 value는 빈칸이어야 함')
        self.assertEqual((process.products, process.equipment), before)
        event['value'] = ''
        self.assertTrue(process.apply(event).accepted)
        self.assertEqual(process.products, before[0])
        self.assertEqual(process.equipment['LEAK-1'].recent_results, ())
        print('P02: measured+lot restart validates lot before value; rejected restarts preserve state')

    def test_p03_negative_one_sided_precision_and_equivalent_specs(self):
        data = json.loads(RECIPE.read_text(encoding='utf-8-sig'))
        for body in data.values():
            for item in body['inspections']:
                item.update(lsl='-0000.000', usl=None)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'recipe.json'
            data['A']['inspections'][0]['lsl'] = '0'
            path.write_text(json.dumps(data), encoding='utf-8')
            models = load_recipe(path).models
            process = RecipeProcess(models, BOOK)
            for pid, value, expected in (('p', '-0.000', 'PASS'),
                                         ('q', '-0.' + '0' * 27 + '1', 'FAIL')):
                for event in prepared(pid):
                    self.assertTrue(process.apply(event).accepted)
                self.assertEqual(process.apply(measure(pid, value)).result, expected)
            data['A']['inspections'][0]['unit'] = 'another unit'
            path.write_text(json.dumps(data), encoding='utf-8')
            with self.assertRaisesRegex(RecipeError, '같은 검사 ID'):
                load_recipe(path)
        print('P03: signed zero and tiny negative value compared exactly; unit mismatch rejected')

    def test_p04_restarts_are_equipment_local_and_physical_order(self):
        events = []
        def add(pid, value, equipment):
            events.extend(prepared(pid))
            events.append(measure(pid, value, equipment))
        for i, value in enumerate(('10', '10', '10', '14', '14')):
            add('a' + str(i), value, 'LEAK-1')
            add('b' + str(i), '10', 'LEAK-2')
        events.append(row('', 'EQUIP_RESTART', result='NO_FAULT', equipment='LEAK-2'))
        events.append(row('', 'EQUIP_RESTART', result='FIXED', equipment='LEAK-1'))
        for i in range(4):
            add('c' + str(i), '10', 'LEAK-1')
            add('d' + str(i), '10', 'LEAK-2')
        # All seq values intentionally repeat; physical row order governs segments.
        analysis = build_analysis(events, MODELS, BOOK)
        self.assertEqual(sum(not d.accepted for d in analysis.decisions), 1)
        report = {r['equipment']: r for r in build_capability(analysis)[1:]}
        self.assertEqual((report['LEAK-1']['n'], report['LEAK-1']['subgroups']), (9, 1))
        self.assertEqual((report['LEAK-2']['n'], report['LEAK-2']['subgroups']), (9, 1))
        self.assertEqual(len(analysis.restarts), 1)
        print('P04: repeated seq; only accepted restart cuts its equipment; n=9/groups=1 for each')

    def test_p05_integer_shift_overflow_is_controlled_configuration_error(self):
        with tempfile.TemporaryDirectory() as folder:
            config = config_file(folder, {'process_cpk': 0.1, 'defect_shift_sigma': 10 ** 308,
                                          'fault_shift_sigma': {'LEAK-2': 10 ** 308}})
            out = Path(folder) / 'out.csv'
            result = cli(folder, 'src.generate', '--config', config, '--products', 20, '--out', out)
            self.assertFalse(out.exists())
            self.assertFalse(Path(str(out) + '.meta.json').exists())
            print('P05: exit=' + str(result.returncode) + '; OverflowError=' + str('OverflowError' in result.stderr))
            self.assertEqual(result.returncode, 2, result.stderr)

    def test_p06_huge_finite_draw_is_controlled_digit_limit_error(self):
        with tempfile.TemporaryDirectory() as folder:
            config = config_file(folder, {'process_cpk': 1e-307, 'error_rate': 0})
            out = Path(folder) / 'out.csv'
            result = cli(folder, 'src.generate', '--config', config, '--products', 20, '--out', out)
            self.assertFalse(out.exists())
            self.assertFalse(Path(str(out) + '.meta.json').exists())
            print('P06: exit=' + str(result.returncode) + '; InvalidOperation=' + str('InvalidOperation' in result.stderr))
            self.assertEqual(result.returncode, 2, result.stderr)

    def test_p07_t108_settings_must_not_alias_one_fixture(self):
        spec = importlib.util.spec_from_file_location('measurement_review014', ROOT / 'tests/test_measurement.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        helper = module.GeneratorTests()
        with tempfile.TemporaryDirectory() as folder:
            # Exact first two calls and deferred reads used by test_t108.
            paths = (helper.setup_paths(folder, {'process_cpk': 0}),
                     helper.setup_paths(folder, {'fault_shift_sigma': {'LEAK-2': -1}}))
            values = [json.loads(p.read_text(encoding='utf-8')) for p in paths]
            print('P07: saved process_cpk values=' + repr([v['process_cpk'] for v in values]) +
                  '; distinct fixture paths=' + str(len(set(paths))))
            self.assertEqual(values[0]['process_cpk'], 0,
                             'The first T108 case was overwritten before execution')

    def test_p08_capability_small_variation_retains_decimal_precision(self):
        values = ['999999999999999.00000000000000' + str(i) for i in (1, 2, 3, 4, 5)] * 25
        result = capability([values], '999999999999998', '1000000000000000')
        self.assertEqual((result.n, result.subgroups), (125, 25))
        self.assertGreater(result.sigma_within, Decimal(0))
        self.assertIsNotNone(result.cpk)
        self.assertNotIn('E', show(result.cpk))
        self.assertEqual(show(Decimal('-0.000049')), '0.0000')
        print('P08: high-offset tiny variation retains nonzero sigma and fixed-point Cpk')


class PreservationTests(unittest.TestCase):
    def success(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)

    def compare_reports(self, folder, expected_names):
        paths = {p.name: p for p in (Path(folder) / 'reports').glob('*.csv')}
        self.assertEqual(set(paths), set(expected_names))
        for name, path in paths.items():
            self.assertEqual(path.read_bytes(), (ROOT / 'reports' / name).read_bytes(), name)
        return len(paths)

    def test_p09_protected_tracked_files_are_unchanged(self):
        names = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', BASE, '--',
                                         'tests', 'src/rules.py', 'recipes', 'data', 'reports'], cwd=ROOT,
                                        text=True, encoding='utf-8').splitlines()
        for name in names:
            old = subprocess.check_output(['git', 'rev-parse', BASE + ':' + name], cwd=ROOT, text=True).strip()
            actual = subprocess.check_output(['git', 'hash-object', '--', name], cwd=ROOT, text=True).strip()
            self.assertEqual(actual, old, name)
        self.assertEqual(sum(n.startswith('tests/test_') for n in names), 9)
        print('P09: protected tracked files unchanged=' + str(len(names)) + '; legacy test files=9')

    def test_p10_all_legacy_samples_and_generated_reports(self):
        with tempfile.TemporaryDirectory() as folder:
            for name, recipe, equipment, extra in (
                ('sample_events', None, None, ()),
                ('sample_events_v2', 'lamp_models.json', None, ()),
                ('sample_events_retest', 'lamp_models_retest.json', None, ()),
                ('sample_events_equipment', 'lamp_models_retest.json', 'equipment.json', ()),
                ('sample_events_restart', 'lamp_models_retest.json', 'equipment_restart.json', ('--summary', '--trace', 'f')),
                ('sample_events_lot', 'lamp_models_retest.json', 'equipment_lot.json', ('--summary', '--containment'))):
                args = [ROOT / 'data' / (name + '.csv')]
                if recipe:
                    args += ['--recipe', ROOT / 'recipes' / recipe]
                if equipment:
                    args += ['--equipment', ROOT / 'recipes' / equipment]
                self.success(cli(folder, 'src.main', *args, *extra))
            generated = Path(folder) / 'gen_seed42.csv'
            generate(42, 500, generated, ROOT / 'recipes/generator.json')
            for suffix in ('', '.meta.json'):
                self.assertEqual(Path(str(generated) + suffix).read_bytes(),
                                 (ROOT / 'data/generated' / ('gen_seed42.csv' + suffix)).read_bytes())
            self.success(cli(folder, 'src.main', generated, '--recipe', ROOT / 'recipes/lamp_models_retest.json',
                             '--equipment', ROOT / 'recipes/equipment_generated.json', '--summary',
                             '--trace', 'GEN_0005', '--trace', 'GEN_0030'))
            expected = [p.name for p in (ROOT / 'reports').glob('*.csv')
                        if not p.name.startswith(('eval_', 'gen_measured_', 'sample_events_measured_'))]
            print('P10: legacy reports byte-identical=' + str(self.compare_reports(folder, expected)) + '; CSV/meta=2')

    def test_p11_all_legacy_evaluation_reports(self):
        with tempfile.TemporaryDirectory() as folder:
            for out, config, seeds, rules, extra in (
                ('eval_dev', 'generator_restart.json', '0-99', '3:2,5:2,5:3,10:3,10:4,20:4', ()),
                ('eval_holdout', 'generator_restart.json', '1000-1099', '3:2', ('--holdout',)),
                ('eval_baseline', 'generator.json', '0-99', '3:2', ('--holdout',))):
                self.success(cli(folder, 'src.evaluate', '--config', ROOT / 'recipes' / config,
                                 '--seeds', seeds, '--rules', rules, '--out', out, *extra))
                print('P11 completed: ' + out, flush=True)
            for setting in ('lot', 'lot_clustered'):
                config = ROOT / 'recipes' / ('generator_' + setting + '.json')
                dev = 'eval_' + setting + '_dev'
                self.success(cli(folder, 'src.evaluate', '--containment', '--config', config,
                                 '--seeds', '0-99', '--rules', '3:2', '--out', dev))
                self.success(cli(folder, 'src.evaluate', '--containment', '--config', config,
                                 '--seeds', '1000-1099', '--rules', '3:2', '--out',
                                 'eval_' + setting + '_holdout', '--holdout', '--selected-from',
                                 Path(folder) / 'reports' / (dev + '_containment.csv')))
                print('P11 completed: ' + setting, flush=True)
            expected = [p.name for p in (ROOT / 'reports').glob('eval_*.csv')]
            print('P11: legacy evaluation reports byte-identical=' + str(self.compare_reports(folder, expected)))

    def test_p12_saved_measured_reports_match_replay(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'gen_measured_seed42.csv'
            generate(42, 500, source, CONFIG)
            for suffix in ('', '.meta.json'):
                self.assertEqual(Path(str(source) + suffix).read_bytes(),
                                 (ROOT / 'data/generated' / (source.name + suffix)).read_bytes())
            for path, trace, extra in ((source, 'GEN_0005', ('--containment',)),
                                        (ROOT / 'data/sample_events_measured.csv', 'c', ())):
                self.success(cli(folder, 'src.main', path, '--recipe', RECIPE, '--equipment', EQUIPMENT,
                                 '--summary', '--capability', '--trace', trace, *extra))
            expected = [p.name for p in (ROOT / 'reports').glob('*.csv')
                        if p.name.startswith(('gen_measured_', 'sample_events_measured_'))]
            print('P12: measured reports byte-identical=' + str(self.compare_reports(folder, expected)) + '; CSV/meta=2')


if __name__ == '__main__':
    unittest.main()

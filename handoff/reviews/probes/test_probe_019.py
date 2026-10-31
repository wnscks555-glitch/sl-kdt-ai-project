"""Review 019: independent boundary and integration probes; writes only inside tempfile.

Run: py -m unittest handoff/reviews/probes/test_probe_019.py
The optional run_legacy_suite() only redirects subprocess 'py' to sys.executable
in this process; it neither edits tests nor changes the machine configuration.
"""
import copy
import csv
from dataclasses import replace
from decimal import Decimal, ROUND_HALF_UP, localcontext
from fractions import Fraction
import io
import json
import math
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
from unittest.mock import patch

from src import anomaly, capability, generate, line, modbus, pfmea, plc, station
from src.recipe_rules import RecipeProcess, input_columns
from src.summary import build_analysis

ROOT = Path(__file__).resolve().parents[3]
SETTINGS = anomaly.load_settings(ROOT / 'recipes/anomaly_lamp.json')
PROCESS = anomaly.load_process(SETTINGS)
CONFIG, _, RECIPE, BOOK = generate.load_setup(ROOT / 'recipes/generator_measured.json')


def read_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def dump(path, data):
    Path(path).write_text(json.dumps(data), encoding='utf-8')
    return Path(path)


def cli(module, *args, cwd):
    return subprocess.run([sys.executable, '-m', module, *map(str, args)], cwd=cwd,
                          env=dict(os.environ, PYTHONPATH=str(ROOT), PYTHONIOENCODING='utf-8',
                                   PYTHONDONTWRITEBYTECODE='1'), capture_output=True, text=True, encoding='utf-8')


def config_at(folder, **changes):
    data = copy.deepcopy(CONFIG)
    data.update(recipe=str(ROOT / 'recipes/lamp_models_measured.json'),
                equipment=str(ROOT / 'recipes/equipment_measured.json'))
    data.update(changes)
    return dump(Path(folder) / 'generator.json', data)


def event(pid, name, **fields):
    result = dict.fromkeys(input_columns(BOOK, True), '')
    result.update(seq='1', product_id=pid, event=name, **fields)
    return result


class Rig:
    def __init__(self):
        self.table = modbus.Table()
        self.controller = plc.Plc(self.table, station.load_station(ROOT / 'recipes/plc_station.json').timing)
        self.set(clamp_open=True, guard_closed=True)

    def set(self, **signals):
        for key, value in signals.items():
            self.table.discrete[plc.INPUTS.index(key)] = value

    def scan(self, value=''):
        self.table.holding[0] = (self.table.holding[0] + 1) % 65536
        return self.controller.scan(value)

    def publish(self):
        for signals in (dict(part_present=True), dict(seated=True, direction_ok=True),
                        dict(clamp_open=False, clamp_closed=True), dict(measure_done=True),
                        dict(measure_done=False)):
            self.set(**signals)
            self.scan('-0.001')
        assert self.controller.state == plc.WAIT_JUDGE


class Probe019(unittest.TestCase):
    def test_p01_rejection_then_valid_retest_preserves_state(self):
        p = RecipeProcess(RECIPE.models, BOOK)
        for pid in ('a', 'A'):
            for row in (event(pid, 'REGISTER', model='B'), event(pid, 'P1'), event(pid, 'P2'),
                        event(pid, 'INSPECT', inspection='LEAK', equipment='LEAK-1', value='14')):
                self.assertTrue(p.apply(row).accepted)
        self.assertTrue(p.apply(event('a', 'RETEST_REQUEST', inspection='LEAK')).accepted)
        for value, equipment in (('', 'LEAK-2'), ('10', 'leak-2'), ('10', 'LEAK-1'), (' 10', 'LEAK-2')):
            before = copy.deepcopy((p.products, p.equipment))
            self.assertFalse(p.apply(event('a', 'INSPECT', inspection='LEAK', equipment=equipment, value=value)).accepted)
            self.assertEqual((p.products, p.equipment), before)
        self.assertTrue(p.apply(event('a', 'INSPECT', inspection='LEAK', equipment='LEAK-2', value='10.000')).accepted)
        self.assertEqual(p.products['a'].inspections['LEAK'], 'PASS')
        self.assertEqual(p.products['A'].inspections['LEAK'], 'FAIL')
        self.assertEqual(len(p.equipment['LEAK-2'].recent_results), 0)

    def test_p02_capability_restarts_remainders_independent(self):
        segments = [[str(8 + i % 5) for i in range(129)], ['13'] * 4,
                    [str(9 + i % 3) for i in range(131)]]
        actual = capability.capability(segments, '7', '13')
        with localcontext() as ctx:
            ctx.prec = 100
            values = [Decimal(v) for s in segments for v in s]
            groups = [list(map(Decimal, s[i:i+5])) for s in segments for i in range(0, len(s)-4, 5)]
            mean = sum(values) / len(values)
            sd = (sum((v-mean)**2 for v in values) / (len(values)-1)).sqrt()
            center = sum(sum(g)/5 for g in groups) / len(groups)
            within = sum(max(g)-min(g) for g in groups) / len(groups) / Decimal('2.326')
            self.assertEqual(actual.cpk, min(13-center, center-7)/(3*within))
            self.assertEqual(actual.ppk, min(13-mean, mean-7)/(3*sd))
            self.assertEqual((actual.n, actual.subgroups), (264, 51))

    def test_p03_equal_numeric_specs_across_shared_loaders(self):
        with tempfile.TemporaryDirectory() as td:
            recipe = json.loads((ROOT / 'recipes/lamp_models_measured.json').read_text(encoding='utf-8'))
            for item in recipe['B']['inspections']:
                item.update(lsl='7', usl='13')
            path = config_at(td, recipe=str(dump(Path(td)/'recipe.json', recipe)))
            generate.load_setup(path)  # the shared recipe contract explicitly accepts numeric equality
            for name, loader in (
                    ('anomaly', lambda: anomaly.load_process(replace(SETTINGS, generator=path))),
                    ('station', lambda: station.load_values(replace(station.load_station(ROOT/'recipes/plc_station.json'),
                                                                   generator=path), 42, 20))):
                with self.subTest(loader=name):
                    try:
                        loader()
                    except ValueError as error:
                        self.fail('equal numeric specifications were rejected: ' + str(error))

    def test_p04_generator_extreme_errors_and_rounding(self):
        with tempfile.TemporaryDirectory() as td:
            for changes in (dict(process_cpk=.1, defect_shift_sigma=10**308, fault_shift_sigma={'LEAK-2':10**308}),
                            dict(process_cpk=1e-307, error_rate=0)):
                result = cli('src.generate', '--config', config_at(td, **changes), '--products', 20,
                             '--out', Path(td)/'out.csv', cwd=td)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertNotIn('Traceback', result.stderr)
                self.assertFalse((Path(td)/'out.csv').exists())
        for value, expected in ((-0.0005, '-0.001'), (1e-300, '0.000'), (13.0005, '13.001')):
            self.assertEqual(generate.confirm_value(value), expected)

    def test_p05_report_reference_missing_cell_and_empty(self):
        with tempfile.TemporaryDirectory() as td:
            directory = Path(td)/'reports'; directory.mkdir()
            path = directory/'probe.csv'
            provenance = ''.join('provenance,'+name+',x,\n' for name in pfmea.REQUIRED_PROVENANCE)
            for tail, accepted in (('method,m,x\n', False), ('method,m,x,\n', True)):
                path.write_text('section,method,value,capture_rate\n'+provenance+tail, encoding='utf-8')
                if accepted:
                    self.assertEqual(pfmea.resolve_reference('report:probe:m:capture_rate', td).report[0], '')
                else:
                    with self.assertRaises(ValueError):
                        pfmea.resolve_reference('report:probe:m:capture_rate', td)
        self.assertEqual(pfmea.effect_result(Fraction(2, 3), '>=', '0.6666666666666666666666666667'), '미충족')

    def test_p06_line_zero_buffer_repair_and_escape(self):
        stages = [line.SimStation('M', 1, {'A':1000}), line.SimStation('I', 2, {'A':10000}, 'LEAK')]
        routes = [line.Route(str(i), 'A', {'LEAK':1}, defective=i==0,
                             stops=frozenset({'LEAK'}) if i<2 else frozenset()) for i in range(4)]
        r = line.simulate(stages, routes, 0, 100000)
        self.assertEqual((r.end, r.good, r.passed, r.escaped), (122000, 3, 4, 1))
        self.assertEqual(line.uph(r.good, r.end), Fraction(10800000, 122000))
        self.assertEqual((r.work['I'], r.repair['I']), (40000, 200000))

    def test_p07_line_long_seconds_end_to_end(self):
        with tempfile.TemporaryDirectory() as td:
            data=json.loads((ROOT/'recipes/line_lamp.json').read_text(encoding='utf-8'))
            data.update(generator=str(ROOT/'recipes/generator_measured.json'),
                        period_seconds='123456789012345678901234567890.123')
            result=cli('src.line',dump(Path(td)/'line.json',data),'--seeds','0-0','--holdout-seeds','1000-1000',
                       '--products',1,cwd=td)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertNotIn('Traceback',result.stderr)

    def test_p08_plc_reset_and_alarm_priority_over_valid_pair(self):
        r=Rig(); r.publish()
        r.table.holding[1:3]=[1,1]; r.set(guard_closed=False)
        self.assertEqual(r.scan(),plc.ALARM)
        self.assertFalse(r.controller.outputs['gate_ok'])
        r.table.coils[8]=True; self.assertEqual(r.scan(),plc.ALARM)
        r.table.coils[9]=True; r.scan()
        r.set(guard_closed=True,clamp_closed=False,clamp_open=True,part_present=False)
        r.table.coils[8]=False; r.scan(); r.table.coils[8]=True
        self.assertEqual(r.scan(),plc.IDLE)
        self.assertEqual(r.table.input_registers[2:5],[1,0,0])
        self.assertEqual(r.table.holding[1:3],[0,0])
        self.assertTrue(r.table.coils[8] and r.table.coils[9])

    def test_p09_repeated_rejected_pair_after_intervening_pair(self):
        r=Rig(); r.publish(); rejected=[]
        for pair in ([2,1],[1,3],[2,1],[0,0],[1,3]):
            r.table.holding[1:3]=pair; r.scan(); rejected.extend(r.controller.events)
        self.assertEqual(len(rejected),2,repr(rejected))
        r.table.holding[1:3]=[1,2]
        self.assertEqual(r.scan(),plc.UNCLAMP)

    def test_p10_modbus_every_split_before_damage_and_pair_atomicity(self):
        def frame(tid,pdu,protocol=0):
            return struct.pack('>HHHB',tid,protocol,len(pdu)+1,1)+pdu
        stream=frame(1,bytes.fromhex('0600000007'))+frame(2,bytes.fromhex('10000100020400010002'))
        stream+=frame(3,bytes.fromhex('0600000009'),1)+frame(4,bytes.fromhex('060000000B'))
        for cut in range(1,len(stream)):
            b=modbus.FrameBuffer(); table=modbus.Table(); replies=[]
            for chunk in (stream[:cut],stream[cut:]):
                replies.extend(modbus.respond(f,table) for f in b.feed(chunk))
                if b.damaged: break
            self.assertEqual((table.holding[:3],len(replies)),([7,1,2],2))
            before=list(table.holding)
            self.assertEqual(modbus.handle_pdu(bytes.fromhex('100000000204000B000C'),table),b'\x90\x02')
            self.assertEqual(table.holding,before)

    def test_p11_modbus_total_response_deadline(self):
        listener=socket.socket(); listener.bind(('127.0.0.1',0)); listener.listen()
        def serve():
            conn,_=listener.accept()
            with conn:
                request=conn.recv(1024)
                reply=request[:4]+struct.pack('>H',5)+b'\x01\x03\x02\x00\x07'
                try:
                    for byte in reply:
                        time.sleep(.15)
                        conn.sendall(bytes([byte]))
                except OSError:
                    pass
        worker=threading.Thread(target=serve,daemon=True); worker.start()
        client=modbus.ModbusClient(listener.getsockname()[1],timeout=1.0)
        start=time.monotonic()
        try:
            with self.assertRaises(modbus.ModbusTimeout):
                client.read_registers(modbus.READ_HOLDING,0,1)
        finally:
            print('P11 total_response_seconds=%.3f'%(time.monotonic()-start),flush=True)
            client.close(); worker.join(3); listener.close()

    def test_p12_anomaly_metrics_independent_boundary_exposure(self):
        outcomes=[(0,None,4),(0,None,None),(1,6,5),(1,6,6),(2,8,None),(2,8,10)]
        m=anomaly.measure_alarms(outcomes,12,5)
        # exposures: 1+8+2+2+4+4; costs: 6+0+4+2; suspect: 6+1+4+3.
        self.assertEqual((m.alarms,m.exposure,m.detected,m.early,m.missed,m.cost,m.suspect),(2,21,2,1,1,12,14))
        self.assertEqual(m.false_per_1000,Fraction(2000,21))
        self.assertEqual(m.mean_cost,3)
        self.assertEqual(m.suspect_output,Fraction(7,2))

    def test_p13_anomaly_holdout_changes_not_selection_or_training(self):
        cfg=replace(SETTINGS,length=35,onset_min=15,onset_max=25,iterations=10,
                    splits={'train':range(6),'validation':range(100,106),'holdout':range(200,206)},
                    min_detection=0,min_shift_detection=0,false_limit=1000)
        splits={name:anomaly.build_split(seeds,cfg,PROCESS) for name,seeds in cfg.splits.items()}
        model=anomaly.fit_model(splits['train'],cfg)
        first=anomaly.compare(splits,model,cfg)
        changed=dict(splits,holdout=anomaly.build_split(range(600,606),cfg,PROCESS))
        second=anomaly.compare(changed,model,cfg)
        self.assertEqual(first[1],second[1]); self.assertEqual(first[3:],second[3:])
        self.assertEqual([r for r in first[0] if r['section'].startswith('validation')],
                         [r for r in second[0] if r['section'].startswith('validation')])
        self.assertNotEqual([r for r in first[0] if r['section']=='holdout'],
                            [r for r in second[0] if r['section']=='holdout'])
        self.assertEqual(model,anomaly.fit_model(changed['train'],cfg))

    def test_p14_review018_fixes_numeric_rule_replay(self):
        with tempfile.TemporaryDirectory() as td:
            raw=json.loads((ROOT/'recipes/anomaly_lamp.json').read_text(encoding='utf-8'))
            for key in ('min_detection','ewma_lambda','false_limit','learning_rate'):
                data=dict(raw,**{key:10**400})
                r=cli('src.anomaly',dump(Path(td)/'a.json',data),cwd=td)
                self.assertEqual(r.returncode,3,r.stderr); self.assertIn('$.'+key,r.stderr)
                self.assertNotIn('Traceback',r.stderr)
            self.assertFalse((Path(td)/'reports').exists())
        sample=anomaly.Scenario(1,1,10,['10']*20,[False]*9+[True,True]+[False]*9,[],[])
        self.assertEqual(anomaly.rule_outcomes([sample],SETTINGS),[(1,10,10)])
        for a,expected in ((14,(14,14)),(15,(15,15)),(19,(15,19))):
            self.assertEqual(anomaly.replay_range(20,a,10,40),expected)

    def test_p15_model_csv_replay_independent_probability(self):
        entries=read_csv(ROOT/'reports/anomaly_lamp_model.csv')
        model={(r['section'],r['name']):r['value'] for r in entries}
        replay=read_csv(ROOT/'reports/anomaly_lamp_replay.csv')
        worst=0
        for row in replay:
            raw=list(map(float,row['window_values'].split()))
            x=[(v-PROCESS.center)/PROCESS.sigma for v in raw]; n=len(x); mean=sum(x)/n
            features=[mean,math.sqrt(sum((v-mean)**2 for v in x)/(n-1)),max(x),
                      sum((i-(n-1)/2)*v for i,v in enumerate(x))/sum((i-(n-1)/2)**2 for i in range(n)),
                      .2*x[-1]+.8*float(row['ewma_prev']),sum(v<7 or v>13 for v in raw)/n]
            z=float(model['bias','bias'])
            for name,value in zip(anomaly.FEATURES,features):
                z+=(value-float(model['mean',name]))/float(model['scale',name])*float(model['weight',name])
            probability=1/(1+math.exp(-z)); error=abs(probability-float(row['p'])); worst=max(worst,error)
            self.assertLess(error,1e-9)
        print('P15 replay_rows=%d max_probability_error=%.12g'%(len(replay),worst),flush=True)

    def test_p16_submitted_anomaly_metrics_independent(self):
        model={(r['section'],r['name']):r['value'] for r in read_csv(ROOT/'reports/anomaly_lamp_model.csv')}
        report=read_csv(ROOT/'reports/anomaly_lamp_methods.csv')
        for split in ('validation','holdout'):
            scenarios=anomaly.build_split(SETTINGS.splits[split],SETTINGS,PROCESS)
            for method in anomaly.METHODS:
                target=next(r for r in report if r['section']==split and r['method']==method)
                threshold=Decimal(target['threshold']) if target['threshold'] else None
                detected=early=missed=exposure=false=cost=suspect=alarms=0
                for s in scenarios:
                    alarm=None
                    for index,features in enumerate(s.features):
                        t=index+9
                        if method=='rule_3_2':
                            hit=sum(s.fails[max(0,t-2):t+1])>=2
                        else:
                            score=features[0]
                            if method=='logistic':
                                z=float(model['bias','bias'])
                                for name,value in zip(anomaly.FEATURES,features):
                                    z+=(value-float(model['mean',name]))/float(model['scale',name])*float(model['weight',name])
                                score=1/(1+math.exp(-z))
                            hit=Decimal(repr(score)).quantize(Decimal('.0001'),rounding=ROUND_HALF_UP)>=threshold
                        if hit:
                            alarm=t; break
                    alarms+=alarm is not None
                    normal_end=399 if s.onset is None else s.onset-1
                    exposure+=max(0,min(normal_end,alarm if alarm is not None else 399)-9+1)
                    false+=alarm is not None and (s.onset is None or alarm<s.onset)
                    if s.onset is not None:
                        if alarm is None:
                            missed+=1; cost+=400-s.onset; suspect+=400-s.onset
                        elif alarm<s.onset:
                            early+=1; cost+=400-s.onset; suspect+=400-s.onset
                        else:
                            detected+=1; cost+=alarm-s.onset; suspect+=alarm-s.onset+1
                fmt=lambda n,d: format((Decimal(n)/Decimal(d)).quantize(Decimal('.0001'),rounding=ROUND_HALF_UP),'f')
                self.assertEqual((target['detection_rate'],target['early'],target['missed'],target['mean_delay_cost'],target['false_per_1000']),
                                 (fmt(detected,120),str(early),str(missed),fmt(cost,120),fmt(false*1000,exposure)))
                if split=='holdout':
                    policy=next(r for r in report if r['section']=='policy' and r['method']==method)
                    self.assertEqual((policy['suspect_output'],policy['stop_minutes']),(fmt(suspect,120),fmt(alarms*10000,240)))
                print('P16',split,method,'detected',detected,'cost',cost,'false/exposure',false,exposure,flush=True)

    def test_p17_submitted_capability_from_measurement_rows(self):
        events=read_csv(ROOT/'data/generated/gen_measured_seed42.csv')
        analysis=build_analysis(events,RECIPE.models,BOOK)
        report=read_csv(ROOT/'reports/gen_measured_seed42_capability.csv')[1:]
        for target in report:
            name=target['equipment']; segments=[[]]
            for e,d in zip(events,analysis.decisions):
                if not d.accepted or e['equipment']!=name: continue
                if e['event']=='EQUIP_RESTART': segments.append([])
                elif e['event']=='INSPECT':
                    # first occurrence per product/inspection, independent of capability.equipment_segments
                    if not any(r.product_id==e['product_id'] and r.inspection==e['inspection'] and r.retest_number>0 and
                               r.seq==e['seq'] for r in analysis.all_inspections):
                        segments[-1].append(Decimal(e['value']))
            values=[v for s in segments for v in s]
            groups=[s[i:i+5] for s in segments for i in range(0,len(s)-4,5)]
            self.assertEqual((int(target['n']),int(target['subgroups'])),(len(values),len(groups)))
            if len(groups)<25: continue
            with localcontext() as ctx:
                ctx.prec=100
                center=sum(sum(g)/5 for g in groups)/len(groups)
                within=sum(max(g)-min(g) for g in groups)/len(groups)/Decimal('2.326')
                mean=sum(values)/len(values)
                sd=(sum((x-mean)**2 for x in values)/(len(values)-1)).sqrt()
                fmt=lambda x: format(x.quantize(Decimal('.0001'),rounding=ROUND_HALF_UP),'f')
                self.assertEqual((target['cpk'],target['ppk']),(fmt(min(13-center,center-7)/(3*within)),fmt(min(13-mean,mean-7)/(3*sd))))
        print('P17 independent capability rows=',len(report),flush=True)

    def test_p18_baseline_blobs_preserved(self):
        def tree(revision):
            raw=subprocess.check_output(['git','ls-tree','-r',revision],cwd=ROOT).decode('utf-8')
            return {path:head.split()[2] for head,path in (s.split('\t',1) for s in raw.splitlines())}
        base,head=tree('bb73241'),tree('HEAD')
        protected={p:h for p,h in base.items() if p.startswith(('tests/','recipes/','data/','reports/')) or p=='src/rules.py'}
        self.assertEqual({p:head.get(p) for p in protected},protected)
        print('P18 preserved baseline blobs=',len(protected),'reports=',sum(p.startswith('reports/') for p in protected),flush=True)

    def test_p19_pfmea_counts_from_raw_runs(self):
        totals={name:[0,0] for name in pfmea.METRICS}
        for seed in range(30):
            g=generate.Generator(seed,CONFIG,RECIPE.models,BOOK)
            analysis=build_analysis(g.normal_events(500),RECIPE.models,BOOK)
            bad=set(g.defective_products); faulty=set(CONFIG['fault_shift_sigma'])
            products=analysis.process.products
            first={}
            attempts={}
            stopped={name:[] for name in BOOK.equipment}
            for index,(e,d) in enumerate(zip(analysis.events,analysis.decisions),1):
                if not d.accepted or e['event']!='INSPECT': continue
                key=(e['product_id'],e['inspection'])
                attempts.setdefault(key,[]).append((e['equipment'],e['value'],index))
                first.setdefault(key,(e['equipment'],e['value'],index))
            for s in analysis.stop_history: stopped[s.equipment].append(s.row_index)
            update=lambda key,n,d: (totals[key].__setitem__(0,totals[key][0]+n),totals[key].__setitem__(1,totals[key][1]+d))
            update('defect_escape',sum(products[p].status==pfmea.COMPLETED for p in bad),len(bad))
            normal=set(products)-bad
            update('normal_reject',sum(products[p].status in ('보류','폐기') for p in normal),len(normal))
            for metric,inspection in (('all_defect_first_fail',None),('leak_defect_first_fail','LEAK')):
                observations=[v for (p,i),(eq,v,idx) in first.items() if p in bad and (inspection is None or i==inspection)]
                update(metric,sum(Decimal(v)<7 or Decimal(v)>13 for v in observations),len(observations))
            retested=[values for (p,i),values in attempts.items() if p in bad and i=='LEAK' and len(values)>1]
            update('leak_defect_retest_pass',sum(7<=Decimal(values[-1][1])<=13 for values in retested),len(retested))
            found=[name for name in faulty if stopped[name]]
            update('fault_stop_run',len(found),len(faulty)); update('fault_no_stop_run',len(faulty)-len(found),len(faulty))
            update('fault_stop_delay',sum(sum(eq==name and index<=stopped[name][0] for eq,v,index in first.values()) for name in found),len(found))
            update('normal_stop_rate',sum(len(stops) for name,stops in stopped.items() if name not in faulty),
                   sum(eq not in faulty for eq,v,index in first.values()))
        report=read_csv(ROOT/'reports/pfmea_lamp_report.csv')
        for row in report:
            if row['section']=='metric':
                name=row['reference'].split(':')[1]
                self.assertEqual(totals[name],[int(row['numerator']),int(row['denominator'])])
        print('P19 PFMEA raw totals='+repr(totals),flush=True)

    def test_p20_line_selected_uph_raw_numerator_denominator(self):
        plan=line.load_line(ROOT/'recipes/line_lamp.json',RECIPE.models)
        weights={k:Fraction(str(v)) for k,v in CONFIG['model_weights'].items()}
        ratios={k:v/sum(weights.values()) for k,v in weights.items()}
        balance=line.optimal_balance(plan.elements,ratios,plan.net,plan.demand)
        combo={'LEAK':2,'LIGHT':1,'FINAL':1}
        stages=line.build_stations(plan,balance,combo)
        report=read_csv(ROOT/'reports/line_lamp_compare.csv')
        for section,seeds in (('development',range(30)),('holdout',range(1000,1030))):
            elapsed=good=passed=escaped=0
            for seed in seeds:
                routes=line.product_routes(CONFIG,RECIPE,BOOK,seed,500)
                r=line.simulate(stages,routes,plan.buffer_units,plan.repair)
                elapsed+=r.end
                good+=sum(route.completed and not route.defective for route in routes)
                passed+=sum(route.completed for route in routes)
                escaped+=sum(route.completed and route.defective for route in routes)
                for s in stages:
                    self.assertLessEqual(r.work[s.id]+r.blocked[s.id]+r.repair[s.id],s.servers*r.end)
            row=next(r for r in report if r['section']==section and r['combo']=='2-1-1')
            fmt=lambda n: format((Decimal(n)*3600000/Decimal(elapsed)).quantize(Decimal('.0001'),rounding=ROUND_HALF_UP),'f')
            self.assertEqual((row['good_uph'],row['pass_uph'],int(row['escaped'])),(fmt(good),fmt(passed),escaped))
            print('P20',section,'good',good,'passed',passed,'escaped',escaped,'elapsed_ms',elapsed,'good_uph',fmt(good),flush=True)


def run_legacy_suite():
    original=subprocess.Popen
    def redirected(args,*pos,**kwargs):
        if isinstance(args,(list,tuple)) and args and args[0]=='py':
            args=[sys.executable,*args[1:]]
        return original(args,*pos,**kwargs)
    with patch('subprocess.Popen',redirected):
        return unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.discover(str(ROOT/'tests')))


if __name__=='__main__':
    unittest.main()

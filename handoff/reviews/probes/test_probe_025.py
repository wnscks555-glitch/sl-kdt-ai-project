"""Review 025: independent checks; all generated output stays in TemporaryDirectory.

Run with the installed Python 3.12 if the Windows py launcher is unavailable.
No source/test fixtures are modified. P20 reruns the README report pipeline.
"""
import ast
import copy
import csv
from dataclasses import replace
from decimal import Decimal, localcontext, ROUND_HALF_UP
from fractions import Fraction as F
from html.parser import HTMLParser
import io
import json
import math
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from src import anomaly, dashboard, incident, msa, spc
from src.station import load_station

ROOT = Path(__file__).resolve().parents[3]
REPORTS = ROOT / 'reports'
ENV = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1')


def rows(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def save_rows(path, data):
    with Path(path).open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(data[0]))
        writer.writeheader()
        writer.writerows(data)


def show(value, digits=4):
    if value is None:
        return ''
    with localcontext() as context:
        context.prec = 500
        v = Decimal(value.numerator) / Decimal(value.denominator) if isinstance(value, F) else Decimal(str(value))
        return format(v.quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP), 'f')


def cli(module, args, cwd):
    return subprocess.run([sys.executable, '-B', '-m', module, *map(str, args)], cwd=cwd,
                          env=dict(ENV, PYTHONPATH=str(ROOT)), capture_output=True, encoding='utf-8', timeout=600)


def inputs(folder):
    dest = Path(folder) / 'reports'
    dest.mkdir()
    for name in list(dashboard.INPUTS) + list(dashboard.TEXT_INPUTS) + [
            'plc_station_%s.csv' % name for name in dashboard.SCENARIOS]:
        shutil.copyfile(REPORTS / name, dest / name)
    return dest


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts = 0
        self.cells = []
        self.in_cell = False
        self.text = ''

    def handle_starttag(self, tag, attrs):
        self.scripts += tag == 'script'
        if tag == 'td':
            self.in_cell, self.text = True, ''

    def handle_data(self, data):
        if self.in_cell:
            self.text += data

    def handle_endtag(self, tag):
        if tag == 'td':
            self.cells.append(self.text)
            self.in_cell = False


def chart_reference(values, center, sigma, tuning, first=9, method='cusum'):
    """Direct recurrence, independent of spc chart classes."""
    z, plus, minus, last_plus, last_minus = center, 0., 0., -1, -1
    q, alarm, change = [], None, None
    width = 0.
    for t, x in enumerate(values):
        z = tuning.ewma_lambda * x + (1-tuning.ewma_lambda)*z
        width = tuning.ewma_l*sigma*math.sqrt(tuning.ewma_lambda/(2-tuning.ewma_lambda)
                                             * (1-(1-tuning.ewma_lambda)**(2*(t+1))))
        plus = max(0., plus+x-center-tuning.cusum_k*sigma)
        minus = max(0., minus-x+center-tuning.cusum_k*sigma)
        if plus == 0:
            last_plus = t
        if minus == 0:
            last_minus = t
        if t >= first:
            hit = abs(z-center) > width if method == 'ewma_chart' else max(plus, minus) > tuning.cusum_h*sigma
            if hit:
                alarm = t
                change = (last_plus if plus > tuning.cusum_h*sigma else last_minus)+1
                break
    return alarm, change


class Probe025(unittest.TestCase):
    def test_p01_msa_extreme_guard_and_cpk(self):
        for sign in (1, -1):
            lo, hi = ('7', '13') if sign == 1 else ('-13', '-7')
            expected = (Decimal('7.001'), Decimal('12.999')) if sign == 1 else (Decimal('-12.999'), Decimal('-7.001'))
            self.assertEqual(msa.acceptance_limits(lo, hi, '0.'+'0'*34+'1', .1), expected)
            self.assertIsNone(msa.acceptance_limits(lo, hi, '1'+'0'*40, .1))
        for ratio in (0, .5, 2):
            self.assertAlmostEqual(msa.observed_cpk(1e200, 1e-200, ratio*1e-200)/1e200,
                                   1/math.sqrt(1+ratio*ratio))
        self.assertEqual(msa._text(1e200), '1'+'0'*200+'.0000')
        print('P01 exact inward limits, large guard, Cpk 1e200: OK')

    def test_p02_independent_anova_from_submitted_study(self):
        report = {r['gauge']: r for r in rows(REPORTS/'msa_lamp_grr.csv')}
        study = rows(REPORTS/'msa_lamp_study.csv')
        for gauge, output in report.items():
            data = {(int(r['part']), int(r['operator']), int(r['trial'])): F(r['value'])
                    for r in study if r['gauge'] == gauge}
            p, o, n = 10, 3, 3
            grand = sum(data.values())/len(data)
            pm = {i: sum(v for (a,b,c),v in data.items() if a==i)/(o*n) for i in range(1,p+1)}
            om = {j: sum(v for (a,b,c),v in data.items() if b==j)/(p*n) for j in range(1,o+1)}
            cm = {(i,j): sum(v for (a,b,c),v in data.items() if (a,b)==(i,j))/n
                  for i in pm for j in om}
            ss = [o*n*sum((v-grand)**2 for v in pm.values()), p*n*sum((v-grand)**2 for v in om.values()),
                  n*sum((v-pm[i]-om[j]+grand)**2 for (i,j),v in cm.items()),
                  sum((v-cm[i,j])**2 for (i,j,k),v in data.items())]
            self.assertEqual(sum(ss), sum((v-grand)**2 for v in data.values()))
            df = [9,2,18,60]
            ms = [s/d for s,d in zip(ss,df)]
            # Integer beta CDF via binomial sum, independent of continued fractions.
            x = float(F(60)/(60+18*ms[2]/ms[3]))
            tail = sum(math.comb(38,j)*x**j*(1-x)**(38-j) for j in range(30,39))
            pooled = tail > .25
            err = (ss[2]+ss[3])/78 if pooled else ms[3]
            term = err if pooled else ms[2]
            variances = [err, max(F(0),(ms[1]-term)/30), F(0) if pooled else max(F(0),(ms[2]-ms[3])/3),
                         max(F(0),(ms[0]-term)/9)]
            grr2, pv2 = sum(variances[:3]), variances[3]
            computed = dict(zip(('ss_part','ss_op','ss_int','ss_e'),ss))
            computed.update(dict(zip(('var_e','var_op','var_int','var_part'),variances)))
            computed['pct_grr'] = 100*math.sqrt(grr2/(grr2+pv2))
            computed['pct_tolerance'] = 100*math.sqrt(grr2)
            for name,value in computed.items():
                self.assertEqual(show(value),output[name],(gauge,name))
            self.assertEqual(show(tail,6),output['p_int'])
            self.assertEqual(str(math.floor(1.41*math.sqrt(pv2/grr2))),output['ndc'])
            print('P02',gauge,'pct_grr',show(computed['pct_grr']),'p_int',show(tail,6))
        # Nonpooled, large offset, negative cells: exact SS decomposition remains invariant.
        base = [[['-4','-3'],['2','3']],[['2','3'],['-4','-3']],[['7','8'],['-8','-7']]]
        result = msa.anova(base)
        moved = msa.anova([[[str(F(v)*7+10**25) for v in cell] for cell in row] for row in base])
        for name in ('ss_part','ss_op','ss_int','ss_e','var_e','var_op','var_int','var_part'):
            self.assertEqual(getattr(moved,name),49*getattr(result,name))

    def test_p03_guard_denominators_and_holdout_isolation(self):
        all_rows = rows(REPORTS/'msa_lamp_guard.csv')
        for r in all_rows:
            for num,den,out in [('false_accepts','true_defects','false_accept'),('false_rejects','true_good','false_reject')]:
                if r[num] and r[den]:
                    self.assertEqual(show(F(int(r[num]),int(r[den]))) if int(r[den]) else '',r[out])
        settings = msa.load_settings(ROOT/'recipes/msa_lamp.json')
        process = anomaly.load_process(settings)
        settings = replace(settings, products=37, dev_seeds=range(7,10), holdout_seeds=range(101,103))
        first = msa.guard_gauge('good',settings.gauges['good'],.1,settings,process)
        second = msa.guard_gauge('good',settings.gauges['good'],.1,
                                 replace(settings,holdout_seeds=range(701,704)),process)
        keep = lambda rs: [r for r in rs if r['section'] in ('development','selection')]
        self.assertEqual(keep(first),keep(second))
        # Unbalanced sample: denominator must be each truth class, not all five products.
        pairs = [('13.100','12.999'),('13.100','13.100'),('13.100','13.100'),('10.000','13.001'),('7.000','7.000')]
        tally = msa.Tally()
        tally.add(pairs,process.item,(Decimal('7'),Decimal('13')))
        self.assertEqual((tally.false_accept,tally.false_reject),(F(1,3),F(1,2)))
        print('P03 report denominators, 3:2 truth classes, changed holdout: OK')

    def test_p04_spc_independent_all_report_metrics(self):
        settings = spc.load_settings(ROOT/'recipes/spc_lamp.json')
        base = anomaly.load_settings(settings.anomaly)
        process = anomaly.load_process(base)
        splits = {name:anomaly.build_split(seeds,base,process) for name,seeds in base.splits.items()}
        groups = []
        for s in splits['train']:
            if s.onset is None:
                x = [(float(v)-process.center)/process.sigma for v in s.values]
                groups.extend(x[i:i+5] for i in range(0,len(x)-4,5))
        center = sum(sum(g)/5 for g in groups)/len(groups)
        rbar = sum(max(g)-min(g) for g in groups)/len(groups)
        sigma, half = rbar/2.326, .577*rbar
        reported = rows(REPORTS/'spc_lamp_methods.csv')
        limits = {r['name']:r['value'] for r in reported if r['section']=='limits'}
        for key,value in {'xbarbar':center,'rbar':rbar,'sigma_hat':sigma,'ucl_x':center+half,
                          'lcl_x':center-half,'ucl_r':2.114*rbar,'sigma_xbar':half/3,'subgroups':len(groups)}.items():
            self.assertEqual(repr(value),limits[key])
        for section in ('validation','holdout'):
            for method in spc.METHODS:
                outcomes=[]
                for s in splits[section]:
                    x=[(float(v)-process.center)/process.sigma for v in s.values]
                    if method in ('ewma_chart','cusum'):
                        alarm,_=chart_reference(x,center,sigma,settings.tuning,base.window-1,method)
                    else:
                        q=[]; alarm=None
                        for end in range(4,len(x),5):
                            group=x[end-4:end+1]; mean=sum(group)/5
                            q.append((mean-center)/(half/3))
                            hit=abs(mean-center)>half or max(group)-min(group)>2.114*rbar
                            if method=='xbar_we':
                                for count,need,edge in ((3,2,2),(5,4,1),(8,8,0)):
                                    hit |= len(q)>=count and any(sum(sign*v>edge for v in q[-count:])>=need for sign in (-1,1))
                            if end>=base.window-1 and hit:
                                alarm=end; break
                    outcomes.append((s.shift,s.onset,alarm))
                detected=early=missed=false=exposure=decisions=cost=delay=0
                runs=[]; no_alarm=0; shift_counts={}
                first=base.window-1
                for shift,onset,a in outcomes:
                    end=(base.length-1 if a is None else a) if onset is None else (a if a is not None and a<onset else onset-1)
                    exposure+=max(0,end-first+1)
                    decisions+=sum(1 for t in range(first,end+1) if method not in ('xbar_r','xbar_we') or t%5==4)
                    false+=a is not None and (onset is None or a<onset)
                    if onset is None:
                        runs.append(base.length-first if a is None else a-first+1); no_alarm+=a is None
                        continue
                    hit=a is not None and a>=onset
                    pair=shift_counts.setdefault(shift,[0,0]);pair[0]+=hit;pair[1]+=1
                    detected+=hit;early+=a is not None and a<onset;missed+=a is None
                    cost+=(a-onset) if hit else base.length-onset
                    if hit:delay+=a-onset
                count=detected+early+missed
                out=next(r for r in reported if r['section']==section and r['method']==method)
                calc={'detection_rate':F(detected,count),'mean_delay_cost':F(cost,count),
                      'mean_detected_delay':F(delay,detected) if detected else None,
                      'false_per_1000':F(1000*false,exposure),'false_per_1000_decisions':F(1000*false,decisions),
                      'restricted_mean_run':F(sum(runs),len(runs))}
                for key,value in calc.items(): self.assertEqual(show(value),out[key],(section,method,key))
                for key,value in {'early':early,'missed':missed,'no_alarm':no_alarm}.items():self.assertEqual(str(value),out[key])
                for shift,(hit,count) in shift_counts.items():
                    out_shift=next(r for r in reported if r['section']==section+'_shift' and r['method']==method and float(r['shift'])==shift)
                    self.assertEqual(show(F(hit,count)),out_shift['detection_rate'])
                print('P04',section,method,show(calc['detection_rate']),show(calc['false_per_1000']))

    def test_p05_tiny_ewma_and_subgroup_boundaries(self):
        limits=spc.Limits(0.,2.326,1.,1.342,-1.342,4.917,.4474,10)
        for weight in (5e-324,1e-200,1e-20,1.):
            chart=spc.Ewma(limits,spc.Tuning(weight,3.,.5,5.))
            with localcontext() as context:
                context.prec=750
                w=Decimal.from_float(weight); z=Decimal(0)
                for t in range(17):
                    z=w*Decimal('.1')+(1-w)*z
                    width=3*(w/(2-w)*(1-(1-w)**(2*(t+1)))).sqrt()
                    actual=chart.update(.1)
                    self.assertEqual(actual,abs(z)>width)
                    self.assertGreater(chart.limit,0)
        for first in range(17):
            for last in range(34):
                self.assertEqual(spc.decision_count('xbar_r',first,last),sum(t%5==4 for t in range(first,last+1)))
        print('P05 tiny EWMA 750-digit reference and 578 decision intervals: OK')

    def test_p06_duplicate_limits_replay_and_seed_rejections(self):
        source=rows(REPORTS/'spc_lamp_methods.csv')
        duplicate=dict(next(r for r in source if r['section']=='limits'),value='999')
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'limits.csv'
            for data in ([duplicate]+source,source+[duplicate],source+[dict(duplicate,value=source[6]['value'])]):
                save_rows(path,data)
                with self.assertRaises(ValueError):spc.load_limits(path)
            save_rows(path,source);self.assertIn('sigma_hat',spc.load_limits(path))
            settings=anomaly.load_settings(ROOT/'recipes/anomaly_lamp.json')
            scenario=anomaly.build_split(settings.splits['holdout'],settings,anomaly.load_process(settings))[1]
            replay=rows(REPORTS/'anomaly_lamp_replay.csv')
            for t in ('-1',str(len(scenario.values))):
                changed=copy.deepcopy(replay);changed[0]['t']=t;save_rows(path,changed)
                with self.assertRaises(ValueError):spc.check_replay(path,scenario)
            save_rows(path,replay);spc.check_replay(path,scenario)
            raw=json.loads((ROOT/'recipes/incident_lamp.json').read_text(encoding='utf-8'))
            for value in (65536,True,10**400):
                path=Path(tmp)/'incident.json';path.write_text(json.dumps(dict(raw,products=value)),encoding='utf-8')
                with self.assertRaises(incident.IncidentError):incident.load_settings(path)
        print('P06 duplicate limits both orders, replay bounds, product limits: OK')

    def test_p07_multiple_stops_socket_memory_and_repair(self):
        station=load_station(ROOT/'recipes/plc_station.json');process=anomaly.load_process(station)
        fault=incident.fault_series(7042,24,8,1.5,process);normal=incident.repair_series(7042,24,process)
        stops={0,1,9,10,23}
        class Forced:
            def __init__(self,first):self.n=first-1;self.first=first
            def update(self,value):self.n+=1;return self.n in stops
            def change_point(self):return self.first
            def evidence(self,value):return 'value='+value
        def flow():return incident.Flow('cusum',fault,normal,8,process.item,lambda method,first:Forced(first))
        story=incident.run_story(station,flow(),24,2,3000)
        memory=incident.run_memory(flow(),24)
        self.assertEqual(story.flow.values,memory.values);self.assertEqual(story.flow.disposition,memory.disposition)
        self.assertEqual(story.ok_count+story.ng_count+story.flow.count('aborted'),24)
        self.assertEqual([s.product for s in story.flow.stops],sorted(stops))
        for n in range(24): self.assertEqual(story.flow.values[n],(fault if n<=9 else normal)[n])
        for number in range(1,6):
            events=[e for e in story.events if e['incident_id']=='cusum-%d'%number]
            self.assertEqual([e['event'] for e in events],['alarm','pc_stop','alarm_26','release','clamp_open','remove','reset','restart'])
            self.assertGreater(events[2]['cycle'],events[1]['cycle'])
            self.assertGreaterEqual(events[6]['cycle']-events[5]['cycle'],3)
            self.assertIn('part_present=0 pc_stop=0',events[6]['detail'])
        self.assertEqual(story.events[-1]['event'],'finish')
        print('P07 24 products, stops 0/1/9/10/23, socket=memory, recovery sequence: OK')

    def test_p08_incident_summary_independent(self):
        settings=incident.load_settings(ROOT/'recipes/incident_lamp.json')
        cfg=spc.load_settings(settings.spc);base=anomaly.load_settings(cfg.anomaly);process=anomaly.load_process(base)
        lr=spc.load_limits(settings.spc_report);center=float(lr['xbarbar']);sigma=float(lr['sigma_hat'])
        report=rows(REPORTS/'incident_lamp_compare.csv');onset=settings.onset_product-1
        for method in settings.methods:
            totals=dict(detected=0,early=0,missed=0,delay=0,passed=0,stops=0,false=0)
            scopes={scope:dict(captured=0,parts=0,size=0,over=0,ranged=0) for scope in settings.scopes}
            for seed in settings.summary_seeds:
                # New independent detector state for every segment, separate from Flow/Tracker.
                fault=incident.fault_series(seed,settings.products,onset,settings.shift_sigma,process)
                normal=incident.repair_series(seed,settings.products,process)
                start=0;repaired=False;stops=[];passed=[];shifted=[];a=None;cp=None
                z=center;plus=minus=0.;zp=zm=-1;fails=[]
                for n in range(settings.products):
                    s=n-start;value=(normal if repaired else fault)[n]
                    x=(float(value)-process.center)/process.sigma
                    fail=not (Decimal(process.item.lsl)<=Decimal(value)<=Decimal(process.item.usl))
                    fails.append(fail)
                    z=cfg.tuning.ewma_lambda*x+(1-cfg.tuning.ewma_lambda)*z
                    width=cfg.tuning.ewma_l*sigma*math.sqrt(cfg.tuning.ewma_lambda/(2-cfg.tuning.ewma_lambda)
                                                          *(1-(1-cfg.tuning.ewma_lambda)**(2*(s+1))))
                    plus=max(0.,plus+x-center-cfg.tuning.cusum_k*sigma)
                    minus=max(0.,minus-x+center-cfg.tuning.cusum_k*sigma)
                    if plus==0:zp=s
                    if minus==0:zm=s
                    hit={'rule_3_2':sum(fails[-3:])>=2,'ewma_chart':abs(z-center)>width,
                         'cusum':max(plus,minus)>cfg.tuning.cusum_h*sigma}[method] and s>=base.window-1
                    shifted.append(n>=onset and not repaired);passed.append(not fail and not hit)
                    if hit:
                        stops.append(n)
                        if a is None and n>=onset:
                            a=n;cp=start+(zp if plus>cfg.tuning.cusum_h*sigma else zm)+1;repaired=True
                        start=n+1;z=center;plus=minus=0.;zp=zm=-1;fails=[]
                totals['detected' if a is not None else ('early' if stops else 'missed')]+=1
                totals['delay']+=0 if a is None else a-onset
                totals['passed']+=sum(s and p for s,p in zip(shifted,passed))
                totals['stops']+=len(stops);totals['false']+=len(stops)-(a is not None)
                if a is not None:
                    for scope,target in scopes.items():
                        if scope=='change_point' and method!='cusum':continue
                        first=cp if scope=='change_point' else max(0,a-int(scope.split('_')[1])+1)
                        target['captured']+=first<=onset;target['parts']+=sum(shifted[n] and passed[n] for n in range(first,a+1))
                        target['size']+=a-first+1;target['over']+=sum(not shifted[n] for n in range(first,a+1));target['ranged']+=1
            count=len(settings.summary_seeds)
            expected={key:str(totals[key]) for key in ('detected','early','missed')}
            expected.update(mean_delay=show(F(totals['delay'],totals['detected'])) if totals['detected'] else '',
                            mean_suspect_passed=show(F(totals['passed'],count)),mean_stops=show(F(totals['stops'],count)),
                            mean_false_stops=show(F(totals['false'],count)))
            for name,value in expected.items():
                self.assertEqual(next(r['value'] for r in report if r['section']=='summary' and r['method']==method and r['name']==name),value)
            for scope,t in scopes.items():
                def ratio(num,den):return show(F(num,den)) if den else ''
                expected_scope=dict(run_capture_rate=ratio(t['captured'],count),part_capture_rate=ratio(t['parts'],totals['passed']),
                                    mean_scope_size=ratio(t['size'],t['ranged']),mean_over_scope=ratio(t['over'],t['ranged']))
                for name,value in expected_scope.items():
                    if scope=='change_point' and method!='cusum':value=''
                    self.assertEqual(next(r['value'] for r in report if r['section']=='summary_scope' and r['method']==method and r['scope']==scope and r['name']==name),value)
            print('P08',method,expected)

    def test_p09_dashboard_all_finite_and_overflow_guards(self):
        data=dashboard.load_reports(ROOT)
        bias,alarms=dashboard.contribution_rows(data)
        self.assertTrue(alarms)
        original=copy.deepcopy(data)
        for field in ('z','s_mean'):
            for value in ('NaN','Infinity','-Infinity'):
                data=copy.deepcopy(original);next(r for r in data['anomaly_lamp_replay.csv'] if r['alarm']=='1')[field]=value
                with self.assertRaises(dashboard.DashboardError):dashboard.contribution_rows(data)
        data=copy.deepcopy(original)
        for r in data['anomaly_lamp_model.csv']:
            if r['section']=='weight':r['value']={'mean':'1e308','sd':'-1e308'}.get(r['name'],'0')
            if r['section']=='bias':r['value']='0'
        for r in data['anomaly_lamp_replay.csv']:
            if r['alarm']=='1':
                r['z']='1'
                for name in dashboard.FEATURES:r['s_'+name]='2' if name in ('mean','sd') else '0'
        with self.assertRaises(dashboard.DashboardError):dashboard.contribution_rows(data)
        bad=dict(alarms[0][0],z='99')
        for bad_first in (True,False):
            data=copy.deepcopy(original)
            if bad_first:data['anomaly_lamp_replay.csv'].insert(0,bad)
            else:data['anomaly_lamp_replay.csv'].append(bad)
            with self.assertRaises(dashboard.DashboardError):dashboard.contribution_rows(data)
        print('P09 R23/R24 NaN, infinity, opposing overflow and later alarm rejection: OK')

    def test_p10_dashboard_static_escaping_and_report_values(self):
        data=dashboard.load_reports(ROOT)
        payload='</script><!--<script>"&\u2028\u2029'
        next(r for r in data['pfmea_lamp_report.csv'] if r['section']=='evidence')['reference']=payload
        page=Page();page.feed(dashboard.pfmea_section(data))
        self.assertEqual(page.scripts,0);self.assertIn(payload,page.cells)
        self.assertEqual(json.loads(dashboard.safe_json({'x':payload})),{'x':payload})
        for r in data['gen_measured_seed42_capability.csv']:
            if r['section']=='capability':r.update(cpk='',ppk='',status='표본 부족')
        self.assertIn('유효한 Cpk 없음',dashboard.overview_section(data))
        changed=copy.deepcopy(data)
        changed['spc_lamp_chart.csv'][15]['c_plus']='76.1234560250'
        page=Page();page.feed(dashboard.detect_section(changed));self.assertIn('76.1234560250',page.cells)
        for value in ('URL(//example.invalid/x)','uRl(//example.invalid/x)','url(#absent)'):
            with self.assertRaises(dashboard.DashboardError):
                dashboard.check_svg('<svg xmlns="http://www.w3.org/2000/svg"><rect fill="'+value+'"/></svg>')
        print('P10 escaped static cells, round-trip JSON, missing Cpk, chart cells, mixed-case SVG: OK')

    def test_p11_svg_xml_comment_is_not_html_comment(self):
        # XML considers this a comment; the HTML tokenizer closes <!--> immediately.
        payload='<svg xmlns="http://www.w3.org/2000/svg"><!--><script>document.body.setAttribute("data-probe025","executed")</script>--></svg>'
        with tempfile.TemporaryDirectory() as tmp:
            dest=inputs(tmp);(dest/'line_lamp_layout.svg').write_text(payload,encoding='utf-8')
            target=dest/'dashboard.html';target.write_bytes(b'previous')
            result=cli('src.dashboard',['--root',tmp,'--out','reports/dashboard.html'],tmp)
            chrome=Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe')
            if result.returncode==0 and chrome.exists():
                run=subprocess.run([str(chrome),'--headless','--no-sandbox','--disable-gpu','--no-first-run',
                                    '--no-default-browser-check','--disable-background-networking','--disable-extensions',
                                    '--user-data-dir='+str(Path(tmp)/'profile'),'--dump-dom',target.as_uri()],
                                   capture_output=True,timeout=30)
                executed='data-probe025="executed"' in run.stdout.decode('utf-8',errors='replace')
                print('P11 CLI',result.returncode,'previous_preserved',target.read_bytes()==b'previous',
                      'Chrome exit',run.returncode,'injected_script_executed',executed)
            self.assertEqual(result.returncode,2,'XML comment can become executable HTML; original output must survive')
            self.assertEqual(target.read_bytes(),b'previous')

    def test_p12_dashboard_no_selected_anomaly_is_valid_result(self):
        data=dashboard.load_reports(ROOT)
        picked=[r for r in data['anomaly_lamp_methods.csv'] if r['section']=='selection']
        picked[0].update(method='',value='기준 충족 방법 없음')
        picked[1].update(method='',value='홀드아웃 검증할 선택 없음')
        try:
            text=dashboard.overview_section(data)
        except dashboard.DashboardError as error:
            self.fail('A valid no-selection result must remain visible: '+str(error))
        self.assertIn('기준 충족 방법 없음',text)

    def test_p13_dashboard_ewma_graph_has_actual_limits(self):
        data=dashboard.load_reports(ROOT);calls=[]
        real=dashboard.line_chart
        def record(*args,**kwargs):calls.append(args);return real(*args,**kwargs)
        with patch.object(dashboard,'line_chart',side_effect=record):dashboard.detect_section(data)
        ewma=next(args for args in calls if args[0]=='ewma')
        lr=spc.load_limits(REPORTS/'spc_lamp_methods.csv');center=float(lr['xbarbar'])
        chart=data['spc_lamp_chart.csv'];width=float(chart[-1]['ewma_limit'])
        plotted=[(name,ys[-1]) for name,ys,style in ewma[3]]
        print('P13 center',center,'width',width,'actual lower/upper',center-width,center+width,'plotted',plotted)
        self.assertTrue(any(abs(ys[-1]-(center+width))<1e-8 for _,ys,_ in ewma[3]),'Upper control limit missing; width alone is not UCL')
        self.assertTrue(any(abs(ys[-1]-(center-width))<1e-8 for _,ys,_ in ewma[3]),'Lower control limit missing')

    def test_p14_repair_seed_overlap_with_training(self):
        settings=incident.load_settings(ROOT/'recipes/incident_lamp.json')
        base=anomaly.load_settings(ROOT/'recipes/anomaly_lamp.json')
        changed=replace(base,splits=dict(base.splits,train=range(1003000,1003300)))
        candidate=replace(settings,story_seed=3000,summary_seeds=range(3000,3001))
        process=anomaly.load_process(base)
        normal=incident.repair_series(3000,base.length,process)
        training=anomaly.build_scenario(1003000,0,changed,process).values
        self.assertEqual(normal,training)
        with self.assertRaises(incident.IncidentError,msg='Repair series reuses a training-normal seed but check_seeds accepts it'):
            incident.check_seeds(candidate,changed)

    def test_p15_preservation_and_preregistered_parameters(self):
        changed=subprocess.check_output(['git','diff','--name-only','e93b5c9..HEAD'],cwd=ROOT).decode().splitlines()
        old=subprocess.check_output(['git','ls-tree','-r','--name-only','e93b5c9'],cwd=ROOT).decode().splitlines()
        protected=[p for p in old if p.startswith(('src/','tests/','recipes/','data/','reports/'))]
        modified=[p for p in protected if p in changed]
        self.assertEqual(sorted(modified),['src/modbus.py','src/plc.py','src/station.py'])
        for commit,filename in [('12c0617','msa_lamp.json'),('05329f2','spc_lamp.json'),('461e3dc','incident_lamp.json')]:
            original=json.loads(subprocess.check_output(['git','show',commit+':recipes/'+filename],cwd=ROOT))
            current=json.loads((ROOT/'recipes'/filename).read_text(encoding='utf-8'))
            if filename=='spc_lamp.json':current.pop('anomaly_replay')
            self.assertEqual(original,current)
        print('P15 base protected files',len(protected),'only permitted PLC additions; numerical recipes unchanged')

    def test_p20_readme_pipeline_end_to_end(self):
        before={str(p.relative_to(ROOT)):p.read_bytes() for folder in ('reports','data','recipes')
                for p in (ROOT/folder).rglob('*') if p.is_file()}
        generated=[]
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ('src','recipes','data'):
                shutil.copytree(ROOT/name,root/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
            (root/'reports').mkdir()
            # README begins at stage 12; these earlier-stage dashboard prerequisites are submitted inputs.
            for name in ('gen_measured_seed42_capability.csv','pfmea_lamp_report.csv','line_lamp_compare.csv','line_lamp_layout.svg'):
                shutil.copyfile(REPORTS/name,root/'reports'/name)
            commands=[('src.msa',['recipes/msa_lamp.json'],'msa_lamp_*'),
                      ('src.anomaly',['recipes/anomaly_lamp.json'],'anomaly_lamp_*'),
                      ('src.spc',['recipes/spc_lamp.json'],'spc_lamp_*'),
                      ('src.station',['recipes/plc_station.json','--scenario','all'],'plc_station_*'),
                      ('src.incident',['recipes/incident_lamp.json'],'incident_lamp_*'),
                      ('src.dashboard',['--root',str(root),'--out','reports/dashboard.html'],'dashboard.html')]
            for module,args,pattern in commands:
                r=subprocess.run([sys.executable,'-B','-m',module,*args],cwd=root,env=ENV,capture_output=True,encoding='utf-8',timeout=600)
                self.assertEqual(r.returncode,0,r.stdout+r.stderr)
                files=list((root/'reports').glob(pattern))
                for path in files:self.assertEqual(path.read_bytes(),(REPORTS/path.name).read_bytes(),path.name)
                generated.extend(p.name for p in files)
                print('P20',module,'exit=0 byte_equal='+str(len(files)),flush=True)
            html=(root/'reports/dashboard.html').read_bytes()
            again=subprocess.run([sys.executable,'-B','-m','src.dashboard','--root',str(root),'--out','reports/dashboard.html'],
                                 cwd=root,env=ENV,capture_output=True,encoding='utf-8',timeout=30)
            self.assertEqual(again.returncode,0,again.stderr);self.assertEqual(html,(root/'reports/dashboard.html').read_bytes())
            self.assertLess(len(html),5*1024*1024)
            page=Page();page.feed(html.decode('utf-8'));self.assertEqual(page.scripts,3)
        for name,content in before.items():self.assertEqual((ROOT/name).read_bytes(),content,name)
        self.assertEqual(len(generated),30)
        print('P20 reports=30 byte-identical; original files='+str(len(before))+' unchanged; dashboard repeated')


if __name__ == '__main__':
    unittest.main()

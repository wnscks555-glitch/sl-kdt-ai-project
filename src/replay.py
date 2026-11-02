"""9단계 가상 라인 시뮬레이션의 사건을 기록해 재생 화면 HTML 한 파일로 만든다."""

import argparse
from collections import Counter
import csv
from dataclasses import dataclass
from fractions import Fraction
import html
import json
from pathlib import Path

from . import line as lines
from .dashboard import DashboardError, output_path, safe_json, write_atomic
from .line import machine_order, show, target_uph, uph
from .sizing import balance_of, check_outputs, combo_of, load_routes, read_compare, setup_inputs


NOTICE = ("가상 라인 시뮬레이션 재생이다. 9단계 모의가 실제로 낸 사건을 그대로 그리며, 시간과 설비는 가상이고 "
          "실제 라인이나 실시간 모니터링이 아니다.")
KEYS = {"line", "line_report", "seed", "products"}
KINDS = ("begin", "done", "release", "down", "up", "queue", "dequeue", "leave")
MAX_PRODUCTS = 500
MAX_BYTES = 2 * 1024 * 1024


class ReplayError(ValueError):
    """설정이 잘못되었다. 종료 코드는 3이다."""

    def __init__(self, errors):
        super().__init__("; ".join(errors))
        self.errors = errors


@dataclass(frozen=True)
class Settings:
    line: Path
    line_report: Path
    seed: int
    products: int


def _reject_constant(name):
    raise ReplayError(["JSON에 허용되지 않는 값: " + name])


def load_settings(path):
    path = Path(path)
    try:
        with path.open(encoding="utf-8-sig") as source:
            data = json.load(source, parse_constant=_reject_constant)
    except (json.JSONDecodeError, UnicodeError) as error:
        raise ReplayError(["$: JSON을 읽을 수 없음: " + str(error)]) from error
    if not isinstance(data, dict):
        raise ReplayError(["$: 객체여야 함"])
    errors = ["$: 필요한 키 없음 " + key for key in sorted(KEYS - set(data))]
    errors += ["$: 허용 밖 키 " + key for key in sorted(set(data) - KEYS)]
    for key in ("line", "line_report"):
        if key in data and not (isinstance(data[key], str) and data[key]):
            errors.append("$.%s: 경로 문자열이어야 함" % key)
    for key, low, high in (("seed", 0, 10 ** 9), ("products", 1, MAX_PRODUCTS)):
        value = data.get(key)
        if key in data and (type(value) is not int or not low <= value <= high):
            errors.append("$.%s: %d–%d 정수여야 함" % (key, low, high))
    if errors:
        raise ReplayError(errors)
    return Settings(path.parent / data["line"], path.parent / data["line_report"], data["seed"], data["products"])


def outcome(result):
    """두 실행이 같은지 볼 값이다. 기록이 시뮬레이션을 바꾸지 않았다는 근거다."""
    return (result.end, result.left, result.passed, result.good, result.escaped, result.wait,
            sorted(result.work.items()), sorted(result.blocked.items()), sorted(result.repair.items()))


EXPECT = {"begin": "idle", "done": "busy", "release": "done", "down": "idle", "up": "down"}


def check_events(events, stations, result, buffer_units):
    """사건만으로 상태를 다시 세워 원 결과와 맞춘다. 화면이 그릴 상태가 실제 실행과 같다는 근거다.

    마지막 제품이 떠나면 시뮬레이션이 끝나므로 끝나지 않은 수리는 `up` 없이 남고, 종료 시각에서 자른다.
    """
    servers = [[["idle", None, 0] for _ in range(station.servers)] for station in stations]
    work, blocked, repair = Counter(), Counter(), Counter()
    buffers = [0] * len(stations)
    gone, left, passed, good = set(), 0, 0, 0
    for clock, kind, index, number, route in events:
        if kind == "leave":
            if route.product_id in gone:
                raise ValueError("같은 제품이 두 번 떠남: " + route.product_id)
            gone.add(route.product_id)
            left, passed, good = left + 1, passed + route.completed, good + route.good
            continue
        if route is not None and kind in ("begin", "queue", "dequeue") and route.product_id in gone:
            raise ValueError("떠난 제품의 사건이 있음: " + route.product_id)
        if kind in ("queue", "dequeue"):
            buffers[index] += 1 if kind == "queue" else -1
            if not 0 <= buffers[index] <= buffer_units:
                raise ValueError("버퍼 개수가 범위 밖임: " + stations[index].id)
            continue
        server = servers[index][number]
        if server[0] != EXPECT[kind]:
            raise ValueError("서버 사건 순서가 맞지 않음: %s %s" % (stations[index].id, kind))
        name = stations[index].id
        if kind == "begin":
            server[:] = ["busy", route, clock]
        elif kind == "done":
            work[name] += clock - server[2]
            server[:] = ["done", server[1], clock]
        elif kind == "release":
            blocked[name] += clock - server[2]
            server[:] = ["idle", None, clock]
        elif kind == "down":
            server[:] = ["down", None, clock]
        else:
            repair[name] += clock - server[2]
            server[:] = ["idle", None, clock]
    for station, row in zip(stations, servers):
        for server in row:
            if server[0] == "down":
                repair[station.id] += result.end - server[2]
            elif server[0] != "idle":
                raise ValueError("끝났는데 일하는 서버가 있음: " + station.id)
    rebuilt = (left, passed, good, sorted((key, value) for key, value in work.items() if value),
               sorted((key, value) for key, value in blocked.items() if value),
               sorted((key, value) for key, value in repair.items() if value))
    actual = (result.left, result.passed, result.good,
              sorted((key, value) for key, value in result.work.items() if value),
              sorted((key, value) for key, value in result.blocked.items() if value),
              sorted((key, value) for key, value in result.repair.items() if value))
    if rebuilt != actual or any(buffers):
        raise ValueError("사건으로 다시 계산한 값이 실행 결과와 다름")


def record(stations, routes, buffer_units, repair):
    """사건을 기록하며 돌린다. 기록 없이 돌린 결과와 다르거나 사건이 결과를 설명하지 못하면 멈춘다."""
    plain = lines.simulate(stations, routes, buffer_units, repair)
    events = []
    traced = lines.simulate(stations, routes, buffer_units, repair,
                            on_event=lambda clock, kind, index, number, route: events.append(
                                (clock, kind, index, number, route)))
    if outcome(plain) != outcome(traced):
        raise ValueError("기록한 실행과 원래 실행의 결과가 다름")
    check_events(events, stations, traced, buffer_units)
    return traced, events


def compact(events, routes):
    """화면용 정수 배열이다. 제품은 투입 순서 번호로 바꾼다."""
    number = {route.product_id: index for index, route in enumerate(routes)}
    rows = []
    for clock, kind, index, server, route in events:
        product = -1 if route is None else number[route.product_id]
        extra = 0
        if kind == "leave":
            extra = 2 if route.good else 1 if route.completed else 0
        rows.append([clock, KINDS.index(kind), index, server, product, extra])
    return rows


def station_rows(stations, result):
    rows = []
    for station in stations:
        span = station.servers * result.end
        share = (lambda amount: show(Fraction(amount, span)) if span else "")
        rows.append((station.id, station.inspection or "수작업", station.servers, share(result.work[station.id]),
                     share(result.blocked[station.id]), share(result.repair[station.id])))
    return rows


def table(headers, rows, caption):
    head = "".join("<th scope=\"col\">%s</th>" % html.escape(str(item)) for item in headers)
    body = "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % html.escape(str(cell)) for cell in row) for row in rows)
    return ("<div class=\"scroll\" tabindex=\"0\"><table><caption>%s</caption><thead><tr>%s</tr></thead><tbody>%s"
            "</tbody></table></div>" % (html.escape(caption), head, body))


STYLE = """
:root{color-scheme:light;--bg:#f2f4f3;--panel:#fff;--ink:#17201d;--muted:#55625c;--line:#d3dad6;
--idle:#e7ebe9;--busy:#2a78d6;--blocked:#c98a12;--down:#c4392d;--good:#1b8a5a;--on:#ffffff}
@media (prefers-color-scheme:dark){:root{color-scheme:dark;--bg:#151a18;--panel:#1d2421;--ink:#e9eeeb;--muted:#aab6b0;
--line:#34403b;--idle:#2a332f;--busy:#4a92e8;--blocked:#e0a43a;--down:#ef7a6e;--good:#4cc48e;--on:#0f1412}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 "Malgun Gothic","Apple SD Gothic Neo","Noto Sans KR",sans-serif}
main{max-width:1120px;margin:0 auto;padding:16px;display:grid;gap:18px}
h1{font-size:22px;margin:0}
p{margin:0}
.notice{padding:10px 12px;border:1px solid var(--line);border-left:4px solid var(--blocked);background:var(--panel)}
.controls{display:flex;flex-wrap:wrap;gap:10px;align-items:center;padding:12px;background:var(--panel);border:1px solid var(--line)}
.controls label{display:inline-flex;align-items:center;gap:6px;white-space:nowrap}
.controls .grow{flex:1;min-width:200px}
.controls input[type=range]{width:100%}
button{font:inherit;padding:6px 14px;border:1px solid var(--busy);background:var(--busy);color:var(--on);cursor:pointer}
button:focus-visible,input:focus-visible,select:focus-visible{outline:2px solid var(--busy);outline-offset:2px}
.stats{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:1px;background:var(--line);border:1px solid var(--line)}
.stats div{background:var(--panel);padding:10px}
.stats b{display:block;font:600 20px/1.3 Consolas,monospace}
.stats span{color:var(--muted);font-size:13px}
.flow{display:flex;gap:8px;overflow-x:auto;padding:12px;background:var(--panel);border:1px solid var(--line)}
.side{min-width:96px;display:grid;align-content:center;gap:4px;text-align:center;color:var(--muted)}
.side b{font:600 22px Consolas,monospace;color:var(--ink)}
.station{min-width:112px;border:1px solid var(--line);padding:8px;display:grid;gap:6px;align-content:start}
.station h2{font-size:14px;margin:0}
.station small{color:var(--muted)}
.buffer{font-size:13px;color:var(--muted)}
.server{border-radius:4px;padding:6px;min-height:46px;background:var(--idle);color:var(--ink);font-size:13px}
.server b{display:block;font:600 14px Consolas,monospace}
.server.busy{background:var(--busy);color:var(--on)}
.server.blocked{background:var(--blocked);color:var(--on)}
.server.down{background:var(--down);color:var(--on)}
.legend{display:flex;flex-wrap:wrap;gap:14px;font-size:13px;color:var(--muted)}
.legend i{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:5px;vertical-align:-1px}
.log{font:13px/1.5 Consolas,monospace;background:var(--panel);border:1px solid var(--line);padding:8px 12px;min-height:7.5em;white-space:pre-wrap}
.scroll{overflow-x:auto;background:var(--panel);border:1px solid var(--line)}
table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}
caption{text-align:left;font-weight:600;padding:8px 10px 0}
th,td{padding:6px 10px;border-bottom:1px solid var(--line);text-align:left}
th{color:var(--muted);font-weight:600}
.js-only{display:none}
.js .stats.js-only{display:grid}
.js .controls.js-only,.js .flow.js-only,.js .legend.js-only{display:flex}
.js .log.js-only{display:block}
@media (max-width:640px){.stats{grid-template-columns:repeat(2,minmax(0,1fr))}}
"""

SCRIPT = """
(function(){
  document.documentElement.className='js';
  var D=JSON.parse(document.getElementById('replay-data').textContent);
  var KINDS=['begin','done','release','down','up','queue','dequeue','leave'];
  var NAMES={begin:'작업 시작',done:'작업 끝',release:'서버 비움',down:'수리 시작',up:'수리 끝',queue:'버퍼 진입',dequeue:'버퍼에서 나감',leave:'라인 이탈'};
  var flow=document.getElementById('flow'),cells=[],buffers=[];
  function add(parent,tag,cls,text){var n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;parent.appendChild(n);return n;}
  var start=add(flow,'div','side');add(start,'span',null,'투입 대기');var waitBox=add(start,'b',null,'');
  D.stations.forEach(function(s,i){
    var box=add(flow,'div','station');add(box,'h2',null,s.id+' '+s.kind);add(box,'small',null,'서버 '+s.servers+'대');
    buffers.push(add(box,'div','buffer',''));cells.push([]);
    for(var k=0;k<s.servers;k++){var c=add(box,'div','server');cells[i].push(c);}
  });
  var end=add(flow,'div','side');add(end,'span',null,'완료');var doneBox=add(end,'b',null,'');
  var slider=document.getElementById('time'),play=document.getElementById('play'),speed=document.getElementById('speed');
  var log=document.getElementById('log');
  var stat={clock:document.getElementById('s-clock'),left:document.getElementById('s-left'),good:document.getElementById('s-good'),
    uph:document.getElementById('s-uph'),bad:document.getElementById('s-bad')};
  slider.max=D.end;
  var state,applied;
  function reset(){
    state={servers:D.stations.map(function(s){var a=[];for(var k=0;k<s.servers;k++)a.push({s:'idle',p:-1});return a;}),
      buffers:D.stations.map(function(){return 0;}),entered:{},left:0,good:0,bad:0,lines:[]};applied=0;
  }
  function apply(e){
    var kind=KINDS[e[1]],i=e[2],k=e[3],p=e[4];
    if(kind==='begin'){state.servers[i][k]={s:'busy',p:p};state.entered[p]=1;}
    else if(kind==='done'){state.servers[i][k]={s:'blocked',p:p};}
    else if(kind==='release'){state.servers[i][k]={s:'idle',p:-1};}
    else if(kind==='down'){state.servers[i][k]={s:'down',p:-1};}
    else if(kind==='up'){state.servers[i][k]={s:'idle',p:-1};}
    else if(kind==='queue'){state.buffers[i]+=1;}
    else if(kind==='dequeue'){state.buffers[i]-=1;}
    else if(kind==='leave'){state.left+=1;state.entered[p]=1;if(e[5]===2)state.good+=1;else state.bad+=1;}
    var where=i>=0?D.stations[i].id:'라인';
    state.lines.push((e[0]/1000).toFixed(1)+'초  '+where+'  '+NAMES[kind]+(p>=0?'  제품 '+(p+1):''));
    if(state.lines.length>5)state.lines.shift();
  }
  function seek(t){
    if(applied>0&&D.events[applied-1][0]>t)reset();
    while(applied<D.events.length&&D.events[applied][0]<=t){apply(D.events[applied]);applied+=1;}
    draw(t);
  }
  var LABEL={idle:'유휴',busy:'작업',blocked:'막힘',down:'수리'};
  function draw(t){
    state.servers.forEach(function(list,i){list.forEach(function(v,k){
      var c=cells[i][k];c.className='server '+v.s;c.textContent='';
      add(c,'b',null,LABEL[v.s]);if(v.p>=0)add(c,'span',null,'제품 '+(v.p+1));
    });buffers[i].textContent='버퍼 '+state.buffers[i]+'개';});
    waitBox.textContent=D.products-Object.keys(state.entered).length;
    doneBox.textContent=state.left;
    stat.clock.textContent=(t/1000).toFixed(1);stat.left.textContent=state.left;stat.good.textContent=state.good;
    stat.bad.textContent=state.bad;stat.uph.textContent=t>0?(state.good*3600000/t).toFixed(1):'0.0';
    log.textContent=state.lines.join('\\n');slider.value=t;
  }
  var timer=null,last=0;
  function step(now){
    if(timer===null)return;
    var dt=last?now-last:0;last=now;
    var t=Math.min(D.end,parseFloat(slider.value)+dt*parseFloat(speed.value));
    seek(t);
    if(t>=D.end){stop();return;}
    timer=requestAnimationFrame(step);
  }
  function stop(){if(timer!==null)cancelAnimationFrame(timer);timer=null;last=0;play.textContent='재생';}
  play.addEventListener('click',function(){
    if(timer!==null){stop();return;}
    if(parseFloat(slider.value)>=D.end)seek(0);
    play.textContent='정지';timer=requestAnimationFrame(step);
  });
  slider.addEventListener('input',function(){stop();seek(parseFloat(slider.value));});
  reset();seek(0);
})();
"""


def build(settings):
    raw = lines.read_line_file(settings.line)
    _, _, recipe, _ = lines.load_setup(settings.line.parent / raw["generator"])
    line = lines.load_line(settings.line, recipe.models)
    label, _, _ = read_compare(settings.line_report, line)
    combo = combo_of(machine_order(line), label)
    config, _, seed_routes = load_routes(settings.line, "%d-%d" % (settings.seed, settings.seed), settings.products)
    routes = seed_routes[0]
    stations = lines.build_stations(line, balance_of(line, config), combo)
    result, events = record(stations, routes, line.buffer_units, line.repair)
    data = {"end": result.end, "products": len(routes), "events": compact(events, routes),
            "stations": [{"id": station.id, "kind": station.inspection or "수작업", "servers": station.servers}
                         for station in stations]}
    good_uph = show(uph(result.good, result.end))
    summary = ("<p>조합 %s, 시드 %d, 제품 %d개. 끝 시각 %s초, 검사 통과 %d, 양품 %d, 누적 양품 UPH %s(목표 %s). "
               "사건 %d개를 재생합니다. 짧은 실행이라 9단계의 30시드 결과와 UPH가 다를 수 있습니다.</p>"
               % (html.escape(label), settings.seed, len(routes), "%.1f" % (result.end / 1000), result.passed,
                  result.good, good_uph, show(target_uph(line)), len(events)))
    stats = ("<div class=\"stats js-only\" aria-live=\"off\"><div><b id=\"s-clock\">0.0</b><span>시각(초)</span></div>"
             "<div><b id=\"s-left\">0</b><span>라인을 떠난 제품</span></div><div><b id=\"s-good\">0</b><span>양품</span></div>"
             "<div><b id=\"s-bad\">0</b><span>양품 아님</span></div><div><b id=\"s-uph\">0.0</b><span>누적 양품 UPH</span></div></div>")
    controls = ("<div class=\"controls js-only\"><button id=\"play\" type=\"button\">재생</button>"
                "<label>속도 <select id=\"speed\"><option value=\"5\">5배</option><option value=\"20\" selected>20배</option>"
                "<option value=\"60\">60배</option><option value=\"200\">200배</option></select></label>"
                "<label class=\"grow\">시각 <input id=\"time\" type=\"range\" min=\"0\" max=\"0\" step=\"100\" value=\"0\"></label></div>")
    legend = ("<div class=\"legend js-only\"><span><i style=\"background:var(--idle)\"></i>유휴</span>"
              "<span><i style=\"background:var(--busy)\"></i>작업</span><span><i style=\"background:var(--blocked)\"></i>"
              "막힘(다음 공정이 가득 참)</span><span><i style=\"background:var(--down)\"></i>수리</span></div>")
    body = ("<main><h1>가상 라인 시뮬레이션 재생</h1><p class=\"notice\">%s</p>%s%s%s%s"
            "<div id=\"flow\" class=\"flow js-only\" aria-label=\"스테이션 상태\"></div><div id=\"log\" class=\"log js-only\" "
            "aria-live=\"off\"></div>%s</main>"
            % (html.escape(NOTICE), summary, controls, stats, legend,
               table(("스테이션", "공정", "서버", "작업 비율", "막힘 비율", "수리 비율"), station_rows(stations, result),
                     "스테이션별 시간 비율 (이 실행)")))
    return ("<!doctype html><html lang=\"ko\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" "
            "content=\"width=device-width, initial-scale=1\"><title>가상 라인 시뮬레이션 재생</title><style>%s</style></head>"
            "<body>%s<script id=\"replay-data\" type=\"application/json\">%s</script><script>%s</script></body></html>\n"
            % (STYLE, body, safe_json(data), SCRIPT))


def run(config, root, target):
    settings = load_settings(config)
    root = Path(root).resolve()
    path = output_path(root, Path(target))
    raw = lines.read_line_file(settings.line)
    check_outputs([path], [Path(config), settings.line, settings.line_report]
                  + setup_inputs(settings.line.parent / raw["generator"]))
    data = build(settings).encode("utf-8")
    if len(data) > MAX_BYTES:
        raise ValueError("HTML이 2MB를 넘음")
    write_atomic(path, data)
    return path, len(data)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    try:
        path, size = run(args.config, args.root, args.out)
    except ReplayError as error:
        parser.exit(3, "재생 입력 오류:\n" + "\n".join(error.errors) + "\n")
    except (OSError, UnicodeError, csv.Error, ValueError, KeyError) as error:
        parser.exit(2, "오류: " + str(error) + "\n")
    print(NOTICE)
    print("저장 파일: %s (%d바이트)" % (path.name, size))


if __name__ == "__main__":
    main()

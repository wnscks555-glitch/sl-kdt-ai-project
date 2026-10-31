"""합성 혼류 라인의 작업 배치, 가상 시계 시뮬레이션, 검사기 대수 비교."""

import argparse
from collections import Counter, deque
import csv
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction
import heapq
from itertools import product as combinations_of
import json
from math import ceil
from pathlib import Path
import re
from typing import Dict, FrozenSet, List, Optional, Tuple
from xml.sax.saxutils import escape

from .evaluate import parse_seeds
from .generate import Generator, load_setup
from .summary import ASSUMPTION_NOTICE, build_analysis


MAX_ELEMENTS = 12
SECONDS_PATTERN = r"[0-9]+(\.[0-9]{1,3})?"
COMPLETED = "레시피 모의 흐름 완료"
SYNTHETIC_NOTICE = "시간과 치수는 가상이며 실제 설비 사양이 아니다."
ROUTE_NOTICE = ("제품 경로와 정지는 설비 3·2·2대 기준으로 생성한 외생 입력이다. 대수를 바꿔도 다시 생성하지 않고, "
                "수리 지연과 재검사 설비 변경은 쓰지 않는다. 라인의 B는 LEAK 앞에 P3를 한다.")
COMPARE_NOTICE = "고정 경로·정지 시나리오에 조건부인 용량 비교다. 설비 증설의 품질·신뢰성 효과를 평가하지 않는다."
NO_COMBO = "기준 충족 조합 없음"
NO_SELECTION = "검증할 선택 없음"
NO_BALANCE = "배치 불가"
NO_TARGET = "대상 없음"
BALANCE_COLUMNS = ("section", "key", "station", "elements", "model", "load_seconds", "idle_seconds", "value", "text")
COMPARE_COLUMNS = (
    "section", "combo", "leak", "light", "final", "area_mm2", "seeds", "products", "station", "pass_uph", "good_uph",
    "escaped", "utilization", "blocked_share", "repair_share", "mean_wait_seconds", "bottleneck", "meets_uph",
    "meets_takt", "meets_floor", "reject_reason", "selected", "value",
)


class LineError(ValueError):
    def __init__(self, errors):
        self.errors = tuple(errors)
        super().__init__("\n".join(self.errors))


@dataclass(frozen=True)
class Element:
    id: str
    step: str
    times: Dict[str, int]
    predecessors: Tuple[str, ...] = ()
    inspection: bool = False


@dataclass(frozen=True)
class Machine:
    inspection: str
    counts: Tuple[int, ...]
    load: int
    clamp: int
    test: int
    unload: int
    width: int
    depth: int
    service: int


@dataclass(frozen=True)
class Floor:
    length: int
    width: int
    aisle: int
    pitch: int
    gap: int


@dataclass(frozen=True)
class Line:
    period: int
    planned_stop: int
    demand: int
    buffer_units: int
    repair: int
    elements: Tuple[Element, ...]
    machines: Dict[str, Machine]
    manual_width: int
    manual_depth: int
    floor: Floor

    @property
    def net(self):
        return self.period - self.planned_stop


@dataclass(frozen=True)
class Balance:
    stations: Tuple[Tuple[str, ...], ...]
    manual_count: int
    idle_cost: Fraction


@dataclass(frozen=True)
class SimStation:
    id: str
    servers: int
    times: Dict[str, int]
    inspection: Optional[str] = None


@dataclass(frozen=True)
class Route:
    product_id: str
    model: str
    attempts: Dict[str, int] = field(default_factory=dict)
    completed: bool = True
    defective: bool = False
    end_inspection: str = ""
    stops: FrozenSet[str] = frozenset()

    @property
    def good(self):
        return self.completed and not self.defective


@dataclass
class SimResult:
    end: int = 0
    left: int = 0
    passed: int = 0
    good: int = 0
    escaped: int = 0
    wait: int = 0
    work: Dict[str, int] = field(default_factory=Counter)
    blocked: Dict[str, int] = field(default_factory=Counter)
    repair: Dict[str, int] = field(default_factory=Counter)

    def add(self, other):
        self.end += other.end
        self.left += other.left
        self.passed += other.passed
        self.good += other.good
        self.escaped += other.escaped
        self.wait += other.wait
        for name in ("work", "blocked", "repair"):
            getattr(self, name).update(getattr(other, name))


def _seconds(value, location, errors, positive=False):
    if not isinstance(value, str) or re.fullmatch(SECONDS_PATTERN, value) is None:
        errors.append(location + ": 소수 셋째 자리까지의 문자열 초여야 함")
        return 0
    # 긴 입력도 반올림되지 않게 문자열을 정수로 바꾼다.
    whole, _, fraction = value.partition(".")
    milliseconds = int(whole) * 1000 + int(fraction.ljust(3, "0") or 0)
    if positive and milliseconds == 0:
        errors.append(location + ": 0보다 커야 함")
    return milliseconds


def _integer(value, location, errors, minimum=1):
    if type(value) is not int or value < minimum:
        errors.append(location + ": " + str(minimum) + " 이상의 정수여야 함")
        return minimum
    return value


def _keys(value, allowed, location, errors):
    for key in allowed:
        if key not in value:
            errors.append(location + "." + key + ": 없는 키")
    for key in value:
        if key not in allowed:
            errors.append(location + "." + key + ": 허용하지 않은 키")


def _ancestors(elements, errors):
    """요소별 조상 집합이다. 순환이면 오류를 남기고 빈 표를 돌려준다."""
    known = {element.id: element for element in elements}
    done, visiting = {}, set()

    def visit(name):
        if name in done:
            return done[name]
        if name in visiting:
            raise LineError(["elements." + name + ": 선행 순환"])
        visiting.add(name)
        found = set()
        for parent in known[name].predecessors:
            found |= {parent} | visit(parent)
        visiting.discard(name)
        done[name] = found
        return found

    try:
        for element in elements:
            visit(element.id)
    except LineError as error:
        errors.extend(error.errors)
        return None
    return done


def _check_order(elements, models, errors):
    table = _ancestors(elements, errors)
    if table is None:
        return

    def working(model, step):
        return [element for element in elements if element.step == step and element.times.get(model, 0) > 0]

    def require(model, before, after, message):
        for first in before:
            for second in after:
                if first.id not in table[second.id]:
                    errors.append("elements." + second.id + ": " + model + "의 " + message + " 위반 (" + first.id + ")")

    for model, recipe in models.items():
        for first, second in zip(recipe.steps, recipe.steps[1:]):
            require(model, working(model, first), working(model, second), "공정 순서")
        for first, second in zip(recipe.inspections, recipe.inspections[1:]):
            require(model, working(model, first.id), working(model, second.id), "검사 순서")
        for item in recipe.inspections:
            require(model, working(model, item.after), working(model, item.id), "after")


def read_line_file(path):
    """측정 설정을 찾기 전에 파일 구조를 본다. 파일 접근 오류는 호출자에게 그대로 넘긴다."""
    try:
        data = json.loads(Path(path).read_bytes().decode("utf-8-sig"))
    except ValueError as error:
        raise LineError(["$: JSON 오류: " + str(error)]) from error
    if not isinstance(data, dict):
        raise LineError(["$: 최상위는 객체여야 함"])
    if "generator" not in data:
        raise LineError(["$.generator: 없는 키"])
    if not isinstance(data["generator"], str) or not data["generator"].strip():
        raise LineError(["$.generator: 비어 있지 않은 문자열이어야 함"])
    return data


def load_line(path, models):
    """라인 파일을 읽어 검증한다. 문제는 위치와 함께 모아서 보고한다."""
    data = read_line_file(path)
    errors = []
    _keys(data, ("generator", "period_seconds", "planned_stop_seconds", "demand_units", "buffer_units",
                 "repair_seconds", "elements", "machines", "manual_station", "floor"), "$", errors)
    if errors:
        raise LineError(errors)
    period = _seconds(data["period_seconds"], "$.period_seconds", errors, True)
    planned = _seconds(data["planned_stop_seconds"], "$.planned_stop_seconds", errors)
    if planned >= period:
        errors.append("$.planned_stop_seconds: period_seconds보다 작아야 함")
    demand = _integer(data["demand_units"], "$.demand_units", errors)
    buffer_units = _integer(data["buffer_units"], "$.buffer_units", errors, 0)
    repair = _seconds(data["repair_seconds"], "$.repair_seconds", errors)

    inspections = {item.id for model in models.values() for item in model.inspections}
    steps = {step for model in models.values() for step in model.steps}
    raw = data["elements"]
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_ELEMENTS:
        raise LineError(errors + ["$.elements: 1–" + str(MAX_ELEMENTS) + "개 배열이어야 함"])
    elements, seen = [], set()
    for index, item in enumerate(raw):
        location = "$.elements[" + str(index) + "]"
        if not isinstance(item, dict):
            errors.append(location + ": 객체여야 함")
            continue
        before = len(errors)
        _keys(item, ("id", "step", "seconds", "predecessors"), location, errors)
        if len(errors) != before:
            continue
        name, step = item["id"], item["step"]
        if not isinstance(name, str) or not name or name in seen:
            errors.append(location + ".id: 비어 있거나 중복")
            continue
        seen.add(name)
        if not isinstance(step, str):
            errors.append(location + ".step: 문자열이어야 함")
            continue
        if step not in steps | inspections:
            errors.append(location + ".step: 레시피에 없는 공정 또는 검사")
        seconds = item["seconds"]
        if not isinstance(seconds, dict) or set(seconds) != set(models):
            errors.append(location + ".seconds: 모델 키가 레시피와 같아야 함")
            continue
        times = {model: _seconds(value, location + ".seconds." + model, errors) for model, value in seconds.items()}
        parents = item["predecessors"]
        if not isinstance(parents, list) or any(not isinstance(parent, str) for parent in parents):
            errors.append(location + ".predecessors: 문자열 배열이어야 함")
            continue
        if len(set(parents)) != len(parents):
            errors.append(location + ".predecessors: 같은 선행 요소가 중복됨")
            continue
        elements.append(Element(name, step, times, tuple(parents), step in inspections))
    names = {element.id for element in elements}
    for element in elements:
        for parent in element.predecessors:
            if parent not in names:
                errors.append("elements." + element.id + ": 없는 선행 요소 " + parent)
    covered = {element.step for element in elements}
    for step in sorted((steps | inspections) - covered):
        errors.append("$.elements: 요소가 없는 공정 또는 검사 " + step)
    for model, recipe in models.items():
        own = set(recipe.steps) | {item.id for item in recipe.inspections}
        for step in covered:
            total = sum(element.times.get(model, 0) for element in elements if element.step == step)
            if step in own and total == 0:
                errors.append("$.elements: " + model + "의 " + step + " 시간이 0")
            if step not in own and total > 0:
                errors.append("$.elements: " + model + "에 없는 " + step + " 시간이 0보다 큼")
    for step in inspections:
        if sum(element.step == step for element in elements) > 1:
            errors.append("$.elements: 검사 " + step + "의 요소는 하나여야 함")
    if not errors:
        _check_order(elements, models, errors)

    machines = {}
    raw = data["machines"]
    if not isinstance(raw, dict):
        errors.append("$.machines: 객체여야 함")
        raw = {}
    for name in sorted(inspections - set(raw)):
        errors.append("$.machines." + name + ": 없는 키")
    for name, item in raw.items():
        location = "$.machines." + name
        if name not in inspections:
            errors.append(location + ": 레시피에 없는 검사")
            continue
        before = len(errors)
        if not isinstance(item, dict):
            errors.append(location + ": 객체여야 함")
            continue
        _keys(item, ("counts", "load", "clamp", "test", "unload", "width_mm", "depth_mm", "service_mm"), location, errors)
        if len(errors) != before:
            continue
        counts = item["counts"]
        if (not isinstance(counts, list) or not counts or any(type(count) is not int or count < 1 for count in counts)
                or sorted(set(counts)) != counts):
            errors.append(location + ".counts: 오름차순 양의 정수 배열이어야 함")
            continue
        parts = [_seconds(item[key], location + "." + key, errors) for key in ("load", "clamp", "test", "unload")]
        machines[name] = Machine(name, tuple(counts), *parts, _integer(item["width_mm"], location + ".width_mm", errors),
                                 _integer(item["depth_mm"], location + ".depth_mm", errors),
                                 _integer(item["service_mm"], location + ".service_mm", errors, 0))
        for element in elements:
            if element.step == name:
                for model, milliseconds in element.times.items():
                    if milliseconds and milliseconds != sum(parts):
                        errors.append(location + ": " + model + "의 구간 합이 검사 시간과 다름")

    station = data["manual_station"]
    floor = data["floor"]
    for location, value, allowed in (("$.manual_station", station, ("width_mm", "depth_mm")),
                                     ("$.floor", floor, ("length_mm", "width_mm", "aisle_mm", "pitch_mm", "gap_mm"))):
        if isinstance(value, dict):
            _keys(value, allowed, location, errors)
        else:
            errors.append(location + ": 객체여야 함")
    if errors:
        raise LineError(errors)
    numbers = [_integer(station[key], "$.manual_station." + key, errors) for key in ("width_mm", "depth_mm")]
    measures = [_integer(floor[key], "$.floor." + key, errors)
                for key in ("length_mm", "width_mm", "aisle_mm", "pitch_mm", "gap_mm")]
    if errors:
        raise LineError(errors)
    return Line(period, planned, demand, buffer_units, repair, tuple(elements), machines, numbers[0], numbers[1],
                Floor(*measures))


def takt_of(line):
    return Fraction(line.net, line.demand)


def target_uph(line):
    return Fraction(line.demand * 3_600_000, line.net)


def fits(load, net, demand):
    return load * demand <= net


def manual_bound(elements, net, demand):
    models = {model for element in elements for model in element.times}
    totals = (sum(element.times.get(model, 0) for element in elements if not element.inspection) for model in models)
    return max(ceil(Fraction(total * demand, net)) for total in totals)


def _ordered(elements):
    """입력 순서를 유지한 위상 순서다."""
    placed, ordered, remaining = set(), [], list(elements)
    while remaining:
        for element in remaining:
            if set(element.predecessors) <= placed:
                ordered.append(element)
                placed.add(element.id)
                remaining.remove(element)
                break
        else:
            raise ValueError("선행 순환")
    return ordered


def _idle_cost(members, ratios, net, demand):
    takt = Fraction(net, demand)
    return sum(ratio * (takt - sum(element.times.get(model, 0) for element in members)) ** 2
               for model, ratio in ratios.items())


def optimal_balance(elements, ratios, net, demand):
    """(수작업 작업장 수, 유휴 제곱합, 배치 키)의 사전순 최소를 부분집합 동적 계획으로 찾는다."""
    ordered = _ordered(elements)
    index = {element.id: position for position, element in enumerate(ordered)}
    rank = {element.id: position for position, element in enumerate(elements)}
    needs = [sum(1 << index[parent] for parent in element.predecessors) for element in ordered]
    full = (1 << len(ordered)) - 1
    memo = {}

    def station_key(members):
        return tuple(sorted((element.id for element in members), key=rank.get))

    def choices(mask):
        for position, element in enumerate(ordered):
            if element.inspection and not mask >> position & 1 and needs[position] & ~mask == 0:
                yield (element,), 1 << position

        def extend(start, chosen, used):
            for position in range(start, len(ordered)):
                element = ordered[position]
                if element.inspection or (mask | used) >> position & 1 or needs[position] & ~(mask | used):
                    continue
                members = chosen + (element,)
                if all(fits(sum(item.times.get(model, 0) for item in members), net, demand) for model in ratios):
                    yield members, used | 1 << position
                    yield from extend(position + 1, members, used | 1 << position)

        yield from extend(0, (), 0)

    def best(mask):
        if mask == full:
            return (0, Fraction(0), ())
        if mask in memo:
            return memo[mask]
        result = None
        for members, used in choices(mask):
            rest = best(mask | used)
            if rest is None:
                continue
            manual = not members[0].inspection
            cost = _idle_cost(members, ratios, net, demand) if manual else Fraction(0)
            candidate = (rest[0] + manual, rest[1] + cost, (station_key(members),) + rest[2])
            if result is None or candidate < result:
                result = candidate
        memo[mask] = result
        return result

    found = best(0)
    return None if found is None else Balance(found[2], found[0], found[1])


def heuristic_balance(elements, ratios, net, demand):
    """RPW 휴리스틱이다. 제약은 전수 탐색과 같다."""
    by_id = {element.id: element for element in elements}
    children = {element.id: set() for element in elements}
    for element in elements:
        for parent in element.predecessors:
            children[parent].add(element.id)

    def family(name):
        found = {name}
        for child in children[name]:
            found |= family(child)
        return found

    weights = {element.id: sum(ratio * by_id[name].times.get(model, 0) for name in family(element.id)
                               for model, ratio in ratios.items()) for element in elements}
    rank = {element.id: position for position, element in enumerate(elements)}
    done, stations = set(), []
    while len(done) < len(elements):
        current = []
        while True:
            placed = done | {element.id for element in current}
            candidates = [element for element in elements if element.id not in placed and not element.inspection
                          and set(element.predecessors) <= placed
                          and all(fits(sum(item.times.get(model, 0) for item in current + [element]), net, demand)
                                  for model in ratios)]
            if not candidates:
                break
            current.append(max(candidates, key=lambda element: (weights[element.id], -rank[element.id])))
        if current:
            stations.append(current)
            done |= {element.id for element in current}
            continue
        ready = [element for element in elements if element.id not in done and element.inspection
                 and set(element.predecessors) <= done]
        if not ready:
            return None
        chosen = max(ready, key=lambda element: (weights[element.id], -rank[element.id]))
        stations.append([chosen])
        done.add(chosen.id)
    manual = [members for members in stations if not members[0].inspection]
    cost = sum((_idle_cost(members, ratios, net, demand) for members in manual), Fraction(0))
    return Balance(tuple(tuple(sorted((element.id for element in members), key=rank.get)) for members in stations),
                   len(manual), cost)


def simulate(stations, routes, buffer_units, repair):
    """사건 기반 시뮬레이션이다. 같은 시각의 이동은 변화가 없을 때까지 반복한다."""
    buffers = [deque() for _ in stations]
    # 서버 상태: [상태, 경로, 시작 시각]. 상태는 idle, busy, done, down이다.
    servers = [[["idle", None, 0] for _ in range(station.servers)] for station in stations]
    waiting = deque(routes)
    events, result, repairs, remaining = [], SimResult(), [], len(routes)
    clock = 0
    order = 0

    def service(route, index):
        station = stations[index]
        time = station.times.get(route.model, 0)
        if station.inspection is None:
            return time
        return route.attempts.get(station.inspection, 0) * time

    def target_after(route, index):
        if index >= 0 and stations[index].inspection and stations[index].inspection == route.end_inspection:
            return None
        for position in range(index + 1, len(stations)):
            if service(route, position) > 0:
                return position
        return None

    def begin(route, index):
        nonlocal order
        for number, server in enumerate(servers[index]):
            if server[0] == "idle":
                duration = service(route, index)
                server[:] = ["busy", route, clock]
                order += 1
                heapq.heappush(events, (clock + duration, order, index, number))
                result.work[stations[index].id] += duration
                return True
        return False

    def free(index):
        return any(server[0] == "idle" for server in servers[index])

    def leave(route):
        nonlocal remaining
        remaining -= 1
        result.left += 1
        result.passed += route.completed
        result.good += route.good
        result.escaped += route.completed and route.defective
        result.end = clock

    def release(index, number, route):
        nonlocal order
        server = servers[index][number]
        result.blocked[stations[index].id] += clock - server[2]
        if stations[index].inspection in route.stops and repair > 0:
            server[:] = ["down", None, clock]
            order += 1
            heapq.heappush(events, (clock + repair, order, index, number))
            repairs.append((stations[index].id, clock))
        else:
            server[:] = ["idle", None, 0]

    def settle():
        changed = True
        while changed:
            changed = False
            for index in range(len(stations) - 1, -1, -1):
                for number, server in enumerate(servers[index]):
                    if server[0] != "done":
                        continue
                    route = server[1]
                    target = target_after(route, index)
                    if target is None:
                        leave(route)
                    elif not buffers[target] and free(target):
                        begin(route, target)
                    elif len(buffers[target]) < buffer_units:
                        buffers[target].append((route, clock))
                    else:
                        continue
                    release(index, number, route)
                    changed = True
            for index in range(len(stations) - 1, -1, -1):
                while buffers[index] and free(index):
                    route, arrived = buffers[index].popleft()
                    result.wait += clock - arrived
                    begin(route, index)
                    changed = True
            while waiting:
                route = waiting[0]
                target = target_after(route, -1)
                if target is None:
                    waiting.popleft()
                    leave(route)
                elif free(target):
                    waiting.popleft()
                    begin(route, target)
                else:
                    break
                changed = True

    settle()
    while remaining:
        if not events:
            raise ValueError("교착: 남은 제품이 있는데 다음 사건이 없음")
        clock = events[0][0]
        while events and events[0][0] == clock:
            _, _, index, number = heapq.heappop(events)
            server = servers[index][number]
            if server[0] == "busy":
                server[0], server[2] = "done", clock
            else:
                server[:] = ["idle", None, 0]
        settle()
    for name, start in repairs:
        result.repair[name] += max(0, min(start + repair, result.end) - start)
    return result


def _fixed(value):
    return format(value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP), ".4f")


def show(value):
    """분수를 표시 문자열로 바꾼다. 비교에는 쓰지 않는다."""
    fraction = Fraction(value)
    return _fixed(Decimal(fraction.numerator) / Decimal(fraction.denominator))


def uph(count, end):
    return Fraction(count * 3_600_000, end) if end else Fraction(0)


def cycle_limits(takt, count, visits, good_rate):
    """명목 상한과 양품 보정 상한이다. 방문이 없으면 None이다."""
    if not visits:
        return None
    return takt * count / visits, takt * count * good_rate / visits


def select_combo(candidates):
    """(면적, 총 대수, 조합, 통과) 중 통과한 것의 최솟값을 고른다."""
    passed = [item[:3] for item in candidates if item[3]]
    return min(passed)[2] if passed else None


def holdout_result(selected, value, target):
    if selected is None:
        return NO_SELECTION
    return "확인" if value >= target else "미달"


def build_stations(line, balance, combo):
    by_id = {element.id: element for element in line.elements}
    stations = []
    for number, members in enumerate(balance.stations, 1):
        items = [by_id[name] for name in members]
        models = {model for element in items for model in element.times}
        times = {model: sum(element.times.get(model, 0) for element in items) for model in models}
        inspection = items[0].step if items[0].inspection else None
        stations.append(SimStation("S" + str(number), combo[inspection] if inspection else 1, times, inspection))
    return stations


def area_of(line, combo):
    return sum(count * line.machines[name].width * (line.machines[name].depth + line.machines[name].service)
               for name, count in combo.items())


def layout_of(line, balance, combo):
    """제약 계산과 SVG가 같은 좌표를 쓴다."""
    by_id = {element.id: element for element in line.elements}
    boxes, x = [], 0
    pitch = line.buffer_units * line.floor.pitch
    for number, members in enumerate(balance.stations, 1):
        first = by_id[members[0]]
        if first.inspection:
            machine = line.machines[first.step]
            count = combo[first.step]
            depth = count * (machine.depth + machine.service) + (count - 1) * line.floor.gap
            box = dict(id="S" + str(number), elements=members, x=x, width=machine.width, depth=depth, count=count,
                       machine=machine)
        else:
            box = dict(id="S" + str(number), elements=members, x=x, width=line.manual_width, depth=line.manual_depth,
                       count=1, machine=None)
        boxes.append(box)
        x += box["width"] + pitch
    length = x - pitch
    width = max(box["depth"] for box in boxes) + line.floor.aisle * 2
    return dict(boxes=boxes, length=length, width=width,
                meets_floor=length <= line.floor.length and width <= line.floor.width, pitch=pitch)


def render_svg(line, layout, combo, title):
    scale = Fraction(1, 20)
    margin = 60

    def px(value):
        return format(float(value * scale), ".1f")

    top = 70.0
    band = float(layout["width"] * scale)
    bottom = top + band + 30
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="' + px(layout["length"] + 4000) + '" height="'
             + format(bottom + 50, ".1f") + '" font-size="11" font-family="sans-serif">']

    def text(x, y, value, anchor="start"):
        parts.append('<text x="' + format(x, ".1f") + '" y="' + format(y, ".1f") + '" text-anchor="' + anchor + '">'
                     + escape(str(value)) + "</text>")

    text(margin, 20, title)
    text(margin, 36, SYNTHETIC_NOTICE + " CAD 도면이 아니다.")
    centre = top + band / 2
    parts.append('<rect class="aisle" x="' + str(margin) + '" y="' + format(top, ".1f") + '" width="'
                 + px(layout["length"]) + '" height="' + format(band, ".1f")
                 + '" fill="none" stroke="gray" stroke-dasharray="6"/>')
    parts.append('<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto">'
                 '<path d="M0,0 L7,3 L0,6 z"/></marker></defs>')
    text(margin - 40, centre, "투입")
    for position, box in enumerate(layout["boxes"]):
        x = margin + float(box["x"] * scale)
        width, depth = float(box["width"] * scale), float(box["depth"] * scale)
        y = centre - depth / 2
        parts.append('<rect class="station" x="' + format(x, ".1f") + '" y="' + format(y, ".1f") + '" width="'
                     + format(width, ".1f") + '" height="' + format(depth, ".1f") + '" fill="none" stroke="black"/>')
        text(x, y - 16, box["id"] + (" ×" + str(box["count"]) if box["machine"] else ""))
        text(x, y + depth + 12, ",".join(box["elements"]))
        text(x, y + depth + 26, str(box["width"]) + "×" + str(box["depth"]) + "mm")
        if box["machine"]:
            machine = box["machine"]
            offset = y
            for _ in range(box["count"]):
                body = float(machine.depth * scale)
                parts.append('<rect class="machine" x="' + format(x, ".1f") + '" y="' + format(offset, ".1f")
                             + '" width="' + format(width, ".1f") + '" height="' + format(body, ".1f")
                             + '" fill="#dddddd"/>')
                parts.append('<rect class="service" x="' + format(x, ".1f") + '" y="' + format(offset + body, ".1f")
                             + '" width="' + format(width, ".1f") + '" height="'
                             + format(float(machine.service * scale), ".1f") + '" fill="none" stroke="gray"'
                             + ' stroke-dasharray="3"/>')
                offset += float((machine.depth + machine.service + line.floor.gap) * scale)
            text(x, y + depth + 40, "보전 " + str(machine.service) + "mm")
        if position + 1 < len(layout["boxes"]):
            start = x + width
            parts.append('<line x1="' + format(start, ".1f") + '" y1="' + format(centre, ".1f") + '" x2="'
                         + format(start + float(layout["pitch"] * scale), ".1f") + '" y2="' + format(centre, ".1f")
                         + '" stroke="black" marker-end="url(#arrow)"/>')
            text(start, centre - 6, "버퍼")
    text(margin + float(layout["length"] * scale) + 6, centre, "배출")
    text(margin, bottom, "라인 길이 " + str(layout["length"]) + "mm / 바닥 " + str(line.floor.length) + "mm")
    text(margin, bottom + 14, "라인 폭 " + str(layout["width"]) + "mm / 바닥 " + str(line.floor.width) + "mm")
    text(margin, bottom + 28, "통로 " + str(line.floor.aisle) + "mm, 버퍼 칸 " + str(layout["pitch"]) + "mm")
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def product_routes(config, recipe, book, seed, products):
    generator = Generator(seed, config, recipe.models, book)
    normal = generator.normal_events(products)
    analysis = build_analysis(normal, recipe.models, book)
    process = analysis.process
    attempts, last = {}, {}
    for record in analysis.all_inspections:
        counts = attempts.setdefault(record.product_id, Counter())
        counts[record.inspection] += 1
        last[record.product_id] = record.inspection
    stops = {}
    for stop in analysis.stop_history:
        stops.setdefault(stop.product_id, set()).add(book.equipment[stop.equipment])
    defective = set(generator.defective_products)
    routes = []
    # 판정기의 등록 순서가 생성 번호 순서다. 문자열로 정렬하면 GEN_10000이 GEN_1001 앞에 온다.
    for product_id, state in process.products.items():
        completed = state.status == COMPLETED
        routes.append(Route(product_id, state.model, dict(attempts.get(product_id, {})), completed,
                            product_id in defective, "" if completed else last.get(product_id, ""),
                            frozenset(stops.get(product_id, ()))))
    return routes


def _row(columns, section, **fields):
    return {column: fields.get(column, section if column == "section" else "") for column in columns}


def balance_rows(line, ratios, heuristic, optimal, visits, good_rate):
    takt = takt_of(line)
    manual = [element for element in line.elements if not element.inspection]
    inspections = sum(element.inspection for element in line.elements)
    lower = manual_bound(line.elements, line.net, line.demand)

    def summary(key, value):
        return _row(BALANCE_COLUMNS, "summary", key=key, value=value)

    rows = [_row(BALANCE_COLUMNS, "notice", text=text) for text in (ASSUMPTION_NOTICE, SYNTHETIC_NOTICE, ROUTE_NOTICE)]
    rows += [summary("net_seconds", show(Fraction(line.net, 1000))), summary("takt_seconds", show(takt / 1000)),
             summary("target_uph", show(target_uph(line))), summary("manual_lower_bound", lower),
             summary("station_lower_bound", lower + inspections),
             summary("heuristic_stations", len(heuristic.stations) if heuristic else NO_BALANCE),
             summary("optimal_stations", len(optimal.stations) if optimal else NO_BALANCE)]
    if heuristic and optimal:
        weighted = sum(ratio * element.times.get(model, 0) for element in manual for model, ratio in ratios.items())
        rows += [summary("gap", len(heuristic.stations) - len(optimal.stations)),
                 summary("manual_balance_rate", show(weighted / (optimal.manual_count * takt)))]
    by_id = {element.id: element for element in line.elements}
    for section, balance in (("heuristic", heuristic), ("optimal", optimal)):
        if balance is None:
            continue
        for number, members in enumerate(balance.stations, 1):
            for model in ratios:
                load = sum(by_id[name].times.get(model, 0) for name in members)
                rows.append(_row(
                    BALANCE_COLUMNS, section, station="S" + str(number), elements=",".join(members), model=model,
                    load_seconds=show(Fraction(load, 1000)),
                    idle_seconds="" if by_id[members[0]].inspection else show(takt / 1000 - Fraction(load, 1000))))
    if optimal is None:
        return rows
    for name in line.machines:
        rows.append(_row(BALANCE_COLUMNS, "visit", key=name, value=show(visits[name])))
    rows.append(_row(BALANCE_COLUMNS, "visit", key="good_rate", value=show(good_rate)))
    for name, machine in line.machines.items():
        element = next(item for item in line.elements if item.step == name)
        time = max(element.times.values())
        fixed = machine.load + machine.clamp + machine.unload
        for count in machine.counts:
            limits = cycle_limits(takt, count, visits[name], good_rate)
            fields = dict(가상검사시간=show(Fraction(time, 1000)),
                          자동구간=show(Fraction(machine.clamp + machine.test, 1000)),
                          점유면적=count * machine.width * (machine.depth + machine.service))
            if limits is None:
                fields.update(명목상한=NO_TARGET, 양품보정상한=NO_TARGET)
            else:
                nominal, adjusted = limits
                fields.update(
                    명목상한=show(nominal / 1000), 양품보정상한=show(adjusted / 1000),
                    양품보정허용test=show((adjusted - fixed) / 1000),
                    충족="손실 미반영 명목 조건 충족" if time <= nominal else "명목 조건 미충족",
                    양품보정="양품 보정 조건 충족" if time <= adjusted else "양품 보정 조건 미충족")
            rows.append(_row(BALANCE_COLUMNS, "spec", key=name + ":" + str(count),
                             text="".join(key + "=" + str(value) + ";" for key, value in fields.items())))
    return rows


def _rate_fields(total):
    return dict(pass_uph=show(uph(total.passed, total.end)), good_uph=show(uph(total.good, total.end)),
                escaped=total.escaped, mean_wait_seconds=show(Fraction(total.wait, 1000 * total.left)))


def _share(amount, servers, end):
    return Fraction(amount, servers * end) if end else Fraction(0)


def bottleneck_of(stations, total):
    best = max(_share(total.work[station.id], station.servers, total.end) for station in stations)
    return next(station.id for station in stations
                if _share(total.work[station.id], station.servers, total.end) == best)


def run_combo(line, balance, combo, seed_routes):
    stations = build_stations(line, balance, combo)
    total = SimResult()
    for routes in seed_routes:
        total.add(simulate(stations, routes, line.buffer_units, line.repair))
    return stations, total


def machine_order(line):
    """동률 키와 조합 표기의 순서다. 입력 파일의 키 순서와 무관하다."""
    fixed = [name for name in ("LEAK", "LIGHT", "FINAL") if name in line.machines]
    return fixed + sorted(set(line.machines) - set(fixed))


def compare(line, balance, seed_text, holdout_text, products, dev_routes, holdout_routes):
    names = machine_order(line)
    target = target_uph(line)
    meets_takt = _manual_fit(line, balance)
    rows = [_row(COMPARE_COLUMNS, "notice", value=text) for text in (COMPARE_NOTICE, SYNTHETIC_NOTICE, ROUTE_NOTICE)]
    results, candidates, station_rows = {}, [], []
    combos = [dict(zip(names, counts)) for counts in combinations_of(*(line.machines[name].counts for name in names))]
    for combo in combos:
        stations, total = run_combo(line, balance, combo, dev_routes)
        layout = layout_of(line, balance, combo)
        passes_uph = uph(total.good, total.end) >= target
        passed = passes_uph and meets_takt and layout["meets_floor"]
        key = tuple(combo[name] for name in names)
        results[key] = (combo, stations, total, layout, passes_uph)
        candidates.append((area_of(line, combo), sum(combo.values()), key, passed))
    selected = select_combo(candidates)
    for key, (combo, stations, total, layout, passes_uph) in results.items():
        label = "-".join(str(count) for count in key)
        reasons = [name for name, good in (("uph", passes_uph), ("takt", meets_takt), ("floor", layout["meets_floor"]))
                   if not good]
        rows.append(_row(COMPARE_COLUMNS, "development", combo=label, leak=combo.get("LEAK", ""),
                         light=combo.get("LIGHT", ""), final=combo.get("FINAL", ""), area_mm2=area_of(line, combo),
                         seeds=seed_text, products=products, bottleneck=bottleneck_of(stations, total),
                         meets_uph=passes_uph, meets_takt=meets_takt, meets_floor=layout["meets_floor"],
                         reject_reason=";".join(reasons), selected="선택" if key == selected else "",
                         **_rate_fields(total)))
        for station in stations:
            station_rows.append(_row(
                COMPARE_COLUMNS, "station", combo=label, seeds=seed_text, products=products, station=station.id,
                utilization=show(_share(total.work[station.id], station.servers, total.end)),
                blocked_share=show(_share(total.blocked[station.id], station.servers, total.end)),
                repair_share=show(_share(total.repair[station.id], station.servers, total.end))))
    rows += station_rows
    uph_value = None
    if selected is not None:
        combo = results[selected][0]
        stations, total = run_combo(line, balance, combo, holdout_routes)
        uph_value = uph(total.good, total.end)
        rows.append(_row(COMPARE_COLUMNS, "holdout", combo="-".join(map(str, selected)), leak=combo.get("LEAK", ""),
                         light=combo.get("LIGHT", ""), final=combo.get("FINAL", ""), seeds=holdout_text,
                         products=products, bottleneck=bottleneck_of(stations, total),
                         meets_uph=uph_value >= target, **_rate_fields(total)))
    rows.append(_row(COMPARE_COLUMNS, "selection", combo="-".join(map(str, selected)) if selected else "",
                     value=(NO_COMBO if selected is None else "선택") + " / " + holdout_result(
                         selected, uph_value, target)))
    return rows, selected, results, candidates


def _manual_fit(line, balance):
    by_id = {element.id: element for element in line.elements}
    for members in balance.stations:
        items = [by_id[name] for name in members]
        if items[0].inspection:
            continue
        for model in items[0].times:
            if not fits(sum(item.times.get(model, 0) for item in items), line.net, line.demand):
                return False
    return True


def _write_csv(path, columns, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def run(path, seed_text, holdout_text, products):
    path = Path(path)
    if products < 1:
        raise ValueError("products는 양의 정수여야 함")
    seeds, holdout = parse_seeds(seed_text), parse_seeds(holdout_text)
    if set(seeds) & set(holdout):
        raise ValueError("--seeds와 --holdout-seeds는 겹칠 수 없음")
    raw = read_line_file(path)
    config, _, recipe, book = load_setup(path.parent / raw["generator"])
    if "process_cpk" not in config:
        raise ValueError("generator는 측정 설정이어야 함")
    line = load_line(path, recipe.models)
    weights = {model: Fraction(str(value)) for model, value in config["model_weights"].items()}
    ratios = {model: value / sum(weights.values()) for model, value in weights.items()}
    heuristic = heuristic_balance(line.elements, ratios, line.net, line.demand)
    optimal = optimal_balance(line.elements, ratios, line.net, line.demand)
    stem = path.stem
    directory = Path("reports")
    directory.mkdir(exist_ok=True)
    if optimal is None:
        _write_csv(directory / (stem + "_balance.csv"), BALANCE_COLUMNS,
                   balance_rows(line, ratios, heuristic, None, {}, Fraction(0)))
        _write_csv(directory / (stem + "_compare.csv"), COMPARE_COLUMNS,
                   [_row(COMPARE_COLUMNS, "notice", value=COMPARE_NOTICE),
                    _row(COMPARE_COLUMNS, "selection", value=NO_BALANCE)])
        return NO_BALANCE, None, [directory / (stem + "_balance.csv"), directory / (stem + "_compare.csv")]
    dev_routes = [product_routes(config, recipe, book, seed, products) for seed in seeds]
    holdout_routes = [product_routes(config, recipe, book, seed, products) for seed in holdout]
    routes = [route for run_routes in dev_routes for route in run_routes]
    visits = {name: Fraction(sum(route.attempts.get(name, 0) for route in routes), len(routes)) for name in line.machines}
    good_rate = Fraction(sum(route.good for route in routes), len(routes))
    rows, selected, results, candidates = compare(line, optimal, seed_text, holdout_text, products, dev_routes,
                                                  holdout_routes)
    _write_csv(directory / (stem + "_balance.csv"), BALANCE_COLUMNS,
               balance_rows(line, ratios, heuristic, optimal, visits, good_rate))
    _write_csv(directory / (stem + "_compare.csv"), COMPARE_COLUMNS, rows)
    if selected is None:
        key = min(candidates)[2]
        title = "기준 미달 조합 " + "-".join(map(str, key))
    else:
        key = selected
        title = "선택 조합 " + "-".join(map(str, key))
    combo, _, _, layout, _ = results[key]
    if not layout["meets_floor"]:
        title += " (바닥 제약 초과)"
    with (directory / (stem + "_layout.svg")).open("w", encoding="utf-8", newline="\n") as target:
        target.write(render_svg(line, layout, combo, title))
    paths = [directory / (stem + suffix) for suffix in ("_balance.csv", "_compare.csv", "_layout.svg")]
    return ("선택" if selected else NO_COMBO), rows, paths


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("line", type=Path)
    parser.add_argument("--seeds", required=True, help="개발 시드, 예: 0-29")
    parser.add_argument("--holdout-seeds", required=True, help="확인 시드, 예: 1000-1029")
    parser.add_argument("--products", type=int, default=500)
    args = parser.parse_args(argv)
    try:
        outcome, rows, paths = run(args.line, args.seeds, args.holdout_seeds, args.products)
    except LineError as error:
        parser.exit(3, "라인 입력 오류:\n" + "\n".join(error.errors) + "\n")
    except (OSError, UnicodeError, csv.Error, ValueError, KeyError) as error:
        parser.exit(2, "오류: " + str(error) + "\n")
    print(COMPARE_NOTICE)
    if rows:
        print("combo | good_uph | area_mm2 | bottleneck | reject_reason | selected")
        for row in rows:
            if row["section"] == "development":
                print(" | ".join(str(row[column]) for column in
                                 ("combo", "good_uph", "area_mm2", "bottleneck", "reject_reason", "selected")))
        print(next(row["value"] for row in rows if row["section"] == "selection"))
    else:
        print(outcome)
    print("저장 파일: " + ", ".join(path.as_posix() for path in paths))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

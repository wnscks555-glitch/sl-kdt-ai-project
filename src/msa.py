"""합성 측정 시스템에 교차 Gage R&R과 가드밴드를 적용한다. 실제 게이지, 작업자, 부품 평가가 아니다."""

import argparse
import csv
from dataclasses import dataclass, field
from decimal import Decimal
from fractions import Fraction
import json
import math
from pathlib import Path
import random
import re

from src.anomaly import _integer, _keys, _number, _write_csv, load_process
from src.generate import confirm_value, load_setup
from src.line import show
from src.recipe_rules import judge_value


NOTICE = ("합성 측정 시스템 분석 연습이다. 실제 게이지, 작업자, 부품이 아니고 10%·30%는 널리 쓰이는 관행 값을 빌린 것이며 "
          "SL 기준이 아니다. 모의는 작업자 분산을 측정마다 독립으로 뽑는 단순화를 쓴다.")
TOP_KEYS = ("generator", "inspection", "parts", "operators", "trials", "study_seed", "gauges", "guard_multipliers",
            "products", "dev_seeds", "holdout_seeds", "max_false_accept")
GAUGE_KEYS = ("repeatability", "operator", "interaction")
GAUGE_NAME = re.compile(r"[a-z][a-z0-9_]{0,31}")
MULTIPLIER = re.compile(r"[0-9]+(\.[0-9]+)?")
SEEDS = re.compile(r"([0-9]+)-([0-9]+)")
MAX_SEED = 2 ** 31 - 1
MAX_RATIO = 100
MAX_PRODUCTS = 1000000
POOL_LIMIT = 0.25
K1 = {2: 0.8862, 3: 0.5908}
K2 = {2: 0.7071, 3: 0.5231}
K3 = {2: 0.7071, 3: 0.5231, 4: 0.4467, 5: 0.4030, 6: 0.3742, 7: 0.3534, 8: 0.3375, 9: 0.3249, 10: 0.3146}
ACCEPT_LIMIT = 10
MARGINAL_LIMIT = 30
NDC_FACTOR = 1.41
NDC_MIN = 5
LIMIT_SCALE = 1000
BETA_ITERATIONS = 300
BETA_EPSILON = 3e-14
BETA_FLOOR = 1e-300
NO_GUARD = "가드 불가"
NO_SELECTION = "기준 충족 가드밴드 없음"
NOT_VERIFIED = "검증할 선택 없음"
UNDEFINED = "판정 불가"
STUDY_COLUMNS = ("gauge", "part", "operator", "trial", "value")
GRR_COLUMNS = ("gauge", "ss_part", "ss_op", "ss_int", "ss_e", "df_part", "df_op", "df_int", "df_e", "ms_part", "ms_op",
               "ms_int", "ms_e", "p_int", "pooled", "var_e", "var_op", "var_int", "var_part", "ev", "av", "grr", "pv",
               "tv", "pct_grr", "pct_tolerance", "ndc", "ndc_ok", "verdict", "ar_ev", "ar_av", "ar_pv", "cpk_true",
               "cpk_obs")
GUARD_COLUMNS = ("section", "gauge", "operator", "multiplier", "lower", "upper", "status", "true_defects",
                 "false_accepts", "false_accept", "true_good", "false_rejects", "false_reject", "value")


class MsaError(ValueError):
    """설정 문제를 위치와 함께 모아서 보고한다. 종료 코드는 3이다."""

    def __init__(self, errors):
        super().__init__("\n".join(errors))
        self.errors = errors


@dataclass(frozen=True)
class Gauge:
    repeatability: float
    operator: float
    interaction: float


@dataclass(frozen=True)
class Settings:
    generator: Path
    inspection: str
    parts: int
    operators: int
    trials: int
    study_seed: int
    gauges: dict
    guard_multipliers: tuple
    products: int
    dev_seeds: range
    holdout_seeds: range
    max_false_accept: Fraction


def parse_seeds(text):
    """`시작-끝`을 range로 읽는다. 잘못된 문자열은 None이다."""
    match = SEEDS.fullmatch(text) if isinstance(text, str) else None
    if match is None:
        return None
    start, end = int(match.group(1)), int(match.group(2))
    return range(start, end + 1) if start <= end <= MAX_SEED else None


def _check_gauges(gauges, errors):
    if not isinstance(gauges, dict) or not 1 <= len(gauges) <= 10:
        errors.append("$.gauges: 1–10개의 객체여야 함")
        return
    for name, gauge in gauges.items():
        location = "$.gauges." + name
        if not GAUGE_NAME.fullmatch(name):
            errors.append(location + ": 이름 규칙 위반")
        if not _keys(gauge, GAUGE_KEYS, location, errors) or set(gauge) != set(GAUGE_KEYS):
            continue
        for key in GAUGE_KEYS:
            if not _number(gauge[key]) or not 0 <= gauge[key] <= MAX_RATIO:
                errors.append(location + "." + key + ": 0–100의 유한한 수여야 함")
        if _number(gauge["repeatability"]) and gauge["repeatability"] == 0:
            errors.append(location + ".repeatability: 0 초과여야 함")


def _check_multipliers(values, errors):
    location = "$.guard_multipliers"
    if not isinstance(values, list) or not values:
        errors.append(location + ": 비어 있지 않은 목록이어야 함")
        return
    if not all(isinstance(value, str) and MULTIPLIER.fullmatch(value) for value in values):
        errors.append(location + ": 소수 문자열이어야 함")
        return
    numbers = [Decimal(value) for value in values]
    if any(left >= right for left, right in zip(numbers, numbers[1:])):
        errors.append(location + ": 중복 없이 오름차순이어야 함")


def _check(data):
    errors = []
    for key in ("generator", "inspection"):
        if not isinstance(data[key], str) or not data[key].strip():
            errors.append("$." + key + ": 비어 있지 않은 문자열이어야 함")
    for key, low, high in (("parts", 2, 10), ("operators", 2, 3), ("trials", 2, 3), ("study_seed", 0, MAX_SEED),
                           ("products", 1, MAX_PRODUCTS)):
        if not _integer(data[key]) or not low <= data[key] <= high:
            errors.append("$.%s: %d–%d의 정수여야 함" % (key, low, high))
    _check_gauges(data["gauges"], errors)
    _check_multipliers(data["guard_multipliers"], errors)
    seeds = {key: parse_seeds(data[key]) for key in ("dev_seeds", "holdout_seeds")}
    for key, value in seeds.items():
        if value is None:
            errors.append("$." + key + ": `시작-끝` 형식이어야 함")
    if all(seeds.values()) and set(seeds["dev_seeds"]) & set(seeds["holdout_seeds"]):
        errors.append("$.holdout_seeds: 개발 시드와 겹침")
    if not _number(data["max_false_accept"]) or not 0 <= data["max_false_accept"] <= 1:
        errors.append("$.max_false_accept: 0–1이어야 함")
    return errors


def load_settings(path):
    path = Path(path)
    try:
        data = json.loads(path.read_bytes().decode("utf-8-sig"))
    except ValueError as error:
        raise MsaError(["$: JSON 오류: " + str(error)]) from error
    errors = []
    _keys(data, TOP_KEYS, "$", errors)
    if errors:
        raise MsaError(errors)
    errors = _check(data)
    if errors:
        raise MsaError(errors)
    gauges = {name: Gauge(**{key: value[key] for key in GAUGE_KEYS}) for name, value in data["gauges"].items()}
    return Settings(path.parent / data["generator"], data["inspection"], data["parts"], data["operators"],
                    data["trials"], data["study_seed"], gauges, tuple(data["guard_multipliers"]), data["products"],
                    parse_seeds(data["dev_seeds"]), parse_seeds(data["holdout_seeds"]),
                    Fraction(str(data["max_false_accept"])))


def _beta_fraction(a, b, x):
    """정규화 불완전 베타 함수의 연분수다. 수정 Lentz 방식이다."""
    total, up, down = a + b, a + 1, a - 1
    c = 1.0
    d = 1 - total * x / up
    d = 1 / (d if abs(d) > BETA_FLOOR else BETA_FLOOR)
    value = d
    for step in range(1, BETA_ITERATIONS + 1):
        double = 2 * step
        for numerator in (step * (b - step) * x / ((down + double) * (a + double)),
                          -(a + step) * (total + step) * x / ((a + double) * (up + double))):
            d = 1 + numerator * d
            d = 1 / (d if abs(d) > BETA_FLOOR else BETA_FLOOR)
            c = 1 + numerator / c
            c = c if abs(c) > BETA_FLOOR else BETA_FLOOR
            change = d * c
            value *= change
        if abs(change - 1) < BETA_EPSILON:
            break
    return value


def beta_tail(a, b, x):
    """정규화 불완전 베타 I_x(a, b)다."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    front = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1) / (a + b + 2):
        return front * _beta_fraction(a, b, x) / a
    return 1 - front * _beta_fraction(b, a, 1 - x) / b


def f_tail(d1, d2, statistic):
    """P(F(d1, d2) ≥ x)다."""
    if statistic <= 0:
        return 1.0
    return beta_tail(d2 / 2, d1 / 2, float(Fraction(d2) / (d2 + d1 * Fraction(statistic))))


@dataclass(frozen=True)
class Anova:
    ss_part: Fraction
    ss_op: Fraction
    ss_int: Fraction
    ss_e: Fraction
    df_part: int
    df_op: int
    df_int: int
    df_e: int
    p_int: float
    pooled: bool
    var_e: Fraction
    var_op: Fraction
    var_int: Fraction
    var_part: Fraction

    @property
    def ms_part(self):
        return self.ss_part / self.df_part

    @property
    def ms_op(self):
        return self.ss_op / self.df_op

    @property
    def ms_int(self):
        return self.ss_int / self.df_int

    @property
    def ms_e(self):
        return self.ss_e / self.df_e

    @property
    def grr_squared(self):
        return self.var_e + self.var_op + self.var_int

    @property
    def tv_squared(self):
        return self.grr_squared + self.var_part

    @property
    def ev(self):
        return math.sqrt(self.var_e)

    @property
    def av(self):
        return math.sqrt(self.var_op + self.var_int)

    @property
    def grr(self):
        return math.sqrt(self.grr_squared)

    @property
    def pv(self):
        return math.sqrt(self.var_part)

    @property
    def tv(self):
        return math.sqrt(self.tv_squared)


def _mean(values):
    return sum(values) / len(values)


def _interaction_tail(ms_int, ms_e, df_int, df_e):
    if ms_e == 0:
        return 0.0 if ms_int > 0 else 1.0
    return f_tail(df_int, df_e, ms_int / ms_e)


def anova(study):
    """`study[부품][작업자]`는 반복 측정 문자열 목록이다. 계산은 소수 문자열의 Fraction으로 한다."""
    data = [[[Fraction(value) for value in cell] for cell in row] for row in study]
    p, o, r = len(data), len(data[0]), len(data[0][0])
    cells = [[_mean(cell) for cell in row] for row in data]
    parts = [_mean(row) for row in cells]
    operators = [_mean([row[j] for row in cells]) for j in range(o)]
    grand = _mean(parts)
    ss_part = o * r * sum((value - grand) ** 2 for value in parts)
    ss_op = p * r * sum((value - grand) ** 2 for value in operators)
    ss_int = r * sum((cells[i][j] - parts[i] - operators[j] + grand) ** 2 for i in range(p) for j in range(o))
    ss_e = sum((value - cells[i][j]) ** 2 for i in range(p) for j in range(o) for value in data[i][j])
    df_part, df_op, df_int, df_e = p - 1, o - 1, (p - 1) * (o - 1), p * o * (r - 1)
    ms_part, ms_op, ms_int, ms_e = ss_part / df_part, ss_op / df_op, ss_int / df_int, ss_e / df_e
    p_int = _interaction_tail(ms_int, ms_e, df_int, df_e)
    pooled = p_int > POOL_LIMIT
    if pooled:
        var_e = (ss_int + ss_e) / (df_int + df_e)
        var_int = Fraction(0)
        term = var_e
    else:
        var_e = ms_e
        var_int = max(Fraction(0), (ms_int - ms_e) / r)
        term = ms_int
    var_op = max(Fraction(0), (ms_op - term) / (p * r))
    var_part = max(Fraction(0), (ms_part - term) / (o * r))
    return Anova(ss_part, ss_op, ss_int, ss_e, df_part, df_op, df_int, df_e, p_int, pooled, var_e, var_op, var_int,
                 var_part)


def average_range(study):
    """평균·범위법 참고값이다. K1은 칸 수 보정이 없는 고정 근삿값이다. 판정에 쓰지 않는다."""
    data = [[[float(value) for value in cell] for cell in row] for row in study]
    p, o, r = len(data), len(data[0]), len(data[0][0])
    ranges = [max(cell) - min(cell) for row in data for cell in row]
    ev = _mean(ranges) * K1[r]
    operators = [_mean([value for row in data for value in row[j]]) for j in range(o)]
    parts = [_mean([value for cell in row for value in cell]) for row in data]
    av = math.sqrt(max(0.0, ((max(operators) - min(operators)) * K2[o]) ** 2 - ev ** 2 / (p * r)))
    return ev, av, (max(parts) - min(parts)) * K3[p]


def percent_grr(result):
    """제곱 비율로 계산해 10, 30 같은 경계가 부동소수 오차로 넘어가지 않게 한다. 총변동이 0이면 None이다."""
    if result.tv_squared == 0:
        return None
    return math.sqrt(10000 * result.grr_squared / result.tv_squared)


def distinct_categories(result):
    if result.grr_squared == 0:
        return None
    return math.floor(NDC_FACTOR * result.pv / result.grr)


def verdict(percent):
    if percent is None:
        return UNDEFINED
    if percent < ACCEPT_LIMIT:
        return "허용"
    return "조건부" if percent <= MARGINAL_LIMIT else "부적합"


def ndc_ok(ndc):
    return None if ndc is None else ndc >= NDC_MIN


def observed_cpk(cpk, sigma, grr):
    """공정이 중앙이라 가정한 관측 Cpk다. σ² 대신 σ²+GRR²를 쓴다."""
    return cpk / math.hypot(1.0, grr / sigma)


def build_study(rng, center, sigma, gauge, settings):
    """호출 순서가 시드 재현의 일부다. 교호작용이 0이어도 호출한다."""
    p, o, r = settings.parts, settings.operators, settings.trials
    truths = [rng.gauss(center, sigma) for _ in range(p)]
    offsets = [rng.gauss(0, gauge.operator * sigma) for _ in range(o)]
    interactions = [[rng.gauss(0, gauge.interaction * sigma) for _ in range(o)] for _ in range(p)]
    return [[[confirm_value(truths[i] + offsets[j] + interactions[i][j] + rng.gauss(0, gauge.repeatability * sigma))
              for _ in range(r)] for j in range(o)] for i in range(p)]


def noise_sigma(gauge, sigma):
    return sigma * math.sqrt(gauge.repeatability ** 2 + gauge.operator ** 2 + gauge.interaction ** 2)


def fixed_noise_sigma(gauge, sigma):
    """작업자 분산을 고정 편차로 뺀 측정 잡음이다."""
    return sigma * math.sqrt(gauge.repeatability ** 2 + gauge.interaction ** 2)


def operator_offsets(operators, ratio, sigma):
    """난수가 아닌 고정 편차다. 3명이면 −1, 0, +1배, 2명이면 −1, +1배다."""
    return [(2 * j / (operators - 1) - 1) * ratio * sigma for j in range(operators)]


def draw_truth(rng, process):
    """결함을 뽑은 뒤 참값을 뽑는다. 호출 순서가 시드 재현의 일부다."""
    defective = rng.random() < process.defect_probability
    return confirm_value(rng.gauss(process.center + (process.defect_shift if defective else 0) * process.sigma,
                                   process.sigma))


def sample_pairs(seed, products, process, noise):
    """(참값, 측정값) 문자열 쌍이다. 오차는 확정한 참값에 더한다."""
    rng = random.Random(seed)
    pairs = []
    for _ in range(products):
        truth = draw_truth(rng, process)
        pairs.append((truth, confirm_value(float(truth) + rng.gauss(0, noise))))
    return pairs


def fixed_operator_pairs(seed, products, process, offsets, noise):
    """제품 n은 작업자 n mod o가 측정한다. 작업자별 쌍 목록을 돌려준다."""
    rng = random.Random(seed)
    pairs = [[] for _ in offsets]
    for product in range(products):
        operator = product % len(offsets)
        truth = draw_truth(rng, process)
        pairs[operator].append((truth, confirm_value(float(truth) + rng.gauss(offsets[operator], noise))))
    return pairs


def _thousandths(number):
    """Decimal 문맥의 자릿수 제한을 거치지 않고 소수 셋째 자리 값을 만든다."""
    return Decimal((int(number < 0), tuple(map(int, str(abs(number)))), -3))


def acceptance_limits(lsl, usl, multiplier, grr):
    """항상 안쪽으로 자른다. 반올림하면 12.9995가 13.000이 되어 규격 밖 값을 합격시킨다. 불가능하면 None이다."""
    width = Fraction(multiplier) * Fraction(repr(grr))
    lower = math.ceil((Fraction(lsl) + width) * LIMIT_SCALE)
    upper = math.floor((Fraction(usl) - width) * LIMIT_SCALE)
    return None if lower >= upper else (_thousandths(lower), _thousandths(upper))


@dataclass
class Tally:
    true_defects: int = 0
    false_accepts: int = 0
    true_good: int = 0
    false_rejects: int = 0

    @property
    def false_accept(self):
        return Fraction(self.false_accepts, self.true_defects) if self.true_defects else None

    @property
    def false_reject(self):
        return Fraction(self.false_rejects, self.true_good) if self.true_good else None

    def add(self, pairs, item, limits):
        lower, upper = limits
        for truth, measured in pairs:
            accepted = lower <= Decimal(measured) <= upper
            if judge_value(truth, item) == "FAIL":
                self.true_defects += 1
                self.false_accepts += accepted
            else:
                self.true_good += 1
                self.false_rejects += not accepted


@dataclass
class Candidate:
    multiplier: str
    limits: object
    tally: Tally = field(default_factory=Tally)


def select_guard(rows, limit):
    """`(g, false_accept, false_reject)`를 받는다. 조건을 만족하고 오불합격이 가장 작은 g다. 동률이면 작은 g다."""
    valid = [(reject, Decimal(multiplier), multiplier) for multiplier, accept, reject in rows
             if accept is not None and reject is not None and accept <= limit]
    return min(valid)[2] if valid else None


def holdout_result(selected, tally, limit):
    if selected is None:
        return NOT_VERIFIED
    accept = tally.false_accept
    return "확인" if accept is not None and accept <= limit else "미달"


def evaluate_seeds(seeds, settings, process, noise, candidates):
    for seed in seeds:
        pairs = sample_pairs(seed, settings.products, process, noise)
        for candidate in candidates:
            if candidate.limits is not None:
                candidate.tally.add(pairs, process.item, candidate.limits)


def _text(value, digits=4):
    if value is None:
        return ""
    if digits != 4:
        return "%.*f" % (digits, value)
    return show(Fraction(repr(value)) if isinstance(value, float) else value)


def _flag(value):
    return "" if value is None else int(value)


def grr_row(name, study, result, tolerance, process, cpk):
    percent = percent_grr(result)
    ndc = distinct_categories(result)
    ar_ev, ar_av, ar_pv = average_range(study)
    return {
        "gauge": name, "ss_part": _text(result.ss_part), "ss_op": _text(result.ss_op), "ss_int": _text(result.ss_int),
        "ss_e": _text(result.ss_e), "df_part": result.df_part, "df_op": result.df_op, "df_int": result.df_int,
        "df_e": result.df_e, "ms_part": _text(result.ms_part), "ms_op": _text(result.ms_op),
        "ms_int": _text(result.ms_int), "ms_e": _text(result.ms_e), "p_int": _text(result.p_int, 6),
        "pooled": _flag(result.pooled), "var_e": _text(result.var_e), "var_op": _text(result.var_op),
        "var_int": _text(result.var_int), "var_part": _text(result.var_part), "ev": _text(result.ev),
        "av": _text(result.av), "grr": _text(result.grr), "pv": _text(result.pv), "tv": _text(result.tv),
        "pct_grr": _text(percent), "pct_tolerance": _text(100 * 6 * result.grr / tolerance),
        "ndc": "" if ndc is None else ndc, "ndc_ok": _flag(ndc_ok(ndc)), "verdict": verdict(percent),
        "ar_ev": _text(ar_ev), "ar_av": _text(ar_av), "ar_pv": _text(ar_pv), "cpk_true": _text(cpk),
        "cpk_obs": _text(observed_cpk(cpk, process.sigma, result.grr)),
    }


def _guard_row(section, **fields):
    row = {column: "" for column in GUARD_COLUMNS}
    row["section"] = section
    row.update(fields)
    return row


def _tally_fields(tally):
    return {"true_defects": tally.true_defects, "false_accepts": tally.false_accepts,
            "false_accept": _text(tally.false_accept), "true_good": tally.true_good,
            "false_rejects": tally.false_rejects, "false_reject": _text(tally.false_reject)}


def _limit_fields(limits):
    if limits is None:
        return {"status": NO_GUARD}
    return {"lower": str(limits[0]), "upper": str(limits[1])}


def candidates_of(settings, process, grr):
    item = process.item
    return [Candidate(multiplier, acceptance_limits(item.lsl, item.usl, multiplier, grr))
            for multiplier in settings.guard_multipliers]


def guard_gauge(name, gauge, grr, settings, process):
    """게이지 하나의 개발, 선택, 홀드아웃, 민감도 행이다. 게이지끼리는 고르지 않는다."""
    candidates = candidates_of(settings, process, grr)
    noise = noise_sigma(gauge, process.sigma)
    evaluate_seeds(settings.dev_seeds, settings, process, noise, candidates)
    development = [_guard_row("development", gauge=name, multiplier=candidate.multiplier,
                              **_limit_fields(candidate.limits),
                              **({} if candidate.limits is None else _tally_fields(candidate.tally)))
                   for candidate in candidates]
    rows = [(candidate.multiplier, candidate.tally.false_accept, candidate.tally.false_reject)
            for candidate in candidates if candidate.limits is not None]
    selected = select_guard(rows, settings.max_false_accept)
    chosen = next((candidate for candidate in candidates if candidate.multiplier == selected), None)
    selection = _guard_row("selection", gauge=name, multiplier=selected or "", value="" if selected else NO_SELECTION)
    if chosen is None:
        holdout = _guard_row("holdout", gauge=name, value=NOT_VERIFIED)
        sensitivity = [_guard_row("operator_sensitivity", gauge=name, value=NOT_VERIFIED)]
        return development + [selection, holdout] + sensitivity
    final = Candidate(selected, chosen.limits)
    evaluate_seeds(settings.holdout_seeds, settings, process, noise, [final])
    holdout = _guard_row("holdout", gauge=name, multiplier=selected, **_limit_fields(final.limits),
                         **_tally_fields(final.tally),
                         value=holdout_result(selected, final.tally, settings.max_false_accept))
    return development + [selection, holdout] + sensitivity_rows(name, gauge, final, settings, process)


def sensitivity_rows(name, gauge, chosen, settings, process):
    offsets = operator_offsets(settings.operators, gauge.operator, process.sigma)
    noise = fixed_noise_sigma(gauge, process.sigma)
    tallies = [Tally() for _ in offsets]
    for seed in settings.holdout_seeds:
        for tally, pairs in zip(tallies, fixed_operator_pairs(seed, settings.products, process, offsets, noise)):
            tally.add(pairs, process.item, chosen.limits)
    return [_guard_row("operator_sensitivity", gauge=name, operator=index + 1, multiplier=chosen.multiplier,
                       **_limit_fields(chosen.limits), **_tally_fields(tally))
            for index, tally in enumerate(tallies)]


def study_rows(name, study):
    return [{"gauge": name, "part": i + 1, "operator": j + 1, "trial": k + 1, "value": value}
            for i, row in enumerate(study) for j, cell in enumerate(row) for k, value in enumerate(cell)]


def analyze(settings, process, cpk):
    """보고서 행을 전부 메모리에서 만든다."""
    tolerance = float(process.item.usl) - float(process.item.lsl)
    studies, grr_rows, guard_rows = [], [], [_guard_row("notice", value=NOTICE)]
    for order, (name, gauge) in enumerate(settings.gauges.items()):
        rng = random.Random(settings.study_seed + order)
        study = build_study(rng, process.center, process.sigma, gauge, settings)
        result = anova(study)
        studies.extend(study_rows(name, study))
        grr_rows.append(grr_row(name, study, result, tolerance, process, cpk))
        guard_rows.extend(guard_gauge(name, gauge, result.grr, settings, process))
    return studies, grr_rows, guard_rows


def run(path):
    path = Path(path)
    settings = load_settings(path)
    process = load_process(settings)
    config = load_setup(settings.generator)[0]
    studies, grr_rows, guard_rows = analyze(settings, process, config["process_cpk"])
    directory = Path("reports")
    directory.mkdir(exist_ok=True)
    written = [directory / (path.stem + suffix) for suffix in ("_study.csv", "_grr.csv", "_guard.csv")]
    _write_csv(written[0], STUDY_COLUMNS, studies)
    _write_csv(written[1], GRR_COLUMNS, grr_rows)
    _write_csv(written[2], GUARD_COLUMNS, guard_rows)
    return grr_rows, guard_rows, written


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    args = parser.parse_args(argv)
    try:
        grr_rows, guard_rows, written = run(args.config)
    except MsaError as error:
        parser.exit(3, "측정 시스템 분석 입력 오류:\n" + "\n".join(error.errors) + "\n")
    except (OSError, UnicodeError, csv.Error, ValueError, KeyError) as error:
        parser.exit(2, "오류: " + str(error) + "\n")
    print(NOTICE)
    print("gauge | pct_grr | ndc | verdict | cpk_obs")
    for row in grr_rows:
        print(" | ".join(str(row[column]) for column in ("gauge", "pct_grr", "ndc", "verdict", "cpk_obs")))
    print("gauge | selected | holdout | false_accept | false_reject")
    for row in guard_rows:
        if row["section"] == "holdout":
            print(" | ".join(str(row[column]) for column in ("gauge", "multiplier", "value", "false_accept",
                                                             "false_reject")))
    print("저장 파일: " + ", ".join(item.as_posix() for item in written))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

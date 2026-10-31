"""합성 측정열에서 평균 이동 뒤의 변화를 검출하는 방법을 비교한다. 예지보전이나 실제 설비 데이터가 아니다."""

import argparse
from bisect import bisect_left
import csv
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction
import json
import math
from operator import mul
from pathlib import Path
import random
import sys

from src.equipment import EquipmentState
from src.generate import confirm_value, load_setup
from src.recipe import is_measured
from src.recipe_rules import judge_value


NOTICE = ("합성 평균 이동 가정 안의 비교다. 실제 설비 데이터가 아니고, 예지보전 구현이나 이상 예측이 아니다. "
          "정지 뒤 생산 변화와 설비 전환은 모의하지 않는다.")
TOP_KEYS = ("generator", "inspection", "length", "onset_min", "onset_max", "shifts", "window", "ewma_lambda", "splits",
            "learning_rate", "iterations", "l2", "false_limit", "min_detection", "min_shift_detection",
            "repair_minutes")
SPLITS = ("train", "validation", "holdout")
FEATURES = ("mean", "sd", "max", "slope", "ewma", "fail_share")
METHODS = ("rule_3_2", "moving_average", "logistic")
SCALE = 10000
RULE_WINDOW = 3
RULE_FAILS = 2
GRADIENT_LIMIT = 1e-3
NO_THRESHOLD = "임계값 없음"
NO_METHOD = "기준 충족 방법 없음"
NO_SELECTION = "검증할 선택 없음"
METHOD_COLUMNS = ("section", "method", "shift", "threshold", "candidates", "detection_rate", "early", "missed",
                  "mean_delay_cost", "mean_detected_delay", "false_per_1000", "suspect_output", "false_stops",
                  "stop_minutes", "value")
MODEL_COLUMNS = ("section", "name", "value")
REPLAY_COLUMNS = (("seed", "method", "onset", "status", "t", "value", "window_values", "ewma_prev")
                  + FEATURES + tuple("s_" + name for name in FEATURES) + ("z", "p", "threshold", "alarm"))


class AnomalyError(ValueError):
    """설정 문제를 위치와 함께 모아서 보고한다. 종료 코드는 3이다."""

    def __init__(self, errors):
        super().__init__("\n".join(errors))
        self.errors = errors


@dataclass(frozen=True)
class Settings:
    generator: Path
    inspection: str
    length: int
    onset_min: int
    onset_max: int
    shifts: tuple
    window: int
    ewma_lambda: float
    splits: dict
    learning_rate: float
    iterations: int
    l2: float
    false_limit: float
    min_detection: float
    min_shift_detection: float
    repair_minutes: float


@dataclass(frozen=True)
class Process:
    item: object
    center: float
    sigma: float
    defect_probability: float
    defect_shift: float


@dataclass
class Scenario:
    seed: int
    shift: float
    onset: object
    values: list
    fails: list
    ewma: list
    features: list


def _number(value):
    """큰 정수는 float로 바꾸면 넘치므로 비교만 한다."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return abs(value) <= sys.float_info.max


def _integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _keys(data, allowed, location, errors):
    if not isinstance(data, dict):
        errors.append(location + ": 객체여야 함")
        return False
    errors.extend(location + "." + key + ": 없는 키" for key in allowed if key not in data)
    errors.extend(location + "." + key + ": 허용 밖 키" for key in data if key not in allowed)
    return True


def _check_splits(data, shifts, errors):
    if not _keys(data, SPLITS, "$.splits", errors):
        return
    ranges = []
    for name in SPLITS:
        location = "$.splits." + name
        split = data.get(name)
        if not _keys(split, ("seed_start", "count"), location, errors) or len(split) != 2:
            continue
        start, count = split.get("seed_start"), split.get("count")
        if not _integer(start) or start < 0:
            errors.append(location + ".seed_start: 0 이상의 정수여야 함")
            continue
        if not _integer(count) or count < 1 or (shifts and count % (2 * len(shifts))):
            errors.append(location + ".count: 2 × len(shifts)의 양의 배수여야 함")
            continue
        ranges.append((start, start + count))
    ranges.sort()
    if any(left[1] > right[0] for left, right in zip(ranges, ranges[1:])):
        errors.append("$.splits: 시드 범위가 겹침")


def _check(data):
    errors = []
    for key in ("generator", "inspection"):
        if not isinstance(data[key], str) or not data[key].strip():
            errors.append("$." + key + ": 비어 있지 않은 문자열이어야 함")
    for key in ("length", "onset_min", "onset_max", "window", "iterations"):
        if not _integer(data[key]):
            errors.append("$." + key + ": 정수여야 함")
    for key in ("ewma_lambda", "learning_rate", "l2", "false_limit", "min_detection", "min_shift_detection",
                "repair_minutes"):
        if not _number(data[key]):
            errors.append("$." + key + ": 유한한 수여야 함")
    if errors:
        return errors
    if data["window"] < 2:
        errors.append("$.window: 2 이상이어야 함")
    if data["iterations"] < 1:
        errors.append("$.iterations: 1 이상이어야 함")
    if not data["window"] <= data["onset_min"] <= data["onset_max"] < data["length"]:
        errors.append("$.onset_min: window ≤ onset_min ≤ onset_max < length여야 함")
    if not 0 < data["ewma_lambda"] <= 1:
        errors.append("$.ewma_lambda: 0 초과 1 이하여야 함")
    for key in ("learning_rate", "l2", "false_limit", "repair_minutes"):
        if data[key] <= 0:
            errors.append("$." + key + ": 양수여야 함")
    for key in ("min_detection", "min_shift_detection"):
        if not 0 <= data[key] <= 1:
            errors.append("$." + key + ": 0–1이어야 함")
    shifts = data["shifts"]
    valid = isinstance(shifts, list) and shifts and all(_number(value) and value > 0 for value in shifts)
    if not valid or len(set(shifts)) != len(shifts):
        errors.append("$.shifts: 비어 있지 않고 서로 다른 양수 목록이어야 함")
        shifts = []
    _check_splits(data["splits"], shifts, errors)
    return errors


def load_settings(path):
    path = Path(path)
    try:
        data = json.loads(path.read_bytes().decode("utf-8-sig"))
    except ValueError as error:
        raise AnomalyError(["$: JSON 오류: " + str(error)]) from error
    errors = []
    _keys(data, TOP_KEYS, "$", errors)
    if errors:
        raise AnomalyError(errors)
    errors = _check(data)
    if errors:
        raise AnomalyError(errors)
    values = {key: data[key] for key in TOP_KEYS}
    values["generator"] = path.parent / data["generator"]
    values["shifts"] = tuple(data["shifts"])
    values["splits"] = {name: range(data["splits"][name]["seed_start"],
                                    data["splits"][name]["seed_start"] + data["splits"][name]["count"])
                        for name in SPLITS}
    return Settings(**values)


def load_process(settings):
    config, _, recipe, book = load_setup(settings.generator)
    if "process_cpk" not in config or not is_measured(recipe.models):
        raise ValueError("generator는 측정 설정이어야 함")
    items = {(item.lsl, item.usl): item for model in recipe.models.values() for item in model.inspections
             if item.id == settings.inspection}
    if len(items) != 1 or None in next(iter(items)):
        raise ValueError(settings.inspection + ": 모든 모델에서 같은 양측 규격이어야 함")
    item = next(iter(items.values()))
    lsl, usl = float(item.lsl), float(item.usl)
    return Process(item, (lsl + usl) / 2, (usl - lsl) / (6 * config["process_cpk"]),
                   config["defective_product_probability"], config["defect_shift_sigma"])


def measure(rng, process, fault_shift):
    """결함 여부를 뽑은 뒤 값을 뽑는다. 호출 순서가 시드 재현의 일부다."""
    defective = rng.random() < process.defect_probability
    shift = (process.defect_shift if defective else 0) + fault_shift
    return confirm_value(rng.gauss(process.center + shift * process.sigma, process.sigma))


def assignment(index, shifts):
    """분할 안의 위치로 배정한다. 짝수는 정상(0)이고 홀수는 이동량을 돌아가며 쓴다."""
    return 0 if index % 2 == 0 else shifts[((index - 1) // 2) % len(shifts)]


def window_features(x, fails, ewma, window, t):
    """현재값을 포함한 창의 특징이다. t와 그 이전 값만 쓴다."""
    values = x[t - window + 1:t + 1]
    mean = sum(values) / window
    variance = sum((value - mean) ** 2 for value in values) / (window - 1)
    center = (window - 1) / 2
    denominator = sum((time - center) ** 2 for time in range(window))
    slope = sum((time - center) * value for time, value in enumerate(values)) / denominator
    return (mean, math.sqrt(variance), max(values), slope, ewma[t], sum(fails[t - window + 1:t + 1]) / window)


def ewma_of(x, weight):
    series = []
    previous = 0.0
    for value in x:
        previous = weight * value + (1 - weight) * previous
        series.append(previous)
    return series


def build_scenario(seed, fault_shift, settings, process):
    rng = random.Random(seed)
    onset = rng.randint(settings.onset_min, settings.onset_max) if fault_shift else None
    values = [measure(rng, process, fault_shift if onset is not None and t >= onset else 0)
              for t in range(settings.length)]
    x = [(float(value) - process.center) / process.sigma for value in values]
    fails = [judge_value(value, process.item) == "FAIL" for value in values]
    ewma = ewma_of(x, settings.ewma_lambda)
    features = [window_features(x, fails, ewma, settings.window, t)
                for t in range(settings.window - 1, settings.length)]
    return Scenario(seed, fault_shift, onset, values, fails, ewma, features)


def build_split(seeds, settings, process):
    return [build_scenario(seed, assignment(index, settings.shifts), settings, process)
            for index, seed in enumerate(seeds)]


def standardizer(rows):
    """특징별 평균과 모집단 표준편차다. 표준편차가 0이면 1로 나눈다."""
    count = len(rows)
    means = [sum(column) / count for column in zip(*rows)]
    scales = []
    for column, mean in zip(zip(*rows), means):
        scale = math.sqrt(sum((value - mean) ** 2 for value in column) / count)
        scales.append(scale or 1.0)
    return means, scales


def standardize(row, means, scales):
    return [(value - mean) / scale for value, mean, scale in zip(row, means, scales)]


def sigmoid(z):
    """부호별 식이다. 지수의 인자가 양수가 되지 않아 어떤 z에서도 넘치지 않는다."""
    return 1 / (1 + math.exp(-z)) if z >= 0 else math.exp(z) / (1 + math.exp(z))


def sample_loss(z, label):
    return max(z, 0.0) - label * z + math.log1p(math.exp(-abs(z)))


def _gradient(columns, labels, weights, bias, l2):
    linear = [bias] * len(labels)
    for weight, column in zip(weights, columns):
        linear = [left + weight * right for left, right in zip(linear, column)]
    errors = [sigmoid(z) - label for z, label in zip(linear, labels)]
    count = len(labels)
    gradient = [sum(map(mul, errors, column)) / count + l2 * weight for column, weight in zip(columns, weights)]
    return gradient, sum(errors) / count


def fit_logistic(rows, labels, learning_rate, iterations, l2):
    """배치 경사 하강이다. 초기값은 0이고 난수를 쓰지 않는다. 노름은 마지막 계수의 전체 경사다."""
    columns = [list(column) for column in zip(*rows)]
    weights = [0.0] * len(columns)
    bias = 0.0
    for _ in range(iterations):
        gradient, bias_gradient = _gradient(columns, labels, weights, bias, l2)
        weights = [weight - learning_rate * step for weight, step in zip(weights, gradient)]
        bias -= learning_rate * bias_gradient
    gradient, bias_gradient = _gradient(columns, labels, weights, bias, l2)
    norm = math.sqrt(sum(step * step for step in gradient) + bias_gradient * bias_gradient)
    return weights, bias, norm


def linear_score(row, weights, bias):
    return bias + sum(map(mul, weights, row))


@dataclass(frozen=True)
class Model:
    means: list
    scales: list
    weights: list
    bias: float
    norm: float
    positive: int
    negative: int

    def z(self, row):
        return linear_score(standardize(row, self.means, self.scales), self.weights, self.bias)


def training_rows(scenarios, window):
    rows, labels = [], []
    for scenario in scenarios:
        for index, row in enumerate(scenario.features):
            t = index + window - 1
            rows.append(row)
            labels.append(1 if scenario.onset is not None and t >= scenario.onset else 0)
    return rows, labels


def fit_model(scenarios, settings):
    rows, labels = training_rows(scenarios, settings.window)
    means, scales = standardizer(rows)
    scaled = [standardize(row, means, scales) for row in rows]
    weights, bias, norm = fit_logistic(scaled, labels, settings.learning_rate, settings.iterations, settings.l2)
    return Model(means, scales, weights, bias, norm, sum(labels), len(labels) - sum(labels))


def quantize(score):
    """판단값을 소수 넷째 자리 ROUND_HALF_UP 정수로 바꾼다. 비교는 이 값으로 한다."""
    return int((Decimal(repr(score)) * SCALE).to_integral_value(rounding=ROUND_HALF_UP))


def stop_flags(fails, window, need):
    """기존 EquipmentState.record와 같게 쌓은 위치별 정지 판정이다. t = 0부터 낸다."""
    flags = []
    for t in range(len(fails)):
        flags.append(sum(fails[max(0, t - window + 1):t + 1]) >= need)
    return flags


def reproduce_stops(fails, book):
    """기존 동작 재현 함수다. 재가동 없이 위치별로 record를 그대로 호출한다."""
    state = EquipmentState()
    flags = []
    for t, fail in enumerate(fails):
        state = state.record("FAIL" if fail else "PASS", str(t), book)
        flags.append(state.stopped_at_seq is not None)
    return flags


def first_rule_alarm(fails, window, need, start):
    """비교용 3:2다. 창은 t = 0부터 쌓고, 판단 시점 이후의 첫 참만 경보로 인정한다."""
    flags = stop_flags(fails, window, need)
    return next((t for t in range(start, len(flags)) if flags[t]), None)


@dataclass
class Metrics:
    faults: int = 0
    detected: int = 0
    early: int = 0
    missed: int = 0
    cost: int = 0
    detected_delay: int = 0
    alarms: int = 0
    exposure: int = 0
    scenarios: int = 0
    first_alarms: int = 0
    suspect: int = 0
    by_shift: dict = field(default_factory=dict)

    @property
    def detection_rate(self):
        return Fraction(self.detected, self.faults) if self.faults else None

    @property
    def mean_cost(self):
        return Fraction(self.cost, self.faults) if self.faults else None

    @property
    def mean_detected(self):
        return Fraction(self.detected_delay, self.detected) if self.detected else None

    @property
    def false_per_1000(self):
        return Fraction(self.alarms * 1000, self.exposure) if self.exposure else None

    @property
    def suspect_output(self):
        return Fraction(self.suspect, self.faults) if self.faults else None

    @property
    def stop_minutes_per_1000(self):
        return Fraction(self.first_alarms * 1000, self.scenarios) if self.scenarios else None

    def shift_rate(self, shift):
        detected, total = self.by_shift[shift]
        return Fraction(detected, total)


def add_outcome(metrics, shift, onset, alarm, length, window):
    """시나리오 하나의 원시 값을 더한다. 경보가 나면 그 측정까지 세고 노출을 끝낸다."""
    metrics.scenarios += 1
    metrics.first_alarms += alarm is not None
    first = window - 1
    if onset is None:
        last = length - 1
        if alarm is None:
            metrics.exposure += last - first + 1
        else:
            metrics.exposure += alarm - first + 1
            metrics.alarms += 1
        return
    metrics.faults += 1
    late = length - onset
    detected, total = metrics.by_shift.get(shift, (0, 0))
    if alarm is None:
        metrics.missed += 1
        metrics.cost += late
        metrics.suspect += late
        metrics.exposure += onset - first
    elif alarm < onset:
        metrics.early += 1
        metrics.cost += late
        metrics.suspect += late
        metrics.exposure += alarm - first + 1
        metrics.alarms += 1
    else:
        metrics.detected += 1
        detected += 1
        delay = alarm - onset
        metrics.cost += delay
        metrics.detected_delay += delay
        metrics.suspect += delay + 1
        metrics.exposure += onset - first
    metrics.by_shift[shift] = (detected, total + 1)


def measure_alarms(outcomes, length, window):
    metrics = Metrics()
    for shift, onset, alarm in outcomes:
        add_outcome(metrics, shift, onset, alarm, length, window)
    return metrics


def passes(metrics, settings):
    """임계값과 방법 선택의 공통 조건이다."""
    if metrics.false_per_1000 is None or metrics.detection_rate is None:
        return False
    return (metrics.false_per_1000 <= Fraction(str(settings.false_limit))
            and metrics.detection_rate >= Fraction(str(settings.min_detection))
            and all(metrics.shift_rate(shift) >= Fraction(str(settings.min_shift_detection))
                    for shift in metrics.by_shift))


def select_threshold(candidates, settings):
    """`(h, Metrics)` 후보 중 조건을 만족하고 비용이 가장 작은 것을 고른다. 동률이면 큰 h다."""
    valid = [(metrics.mean_cost, -threshold, threshold, metrics) for threshold, metrics in candidates
             if passes(metrics, settings)]
    if not valid:
        return None
    best = min(valid, key=lambda row: row[:2])
    return best[2], best[3]


def select_method(rows, settings):
    """`(이름, Metrics 또는 None)`을 표의 순서로 받아 고른다. 동률이면 앞선 방법이다."""
    valid = [(metrics.mean_cost, order, name) for order, (name, metrics) in enumerate(rows)
             if metrics is not None and passes(metrics, settings)]
    return min(valid)[2] if valid else None


def holdout_result(selected, metrics, settings):
    if selected is None:
        return NO_SELECTION
    return "확인" if passes(metrics, settings) else "미달"


@dataclass(frozen=True)
class Trace:
    """시나리오의 누적 최댓값이다. 값은 양자화한 판단값이다."""

    shift: float
    onset: object
    peaks: list
    times: list
    values: frozenset

    def first_alarm(self, threshold):
        index = bisect_left(self.peaks, threshold)
        return self.times[index] if index < len(self.peaks) else None


def trace_of(scenario, scores, window):
    peaks, times = [], []
    for index, score in enumerate(scores):
        if not peaks or score > peaks[-1]:
            peaks.append(score)
            times.append(index + window - 1)
    return Trace(scenario.shift, scenario.onset, peaks, times, frozenset(scores))


def threshold_candidates(traces):
    """고유값과 무경보 후보다. 누적 최댓값이 아닌 값은 바로 위 최댓값과 지표가 같고 더 작으므로 뽑히지 않는다."""
    unique = set().union(*(trace.values for trace in traces))
    silent = max(unique) + 1
    evaluated = set().union(*(trace.peaks for trace in traces)) | {silent}
    return sorted(evaluated), len(unique) + 1


def choose_threshold(traces, settings):
    evaluated, count = threshold_candidates(traces)
    rows = []
    for threshold in evaluated:
        outcomes = [(trace.shift, trace.onset, trace.first_alarm(threshold)) for trace in traces]
        rows.append((threshold, measure_alarms(outcomes, settings.length, settings.window)))
    return select_threshold(rows, settings), count


def mean_scores(scenario):
    return [quantize(row[0]) for row in scenario.features]


def logistic_scores(scenario, model):
    return [quantize(sigmoid(model.z(row))) for row in scenario.features]


def rule_outcomes(scenarios, settings):
    """비교 대상은 명세의 3:2로 고정한다. 생성 설정이 참조하는 설비 규칙을 따르지 않는다."""
    start = settings.window - 1
    return [(scenario.shift, scenario.onset, first_rule_alarm(scenario.fails, RULE_WINDOW, RULE_FAILS, start))
            for scenario in scenarios]


def replay_range(onset, alarm, window, length):
    """재생 구간이다. 경보가 없으면 onset + 20까지다. 경보가 onset − 5보다 앞서면 경보 행 하나만 남는다."""
    if alarm is None:
        return max(window - 1, onset - 5), min(onset + 20, length - 1)
    return max(window - 1, min(onset - 5, alarm)), alarm


def replay_status(onset, alarm, threshold):
    if threshold is None:
        return NO_THRESHOLD
    if alarm is None:
        return "missed"
    return "early" if alarm < onset else "detected"


def replay_rows(scenario, model, threshold, settings):
    window = settings.window
    scores = logistic_scores(scenario, model)
    alarm = None
    if threshold is not None:
        alarm = trace_of(scenario, scores, window).first_alarm(threshold)
    start, end = replay_range(scenario.onset, alarm, window, settings.length)
    status = replay_status(scenario.onset, alarm, threshold)
    rows = []
    for t in range(start, end + 1):
        raw = scenario.features[t - window + 1]
        scaled = standardize(raw, model.means, model.scales)
        z = linear_score(scaled, model.weights, model.bias)
        row = {"seed": scenario.seed, "method": "logistic", "onset": scenario.onset, "status": status, "t": t,
               "value": scenario.values[t], "window_values": " ".join(scenario.values[t - window + 1:t + 1]),
               "ewma_prev": "%.10f" % (scenario.ewma[t - 1] if t else 0.0), "z": "%.10f" % z,
               "p": "%.10f" % sigmoid(z)}
        row.update({name: "%.10f" % value for name, value in zip(FEATURES, raw)})
        row.update({"s_" + name: "%.10f" % value for name, value in zip(FEATURES, scaled)})
        row["threshold"] = "" if threshold is None else _threshold_text(threshold)
        row["alarm"] = "" if threshold is None else int(alarm == t)
        rows.append(row)
    return rows


def _threshold_text(threshold):
    return str((Decimal(threshold) / SCALE).quantize(Decimal("0.0001")))


def show(value):
    if value is None:
        return ""
    number = Decimal(value.numerator) / Decimal(value.denominator)
    return str(number.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


def _blank(columns, section, **fields):
    row = {column: "" for column in columns}
    row["section"] = section
    row.update(fields)
    return row


def metric_row(section, method, metrics, threshold="", candidates=""):
    return _blank(METHOD_COLUMNS, section, method=method, threshold=threshold, candidates=candidates,
                  detection_rate=show(metrics.detection_rate), early=metrics.early, missed=metrics.missed,
                  mean_delay_cost=show(metrics.mean_cost), mean_detected_delay=show(metrics.mean_detected),
                  false_per_1000=show(metrics.false_per_1000))


def shift_rows(section, method, metrics):
    return [_blank(METHOD_COLUMNS, section, method=method, shift=shift, detection_rate=show(metrics.shift_rate(shift)))
            for shift in sorted(metrics.by_shift)]


def policy_row(method, metrics, threshold, settings):
    minutes = metrics.stop_minutes_per_1000 * Fraction(str(settings.repair_minutes))
    return _blank(METHOD_COLUMNS, "policy", method=method, threshold=threshold,
                  suspect_output=show(metrics.suspect_output), false_stops=show(metrics.false_per_1000),
                  stop_minutes=show(minutes))


def evaluate(scenarios, score, threshold, settings):
    traces = [trace_of(scenario, score(scenario), settings.window) for scenario in scenarios]
    outcomes = [(trace.shift, trace.onset, trace.first_alarm(threshold)) for trace in traces]
    return measure_alarms(outcomes, settings.length, settings.window)


def compare(splits, model, settings):
    """검증에서 임계값과 방법을 고르고, 홀드아웃은 확인만 한다."""
    validation, holdout = splits["validation"], splits["holdout"]
    length, window = settings.length, settings.window
    scorers = {"moving_average": mean_scores, "logistic": lambda scenario: logistic_scores(scenario, model)}
    chosen = {"rule_3_2": (None, measure_alarms(rule_outcomes(validation, settings), length, window))}
    counts = {}
    for name, score in scorers.items():
        traces = [trace_of(scenario, score(scenario), window) for scenario in validation]
        best, counts[name] = choose_threshold(traces, settings)
        chosen[name] = best
    rows = [_blank(METHOD_COLUMNS, "notice", value=NOTICE)]
    final = {"rule_3_2": measure_alarms(rule_outcomes(holdout, settings), length, window)}
    for name, score in scorers.items():
        final[name] = None if chosen[name] is None else evaluate(holdout, score, chosen[name][0], settings)
    candidates = [(name, chosen[name][1] if chosen[name] else None) for name in METHODS]
    selected = select_method(candidates, settings)
    for section, table in (("validation", dict(candidates)), ("holdout", final)):
        for name in METHODS:
            metrics = table[name]
            threshold = _threshold_text(chosen[name][0]) if name in counts and chosen[name] else ""
            if metrics is None:
                rows.append(_blank(METHOD_COLUMNS, section, method=name, candidates=counts[name],
                                   value=NO_THRESHOLD))
            else:
                rows.append(metric_row(section, name, metrics, threshold,
                                       counts.get(name, "") if section == "validation" else ""))
        for name in METHODS:
            if table[name] is not None:
                rows.extend(shift_rows(section + "_shift", name, table[name]))
    for name in METHODS:
        if final[name] is not None:
            threshold = _threshold_text(chosen[name][0]) if name in counts else ""
            rows.append(policy_row(name, final[name], threshold, settings))
    outcome = holdout_result(selected, final.get(selected), settings)
    rows.append(_blank(METHOD_COLUMNS, "selection", method=selected or "", value=selected or NO_METHOD))
    rows.append(_blank(METHOD_COLUMNS, "selection", method=selected or "", value="홀드아웃 " + outcome))
    logistic = chosen["logistic"]
    return rows, selected, outcome, logistic[0] if logistic else None, counts


def model_rows(settings, model, threshold, counts):
    rows = []
    for name, value in (("generator", settings.generator.name), ("inspection", settings.inspection),
                        ("window", settings.window), ("ewma_lambda", settings.ewma_lambda)):
        rows.append(_blank(MODEL_COLUMNS, "setting", name=name, value=value))
    for name in SPLITS:
        seeds = settings.splits[name]
        rows.append(_blank(MODEL_COLUMNS, "split", name=name, value="%d-%d" % (seeds.start, seeds.stop - 1)))
    rows.append(_blank(MODEL_COLUMNS, "windows", name="positive", value=model.positive))
    rows.append(_blank(MODEL_COLUMNS, "windows", name="negative", value=model.negative))
    for name, mean, scale, weight in zip(FEATURES, model.means, model.scales, model.weights):
        rows.append(_blank(MODEL_COLUMNS, "mean", name=name, value=repr(mean)))
        rows.append(_blank(MODEL_COLUMNS, "scale", name=name, value=repr(scale)))
        rows.append(_blank(MODEL_COLUMNS, "weight", name=name, value=repr(weight)))
    rows.append(_blank(MODEL_COLUMNS, "bias", name="bias", value=repr(model.bias)))
    rows.append(_blank(MODEL_COLUMNS, "fit", name="gradient_norm", value=repr(model.norm)))
    rows.append(_blank(MODEL_COLUMNS, "fit", name="status", value="수렴 미달" if model.norm > GRADIENT_LIMIT else "수렴"))
    rows.append(_blank(MODEL_COLUMNS, "threshold", name="logistic",
                       value="" if threshold is None else _threshold_text(threshold)))
    for name, count in counts.items():
        rows.append(_blank(MODEL_COLUMNS, "candidates", name=name, value=count))
    return rows


def _write_csv(path, columns, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def run(path):
    path = Path(path)
    settings = load_settings(path)
    process = load_process(settings)
    splits = {name: build_split(settings.splits[name], settings, process) for name in SPLITS}
    model = fit_model(splits["train"], settings)
    rows, selected, outcome, threshold, counts = compare(splits, model, settings)
    replay = replay_rows(splits["holdout"][1], model, threshold, settings)
    directory = Path("reports")
    directory.mkdir(exist_ok=True)
    stem = path.stem
    written = [directory / (stem + suffix) for suffix in ("_methods.csv", "_model.csv", "_replay.csv")]
    _write_csv(written[0], METHOD_COLUMNS, rows)
    _write_csv(written[1], MODEL_COLUMNS, model_rows(settings, model, threshold, counts))
    _write_csv(written[2], REPLAY_COLUMNS, replay)
    return rows, selected, outcome, written


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    args = parser.parse_args(argv)
    try:
        rows, selected, outcome, written = run(args.config)
    except AnomalyError as error:
        parser.exit(3, "이상 검출 입력 오류:\n" + "\n".join(error.errors) + "\n")
    except (OSError, UnicodeError, csv.Error, ValueError, KeyError) as error:
        parser.exit(2, "오류: " + str(error) + "\n")
    print(NOTICE)
    print("section | method | threshold | detection_rate | early | missed | mean_delay_cost | false_per_1000")
    for row in rows:
        if row["section"] in ("validation", "holdout"):
            print(" | ".join(str(row[column]) for column in ("section", "method", "threshold", "detection_rate", "early",
                                                             "missed", "mean_delay_cost", "false_per_1000")))
    print("선택: " + (selected or NO_METHOD) + ", 홀드아웃: " + outcome)
    print("저장 파일: " + ", ".join(item.as_posix() for item in written))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

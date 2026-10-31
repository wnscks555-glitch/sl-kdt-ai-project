"""11단계와 같은 합성 측정열에 SPC 관리도를 적용해 경보 성능을 비교한다. 실제 공정 관리 기록이 아니다."""

import argparse
import csv
from dataclasses import dataclass, replace
from decimal import Decimal
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path

from src import anomaly
from src.anomaly import _integer, _keys, _number, _write_csv, holdout_result, measure_alarms, select_method, show


NOTICE = ("합성 측정열의 SPC 관리도 비교다. 실제 공정 관리 기록이 아니고 성능은 같은 평균 이동 가정 안에서만 뜻이 있다. "
          "정상 기준에 합성 결함이 섞여 있어 한계가 그만큼 넓고, 깨끗한 기준의 한계는 참고로 따로 낸다.")
TOP_KEYS = ("anomaly", "anomaly_report", "anomaly_model", "anomaly_replay", "subgroup", "ewma_lambda", "ewma_l",
            "cusum_k", "cusum_h")
METHODS = ("xbar_r", "xbar_we", "ewma_chart", "cusum")
SUBGROUP_METHODS = ("xbar_r", "xbar_we")
SUBGROUP = 5
A2 = 0.577
D2 = 2.326
D4 = 2.114
TRIGGERS = ("limit", "range", "run_2of3", "run_4of5", "run_8")
METRIC_FIELDS = ("detection_rate", "early", "missed", "mean_delay_cost", "mean_detected_delay", "false_per_1000")
NO_METHOD = "기준 충족 관리도 없음"
METHOD_COLUMNS = ("section", "method", "shift", "split", "name", "value", "decision_interval", "max_wait",
                  "detection_rate", "early", "missed", "mean_delay_cost", "mean_detected_delay", "false_per_1000",
                  "false_per_1000_decisions", "restricted_mean_run", "no_alarm")
CHART_COLUMNS = ("seed", "shift", "onset", "t", "value", "x", "z", "ewma_limit", "c_plus", "c_minus", "xbar", "range")


class SpcError(ValueError):
    """설정 문제를 위치와 함께 모아서 보고한다. 종료 코드는 3이다."""

    def __init__(self, errors):
        super().__init__("\n".join(errors))
        self.errors = errors


@dataclass(frozen=True)
class Tuning:
    ewma_lambda: float
    ewma_l: float
    cusum_k: float
    cusum_h: float


@dataclass(frozen=True)
class Settings:
    anomaly: Path
    anomaly_report: Path
    anomaly_model: Path
    anomaly_replay: Path
    tuning: Tuning


@dataclass(frozen=True)
class Limits:
    xbarbar: float
    rbar: float
    sigma_hat: float
    ucl_x: float
    lcl_x: float
    ucl_r: float
    sigma_xbar: float
    subgroups: int


def _check(data):
    errors = []
    for key in ("anomaly", "anomaly_report", "anomaly_model", "anomaly_replay"):
        if not isinstance(data[key], str) or not data[key].strip():
            errors.append("$." + key + ": 비어 있지 않은 문자열이어야 함")
    if not _integer(data["subgroup"]) or data["subgroup"] != SUBGROUP:
        errors.append("$.subgroup: 5여야 함. 상수 표가 이 값임")
    for key in ("ewma_lambda", "ewma_l", "cusum_k", "cusum_h"):
        if not _number(data[key]) or data[key] <= 0:
            errors.append("$." + key + ": 유한한 양수여야 함")
    if _number(data["ewma_lambda"]) and data["ewma_lambda"] > 1:
        errors.append("$.ewma_lambda: 1 이하여야 함")
    return errors


def load_settings(path):
    path = Path(path)
    try:
        data = json.loads(path.read_bytes().decode("utf-8-sig"))
    except ValueError as error:
        raise SpcError(["$: JSON 오류: " + str(error)]) from error
    errors = []
    _keys(data, TOP_KEYS, "$", errors)
    if errors:
        raise SpcError(errors)
    errors = _check(data)
    if errors:
        raise SpcError(errors)
    return Settings(path.parent / data["anomaly"], path.parent / data["anomaly_report"],
                    path.parent / data["anomaly_model"], path.parent / data["anomaly_replay"],
                    Tuning(data["ewma_lambda"], data["ewma_l"], data["cusum_k"], data["cusum_h"]))


def normalized(values, process):
    """11단계의 x와 같은 식이다."""
    return [(float(value) - process.center) / process.sigma for value in values]


def subgroups_of(x):
    """앞에서부터 5건씩 끊는다. 남는 값은 버린다."""
    return [x[start:start + SUBGROUP] for start in range(0, len(x) - SUBGROUP + 1, SUBGROUP)]


def estimate(series):
    """측정열 목록에서 1단계 한계를 추정한다. 부분군이 없거나 R̄가 0이면 정의되지 않으므로 거절한다."""
    groups = [group for x in series for group in subgroups_of(x)]
    if not groups:
        raise ValueError("관리 한계 추정 불가: 부분군이 없음")
    xbarbar = sum(sum(group) / SUBGROUP for group in groups) / len(groups)
    rbar = sum(max(group) - min(group) for group in groups) / len(groups)
    if rbar == 0:
        raise ValueError("관리 한계 추정 불가: R̄가 0")
    half = A2 * rbar
    return Limits(xbarbar, rbar, rbar / D2, xbarbar + half, xbarbar - half, D4 * rbar, half / 3, len(groups))


def training_series(scenarios, process):
    """학습 분할의 정상 시나리오만 쓴다."""
    return [normalized(scenario.values, process) for scenario in scenarios if scenario.onset is None]


def _hits(points, size, need, passes):
    return len(points) >= size and sum(passes(point) for point in points[-size:]) >= need


def run_rules(points):
    """부분군 위치 열의 마지막 점에서 참인 런 규칙이다. 위아래를 따로 세고 경계값은 넣지 않는다."""
    active = []
    if _hits(points, 3, 2, lambda q: q > 2) or _hits(points, 3, 2, lambda q: q < -2):
        active.append("run_2of3")
    if _hits(points, 5, 4, lambda q: q > 1) or _hits(points, 5, 4, lambda q: q < -1):
        active.append("run_4of5")
    if _hits(points, 8, 8, lambda q: q > 0) or _hits(points, 8, 8, lambda q: q < 0):
        active.append("run_8")
    return active


def subgroup_points(x):
    """부분군 끝 위치, 평균, 범위다."""
    return [(index * SUBGROUP + SUBGROUP - 1, sum(group) / SUBGROUP, max(group) - min(group))
            for index, group in enumerate(subgroups_of(x))]


def subgroup_alarm(x, limits, start, use_runs):
    """첫 경보 위치와 그때 참인 규칙 목록이다. 런은 첫 부분군부터 세고 판단 위치에서만 인정한다."""
    points = []
    for end, mean, spread in subgroup_points(x):
        points.append((mean - limits.xbarbar) / limits.sigma_xbar)
        if end < start:
            continue
        active = []
        if mean > limits.ucl_x or mean < limits.lcl_x:
            active.append("limit")
        if spread > limits.ucl_r:
            active.append("range")
        if use_runs:
            active.extend(run_rules(points))
        if active:
            return end, active
    return None, []


class Ewma:
    """매 측정 한 번 갱신한다. 14단계는 재가동 때 새로 만들어 구간 인덱스를 다시 센다."""

    def _start_factor(self):
        """`1 − (1−λ)^{2(t+1)}`이다. 작은 λ에서 1−λ가 1로 반올림되어 한계가 0이 되지 않게 로그로 계산한다."""
        weight = self.tuning.ewma_lambda
        if weight == 1:
            return 1.0
        return -math.expm1(2 * (self.index + 1) * math.log1p(-weight))

    def __init__(self, limits, tuning):
        self.limits = limits
        self.tuning = tuning
        self.index = -1
        self.value = limits.xbarbar
        self.limit = 0.0

    def update(self, x):
        weight = self.tuning.ewma_lambda
        self.index += 1
        self.value = weight * x + (1 - weight) * self.value
        variance = weight / (2 - weight) * self._start_factor()
        self.limit = self.tuning.ewma_l * self.limits.sigma_hat * math.sqrt(variance)
        return abs(self.value - self.limits.xbarbar) > self.limit


class Cusum:
    """매 측정 한 번 갱신한다. 위아래 누적합 기록으로 변화 시점을 추정한다."""

    def __init__(self, limits, tuning):
        self.limits = limits
        self.allowance = tuning.cusum_k * limits.sigma_hat
        self.bound = tuning.cusum_h * limits.sigma_hat
        self.plus = []
        self.minus = []

    def update(self, x):
        step = x - self.limits.xbarbar
        self.plus.append(max(0.0, (self.plus[-1] if self.plus else 0.0) + step - self.allowance))
        self.minus.append(max(0.0, (self.minus[-1] if self.minus else 0.0) - step - self.allowance))
        return self.plus[-1] > self.bound or self.minus[-1] > self.bound

    def change_point(self):
        """마지막 측정에서 경보한 쪽이 마지막으로 0이었던 다음 위치다. 양쪽이 함께면 위쪽을 쓴다."""
        series = self.plus if self.plus[-1] > self.bound else self.minus
        for index in range(len(series) - 2, -1, -1):
            if series[index] == 0:
                return index + 1
        return 0


def first_alarm(chart, x, start):
    """판단 시작 전 초과는 무시하고 그 뒤 첫 초과 위치를 돌려준다."""
    for t, value in enumerate(x):
        if chart.update(value) and t >= start:
            return t
    return None


def alarm_of(method, x, limits, tuning, start):
    if method == "xbar_r":
        return subgroup_alarm(x, limits, start, False)[0]
    if method == "xbar_we":
        return subgroup_alarm(x, limits, start, True)[0]
    return first_alarm((Ewma if method == "ewma_chart" else Cusum)(limits, tuning), x, start)


def outcomes_of(method, scenarios, limits, tuning, process, start):
    return [(scenario.shift, scenario.onset, alarm_of(method, normalized(scenario.values, process), limits, tuning,
                                                      start)) for scenario in scenarios]


def decision_count(method, first, last):
    """구간 안의 판단 횟수다. 부분군 방법은 부분군 끝에서만 판단한다."""
    if last < first:
        return 0
    if method in SUBGROUP_METHODS:
        return (last + 1) // SUBGROUP - first // SUBGROUP
    return last - first + 1


def exposure_end(onset, alarm, length):
    """anomaly.add_outcome의 노출 구간 끝이다."""
    if onset is None:
        return length - 1 if alarm is None else alarm
    if alarm is not None and alarm < onset:
        return alarm
    return onset - 1


def false_per_1000_decisions(method, outcomes, length, first):
    alarms = sum(1 for _, onset, alarm in outcomes if alarm is not None and (onset is None or alarm < onset))
    decisions = sum(decision_count(method, first, exposure_end(onset, alarm, length)) for _, onset, alarm in outcomes)
    return Fraction(alarms * 1000, decisions) if decisions else None


def restricted_run(outcomes, length, first):
    """정상 시나리오의 첫 경보까지 측정 수 평균이다. 무경보는 관측 끝에서 자른다. 일반적인 ARL이 아니다."""
    runs = [(length - first if alarm is None else alarm - first + 1) for _, onset, alarm in outcomes if onset is None]
    silent = sum(1 for _, onset, alarm in outcomes if onset is None and alarm is None)
    return (Fraction(sum(runs), len(runs)) if runs else None), silent


def count_triggers(records):
    """시나리오별 첫 경보 규칙 목록을 받는다. 앞선 규칙 하나에 세고 동시 참은 joint로 따로 센다."""
    counts = {name: 0 for name in TRIGGERS}
    counts["joint"] = 0
    for active in records:
        if active:
            counts[min(active, key=TRIGGERS.index)] += 1
            counts["joint"] += len(active) > 1
    return counts


def _row(section, **fields):
    row = {column: "" for column in METHOD_COLUMNS}
    row["section"] = section
    row.update(fields)
    return row


def metric_fields(method, metrics, outcomes, length, first):
    run_length, silent = restricted_run(outcomes, length, first)
    subgroup = method in SUBGROUP_METHODS
    return {"decision_interval": SUBGROUP if subgroup else 1, "max_wait": SUBGROUP - 1 if subgroup else 0,
            "detection_rate": show(metrics.detection_rate), "early": metrics.early, "missed": metrics.missed,
            "mean_delay_cost": show(metrics.mean_cost), "mean_detected_delay": show(metrics.mean_detected),
            "false_per_1000": show(metrics.false_per_1000),
            "false_per_1000_decisions": show(false_per_1000_decisions(method, outcomes, length, first)),
            "restricted_mean_run": show(run_length), "no_alarm": silent}


def limit_rows(section, limits, extra=()):
    names = ("xbarbar", "rbar", "sigma_hat", "ucl_x", "lcl_x", "ucl_r", "sigma_xbar", "subgroups")
    rows = [_row(section, name=name, value=repr(value)) for name, value in extra]
    return rows + [_row(section, name=name, value=repr(getattr(limits, name))) for name in names]


def tuning_rows(tuning, window):
    return [_row("limits", name=name, value=repr(value))
            for name, value in (("ewma_lambda", tuning.ewma_lambda), ("ewma_l", tuning.ewma_l),
                                ("cusum_k", tuning.cusum_k), ("cusum_h", tuning.cusum_h), ("window", window))]


def _read_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def _unique(rows, key):
    """같은 키가 두 번이면 어느 행을 믿을지 정할 수 없으므로 거절한다."""
    table = {}
    for row in rows:
        name = key(row)
        if name in table:
            raise ValueError("보고서에 같은 행이 두 번 있음: %s" % (name,))
        table[name] = row
    return table


def load_reference(path):
    rows = [row for row in _read_rows(path)
            if row["section"] in ("validation", "holdout", "validation_shift", "holdout_shift")]
    table = _unique(rows, lambda row: (row["section"], row["method"], row["shift"]))
    for section in ("validation", "holdout"):
        for method in anomaly.METHODS:
            if (section, method, "") not in table:
                raise ValueError("anomaly_report: %s %s 행이 없음" % (section, method))
    return table


def check_model(path, settings):
    """현재 11단계 설정과 모델 보고서의 설정·분할 행이 같아야 한다."""
    kept = [row for row in _read_rows(path) if row["section"] in ("setting", "split")]
    rows = {key: row["value"] for key, row in _unique(kept, lambda row: (row["section"], row["name"])).items()}
    expected = {("setting", "generator"): settings.generator.name, ("setting", "inspection"): settings.inspection,
                ("setting", "window"): str(settings.window), ("setting", "ewma_lambda"): str(settings.ewma_lambda)}
    for name in anomaly.SPLITS:
        seeds = settings.splits[name]
        expected[("split", name)] = "%d-%d" % (seeds.start, seeds.stop - 1)
    for key, value in expected.items():
        if rows.get(key) != value:
            raise ValueError("anomaly_model: 현재 설정과 다름 %s" % (key,))


def check_rule(table, section, scenarios, settings):
    """rule_3_2는 측정열에만 의존하므로 다시 계산해 같은 측정열인지 확인한다."""
    metrics = measure_alarms(anomaly.rule_outcomes(scenarios, settings), settings.length, settings.window)
    row = anomaly.metric_row(section, "rule_3_2", metrics)
    if any(str(row[name]) != table[(section, "rule_3_2", "")][name] for name in METRIC_FIELDS):
        raise ValueError("anomaly_report: %s의 rule_3_2가 현재 측정열과 다름" % section)
    for shifted in anomaly.shift_rows(section + "_shift", "rule_3_2", metrics):
        reported = table.get((section + "_shift", "rule_3_2", str(shifted["shift"])))
        if reported is None or reported["detection_rate"] != shifted["detection_rate"]:
            raise ValueError("anomaly_report: %s의 이동량별 rule_3_2가 현재 측정열과 다름" % section)


def check_values(table, section, scenarios, settings):
    """이동평균은 측정값 전체의 합에 의존한다. 보고서 임계값으로 다시 계산해 측정열을 확인한다."""
    row = table[(section, "moving_average", "")]
    if not row["threshold"]:
        return
    threshold = int(Decimal(row["threshold"]) * anomaly.SCALE)
    metrics = anomaly.evaluate(scenarios, anomaly.mean_scores, threshold, settings)
    fresh = anomaly.metric_row(section, "moving_average", metrics)
    if any(str(fresh[name]) != row[name] for name in METRIC_FIELDS):
        raise ValueError("anomaly_report: %s의 moving_average가 현재 측정열과 다름" % section)


def check_replay(path, scenario):
    """재생 보고서의 원 측정값은 측정열 자체다. 집계가 우연히 같아도 값이 다르면 여기서 걸린다."""
    rows = _read_rows(path)
    if not rows:
        raise ValueError("anomaly_replay: 행이 없음")
    for row in rows:
        t = int(row["t"])
        if int(row["seed"]) != scenario.seed or row["value"] != scenario.values[t]:
            raise ValueError("anomaly_replay: 현재 측정열과 다름")
        window = row["window_values"].split(" ")
        if window != scenario.values[t - len(window) + 1:t + 1]:
            raise ValueError("anomaly_replay: 현재 측정열과 다름")


def reference_rows(table):
    rows = []
    for section in ("validation", "holdout"):
        for method in anomaly.METHODS:
            source = table[(section, method, "")]
            rows.append(_row("reference", method=method, split=section,
                             **{name: source[name] for name in METRIC_FIELDS}))
    return rows


def provenance_rows(paths):
    return [_row("provenance", name=path.name, value=hashlib.sha256(path.read_bytes()).hexdigest()) for path in paths]


def evaluate_split(section, scenarios, limits, tuning, process, settings):
    """방법별 지표와 행이다."""
    first = settings.window - 1
    rows, table = [], {}
    for method in METHODS:
        outcomes = outcomes_of(method, scenarios, limits, tuning, process, first)
        metrics = measure_alarms(outcomes, settings.length, settings.window)
        table[method] = metrics
        rows.append(_row(section, method=method, **metric_fields(method, metrics, outcomes, settings.length, first)))
    return rows, table


def shift_section(section, table):
    return [_row(section + "_shift", method=method, shift=shift, detection_rate=show(table[method].shift_rate(shift)))
            for method in METHODS for shift in sorted(table[method].by_shift)]


def trigger_rows(split, scenarios, limits, process, settings):
    start = settings.window - 1
    records = [subgroup_alarm(normalized(scenario.values, process), limits, start, True)[1] for scenario in scenarios]
    return [_row("triggers", method="xbar_we", split=split, name=name, value=value)
            for name, value in count_triggers(records).items()]


def chart_rows(scenario, limits, tuning, process):
    x = normalized(scenario.values, process)
    ewma, cusum = Ewma(limits, tuning), Cusum(limits, tuning)
    ends = {end: (mean, spread) for end, mean, spread in subgroup_points(x)}
    rows = []
    for t, value in enumerate(x):
        ewma.update(value)
        cusum.update(value)
        mean, spread = ends.get(t, (None, None))
        rows.append({"seed": scenario.seed, "shift": scenario.shift, "onset": scenario.onset, "t": t,
                     "value": scenario.values[t], "x": "%.10f" % value, "z": "%.10f" % ewma.value,
                     "ewma_limit": "%.10f" % ewma.limit, "c_plus": "%.10f" % cusum.plus[-1],
                     "c_minus": "%.10f" % cusum.minus[-1], "xbar": "" if mean is None else "%.10f" % mean,
                     "range": "" if spread is None else "%.10f" % spread})
    return rows


def clean_limits(settings, process):
    """같은 학습 시드의 정상 시나리오를 결함 없이 다시 만들어 추정한다. 참고값이다."""
    clean = replace(process, defect_probability=0.0)
    seeds = [seed for index, seed in enumerate(settings.splits["train"])
             if anomaly.assignment(index, settings.shifts) == 0]
    return estimate([normalized(anomaly.build_scenario(seed, 0, settings, clean).values, clean) for seed in seeds])


def compare(splits, limits, clean, tuning, process, settings, table):
    rows, metrics = {}, {}
    for section in ("validation", "holdout"):
        rows[section], metrics[section] = evaluate_split(section, splits[section], limits, tuning, process, settings)
    selected = select_method([(method, metrics["validation"][method]) for method in METHODS], settings)
    outcome = holdout_result(selected, metrics["holdout"].get(selected), settings)
    result = (rows["validation"] + shift_section("validation", metrics["validation"])
              + rows["holdout"] + shift_section("holdout", metrics["holdout"]) + reference_rows(table))
    result.extend(limit_rows("clean_limits", clean))
    result.extend(evaluate_split("clean_holdout", splits["holdout"], clean, tuning, process, settings)[0])
    for section in ("validation", "holdout"):
        result.extend(trigger_rows(section, splits[section], limits, process, settings))
    result.append(_row("selection", method=selected or "", value=selected or NO_METHOD))
    result.append(_row("selection", method=selected or "", value="홀드아웃 " + outcome))
    return result, selected, outcome


def load_limits(path):
    """14단계가 읽는 한계와 정규화 기준이다. 행이 없으면 ValueError다."""
    rows = {row["name"]: row["value"] for row in _read_rows(path) if row["section"] == "limits"}
    if not rows:
        raise ValueError("limits 행이 없음")
    return rows


def run(path):
    path = Path(path)
    settings = load_settings(path)
    base = anomaly.load_settings(settings.anomaly)
    process = anomaly.load_process(base)
    table = load_reference(settings.anomaly_report)
    check_model(settings.anomaly_model, base)
    splits = {name: anomaly.build_split(base.splits[name], base, process) for name in anomaly.SPLITS}
    for section in ("validation", "holdout"):
        check_rule(table, section, splits[section], base)
        check_values(table, section, splits[section], base)
    check_replay(settings.anomaly_replay, splits["holdout"][1])
    limits = estimate(training_series(splits["train"], process))
    clean = clean_limits(base, process)
    body, selected, outcome = compare(splits, limits, clean, settings.tuning, process, base, table)
    rows = [_row("notice", value=NOTICE)]
    rows.extend(provenance_rows((path, settings.anomaly, settings.anomaly_report, settings.anomaly_model,
                                 settings.anomaly_replay)))
    rows.extend(limit_rows("limits", limits, (("center", process.center), ("sigma", process.sigma))))
    rows.extend(tuning_rows(settings.tuning, base.window))
    rows.extend(body)
    chart = chart_rows(splits["holdout"][1], limits, settings.tuning, process)
    directory = Path("reports")
    directory.mkdir(exist_ok=True)
    written = [directory / (path.stem + "_methods.csv"), directory / (path.stem + "_chart.csv")]
    _write_csv(written[0], METHOD_COLUMNS, rows)
    _write_csv(written[1], CHART_COLUMNS, chart)
    return rows, selected, outcome, written


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    args = parser.parse_args(argv)
    try:
        rows, selected, outcome, written = run(args.config)
    except (SpcError, anomaly.AnomalyError) as error:
        parser.exit(3, "관리도 입력 오류:\n" + "\n".join(error.errors) + "\n")
    except (OSError, UnicodeError, csv.Error, ValueError, KeyError) as error:
        parser.exit(2, "오류: " + str(error) + "\n")
    print(NOTICE)
    print("section | method | detection_rate | early | missed | mean_delay_cost | false_per_1000")
    for row in rows:
        if row["section"] in ("validation", "holdout"):
            print(" | ".join(str(row[column]) for column in ("section", "method", "detection_rate", "early", "missed",
                                                             "mean_delay_cost", "false_per_1000")))
    print("선택: " + (selected or NO_METHOD) + ", 홀드아웃: " + outcome)
    print("저장 파일: " + ", ".join(item.as_posix() for item in written))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

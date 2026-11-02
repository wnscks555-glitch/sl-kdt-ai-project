"""공개 실측 자료(UCI SECOM)로 1–16단계의 합성 가정을 점검한다. 검출률을 내지 않는다."""

import argparse
import csv
from dataclasses import dataclass, replace
from datetime import datetime
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import random
import re
from statistics import median

from . import anomaly
from .line import show
from .sizing import check_outputs, setup_inputs
from .spc import Ewma


NOTICE = ("공개 반도체 공정 실측 자료(UCI SECOM)로 합성 가정을 점검한 연습이다. 자동차·조립·램프 자료가 아니다. "
          "합격은 공정이 관리 상태라는 정답이 아니므로, 비율은 합격 행에 조건부인 한계 초과 비율이고 오경보율이나 검출률이 아니다.")
SOURCE = ("McCann, M. & Johnston, A. (2008). SECOM [Dataset]. UCI Machine Learning Repository. "
          "https://doi.org/10.24432/C54305. 라이선스 CC BY 4.0.")
EXPECTED_I_RATE = Fraction(27, 10000)
MIN_PHASE1 = 30
SYNTHETIC_RUNS = 30
D2 = 1.128
NUMBERS = ("max_missing", "phase1_share", "ewma_lambda", "ewma_l", "skew_limit", "kurtosis_limit", "autocorr_limit",
           "rate_limit")
KEYS = {"data", "labels", "data_sha256", "labels_sha256", "anomaly"} | set(NUMBERS)
LABEL = re.compile(r'(-1|1) "(\d\d/\d\d/\d{4} \d\d:\d\d:\d\d)"\Z')
HEX = re.compile(r"[0-9a-f]{64}\Z")
FEATURE_COLUMNS = ("feature", "selected", "reason", "missing", "missing1", "missing2", "n1", "n2", "mean", "sd",
                   "sigma_mr", "skew", "kurtosis", "r1", "out3s", "i_rate", "ewma_rate")
SUMMARY_COLUMNS = ("section", "name", "value", "text")


class SecomError(ValueError):
    """설정이 잘못되었다. 종료 코드는 3이다."""

    def __init__(self, errors):
        super().__init__("; ".join(errors))
        self.errors = errors


@dataclass(frozen=True)
class Settings:
    data: Path
    labels: Path
    data_sha256: str
    labels_sha256: str
    anomaly: Path
    max_missing: Fraction
    phase1_share: Fraction
    ewma_lambda: float
    ewma_l: float
    skew_limit: float
    kurtosis_limit: float
    autocorr_limit: float
    rate_limit: Fraction


@dataclass(frozen=True)
class Chart:
    """13단계 Ewma가 읽는 값만 둔다."""
    xbarbar: float
    sigma_hat: float


@dataclass(frozen=True)
class Tuning:
    ewma_lambda: float
    ewma_l: float


def _reject_constant(name):
    raise SecomError(["JSON에 허용되지 않는 값: " + name])


def _number(value):
    if type(value) is bool or not isinstance(value, (int, float, str)):
        raise ValueError
    number = Fraction(value)
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError
    return number


def load_settings(path):
    path = Path(path)
    try:
        with path.open(encoding="utf-8-sig") as source:
            data = json.load(source, parse_constant=_reject_constant)
    except (json.JSONDecodeError, UnicodeError) as error:
        raise SecomError(["$: JSON을 읽을 수 없음: " + str(error)]) from error
    if not isinstance(data, dict):
        raise SecomError(["$: 객체여야 함"])
    errors = ["$: 필요한 키 없음 " + key for key in sorted(KEYS - set(data))]
    errors += ["$: 허용 밖 키 " + key for key in sorted(set(data) - KEYS)]
    for key in ("data", "labels", "anomaly"):
        if key in data and not (isinstance(data[key], str) and data[key]):
            errors.append("$.%s: 경로 문자열이어야 함" % key)
    for key in ("data_sha256", "labels_sha256"):
        if key in data and not (isinstance(data[key], str) and HEX.match(data[key])):
            errors.append("$.%s: SHA-256 소문자 16진수 64자여야 함" % key)
    numbers = {}
    for key in NUMBERS:
        if key not in data:
            continue
        try:
            numbers[key] = _number(data[key])
        except (ValueError, ZeroDivisionError):
            errors.append("$.%s: 유한한 수여야 함" % key)
    bounds = {"max_missing": (0, 1, True), "phase1_share": (0, 1, False), "ewma_lambda": (0, 1, False),
              "ewma_l": (0, None, False), "skew_limit": (0, None, False), "kurtosis_limit": (0, None, False),
              "autocorr_limit": (0, 1, False), "rate_limit": (0, 1, False)}
    for key, (low, high, closed) in bounds.items():
        if key in numbers:
            value = numbers[key]
            if not (value >= low if closed else value > low) or (high is not None and value >= high
                                                                  and not (closed or key == "ewma_lambda")):
                errors.append("$.%s: 범위 밖" % key)
            elif key == "ewma_lambda" and value > 1:
                errors.append("$.%s: 범위 밖" % key)
    if errors:
        raise SecomError(errors)
    base = path.parent
    return Settings(base / data["data"], base / data["labels"], data["data_sha256"], data["labels_sha256"],
                    base / data["anomaly"], numbers["max_missing"], numbers["phase1_share"],
                    float(numbers["ewma_lambda"]), float(numbers["ewma_l"]), float(numbers["skew_limit"]),
                    float(numbers["kurtosis_limit"]), float(numbers["autocorr_limit"]), numbers["rate_limit"])


def checked_bytes(path, digest):
    data = Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError("해시가 설정과 다름: " + Path(path).name)
    return data.decode("utf-8")


def parse_value(text):
    if text == "NaN":
        return None
    value = float(text)
    if not math.isfinite(value):
        raise ValueError("유한하지 않은 값: " + text)
    return value


def read_rows(data_text, label_text):
    """행마다 (시각, 원래 순서, 합격 여부, 값 목록)이다."""
    data_lines = [line for line in data_text.splitlines() if line.strip()]
    label_lines = [line.strip() for line in label_text.splitlines() if line.strip()]
    if len(data_lines) != len(label_lines) or not data_lines:
        raise ValueError("자료와 라벨의 행 수가 다름")
    rows, width = [], None
    for index, (values, label) in enumerate(zip(data_lines, label_lines)):
        match = LABEL.match(label)
        if match is None:
            raise ValueError("라벨 형식이 다름: %d행" % (index + 1))
        stamp = datetime.strptime(match.group(2), "%d/%m/%Y %H:%M:%S")
        try:
            parsed = [parse_value(item) for item in values.split()]
        except ValueError as error:
            raise ValueError("값이 숫자나 NaN이 아님: %d행" % (index + 1)) from error
        if width is None:
            width = len(parsed)
        if len(parsed) != width or not width:
            raise ValueError("열 수가 다름: %d행" % (index + 1))
        rows.append((stamp, index, match.group(1) == "-1", parsed))
    return sorted(rows, key=lambda row: (row[0], row[1]))


def split_point(count, share):
    return math.floor(count * share)


def moments(values):
    """모멘트 왜도 g1 = m3/m2^1.5, 초과 첨도 g2 = m4/m2² − 3이다. m2가 0이면 None이다."""
    count = len(values)
    center = sum(values) / count
    m2 = sum((value - center) ** 2 for value in values) / count
    if m2 == 0:
        return None, None
    m3 = sum((value - center) ** 3 for value in values) / count
    m4 = sum((value - center) ** 4 for value in values) / count
    return m3 / m2 ** 1.5, m4 / m2 ** 2 - 3


def lag1(values):
    center = sum(values) / len(values)
    denominator = sum((value - center) ** 2 for value in values)
    if denominator == 0:
        return None
    return sum((values[t] - center) * (values[t + 1] - center) for t in range(len(values) - 1)) / denominator


def moving_range(values):
    """결측을 이미 건너뛴 연속 값의 이동범위 평균이다."""
    ranges = [abs(values[t + 1] - values[t]) for t in range(len(values) - 1)]
    return sum(ranges) / len(ranges) if ranges else 0.0


def sample_sd(values):
    center = sum(values) / len(values)
    return math.sqrt(sum((value - center) ** 2 for value in values) / (len(values) - 1))


def chart_rates(phase1, phase2, settings):
    """1단계 합격 값으로 한계를 정하고 2단계 합격 값의 한계 밖 비율과 EWMA 경보 비율을 낸다."""
    center = sum(phase1) / len(phase1)
    sigma = moving_range(phase1) / D2
    outside = sum(abs(value - center) > 3 * sigma for value in phase2)
    ewma = Ewma(Chart(center, sigma), Tuning(settings.ewma_lambda, settings.ewma_l))
    alarms = sum(ewma.update(value) for value in phase2)
    if not phase2:
        return sigma, None, None
    return sigma, Fraction(outside, len(phase2)), Fraction(alarms, len(phase2))


def feature_rows(rows, settings):
    n1 = split_point(len(rows), settings.phase1_share)
    result = []
    for feature in range(len(rows[0][3])):
        column = [row[3][feature] for row in rows]
        missing = Fraction(sum(value is None for value in column), len(column))
        phase1 = [row[3][feature] for row in rows[:n1] if row[2] and row[3][feature] is not None]
        phase2 = [row[3][feature] for row in rows[n1:] if row[2] and row[3][feature] is not None]
        first = column[:n1]
        missing1 = Fraction(sum(value is None for value in first), len(first)) if first else Fraction(1)
        later = column[n1:]
        missing2 = Fraction(sum(value is None for value in later), len(later)) if later else Fraction(0)
        record = {"feature": feature, "missing": show(missing), "missing1": show(missing1), "missing2": show(missing2),
                  "n1": len(phase1), "n2": len(phase2)}
        reason = ""
        if missing1 > settings.max_missing:
            reason = "1단계 결측 초과"
        elif len(phase1) < MIN_PHASE1:
            reason = "1단계 값 부족"
        elif len(set(phase1)) == 1:
            reason = "상수"
        elif moving_range(phase1) == 0:
            reason = "MR 0"
        elif not phase2:
            reason = "2단계 값 없음"
        if reason:
            result.append(dict(record, selected=0, reason=reason))
            continue
        skew, kurtosis = moments(phase1)
        center, sd = sum(phase1) / len(phase1), sample_sd(phase1)
        sigma, i_rate, ewma_rate = chart_rates(phase1, phase2, settings)
        r1 = lag1(phase1)
        result.append(dict(record, selected=1, reason="", mean=repr(center), sd=repr(sd), sigma_mr=repr(sigma),
                           skew=_float(skew), kurtosis=_float(kurtosis), r1=_float(r1),
                           out3s=show(Fraction(sum(abs(value - center) > 3 * sd for value in phase1), len(phase1))),
                           i_rate=show(i_rate), ewma_rate=show(ewma_rate),
                           _skew=skew, _kurtosis=kurtosis, _r1=r1, _i=i_rate, _e=ewma_rate))
    return n1, result


def _float(value):
    return "" if value is None else "%.4f" % value


def share(count, total):
    return show(Fraction(count, total)) if total else ""


def quantile(values, fraction):
    """하위 `fraction` 위치의 값이다. 정렬 뒤 ⌈n·p⌉번째를 쓴다."""
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)]


def synthetic_rates(settings, n1, n2):
    """같은 절차를 두 합성열에 적용한다. 시드마다 1단계 n1점, 2단계 n2점이고 시드별 비율의 중앙값을 낸다.

    `pure`는 순수 정규·독립열이다. `mixed`는 11단계 생성기의 고장 이동 없는 열이며 2% 결함 혼합이 들어 있다.
    """
    base = anomaly.load_settings(settings.anomaly)
    process = anomaly.load_process(base)
    seeds = list(base.splits["validation"])[:SYNTHETIC_RUNS]
    sized = replace(base, length=max(n1 + n2, base.window))
    rates = {"pure": ([], []), "mixed": ([], [])}
    for seed in seeds:
        rng = random.Random(seed)
        pure = [rng.gauss(process.center, process.sigma) for _ in range(n1 + n2)]
        mixed = [float(value) for value in anomaly.build_scenario(seed, 0, sized, process).values]
        for name, values in (("pure", pure), ("mixed", mixed)):
            _, i_rate, ewma_rate = chart_rates(values[:n1], values[n1:n1 + n2], settings)
            rates[name][0].append(i_rate)
            rates[name][1].append(ewma_rate)
    return seeds, {name: (median(pair[0]), median(pair[1])) for name, pair in rates.items()}


def summary_rows(rows, n1, features, settings):
    out = [{"section": "notice", "text": NOTICE}, {"section": "notice", "text": SOURCE}]
    fails = [not row[2] for row in rows]
    out.append({"section": "data", "name": "rows", "value": len(rows)})
    out.append({"section": "data", "name": "features", "value": len(features)})
    out.append({"section": "data", "name": "phase1_rows", "value": n1})
    out.append({"section": "data", "name": "phase2_rows", "value": len(rows) - n1})
    for name, part in (("fail_rate", fails), ("fail_rate_phase1", fails[:n1]), ("fail_rate_phase2", fails[n1:])):
        out.append({"section": "data", "name": name, "value": share(sum(part), len(part)),
                    "text": "%d/%d" % (sum(part), len(part))})
    out.append({"section": "data", "name": "data_sha256", "value": settings.data_sha256})
    out.append({"section": "data", "name": "labels_sha256", "value": settings.labels_sha256})
    reasons = {}
    for row in features:
        if not row["selected"]:
            reasons[row["reason"]] = reasons.get(row["reason"], 0) + 1
    for reason in sorted(reasons):
        out.append({"section": "excluded", "name": reason, "value": reasons[reason]})
    chosen = [row for row in features if row["selected"]]
    total = len(chosen)
    out.append({"section": "summary", "name": "selected", "value": total})
    if total:
        checks = (("skew_over", lambda row: row["_skew"] is not None and abs(row["_skew"]) > settings.skew_limit),
                  ("kurtosis_over", lambda row: row["_kurtosis"] is not None
                   and abs(row["_kurtosis"]) > settings.kurtosis_limit),
                  ("autocorr_over", lambda row: row["_r1"] is not None and abs(row["_r1"]) > settings.autocorr_limit),
                  ("i_rate_over", lambda row: row["_i"] > settings.rate_limit))
        for name, test in checks:
            count = sum(1 for row in chosen if test(row))
            out.append({"section": "summary", "name": name, "value": share(count, total),
                        "text": "%d/%d" % (count, total)})
        i_rates = [row["_i"] for row in chosen]
        e_rates = [row["_e"] for row in chosen]
        out.append({"section": "summary", "name": "i_rate_median", "value": show(median(i_rates))})
        out.append({"section": "summary", "name": "i_rate_p90", "value": show(quantile(i_rates, Fraction(9, 10)))})
        out.append({"section": "summary", "name": "i_rate_expected", "value": show(EXPECTED_I_RATE),
                    "text": "모수를 아는 이상적 정규·독립 조건의 ±3σ 밖 비율. 추정 한계의 기대값이 아니라 참고값"})
        out.append({"section": "summary", "name": "ewma_rate_median", "value": show(median(e_rates))})
    if not total:
        out.append({"section": "synthetic", "name": "skipped",
                    "text": "분석한 특징이 없어 같은 길이의 합성 비교를 계산하지 않음"})
        return out
    n1_size = int(median(row["n1"] for row in chosen))
    n2_size = int(median(row["n2"] for row in chosen))
    seeds, rates = synthetic_rates(settings, n1_size, n2_size)
    label = {"pure": "순수 정규·독립열", "mixed": "11단계 생성기 고장 이동 없는 열(2% 결함 혼합)"}
    for name in ("pure", "mixed"):
        text = "%s, 시드 %d–%d의 %d회 중앙값, 1단계 %d·2단계 %d점(선택 특징의 n 중앙값)" % (
            label[name], seeds[0], seeds[-1], len(seeds), n1_size, n2_size)
        out.append({"section": "synthetic_" + name, "name": "i_rate", "value": show(rates[name][0]), "text": text})
        out.append({"section": "synthetic_" + name, "name": "ewma_rate", "value": show(rates[name][1]), "text": text})
    return out


def report_text(summary):
    values = {(row["section"], row.get("name", "")): row for row in summary}

    def value(section, name):
        row = values.get((section, name))
        return "" if row is None else str(row.get("value", ""))

    def count(section, name):
        row = values.get((section, name))
        return "" if row is None else row.get("text", "")

    lines = ["# 공개 실측 자료로 합성 가정 점검 (UCI SECOM)", "", NOTICE, "", "출처: " + SOURCE, "",
             "원자료는 저장소에 넣지 않는다. 받은 파일의 SHA-256을 설정에 고정했다.", "",
             "## 자료", "",
             "| 항목 | 값 |", "| --- | --- |",
             "| 행 | %s |" % value("data", "rows"), "| 특징 | %s |" % value("data", "features"),
             "| 1단계 행(시간순 앞) | %s |" % value("data", "phase1_rows"),
             "| 2단계 행 | %s |" % value("data", "phase2_rows"),
             "| 불합격률 전체 | %s (%s) |" % (value("data", "fail_rate"), count("data", "fail_rate")),
             "| 불합격률 1단계 | %s (%s) |" % (value("data", "fail_rate_phase1"), count("data", "fail_rate_phase1")),
             "| 불합격률 2단계 | %s (%s) |" % (value("data", "fail_rate_phase2"), count("data", "fail_rate_phase2")),
             "| 분석한 특징 | %s |" % value("summary", "selected"), "",
             "## 가정 점검 (1단계 합격 값)", "",
             "기준(왜도 1, 초과 첨도 3, 자기상관 0.2, 한계 초과 0.01)은 결과 전에 고정한 표시 기준이다. 정규성이나 독립성을 "
             "검정하거나 기각하는 값이 아니다. 특징별 원래 통계량은 `secom_check_features.csv`에 있다. 자기상관은 결측과 "
             "불합격 행을 뺀 뒤 남은 관측 순번 기준이고, 시각은 등간격이 아니다.", "",
             "| 점검 | 특징 비율 |", "| --- | --- |",
             "| 왜도 절댓값이 기준 초과 | %s (%s) |" % (value("summary", "skew_over"), count("summary", "skew_over")),
             "| 초과 첨도 절댓값이 기준 초과 | %s (%s) |" % (value("summary", "kurtosis_over"),
                                                  count("summary", "kurtosis_over")),
             "| lag-1 자기상관 절댓값이 기준 초과 | %s (%s) |" % (value("summary", "autocorr_over"),
                                                      count("summary", "autocorr_over")), "",
             "## 같은 관리도를 적용했을 때 (2단계 합격 값)", "",
             "1단계 합격 값으로 중심과 σ̂ = MR̄/1.128을 정하고 2단계 합격 값에 적용했다. EWMA는 2단계 첫 값에서 z₀ = 중심, "
             "t = 1로 시작하고 결측·불합격 행에서는 갱신하지 않는다. 합성 열은 같은 길이로 30개 시드를 돌린 중앙값이다.", "",
             "| 항목 | SECOM 특징 중앙값 | 순수 정규·독립열 | 생성기 열(2% 결함 혼합) | 이상적 참고값 |",
             "| --- | --- | --- | --- | --- |",
             "| 개별값 관리도 한계 초과 비율 | %s | %s | %s | %s |" % (value("summary", "i_rate_median"),
                                                          value("synthetic_pure", "i_rate"),
                                                          value("synthetic_mixed", "i_rate"),
                                                          value("summary", "i_rate_expected")),
             "| EWMA 경보 비율 | %s | %s | %s | |" % (value("summary", "ewma_rate_median"),
                                                 value("synthetic_pure", "ewma_rate"),
                                                 value("synthetic_mixed", "ewma_rate")), "",
             "| SECOM 분포 | 값 |", "| --- | --- |",
             "| 한계 초과 비율 상위 10%% 경계(⌈0.9n⌉번째) | %s |" % value("summary", "i_rate_p90"),
             "| 한계 초과 비율이 표시 기준 초과인 특징 | %s (%s) |" % (value("summary", "i_rate_over"),
                                                         count("summary", "i_rate_over")), "",
             "## 해석 한계", "",
             "- 반도체 공정 자료다. 자동차 부품, 조립, 램프 공정의 성능으로 옮길 수 없다.",
             "- 특징 이름과 규격이 없어 Cpk, Gage R&R, 규격 판정을 하지 않는다.",
             "- 합격은 관리 상태의 정답이 아니다. 비율은 합격 행에 조건부인 한계 초과 비율이고 오경보율이나 검출률이 아니다.",
             "- 합격 행만 쓰면 품질 결과에 조건을 건 분포가 되어 전체 공정 분포와 다르다.",
             "- 1단계 합격 자료에도 이상이 섞였을 수 있다. 그러면 한계가 넓어지거나 2단계 비율이 달라진다.",
             "- 임계값, 분할 비율, 선택 규칙은 SECOM 통계를 계산하기 전에 명세로 고정했다. 특징 선택에는 1단계 결측률만 쓴다."]
    return "\n".join(lines) + "\n"


def _write_csv(path, columns, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def run(path):
    path = Path(path)
    settings = load_settings(path)
    outputs = [Path("reports") / (path.stem + suffix) for suffix in ("_features.csv", "_summary.csv", ".md")]
    base = anomaly.load_settings(settings.anomaly)
    check_outputs(outputs, [path, settings.data, settings.labels, settings.anomaly] + setup_inputs(base.generator))
    rows = read_rows(checked_bytes(settings.data, settings.data_sha256),
                     checked_bytes(settings.labels, settings.labels_sha256))
    n1, features = feature_rows(rows, settings)
    summary = summary_rows(rows, n1, features, settings)
    outputs[0].parent.mkdir(exist_ok=True)
    _write_csv(outputs[0], FEATURE_COLUMNS, features)
    _write_csv(outputs[1], SUMMARY_COLUMNS, summary)
    with outputs[2].open("w", encoding="utf-8", newline="\n") as target:
        target.write(report_text(summary))
    return summary, outputs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    args = parser.parse_args(argv)
    try:
        summary, outputs = run(args.config)
    except SecomError as error:
        parser.exit(3, "SECOM 입력 오류:\n" + "\n".join(error.errors) + "\n")
    except (OSError, UnicodeError, csv.Error, ValueError, KeyError) as error:
        parser.exit(2, "오류: " + str(error) + "\n")
    print(NOTICE)
    for row in summary:
        if row["section"] in ("summary", "synthetic"):
            print("%s %s %s %s" % (row["section"], row["name"], row.get("value", ""), row.get("text", "")))
    print("저장 파일: " + ", ".join(output.as_posix() for output in outputs))


if __name__ == "__main__":
    main()

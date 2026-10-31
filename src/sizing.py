"""합성 라인의 설비 요구 사양 역산이다. 9단계 선택 조합을 고정하고 조건별 경계를 찾는다."""

import argparse
import csv
from dataclasses import dataclass, replace
from fractions import Fraction
import hashlib
from itertools import product
import json
from math import floor
from pathlib import Path
import re
from typing import Tuple

from . import line as lines
from .line import machine_order, show, target_uph, uph


NOTICE = ("합성 입력에서 개별 조건의 생산성 민감도를 계산한 연습이다. 모든 시간과 확률은 가상이고, "
          "실제 설비 사양이나 공급사 값이 아니다.")
SINGLE_NOTICE = "각 경계는 다른 조건을 기준값에 둔 개별 민감도이고 동시 허용 사양이 아니다."
MODEL_NOTICE = "검사 시간을 늘려도 검출 성능은 그대로라고 가정한다. 시간과 검사 성능의 관계는 모의하지 않았다."
GAUGE_NOTICE = ("허용 오불합격은 최종 양품의 추가 손실을 가정한 최악 산술값이다. 12단계 false_reject는 "
                "false_rejects / true_good인 별도 모의의 측정 관측 비율이고, 분모와 적용 대상이 다르다.")
HOLDOUT_NOTICE = "홀드아웃은 9단계 결과가 공개된 시드의 재사용 확인이고 새 독립 검증이 아니다."
FIRST_FAIL = "첫 미충족 직전 충족점"
NO_FAIL = "탐색 범위 내 미충족 미관측"
WITHIN = "가정상 산술 비교 이내"
OVER = "초과"
KEYS = {"line", "line_report", "balance_report", "guard_report", "test_multipliers", "repair_multipliers"}
DECIMAL = re.compile(r"[0-9]+(\.[0-9]+)?\Z")
ALLOWANCE = re.compile(r"양품보정허용test=(-?[0-9.]+);")
CURVE_COLUMNS = ("kind", "machine", "multiplier", "value_seconds", "seeds", "good_uph", "meets")
SPEC_COLUMNS = ("section", "machine", "combo", "gauge", "count", "current_seconds", "limit_seconds", "multiplier",
                "limit_kind", "nominal_seconds", "good_uph", "holdout_good_uph", "value", "guard_multiplier",
                "false_reject", "false_accept", "f_allow", "area_mm2")
GUARD_FIELDS = ("gauge", "multiplier", "true_defects", "false_accepts", "true_good", "false_rejects")


class SizingError(ValueError):
    """설정이 잘못되었다. 종료 코드는 3이다."""

    def __init__(self, errors):
        super().__init__("; ".join(errors))
        self.errors = errors


@dataclass(frozen=True)
class Settings:
    line: Path
    line_report: Path
    balance_report: Path
    guard_report: Path
    test_multipliers: Tuple[str, ...]
    repair_multipliers: Tuple[str, ...]


def _reject_constant(name):
    raise SizingError(["JSON에 허용되지 않는 값: " + name])


def _grid(data, key, errors):
    grid = data.get(key)
    if not isinstance(grid, list) or not grid or not all(isinstance(item, str) and DECIMAL.match(item) for item in grid):
        errors.append("$.%s: 십진수 문자열 목록이어야 함" % key)
        return ()
    values = [Fraction(item) for item in grid]
    if values[0] != 1 or any(right <= left for left, right in zip(values, values[1:])):
        errors.append("$.%s: 첫 값은 1이고 엄격히 증가해야 함" % key)
    return tuple(grid)


def load_settings(path):
    path = Path(path)
    with path.open(encoding="utf-8-sig") as source:
        data = json.load(source, parse_constant=_reject_constant)
    if not isinstance(data, dict):
        raise SizingError(["$: 객체여야 함"])
    errors = ["$: 필요한 키 없음 " + key for key in sorted(KEYS - set(data))]
    errors += ["$: 허용 밖 키 " + key for key in sorted(set(data) - KEYS)]
    for key in ("line", "line_report", "balance_report", "guard_report"):
        if key in data and not (isinstance(data[key], str) and data[key]):
            errors.append("$.%s: 경로 문자열이어야 함" % key)
    tests = _grid(data, "test_multipliers", errors) if "test_multipliers" in data else ()
    repairs = _grid(data, "repair_multipliers", errors) if "repair_multipliers" in data else ()
    if errors:
        raise SizingError(errors)
    return Settings(path.parent / data["line"], path.parent / data["line_report"], path.parent / data["balance_report"],
                    path.parent / data["guard_report"], tests, repairs)


def read_rows(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def first_limit(met):
    """충족 열에서 경계 위치와 종류를 고른다. 뒤에서 다시 충족해도 쓰지 않는다."""
    if not met or not met[0]:
        raise ValueError("기준선이 목표를 충족하지 않음")
    for index, value in enumerate(met):
        if not value:
            return index - 1, FIRST_FAIL
    return len(met) - 1, NO_FAIL


def extra_time(multiplier, test):
    """정수 ms 증분이다. 보고 경계는 이 증분을 더한 실제 적용 시간이다."""
    return floor((Fraction(multiplier) - 1) * test)


def repair_time(multiplier, repair):
    return floor(Fraction(multiplier) * repair)


def stretch(stations, machine, extra):
    """시간 0은 그 설비를 건너뛰는 표시다. 양수인 모델만 늘린다."""
    return [replace(station, times={model: value + extra if value > 0 else value
                                    for model, value in station.times.items()})
            if station.inspection == machine else station for station in stations]


def allowed_reject(target, value):
    """최종 양품의 추가 손실 최악 가정에서 허용되는 비율이다. 기준 미달이면 없다."""
    return 1 - target / value if value >= target else None


def gauge_status(reject, allowed):
    return WITHIN if reject <= allowed else OVER


def digest(value):
    return hashlib.sha256(repr(value).encode("utf-8")).hexdigest()[:16]


def route_digest(seed_routes):
    return digest([[(route.product_id, route.model, sorted(route.attempts.items()), route.completed, route.defective,
                     route.end_inspection, sorted(route.stops)) for route in routes] for routes in seed_routes])


def good_rate(stations, seed_routes, buffer_units, repair):
    total = lines.SimResult()
    for routes in seed_routes:
        total.add(lines.simulate(stations, routes, buffer_units, repair))
    return uph(total.good, total.end)


def read_compare(path, line):
    """9단계 결과의 형태를 확인한다. 선택과 시드를 여기서만 읽는다."""
    rows = read_rows(path)
    picks = [row for row in rows if row["section"] == "selection"]
    if len(picks) != 1 or not picks[0]["combo"]:
        raise ValueError("9단계 선택 조합이 없음")
    names = machine_order(line)
    expected = {"-".join(map(str, counts)) for counts in product(*(line.machines[name].counts for name in names))}
    development = [row for row in rows if row["section"] == "development"]
    labels = [row["combo"] for row in development]
    if len(labels) != len(set(labels)) or set(labels) != expected:
        raise ValueError("9단계 개발 행의 조합이 맞지 않음")
    holdout = [row for row in rows if row["section"] == "holdout"]
    if len(holdout) != 1 or holdout[0]["combo"] != picks[0]["combo"]:
        raise ValueError("9단계 홀드아웃 행이 맞지 않음")
    if len({(row["seeds"], row["products"]) for row in development}) != 1:
        raise ValueError("9단계 개발 행의 시드나 제품 수가 다름")
    return picks[0]["combo"], development, holdout[0]


def read_nominal(path, combo):
    keys = {"%s:%s" % pair: pair[0] for pair in combo.items()}
    found = {}
    for row in read_rows(path):
        if row["section"] == "spec" and row["key"] in keys:
            match = ALLOWANCE.search(row["text"])
            if match is None or keys[row["key"]] in found:
                raise ValueError("9단계 spec 행이 맞지 않음: " + row["key"])
            found[keys[row["key"]]] = match.group(1)
    if set(found) != set(combo):
        raise ValueError("9단계 spec 행이 없음")
    return found


def read_gauges(path):
    rows = [row for row in read_rows(path) if row["section"] == "holdout"]
    if len(rows) != 3 or len({row["gauge"] for row in rows}) != 3:
        raise ValueError("12단계 holdout 행이 세 게이지가 아님")
    for row in rows:
        if not all(row[name] for name in GUARD_FIELDS) or int(row["true_good"]) <= 0 or int(row["true_defects"]) <= 0:
            raise ValueError("12단계 holdout 값이 비어 있음: " + row["gauge"])
    return [(row["gauge"], row["multiplier"], Fraction(int(row["false_rejects"]), int(row["true_good"])),
             Fraction(int(row["false_accepts"]), int(row["true_defects"]))) for row in rows]


def load_routes(line_path, seed_text, products):
    raw = lines.read_line_file(line_path)
    config, _, recipe, book = lines.load_setup(line_path.parent / raw["generator"])
    return (config, recipe, [lines.product_routes(config, recipe, book, seed, products)
                             for seed in lines.parse_seeds(seed_text)])


def balance_of(line, config):
    weights = {model: Fraction(str(value)) for model, value in config["model_weights"].items()}
    ratios = {model: value / sum(weights.values()) for model, value in weights.items()}
    balance = lines.optimal_balance(line.elements, ratios, line.net, line.demand)
    if balance is None:
        raise ValueError("균형 해가 없음")
    return balance


def combo_of(names, label):
    return dict(zip(names, map(int, label.split("-"))))


def _row(columns, section=None, **fields):
    row = {column: fields.get(column, "") for column in columns}
    if section is not None:
        row["section"] = section
    return row


def seconds(value):
    return show(Fraction(value, 1000))


def scan(kind, machine, grid, values, measure, target, seeds):
    """격자 전부를 돌리고 첫 미충족 직전 충족점을 고른다. 곡선에는 미충족 뒤 값도 남긴다."""
    rates = [measure(value) for value in values]
    curve = [_row(CURVE_COLUMNS, kind=kind, machine=machine, multiplier=text, value_seconds=seconds(value), seeds=seeds,
                  good_uph=show(rate), meets=int(rate >= target))
             for text, value, rate in zip(grid, values, rates)]
    index, kinds = first_limit([rate >= target for rate in rates])
    return curve, index, kinds


def sheet_text(baseline, test_rows, repair, joint, gauges):
    lines_out = ["# 합성 설비 요구 사양 역산 연습표", "", NOTICE, "", SINGLE_NOTICE, "", MODEL_NOTICE, "", HOLDOUT_NOTICE, "",
                 "선택 조합 %s, 목표 양품 UPH %s, 기준선 개발 %s, 홀드아웃 %s." % baseline, "",
                 "## 조건별 경계", "",
                 "| 설비 | 대수 | 현재 test(초) | 경계(초) | 배수 | 경계 종류 | 9단계 명목 허용(초) | 홀드아웃 |",
                 "| --- | ---: | ---: | ---: | ---: | --- | ---: | --- |"]
    for row in test_rows:
        lines_out.append("| %s | %s | %s | %s | %s | %s | %s | %s |" % (
            row["machine"], row["count"], row["current_seconds"], row["limit_seconds"], row["multiplier"],
            row["limit_kind"], row["nominal_seconds"], row["value"]))
    lines_out += ["", "모의 경계와 명목 허용의 차이는 명목식과 고정 경로 모의의 차이이고, 손실 크기나 원인별 기여가 아니다.", "",
                  "| 수리 1회 현재(초) | 경계(초) | 배수 | 경계 종류 | 홀드아웃 |", "| ---: | ---: | ---: | --- | --- |",
                  "| %s | %s | %s | %s | %s |" % (repair["current_seconds"], repair["limit_seconds"], repair["multiplier"],
                                                 repair["limit_kind"], repair["value"]),
                  "", "수리 경계는 고정된 정지 표식에 따른 서버 해제 뒤 복구 지연이다. 고장 간격이나 가동률 사양이 아니다.", "",
                  "## 동시 적용", "",
                  "모든 경계를 함께 넣으면 개발 %s, 홀드아웃 %s, 결과는 **%s**." % (joint["good_uph"], joint["holdout_good_uph"],
                                                                 joint["value"]), "",
                  "## 측정기 허용 오불합격", "", GAUGE_NOTICE, "",
                  "| 게이지 | 가드 배수 | 12단계 오불합격 | 12단계 오합격 | 라인 허용값 | 비교 |",
                  "| --- | ---: | ---: | ---: | ---: | --- |"]
    for row in gauges:
        lines_out.append("| %s | %s | %s | %s | %s | %s |" % (row["gauge"], row["guard_multiplier"], row["false_reject"],
                                                              row["false_accept"], row["f_allow"], row["value"]))
    lines_out += ["", "비교는 측정기 적합 판정이 아니다. 유출 기준은 12단계가 따로 판단한다.", "",
                  "## 실제 적용 전 필요한 확인", "",
                  "| 가정 | 계산한 경계 | 필요한 확인 |", "| --- | --- | --- |",
                  "| 사이클은 고정 시간이다 | test 경계 | 실측 사이클과 시간 구성 |",
                  "| test를 늘려도 검출 성능은 같다 | test 경계 | 검사 성능과 시간의 관계 |",
                  "| 정지는 외생이고 수리는 고정 시간이다 | 수리 경계 | 정지·복구 기록 |",
                  "| 조건을 하나씩만 바꾼다 | 개별 경계 전부 | 동시 조건 검증 |"]
    return "\n".join(lines_out) + "\n"


def _write_csv(path, columns, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def run(path):
    path = Path(path)
    settings = load_settings(path)
    raw = lines.read_line_file(settings.line)
    _, _, recipe, _ = lines.load_setup(settings.line.parent / raw["generator"])
    line = lines.load_line(settings.line, recipe.models)
    label, development, held = read_compare(settings.line_report, line)
    names = machine_order(line)
    combo = combo_of(names, label)
    nominal = read_nominal(settings.balance_report, combo)
    gauges = read_gauges(settings.guard_report)
    seed_text, products = development[0]["seeds"], int(development[0]["products"])
    config, _, dev_routes = load_routes(settings.line, seed_text, products)
    _, _, hold_routes = load_routes(settings.line, held["seeds"], int(held["products"]))
    balance = balance_of(line, config)
    target = target_uph(line)

    def rate(stations, routes, repair=line.repair):
        return good_rate(stations, routes, line.buffer_units, repair)

    def stations_of(counts):
        return lines.build_stations(line, balance, counts)

    rates = {}
    for row in development:
        rates[row["combo"]] = rate(stations_of(combo_of(names, row["combo"])), dev_routes)
        if show(rates[row["combo"]]) != row["good_uph"]:
            raise ValueError("9단계 개발 결과가 재현되지 않음: " + row["combo"])
    base = stations_of(combo)
    hold_rate = rate(base, hold_routes)
    if show(hold_rate) != held["good_uph"]:
        raise ValueError("9단계 홀드아웃 결과가 재현되지 않음")
    if rates[label] < target:
        raise ValueError("기준선이 목표를 충족하지 않음")
    rows = [_row(SPEC_COLUMNS, "notice", value=text)
            for text in (NOTICE, SINGLE_NOTICE, MODEL_NOTICE, GAUGE_NOTICE, HOLDOUT_NOTICE)]
    rows.append(_row(SPEC_COLUMNS, "baseline", combo=label, good_uph=show(rates[label]), holdout_good_uph=show(hold_rate),
                     value="target_uph=%s;line=%s;dev_routes=%s;holdout_routes=%s" % (
                         show(target), digest(line), route_digest(dev_routes), route_digest(hold_routes))))
    curve, test_rows, joint_stations = [], [], base
    for name in names:
        test = line.machines[name].test
        extras = [extra_time(text, test) for text in settings.test_multipliers]

        def measure(value):
            return rate(stretch(base, name, value - test), dev_routes)

        part, index, kind = scan("test", name, settings.test_multipliers, [test + extra for extra in extras], measure,
                                 target, seed_text)
        curve += part
        stretched = stretch(base, name, extras[index])
        joint_stations = stretch(joint_stations, name, extras[index])
        held_value = rate(stretched, hold_routes)
        test_rows.append(_row(SPEC_COLUMNS, "test", machine=name, combo=label, count=combo[name],
                              current_seconds=seconds(test), limit_seconds=seconds(test + extras[index]),
                              multiplier=settings.test_multipliers[index], limit_kind=kind, nominal_seconds=nominal[name],
                              good_uph=part[index]["good_uph"], holdout_good_uph=show(held_value),
                              value="확인" if held_value >= target else "미달"))
    repairs = [repair_time(text, line.repair) for text in settings.repair_multipliers]
    part, index, kind = scan("repair", "ALL", settings.repair_multipliers, repairs, lambda value: rate(base, dev_routes, value),
                             target, seed_text)
    curve += part
    held_value = rate(base, hold_routes, repairs[index])
    repair_row = _row(SPEC_COLUMNS, "repair", machine="ALL", combo=label, current_seconds=seconds(line.repair),
                      limit_seconds=seconds(repairs[index]), multiplier=settings.repair_multipliers[index], limit_kind=kind,
                      good_uph=part[index]["good_uph"], holdout_good_uph=show(held_value),
                      value="확인" if held_value >= target else "미달")
    joint_dev = rate(joint_stations, dev_routes, repairs[index])
    joint_hold = rate(joint_stations, hold_routes, repairs[index])
    joint_row = _row(SPEC_COLUMNS, "joint", combo=label, good_uph=show(joint_dev), holdout_good_uph=show(joint_hold),
                     value="동시 충족" if joint_dev >= target and joint_hold >= target else "동시 미충족")
    allowed = allowed_reject(target, rates[label])
    gauge_rows = [_row(SPEC_COLUMNS, "gauge", combo=label, gauge=gauge, guard_multiplier=multiplier,
                       false_reject=show(reject), false_accept=show(accept), f_allow=show(allowed),
                       value=gauge_status(reject, allowed)) for gauge, multiplier, reject, accept in gauges]
    combo_rows = []
    for row in development:
        value = allowed_reject(target, rates[row["combo"]])
        combo_rows.append(_row(SPEC_COLUMNS, "combo", combo=row["combo"], good_uph=row["good_uph"],
                               f_allow="" if value is None else show(value), area_mm2=row["area_mm2"]))
    rows += test_rows + [repair_row, joint_row] + gauge_rows + combo_rows
    directory = Path("reports")
    directory.mkdir(exist_ok=True)
    stem = path.stem
    written = [directory / (stem + suffix) for suffix in ("_curve.csv", "_spec.csv", "_sheet.md")]
    _write_csv(written[0], CURVE_COLUMNS, curve)
    _write_csv(written[1], SPEC_COLUMNS, rows)
    text = sheet_text((label, show(target), show(rates[label]), show(hold_rate)), test_rows, repair_row, joint_row, gauge_rows)
    with written[2].open("w", encoding="utf-8", newline="\n") as target_file:
        target_file.write(text)
    return test_rows, repair_row, joint_row, gauge_rows, written


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    args = parser.parse_args(argv)
    try:
        test_rows, repair_row, joint_row, gauge_rows, written = run(args.config)
    except SizingError as error:
        parser.exit(3, "역산 입력 오류:\n" + "\n".join(error.errors) + "\n")
    except (OSError, UnicodeError, csv.Error, ValueError, KeyError) as error:
        parser.exit(2, "오류: " + str(error) + "\n")
    print(NOTICE)
    print(SINGLE_NOTICE)
    print("machine | count | current_seconds | limit_seconds | limit_kind | holdout")
    for row in test_rows:
        print(" | ".join(str(row[column]) for column in ("machine", "count", "current_seconds", "limit_seconds", "limit_kind",
                                                         "value")))
    print("repair | %s -> %s | %s" % (repair_row["current_seconds"], repair_row["limit_seconds"], repair_row["value"]))
    print("joint | %s" % joint_row["value"])
    print("저장 파일: " + ", ".join(path.as_posix() for path in written))


if __name__ == "__main__":
    main()

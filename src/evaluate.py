"""여러 시드로 설비 정지 규칙을 비교한다. 숨은 진실은 평가에서만 쓰고 판정기에는 주지 않는다."""

import argparse
import csv
from dataclasses import dataclass, replace
from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction
import hashlib
from pathlib import Path
from statistics import median

from .generate import GENERATOR_VERSION, RESTART_GENERATOR_VERSION, build_rows, load_setup
from .summary import ASSUMPTION_NOTICE, build_analysis


DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "recipes/generator_restart.json"
MIN_DETECTION = Fraction(95, 100)
MAX_MEAN_DELAY = 10
NO_RULE = "기준 충족 규칙 없음"
RUN_COLUMNS = (
    "rule", "seed", "stops", "true_stops", "false_stops", "detected", "delay_sum", "full_outage",
    "unfinished", "normal_held", "defective_completed",
)
RULE_COLUMNS = (
    "section", "rule", "runs", "detection_rate", "mean_delay", "stop_precision", "mean_false_stops",
    "false_stop_runs", "full_outage_runs", "unfinished_min", "unfinished_median", "unfinished_max",
    "mean_normal_held", "mean_defective_completed", "criteria", "value",
)


@dataclass(frozen=True)
class RunMetrics:
    true_stops: int
    false_stops: int
    detected: int
    delay_sum: int
    full_outage: bool
    unfinished: int
    normal_held: int
    defective_completed: int


def run_metrics(analysis, faulty, defective):
    """정지 시점에 수리되지 않은 고장 설비의 정지만 정탐이다."""
    fixed_at = {}
    for restart in analysis.restarts:
        if restart.result == "FIXED":
            fixed_at.setdefault(restart.equipment, restart.row_index)
    first_true = {}
    true_stops = 0
    for stop in analysis.stop_history:
        if stop.equipment in faulty and stop.row_index < fixed_at.get(stop.equipment, stop.row_index + 1):
            true_stops += 1
            first_true.setdefault(stop.equipment, stop)
    delays = [sum(item.equipment == name and item.row_index <= stop.row_index
                  for item in analysis.first_inspections) for name, stop in first_true.items()]

    book = analysis.process.equipment_book.equipment
    timeline = sorted([(stop.row_index, 1, stop.equipment) for stop in analysis.stop_history]
                      + [(item.row_index, 0, item.equipment) for item in analysis.restarts])
    stopped, full_outage = set(), False
    for _, stopping, equipment in timeline:
        if stopping:
            stopped.add(equipment)
        else:
            stopped.discard(equipment)
        full_outage = full_outage or all(name in stopped for name, kind in book.items() if kind == book[equipment])

    products = analysis.process.products
    complete = "레시피 모의 흐름 완료"
    return RunMetrics(
        true_stops, len(analysis.stop_history) - true_stops, len(first_true), sum(delays), full_outage,
        sum(product.status != complete for product in products.values()),
        sum(product.status == "보류" and product_id not in defective for product_id, product in products.items()),
        sum(product.status == complete and product_id in defective for product_id, product in products.items()),
    )


def aggregate(runs, faulty_count):
    count = len(runs)
    stops = sum(run.true_stops + run.false_stops for run in runs)
    detected = sum(run.detected for run in runs)
    unfinished = [run.unfinished for run in runs]
    return {
        "runs": count,
        "detection_rate": Fraction(detected, count * faulty_count) if faulty_count else None,
        "mean_delay": Fraction(sum(run.delay_sum for run in runs), detected) if detected else None,
        "stop_precision": Fraction(sum(run.true_stops for run in runs), stops) if stops else None,
        "mean_false_stops": Fraction(sum(run.false_stops for run in runs), count),
        "false_stop_runs": sum(run.false_stops > 0 for run in runs),
        "full_outage_runs": sum(run.full_outage for run in runs),
        "unfinished_min": min(unfinished), "unfinished_median": Fraction(median(unfinished)),
        "unfinished_max": max(unfinished),
        "mean_normal_held": Fraction(sum(run.normal_held for run in runs), count),
        "mean_defective_completed": Fraction(sum(run.defective_completed for run in runs), count),
    }


def meets_criteria(metrics):
    return (metrics["detection_rate"] is not None and metrics["mean_delay"] is not None
            and metrics["detection_rate"] >= MIN_DETECTION and metrics["mean_delay"] <= MAX_MEAN_DELAY)


def select_rule(rule_metrics):
    """명세에 미리 고정한 기준이다. 후보가 없으면 완화하지 않고 None을 돌려준다."""
    candidates = [rule for rule, metrics in rule_metrics.items() if meets_criteria(metrics)]
    if not candidates:
        return None
    return min(candidates, key=lambda rule: (
        rule_metrics[rule]["mean_false_stops"], rule_metrics[rule]["mean_delay"],
        rule_metrics[rule]["unfinished_median"], rule,
    ))


def holdout_verdict(metrics):
    return "확인" if meets_criteria(metrics) else "미확인"


def parse_seeds(text):
    start, separator, end = text.partition("-")
    if not separator or not start.isdigit() or not end.isdigit() or int(start) > int(end):
        raise ValueError("--seeds는 시작-끝 형식이고 시작이 끝 이하여야 함: " + text)
    return range(int(start), int(end) + 1)


def parse_rules(text):
    rules = []
    for item in text.split(","):
        window, separator, fails = item.partition(":")
        if not separator or not window.isdigit() or not fails.isdigit():
            raise ValueError("--rules는 window:fails 형식이어야 함: " + item)
        rule = (int(window), int(fails))
        if not 1 <= rule[1] <= rule[0] <= 20:
            raise ValueError("규칙은 1 <= fails <= window <= 20이어야 함: " + item)
        if rule in rules:
            raise ValueError("중복 규칙: " + item)
        rules.append(rule)
    return rules


def evaluate(config_path, seeds, rules, products):
    config, content, recipe, book = load_setup(config_path)
    faulty = set(config["faulty_equipment"])
    runs, rule_metrics = {}, {}
    for window, fails in rules:
        ruled = replace(book, window=window, fails=fails)
        rule_runs = []
        for seed in seeds:
            generator, _, rows, _ = build_rows(seed, products, config, recipe.models, ruled)
            analysis = build_analysis(rows, recipe.models, ruled)
            rule_runs.append(run_metrics(analysis, faulty, set(generator.defective_products)))
        runs[window, fails] = rule_runs
        rule_metrics[window, fails] = aggregate(rule_runs, len(faulty))
    provenance = {
        "config_sha256": hashlib.sha256(content).hexdigest(), "recipe_sha256": recipe.sha256,
        "equipment_sha256": book.sha256,
        "generator_version": RESTART_GENERATOR_VERSION if "restart" in config else GENERATOR_VERSION,
        "seeds": str(seeds[0]) + "-" + str(seeds[-1]), "products": str(products),
    }
    return runs, rule_metrics, provenance


def _name(rule):
    return str(rule[0]) + ":" + str(rule[1])


def _decimal(value, places):
    if value is None:
        return ""
    exact = Decimal(value.numerator) / Decimal(value.denominator)
    return format(exact.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP), "." + str(places) + "f")


def rule_rows(rule_metrics, provenance, holdout):
    rows = [dict.fromkeys(RULE_COLUMNS, "") for _ in range(len(provenance) + 1)]
    rows[0].update(section="notice", value=ASSUMPTION_NOTICE)
    for row, (key, value) in zip(rows[1:], provenance.items()):
        row.update(section="provenance", rule=key, value=value)
    for rule, metrics in rule_metrics.items():
        rows.append({
            **dict.fromkeys(RULE_COLUMNS, ""), "section": "rule", "rule": _name(rule), "runs": metrics["runs"],
            "detection_rate": _decimal(metrics["detection_rate"], 4), "mean_delay": _decimal(metrics["mean_delay"], 2),
            "stop_precision": _decimal(metrics["stop_precision"], 4),
            "mean_false_stops": _decimal(metrics["mean_false_stops"], 2),
            "false_stop_runs": metrics["false_stop_runs"], "full_outage_runs": metrics["full_outage_runs"],
            "unfinished_min": metrics["unfinished_min"],
            "unfinished_median": _decimal(metrics["unfinished_median"], 1),
            "unfinished_max": metrics["unfinished_max"],
            "mean_normal_held": _decimal(metrics["mean_normal_held"], 2),
            "mean_defective_completed": _decimal(metrics["mean_defective_completed"], 2),
            "criteria": holdout_verdict(metrics),
        })
    if not holdout:
        selected = select_rule(rule_metrics)
        rows.append({**dict.fromkeys(RULE_COLUMNS, ""), "section": "selection",
                     "rule": _name(selected) if selected else "", "value": "선택" if selected else NO_RULE})
    return rows


def run_rows(runs, seeds):
    return [{"rule": _name(rule), "seed": seed, "stops": run.true_stops + run.false_stops,
             "true_stops": run.true_stops, "false_stops": run.false_stops, "detected": run.detected,
             "delay_sum": run.delay_sum, "full_outage": int(run.full_outage), "unfinished": run.unfinished,
             "normal_held": run.normal_held, "defective_completed": run.defective_completed}
            for rule, rule_runs in runs.items() for seed, run in zip(seeds, rule_runs)]


def write_csv(path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def print_rules(rows):
    columns = RULE_COLUMNS[1:-1]
    print(" | ".join(columns))
    for row in rows:
        if row["section"] == "rule":
            print(" | ".join(str(row[column]) for column in columns))
    for row in rows:
        if row["section"] in ("notice", "selection"):
            print((row["rule"] + " " if row["rule"] else "") + row["value"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--seeds", required=True, help="시작-끝, 예: 0-99")
    parser.add_argument("--rules", required=True, help="window:fails 목록, 예: 3:2,5:3")
    parser.add_argument("--products", type=int, default=500)
    parser.add_argument("--out", required=True, help="reports/ 아래 보고서 이름")
    parser.add_argument("--holdout", action="store_true", help="규칙을 고르지 않고 기준 충족만 확인")
    args = parser.parse_args(argv)
    try:
        if args.products < 1:
            raise ValueError("products는 양의 정수여야 함")
        seeds = parse_seeds(args.seeds)
        runs, rule_metrics, provenance = evaluate(args.config, seeds, parse_rules(args.rules), args.products)
        rows = rule_rows(rule_metrics, provenance, args.holdout)
    except (OSError, UnicodeError, ValueError, KeyError) as error:
        parser.exit(2, "오류: " + str(error) + "\n")
    rules_path, runs_path = Path("reports") / (args.out + "_rules.csv"), Path("reports") / (args.out + "_runs.csv")
    write_csv(rules_path, RULE_COLUMNS, rows)
    write_csv(runs_path, RUN_COLUMNS, run_rows(runs, seeds))
    print_rules(rows)
    print("저장 파일: " + rules_path.as_posix() + ", " + runs_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

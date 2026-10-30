"""기존 보고서 묶음과 독립된 전체 입력 분석과 긴 표 summary."""

from collections import Counter, defaultdict
import csv
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from .recipe_rules import RESTART_EVENT, RecipeProcess
from .reason_codes import REASON_CODES, injected_error_codes, rejection_code


ASSUMPTION_NOTICE = "생성 데이터의 확률은 가정이며 실제 설비 진단 근거가 아니다."
SUMMARY_COLUMNS = (
    "section", "key", "value", "numerator", "denominator", "count", "inspection", "equipment", "rule_id",
    "first_count", "first_fail_count", "first_fail_rate", "all_count", "all_fail_count", "all_fail_rate",
    "rejected_count", "unperformed_count", "state", "row_index", "seq", "product_id",
    "cause_row_indices", "cause_seqs", "cause_product_ids", "normal_rows", "injected_count",
    "injection_rate", "actual_rejections", "reason_template",
)


@dataclass(frozen=True)
class InspectionRecord:
    # 1부터 세는 데이터 행 인덱스이며 CSV 헤더는 세지 않는다. seq와 무관하다.
    row_index: int
    seq: str
    product_id: str
    inspection: str
    equipment: str
    result: str
    retest_number: int
    value: str = ""


@dataclass(frozen=True)
class EquipmentStop:
    equipment: str
    row_index: int
    seq: str
    product_id: str
    fail_causes: tuple
    window: tuple


@dataclass(frozen=True)
class EquipmentRestart:
    equipment: str
    row_index: int
    seq: str
    result: str


@dataclass
class Analysis:
    process: RecipeProcess
    events: list
    decisions: list
    first_inspections: list
    all_inspections: list
    stops: dict
    stop_history: list
    restarts: list

    def stop_at(self, equipment, row_index):
        """그 행 시점에 유효했던 정지."""
        return [stop for stop in self.stop_history
                if stop.equipment == equipment and stop.row_index < row_index][-1]


def build_analysis(events, models, equipment_book):
    """입력을 물리 순서로 처리한다. 분석과 trace가 같은 판정·정지 근거를 쓴다."""
    process = RecipeProcess(models, equipment_book)
    events = [dict(event) for event in events]
    decisions, first, all_results, stops = [], [], [], {}
    stop_history, restarts = [], []
    equipment_windows = defaultdict(list)
    for row_index, event in enumerate(events, 1):
        product_before = process.products.get(event.get("product_id"))
        inspection = event.get("inspection")
        is_first = product_before is not None and inspection not in product_before.inspections
        decision = process.apply(event)
        decisions.append(decision)
        if decision.accepted and equipment_book.restart_enabled and event["event"] == RESTART_EVENT:
            equipment_windows[event["equipment"]].clear()
            restarts.append(EquipmentRestart(event["equipment"], row_index, decision.seq, event["result"]))
        if not decision.accepted or event["event"] != "INSPECT":
            continue
        product = process.products[event["product_id"]]
        record = InspectionRecord(
            row_index, decision.seq, decision.product_id, inspection, event["equipment"], decision.result,
            0 if is_first else product.retest_counts[inspection], decision.value,
        )
        all_results.append(record)
        if not is_first:
            continue
        first.append(record)
        window = equipment_windows[record.equipment]
        window.append(record)
        del window[:-equipment_book.window]
        if process.equipment[record.equipment].stopped_at_seq is not None:
            stop = EquipmentStop(
                record.equipment, row_index, record.seq, record.product_id,
                tuple(item for item in window if item.result == "FAIL"), tuple(window),
            )
            stops.setdefault(record.equipment, stop)
            stop_history.append(stop)
    return Analysis(process, events, decisions, first, all_results, stops, stop_history, restarts)


def _ratio(numerator, denominator):
    if not denominator:
        return ""
    value = Decimal(numerator) / Decimal(denominator)
    return format(value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP), ".4f")


def _row(section, key, **fields):
    return {column: fields.get(column, section if column == "section" else key if column == "key" else "")
            for column in SUMMARY_COLUMNS}


def _metrics(section, key, first, all_results, rejected_count, unperformed_count="", **identity):
    first_fails = sum(item.result == "FAIL" for item in first)
    all_fails = sum(item.result == "FAIL" for item in all_results)
    return _row(
        section, key, first_count=len(first), first_fail_count=first_fails,
        first_fail_rate=_ratio(first_fails, len(first)), all_count=len(all_results),
        all_fail_count=all_fails, all_fail_rate=_ratio(all_fails, len(all_results)),
        rejected_count=rejected_count, unperformed_count=unperformed_count, **identity,
    )


def build_summary(analysis, meta=None):
    """비율 분모는 허용된 결과뿐이다. 알려지지 않은 거절 사유는 실패한다."""
    process = analysis.process
    rejected = [(event, decision) for event, decision in zip(analysis.events, analysis.decisions)
                if not decision.accepted]
    codes = Counter(rejection_code(decision, event, process.models) for event, decision in rejected)
    first, all_results = analysis.first_inspections, analysis.all_inspections
    products = list(process.products.values())
    inspection_ids = sorted({item.id for model in process.models.values() for item in model.inspections})
    unperformed = Counter(item.id for product in products for item in product.recipe.inspections
                          if item.id not in product.inspections)
    rejected_inspections = [event for event, _ in rejected if event.get("event") == "INSPECT"]
    rows = [_row("notice", "generation_assumption", value=ASSUMPTION_NOTICE)]

    first_results = {(record.product_id, record.inspection): record.result for record in first}
    first_pass = sum(product.status == "레시피 모의 흐름 완료" and all(
        first_results.get((product_id, item.id)) == "PASS" for item in product.recipe.inspections
    ) for product_id, product in process.products.items())
    rows.extend((
        _row("product_metrics", "registered_count", value=len(products)),
        _row("product_metrics", "first_pass_count", value=first_pass),
        _row("product_metrics", "fpy", value=_ratio(first_pass, len(products)), numerator=first_pass,
             denominator=len(products)),
    ))
    statuses = Counter("완료" if product.status == "레시피 모의 흐름 완료" else
                       "공정 진행 중" if product.status.startswith("공정 진행 중(") else product.status
                       for product in products)
    for state in ("완료", "보류", "폐기", "검사 대기", "공정 진행 중", "등록"):
        rows.append(_row("status_distribution", state, count=statuses[state]))

    rows.append(_metrics("inspection_metrics", "ALL", first, all_results,
                         len(rejected_inspections), sum(unperformed.values())))
    for inspection in sorted(set(inspection_ids) | {event.get("inspection") or "" for event in rejected_inspections}):
        rows.append(_metrics(
            "inspection_metrics", inspection,
            [item for item in first if item.inspection == inspection],
            [item for item in all_results if item.inspection == inspection],
            sum((event.get("inspection") or "") == inspection for event in rejected_inspections), unperformed[inspection],
            inspection=inspection,
        ))
    equipment_ids = set(process.equipment) | {event.get("equipment") or "" for event in rejected_inspections}
    for equipment in sorted(equipment_ids):
        rows.append(_metrics(
            "equipment_metrics", equipment,
            [item for item in first if item.equipment == equipment],
            [item for item in all_results if item.equipment == equipment],
            sum((event.get("equipment") or "") == equipment for event in rejected_inspections),
            inspection=process.equipment_book.equipment.get(equipment, ""), equipment=equipment,
        ))

    quality_first = Counter((item.inspection, item.equipment) for item in first if item.result == "FAIL")
    quality_all = Counter((item.inspection, item.equipment) for item in all_results if item.result == "FAIL")
    quality_pairs = quality_first.keys() | quality_all.keys()
    for inspection, equipment in sorted(quality_pairs, key=lambda pair: (-quality_first[pair], pair)):
        rows.append(_row("quality_pareto", inspection + "@" + equipment, inspection=inspection, equipment=equipment,
                         first_fail_count=quality_first[inspection, equipment],
                         all_fail_count=quality_all[inspection, equipment]))
    for code, count in sorted(codes.items(), key=lambda item: (-item[1], item[0])):
        if code != "EQUIP_STOPPED":
            rule, template = REASON_CODES[code]
            rows.append(_row("input_error_pareto", code, rule_id=rule, count=count, reason_template=template))

    stopped_rows = [(row_index, event["equipment"]) for row_index, (event, decision)
                    in enumerate(zip(analysis.events, analysis.decisions), 1)
                    if not decision.accepted and decision.rule_id == "RULE_EQUIP" and decision.reason == "정지된 설비"]
    restart_mode = process.equipment_book.restart_enabled
    for equipment, state in process.equipment.items():
        history = [stop for stop in analysis.stop_history if stop.equipment == equipment]
        for number, stop in enumerate(history or [None], 1):
            numbered = restart_mode and stop is not None
            resumed = numbered and (number < len(history) or state.stopped_at_seq is None)
            rows.append(_row(
                "equipment_stops", equipment + "#" + str(number) if numbered else equipment,
                equipment=equipment, inspection=process.equipment_book.equipment[equipment],
                state="재가동" if resumed else state.state,
                row_index=stop.row_index if stop else "", seq=stop.seq if stop else "",
                product_id=stop.product_id if stop else "",
                cause_row_indices=";".join(str(item.row_index) for item in stop.fail_causes) if stop else "",
                cause_seqs=";".join(item.seq for item in stop.fail_causes) if stop else "",
                cause_product_ids=";".join(item.product_id for item in stop.fail_causes) if stop else "",
                rejected_count=sum(name == equipment and analysis.stop_at(name, row_index) is stop
                                   for row_index, name in stopped_rows),
            ))
    if restart_mode:
        for equipment in process.equipment:
            history = [item for item in analysis.restarts if item.equipment == equipment]
            for number, restart in enumerate(history, 1):
                rows.append(_row("equipment_restarts", equipment + "#" + str(number), equipment=equipment,
                                 row_index=restart.row_index, seq=restart.seq, state=restart.result))
    input_errors = sum(count for code, count in codes.items() if code != "EQUIP_STOPPED")
    for key, value in (("input_rows", len(analysis.events)), ("rejected_rows", len(rejected)),
                       ("rule_rejections", len(rejected)), ("input_errors", input_errors),
                       ("equipment_stopped", codes["EQUIP_STOPPED"]), ("other_rejections", 0)):
        rows.append(_row("rejection_totals", key, value=value))
    rows.append(_row("rejection_totals", "rejection_rate", value=_ratio(len(rejected), len(analysis.events)),
                     numerator=len(rejected), denominator=len(analysis.events)))
    for rule, count in sorted(Counter(decision.rule_id for _, decision in rejected).items()):
        rows.append(_row("rule_rejections", rule, rule_id=rule, count=count))

    if meta is not None:
        normal_rows = meta["normal_rows"]
        injected = meta["injected_errors"]
        for code in injected_error_codes(process.measured):
            count = injected.get(code, 0)
            rows.append(_row("injection_comparison", code, rule_id=REASON_CODES[code][0], normal_rows=normal_rows,
                             injected_count=count, injection_rate=_ratio(count, normal_rows),
                             actual_rejections=codes[code]))
        rows.append(_row("injection_comparison", "TOTAL", normal_rows=normal_rows,
                         injected_count=sum(injected.values()), injection_rate=_ratio(sum(injected.values()), normal_rows),
                         actual_rejections=len(rejected)))
        if "defective_products" in meta:
            defective = set(meta["defective_products"])
            unregistered = defective - process.products.keys()
            if unregistered:
                raise ValueError("meta.json의 defective_products에 등록되지 않은 제품 ID: " + repr(sorted(unregistered)))
            unregistered = set(meta.get("leaked_products", ())) - process.products.keys()
            if unregistered:
                raise ValueError("meta.json의 leaked_products에 등록되지 않은 제품 ID: " + repr(sorted(unregistered)))
            defect_states = Counter(process.products[product_id].status for product_id in defective)
            completed = defect_states["레시피 모의 흐름 완료"]
            discarded, held = defect_states["폐기"], defect_states["보류"]
            for key, state, count in (
                ("defective_discarded", "폐기", discarded),
                ("defective_held", "보류", held),
                ("defective_completed", "완료", completed),
                ("defective_other", "그 밖", len(defective) - discarded - held - completed),
                ("normal_discarded", "폐기", statuses["폐기"] - discarded),
            ):
                rows.append(_row("injection_comparison", key, state=state, count=count))
    return rows


def write_summary(stem, rows):
    """일반 stem은 reports/에 쓴다. 절대 stem은 지정한 디렉터리에 쓴다."""
    path = Path("reports") / (str(stem) + "_summary.csv")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=SUMMARY_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def print_summary(rows, path):
    """각 절에 값이 있는 열만 터미널 표에 표시한다."""
    sections = dict.fromkeys(row["section"] for row in rows)
    for section in sections:
        section_rows = [row for row in rows if row["section"] == section]
        columns = [column for column in SUMMARY_COLUMNS if column != "section" and
                   any(row[column] != "" for row in section_rows)]
        print("[" + section + "]")
        print(" | ".join(columns))
        for row in section_rows:
            print(" | ".join(str(row[column]) for column in columns))
        print()
    print("저장 파일: " + path.as_posix())

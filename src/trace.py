"""전체 처리 후 제품의 물리 행 순서와 다른 제품의 설비 정지 원인을 추적한다."""

import csv
from pathlib import Path
from urllib.parse import quote


TRACE_COLUMNS = (
    "section", "row_index", "seq", "product_id", "input", "model", "equipment", "rule_id",
    "decision", "reason", "state", "stop_row_index", "stop_seq", "stop_product_id",
    "cause_row_indices", "cause_seqs", "cause_product_ids", "incomplete_reason", "history",
)


def _row(section, product_id, **values):
    values.update(section=section, product_id=product_id)
    return {column: values.get(column, "") for column in TRACE_COLUMNS}


def build_trace(analysis, product_id):
    rows = []
    for row_index, (event, decision) in enumerate(zip(analysis.events, analysis.decisions), 1):
        if decision.product_id != product_id:
            continue
        causes = {}
        if not decision.accepted and decision.rule_id == "RULE_EQUIP" and decision.reason == "정지된 설비":
            stop = analysis.stops[event["equipment"]]
            causes = {
                "stop_row_index": stop.row_index, "stop_seq": stop.seq, "stop_product_id": stop.product_id,
                "cause_row_indices": ";".join(str(item.row_index) for item in stop.fail_causes),
                "cause_seqs": ";".join(item.seq for item in stop.fail_causes),
                "cause_product_ids": ";".join(item.product_id for item in stop.fail_causes),
            }
        rows.append(_row(
            "event", product_id, row_index=row_index, seq=decision.seq, input=decision.input_text,
            model=event.get("model", ""), equipment=event.get("equipment", ""), rule_id=decision.rule_id,
            decision="허용" if decision.accepted else "거절", reason=decision.reason, state=decision.state, **causes,
        ))
    if not rows:
        raise ValueError("입력에 없는 제품 ID: " + product_id)
    product = analysis.process.products.get(product_id)
    history = product.history if product is not None else ""
    if product is not None and not analysis.process.retest_enabled:
        history = "; ".join(
            item.id + ": " + " → ".join(record.result + "@" + record.seq + "[" + record.equipment + "]"
                                        for record in analysis.all_inspections
                                        if record.product_id == product_id and record.inspection == item.id)
            for item in product.recipe.inspections if item.id in product.inspections
        )
    rows.append(_row(
        "current_state", product_id, state=product.status if product is not None else "미등록",
        incomplete_reason=product.incomplete_reason if product is not None else "등록된 제품 없음", history=history,
    ))
    return rows


def write_trace(stem, product_id, rows, product_ids):
    component = quote(product_id, safe="")
    if any(other != product_id and quote(other, safe="").casefold() == component.casefold()
           for other in product_ids):
        component += "!" + product_id.encode("utf-8").hex()
    path = Path("reports") / (stem + "_trace_" + component + ".csv")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=TRACE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def print_trace(rows, path):
    print("[제품 추적: " + rows[0]["product_id"] + "]")
    print(" | ".join(TRACE_COLUMNS[1:-2]))
    for row in rows[:-1]:
        print(" | ".join(str(row[column]) for column in TRACE_COLUMNS[1:-2]))
    final = rows[-1]
    print("현재 상태의 근거")
    for column in ("state", "incomplete_reason", "history"):
        print(column + ": " + str(final[column]))
    print("저장 파일: " + path.as_posix())
    print()

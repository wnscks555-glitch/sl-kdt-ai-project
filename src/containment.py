"""설비 정지 시점까지 그 설비를 PASS한 제품 중 어디까지 의심할지 뽑는 분석. 제품 상태는 바꾸지 않는다."""

from collections import Counter
import csv
from pathlib import Path


METHODS = ("window", "last_10", "last_20", "lot", "since_restart")
CONTAINMENT_COLUMNS = ("stop_key", "equipment", "method", "row_index", "seq", "product_id", "lot", "final_state")


def _passes(records):
    return [record for record in records if record.result == "PASS"]


def stop_scopes(analysis):
    """정지 순서대로 (stop_key, 정지, 방식, 최초 PASS 기록들)을 돌려준다."""
    products = analysis.process.products
    lot_tracking = analysis.process.equipment_book.lot_tracking
    numbers = Counter()
    scopes = []
    for stop in analysis.stop_history:
        numbers[stop.equipment] += 1
        # 허용된 같은 설비의 재가동만 구간을 나눈다.
        start = max((item.row_index for item in analysis.restarts
                     if item.equipment == stop.equipment and item.row_index < stop.row_index), default=0)
        records = [record for record in analysis.first_inspections
                   if record.equipment == stop.equipment and start < record.row_index <= stop.row_index]
        chosen = {
            "window": _passes(stop.window),
            "last_10": _passes(records[-10:]),
            "last_20": _passes(records[-20:]),
            "since_restart": _passes(records),
        }
        if lot_tracking:
            lots = {products[item.product_id].lot for item in stop.fail_causes}
            chosen["lot"] = [record for record in _passes(records) if products[record.product_id].lot in lots]
        key = stop.equipment + "#" + str(numbers[stop.equipment])
        scopes.extend((key, stop, method, chosen[method]) for method in METHODS if method in chosen)
    return scopes


def build_containment(analysis):
    products = analysis.process.products
    return [dict(zip(CONTAINMENT_COLUMNS, (
        key, stop.equipment, method, record.row_index, record.seq, record.product_id,
        products[record.product_id].lot, products[record.product_id].status,
    ))) for key, stop, method, records in stop_scopes(analysis) for record in records]


def run_scopes(analysis):
    """방식별로 한 실행의 모든 정지에서 고른 고유 제품 합집합. 정지가 없어도 적용 가능한 방식은 빈 집합으로 남긴다."""
    lot_tracking = analysis.process.equipment_book.lot_tracking
    methods = {method: set() for method in METHODS if lot_tracking or method != "lot"}
    for _, _, method, records in stop_scopes(analysis):
        methods[method].update(record.product_id for record in records)
    return methods


def write_containment(stem, rows):
    path = Path("reports") / (str(stem) + "_containment.csv")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=CONTAINMENT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def print_containment(rows, path):
    print("[격리 범위]")
    print("stop_key | method | product_count")
    for (key, method), count in Counter((row["stop_key"], row["method"]) for row in rows).items():
        print(key + " | " + method + " | " + str(count))
    print()
    print("저장 파일: " + path.as_posix())

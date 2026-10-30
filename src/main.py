"""CSV 입력, 터미널 출력과 CSV 보고서 저장."""

import argparse
import csv
import json
from pathlib import Path
from typing import Optional, Sequence

from .rules import INPUT_COLUMNS, RULE_IDS, Process


ROW_COLUMNS = ("seq", "product_id", "input", "rule_id", "decision", "rejection_reason", "state")
PRODUCT_COLUMNS = ("product_id", "state", "incomplete_reason")
REJECTION_COLUMNS = ("rule_id", "rejection_count")


def read_events(path: Path, columns=INPUT_COLUMNS):
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source, strict=True)
        if reader.fieldnames != list(columns):
            raise ValueError("CSV 헤더는 " + ",".join(columns) + " 이어야 함")
        return list(reader)


def build_reports(events):
    process = Process()
    rows = []
    counts = dict.fromkeys(RULE_IDS, 0)
    for event in events:
        decision = process.apply(event)
        rows.append(
            (
                decision.seq,
                decision.product_id,
                decision.input_text,
                decision.rule_id,
                "허용" if decision.accepted else "거절",
                decision.reason,
                decision.state,
            )
        )
        if not decision.accepted:
            counts[decision.rule_id] += 1
    products = [
        (product_id, product.status, product.incomplete_reason)
        for product_id, product in process.products.items()
    ]
    return rows, products, list(counts.items())


def write_reports(stem: str, reports, product_columns=PRODUCT_COLUMNS, *, equipment_mode=False, restart_mode=False):
    directory = Path("reports")
    directory.mkdir(exist_ok=True)
    paths = []
    suffixes = ("rows", "products", "rejections")
    report_columns = (ROW_COLUMNS, product_columns, REJECTION_COLUMNS)
    if equipment_mode:
        from .recipe_reports import EQUIPMENT_COLUMNS, RESTART_COLUMNS

        suffixes += ("equipment",)
        report_columns += (RESTART_COLUMNS if restart_mode else EQUIPMENT_COLUMNS,)
    for suffix, columns, rows in zip(
        suffixes,
        report_columns,
        reports,
    ):
        path = directory / (stem + "_" + suffix + ".csv")
        with path.open("w", encoding="utf-8-sig", newline="") as target:
            writer = csv.writer(target)
            writer.writerow(columns)
            writer.writerows(rows)
        paths.append(path)
    return paths


def print_reports(reports, paths, product_heading="product_id | 최종 상태 | 미완료 이유", *, equipment_mode=False,
                  restart_mode=False):
    sections = (
        ("행별 판정", "seq | product_id | 입력 | 적용 규칙 ID | 허용/거절 | 거절 이유 | 처리 후 상태"),
        ("제품별 최종 상태", product_heading),
        ("규칙 ID별 거절 건수", "규칙 ID | 거절 건수"),
    )
    if equipment_mode:
        heading = "equipment | inspection | counted_results | fail_count | state | stopped_at_seq"
        if restart_mode:
            heading += " | stop_count | restart_count | last_restart_result"
        sections += (("설비별 최종 상태", heading),)
    for (title, heading), rows in zip(sections, reports):
        print("[" + title + "]")
        print(heading)
        for row in rows:
            print(" | ".join(str(value) for value in row))
        print()
    print("저장 파일:")
    for path in paths:
        print(path.as_posix())


def run_recipe(input_csv: Path, recipe_path: Path, parser, equipment_path=None, *, summary=False, trace=(),
               containment=False) -> int:
    from .recipe import RecipeError, load_recipe
    from .recipe_reports import (
        LOT_COLUMN_INDEX, PRODUCT_COLUMNS as RECIPE_PRODUCT_COLUMNS, RETEST_PRODUCT_COLUMNS, build_recipe_reports,
    )
    from .recipe_rules import input_columns

    try:
        book = load_recipe(recipe_path)
    except RecipeError as error:
        parser.exit(3, "레시피 오류:\n" + "\n".join(error.errors) + "\n")
    if book.measured and equipment_path is None:
        parser.exit(2, "오류: 측정 레시피에는 --equipment가 필요함\n")
    equipment_book = None
    if equipment_path is not None:
        from .equipment import EquipmentError, load_equipment

        try:
            equipment_book = load_equipment(equipment_path, book.models)
        except EquipmentError as error:
            parser.exit(3, "설비 오류:\n" + "\n".join(error.errors) + "\n")
    print("레시피: " + recipe_path.as_posix() + " | SHA-256: " + book.sha256[:12])
    if equipment_book is not None:
        print("설비: " + equipment_path.as_posix() + " | SHA-256: " + equipment_book.sha256[:12])
    try:
        lot_mode = equipment_book is not None and equipment_book.lot_tracking
        events = read_events(input_csv, input_columns(equipment_book, book.measured))
        reports = build_recipe_reports(events, book.models, equipment_book)
        summary_rows = None
        traces = []
        if summary or trace or containment:
            from .summary import build_analysis

            analysis = build_analysis(events, book.models, equipment_book)
        if summary:
            from .reason_codes import injected_error_codes
            from .summary import build_summary

            meta_path = Path(str(input_csv) + ".meta.json")
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8-sig"))
                if not isinstance(meta, dict):
                    raise ValueError("meta.json은 객체여야 함")
                if type(meta.get("normal_rows")) is not int or meta["normal_rows"] < 0:
                    raise ValueError("meta.json의 normal_rows는 0 이상의 정수여야 함")
                injected = meta.get("injected_errors")
                if not isinstance(injected, dict) or any(
                        type(count) is not int or count < 0 for count in injected.values()):
                    raise ValueError("meta.json의 injected_errors는 값이 0 이상의 정수인 객체여야 함")
                if not set(injected) <= set(injected_error_codes(book.measured)):
                    raise ValueError("meta.json의 injected_errors 키는 주입 오류 5종 코드만 허용됨")
                if "defective_products" in meta:
                    defective = meta["defective_products"]
                    if not isinstance(defective, list) or any(
                            not isinstance(product_id, str) or not product_id.strip() for product_id in defective):
                        raise ValueError("meta.json의 defective_products는 비어 있지 않은 제품 ID 문자열 배열이어야 함")
                    if len(defective) != len(set(defective)):
                        raise ValueError("meta.json의 defective_products에는 중복 제품 ID를 허용하지 않음")
                if "leaked_products" in meta:
                    leaked = meta["leaked_products"]
                    if "defective_products" not in meta:
                        raise ValueError("meta.json의 leaked_products에는 defective_products가 필요함")
                    if not isinstance(leaked, list) or any(
                            not isinstance(product_id, str) or not product_id.strip() for product_id in leaked):
                        raise ValueError("meta.json의 leaked_products는 비어 있지 않은 제품 ID 문자열 배열이어야 함")
                    if len(leaked) != len(set(leaked)):
                        raise ValueError("meta.json의 leaked_products에는 중복 제품 ID를 허용하지 않음")
                    if not set(leaked) <= set(meta["defective_products"]):
                        raise ValueError("meta.json의 leaked_products는 defective_products의 부분집합이어야 함")
            except FileNotFoundError:
                meta = None
            summary_rows = build_summary(analysis, meta)
        if trace:
            from .trace import build_trace

            traces = [(product_id, build_trace(analysis, product_id)) for product_id in trace]
        columns = RETEST_PRODUCT_COLUMNS if book.retest_enabled else RECIPE_PRODUCT_COLUMNS
        if lot_mode:
            columns = columns[:LOT_COLUMN_INDEX] + ("lot",) + columns[LOT_COLUMN_INDEX:]
        restart_mode = equipment_book is not None and equipment_book.restart_enabled
        paths = write_reports(input_csv.stem, reports, columns, equipment_mode=equipment_book is not None,
                              restart_mode=restart_mode)
        if summary_rows is not None:
            from .summary import write_summary

            summary_path = write_summary(input_csv.stem, summary_rows)
        containment_rows = None
        if containment:
            from .containment import build_containment, write_containment

            containment_rows = build_containment(analysis)
            containment_path = write_containment(input_csv.stem, containment_rows)
        trace_paths = []
        if traces:
            from .trace import write_trace

            product_ids = {decision.product_id for decision in analysis.decisions if decision.product_id}
            trace_paths = [write_trace(input_csv.stem, product_id, rows, product_ids) for product_id, rows in traces]
    except (OSError, UnicodeError, csv.Error, ValueError) as error:
        parser.exit(2, "오류: " + str(error) + "\n")
    heading = "product_id | model | lot | 최종 상태 | 미완료 이유" if lot_mode else "product_id | model | 최종 상태 | 미완료 이유"
    if book.retest_enabled:
        heading += " | history"
    print_reports(reports, paths, heading, equipment_mode=equipment_book is not None, restart_mode=restart_mode)
    if summary_rows is not None:
        from .summary import print_summary

        print_summary(summary_rows, summary_path)
    if traces:
        from .trace import print_trace

        for (_, rows), path in zip(traces, trace_paths):
            print_trace(rows, path)
    if containment_rows is not None:
        from .containment import print_containment

        print_containment(containment_rows, containment_path)
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="교육용 가상 조립·검사 공정의 진행 조건 판정기")
    parser.add_argument("input_csv", type=Path, help="seq,product_id,event,inspection,result CSV")
    parser.add_argument("--recipe", type=Path, help="v2 모델별 선형 공정 레시피 JSON (CSV에 model 열 추가)")
    parser.add_argument("--equipment", type=Path, help="검사 설비·정지 규칙 JSON (--recipe 필수)")
    parser.add_argument("--summary", action="store_true", help="설비 모드의 지표·파레토 분석 보고서")
    parser.add_argument("--trace", action="append", default=[], metavar="제품ID", help="설비 모드의 제품 추적 (반복 가능)")
    parser.add_argument("--containment", action="store_true", help="설비 모드의 정지별 격리 범위 보고서")
    args = parser.parse_args(argv)
    if args.equipment is not None and args.recipe is None:
        parser.error("--equipment는 --recipe와 함께만 사용 가능")
    if (args.summary or args.trace) and args.equipment is None:
        parser.error("--summary와 --trace는 설비 모드에서만 사용 가능")
    if args.containment and args.equipment is None:
        parser.error("--containment는 설비 모드에서만 사용 가능")
    if args.recipe is not None:
        return run_recipe(args.input_csv, args.recipe, parser, args.equipment, summary=args.summary, trace=args.trace,
                          containment=args.containment)
    try:
        reports = build_reports(read_events(args.input_csv))
        paths = write_reports(args.input_csv.stem, reports)
    except (OSError, UnicodeError, csv.Error, ValueError) as error:
        parser.exit(2, "오류: " + str(error) + "\n")
    print_reports(reports, paths)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

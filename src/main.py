"""CSV 입력, 터미널 출력과 CSV 보고서 저장."""

import argparse
import csv
from pathlib import Path
from typing import Optional, Sequence

from .rules import INPUT_COLUMNS, RULE_IDS, Process


ROW_COLUMNS = ("seq", "product_id", "input", "rule_id", "decision", "rejection_reason", "state")
PRODUCT_COLUMNS = ("product_id", "state", "incomplete_reason")
REJECTION_COLUMNS = ("rule_id", "rejection_count")


def read_events(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source, strict=True)
        if reader.fieldnames != list(INPUT_COLUMNS):
            raise ValueError("CSV 헤더는 " + ",".join(INPUT_COLUMNS) + " 이어야 함")
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


def write_reports(stem: str, reports):
    directory = Path("reports")
    directory.mkdir(exist_ok=True)
    paths = []
    for suffix, columns, rows in zip(
        ("rows", "products", "rejections"),
        (ROW_COLUMNS, PRODUCT_COLUMNS, REJECTION_COLUMNS),
        reports,
    ):
        path = directory / (stem + "_" + suffix + ".csv")
        with path.open("w", encoding="utf-8-sig", newline="") as target:
            writer = csv.writer(target)
            writer.writerow(columns)
            writer.writerows(rows)
        paths.append(path)
    return paths


def print_reports(reports, paths):
    sections = (
        ("행별 판정", "seq | product_id | 입력 | 적용 규칙 ID | 허용/거절 | 거절 이유 | 처리 후 상태"),
        ("제품별 최종 상태", "product_id | 최종 상태 | 미완료 이유"),
        ("규칙 ID별 거절 건수", "규칙 ID | 거절 건수"),
    )
    for (title, heading), rows in zip(sections, reports):
        print("[" + title + "]")
        print(heading)
        for row in rows:
            print(" | ".join(str(value) for value in row))
        print()
    print("저장 파일:")
    for path in paths:
        print(path.as_posix())


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="교육용 가상 조립·검사 공정의 진행 조건 판정기")
    parser.add_argument("input_csv", type=Path, help="seq,product_id,event,inspection,result CSV")
    args = parser.parse_args(argv)
    try:
        reports = build_reports(read_events(args.input_csv))
        paths = write_reports(args.input_csv.stem, reports)
    except (OSError, UnicodeError, csv.Error, ValueError) as error:
        parser.exit(2, "오류: " + str(error) + "\n")
    print_reports(reports, paths)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

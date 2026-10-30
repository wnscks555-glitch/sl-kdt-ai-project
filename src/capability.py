"""설비별 최초 측정의 Cpk·Ppk 계산과 보고서."""

import csv
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP, localcontext
from pathlib import Path
from typing import Optional

from .summary import ASSUMPTION_NOTICE


SUBGROUP_SIZE = 5
D2 = Decimal("2.326")
MIN_SUBGROUPS = 25
MIN_CPK_SUBGROUPS = 2
PRECISION = 100
LOW_SAMPLE = "표본 부족"
NO_VARIATION = "변동 없음"
COMPUTED = "계산됨"
CAPABILITY_NOTICE = ASSUMPTION_NOTICE + " 구간을 합친 값이며 안정 공정의 능력을 보증하지 않는다."
CAPABILITY_COLUMNS = (
    "section", "inspection", "equipment", "unit", "lsl", "usl", "n", "subgroups", "xbarbar", "rbar",
    "sigma_within", "cpk", "sample_sd", "ppk", "status", "value",
)


@dataclass(frozen=True)
class Capability:
    n: int
    subgroups: int
    xbarbar: Optional[Decimal]
    rbar: Optional[Decimal]
    sigma_within: Optional[Decimal]
    cpk: Optional[Decimal]
    sample_sd: Optional[Decimal]
    ppk: Optional[Decimal]


def _margin(center, lsl, usl):
    """가까운 규격까지의 부호 있는 거리다. 단측이면 있는 쪽만 본다."""
    sides = []
    if usl is not None:
        sides.append(usl - center)
    if lsl is not None:
        sides.append(center - lsl)
    return min(sides)


def capability(segments, lsl, usl):
    """구간별 측정값을 받는다. 계산할 수 없는 항목은 None이고 표본 기준은 여기서 보지 않는다."""
    lsl = None if lsl is None else Decimal(lsl)
    usl = None if usl is None else Decimal(usl)
    with localcontext() as context:
        context.prec = PRECISION
        values = [Decimal(value) for segment in segments for value in segment]
        groups = []
        for segment in segments:
            whole = len(segment) - len(segment) % SUBGROUP_SIZE
            groups += [[Decimal(value) for value in segment[index:index + SUBGROUP_SIZE]]
                       for index in range(0, whole, SUBGROUP_SIZE)]
        xbarbar = rbar = sigma_within = cpk = sample_sd = ppk = None
        if groups:
            xbarbar = sum(sum(group) / len(group) for group in groups) / len(groups)
            rbar = sum(max(group) - min(group) for group in groups) / len(groups)
            sigma_within = rbar / D2
        if len(groups) >= MIN_CPK_SUBGROUPS and sigma_within > 0:
            cpk = _margin(xbarbar, lsl, usl) / (3 * sigma_within)
        if len(values) >= 2:
            mean = sum(values) / len(values)
            sample_sd = (sum((value - mean) ** 2 for value in values) / (len(values) - 1)).sqrt()
            if sample_sd > 0:
                ppk = _margin(mean, lsl, usl) / (3 * sample_sd)
    return Capability(len(values), len(groups), xbarbar, rbar, sigma_within, cpk, sample_sd, ppk)


def show(value):
    """계산값을 보고 문자열로 바꾼다. None은 빈칸이고 음수 영은 쓰지 않는다."""
    if value is None:
        return ""
    with localcontext() as context:
        context.prec = PRECISION
        rounded = value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        return "0.0000" if rounded == 0 else format(rounded, "f")


def status_of(result):
    if result.subgroups < MIN_SUBGROUPS:
        return LOW_SAMPLE
    if result.sigma_within == 0 or not result.sample_sd:
        return NO_VARIATION
    return COMPUTED


def equipment_segments(analysis, equipment):
    """허용된 재가동에서 물리적 행 순서를 끊는다. 재검사와 거절 행은 넣지 않는다."""
    cuts = [restart.row_index for restart in analysis.restarts if restart.equipment == equipment]
    segments = [[] for _ in range(len(cuts) + 1)]
    for record in analysis.first_inspections:
        if record.equipment == equipment:
            segments[sum(cut < record.row_index for cut in cuts)].append(record.value)
    return segments


def _row(section, **fields):
    return {column: fields.get(column, section if column == "section" else "") for column in CAPABILITY_COLUMNS}


def build_capability(analysis):
    process = analysis.process
    specs = {item.id: item for model in process.models.values() for item in model.inspections}
    book = process.equipment_book
    rows = [_row("notice", value=CAPABILITY_NOTICE)]
    for equipment, inspection in sorted(book.equipment.items(), key=lambda pair: (pair[1], pair[0])):
        item = specs[inspection]
        result = capability(equipment_segments(analysis, equipment), item.lsl, item.usl)
        status = status_of(result)
        hidden = status == LOW_SAMPLE
        rows.append(_row(
            "capability", inspection=inspection, equipment=equipment, unit=item.unit, lsl=item.lsl or "",
            usl=item.usl or "", n=result.n, subgroups=result.subgroups, xbarbar=show(result.xbarbar),
            rbar=show(result.rbar), sigma_within=show(result.sigma_within), cpk="" if hidden else show(result.cpk),
            sample_sd=show(result.sample_sd), ppk="" if hidden else show(result.ppk), status=status,
        ))
    return rows


def write_capability(stem, rows):
    path = Path("reports") / (str(stem) + "_capability.csv")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=CAPABILITY_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def print_capability(rows, path):
    print("[공정능력]")
    print(rows[0]["value"])
    print("inspection | equipment | n | subgroups | cpk | ppk | status")
    for row in rows[1:]:
        print(" | ".join(str(row[column]) for column in
                         ("inspection", "equipment", "n", "subgroups", "cpk", "ppk", "status")))
    print()
    print("저장 파일: " + path.as_posix())

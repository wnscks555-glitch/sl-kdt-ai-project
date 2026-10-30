"""합성 공정 PFMEA 연습표를 검증하고 판정 규칙·테스트·평가 수치에 잇는다."""

import argparse
import ast
import csv
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction
import hashlib
from pathlib import Path
import re

from .evaluate import parse_seeds
from .generate import Generator, generator_version, load_setup
from .reason_codes import REASON_CODES
from .recipe_rules import RULE_IDS
from .summary import ASSUMPTION_NOTICE, build_analysis


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "recipes/generator_measured.json"
INPUT_COLUMNS = (
    "id", "failure_type", "process_step", "function_requirement", "failure_mode", "effect", "cause",
    "prevention_control", "detection_control", "severity", "occurrence", "detection", "evidence", "evidence_note",
    "action", "action_owner", "action_state", "action_goal", "control_before", "control_after", "success_reference",
    "success_op", "success_value", "action_evidence", "residual_risk", "post_severity", "post_occurrence",
    "post_detection",
)
REPORT_COLUMNS = ("section",) + INPUT_COLUMNS + (
    "score_status", "rpn", "post_rpn", "priority", "rpn_change", "evidence_status", "effect_result", "reference",
    "condition", "target", "scope", "numerator", "denominator", "value", "generator_version", "config_sha256",
    "recipe_sha256", "equipment_sha256", "seeds", "products", "assumption", "text",
)
FAILURE_TYPES = ("product", "equipment", "record")
TEXT_COLUMNS = ("function_requirement", "failure_mode", "effect", "cause", "prevention_control", "detection_control")
SCORE_COLUMNS = ("severity", "occurrence", "detection")
POST_COLUMNS = ("post_severity", "post_occurrence", "post_detection")
SUCCESS_COLUMNS = ("success_reference", "success_op", "success_value")
SCORE_PATTERN = r"10|[1-9]"
# 조치 상태별 열 묶음의 허용 조합이다. blank, required, together만 쓴다.
ACTION_RULES = {
    "": dict(core="blank", control="blank", success="blank", evidence="blank", residual="blank", post="blank"),
    "계획": dict(core="required", control="blank", success="together", evidence="blank", residual="blank", post="blank"),
    "완료": dict(core="required", control="required", success="blank", evidence="required", residual="blank",
                 post="blank"),
    "효과 확인": dict(core="required", control="required", success="required", evidence="required",
                      residual="required", post="together"),
}
ACTION_GROUPS = dict(
    core=("action", "action_owner", "action_goal"), control=("control_before", "control_after"),
    success=SUCCESS_COLUMNS, evidence=("action_evidence",), residual=("residual_risk",), post=POST_COLUMNS,
)
REPORT_VALUE_COLUMNS = ("capture_rate", "mean_quarantine", "precision", "mean_residual")
REQUIRED_PROVENANCE = ("generator_version", "seeds", "products", "config_sha256")
COMPLETED = "레시피 모의 흐름 완료"
OVERALL = "전체 흐름 참고값"
METRIC_ASSUMPTION = "7a 측정 설정"
REPORT_ASSUMPTION = "이전 단계 가정, 7a 결과 아님"
PRACTICE_NOTICE = "합성 공정의 PFMEA 연습이며 실제 공정, 고객 영향, 실무 PFMEA가 아니다."
METRIC_NOTICE = "최초 FAIL률은 원인 발생률이 아니고, 설비 정지율은 제품 불량 검출률이 아니다."
LINK_NOTICE = ("연결됨은 참조가 이어졌다는 뜻이고 관리 효과의 검증이 아니다. 효과 판정은 현재 관리의 성능 확인이며 "
               "개선 전후 비교가 아니다. 합성 수치는 참고 관측치이고 점수 환산표가 아니다.")
ALTERNATIVES = (("current", None), ("half", 0.35), ("none", 0.0))
ALTERNATIVE_METRICS = ("defect_escape", "leak_defect_retest_pass", "normal_reject", "all_defect_first_fail")


@dataclass(frozen=True)
class Metric:
    target: str
    scope: str
    overall: bool = False


METRICS = {
    "defect_escape": Metric("product", "전체 흐름, 실행 끝 상태", True),
    "all_defect_first_fail": Metric("product", "모든 검사", True),
    "leak_defect_first_fail": Metric("product", "LEAK"),
    "leak_defect_retest_pass": Metric("product", "LEAK"),
    "normal_reject": Metric("product", "전체 흐름, 실행 끝 상태", True),
    "fault_stop_run": Metric("equipment", "고장 설비"),
    "fault_no_stop_run": Metric("equipment", "고장 설비"),
    "fault_stop_delay": Metric("equipment", "고장 설비, 첫 정지까지"),
    "normal_stop_rate": Metric("equipment", "고장 키에 없는 모든 설비, 실행 전체", True),
}


class PfmeaError(ValueError):
    def __init__(self, errors):
        self.errors = tuple(errors)
        super().__init__("\n".join(self.errors))


@dataclass(frozen=True)
class Reference:
    text: str
    kind: str
    target: str
    report: tuple = ()


def _report_reference(text, value, root):
    parts = value.split(":")
    if len(parts) != 3 or re.fullmatch(r"[A-Za-z0-9_]+", parts[0]) is None:
        raise ValueError("report 참조는 파일:방식:열 형식이어야 함: " + text)
    name, method, column = parts
    path = Path(root) / "reports" / (name + ".csv")
    if column not in REPORT_VALUE_COLUMNS:
        raise ValueError("허용하지 않은 보고서 열: " + text)
    if not path.is_file():
        raise ValueError("없는 보고서: " + text)
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    matches = [row for row in rows if row.get("section") == "method" and row.get("method") == method]
    if len(matches) != 1:
        raise ValueError("보고서의 방식 행이 정확히 하나가 아님: " + text)
    number = matches[0].get(column, "")
    if number and re.fullmatch(r"-?[0-9]+(\.[0-9]+)?", number) is None:
        raise ValueError("보고서 값이 소수 형식이 아님: " + text)
    provenance = {row.get("method"): row.get("value", "") for row in rows if row.get("section") == "provenance"}
    if any(not provenance.get(key) for key in REQUIRED_PROVENANCE):
        raise ValueError("보고서에 출처가 없음: " + text)
    selection = next((row.get("value", "") for row in rows if row.get("section") == "selection"), "")
    return number, provenance, selection


def _check_test(text, value, root):
    parts = value.split("::")
    if len(parts) != 3 or re.fullmatch(r"tests/[A-Za-z0-9_]+\.py", parts[0]) is None:
        raise ValueError("test 참조는 tests/파일.py::클래스::메서드 형식이어야 함: " + text)
    path = Path(root) / parts[0]
    if not path.is_file():
        raise ValueError("없는 테스트 파일: " + text)
    try:
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    except SyntaxError as error:
        raise ValueError("테스트 파일 구문 오류: " + text) from error
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == parts[1]:
            if any(isinstance(item, ast.FunctionDef) and item.name == parts[2] for item in node.body):
                return
    raise ValueError("없는 테스트 메서드: " + text)


def resolve_reference(text, root=ROOT):
    """참조 하나를 확인한다. 값은 report만 여기서 읽고 metric은 실행 뒤에 채운다."""
    if text != text.strip() or not text:
        raise ValueError("참조에 빈 조각이나 앞뒤 공백이 있음: " + repr(text))
    kind, separator, value = text.partition(":")
    if not separator or kind not in ("rule", "reason", "test", "metric", "report"):
        raise ValueError("알 수 없는 근거 종류: " + text)
    if kind == "rule":
        if value not in RULE_IDS + ("RULE_RETEST", "RULE_EQUIP"):
            raise ValueError("없는 규칙: " + text)
    elif kind == "reason":
        if value not in REASON_CODES:
            raise ValueError("없는 사유 코드: " + text)
    elif kind == "test":
        _check_test(text, value, root)
    elif kind == "metric":
        if value not in METRICS:
            raise ValueError("없는 지표: " + text)
        return Reference(text, kind, METRICS[value].target)
    else:
        return Reference(text, kind, "product", _report_reference(text, value, root))
    return Reference(text, kind, "record")


def _references(cell, location, errors, root):
    if not cell:
        return []
    found = []
    pieces = cell.split(";")
    if len(set(pieces)) != len(pieces):
        errors.append(location + ": 같은 칸에 중복 참조")
    for piece in pieces:
        try:
            found.append(resolve_reference(piece, root))
        except ValueError as error:
            errors.append(location + ": " + str(error))
    return found


def _check_group(row, index, group, mode, errors):
    columns = ACTION_GROUPS[group]
    filled = [bool(row[column].strip()) for column in columns]
    for column, present in zip(columns, filled):
        location = str(index) + "." + column
        if mode == "blank" and row[column]:
            errors.append(location + ": 이 조치 상태에서는 빈칸이어야 함")
        if mode == "required" and not present:
            errors.append(location + ": 이 조치 상태에서는 필수")
    if mode == "together" and any(filled) and not all(filled):
        errors.append(str(index) + "." + columns[0] + ": " + ", ".join(columns) + "은 함께 있어야 함")


def check_table(rows, models, root=ROOT):
    """표 전체를 검사해 행별 현재 관리·기준 참조를 돌려준다. 문제는 모아서 한 번에 보고한다."""
    steps = {"ALL"} | {step for model in models.values() for step in model.steps}
    steps |= {item.id for model in models.values() for item in model.inspections}
    errors, seen, references = [], [], {}
    for index, row in enumerate(rows, 1):
        if any(row.get(column) is None for column in INPUT_COLUMNS) or None in row:
            errors.append(str(index) + ": 열 수가 맞지 않음")
            continue
        at = lambda column: str(index) + "." + column
        identifier = row["id"]
        if re.fullmatch(r"PF-[0-9]{2}", identifier) is None:
            errors.append(at("id") + ": 형식은 PF-00이어야 함")
        if identifier in seen:
            errors.append(at("id") + ": 중복 " + identifier)
        elif seen and identifier < seen[-1]:
            errors.append(at("id") + ": id 오름차순이어야 함")
        seen.append(identifier)
        if row["failure_type"] not in FAILURE_TYPES:
            errors.append(at("failure_type") + ": " + ", ".join(FAILURE_TYPES) + " 중 하나여야 함")
        if row["process_step"] not in steps:
            errors.append(at("process_step") + ": 레시피에 없는 공정 또는 검사")
        for column in TEXT_COLUMNS:
            if not row[column].strip():
                errors.append(at(column) + ": 비어 있을 수 없음")
        for columns in (SCORE_COLUMNS, POST_COLUMNS):
            for column in columns:
                if row[column] and re.fullmatch(SCORE_PATTERN, row[column]) is None:
                    errors.append(at(column) + ": 1–10 정수여야 함")
            if any(row[column] for column in columns) and not all(row[column] for column in columns):
                errors.append(at(columns[0]) + ": 점수 3개는 함께 있어야 함")
        if row["post_severity"] and not row["severity"]:
            errors.append(at("post_severity") + ": 조치 전 점수가 필요함")
        if row["evidence"] and not row["evidence_note"].strip():
            errors.append(at("evidence_note") + ": 근거가 있으면 필수")
        state = row["action_state"]
        if state not in ACTION_RULES:
            errors.append(at("action_state") + ": 계획, 완료, 효과 확인 또는 빈칸이어야 함")
            continue
        for group, mode in ACTION_RULES[state].items():
            _check_group(row, index, group, mode, errors)
        current = _references(row["evidence"], at("evidence"), errors, root)
        _references(row["action_evidence"], at("action_evidence"), errors, root)
        success = None
        if row["success_reference"]:
            found = _references(row["success_reference"], at("success_reference"), errors, root)
            if found and (len(found) != 1 or found[0].kind not in ("metric", "report")):
                errors.append(at("success_reference") + ": metric 또는 report 참조 1개여야 함")
            elif found:
                success = found[0]
        if row["success_op"] and row["success_op"] not in (">=", "<="):
            errors.append(at("success_op") + ": >= 또는 <=여야 함")
        if row["success_value"] and re.fullmatch(r"-?[0-9]+(\.[0-9]+)?", row["success_value"]) is None:
            errors.append(at("success_value") + ": 소수 형식이어야 함")
        references[identifier] = current, success
    if errors:
        raise PfmeaError(errors)
    return references


def read_table(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source, strict=True)
        if reader.fieldnames != list(INPUT_COLUMNS):
            raise PfmeaError(["0: 헤더는 " + ",".join(INPUT_COLUMNS) + " 이어야 함"])
        return list(reader)


def run_counts(analysis, defective, faulty):
    """한 실행의 원시 분자·분모다. 합산은 merge_counts가 한다."""
    products = analysis.process.products
    defective = set(defective)
    first, every = analysis.first_inspections, analysis.all_inspections
    bad = [product_id for product_id in products if product_id in defective]
    normal = [product_id for product_id in products if product_id not in defective]
    defect_first = [record for record in first if record.product_id in defective]
    leak_first = [record for record in defect_first if record.inspection == "LEAK"]
    retested = {record.product_id for record in every if record.product_id in defective
                and record.inspection == "LEAK" and record.retest_number > 0}
    counts = {
        "defect_escape": (sum(products[item].status == COMPLETED for item in bad), len(bad)),
        "all_defect_first_fail": (sum(record.result == "FAIL" for record in defect_first), len(defect_first)),
        "leak_defect_first_fail": (sum(record.result == "FAIL" for record in leak_first), len(leak_first)),
        "leak_defect_retest_pass": (sum(products[item].inspections.get("LEAK") == "PASS" for item in retested),
                                    len(retested)),
        "normal_reject": (sum(products[item].status in ("보류", "폐기") for item in normal), len(normal)),
    }
    stopped_pairs, delay = 0, 0
    detail = {}
    for name in faulty:
        stops = [stop for stop in analysis.stop_history if stop.equipment == name]
        stopped_pairs += bool(stops)
        detail[name] = (int(bool(stops)), 1)
        if stops:
            delay += sum(record.equipment == name and record.row_index <= stops[0].row_index for record in first)
    pairs = len(faulty)
    healthy_stops = sum(stop.equipment not in faulty for stop in analysis.stop_history)
    healthy_first = sum(record.equipment not in faulty for record in first)
    counts.update(
        fault_stop_run=(stopped_pairs, pairs), fault_no_stop_run=(pairs - stopped_pairs, pairs),
        fault_stop_delay=(delay, stopped_pairs), normal_stop_rate=(healthy_stops, healthy_first),
    )
    return counts, detail


def merge_counts(runs):
    """실행별 원시 값을 더한다. 실행별 비율을 평균하지 않는다."""
    total = {name: (0, 0) for name in METRICS}
    detail = {}
    for counts, equipment in runs:
        for name, (numerator, denominator) in counts.items():
            total[name] = (total[name][0] + numerator, total[name][1] + denominator)
        for name, (numerator, denominator) in equipment.items():
            old = detail.get(name, (0, 0))
            detail[name] = (old[0] + numerator, old[1] + denominator)
    return total, detail


def collect(config, recipe, book, seeds, products):
    runs = []
    for seed in seeds:
        generator = Generator(seed, config, recipe.models, book)
        normal = generator.normal_events(products)
        analysis = build_analysis(normal, recipe.models, book)
        runs.append(run_counts(analysis, generator.defective_products, sorted(config["fault_shift_sigma"])))
    return merge_counts(runs)


def show_ratio(numerator, denominator):
    if not denominator:
        return ""
    value = Decimal(numerator) / Decimal(denominator)
    return format(value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP), ".4f")


def reference_value(reference, metrics):
    """비교에 쓸 정확한 값이다. 표시용으로 반올림하지 않는다. 없으면 None이다."""
    if reference.kind == "report":
        return Fraction(reference.report[0]) if reference.report[0] else None
    if reference.kind != "metric":
        return None
    numerator, denominator = metrics[reference.text.partition(":")[2]]
    return Fraction(numerator, denominator) if denominator else None


def effect_result(value, operator, limit):
    if value is None:
        return "값 없음"
    limit = Fraction(limit)
    return "충족" if (value >= limit if operator == ">=" else value <= limit) else "미충족"


def evidence_status(failure_type, references, metrics):
    if not references:
        return "근거 없음"
    matching = [reference for reference in references if reference.target == failure_type]
    if not matching:
        return "근거 부족"
    if all(reference.kind in ("metric", "report") and reference_value(reference, metrics) is None
           for reference in matching):
        return "값 없음"
    return "연결됨"


def rpn(row, columns):
    return int(row[columns[0]]) * int(row[columns[1]]) * int(row[columns[2]]) if row[columns[0]] else None


def scored_fields(row):
    before, after = rpn(row, SCORE_COLUMNS), rpn(row, POST_COLUMNS)
    return dict(
        score_status="점수 대기" if before is None else "점수 입력",
        rpn="" if before is None else before,
        post_rpn="" if after is None else after,
        priority="우선" if row["severity"] and int(row["severity"]) >= 9 else "",
        rpn_change="" if after is None else after - before,
    )


def _row(section, **fields):
    return {column: fields.get(column, section if column == "section" else "") for column in REPORT_COLUMNS}


def _reference_fields(reference, metrics, source):
    if reference.kind == "metric":
        name = reference.text.partition(":")[2]
        numerator, denominator = metrics[name]
        return dict(reference=reference.text, target=reference.target, scope=METRICS[name].scope, numerator=numerator,
                    denominator=denominator, value=show_ratio(numerator, denominator), assumption=METRIC_ASSUMPTION,
                    text=OVERALL if METRICS[name].overall else "", **source)
    if reference.kind == "report":
        number, provenance, selection = reference.report
        return dict(reference=reference.text, target=reference.target, value=number, assumption=REPORT_ASSUMPTION,
                    generator_version=provenance["generator_version"], config_sha256=provenance["config_sha256"],
                    recipe_sha256=provenance.get("recipe_sha256", ""),
                    equipment_sha256=provenance.get("equipment_sha256", ""), seeds=provenance["seeds"],
                    products=provenance["products"], text=selection)
    return dict(reference=reference.text, target=reference.target)


def build_report(rows, references, metrics, detail, alternatives, source):
    report = [_row("notice", text=text) for text in
              (PRACTICE_NOTICE, ASSUMPTION_NOTICE, METRIC_NOTICE, LINK_NOTICE)]
    statuses = {}
    for row in rows:
        current, success = references[row["id"]]
        status = evidence_status(row["failure_type"], current, metrics)
        statuses[row["id"]] = status
        result = ""
        if row["action_state"] == "효과 확인":
            result = effect_result(reference_value(success, metrics), row["success_op"], row["success_value"])
        report.append(_row("item", evidence_status=status, effect_result=result, **scored_fields(row),
                           **{column: row[column] for column in INPUT_COLUMNS}))
    for row in rows:
        for reference in references[row["id"]][0]:
            report.append(_row("evidence", id=row["id"], **_reference_fields(reference, metrics, source)))
    for row in rows:
        if row["action_state"] == "효과 확인":
            success = references[row["id"]][1]
            fields = _reference_fields(success, metrics, source)
            fields["text"] = " ".join(filter(None, (row["success_op"] + " " + row["success_value"], fields["text"])))
            report.append(_row("action", id=row["id"], effect_result=effect_result(
                reference_value(success, metrics), row["success_op"], row["success_value"]), **fields))
    for name in METRICS:
        report.append(_row("metric", **_reference_fields(Reference("metric:" + name, "metric", METRICS[name].target),
                                                         metrics, source)))
    for name, (numerator, denominator) in sorted(detail.items()):
        report.append(_row("fault_detail", reference=name, target="equipment", numerator=numerator,
                           denominator=denominator, value=show_ratio(numerator, denominator), **source))
    for condition, counts in alternatives:
        for name in ALTERNATIVE_METRICS:
            numerator, denominator = counts[name]
            report.append(_row("alternative", condition=condition, reference=name, target=METRICS[name].target,
                               scope=METRICS[name].scope, numerator=numerator, denominator=denominator,
                               value=show_ratio(numerator, denominator), assumption=METRIC_ASSUMPTION, **source))
    for failure_type in FAILURE_TYPES:
        for status in ("연결됨", "값 없음", "근거 부족", "근거 없음"):
            count = sum(row["failure_type"] == failure_type and statuses[row["id"]] == status for row in rows)
            report.append(_row("coverage", failure_type=failure_type, evidence_status=status, value=count))
    return report


def _cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ") if value != "" else "-"


def _table(lines, heading, columns, rows):
    lines.extend(("", "## " + heading, "", "| " + " | ".join(columns) + " |", "|" + " --- |" * len(columns)))
    lines.extend("| " + " | ".join(_cell(value) for value in row) + " |" for row in rows)


def build_markdown(report):
    lines = ["# 합성 공정 PFMEA 연습", "", PRACTICE_NOTICE, "", ASSUMPTION_NOTICE, "", METRIC_NOTICE, "", LINK_NOTICE]
    items = [row for row in report if row["section"] == "item"]
    for item in items:
        lines.extend(("", "## " + item["id"] + " " + item["failure_mode"], ""))
        for label, column in (("유형", "failure_type"), ("대상", "process_step"), ("기능", "function_requirement"),
                              ("영향(가정)", "effect"), ("원인(가정)", "cause"), ("예방 관리", "prevention_control"),
                              ("검출 관리", "detection_control"), ("점수", "score_status"), ("근거 상태", "evidence_status"),
                              ("근거 설명", "evidence_note"), ("조치", "action"), ("조치 상태", "action_state"),
                              ("조치 목적", "action_goal"), ("조치 전 관리", "control_before"),
                              ("조치 후 관리", "control_after"), ("잔여 위험", "residual_risk")):
            lines.append("- " + label + ": " + _cell(item[column]))
        if item["success_reference"]:
            lines.append("- 사전 기준: " + " ".join(item[column] for column in SUCCESS_COLUMNS))
        if item["effect_result"]:
            lines.append("- 효과 판정: " + item["effect_result"])
    _table(lines, "지표", ("지표", "범위", "분자", "분모", "값"),
           [(row["reference"], row["scope"], row["numerator"], row["denominator"], row["value"])
            for row in report if row["section"] == "metric"])
    _table(lines, "재검사 대안 비교 (합산 비교, 제품 짝 비교 아님)", ("조건", "지표", "분자", "분모", "값"),
           [(row["condition"], row["reference"], row["numerator"], row["denominator"], row["value"])
            for row in report if row["section"] == "alternative"])
    return "\n".join(lines) + "\n"


def write_outputs(stem, report):
    directory = Path("reports")
    directory.mkdir(exist_ok=True)
    csv_path = directory / (stem + "_report.csv")
    with csv_path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=REPORT_COLUMNS)
        writer.writeheader()
        writer.writerows(report)
    markdown_path = directory / (stem + "_report.md")
    with markdown_path.open("w", encoding="utf-8", newline="\n") as target:
        target.write(build_markdown(report))
    return csv_path, markdown_path


def run(table_path, config_path, seed_text, products, root=ROOT):
    if products < 1:
        raise ValueError("products는 양의 정수여야 함")
    seeds = parse_seeds(seed_text)
    config, content, recipe, book = load_setup(config_path)
    if "process_cpk" not in config:
        raise ValueError("--config는 측정 설정이어야 함")
    rows = read_table(table_path)
    references = check_table(rows, recipe.models, root)
    source = dict(generator_version=generator_version(config), config_sha256=hashlib.sha256(content).hexdigest(),
                  recipe_sha256=recipe.sha256, equipment_sha256=book.sha256, seeds=seed_text, products=products)
    alternatives = []
    metrics, detail = None, None
    for condition, probability in ALTERNATIVES:
        changed = config if probability is None else dict(config, retest_probability=probability)
        counts, equipment = collect(changed, recipe, book, seeds, products)
        if probability is None:
            metrics, detail = counts, equipment
        alternatives.append((condition, counts))
    return build_report(rows, references, metrics, detail, alternatives, source)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("table", type=Path)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--seeds", required=True, help="시작-끝, 예: 0-29")
    parser.add_argument("--products", type=int, default=500)
    args = parser.parse_args(argv)
    try:
        report = run(args.table, args.config, args.seeds, args.products)
        csv_path, markdown_path = write_outputs(args.table.stem, report)
    except PfmeaError as error:
        parser.exit(3, "PFMEA 표 오류:\n" + "\n".join(error.errors) + "\n")
    except (OSError, UnicodeError, csv.Error, ValueError, KeyError) as error:
        parser.exit(2, "오류: " + str(error) + "\n")
    print(PRACTICE_NOTICE)
    print("id | 유형 | 점수 | 근거 | 효과 판정")
    for row in report:
        if row["section"] == "item":
            print(" | ".join((row["id"], row["failure_type"], row["score_status"], row["evidence_status"],
                              row["effect_result"])))
    print("저장 파일: " + csv_path.as_posix() + ", " + markdown_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

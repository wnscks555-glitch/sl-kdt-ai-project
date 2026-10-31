"""이미 나온 보고서를 읽어 합성 결과 대시보드 HTML 하나를 만든다. 실시간 모니터링 시스템이 아니다."""

import argparse
import csv
import html
import json
import math
import os
from pathlib import Path
import re
import tempfile
import xml.etree.ElementTree as ElementTree


NOTICE = "모든 값은 합성 데이터와 소프트웨어 모의 결과입니다. 실제 설비, 실제 라인, SL 기준이 아닙니다."
TITLE = "공정 판정기 합성 결과 대시보드"
MAX_BYTES = 5 * 1024 * 1024
SCENARIOS = ("normal", "seat_ng", "clamp_stuck", "judge_lost", "pc_silent", "disconnect", "guard_open", "stale_judge")
STATES = ("IDLE", "CHECK", "CLAMP", "MEASURE", "PUBLISH", "WAIT_JUDGE", "UNCLAMP", "DISCHARGE", "ALARM")
OUTPUTS = ("clamp_cmd", "measure_cmd", "gate_ok", "gate_ng", "alarm_lamp")
TABS = (("overview", "개요"), ("measure", "측정"), ("msa", "측정 시스템"), ("detect", "이상 검출"), ("pfmea", "PFMEA"),
        ("line", "라인"), ("plc", "PLC"), ("incident", "사건"))
METRICS = ("detection_rate", "early", "missed", "mean_delay_cost", "false_per_1000")
PLC_COLUMNS = ("cycle", "state", "alarm", "outputs", "processed", "events", "value")
INPUTS = {
    "gen_measured_seed42_capability.csv": ("section", "inspection", "equipment", "n", "cpk", "ppk", "status"),
    "msa_lamp_grr.csv": ("gauge", "pct_grr", "pct_tolerance", "ndc", "verdict", "cpk_obs"),
    "msa_lamp_guard.csv": ("section", "gauge", "operator", "multiplier", "lower", "upper", "false_accept",
                           "false_reject", "value"),
    "anomaly_lamp_methods.csv": ("section", "method", "shift", "threshold", "detection_rate", "early", "missed",
                                 "mean_delay_cost", "false_per_1000", "value"),
    "anomaly_lamp_model.csv": ("section", "name", "value"),
    "anomaly_lamp_replay.csv": ("t", "z", "threshold", "alarm", "status", "s_mean", "s_sd", "s_max", "s_slope",
                                "s_ewma", "s_fail_share"),
    "spc_lamp_methods.csv": ("section", "method", "shift", "name", "value", "detection_rate", "early", "missed",
                             "mean_delay_cost", "false_per_1000", "decision_interval"),
    "spc_lamp_chart.csv": ("onset", "t", "value", "z", "ewma_limit", "c_plus", "c_minus", "xbar", "range"),
    "pfmea_lamp_report.csv": ("section", "id", "failure_mode", "severity", "occurrence", "detection",
                              "evidence_status", "effect_result", "reference", "scope", "numerator", "denominator",
                              "value"),
    "line_lamp_compare.csv": ("section", "combo", "area_mm2", "pass_uph", "good_uph", "bottleneck", "reject_reason",
                              "selected", "value"),
    "incident_lamp_timeline.csv": ("method", "incident_id", "cycle", "product", "event", "detail"),
    "incident_lamp_compare.csv": ("section", "method", "scope", "name", "value", "stops", "false_stops", "detection",
                                  "a", "delay", "suspect_passed", "captured", "captured_parts", "scope_size",
                                  "over_scope"),
    "incident_lamp_suspects.csv": ("incident_id", "scope", "product"),
}
TEXT_INPUTS = ("line_lamp_layout.svg", "incident_lamp_pfmea.md")
FEATURES = ("mean", "sd", "max", "slope", "ewma", "fail_share")
SVG_NAMESPACE = "{http://www.w3.org/2000/svg}"
SVG_ELEMENTS = {"svg", "defs", "marker", "line", "path", "rect", "text"}
SVG_ATTRIBUTES = {"class", "d", "fill", "font-family", "font-size", "height", "id", "marker-end", "markerHeight",
                  "markerWidth", "orient", "refX", "refY", "stroke", "stroke-dasharray", "text-anchor", "width", "x",
                  "x1", "x2", "y", "y1", "y2", "viewBox"}
SVG_REFERENCE = re.compile(r"url\(#([A-Za-z0-9_-]+)\)")


class DashboardError(ValueError):
    """입력이 모자라거나 믿을 수 없다. 종료 코드는 2이고 HTML을 만들지 않는다."""


def e(value):
    return html.escape(str(value), quote=True)


def safe_json(data):
    """`<script>` 안에 넣는 JSON이다. `</`만 막으면 `<!--`가 파싱 상태를 바꿀 수 있어 꺾쇠를 전부 바꾼다."""
    text = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    for char, code in (("<", "\\u003c"), (">", "\\u003e"), ("&", "\\u0026"), (" ", "\\u2028"),
                       (" ", "\\u2029")):
        text = text.replace(char, code)
    return text


def read_rows(path, columns):
    try:
        with path.open(encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            rows = list(reader)
            fields = reader.fieldnames or ()
    except OSError as error:
        raise DashboardError("입력 파일 없음: " + path.name) from error
    missing = [column for column in columns if column not in fields]
    if missing:
        raise DashboardError("%s: 필요한 열 없음 %s" % (path.name, ", ".join(missing)))
    return rows


def read_text(path):
    try:
        return path.read_bytes().decode("utf-8-sig")
    except OSError as error:
        raise DashboardError("입력 파일 없음: " + path.name) from error


def check_svg(text):
    """허용 목록으로 검사한다. 금지 목록은 foreignObject나 애니메이션 같은 빈틈을 남긴다.

    `<!`는 전부 거절한다. XML이 주석으로 읽는 `<!-->`를 HTML은 바로 닫고 뒤를 실행한다.
    """
    declaration = text.lstrip()
    if declaration.startswith("<?xml"):
        declaration = declaration[declaration.index("?>") + 2:].lstrip()
    if "<!" in declaration or "<?" in declaration:
        raise DashboardError("SVG: 주석, 선언, 처리 지시가 있음")
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError as error:
        raise DashboardError("SVG: 깨진 XML") from error
    ids = {node.get("id") for node in root.iter() if node.get("id")}
    for node in root.iter():
        if not isinstance(node.tag, str) or not node.tag.startswith(SVG_NAMESPACE):
            raise DashboardError("SVG: 허용 밖 이름공간")
        if node.tag[len(SVG_NAMESPACE):] not in SVG_ELEMENTS:
            raise DashboardError("SVG: 허용 밖 요소 " + node.tag)
        for name, value in node.attrib.items():
            if name not in SVG_ATTRIBUTES:
                raise DashboardError("SVG: 허용 밖 속성 " + name)
            references = SVG_REFERENCE.findall(value)
            if any(reference not in ids for reference in references):
                raise DashboardError("SVG: 없는 id 참조")
            if ":" in value or "\\" in value or "url(" in SVG_REFERENCE.sub("", value).lower():
                raise DashboardError("SVG: 허용 밖 참조")
    return declaration


def table(headers, rows, caption=""):
    head = "".join("<th scope=\"col\">%s</th>" % e(header) for header in headers)
    body = "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % e(cell) for cell in row) for row in rows)
    title = "<caption>%s</caption>" % e(caption) if caption else ""
    return ("<div class=\"scroll\" tabindex=\"0\"><table>%s<thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>"
            % (title, head, body))


def legend(items):
    keys = "".join("<span class=\"key\"><i class=\"swatch %s\"></i>%s</span>" % (e(style), e(label))
                   for label, style in items)
    return "<div class=\"legend\">%s</div>" % keys


def _ticks(low, high, count=4):
    return [low + (high - low) * index / count for index in range(count + 1)]


def line_chart(name, title, xs, series, marks):
    """선 그래프 하나다. 축은 하나만 쓴다. `series`는 (이름, 값, 클래스), `marks`는 (이름, 값, 축)이다."""
    width, height, left, right, top, bottom = 720, 240, 52, 12, 12, 30
    values = [value for _, data, _ in series for value in data]
    values += [value for _, value, axis in marks if axis == "y"]
    low, high = min(values), max(values)
    high = high if high > low else low + 1
    start, stop = xs[0], xs[-1]

    def px(value):
        return left + (value - start) / ((stop - start) or 1) * (width - left - right)

    def py(value):
        return top + (high - value) / (high - low) * (height - top - bottom)

    parts = ["<svg class=\"chart\" data-chart=\"%s\" viewBox=\"0 0 %d %d\" role=\"img\" aria-label=\"%s\">"
             % (e(name), width, height, e(title))]
    for tick in _ticks(low, high):
        parts.append("<line class=\"grid\" x1=\"%d\" x2=\"%d\" y1=\"%.1f\" y2=\"%.1f\"></line>"
                     % (left, width - right, py(tick), py(tick)))
        parts.append("<text class=\"tick\" x=\"%d\" y=\"%.1f\" text-anchor=\"end\">%.1f</text>"
                     % (left - 6, py(tick) + 4, tick))
    for tick in _ticks(start, stop):
        parts.append("<text class=\"tick\" x=\"%.1f\" y=\"%d\" text-anchor=\"middle\">%d</text>"
                     % (px(tick), height - 10, round(tick)))
    for label, value, axis in marks:
        if axis == "y":
            parts.append("<line class=\"mark\" x1=\"%d\" x2=\"%d\" y1=\"%.1f\" y2=\"%.1f\"></line>"
                         % (left, width - right, py(value), py(value)))
            parts.append("<text class=\"tick\" x=\"%d\" y=\"%.1f\" text-anchor=\"end\">%s</text>"
                         % (width - right, py(value) - 4, e(label)))
        else:
            parts.append("<line class=\"mark\" x1=\"%.1f\" x2=\"%.1f\" y1=\"%d\" y2=\"%d\"></line>"
                         % (px(value), px(value), top, height - bottom))
            parts.append("<text class=\"tick\" x=\"%.1f\" y=\"%d\">%s</text>" % (px(value) + 4, top + 10, e(label)))
    for _, data, style in series:
        points = " ".join("%.1f,%.1f" % (px(x), py(y)) for x, y in zip(xs, data))
        parts.append("<polyline class=\"line %s\" points=\"%s\"></polyline>" % (e(style), points))
    parts.append("<line class=\"cross\" x1=\"0\" x2=\"0\" y1=\"%d\" y2=\"%d\" visibility=\"hidden\"></line>"
                 % (top, height - bottom))
    parts.append("</svg>")
    keys = [(label, style) for label, _, style in series]
    return ("<figure class=\"figure\"><figcaption>%s</figcaption>%s<div class=\"plot\">%s"
            "<div class=\"tip\" hidden></div></div></figure>"
            % (e(title), legend(keys) if len(keys) > 1 else "", "".join(parts)))


def bar_chart(title, groups, labels, styles, top_value, marks=()):
    """묶음 막대다. `groups`는 (묶음 이름, 값 목록)이다. 값은 문자열 그대로 제목에 넣는다."""
    width, height, left, bottom, top = 720, 230, 40, 44, 10
    slot = (width - left - 8) / len(groups)
    bar = min(18.0, (slot - 14) / len(labels) - 2)

    def py(value):
        return top + (top_value - value) / top_value * (height - top - bottom)

    parts = ["<svg class=\"chart\" viewBox=\"0 0 %d %d\" role=\"img\" aria-label=\"%s\">" % (width, height, e(title))]
    for tick in _ticks(0, top_value):
        parts.append("<line class=\"grid\" x1=\"%d\" x2=\"%d\" y1=\"%.1f\" y2=\"%.1f\"></line>"
                     % (left, width - 8, py(tick), py(tick)))
        parts.append("<text class=\"tick\" x=\"%d\" y=\"%.1f\" text-anchor=\"end\">%g</text>"
                     % (left - 6, py(tick) + 4, tick))
    for label, value in marks:
        parts.append("<line class=\"mark\" x1=\"%d\" x2=\"%d\" y1=\"%.1f\" y2=\"%.1f\"></line>"
                     % (left, width - 8, py(value), py(value)))
        parts.append("<text class=\"tick\" x=\"%d\" y=\"%.1f\" text-anchor=\"end\">%s</text>"
                     % (width - 8, py(value) - 4, e(label)))
    for index, (name, values) in enumerate(groups):
        center = left + slot * (index + 0.5)
        begin = center - (bar + 2) * len(values) / 2
        for position, value in enumerate(values):
            if value == "":
                continue
            x = begin + position * (bar + 2)
            base = py(0)
            y = py(float(value))
            parts.append("<rect class=\"bar %s\" x=\"%.1f\" y=\"%.1f\" width=\"%.1f\" height=\"%.1f\" rx=\"3\">"
                         "<title>%s %s: %s</title></rect>"
                         % (e(styles[position]), x, y, bar, max(base - y, 1), e(name), e(labels[position]), e(value)))
        parts.append("<text class=\"tick\" x=\"%.1f\" y=\"%d\" text-anchor=\"middle\">%s</text>"
                     % (center, height - 24, e(name)))
    parts.append("</svg>")
    keys = list(zip(labels, styles))
    return ("<figure class=\"figure\"><figcaption>%s</figcaption>%s%s</figure>"
            % (e(title), legend(keys) if len(keys) > 1 else "", "".join(parts)))


def stop_strip(title, methods, stops, onset, last):
    """제품 번호 축 위에 방법별 정지 위치를 찍는다. 고장 뒤 첫 정지는 모양으로도 구분한다."""
    width, left, right, row = 720, 90, 12, 40
    height = row * len(methods) + 34

    def px(value):
        return left + value / (last or 1) * (width - left - right)

    parts = ["<svg class=\"chart\" viewBox=\"0 0 %d %d\" role=\"img\" aria-label=\"%s\">" % (width, height, e(title))]
    parts.append("<line class=\"mark\" x1=\"%.1f\" x2=\"%.1f\" y1=\"4\" y2=\"%d\"></line>"
                 % (px(onset), px(onset), height - 26))
    parts.append("<text class=\"tick\" x=\"%.1f\" y=\"%d\" text-anchor=\"middle\">고장 시작 %d</text>"
                 % (px(onset), height - 12, onset))
    for index, method in enumerate(methods):
        y = 20 + index * row
        parts.append("<text class=\"tick\" x=\"%d\" y=\"%d\" text-anchor=\"end\">%s</text>" % (left - 8, y + 4, e(method)))
        parts.append("<line class=\"grid\" x1=\"%d\" x2=\"%d\" y1=\"%d\" y2=\"%d\"></line>"
                     % (left, width - right, y, y))
        for product, label, real in stops[method]:
            title_text = "<title>%s 제품 %s</title>" % (e(label), e(product))
            if real:
                parts.append("<rect class=\"bar s1\" x=\"%.1f\" y=\"%d\" width=\"10\" height=\"10\" rx=\"2\">%s</rect>"
                             % (px(int(product)) - 5, y - 5, title_text))
            else:
                parts.append("<circle class=\"bar s2\" cx=\"%.1f\" cy=\"%d\" r=\"5\">%s</circle>"
                             % (px(int(product)), y, title_text))
    parts.append("</svg>")
    return ("<figure class=\"figure\"><figcaption>%s</figcaption>%s%s</figure>"
            % (e(title), legend([("고장 뒤 첫 정지", "s1"), ("그 밖의 정지(오경보)", "s2")]), "".join(parts)))


def status(text):
    """상태는 색만으로 구분하지 않고 글자를 함께 쓴다."""
    return "<span class=\"status\">%s</span>" % e(text)


def section_rows(rows, name):
    return [row for row in rows if row["section"] == name]


def one(rows, section, **fields):
    for row in section_rows(rows, section):
        if all(row[key] == value for key, value in fields.items()):
            return row
    raise DashboardError("필요한 행 없음: %s %s" % (section, fields))


def selection_of(rows):
    picked = section_rows(rows, "selection")
    if len(picked) != 2:
        raise DashboardError("선택 행 수가 맞지 않음")
    return picked[0]["value"], picked[1]["value"]


def _finite(text):
    value = float(text)
    if not math.isfinite(value):
        raise DashboardError("로지스틱 기여값 입력이 유한하지 않음")
    return value


def contribution_rows(reports):
    """`b + Σ w_j s_j`를 모든 경보 행에서 펼친다. 이 곱셈이 화면의 유일한 계산이고 보고서 z와 맞아야 한다.

    경보가 없는 재생 자료는 11단계의 정상 결과다. 모델 행이 모자란 경우와 구분한다.
    """
    model = reports["anomaly_lamp_model.csv"]
    weights = {row["name"]: _finite(row["value"]) for row in model if row["section"] == "weight"}
    bias = next((_finite(row["value"]) for row in model if row["section"] == "bias"), None)
    alarms = [row for row in reports["anomaly_lamp_replay.csv"] if row["alarm"] == "1"]
    if bias is None or set(weights) != set(FEATURES):
        raise DashboardError("로지스틱 기여값 입력이 모자람")
    result = []
    for alarm in alarms:
        parts = [(name, weights[name] * _finite(alarm["s_" + name])) for name in FEATURES]
        total = bias + sum(value for _, value in parts)
        if not math.isfinite(total) or not all(math.isfinite(value) for _, value in parts):
            raise DashboardError("로지스틱 기여값 계산이 유한하지 않음")
        if abs(total - _finite(alarm["z"])) > 1e-8:
            raise DashboardError("로지스틱 기여값 합이 z와 다름")
        result.append((alarm, parts))
    return bias, result


def overview_section(reports):
    capability = [row for row in section_rows(reports["gen_measured_seed42_capability.csv"], "capability")
                  if row["cpk"]]
    lowest = min(capability, key=lambda row: float(row["cpk"]), default=None)
    grr = reports["msa_lamp_grr.csv"]
    guard = section_rows(reports["msa_lamp_guard.csv"], "holdout")
    model_pick, model_hold = selection_of(reports["anomaly_lamp_methods.csv"])
    chart_pick, chart_hold = selection_of(reports["spc_lamp_methods.csv"])
    picked = [row for row in section_rows(reports["anomaly_lamp_methods.csv"], "holdout")
              if row["method"] == model_pick]
    model_text = "%s 지연 비용 %s" % (model_pick, picked[0]["mean_delay_cost"]) if picked else model_pick
    items = section_rows(reports["pfmea_lamp_report.csv"], "item")
    judged = [row for row in items if row["effect_result"]]
    line = reports["line_lamp_compare.csv"]
    chosen = section_rows(line, "selection")[0]
    held = section_rows(line, "holdout")
    stories = section_rows(reports["incident_lamp_compare.csv"], "story")
    rows = [
        ("측정", "가장 낮은 Cpk %s %s" % (lowest["equipment"], lowest["cpk"]) if lowest else "유효한 Cpk 없음",
         lowest["status"] if lowest else "표본 부족"),
        ("측정 시스템", ", ".join("%s %%GRR %s" % (row["gauge"], row["pct_grr"] or "계산 불가") for row in grr),
         ", ".join("%s %s" % (row["gauge"], row["verdict"]) for row in grr) + " / 가드밴드 "
         + ", ".join("%s %s" % (row["gauge"], row["value"]) for row in guard)),
        ("이상 검출", "%s, 관리도 선택 %s" % (model_text, chart_pick),
         "%s / %s" % (model_hold, chart_hold)),
        ("PFMEA", ", ".join("%s %s" % (row["id"], row["effect_result"]) for row in judged), "S·O·D는 사용자 입력 전 빈칸"),
        ("라인", "조합 %s, 홀드아웃 UPH %s" % (chosen["combo"], held[0]["pass_uph"]) if held else "선택 조합 없음",
         chosen["value"]),
        ("PLC", "시나리오 %d개 소켓 재생" % len(SCENARIOS), "실제 PLC 프로그램이 아니라 Python 스캔 모의"),
        ("사건", ", ".join("%s 정지 %s" % (row["method"], row["a"] or "없음") for row in stories),
         ", ".join("%s %s" % (row["method"], row["detection"]) for row in stories)),
    ]
    return table(("절", "핵심 수치", "사전 기준 결과"), rows)


def measure_section(reports):
    rows = [(row["inspection"], row["equipment"], row["n"], row["cpk"], row["ppk"], row["status"])
            for row in section_rows(reports["gen_measured_seed42_capability.csv"], "capability")]
    return "<p>Cpk·Ppk 빈칸은 표본 부족입니다.</p>" + table(("검사", "설비", "n", "Cpk", "Ppk", "상태"), rows)


def msa_section(reports):
    grr = reports["msa_lamp_grr.csv"]
    guard = reports["msa_lamp_guard.csv"]
    values = [float(row["pct_grr"]) for row in grr if row["pct_grr"]]
    if values:
        groups = [(row["gauge"], [row["pct_grr"]]) for row in grr]
        top = max(40, 10 * math.ceil(max(values) * 1.1 / 10))
        chart = bar_chart("게이지별 %GRR (10·30은 빌린 관행 값)", groups, ["%GRR"], ["s1"], top, (("10", 10), ("30", 30)))
    else:
        chart = "<p>계산 가능한 %GRR이 없어 막대를 그리지 않습니다. 판정은 아래 표에 있습니다.</p>"
    table_grr = table(("게이지", "%GRR", "%공차", "ndc", "판정", "관측 Cpk"),
                      [(row["gauge"], row["pct_grr"], row["pct_tolerance"], row["ndc"], row["verdict"], row["cpk_obs"])
                       for row in grr])
    selected = table(("게이지", "선택 배수", "한계", "홀드아웃 오합격", "오불합격", "결과"),
                     [(row["gauge"], row["multiplier"], "%s–%s" % (row.get("lower", ""), row.get("upper", "")),
                       row["false_accept"], row["false_reject"], row["value"])
                      for row in section_rows(guard, "holdout")], "가드밴드 선택")
    sensitivity = table(("게이지", "작업자", "오합격", "오불합격"),
                        [(row["gauge"], row["operator"], row["false_accept"], row["false_reject"])
                         for row in section_rows(guard, "operator_sensitivity")], "작업자 고정 편차 민감도 (참고)")
    return chart + table_grr + selected + sensitivity


def detect_section(reports):
    anomaly, spc = reports["anomaly_lamp_methods.csv"], reports["spc_lamp_methods.csv"]
    combined = []
    for rows, step in ((anomaly, "11단계"), (spc, "13단계")):
        for row in section_rows(rows, "holdout"):
            combined.append((step, row["method"]) + tuple(row[name] for name in METRICS))
    methods = [row[1] for row in combined]
    shifts = sorted({row["shift"] for row in section_rows(anomaly, "holdout_shift")}, key=float)
    groups = []
    for method in methods:
        source = anomaly if any(row["method"] == method for row in section_rows(anomaly, "holdout")) else spc
        scored = one(source, "holdout", method=method)["detection_rate"]
        groups.append((method, [one(source, "holdout_shift", method=method, shift=shift)["detection_rate"]
                                if scored else "" for shift in shifts]))
    shift_chart = bar_chart("홀드아웃 이동량별 검출률", groups, [shift + "σ" for shift in shifts], ["s1", "s2", "s3"], 1.0)
    chart = reports["spc_lamp_chart.csv"]
    xs = [int(row["t"]) for row in chart]
    onset = int(chart[0]["onset"])
    limits = {row["name"]: float(row["value"]) for row in section_rows(spc, "limits")}
    center = limits["xbarbar"]
    bound = limits["cusum_h"] * limits["sigma_hat"]
    ewma = line_chart("ewma", "EWMA 값과 시변 관리 한계", xs,
                      [("z", [float(row["z"]) for row in chart], "s1"),
                       ("상한", [center + float(row["ewma_limit"]) for row in chart], "s2"),
                       ("하한", [center - float(row["ewma_limit"]) for row in chart], "s2")],
                      [("고장 시작", onset, "x"), ("중심", center, "y")])
    cusum = line_chart("cusum", "CUSUM 누적합", xs,
                       [("C+", [float(row["c_plus"]) for row in chart], "s1"),
                        ("C−", [float(row["c_minus"]) for row in chart], "s2")],
                       [("고장 시작", onset, "x"), ("h", bound, "y")])
    model = {row["name"]: row["value"] for row in reports["anomaly_lamp_model.csv"] if row["section"] == "fit"}
    bias, alarms = contribution_rows(reports)
    picks = (selection_of(anomaly), selection_of(spc))
    notes = ("<p>11단계 선택: %s, %s. 13단계 선택: %s, %s.</p><p>로지스틱 학습: %s, 경사 노름 %s.</p>"
             % (e(picks[0][0]), e(picks[0][1]), e(picks[1][0]), e(picks[1][1]), status(model["status"]),
                e(model["gradient_norm"])))
    unscored = [row[1] for row in combined if not row[2]]
    if unscored:
        notes += "<p>임계값이 없어 수치가 빈칸인 방법: %s.</p>" % e(", ".join(unscored))
    terms = ""
    if not alarms:
        states = sorted({row["status"] for row in reports["anomaly_lamp_replay.csv"]})
        terms = "<p>재생 상태 %s, 경보가 없어 기여값 표를 만들지 않습니다.</p>" % e(", ".join(states))
    for alarm, parts in alarms:
        rows = [("bias", "%.4f" % bias)] + [(name, "%.4f" % value) for name, value in parts]
        rows.append(("합 z", alarm["z"]))
        terms += table(("항", "기여값"), rows, "경보 측정 t=%s의 b + Σ w_j s_j, 임계값 %s" % (alarm["t"], alarm["threshold"]))
    headers = ("단계", "방법", "검출률", "조기", "무경보", "평균 지연 비용", "측정 1,000건당 오경보")
    shift_table = table(("방법",) + tuple(shift + "σ" for shift in shifts), [(name,) + tuple(values) for name, values in groups],
                        "이동량별 검출률 수치")
    series = table(("t", "측정값", "z", "EWMA 한계 폭", "C+", "C−", "X̄", "R"),
                   [(row["t"], row["value"], row["z"], row["ewma_limit"], row["c_plus"], row["c_minus"], row["xbar"],
                     row["range"]) for row in chart])
    return (notes + table(headers, combined, "홀드아웃 비교") + shift_chart + shift_table + ewma + cusum
            + "<details><summary>관리도 수치 %d행</summary>%s</details>" % (len(chart), series) + terms)


def pfmea_section(reports):
    rows = [(row["id"], row["failure_mode"], row["severity"], row["occurrence"], row["detection"],
             row["evidence_status"], row["effect_result"])
            for row in section_rows(reports["pfmea_lamp_report.csv"], "item")]
    evidence = [(row["id"], row["reference"], row["scope"], row["numerator"], row["denominator"], row["value"])
                for row in section_rows(reports["pfmea_lamp_report.csv"], "evidence")]
    return ("<p>S·O·D 빈칸은 아직 사람이 매기지 않은 값입니다. 프로그램이 추정하지 않습니다.</p>"
            + table(("ID", "고장 모드", "S", "O", "D", "근거 상태", "효과 판정"), rows)
            + table(("ID", "근거 참조", "범위", "분자", "분모", "관측값"), evidence, "행별 근거와 관측값"))


def line_section(reports, layout):
    rows = reports["line_lamp_compare.csv"]
    picked = section_rows(rows, "selection")[0]
    held = section_rows(rows, "holdout")
    body = table(("조합", "면적(mm²)", "통과 UPH", "양품 UPH", "병목", "탈락 사유", "선택"),
                 [(row["combo"], row["area_mm2"], row["pass_uph"], row["good_uph"], row["bottleneck"],
                   row["reject_reason"], row["selected"]) for row in section_rows(rows, "development")],
                 "개발 시드 비교")
    if held:
        summary = "<p>선택 %s, 홀드아웃 UPH %s, %s.</p>" % (e(picked["combo"]), e(held[0]["pass_uph"]), e(picked["value"]))
    else:
        summary = "<p>%s.</p>" % e(picked["value"])
    return summary + body + ("<div class=\"scroll plate\" tabindex=\"0\">%s</div>" % layout if layout else "")


def change_rows(rows):
    """상태, 알람, 출력, 이벤트가 바뀐 주기만 남긴다. 처리 수도 바뀌면 남긴다."""
    kept, previous = [], None
    for row in rows:
        key = (row["state"], row["alarm"], row["outputs"], row["processed"])
        if key != previous or row["events"]:
            kept.append(row)
        previous = key
    return kept


def state_diagram():
    grid = [(0, 0), (1, 0), (2, 0), (3, 0), (3, 1), (2, 1), (1, 1), (0, 1), (1, 2)]
    parts = ["<svg class=\"chart states\" viewBox=\"0 0 720 200\" role=\"img\" aria-label=\"PLC 상태\">"]
    for name, (column, row) in zip(STATES, grid):
        x, y = 12 + column * 176, 8 + row * 64
        parts.append("<g data-state=\"%s\"><rect class=\"node\" x=\"%d\" y=\"%d\" width=\"160\" height=\"48\" rx=\"6\">"
                     "</rect><text class=\"nodetext\" x=\"%d\" y=\"%d\" text-anchor=\"middle\">%s</text></g>"
                     % (name, x, y, x + 80, y + 29, name))
    parts.append("</svg>")
    return "".join(parts)


def plc_section(reports):
    summaries, details, replay = [], [], {}
    for name in SCENARIOS:
        rows = reports["plc:" + name]
        last = rows[-1]
        alarms = sorted({row["alarm"] for row in rows if row["alarm"] != "0"}, key=int)
        summaries.append((name, len(rows), last["state"], last["processed"], ", ".join(alarms)))
        changed = change_rows(rows)
        details.append("<details><summary>%s 변화 %d행</summary>%s</details>"
                       % (e(name), len(changed), table(PLC_COLUMNS, [[row[key] for key in PLC_COLUMNS]
                                                                     for row in changed])))
        replay[name] = [[row[key] for key in PLC_COLUMNS] for row in rows]
    options = "".join("<option value=\"%s\">%s</option>" % (e(name), e(name)) for name in SCENARIOS)
    lamps = "".join("<span class=\"lamp\" data-lamp=\"%d\"><i></i>%s <b>OFF</b></span>" % (index, e(name))
                    for index, name in enumerate(OUTPUTS))
    player = ("<div class=\"player\" hidden><label>시나리오 <select id=\"scenario\">%s</select></label>"
              "<label class=\"grow\">주기 <input id=\"cycle\" type=\"range\" min=\"0\" max=\"0\" value=\"0\"></label>"
              "<button id=\"play\" type=\"button\">재생</button><output id=\"readout\"></output>"
              "%s<div class=\"lamps\">%s</div></div>" % (options, state_diagram(), lamps))
    data = "<script id=\"plc-data\" type=\"application/json\">%s</script>" % safe_json(replay)
    return (player + table(("시나리오", "주기 수", "마지막 상태", "처리 수", "알람"), summaries, "시나리오 요약")
            + "".join(details) + data)


def pfmea_links(text):
    """사건 ID별 PFMEA 행이다. 고장 뒤 정지가 없는 방법의 행은 빈 ID로 모은다. 고장 모드 칸의 `|`는 뒤에서 세어 피한다."""
    rows = {}
    for line in text.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) >= 4 and cells[0].startswith("PF-"):
            rows.setdefault(cells[-2], []).append(cells[0])
    return rows


def chain_rows(reports, links):
    """PFMEA와 격리 범위는 고장 뒤 첫 정지에만 있다. 그 사건의 연결이 빠지면 빈칸으로 넘기지 않고 멈춘다.

    다른 정지는 격리할 고장이 없으므로 해당 없음과 이유를 적는다.
    """
    answer = {row["method"]: row["a"] for row in section_rows(reports["incident_lamp_compare.csv"], "story")}
    required = {item for ids in links.values() for item in ids}
    events = {}
    for row in reports["incident_lamp_timeline.csv"]:
        if row["incident_id"]:
            events.setdefault(row["incident_id"], {})[row["event"]] = row
    suspects = {}
    for row in reports["incident_lamp_suspects.csv"]:
        suspects.setdefault(row["incident_id"], {}).setdefault(row["scope"], 0)
        suspects[row["incident_id"]][row["scope"]] += 1
    rows, real = [], set()
    for incident, table_of in events.items():
        alarm = table_of["alarm"]
        stop = answer[alarm["method"]]
        if alarm["product"] == stop:
            real.add(incident)
            scope = ", ".join("%s %d" % item for item in suspects.get(incident, {}).items())
            pfmea = ", ".join(links.get(incident, ()))
            if not scope or not required or set(links.get(incident, ())) != required:
                raise DashboardError("사건 %s의 격리 범위나 PFMEA 연결이 모자람" % incident)
        else:
            early = not stop or int(alarm["product"]) < int(stop)
            scope, pfmea = "해당 없음", "해당 없음: %s 오경보" % ("고장 전" if early else "수리 뒤")
        rows.append((incident, alarm["product"], alarm["detail"], table_of["pc_stop"]["detail"],
                     table_of["alarm_26"]["cycle"], table_of["reset"]["detail"], scope, pfmea))
    if len(real) != sum(1 for stop in answer.values() if stop) or set(links) - real - {""}:
        raise DashboardError("고장 뒤 첫 정지와 사건 연결이 맞지 않음")
    return rows


def incident_section(reports, links):
    compare = reports["incident_lamp_compare.csv"]
    stories = section_rows(compare, "story")
    timeline = reports["incident_lamp_timeline.csv"]
    onset = next(int(row["product"]) for row in timeline if row["event"] == "fault_start")
    last = max(int(row["product"]) for row in timeline)
    stops = {}
    answer = {row["method"]: row["a"] for row in stories}
    for story in stories:
        method = story["method"]
        marked = [row for row in timeline if row["method"] == method and row["event"] == "alarm"]
        stops[method] = [(row["product"], row["incident_id"], row["product"] == answer[method]) for row in marked]
    strip = stop_strip("방법별 정지 위치 (story 실행)", [row["method"] for row in stories], stops, onset, last)
    chain = table(("사건 ID", "제품", "경보 근거", "정지 코일", "알람 26 주기", "복구 조건", "격리 범위 제품 수", "PFMEA"),
                  chain_rows(reports, links), "사건 연결")
    story = table(("방법", "정지 수", "오경보 정지", "판정", "고장 뒤 첫 정지", "지연", "의심 통과"),
                  [(row["method"], row["stops"], row["false_stops"], row["detection"], row["a"], row["delay"],
                    row["suspect_passed"]) for row in stories], "story 실행")
    scope = table(("방법", "범위", "포착", "포착 제품", "범위 크기", "과잉 범위"),
                  [(row["method"], row["scope"], row["captured"], row["captured_parts"], row["scope_size"],
                    row["over_scope"]) for row in section_rows(compare, "story_scope")], "격리 범위")
    summary = table(("방법", "지표", "값", "시드"),
                    [(row["method"], row["name"], row["value"], row["seeds"])
                     for row in section_rows(compare, "summary")], "시드 요약")
    moments = table(("방법", "사건 ID", "주기", "제품", "사건", "내용"),
                    [(row["method"], row["incident_id"], row["cycle"], row["product"], row["event"], row["detail"])
                     for row in timeline], "타임라인")
    return (strip + story + chain + scope + summary + "<details><summary>타임라인 %d행</summary>%s</details>"
            % (len(timeline), moments))


STYLE = """
:root{color-scheme:light;--bg:#fcfcfb;--panel:#ffffff;--ink:#0b0b0b;--ink2:#52514e;--line:#e1e0d9;
--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--on:#2a78d6;--ontext:#ffffff}
@media (prefers-color-scheme:dark){:root{color-scheme:dark;--bg:#1a1a19;--panel:#232322;--ink:#f0efec;--ink2:#c3c2b7;
--line:#3a3a38;--s1:#3987e5;--s2:#d95926;--s3:#199e70;--on:#3987e5;--ontext:#0b0b0b}}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 "Malgun Gothic","Apple SD Gothic Neo","Noto Sans KR",sans-serif}
header,main{max-width:1120px;margin:0 auto;padding:16px}
h1{font-size:22px;margin:0 0 8px}
h2{font-size:18px;margin:0 0 12px}
.notice{margin:0;padding:10px 12px;border:1px solid var(--line);border-left:4px solid var(--s2);background:var(--panel)}
nav{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}
nav a{padding:6px 12px;border:1px solid var(--line);border-radius:6px;color:var(--ink);text-decoration:none;background:var(--panel)}
nav a[aria-current=true]{background:var(--on);border-color:var(--on);color:var(--ontext)}
section{margin:0 0 28px}
.js section[hidden]{display:none}
.scroll{max-width:100%;overflow-x:auto;margin:0 0 16px}
.plate{background:#fff;color:#000;border:1px solid var(--line);padding:8px}
table{border-collapse:collapse;width:100%;background:var(--panel);font-variant-numeric:tabular-nums}
caption{text-align:left;font-weight:600;padding:4px 0}
th,td{padding:6px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top;overflow-wrap:break-word}
th{color:var(--ink2);font-weight:600;white-space:nowrap}
.status{font-weight:600}
.figure{margin:0 0 20px;padding:12px;background:var(--panel);border:1px solid var(--line);border-radius:6px;overflow-x:auto}
figcaption{font-weight:600;margin-bottom:6px}
.chart{display:block;width:100%;min-width:560px;height:auto}
.plot{position:relative}
.tip{position:absolute;top:4px;right:4px;padding:4px 8px;background:var(--bg);border:1px solid var(--line);border-radius:4px;font-size:13px;pointer-events:none}
.grid{stroke:var(--line);stroke-width:1}
.mark{stroke:var(--ink2);stroke-width:1;stroke-dasharray:4 3}
.cross{stroke:var(--ink2);stroke-width:1}
.tick{fill:var(--ink2);font-size:11px}
.line{fill:none;stroke-width:2;vector-effect:non-scaling-stroke}
.line.s1{stroke:var(--s1)}.line.s2{stroke:var(--s2);stroke-dasharray:6 3}.line.s3{stroke:var(--s3)}
.bar.s1{fill:var(--s1)}.bar.s2{fill:var(--s2)}.bar.s3{fill:var(--s3)}
.legend{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:6px;font-size:13px;color:var(--ink2)}
.key{display:inline-flex;align-items:center;gap:6px}
.swatch{display:inline-block;width:12px;height:12px;border-radius:3px}
.swatch.s1{background:var(--s1)}.swatch.s2{background:var(--s2)}.swatch.s3{background:var(--s3)}
details{margin:0 0 10px}
summary{cursor:pointer;font-weight:600;padding:4px 0}
.player{padding:12px;margin:0 0 16px;background:var(--panel);border:1px solid var(--line);border-radius:6px;overflow-x:auto}
.player label{display:inline-flex;align-items:center;gap:6px;margin:0 12px 8px 0}
.player .grow{display:flex;margin-right:0}
.player input[type=range]{flex:1;min-width:0}
.node{fill:var(--bg);stroke:var(--line);stroke-width:1.5}
.nodetext{fill:var(--ink);font-size:14px}
[data-state].on .node{fill:var(--on);stroke:var(--on)}
[data-state].on .nodetext{fill:var(--ontext)}
.lamps{display:flex;flex-wrap:wrap;gap:12px;margin-top:8px;font-size:13px}
.lamp{display:inline-flex;align-items:center;gap:6px}
.lamp i{display:inline-block;width:12px;height:12px;border-radius:50%;border:2px solid var(--ink2)}
.lamp.on i{background:var(--on);border-color:var(--on)}
button,select{font:inherit;padding:4px 10px;background:var(--bg);color:var(--ink);border:1px solid var(--line);border-radius:6px}
"""

SCRIPT = """
(function(){
  var root=document.documentElement;root.classList.add('js');
  var links=[].slice.call(document.querySelectorAll('nav a'));
  var sections=[].slice.call(document.querySelectorAll('main section'));
  function show(id){
    sections.forEach(function(s){s.hidden=s.id!==id});
    links.forEach(function(a){a.setAttribute('aria-current',a.getAttribute('href')==='#'+id?'true':'false')});
  }
  links.forEach(function(a){a.addEventListener('click',function(ev){ev.preventDefault();show(a.getAttribute('href').slice(1))})});
  show(location.hash&&document.getElementById(location.hash.slice(1))?location.hash.slice(1):sections[0].id);
  var box=document.querySelector('.player');box.hidden=false;
  var data=JSON.parse(document.getElementById('plc-data').textContent);
  var pick=document.getElementById('scenario'),range=document.getElementById('cycle');
  var play=document.getElementById('play'),out=document.getElementById('readout'),timer=null;
  var nodes=[].slice.call(box.querySelectorAll('[data-state]')),lamps=[].slice.call(box.querySelectorAll('[data-lamp]'));
  function paint(){
    var rows=data[pick.value],row=rows[Number(range.value)];
    nodes.forEach(function(n){n.classList.toggle('on',n.getAttribute('data-state')===row[1])});
    lamps.forEach(function(l,i){var on=row[3].charAt(i)==='1';l.classList.toggle('on',on);l.querySelector('b').textContent=on?'ON':'OFF'});
    out.textContent='주기 '+row[0]+' · '+row[1]+' · 알람 '+row[2]+' · 처리 '+row[4]+(row[5]?' · '+row[5]:'');
  }
  function load(){range.max=String(data[pick.value].length-1);range.value='0';stop();paint()}
  function stop(){if(timer){clearInterval(timer);timer=null;play.textContent='재생'}}
  pick.addEventListener('change',load);range.addEventListener('input',function(){stop();paint()});
  play.addEventListener('click',function(){
    if(timer){stop();return}
    play.textContent='멈춤';
    timer=setInterval(function(){
      if(Number(range.value)>=Number(range.max)){stop();return}
      range.value=String(Number(range.value)+1);paint();
    },60);
  });
  load();
  [].slice.call(document.querySelectorAll('svg[data-chart]')).forEach(function(svg){
    var tip=svg.parentNode.querySelector('.tip'),cross=svg.querySelector('.cross');
    var name=svg.getAttribute('data-chart'),rows=JSON.parse(document.getElementById('chart-data').textContent)[name];
    svg.addEventListener('pointermove',function(ev){
      var box=svg.getBoundingClientRect(),view=720,left=52,right=12;
      var x=(ev.clientX-box.left)/box.width*view,share=(x-left)/(view-left-right);
      var i=Math.max(0,Math.min(rows.length-1,Math.round(share*(rows.length-1))));
      var at=left+i/(rows.length-1)*(view-left-right);
      cross.setAttribute('x1',at);cross.setAttribute('x2',at);cross.setAttribute('visibility','visible');
      tip.hidden=false;tip.textContent=rows[i];
    });
    svg.addEventListener('pointerleave',function(){tip.hidden=true;cross.setAttribute('visibility','hidden')});
  });
})();
"""


def chart_data(reports):
    rows = reports["spc_lamp_chart.csv"]
    return {"ewma": ["t %s · z %s · 한계 폭 %s" % (row["t"], row["z"][:7], row["ewma_limit"][:7]) for row in rows],
            "cusum": ["t %s · C+ %s · C− %s" % (row["t"], row["c_plus"][:7], row["c_minus"][:7]) for row in rows]}


def load_reports(root):
    folder = root / "reports"
    reports = {name: read_rows(folder / name, columns) for name, columns in INPUTS.items()}
    for name in SCENARIOS:
        rows = read_rows(folder / ("plc_station_%s.csv" % name), PLC_COLUMNS)
        if not rows:
            raise DashboardError("plc_station_%s.csv: 행이 없음" % name)
        reports["plc:" + name] = rows
    return reports


def build(root):
    reports = load_reports(root)
    # 균형 해가 없으면 9단계는 배치도를 쓰지 않는다. 이전 실행의 배치도가 남아 있어도 싣지 않는다.
    balanced = section_rows(reports["line_lamp_compare.csv"], "development")
    layout = check_svg(read_text(root / "reports" / "line_lamp_layout.svg")) if balanced else ""
    links = pfmea_links(read_text(root / "reports" / "incident_lamp_pfmea.md"))
    bodies = {"overview": overview_section(reports), "measure": measure_section(reports), "msa": msa_section(reports),
              "detect": detect_section(reports), "pfmea": pfmea_section(reports), "line": line_section(reports, layout),
              "plc": plc_section(reports), "incident": incident_section(reports, links)}
    navigation = "".join("<a href=\"#%s\">%s</a>" % (name, e(label)) for name, label in TABS)
    sections = "".join("<section id=\"%s\"><h2>%s</h2>%s</section>" % (name, e(label), bodies[name])
                       for name, label in TABS)
    return ("<!doctype html><html lang=\"ko\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"><title>%s</title><style>%s</style>"
            "</head><body><header><h1>%s</h1><p class=\"notice\">%s</p><nav aria-label=\"절\">%s</nav></header>"
            "<main>%s</main><script id=\"chart-data\" type=\"application/json\">%s</script><script>%s</script>"
            "</body></html>\n" % (e(TITLE), STYLE, e(TITLE), e(NOTICE), navigation, sections,
                                  safe_json(chart_data(reports)), SCRIPT))


def output_path(root, target):
    """쓰기 전에 검사한다. 임시 파일 교체는 입력을 HTML로 덮어쓰는 일을 막지 못한다."""
    path = target if target.is_absolute() else root / target
    if path.suffix.lower() != ".html":
        raise DashboardError("--out: 확장자는 .html이어야 함")
    if path.is_symlink():
        raise DashboardError("--out: 심볼릭 링크를 쓸 수 없음")
    resolved = path.resolve()
    if resolved.parent != (root / "reports").resolve():
        raise DashboardError("--out: reports 바로 아래여야 함")
    return resolved


def write_atomic(path, data):
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(descriptor, "wb") as target:
            target.write(data)
        os.replace(temporary, path)
    except OSError:
        Path(temporary).unlink(missing_ok=True)
        raise


def run(root, target):
    root = root.resolve()
    path = output_path(root, target)
    data = build(root).encode("utf-8")
    if len(data) > MAX_BYTES:
        raise DashboardError("HTML이 5MB를 넘음")
    write_atomic(path, data)
    return path, len(data)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    try:
        path, size = run(args.root, args.out)
    except (OSError, UnicodeError, csv.Error, ValueError, KeyError) as error:
        parser.exit(2, "오류: " + str(error) + "\n")
    print(NOTICE)
    print("저장 파일: %s (%d바이트)" % (path.name, size))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

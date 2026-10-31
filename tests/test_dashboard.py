import csv
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

from src.dashboard import (
    INPUTS, NOTICE, SCENARIOS, TEXT_INPUTS, DashboardError, change_rows, check_svg, output_path, safe_json,
)


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
VOID = {"meta", "br", "input", "hr", "img", "link"}
SVG_HEAD = "<svg xmlns=\"http://www.w3.org/2000/svg\">"


class Page(HTMLParser):
    """태그 짝과 본문 글자를 모은다. script와 style 글자는 본문에서 뺀다."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.broken = []
        self.scripts = []
        self.styles = 0
        self.text = []
        self.tags = {}
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        self.tags[tag] = self.tags.get(tag, 0) + 1
        fields = dict(attrs)
        if "id" in fields:
            self.ids.add(fields["id"])
        if tag == "script":
            self.scripts.append(fields.get("type", ""))
        if tag not in VOID:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.stack.pop()

    def handle_endtag(self, tag):
        if not self.stack or self.stack.pop() != tag:
            self.broken.append(tag)

    def handle_data(self, data):
        if not self.stack or self.stack[-1] not in ("script", "style"):
            self.text.append(data)


def parse(text):
    page = Page()
    page.feed(text)
    page.close()
    return page


def copy_inputs(folder):
    target = Path(folder) / "reports"
    target.mkdir()
    names = list(INPUTS) + list(TEXT_INPUTS) + ["plc_station_%s.csv" % name for name in SCENARIOS]
    for name in names:
        shutil.copyfile(REPORTS / name, target / name)
    return target


def run_cli(root, out="reports/dashboard.html"):
    environment = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, "-m", "src.dashboard", "--root", str(root), "--out", str(out)],
                          cwd=str(root), env=environment, capture_output=True, text=True, encoding="utf-8")


def rows_of(path):
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def section(path, name):
    return [row for row in rows_of(path) if row["section"] == name]


def rewrite(path, change):
    raw = path.read_bytes().decode("utf-8-sig")
    updated = change(raw)
    assert updated != raw, path.name
    path.write_bytes(updated.encode("utf-8-sig"))


class PageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.reports = copy_inputs(cls.folder.name)
        result = run_cli(cls.folder.name)
        assert result.returncode == 0, result.stderr
        cls.path = cls.reports / "dashboard.html"
        cls.text = cls.path.read_text(encoding="utf-8")
        cls.page = parse(cls.text)
        cls.body = " ".join(cls.page.text)

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def test_t237_parses_and_has_tabs(self):
        self.assertEqual(self.page.broken, [])
        self.assertEqual(self.page.stack, [])
        self.assertEqual(self.page.tags["section"], 8)
        self.assertEqual(len(re.findall(r"<nav.*?</nav>", self.text)), 1)
        nav = re.search(r"<nav.*?</nav>", self.text).group(0)
        self.assertEqual(nav.count("<a "), 8)

    def test_t238_notice_before_first_section(self):
        self.assertEqual(NOTICE, "모든 값은 합성 데이터와 소프트웨어 모의 결과입니다. 실제 설비, 실제 라인, SL 기준이 아닙니다.")
        self.assertLess(self.text.index(NOTICE), self.text.index("<section"))

    def test_t239_values_match_reports(self):
        capability = rows_of(REPORTS / "gen_measured_seed42_capability.csv")
        expected = [row["cpk"] for row in capability if row["cpk"]]
        expected += [row["pct_grr"] for row in rows_of(REPORTS / "msa_lamp_grr.csv")]
        expected += [row["mean_delay_cost"] for row in rows_of(REPORTS / "anomaly_lamp_methods.csv")
                     if row["section"] == "holdout"]
        expected += [row["mean_delay_cost"] for row in rows_of(REPORTS / "spc_lamp_methods.csv")
                     if row["section"] == "holdout"]
        expected += [row["pass_uph"] for row in rows_of(REPORTS / "line_lamp_compare.csv")
                     if row["section"] == "holdout"]
        expected += [row["a"] for row in rows_of(REPORTS / "incident_lamp_compare.csv")
                     if row["section"] == "story" and row["a"]]
        expected += [row["effect_result"] for row in rows_of(REPORTS / "pfmea_lamp_report.csv")
                     if row["section"] == "item" and row["effect_result"]]
        for value in expected:
            self.assertIn(value, self.body)

    def test_t239_no_hard_coded_values(self):
        with tempfile.TemporaryDirectory() as folder:
            reports = copy_inputs(folder)
            rewrite(reports / "msa_lamp_grr.csv", lambda text: text.replace("13.3878", "77.7777"))
            rewrite(reports / "line_lamp_compare.csv", lambda text: text.replace("185.8934", "111.1111"))
            rewrite(reports / "spc_lamp_methods.csv", lambda text: text.replace("121.3250", "222.2222"))
            self.assertEqual(run_cli(folder).returncode, 0)
            text = (reports / "dashboard.html").read_text(encoding="utf-8")
        for changed, original in (("77.7777", "13.3878"), ("111.1111", "185.8934"), ("222.2222", "121.3250")):
            self.assertIn(changed, text)
            self.assertNotIn(original, text)

    def test_t240_unmet_items_visible(self):
        self.assertIn("PF-02 미충족", self.body)
        self.assertIn("PF-06 미충족", self.body)
        self.assertIn("수렴 미달", self.body)
        self.assertIn("0.0043102869779180425", self.body)

    def test_t240_model_report_drives_status(self):
        with tempfile.TemporaryDirectory() as folder:
            reports = copy_inputs(folder)
            rewrite(reports / "anomaly_lamp_model.csv", lambda text: text.replace("fit,status,수렴 미달", "fit,status,수렴"))
            self.assertEqual(run_cli(folder).returncode, 0)
            self.assertNotIn("수렴 미달", (reports / "dashboard.html").read_text(encoding="utf-8"))

    def test_t241_blank_scores(self):
        section = self.text[self.text.index("<section id=\"pfmea\""):self.text.index("행별 근거와 관측값")]
        rows = re.findall(r"<tr><td>PF-0\d</td>(.*?)</tr>", section)
        self.assertEqual(len(rows), 6)
        for row in rows:
            self.assertEqual(re.findall(r"<td>(.*?)</td>", row)[1:4], ["", "", ""])

    def test_t244_no_external_references(self):
        text = self.text.replace("http://www.w3.org/2000/svg", "")
        for mark in ("http://", "https://", "file:", "data:", "@import", "src=", "<link", "innerHTML", "eval(",
                     "document.write"):
            self.assertNotIn(mark, text)
        self.assertNotRegex(text, r"[\"'(]//")
        self.assertEqual(set(re.findall(r"url\(([^)]*)\)", text)), {"#arrow"})

    def test_t245_no_absolute_paths(self):
        self.assertNotIn(str(self.folder.name), self.text)
        self.assertNotIn("C:\\", self.text)
        self.assertNotRegex(self.text, r"20\d\d-\d\d-\d\dT")

    def test_t245_repeat_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as folder:
            reports = copy_inputs(folder)
            self.assertEqual(run_cli(folder).returncode, 0)
            self.assertEqual((reports / "dashboard.html").read_bytes(), self.path.read_bytes())

    def test_t246_replay_data(self):
        block = re.search(r"<script id=\"plc-data\" type=\"application/json\">(.*?)</script>", self.text).group(1)
        data = json.loads(block)
        self.assertEqual(sorted(data), sorted(SCENARIOS))
        for name in SCENARIOS:
            rows = rows_of(REPORTS / ("plc_station_%s.csv" % name))
            self.assertEqual(len(data[name]), len(rows))
            self.assertEqual(data[name][-1][1], rows[-1]["state"])
            self.assertEqual(data[name][-1][3], rows[-1]["outputs"])

    def test_t247_size(self):
        self.assertLessEqual(self.path.stat().st_size, 5 * 1024 * 1024)

    def test_t248_inputs_unchanged(self):
        for path in self.reports.iterdir():
            if path.name != "dashboard.html":
                self.assertEqual(path.read_bytes(), (REPORTS / path.name).read_bytes(), path.name)

    def test_t263_chart_numbers_are_static(self):
        rows = rows_of(REPORTS / "spc_lamp_chart.csv")
        for row in (rows[0], rows[len(rows) // 2], rows[-1]):
            self.assertIn(row["c_plus"], self.body)
            self.assertIn(row["z"], self.body)
        for row in rows_of(REPORTS / "spc_lamp_methods.csv"):
            if row["section"] == "holdout_shift":
                self.assertIn(row["detection_rate"], self.body)

    def test_t241_evidence_rows(self):
        rows = [row for row in rows_of(REPORTS / "pfmea_lamp_report.csv") if row["section"] == "evidence"]
        self.assertTrue(rows)
        for row in rows:
            self.assertIn(row["reference"], self.body)
            self.assertIn(row["value"], self.body)

    def test_t263_static_content(self):
        for label in ("개요", "측정", "측정 시스템", "이상 검출", "PFMEA", "라인", "PLC", "사건"):
            self.assertIn("<h2>%s</h2>" % label, self.text)
        for name in SCENARIOS:
            self.assertIn("%s 변화" % name, self.body)
            self.assertIn(name, self.body)
        self.assertGreaterEqual(self.page.tags["svg"], 6)
        self.assertGreaterEqual(self.page.tags["table"], 8)
        self.assertIn("<div class=\"player\" hidden>", self.text)

    def test_t265_contributions(self):
        self.assertIn("합 z", self.body)
        replay = [row for row in rows_of(REPORTS / "anomaly_lamp_replay.csv") if row["alarm"] == "1"]
        self.assertIn(replay[0]["z"], self.body)

    def test_t265_mismatch_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            reports = copy_inputs(folder)
            rows = rows_of(reports / "anomaly_lamp_replay.csv")
            rows[-1]["z"] = "99.0000000000"
            with (reports / "anomaly_lamp_replay.csv").open("w", encoding="utf-8-sig", newline="") as target:
                writer = csv.DictWriter(target, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            self.assertEqual(run_cli(folder).returncode, 2)
            self.assertFalse((reports / "dashboard.html").exists())

    def test_no_selected_model_is_shown(self):
        with tempfile.TemporaryDirectory() as folder:
            reports = copy_inputs(folder)
            rewrite(reports / "anomaly_lamp_methods.csv",
                    lambda text: text.replace("selection,logistic,,,,,,,,,,,,,logistic",
                                              "selection,,,,,,,,,,,,,,기준 충족 방법 없음")
                    .replace("selection,logistic,,,,,,,,,,,,,홀드아웃 확인", "selection,,,,,,,,,,,,,,홀드아웃 검증할 선택 없음"))
            result = run_cli(folder)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("기준 충족 방법 없음", (reports / "dashboard.html").read_text(encoding="utf-8"))

    def test_ewma_graph_uses_actual_limits(self):
        section = self.text[self.text.index("EWMA 값과 시변 관리 한계"):]
        self.assertEqual(section[:section.index("</figure>")].count("<polyline"), 3)
        self.assertIn("상한", section)
        self.assertIn("하한", section)

    def test_all_samples_short_is_shown(self):
        with tempfile.TemporaryDirectory() as folder:
            reports = copy_inputs(folder)
            path = reports / "gen_measured_seed42_capability.csv"
            rows = rows_of(path)
            for row in rows:
                if row["section"] == "capability":
                    row.update(cpk="", ppk="", status="표본 부족")
            with path.open("w", encoding="utf-8-sig", newline="") as target:
                writer = csv.DictWriter(target, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            result = run_cli(folder)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("유효한 Cpk 없음", (reports / "dashboard.html").read_text(encoding="utf-8"))

    def test_t265_later_alarm_and_nan_refused(self):
        rows = rows_of(REPORTS / "anomaly_lamp_replay.csv")
        alarm = next(row for row in rows if row["alarm"] == "1")
        for extra in ([alarm, dict(alarm, t=str(int(alarm["t"]) + 1), z="99.0000000000")], [dict(alarm, z="nan")]):
            with tempfile.TemporaryDirectory() as folder:
                reports = copy_inputs(folder)
                changed = [row for row in rows if row is not alarm] + extra
                with (reports / "anomaly_lamp_replay.csv").open("w", encoding="utf-8-sig", newline="") as target:
                    writer = csv.DictWriter(target, fieldnames=list(rows[0]))
                    writer.writeheader()
                    writer.writerows(changed)
                self.assertEqual(run_cli(folder).returncode, 2)
                self.assertFalse((reports / "dashboard.html").exists())

    def test_t265_finite_inputs_that_overflow_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            reports = copy_inputs(folder)
            path = reports / "anomaly_lamp_replay.csv"
            rows = rows_of(path)
            for row in rows:
                if row["alarm"] == "1":
                    row.update(s_mean="1e308", s_sd="1e308", s_max="0", s_slope="0", s_ewma="0", s_fail_share="0")
            with path.open("w", encoding="utf-8-sig", newline="") as target:
                writer = csv.DictWriter(target, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            model = reports / "anomaly_lamp_model.csv"
            changed = rows_of(model)
            for row in changed:
                if row["section"] == "weight":
                    row["value"] = {"mean": "1e308", "sd": "-1e308"}.get(row["name"], "0")
            with model.open("w", encoding="utf-8-sig", newline="") as target:
                writer = csv.DictWriter(target, fieldnames=list(changed[0]))
                writer.writeheader()
                writer.writerows(changed)
            self.assertEqual(run_cli(folder).returncode, 2)
            self.assertFalse((reports / "dashboard.html").exists())

    def test_t266_incident_chain(self):
        section = self.text[self.text.index("<section id=\"incident\""):]
        timeline = rows_of(REPORTS / "incident_lamp_timeline.csv")
        stories = {row["method"]: row for row in rows_of(REPORTS / "incident_lamp_compare.csv")
                   if row["section"] == "story"}
        alarms = [row for row in timeline if row["event"] == "alarm"]
        self.assertTrue(alarms)
        import html
        decoded = html.unescape(section)
        for row in alarms:
            self.assertIn(row["incident_id"], decoded)
            self.assertIn(row["detail"], decoded)
            line = next(item for item in re.findall(r"<tr>.*?</tr>", decoded) if "<td>%s</td>" % row["incident_id"] in item)
            if row["product"] != stories[row["method"]]["a"]:
                self.assertIn("해당 없음: %s 오경보" % ("고장 전" if int(row["product"]) < 199 else "수리 뒤"), line)
        chain = [row for row in alarms if row["product"] == stories[row["method"]]["a"]]
        self.assertTrue(chain)
        for row in chain:
            line = next(item for item in re.findall(r"<tr>.*?</tr>", decoded) if ">%s<" % row["incident_id"] in item
                        and "PF-02" in item)
            self.assertIn("PF-06", line)
            self.assertIn("last_20", line)


class UpstreamResultTests(unittest.TestCase):
    """앞 단계가 실제로 만든 빈 결과를 잇는다. 보고서를 손으로 고치지 않고 해당 CLI를 돌린다."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.reports = copy_inputs(self.folder.name)
        shutil.copytree(ROOT / "recipes", self.root / "recipes")

    def edit(self, name, **changes):
        path = self.root / "recipes" / name
        data = json.loads(path.read_text(encoding="utf-8"))
        data.update(changes)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def upstream(self, *arguments):
        environment = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONIOENCODING="utf-8")
        result = subprocess.run([sys.executable, "-m", *arguments], cwd=str(self.root), env=environment,
                                capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)

    def shown(self):
        result = run_cli(self.folder.name)
        self.assertEqual(result.returncode, 0, result.stderr)
        return (self.reports / "dashboard.html").read_text(encoding="utf-8")

    def test_uncomputable_grr_is_shown(self):
        self.edit("generator_measured.json", process_cpk=1e6)
        self.edit("msa_lamp.json", products=12, dev_seeds="7-7", holdout_seeds="1007-1007")
        self.upstream("src.msa", "recipes/msa_lamp.json")
        self.assertEqual({row["pct_grr"] for row in rows_of(self.reports / "msa_lamp_grr.csv")}, {""})
        text = self.shown()
        self.assertIn("판정 불가", text)
        self.assertIn("계산 불가", text)
        self.assertIn("계산 가능한 %GRR이 없어", text)

    def test_no_threshold_replay_is_shown(self):
        self.edit("anomaly_lamp.json", shifts=[0.01, 0.02, 0.03], false_limit=1e-9, min_detection=1.0, min_shift_detection=1.0,
                  splits={"train": {"seed_start": 0, "count": 30}, "validation": {"seed_start": 1000, "count": 12},
                          "holdout": {"seed_start": 2000, "count": 12}}, iterations=50)
        self.upstream("src.anomaly", "recipes/anomaly_lamp.json")
        self.upstream("src.spc", "recipes/spc_lamp.json")
        replay = rows_of(self.reports / "anomaly_lamp_replay.csv")
        self.assertEqual({row["status"] for row in replay}, {"임계값 없음"})
        text = self.shown()
        self.assertIn("경보가 없어 기여값 표를 만들지 않습니다", text)
        self.assertIn("임계값이 없어 수치가 빈칸인 방법", text)

    def test_missed_replay_is_shown(self):
        path = self.reports / "anomaly_lamp_replay.csv"
        replay = rows_of(path)
        for row in replay:
            row.update(alarm="0", status="missed")
        with path.open("w", encoding="utf-8-sig", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=list(replay[0]))
            writer.writeheader()
            writer.writerows(replay)
        self.assertIn("재생 상태 missed", self.shown())

    def test_no_line_selection_is_shown(self):
        self.edit("line_lamp.json", floor={"length_mm": 1000, "width_mm": 7000, "aisle_mm": 1000, "pitch_mm": 300,
                                           "gap_mm": 200})
        self.upstream("src.line", "recipes/line_lamp.json", "--seeds", "0-0", "--holdout-seeds", "1000-1000",
                      "--products", "20")
        self.assertFalse(section(self.reports / "line_lamp_compare.csv", "holdout"))
        self.assertIn("기준 충족 조합 없음", self.shown())

    def test_no_balance_ignores_old_layout(self):
        self.edit("line_lamp.json", demand_units=100000000)
        self.upstream("src.line", "recipes/line_lamp.json", "--seeds", "0-0", "--holdout-seeds", "1000-1000",
                      "--products", "20")
        self.assertFalse(section(self.reports / "line_lamp_compare.csv", "development"))
        (self.reports / "line_lamp_layout.svg").write_text("<svg><script>x</script></svg>", encoding="utf-8")
        text = self.shown()
        self.assertIn("선택 조합 없음", text)
        self.assertNotIn("class=\"scroll plate\"", text)


class RefusalTests(unittest.TestCase):
    def refused(self, change):
        with tempfile.TemporaryDirectory() as folder:
            reports = copy_inputs(folder)
            old = reports / "dashboard.html"
            old.write_bytes(b"previous")
            change(reports)
            result = run_cli(folder)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(old.read_bytes(), b"previous")

    def test_t266_true_stop_needs_pfmea_link(self):
        def drop(text):
            return lambda reports: rewrite(reports / "incident_lamp_pfmea.md", lambda raw: "\n".join(
                line for line in raw.splitlines() if text not in line))
        self.refused(drop("cusum-3"))
        self.refused(drop("| PF-06 | 유출품이 후보 목록에서 누락 | cusum-3"))

    def test_t266_true_stop_needs_scope(self):
        self.refused(lambda reports: rewrite(reports / "incident_lamp_suspects.csv", lambda raw: "\n".join(
            line for line in raw.splitlines() if "cusum-3" not in line)))

    def test_t266_pfmea_link_to_other_stop_refused(self):
        self.refused(lambda reports: rewrite(reports / "incident_lamp_pfmea.md",
                                             lambda raw: raw + "| PF-02 | 측정 평균이 위로 이동 | cusum-1 | 임의 |\n"))

    def test_t242_missing_file(self):
        self.refused(lambda reports: (reports / "spc_lamp_chart.csv").unlink())

    def test_t242_missing_scenario(self):
        self.refused(lambda reports: (reports / "plc_station_guard_open.csv").unlink())

    def test_t242_missing_column(self):
        self.refused(lambda reports: rewrite(reports / "msa_lamp_grr.csv",
                                             lambda text: text.replace("pct_grr", "pct_gone", 1)))

    def test_t242_bad_svg_end_to_end(self):
        self.refused(lambda reports: (reports / "line_lamp_layout.svg").write_text(SVG_HEAD + "<script></script></svg>",
                                                                                   encoding="utf-8"))

    def test_t242_svg_rules(self):
        cases = ("<script>alert(1)</script>", "<foreignObject></foreignObject>", "<rect onclick=\"x()\"></rect>",
                 "<rect style=\"fill:red\"></rect>", "<rect href=\"#a\"></rect>", "<animate></animate>",
                 "<image></image>", "<use></use>", "<line stroke=\"url(http://x/y)\"></line>",
                 "<rect fill=\"URL(//example.invalid/p.svg#p)\"></rect>",
                 "<rect fill=\"uRl(//example.invalid/p.svg#p)\"></rect>", "<rect fill=\"URL(#none)\"></rect>",
                 "<line marker-end=\"url(#none)\"></line>", "<rect fill=\"a:b\"></rect>")
        for inner in cases:
            with self.subTest(inner=inner), self.assertRaises(DashboardError):
                check_svg(SVG_HEAD + inner + "</svg>")
        for text in ("<!DOCTYPE svg><svg></svg>", SVG_HEAD + "<rect>", "<svg></svg>",
                     SVG_HEAD + "<?php x?></svg>"):
            with self.subTest(text=text), self.assertRaises(DashboardError):
                check_svg(text)

    def test_t242_xml_comment_refused(self):
        for inner in ("<!--><script>alert(1)</script>-->", "<!-- x -->", "<![CDATA[<script>x</script>]]>"):
            with self.subTest(inner=inner), self.assertRaises(DashboardError):
                check_svg(SVG_HEAD + inner + "</svg>")

    def test_t242_xml_declaration_is_not_embedded(self):
        body = SVG_HEAD + "<rect></rect></svg>"
        self.assertEqual(check_svg("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n" + body), body)

    def test_t244_real_layout_passes(self):
        text = (REPORTS / "line_lamp_layout.svg").read_bytes().decode("utf-8-sig")
        self.assertEqual(check_svg(text), text)

    def test_t243_escape(self):
        attack = "<script>alert(1)</script>"
        with tempfile.TemporaryDirectory() as folder:
            reports = copy_inputs(folder)
            rewrite(reports / "pfmea_lamp_report.csv", lambda text: text.replace("측정 평균이 위로 이동", attack, 1))
            rewrite(reports / "plc_station_normal.csv",
                    lambda text: text.replace("1,IDLE,0,00000,0,,", "1,IDLE,0,00000,0,\"</script><!--<script>&lt;\"\"\",", 1))
            self.assertEqual(run_cli(folder).returncode, 0)
            text = (reports / "dashboard.html").read_text(encoding="utf-8")
        page = parse(text)
        self.assertEqual(page.scripts, ["application/json", "application/json", ""])
        self.assertEqual(page.tags["script"], 3)
        self.assertNotIn(attack, text)
        self.assertIn("&lt;script&gt;", text)
        block = re.search(r"<script id=\"plc-data\" type=\"application/json\">(.*?)</script>", text).group(1)
        self.assertNotIn("<", block)
        self.assertEqual(json.loads(block)["normal"][0][5], "</script><!--<script>&lt;\"")

    def test_t243_safe_json_round_trip(self):
        data = {"a": "<!--<script></script>&\u2028\u2029'\""}
        text = safe_json(data)
        for mark in ("<", ">", "&", "\u2028", "\u2029"):
            self.assertNotIn(mark, text)
        self.assertEqual(json.loads(text), data)

    def test_t264_out_path(self):
        with tempfile.TemporaryDirectory() as folder:
            reports = copy_inputs(folder)
            (reports / "sub").mkdir()
            before = (reports / "anomaly_lamp_methods.csv").read_bytes()
            outside = Path(folder).parent / "outside.html"
            for target in ("reports/anomaly_lamp_methods.csv", "reports/spc_lamp_chart.csv", str(outside),
                           "reports/sub/x.html", "reports/dashboard", "dashboard.html"):
                with self.subTest(target=target):
                    self.assertEqual(run_cli(folder, target).returncode, 2)
            self.assertEqual((reports / "anomaly_lamp_methods.csv").read_bytes(), before)
            self.assertFalse(outside.exists())
            self.assertEqual(output_path(Path(folder).resolve(), Path("reports/a.html")).name, "a.html")

    def test_change_rows_keep_only_changes(self):
        rows = [{"state": "IDLE", "alarm": "0", "outputs": "00000", "processed": "0", "events": ""},
                {"state": "IDLE", "alarm": "0", "outputs": "00000", "processed": "0", "events": ""},
                {"state": "CHECK", "alarm": "0", "outputs": "00000", "processed": "0", "events": ""},
                {"state": "CHECK", "alarm": "0", "outputs": "00000", "processed": "0", "events": "x"}]
        self.assertEqual([rows.index(row) for row in change_rows(rows)], [0, 2, 3])


if __name__ == "__main__":
    unittest.main()

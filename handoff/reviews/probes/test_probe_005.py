"""리뷰 005 반례 탐색. 저장소 reports/·data/는 쓰지 않고 tempfile 폴더만 쓴다.

실행: py -m unittest handoff/reviews/probes/test_probe_005.py
"""

from collections import Counter
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.equipment import load_equipment  # noqa: E402
from src.generate import generate  # noqa: E402
from src.main import read_events  # noqa: E402
from src.recipe import load_recipe  # noqa: E402
from src.recipe_rules import EQUIPMENT_INPUT_COLUMNS  # noqa: E402
from src.summary import _ratio, build_analysis, build_summary  # noqa: E402
from src.trace import build_trace  # noqa: E402

CONFIG = ROOT / "recipes/generator.json"
RETEST = ROOT / "recipes/lamp_models_retest.json"
GEN_EQUIP = ROOT / "recipes/equipment_generated.json"
ENV = {**os.environ, "PYTHONPATH": str(ROOT), "PYTHONIOENCODING": "utf-8"}


def run_main(cwd, *args):
    return subprocess.run(["py", "-m", "src.main", *map(str, args)], cwd=cwd, capture_output=True, env=ENV)


def ev(seq, pid, event, inspection="", result="", model="", equipment=""):
    return dict(zip(EQUIPMENT_INPUT_COLUMNS, (str(seq), pid, event, inspection, result, model, equipment)))


class Probe005(unittest.TestCase):
    # P1: 반올림 경계값. 1/32 = 0.03125 (이진수로 정확히 표현되는 진짜 동점)
    def test_p1_ratio_half_tie_rounds_up(self):
        self.assertEqual(_ratio(1, 32), "0.0313")

    # P2: 입력 옆 meta.json이 깨진 구조(최상위 배열·키 누락)일 때
    def test_p2_malformed_meta_exits_2_without_reports(self):
        for name, content in (("array", "[]"), ("missing_keys", "{}")):
            with self.subTest(meta=name), tempfile.TemporaryDirectory() as directory:
                source = Path(directory) / "in.csv"
                shutil.copyfile(ROOT / "data/sample_events_equipment.csv", source)
                Path(str(source) + ".meta.json").write_text(content, encoding="utf-8")
                run = run_main(directory, source, "--recipe", RETEST, "--equipment",
                               ROOT / "recipes/equipment.json", "--summary")
                stderr = run.stderr.decode("utf-8", "replace")
                self.assertEqual(run.returncode, 2, stderr[-400:])
                self.assertNotIn("Traceback", stderr)

    # P3: 작은 제품 수(명세는 --products 양의 정수만 요구)
    def test_p3_small_product_counts_generate(self):
        failures = []
        with tempfile.TemporaryDirectory() as directory:
            for products in (4, 5, 6):
                for seed in range(1, 41):
                    try:
                        generate(seed, products, Path(directory) / "g.csv", CONFIG)
                    except ValueError as error:
                        failures.append((products, seed, str(error)))
        print("P3 failures:", len(failures), failures[:5])
        self.assertEqual(failures, [])

    # P4: 여러 시드에서 주입 종류별 개수 = 실제 상세 코드 거절 수, 기타 거절 0
    def test_p4_injection_matches_actual_codes_many_seeds(self):
        models = load_recipe(RETEST).models
        book = load_equipment(GEN_EQUIP, models)
        mismatches = []
        with tempfile.TemporaryDirectory() as directory:
            for seed in range(1, 21):
                path = Path(directory) / "g.csv"
                meta = generate(seed, 200, path, CONFIG)
                rows = build_summary(build_analysis(read_events(path, EQUIPMENT_INPUT_COLUMNS), models, book), meta)
                actual = {r["key"]: r["count"] for r in rows if r["section"] == "input_error_pareto"}
                stopped = next(r["value"] for r in rows if r["key"] == "equipment_stopped")
                if actual != meta["injected_errors"] or stopped != 0:
                    mismatches.append((seed, actual, meta["injected_errors"], stopped))
        self.assertEqual(mismatches, [])

    # P5: 상태 분포 6칸의 합 = 등록 제품 수 (상태 문구 누락 탐지)
    def test_p5_status_distribution_sums_to_registered(self):
        models = load_recipe(RETEST).models
        for csv_path, equip in ((ROOT / "data/generated/gen_seed42.csv", GEN_EQUIP),
                                (ROOT / "data/sample_events_equipment.csv", ROOT / "recipes/equipment.json")):
            with self.subTest(input=csv_path.name):
                book = load_equipment(equip, models)
                rows = build_summary(build_analysis(read_events(csv_path, EQUIPMENT_INPUT_COLUMNS), models, book))
                registered = next(r["value"] for r in rows if r["key"] == "registered_count")
                self.assertEqual(sum(r["count"] for r in rows if r["section"] == "status_distribution"), registered)

    # P6: 이전 단계 모드 조합 — 재검사 없는 레시피 + 설비 모드에서 사유 코드·정지 추적·history
    def test_p6_non_retest_recipe_with_equipment(self):
        models = load_recipe(ROOT / "recipes/lamp_models.json").models
        book = load_equipment(ROOT / "recipes/equipment.json", models)
        events = []
        seq = 0
        for pid, model, steps in (("a", "A", 3), ("b", "A", 3), ("c", "A", 3), ("d", "B", 2)):
            seq += 1
            events.append(ev(seq, pid, "REGISTER", model=model))
            for index in range(steps):
                seq += 1
                events.append(ev(seq, pid, "P" + str(index + 1)))
        events += [
            ev(16, "a", "INSPECT", "LEAK", "FAIL", equipment="LEAK-2"),
            ev(17, "b", "INSPECT", "LEAK", "FAIL", equipment="LEAK-2"),   # 정지
            ev(18, "c", "INSPECT", "LEAK", "PASS", equipment="LEAK-2"),   # EQUIP_STOPPED
            ev(19, "a", "RETEST_REQUEST", "LEAK"),                        # RECIPE_RETEST_DISABLED
            ev(20, "  ", "P1"),                                           # PRESERVE_EMPTY_PRODUCT
            ev(21, "d", "INSPECT", "", "PASS", equipment="LEAK-1"),       # PRESERVE_EMPTY_INSPECTION
            ev(22, "d", "INSPECT", "AIM", "PASS", equipment="LEAK-1"),    # RECIPE_UNKNOWN_INSPECTION
            ev(23, "d", "INSPECT", "LIGHT", "PASS", equipment="LIGHT-1"), # INSP_TOO_EARLY
            ev(24, "c", "INSPECT", "LEAK", "PASS", equipment="LEAK-1"),
            ev(25, "zz", "P1"),                                           # PRESERVE_UNREGISTERED
        ]
        analysis = build_analysis(events, models, book)
        rows = build_summary(analysis)
        totals = {r["key"]: r["value"] for r in rows if r["section"] == "rejection_totals"}
        pareto = {r["key"]: r["count"] for r in rows if r["section"] == "input_error_pareto"}
        self.assertEqual(totals["rejected_rows"], 7)
        self.assertEqual(totals["equipment_stopped"], 1)
        self.assertEqual(pareto, {"RECIPE_RETEST_DISABLED": 1, "PRESERVE_EMPTY_PRODUCT": 1,
                                  "PRESERVE_EMPTY_INSPECTION": 1, "RECIPE_UNKNOWN_INSPECTION": 1,
                                  "INSP_TOO_EARLY": 1, "PRESERVE_UNREGISTERED": 1})
        trace = build_trace(analysis, "c")
        stopped = [r for r in trace if r["reason"] == "정지된 설비"]
        self.assertEqual(len(stopped), 1)
        self.assertEqual((stopped[0]["stop_seq"], stopped[0]["stop_product_id"]), ("17", "b"))
        self.assertEqual((stopped[0]["cause_seqs"], stopped[0]["cause_product_ids"]), ("16;17", "a;b"))
        self.assertEqual(trace[-1]["history"], "LEAK: PASS@24[LEAK-1]")
        print("P6 inspection_metrics keys:",
              [r["key"] for r in rows if r["section"] == "inspection_metrics"])

    # P7: 시드 42 설정에서 폐기가 도달 가능한지(명세 이견 검증) — 시드 1..100, 500개
    def test_p7_discard_reachable_over_seeds(self):
        models = load_recipe(RETEST).models
        book = load_equipment(GEN_EQUIP, models)
        discards, first_fails = Counter(), 0
        with tempfile.TemporaryDirectory() as directory:
            for seed in range(1, 101):
                path = Path(directory) / "g.csv"
                generate(seed, 500, path, CONFIG)
                analysis = build_analysis(read_events(path, EQUIPMENT_INPUT_COLUMNS), models, book)
                discards[seed] = sum(p.status == "폐기" for p in analysis.process.products.values())
                first_fails += sum(item.result == "FAIL" for item in analysis.first_inspections)
        print("P7 seeds_with_discard:", sum(1 for v in discards.values() if v),
              "total_discards:", sum(discards.values()), "first_fails_total:", first_fails)
        self.assertGreater(sum(discards.values()), 0)

    # P8: 보존 조건 — 임시 폴더에서 재생성한 기존 13개 + seed42 CSV/meta/보고서 6개가 체크아웃 파일과 바이트 동일
    def test_p8_regenerated_reports_byte_identical(self):
        cases = (
            ("sample_events", ()),
            ("sample_events_v2", ("--recipe", ROOT / "recipes/lamp_models.json")),
            ("sample_events_retest", ("--recipe", RETEST)),
            ("sample_events_equipment", ("--recipe", RETEST, "--equipment", ROOT / "recipes/equipment.json")),
        )
        with tempfile.TemporaryDirectory() as directory:
            for stem, options in cases:
                run = run_main(directory, ROOT / "data" / (stem + ".csv"), *options)
                self.assertEqual(run.returncode, 0)
            gen = Path(directory) / "gen" / "gen_seed42.csv"
            generate(42, 500, gen, CONFIG)
            self.assertEqual(gen.read_bytes(), (ROOT / "data/generated/gen_seed42.csv").read_bytes())
            self.assertEqual(Path(str(gen) + ".meta.json").read_bytes(),
                             (ROOT / "data/generated/gen_seed42.csv.meta.json").read_bytes())
            run = run_main(directory, gen, "--recipe", RETEST, "--equipment", GEN_EQUIP, "--summary",
                           "--trace", "GEN_0005")
            self.assertEqual(run.returncode, 0)
            produced = sorted((Path(directory) / "reports").iterdir())
            self.assertEqual(len(produced), 19)
            for item in produced:
                with self.subTest(report=item.name):
                    self.assertEqual(item.read_bytes(), (ROOT / "reports" / item.name).read_bytes())

    # P9: 같은 --trace를 두 번, 그리고 거절만 있는 미등록 ID trace
    def test_p9_duplicate_trace_and_unregistered_only_id(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "in.csv"
            source.write_text("seq,product_id,event,inspection,result,model,equipment\n"
                              "1,x,REGISTER,,,A,\n2,ghost,P1,,,,\n", encoding="utf-8")
            run = run_main(directory, source, "--recipe", RETEST, "--equipment", ROOT / "recipes/equipment.json",
                           "--trace", "x", "--trace", "x", "--trace", "ghost")
            self.assertEqual(run.returncode, 0, run.stderr.decode("utf-8", "replace"))
            names = sorted(p.name for p in (Path(directory) / "reports").iterdir())
            self.assertIn("in_trace_x.csv", names)
            self.assertIn("in_trace_ghost.csv", names)
            ghost = (Path(directory) / "reports/in_trace_ghost.csv").read_text(encoding="utf-8-sig")
            self.assertIn("미등록", ghost)


if __name__ == "__main__":
    unittest.main()

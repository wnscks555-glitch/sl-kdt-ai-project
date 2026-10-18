"""리뷰 006 반례 탐색(리뷰 005 수정 322ec81 재검토). 저장소 reports/·data/는 쓰지 않고 tempfile 폴더만 쓴다.

실행: py -m unittest handoff/reviews/probes/test_probe_006.py
"""

import csv
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

from src.generate import generate  # noqa: E402
from src.summary import _ratio  # noqa: E402

CONFIG = ROOT / "recipes/generator.json"
RETEST = ROOT / "recipes/lamp_models_retest.json"
EQUIP = ROOT / "recipes/equipment.json"
GEN_EQUIP = ROOT / "recipes/equipment_generated.json"
FIXTURE = ROOT / "tests/fixtures/summary_events.csv"
ENV = {**os.environ, "PYTHONPATH": str(ROOT), "PYTHONIOENCODING": "utf-8"}


def run_main(cwd, *args):
    return subprocess.run(["py", "-m", "src.main", *map(str, args)], cwd=cwd, capture_output=True, env=ENV)


def run_with_meta(directory, meta_text, *extra):
    source = Path(directory) / "events.csv"
    shutil.copyfile(FIXTURE, source)
    if meta_text is not None:
        Path(str(source) + ".meta.json").write_text(meta_text, encoding="utf-8")
    return run_main(directory, source, "--recipe", RETEST, "--equipment", EQUIP, *extra)


def summary_rows(directory, section):
    path = Path(directory) / "reports/events_summary.csv"
    with path.open(encoding="utf-8-sig", newline="") as source:
        return [row for row in csv.DictReader(source) if row["section"] == section]


class Probe006(unittest.TestCase):
    # P1: 보존 조건 + 반올림 변경(M1) 영향 — 기존 샘플 4종 13개, seed42 CSV·meta·보고서 6개를 다시 만들어 체크아웃 파일과 비교
    def test_p1_regenerated_reports_byte_identical_after_rounding_change(self):
        cases = (
            ("sample_events", ()),
            ("sample_events_v2", ("--recipe", ROOT / "recipes/lamp_models.json")),
            ("sample_events_retest", ("--recipe", RETEST)),
            ("sample_events_equipment", ("--recipe", RETEST, "--equipment", EQUIP)),
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

    # P2: 반올림 경계값 추가(M1). 5/100000 = 0.00005 동점, 1/3·2/3 반복소수, 분자=분모
    def test_p2_ratio_boundaries(self):
        for numerator, denominator, expected in ((5, 100000, "0.0001"), (4, 100000, "0.0000"),
                                                 (1, 3, "0.3333"), (2, 3, "0.6667"), (7, 7, "1.0000"),
                                                 (99995, 100000, "1.0000"), (99994, 100000, "0.9999")):
            with self.subTest(numerator=numerator, denominator=denominator):
                self.assertEqual(_ratio(numerator, denominator), expected)

    # P3: Decimal 기본 정밀도(28자리) 경계. 참값 0.0000499999…(유효숫자 29자리 이상)는 0.0000이어야 한다
    def test_p3_ratio_beyond_decimal_precision(self):
        self.assertEqual(_ratio(10 ** 26 - 1, 2 * 10 ** 30), "0.0000")  # 유효숫자 26자리: 정확
        self.assertEqual(_ratio(10 ** 29 - 1, 2 * 10 ** 33), "0.0000")  # 유효숫자 29자리: 28자리에서 잘림

    # P4: meta의 injected_errors에 5종 밖의 키 → TOTAL 주입 수가 종류별 행 합과 같아야 한다(또는 거절)
    def test_p4_meta_unknown_injection_key(self):
        meta = json.dumps({"normal_rows": 24, "injected_errors": {"SEQ_SKIP": 1, "FOO": 5}})
        with tempfile.TemporaryDirectory() as directory:
            run = run_with_meta(directory, meta, "--summary")
            if run.returncode == 2:
                self.assertNotIn(b"Traceback", run.stderr)
                return
            self.assertEqual(run.returncode, 0, run.stderr.decode("utf-8", "replace"))
            rows = summary_rows(directory, "injection_comparison")
            per_kind = sum(int(row["injected_count"]) for row in rows if row["key"] != "TOTAL")
            total = next(int(row["injected_count"]) for row in rows if row["key"] == "TOTAL")
            print("P4 per_kind:", per_kind, "TOTAL:", total)
            self.assertEqual(total, per_kind)

    # P5: meta 경계값 — normal_rows 0, 일부 종류만 있음, BOM, 아주 큰 정수 → 모두 종료 0, 분모 0은 빈칸
    def test_p5_meta_valid_edge_values(self):
        metas = {
            "zero_rows": '{"normal_rows": 0, "injected_errors": {"SEQ_SKIP": 1}}',
            "partial": '{"normal_rows": 24, "injected_errors": {"SEQ_SKIP": 1}}',
            "bom": '﻿{"normal_rows": 24, "injected_errors": {}}',
            "huge": '{"normal_rows": %d, "injected_errors": {"SEQ_SKIP": 1}}' % (10 ** 30),
        }
        for name, text in metas.items():
            with self.subTest(meta=name), tempfile.TemporaryDirectory() as directory:
                run = run_with_meta(directory, text, "--summary")
                self.assertEqual(run.returncode, 0, run.stderr.decode("utf-8", "replace"))
                rows = summary_rows(directory, "injection_comparison")
                seq = next(row for row in rows if row["key"] == "SEQ_SKIP")
                if name == "zero_rows":
                    self.assertEqual(seq["injection_rate"], "")
                if name == "partial":
                    other = next(row for row in rows if row["key"] == "EQUIP_UNKNOWN")
                    self.assertEqual(other["injected_count"], "0")

    # P6: meta 비정상 — NaN·Infinity, 디렉터리로 된 meta 경로, 깨진 JSON → 종료 2, 트레이스백 없음, 보고서 미생성
    def test_p6_meta_other_malformed(self):
        for name in ("nan", "infinity", "directory", "broken_json", "nested_dict_value"):
            with self.subTest(meta=name), tempfile.TemporaryDirectory() as directory:
                source = Path(directory) / "events.csv"
                shutil.copyfile(FIXTURE, source)
                meta_path = Path(str(source) + ".meta.json")
                if name == "directory":
                    meta_path.mkdir()
                else:
                    meta_path.write_text({
                        "nan": '{"normal_rows": NaN, "injected_errors": {}}',
                        "infinity": '{"normal_rows": 24, "injected_errors": {"SEQ_SKIP": Infinity}}',
                        "broken_json": '{"normal_rows": 24,',
                        "nested_dict_value": '{"normal_rows": 24, "injected_errors": {"SEQ_SKIP": {"n": 1}}}',
                    }[name], encoding="utf-8")
                run = run_main(directory, source, "--recipe", RETEST, "--equipment", EQUIP, "--summary")
                self.assertEqual(run.returncode, 2, run.stderr.decode("utf-8", "replace")[-300:])
                self.assertNotIn(b"Traceback", run.stderr)
                self.assertFalse((Path(directory) / "reports").exists())

    # P7: 잘못된 meta가 있어도 --summary 없이 --trace만 주면 meta를 읽지 않아야 한다(이전 동작 보존)
    def test_p7_invalid_meta_ignored_without_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            run = run_with_meta(directory, "[]", "--trace", "a")
            self.assertEqual(run.returncode, 0, run.stderr.decode("utf-8", "replace")[-300:])
            names = sorted(p.name for p in (Path(directory) / "reports").iterdir())
            self.assertFalse(any(name.endswith("_summary.csv") for name in names))

    # P8: M3 — 작은 제품 수(1–8) × 시드 1–60: 실패는 ValueError + 「배정 N건, 후보 0개」 문구뿐이어야 하고 파일 미생성
    def test_p8_small_products_failures_are_explained(self):
        failures, unexplained = [], []
        with tempfile.TemporaryDirectory() as directory:
            for products in range(1, 9):
                for seed in range(1, 61):
                    out = Path(directory) / f"g_{products}_{seed}.csv"
                    try:
                        generate(seed, products, out, CONFIG)
                    except ValueError as error:
                        failures.append((products, seed, str(error)))
                        if "후보 0개" not in str(error) or "배정" not in str(error) or out.exists():
                            unexplained.append((products, seed, str(error)))
                    except Exception as error:  # noqa: BLE001
                        unexplained.append((products, seed, type(error).__name__ + ": " + str(error)))
        print("P8 failures:", len(failures), "of 480;", failures[:3])
        self.assertEqual(unexplained, [])

    # P9: README 「CSV와 meta를 쓰기 전에 중단하므로 기존 출력도 덮어쓰지 않습니다」 — 기존 파일이 있을 때 실패 실행
    def test_p9_failed_generation_keeps_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "small.csv"
            meta = Path(str(target) + ".meta.json")
            target.write_bytes(b"old-csv")
            meta.write_bytes(b"old-meta")
            result = subprocess.run(
                ["py", "-m", "src.generate", "--seed", "39", "--products", "4", "--out", str(target),
                 "--config", str(CONFIG)], cwd=directory, capture_output=True, env=ENV)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(target.read_bytes(), b"old-csv")
            self.assertEqual(meta.read_bytes(), b"old-meta")


if __name__ == "__main__":
    unittest.main()

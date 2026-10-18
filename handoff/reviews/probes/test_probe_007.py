"""리뷰 007 반례 탐색(리뷰 006 수정 d78482b 재검토). 저장소 reports/·data/는 쓰지 않고 tempfile 폴더만 쓴다.

실행: py -m unittest handoff/reviews/probes/test_probe_007.py
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
from src.reason_codes import INJECTED_ERROR_CODES  # noqa: E402

CONFIG = ROOT / "recipes/generator.json"
RETEST = ROOT / "recipes/lamp_models_retest.json"
EQUIP = ROOT / "recipes/equipment.json"
GEN_EQUIP = ROOT / "recipes/equipment_generated.json"
FIXTURE = ROOT / "tests/fixtures/summary_events.csv"
ENV = {**os.environ, "PYTHONPATH": str(ROOT), "PYTHONIOENCODING": "utf-8"}
README_CODES = ("SEQ_SKIP", "PRESERVE_BAD_RESULT", "PRESERVE_DUP_RESULT", "EQUIP_UNKNOWN", "RECIPE_UNKNOWN_STEP")


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


def stderr(run):
    return run.stderr.decode("utf-8", "replace")


class Probe007(unittest.TestCase):
    # P1: 보존 조건 — 키 검사 추가 뒤에도 생성기 meta(최상위에 다른 키 포함)가 통과하고 19개 보고서가 바이트 동일
    def test_p1_regenerated_reports_byte_identical(self):
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
            self.assertEqual(run.returncode, 0, stderr(run)[-300:])
            produced = sorted((Path(directory) / "reports").iterdir())
            self.assertEqual(len(produced), 19)
            for item in produced:
                with self.subTest(report=item.name):
                    self.assertEqual(item.read_bytes(), (ROOT / "reports" / item.name).read_bytes())

    # P2: README가 적은 5종 코드와 코드 상수가 같은지(문서·동작 일치)
    def test_p2_readme_codes_match_constant(self):
        self.assertEqual(tuple(INJECTED_ERROR_CODES), README_CODES)
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for code in README_CODES:
            self.assertIn("`" + code + "`", readme)

    # P3: 대소문자·공백만 다른 키 → 5종 코드와 정확히 같지 않으므로 종료 2, 트레이스백 없음, 보고서 미생성
    def test_p3_case_and_whitespace_keys_rejected(self):
        for key in ("seq_skip", "Seq_Skip", "SEQ_SKIP ", " SEQ_SKIP", ""):
            meta = json.dumps({"normal_rows": 24, "injected_errors": {key: 1}})
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                run = run_with_meta(directory, meta, "--summary")
                self.assertEqual(run.returncode, 2, stderr(run)[-300:])
                self.assertNotIn(b"Traceback", run.stderr)
                self.assertIn("5종", stderr(run))
                self.assertFalse((Path(directory) / "reports").exists())

    # P4: 빈 injected_errors, 5종 전부 → 종료 0, TOTAL 주입 수 = 종류별 합
    def test_p4_valid_key_sets_total_equals_sum(self):
        metas = {
            "empty": {},
            "all_five": {code: index + 1 for index, code in enumerate(README_CODES)},
            "zeros": {code: 0 for code in README_CODES},
        }
        for name, injected in metas.items():
            meta = json.dumps({"normal_rows": 24, "injected_errors": injected})
            with self.subTest(meta=name), tempfile.TemporaryDirectory() as directory:
                run = run_with_meta(directory, meta, "--summary")
                self.assertEqual(run.returncode, 0, stderr(run)[-300:])
                rows = summary_rows(directory, "injection_comparison")
                self.assertEqual([row["key"] for row in rows], [*README_CODES, "TOTAL"])
                per_kind = sum(int(row["injected_count"]) for row in rows if row["key"] != "TOTAL")
                total = next(int(row["injected_count"]) for row in rows if row["key"] == "TOTAL")
                self.assertEqual(total, per_kind)
                self.assertEqual(total, sum(injected.values()))

    # P5: 최상위 meta의 다른 키(seed, version, FOO)는 README가 제한하지 않음 → 종료 0
    def test_p5_extra_top_level_keys_allowed(self):
        meta = json.dumps({"normal_rows": 24, "injected_errors": {"SEQ_SKIP": 1}, "seed": 42, "FOO": [1]})
        with tempfile.TemporaryDirectory() as directory:
            run = run_with_meta(directory, meta, "--summary")
            self.assertEqual(run.returncode, 0, stderr(run)[-300:])

    # P6: 알 수 없는 키 + --trace 동시 → 종료 2이고 trace·기본 보고서도 하나도 쓰지 않음(README 「보고서를 쓰지 않습니다」)
    def test_p6_unknown_key_with_trace_writes_nothing(self):
        meta = json.dumps({"normal_rows": 24, "injected_errors": {"SEQ_SKIP": 1, "EQUIP_STOPPED": 0}})
        with tempfile.TemporaryDirectory() as directory:
            run = run_with_meta(directory, meta, "--summary", "--trace", "a")
            self.assertEqual(run.returncode, 2, stderr(run)[-300:])
            self.assertNotIn(b"Traceback", run.stderr)
            self.assertFalse((Path(directory) / "reports").exists())

    # P7: 값 타입 오류와 키 오류가 겹친 meta({"FOO": "x"}) → 어느 검사가 먼저든 종료 2, 트레이스백 없음
    def test_p7_unknown_key_and_bad_value_overlap(self):
        meta = json.dumps({"normal_rows": 24, "injected_errors": {"FOO": "x"}})
        with tempfile.TemporaryDirectory() as directory:
            run = run_with_meta(directory, meta, "--summary")
            self.assertEqual(run.returncode, 2, stderr(run)[-300:])
            self.assertNotIn(b"Traceback", run.stderr)

    # P8: 같은 키가 두 번 나온 JSON → json 표준 동작(마지막 값)으로 처리되는지 기록. 명세·README 모두 다루지 않음
    def test_p8_duplicate_json_key_behaviour(self):
        meta = '{"normal_rows": 24, "injected_errors": {"SEQ_SKIP": 1, "SEQ_SKIP": 5}}'
        with tempfile.TemporaryDirectory() as directory:
            run = run_with_meta(directory, meta, "--summary")
            self.assertEqual(run.returncode, 0, stderr(run)[-300:])
            rows = summary_rows(directory, "injection_comparison")
            seq = next(row for row in rows if row["key"] == "SEQ_SKIP")
            print("P8 duplicate key SEQ_SKIP injected_count:", seq["injected_count"])
            self.assertEqual(seq["injected_count"], "5")

    # P9: 잘못된 키 meta가 있어도 --summary 없이 기본 실행·--trace만 → meta를 읽지 않음(3단계·이전 동작 보존)
    def test_p9_unknown_key_meta_ignored_without_summary(self):
        meta = json.dumps({"normal_rows": 24, "injected_errors": {"FOO": 1}})
        for extra in ((), ("--trace", "a")):
            with self.subTest(extra=extra), tempfile.TemporaryDirectory() as directory:
                run = run_with_meta(directory, meta, *extra)
                self.assertEqual(run.returncode, 0, stderr(run)[-300:])
                names = sorted(p.name for p in (Path(directory) / "reports").iterdir())
                self.assertFalse(any(name.endswith("_summary.csv") for name in names))


if __name__ == "__main__":
    unittest.main()

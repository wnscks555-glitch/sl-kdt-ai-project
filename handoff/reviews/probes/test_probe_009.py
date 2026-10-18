"""리뷰 009 반례 탐색(리뷰 008 M1 반영, ff8381b..3acd10b). 저장소 reports/·data/는 쓰지 않고 tempfile 폴더만 쓴다.

실행: py -m unittest handoff/reviews/probes/test_probe_009.py
"""

import csv
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.generate import generate  # noqa: E402

CONFIG = ROOT / "recipes/generator.json"
RETEST = ROOT / "recipes/lamp_models_retest.json"
EQUIP = ROOT / "recipes/equipment.json"
GEN_EQUIP = ROOT / "recipes/equipment_generated.json"
FIXTURE = ROOT / "tests/fixtures/summary_events.csv"
ENV = {**os.environ, "PYTHONPATH": str(ROOT), "PYTHONIOENCODING": "utf-8"}
DEFECT_KEYS = ("defective_discarded", "defective_held", "defective_completed", "defective_other", "normal_discarded")


def run_main(cwd, *args, env=ENV):
    return subprocess.run(["py", "-m", "src.main", *map(str, args)], cwd=cwd, capture_output=True, env=env)


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def defect_counts(directory, stem):
    rows = {row["key"]: row for row in read_csv(Path(directory) / "reports" / (stem + "_summary.csv"))
            if row["section"] == "injection_comparison"}
    return tuple(int(rows[key]["count"]) for key in DEFECT_KEYS)


def stderr(run):
    return run.stderr.decode("utf-8", "replace")


def write_input(directory, extra_rows, meta, base=True):
    source = Path(directory) / "events.csv"
    content = FIXTURE.read_bytes() if base else b"seq,product_id,event,inspection,result,model,equipment\n"
    source.write_bytes(content + "".join(row + "\n" for row in extra_rows).encode("utf-8"))
    if meta is not None:
        Path(str(source) + ".meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    return source


def meta_with(defective):
    return {"normal_rows": 26, "injected_errors": {}, "defective_products": defective}


def summary(directory, source, *extra, env=ENV):
    return run_main(directory, source, "--recipe", RETEST, "--equipment", EQUIP, "--summary", *extra, env=env)


class Probe009(unittest.TestCase):
    # P1: 보존 — 기존 샘플 13개 + seed42 CSV·meta 재생성, 그 보고서 6개가 체크아웃 파일과 바이트 동일
    def test_p1_existing_and_seed42_reports_byte_identical(self):
        cases = (
            ("sample_events", ()),
            ("sample_events_v2", ("--recipe", ROOT / "recipes/lamp_models.json")),
            ("sample_events_retest", ("--recipe", RETEST)),
            ("sample_events_equipment", ("--recipe", RETEST, "--equipment", EQUIP)),
        )
        with tempfile.TemporaryDirectory() as directory:
            for stem, options in cases:
                self.assertEqual(run_main(directory, ROOT / "data" / (stem + ".csv"), *options).returncode, 0)
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

    # P2: 새 검사가 생성기 자신의 meta를 거절하지 않는가 — 결함 확률을 0.5로 올리고 여러 시드·소량/대량 생성
    def test_p2_generator_meta_never_rejected(self):
        config = json.loads(CONFIG.read_text(encoding="utf-8-sig"))
        config["defective_product_probability"] = 0.5
        config["recipe"] = str(ROOT / "recipes" / config["recipe"])
        config["equipment"] = str(ROOT / "recipes" / config["equipment"])
        observed = []
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "c.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            for seed in (1, 2, 3, 99):
                for count in (5, 60, 400):
                    with self.subTest(seed=seed, count=count):
                        out = Path(directory) / ("g%d_%d.csv" % (seed, count))
                        try:
                            meta = generate(seed, count, out, path)
                        except Exception as error:  # 소량 생성 실패는 리뷰 006에서 공개된 기존 동작
                            observed.append((seed, count, "gen-fail", type(error).__name__))
                            continue
                        run = run_main(directory, out, "--recipe", RETEST, "--equipment", GEN_EQUIP, "--summary")
                        observed.append((seed, count, run.returncode, len(meta["defective_products"])))
                        self.assertEqual(run.returncode, 0, stderr(run)[-300:])
                        self.assertEqual(sum(defect_counts(directory, out.stem)[:4]),
                                         len(meta["defective_products"]))
        print("P2", observed)

    # P3: CSV에 실제로 공백 포함 ID " A "가 등록된 경우 — 정확히 같은 " A "는 허용, "A"·"a"는 거절
    def test_p3_whitespace_id_registered_through_csv(self):
        rows = ["27, A ,REGISTER,,,A,"]
        for defective, code in (([" A "], 0), (["A"], 2), (["a", " A "], 0)):
            with self.subTest(defective=defective), tempfile.TemporaryDirectory() as directory:
                run = summary(directory, write_input(directory, rows, meta_with(defective)))
                self.assertEqual(run.returncode, code, stderr(run)[-300:])
                if code == 0:
                    self.assertEqual(sum(defect_counts(directory, "events")[:4]), len(defective))

    # P4: 첫 REGISTER가 거절된 뒤 같은 ID가 다시 등록되어 허용된 경우 → 등록 제품. 그 밖(등록 상태)으로 셈
    def test_p4_rejected_then_accepted_registration(self):
        rows = ["27,ghost,REGISTER,,,UNKNOWN,", "28,ghost,REGISTER,,,B,"]
        with tempfile.TemporaryDirectory() as directory:
            run = summary(directory, write_input(directory, rows, meta_with(["ghost"])))
            self.assertEqual(run.returncode, 0, stderr(run)[-300:])
            self.assertEqual(defect_counts(directory, "events"), (0, 0, 0, 1, 0))
            products = {row["product_id"]: row["state"] for row in
                        read_csv(Path(directory) / "reports/events_products.csv")}
            print("P4 ghost state", products["ghost"])

    # P5: 등록 없이 공정·검사 행만 있는(모두 거절된) ID → 등록 제품이 아니므로 종료 2, 보고서 미생성
    def test_p5_id_only_in_rejected_non_register_rows(self):
        rows = ["27,zz,P1,,,,", "28,zz,INSPECT,LEAK,FAIL,,LEAK-1"]
        with tempfile.TemporaryDirectory() as directory:
            run = summary(directory, write_input(directory, rows, meta_with(["zz"])))
            self.assertEqual(run.returncode, 2, stderr(run)[-300:])
            self.assertIn("등록되지 않은", stderr(run))
            self.assertFalse((Path(directory) / "reports").exists())

    # P6: 같은 ID 중복 REGISTER(두 번째 거절) → 한 제품. 결함 1건으로만 셈
    def test_p6_duplicate_register_counts_once(self):
        rows = ["27,a,REGISTER,,,A,"]
        with tempfile.TemporaryDirectory() as directory:
            run = summary(directory, write_input(directory, rows, meta_with(["a"])))
            self.assertEqual(run.returncode, 0, stderr(run)[-300:])
            self.assertEqual(defect_counts(directory, "events"), (0, 0, 1, 0, 0))

    # P7: cp949로 표현할 수 없는 미등록 ID(이모지)를 PYTHONIOENCODING 없이 실행 → 트레이스백 없이 종료 2
    def test_p7_unencodable_unregistered_id_without_utf8_env(self):
        env = {key: value for key, value in ENV.items() if key != "PYTHONIOENCODING"}
        with tempfile.TemporaryDirectory() as directory:
            run = summary(directory, write_input(directory, [], meta_with(["\U0001F4A1lamp"])), env=env)
            print("P7", run.returncode, run.stderr[-120:])
            self.assertEqual(run.returncode, 2)
            self.assertNotIn(b"Traceback", run.stderr)
            self.assertFalse((Path(directory) / "reports").exists())

    # P8: 빈 목록 [] → 결함품 0개(README). 종료 0, 결함 4행 0, 정상품 폐기 = 전체 폐기(0)
    def test_p8_empty_list(self):
        with tempfile.TemporaryDirectory() as directory:
            run = summary(directory, write_input(directory, [], meta_with([])))
            self.assertEqual(run.returncode, 0, stderr(run)[-300:])
            self.assertEqual(defect_counts(directory, "events"), (0, 0, 0, 0, 0))

    # P9: 미등록 ID 여러 개 — 메시지가 해시 시드와 무관하게 같은가(같은 입력 같은 결과)
    def test_p9_error_message_deterministic(self):
        messages = set()
        for hashseed in ("0", "1", "12345"):
            with tempfile.TemporaryDirectory() as directory:
                source = write_input(directory, [], meta_with(["zeta", "a", "Beta", "alpha", "가"]))
                run = summary(directory, source, env={**ENV, "PYTHONHASHSEED": hashseed})
                self.assertEqual(run.returncode, 2)
                messages.add(run.stderr)
        print("P9", [message.decode("utf-8") for message in messages])
        self.assertEqual(len(messages), 1)
        self.assertIn("['Beta', 'alpha', 'zeta', '가']", messages.pop().decode("utf-8"))

    # P10: 이전 실행이 남긴 reports/ 파일이 있을 때 미등록 ID로 실패 → 기존 파일을 덮어쓰지 않음, 보고서 표 출력 없음
    def test_p10_existing_reports_untouched_on_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            reports = Path(directory) / "reports"
            reports.mkdir()
            sentinels = {name: ("old " + name).encode() for name in
                         ("events_rows.csv", "events_summary.csv", "events_trace_a.csv")}
            for name, content in sentinels.items():
                (reports / name).write_bytes(content)
            run = summary(directory, write_input(directory, [], meta_with(["a", "ZZZ"])), "--trace", "a")
            self.assertEqual(run.returncode, 2)
            self.assertEqual(sorted(path.name for path in reports.iterdir()), sorted(sentinels))
            for name, content in sentinels.items():
                self.assertEqual((reports / name).read_bytes(), content)
            self.assertNotIn("저장 파일".encode("utf-8"), run.stdout)

    # P11: 미등록 ID가 든 meta 옆에서 --summary 없이(기본·--trace만) 실행 → meta를 읽지 않으므로 종료 0(이전 동작 보존)
    def test_p11_unregistered_meta_ignored_without_summary(self):
        for extra in ((), ("--trace", "a")):
            with self.subTest(extra=extra), tempfile.TemporaryDirectory() as directory:
                source = write_input(directory, [], meta_with(["ZZZ"]))
                run = run_main(directory, source, "--recipe", RETEST, "--equipment", EQUIP, *extra)
                self.assertEqual(run.returncode, 0, stderr(run)[-300:])
                self.assertFalse((Path(directory) / "reports/events_summary.csv").exists())

    # P12: 규칙 겹침 — 구조 오류(중복)와 미등록 ID가 함께 있으면 구조 오류가 먼저(메시지 하나, 종료 2)
    def test_p12_structure_error_precedes_unregistered(self):
        with tempfile.TemporaryDirectory() as directory:
            run = summary(directory, write_input(directory, [], meta_with(["ZZZ", "ZZZ"])))
            self.assertEqual(run.returncode, 2)
            self.assertIn("중복", stderr(run))
            self.assertNotIn("등록되지 않은", stderr(run))


if __name__ == "__main__":
    unittest.main()

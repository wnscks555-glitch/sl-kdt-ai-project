"""리뷰 008 반례 탐색(수정 1 · T44·T51, a1ed98f..0aa3d9a). 저장소 reports/·data/는 쓰지 않고 tempfile 폴더만 쓴다.

실행: py -m unittest handoff/reviews/probes/test_probe_008.py
"""

from collections import Counter
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

CONFIG = ROOT / "recipes/generator.json"
RETEST = ROOT / "recipes/lamp_models_retest.json"
EQUIP = ROOT / "recipes/equipment.json"
GEN_EQUIP = ROOT / "recipes/equipment_generated.json"
FIXTURE = ROOT / "tests/fixtures/summary_events.csv"
ENV = {**os.environ, "PYTHONPATH": str(ROOT), "PYTHONIOENCODING": "utf-8"}
DEFECT_KEYS = ("defective_discarded", "defective_held", "defective_completed", "defective_other", "normal_discarded")


def run_main(cwd, *args):
    return subprocess.run(["py", "-m", "src.main", *map(str, args)], cwd=cwd, capture_output=True, env=ENV)


def run_generate(cwd, *args):
    return subprocess.run(["py", "-m", "src.generate", *map(str, args)], cwd=cwd, capture_output=True, env=ENV)


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def section(directory, stem, name):
    return [row for row in read_csv(Path(directory) / "reports" / (stem + "_summary.csv")) if row["section"] == name]


def defect_counts(directory, stem):
    rows = {row["key"]: row for row in section(directory, stem, "injection_comparison")}
    return tuple(int(rows[key]["count"]) for key in DEFECT_KEYS)


def stderr(run):
    return run.stderr.decode("utf-8", "replace")


def fixture_with_meta(directory, meta):
    source = Path(directory) / "events.csv"
    shutil.copyfile(FIXTURE, source)
    Path(str(source) + ".meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return source


class Probe008(unittest.TestCase):
    # P1: 보존 조건 — 기존 샘플 13개 + seed42 CSV·meta·보고서 6개가 재생성 시 바이트 동일
    def test_p1_regenerated_reports_byte_identical(self):
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

    # P2: summary 결함 분포를 products 보고서와 meta로 독립 재계산(seed 42/500, 7/200, 43/300)
    #     + 결함품 수 = 목록 길이, CSV 7열, 결함품의 검사 FAIL 비율이 정상품보다 확연히 높음
    def test_p2_independent_recount_of_defect_distribution(self):
        for seed, count in ((42, 500), (7, 200), (43, 300)):
            with self.subTest(seed=seed), tempfile.TemporaryDirectory() as directory:
                gen = Path(directory) / ("g" + str(seed) + ".csv")
                meta = generate(seed, count, gen, CONFIG)
                self.assertEqual(meta["defective_count"], len(meta["defective_products"]))
                events = read_csv(gen)
                self.assertEqual(list(events[0]), ["seq", "product_id", "event", "inspection", "result",
                                                   "model", "equipment"])
                run = run_main(directory, gen, "--recipe", RETEST, "--equipment", GEN_EQUIP, "--summary")
                self.assertEqual(run.returncode, 0, stderr(run)[-300:])
                products = {row["product_id"]: row["state"] for row in read_csv(
                    Path(directory) / "reports" / (gen.stem + "_products.csv"))}
                defective = set(meta["defective_products"])
                states = Counter(products[pid] for pid in defective)
                expected = (states["폐기"], states["보류"], states["레시피 모의 흐름 완료"],
                            len(defective) - states["폐기"] - states["보류"] - states["레시피 모의 흐름 완료"],
                            sum(1 for pid, state in products.items() if state == "폐기" and pid not in defective))
                self.assertEqual(defect_counts(directory, gen.stem), expected)
                fails = {True: Counter(), False: Counter()}
                for row in events:
                    if row["event"] == "INSPECT" and row["result"] in ("PASS", "FAIL"):
                        fails[row["product_id"] in defective][row["result"]] += 1
                rate = {key: value["FAIL"] / max(1, sum(value.values())) for key, value in fails.items()}
                print(f"P2 seed={seed} defective={len(defective)} dist={expected} fail_rate={rate}")
                if defective:
                    self.assertGreater(rate[True], 0.5)
                self.assertLess(rate[False], 0.2)

    # P3: 숨은 진실 격리 — seed42 summary에서 defective_products를 지워도 결함 5행 외 모든 행·trace가 동일
    def test_p3_hidden_truth_does_not_leak_into_other_sections(self):
        with tempfile.TemporaryDirectory() as directory:
            outputs = {}
            for name, drop in (("with", False), ("without", True)):
                sub = Path(directory) / name
                sub.mkdir()
                source = sub / "g.csv"
                shutil.copyfile(ROOT / "data/generated/gen_seed42.csv", source)
                meta = json.loads((ROOT / "data/generated/gen_seed42.csv.meta.json").read_text(encoding="utf-8"))
                if drop:
                    del meta["defective_products"]
                Path(str(source) + ".meta.json").write_text(json.dumps(meta), encoding="utf-8")
                run = run_main(sub, source, "--recipe", RETEST, "--equipment", GEN_EQUIP, "--summary",
                               "--trace", "GEN_0019")
                self.assertEqual(run.returncode, 0, stderr(run)[-300:])
                outputs[name] = sub
            with_rows = read_csv(outputs["with"] / "reports/g_summary.csv")
            without_rows = read_csv(outputs["without"] / "reports/g_summary.csv")
            self.assertEqual([row for row in with_rows if row["key"] not in DEFECT_KEYS], without_rows)
            self.assertEqual(len(with_rows) - len(without_rows), 5)
            for report in ("g_rows.csv", "g_products.csv", "g_rejections.csv", "g_equipment.csv",
                           "g_trace_GEN_0019.csv"):
                with self.subTest(report=report):
                    self.assertEqual((outputs["with"] / "reports" / report).read_bytes(),
                                     (outputs["without"] / "reports" / report).read_bytes())

    # P4: defective_products에 입력에 없는 ID·대소문자만 다른 ID·앞뒤 공백 ID.
    #     명세: 「제품 ID 문자열 배열, 중복 불가」만 검사. 등록 여부는 명세가 다루지 않음 → 동작 기록.
    def test_p4_unknown_or_case_variant_ids(self):
        observed = {}
        for name, ids in (("unknown", ["ZZZ"]), ("case", ["A"]), ("space", [" a"]), ("mixed", ["a", "ZZZ"])):
            with self.subTest(ids=ids), tempfile.TemporaryDirectory() as directory:
                source = fixture_with_meta(directory, {"normal_rows": 24, "injected_errors": {},
                                                       "defective_products": ids})
                run = run_main(directory, source, "--recipe", RETEST, "--equipment", EQUIP, "--summary")
                observed[name] = (run.returncode, defect_counts(directory, "events") if run.returncode == 0 else None)
        print("P4", observed)
        # 실제 동작 고정: 모두 종료 0, 입력에 없는 ID는 「그 밖」(defective_other)으로 셈
        self.assertEqual(observed["unknown"], (0, (0, 0, 0, 1, 0)))
        self.assertEqual(observed["case"], (0, (0, 0, 0, 1, 0)))
        self.assertEqual(observed["space"], (0, (0, 0, 0, 1, 0)))
        self.assertEqual(observed["mixed"][1][3], 1)

    # P5: defective_count와 목록 길이가 다른 meta(손으로 고친 경우) → 명세 T51 「결함품 수 = 목록 길이」
    #     main.py는 defective_count를 검사하지 않음 → 동작 기록
    def test_p5_defective_count_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            source = fixture_with_meta(directory, {"normal_rows": 24, "injected_errors": {},
                                                   "defective_count": 99, "defective_products": ["a"]})
            run = run_main(directory, source, "--recipe", RETEST, "--equipment", EQUIP, "--summary")
            print("P5 returncode", run.returncode)
            self.assertEqual(run.returncode, 0)
            self.assertEqual(sum(defect_counts(directory, "events")[:4]), 1)
            joined = json.dumps(section(directory, "events", "injection_comparison"), ensure_ascii=False)
            self.assertNotIn("99", joined)

    # P6: 잘못된 defective_products meta가 옆에 있어도 --summary 없는 실행(기본·--trace만)은 meta를 읽지 않음(보존)
    def test_p6_invalid_defect_meta_ignored_without_summary(self):
        for extra in ((), ("--trace", "a")):
            with self.subTest(extra=extra), tempfile.TemporaryDirectory() as directory:
                source = fixture_with_meta(directory, {"normal_rows": 24, "injected_errors": {},
                                                       "defective_products": ["a", "a"]})
                run = run_main(directory, source, "--recipe", RETEST, "--equipment", EQUIP, *extra)
                self.assertEqual(run.returncode, 0, stderr(run)[-300:])
                self.assertFalse((Path(directory) / "reports/events_summary.csv").exists())

    # P7: 결함 키가 없는 이전 설정으로 생성 → 트레이스백 없이 종료 2, CSV·meta 미생성
    def test_p7_old_config_without_defect_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            config = json.loads(CONFIG.read_text(encoding="utf-8-sig"))
            config.pop("defective_product_probability")
            config.pop("defective_fail_probability")
            config["recipe"] = str(ROOT / "recipes" / config["recipe"])
            config["equipment"] = str(ROOT / "recipes" / config["equipment"])
            path = Path(directory) / "old.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            out = Path(directory) / "o.csv"
            run = run_generate(directory, "--seed", 1, "--products", 20, "--config", path, "--out", out)
            print("P7", run.returncode, stderr(run).strip())
            self.assertEqual(run.returncode, 2)
            self.assertNotIn("Traceback", stderr(run))
            self.assertFalse(out.exists())

    # P8: 경계 — 결함 확률 1.0(모든 제품 결함)·0.0(결함 없음). 결함 1.0이면 생성이 막혀도 숨김 없이 종료 2이거나,
    #     생성되면 목록 = 전체 제품. 0.0이면 빈 목록이고 summary 결함 행은 모두 0, normal_discarded = 전체 폐기
    def test_p8_defect_probability_boundaries(self):
        for probability in (1.0, 0.0):
            with self.subTest(p=probability), tempfile.TemporaryDirectory() as directory:
                config = json.loads(CONFIG.read_text(encoding="utf-8-sig"))
                config["defective_product_probability"] = probability
                config["recipe"] = str(ROOT / "recipes" / config["recipe"])
                config["equipment"] = str(ROOT / "recipes" / config["equipment"])
                path = Path(directory) / "c.json"
                path.write_text(json.dumps(config), encoding="utf-8")
                out = Path(directory) / "b.csv"
                run = run_generate(directory, "--seed", 42, "--products", 200, "--config", path, "--out", out)
                print("P8", probability, run.returncode, stderr(run).strip()[:200])
                self.assertNotIn("Traceback", stderr(run))
                if run.returncode != 0:
                    self.assertEqual(run.returncode, 2)
                    self.assertFalse(out.exists())
                    continue
                meta = json.loads(Path(str(out) + ".meta.json").read_text(encoding="utf-8"))
                self.assertEqual(meta["defective_count"], 200 if probability else 0)
                run = run_main(directory, out, "--recipe", RETEST, "--equipment", GEN_EQUIP, "--summary")
                self.assertEqual(run.returncode, 0, stderr(run)[-300:])
                counts = defect_counts(directory, "b")
                discarded = int(next(row for row in section(directory, "b", "status_distribution")
                                     if row["key"] == "폐기")["count"]) if probability == 0.0 else None
                print("P8 dist", probability, counts)
                if probability == 0.0:
                    self.assertEqual(counts[:4], (0, 0, 0, 0))
                    self.assertEqual(counts[4], discarded)
                else:
                    self.assertEqual(sum(counts[:4]), 200)
                    self.assertEqual(counts[4], 0)


if __name__ == "__main__":
    unittest.main()

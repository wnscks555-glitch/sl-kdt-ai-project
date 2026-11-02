import csv
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

from src.secom import (
    MIN_PHASE1, SYNTHETIC_RUNS, SecomError, chart_rates, feature_rows, lag1, load_settings, moments, moving_range,
    read_rows, split_point, synthetic_rates,
)


ROOT = Path(__file__).resolve().parents[1]
ANOMALY = ROOT / "recipes" / "anomaly_lamp.json"
OUTPUTS = ("secom_check_features.csv", "secom_check_summary.csv", "secom_check.md")


def stamp(index):
    return "%02d/07/2008 %02d:%02d:00" % (1 + index // 1440, index // 60 % 24, index % 60)


def fixture(rows=80, seed=3):
    """특징 4개: 정상, 상수, 결측 많음, 오른쪽 꼬리. 10행마다 불합격."""
    rng = random.Random(seed)
    data, labels = [], []
    for index in range(rows):
        values = ["%.4f" % rng.gauss(10, 1), "5", "NaN" if index % 3 == 0 else "%.4f" % rng.gauss(0, 1),
                  "%.4f" % rng.expovariate(1)]
        data.append(" ".join(values))
        labels.append('%s "%s"' % ("1" if index % 10 == 9 else "-1", stamp(index)))
    return "\n".join(data) + "\n", "\n".join(labels) + "\n"


def settings_dict(data_hash, label_hash, **changes):
    base = {"data": "secom.data", "labels": "secom_labels.data", "data_sha256": data_hash, "labels_sha256": label_hash,
            "anomaly": str(ANOMALY), "max_missing": "0.05", "phase1_share": "0.5", "ewma_lambda": 0.2, "ewma_l": 3,
            "skew_limit": 1, "kurtosis_limit": 3, "autocorr_limit": "0.2", "rate_limit": "0.01"}
    base.update(changes)
    return base


def write_case(folder, data_text, label_text, **changes):
    folder = Path(folder)
    (folder / "recipes").mkdir(exist_ok=True)
    (folder / "recipes" / "secom.data").write_bytes(data_text.encode("utf-8"))
    (folder / "recipes" / "secom_labels.data").write_bytes(label_text.encode("utf-8"))
    hashes = [hashlib.sha256(text.encode("utf-8")).hexdigest() for text in (data_text, label_text)]
    config = folder / "recipes" / "secom_check.json"
    config.write_text(json.dumps(settings_dict(*hashes, **changes)), encoding="utf-8")
    return config


def run_cli(folder, seed="0"):
    environment = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1",
                       PYTHONHASHSEED=seed)
    return subprocess.run([sys.executable, "-m", "src.secom", "recipes/secom_check.json"], cwd=str(folder),
                          env=environment, capture_output=True, text=True, encoding="utf-8")


class FormulaTests(unittest.TestCase):
    def test_t284_time_order_is_stable(self):
        data = "1\n2\n3\n"
        labels = '-1 "02/07/2008 10:00:00"\n-1 "01/07/2008 10:00:00"\n1 "02/07/2008 10:00:00"\n'
        rows = read_rows(data, labels)
        self.assertEqual([row[1] for row in rows], [1, 0, 2])
        self.assertEqual([row[2] for row in rows], [True, True, False])

    def test_t285_split(self):
        self.assertEqual((split_point(10, Fraction(1, 2)), split_point(11, Fraction(1, 2))), (5, 5))

    def test_t287_moving_range_skips_missing_values(self):
        self.assertEqual(moving_range([1.0, 3.0, 6.0]), 2.5)
        self.assertEqual(moving_range([4.0]), 0.0)

    def test_t288_moments(self):
        skew, kurtosis = moments([1.0, 2.0, 3.0])
        self.assertAlmostEqual(skew, 0.0)
        self.assertAlmostEqual(kurtosis, -1.5)
        skew, _ = moments([0.0, 0.0, 0.0, 3.0])
        self.assertAlmostEqual(skew, 1.1547005, places=6)
        self.assertEqual(moments([2.0, 2.0]), (None, None))

    def test_t289_lag1(self):
        self.assertAlmostEqual(lag1([1.0, 3.0, 2.0, 4.0]), -0.35)
        self.assertGreater(lag1([1.0, 2.0, 3.0, 4.0, 5.0]), 0)
        self.assertIsNone(lag1([7.0, 7.0]))

    def test_t290_rate_counts_only_phase2_values(self):
        settings = load_settings(write_case(tempfile.mkdtemp(), *fixture()))
        phase1 = [10.0, 11.0] * 20
        sigma, i_rate, _ = chart_rates(phase1, [10.5, 10.5 + 3 * (1 / 1.128) + 0.01, 10.5 - 4], settings)
        self.assertAlmostEqual(sigma, 1 / 1.128)
        self.assertEqual(i_rate, Fraction(2, 3))
        self.assertEqual(chart_rates(phase1, [], settings)[1:], (None, None))

    def test_t291_ewma_by_hand(self):
        settings = load_settings(write_case(tempfile.mkdtemp(), *fixture()))
        phase1 = [-1.0, 1.0] * 20
        sigma = 2 / 1.128
        z = 0.0
        alarms = 0
        series = [1.0, 1.0, 1.0, 5.0, 5.0, 5.0, 0.0]
        for t, value in enumerate(series, 1):
            z = 0.2 * value + 0.8 * z
            limit = 3 * sigma * math.sqrt(0.2 / 1.8 * (1 - 0.8 ** (2 * t)))
            alarms += abs(z) > limit
        self.assertGreater(alarms, 0)
        self.assertEqual(chart_rates(phase1, series, settings)[2], Fraction(alarms, len(series)))

    def test_t286_selection_reasons(self):
        rows = read_rows(*fixture())
        settings = load_settings(write_case(tempfile.mkdtemp(), *fixture()))
        _, features = feature_rows(rows, settings)
        self.assertEqual([row["reason"] for row in features], ["", "상수", "1단계 결측 초과", ""])
        short = read_rows(*fixture(rows=2 * MIN_PHASE1 - 2))
        _, features = feature_rows(short, settings)
        self.assertEqual(features[0]["reason"], "1단계 값 부족")

    def test_t286_missing_uses_phase1_only(self):
        data, labels = fixture()
        lines = data.splitlines()
        changed = [line if index < 40 else "NaN " + " ".join(line.split()[1:]) for index, line in enumerate(lines)]
        settings = load_settings(write_case(tempfile.mkdtemp(), *fixture()))
        _, features = feature_rows(read_rows("\n".join(changed) + "\n", labels), settings)
        self.assertEqual(features[0]["reason"], "2단계 값 없음")
        self.assertEqual(features[0]["missing1"], "0.0000")

    def test_t296_synthetic_rows(self):
        settings = load_settings(write_case(tempfile.mkdtemp(), *fixture()))
        seeds, rates = synthetic_rates(settings, 50, 60)
        self.assertEqual(len(seeds), SYNTHETIC_RUNS)
        self.assertEqual(set(rates), {"pure", "mixed"})
        self.assertNotEqual(rates["pure"], rates["mixed"])


class SettingsTests(unittest.TestCase):
    def refused(self, **changes):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(SecomError):
                load_settings(write_case(folder, *fixture(), **changes))

    def test_t293_bad_settings(self):
        for key, value in (("phase1_share", "0"), ("phase1_share", "1"), ("max_missing", True), ("ewma_l", "x"),
                           ("data_sha256", "abc"), ("data", ""), ("rate_limit", "1")):
            with self.subTest(key=key, value=value):
                self.refused(**{key: value})
        with tempfile.TemporaryDirectory() as folder:
            config = write_case(folder, *fixture())
            data = json.loads(config.read_text(encoding="utf-8"))
            for broken in ({k: v for k, v in data.items() if k != "anomaly"}, dict(data, extra=1)):
                config.write_text(json.dumps(broken), encoding="utf-8")
                with self.assertRaises(SecomError):
                    load_settings(config)
            config.write_text(json.dumps(data).replace('"0.05"', "NaN"), encoding="utf-8")
            with self.assertRaises(SecomError):
                load_settings(config)
            config.write_text('{"data":', encoding="utf-8")
            with self.assertRaises(SecomError):
                load_settings(config)


class RunTests(unittest.TestCase):
    def refused(self, data_text, label_text, **changes):
        with tempfile.TemporaryDirectory() as folder:
            write_case(folder, data_text, label_text, **changes)
            result = run_cli(folder)
            self.assertEqual(result.returncode, 2, result.stderr)
            for name in OUTPUTS:
                self.assertFalse((Path(folder) / "reports" / name).exists())

    def test_t292_bad_inputs(self):
        data, labels = fixture()
        self.refused(data, labels, data_sha256="0" * 64)
        self.refused(data, "\n".join(labels.splitlines()[:-1]) + "\n")
        self.refused(data, labels.replace('-1 "', '0 "', 1))
        self.refused(data, labels.replace("/07/2008", "-07-2008", 1))
        self.refused(data.replace(" 5 ", " abc ", 1), labels)
        self.refused(data.replace(" 5 ", " inf ", 1), labels)
        self.refused(data.replace(" 5 ", " ", 1), labels)
        self.refused("", "")

    def test_review028_no_pass_rows_is_reported(self):
        data, labels = fixture()
        for mode in ("all", "first", "second"):
            changed = []
            for index, line in enumerate(labels.splitlines()):
                fail = mode == "all" or (mode == "first" and index < 40) or (mode == "second" and index >= 40)
                changed.append(("1" if fail else "-1") + line[line.index(" "):])
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                write_case(folder, data, "\n".join(changed) + "\n")
                result = run_cli(folder)
                self.assertEqual(result.returncode, 0, result.stderr)
                text = (Path(folder) / "reports" / "secom_check_summary.csv").read_text(encoding="utf-8-sig")
                self.assertIn("합성 비교를 계산하지 않음", text)

    def test_review028_hard_link_to_data_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            config = write_case(folder, *fixture())
            (Path(folder) / "reports").mkdir()
            source = Path(folder) / "recipes" / "secom.data"
            before = source.read_bytes()
            try:
                os.link(source, Path(folder) / "reports" / "secom_check_features.csv")
            except OSError:
                self.skipTest("하드링크를 만들 수 없음")
            result = run_cli(folder)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(source.read_bytes(), before)

    def test_t294_repeat_is_identical_and_t295_text(self):
        with tempfile.TemporaryDirectory() as folder:
            write_case(folder, *fixture())
            first = run_cli(folder, seed="1")
            self.assertEqual(first.returncode, 0, first.stderr)
            saved = {name: (Path(folder) / "reports" / name).read_bytes() for name in OUTPUTS}
            second = run_cli(folder, seed="9")
            self.assertEqual(second.returncode, 0, second.stderr)
            for name in OUTPUTS:
                self.assertEqual((Path(folder) / "reports" / name).read_bytes(), saved[name], name)
            text = saved["secom_check.md"].decode("utf-8")
            for phrase in ("UCI", "CC BY 4.0", "검출률이 아니다", "반도체", "오경보율이나 검출률이 아니다"):
                self.assertIn(phrase, text)
            with (Path(folder) / "reports" / "secom_check_summary.csv").open(encoding="utf-8-sig", newline="") as source:
                sections = {row["section"] for row in csv.DictReader(source)}
            self.assertTrue({"synthetic_pure", "synthetic_mixed", "summary", "data"} <= sections)


if __name__ == "__main__":
    unittest.main()

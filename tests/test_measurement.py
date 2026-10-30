import csv
from decimal import Decimal
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from src.capability import capability, show
from src.equipment import load_equipment
from src.reason_codes import MEASURED_INJECTED_ERROR_CODES, rejection_code
from src.recipe import RecipeError, is_decimal_text, load_recipe
from src.recipe_rules import MEASURE_COLUMN, RecipeProcess, input_columns
from src.summary import build_analysis, build_summary
from src.trace import build_trace


ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "recipes" / "lamp_models_measured.json"
EQUIPMENT = ROOT / "recipes" / "equipment_measured.json"
PLAIN_RECIPE = ROOT / "recipes" / "lamp_models_retest.json"
LOT_EQUIPMENT = ROOT / "recipes" / "equipment_lot.json"


def row(seq, product_id, name, inspection="", result="", model="", equipment="", value=""):
    return dict(zip(input_columns(BOOK, True), (str(seq), product_id, name, inspection, result, model, equipment, value)))


MODELS = load_recipe(RECIPE).models
BOOK = load_equipment(EQUIPMENT, MODELS)


def prepared(products):
    rows = []
    for product_id in products:
        for name, model in (("REGISTER", "B"), ("P1", ""), ("P2", "")):
            rows.append(row(len(rows) + 1, product_id, name, model=model))
    return rows


def leak(seq, product_id, value, equipment="LEAK-1"):
    return row(seq, product_id, "INSPECT", "LEAK", equipment=equipment, value=value)


def restart(seq, result="FIXED", equipment="LEAK-1", value=""):
    return row(seq, "", "EQUIP_RESTART", result=result, equipment=equipment, value=value)


def write_csv(path, rows, columns=None):
    columns = columns or input_columns(BOOK, True)
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def run_cli(module, *arguments, cwd):
    environment = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, "-m", module, *map(str, arguments)], cwd=cwd, env=environment,
                          capture_output=True, encoding="utf-8")


def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def apply_all(process, rows):
    return [process.apply(item) for item in rows]


class JudgmentTests(unittest.TestCase):
    def test_t89_boundaries_are_pass_and_raw_value_is_kept(self):
        values = ["13", "13.000", "7", "13.001", "6.999"]
        products = ["p" + str(index) for index in range(5)]
        rows = prepared(products)
        process = RecipeProcess(MODELS, BOOK)
        apply_all(process, rows)
        decisions = []
        for index, (product_id, value) in enumerate(zip(products, values)):
            # 설비 창이 FAIL로 정지하지 않게 제품마다 다른 설비 조합을 쓴다.
            equipment = "LEAK-3" if value == "6.999" else "LEAK-1"
            decisions.append(process.apply(leak(len(rows) + index + 1, product_id, value, equipment)))
        self.assertEqual([item.result for item in decisions], ["PASS", "PASS", "PASS", "FAIL", "FAIL"])
        self.assertEqual([item.value for item in decisions], values)
        self.assertEqual(decisions[0].input_text, "INSPECT LEAK PASS @LEAK-1 value=13")
        self.assertEqual(decisions[3].input_text, "INSPECT LEAK FAIL @LEAK-1 value=13.001")
        self.assertEqual(process.products["p3"].status, "보류")
        self.assertEqual(process.products["p4"].status, "보류")
        self.assertIn("value=13.001", process.products["p3"].history)

    def test_t90_bad_values_leave_state_unchanged(self):
        for value in ("", "abc", "NaN", "Infinity", "1e1", "+1", "1" * 31, "٣"):
            with self.subTest(value=value):
                rows = prepared(["p"])
                process = RecipeProcess(MODELS, BOOK)
                apply_all(process, rows)
                product, equipment = process.products["p"], dict(process.equipment)
                event = leak(10, "p", value)
                decision = process.apply(event)
                self.assertFalse(decision.accepted)
                self.assertEqual(decision.rule_id, "RULE_PRESERVE")
                self.assertEqual(rejection_code(decision, event, MODELS), "PRESERVE_BAD_VALUE")
                self.assertEqual(decision.result, "")
                self.assertEqual(decision.value, value)
                self.assertIs(process.products["p"], product)
                self.assertEqual(process.equipment, equipment)

    def test_t91_field_positions(self):
        process = RecipeProcess(MODELS, BOOK)
        rows = prepared(["p", "q", "r"])
        apply_all(process, rows)
        cases = (
            (row(20, "p", "INSPECT", "LEAK", "PASS", equipment="LEAK-1", value="10"), "PRESERVE_RESULT_FIELD"),
            (row(21, "p", "INSPECT", "LEAK", "PASS", equipment="LEAK-1"), "PRESERVE_RESULT_FIELD"),
            (row(22, "p", "P3", value="10"), "PRESERVE_VALUE_FIELD"),
        )
        for event, code in cases:
            decision = process.apply(event)
            self.assertFalse(decision.accepted)
            self.assertEqual(rejection_code(decision, event, MODELS), code)
        self.assertEqual(process.apply(leak(30, "p", "14")).result, "FAIL")
        self.assertEqual(process.apply(leak(31, "q", "14")).result, "FAIL")
        self.assertIsNotNone(process.equipment["LEAK-1"].stopped_at_seq)
        event = restart(32, value="10")
        decision = process.apply(event)
        self.assertFalse(decision.accepted)
        self.assertEqual(rejection_code(decision, event, MODELS), "PRESERVE_VALUE_FIELD")
        self.assertIn("value=10", decision.input_text)
        self.assertIsNotNone(process.equipment["LEAK-1"].stopped_at_seq)
        decision = process.apply(restart(33))
        self.assertTrue(decision.accepted)
        self.assertEqual(decision.result, "FIXED")
        self.assertIsNone(process.equipment["LEAK-1"].stopped_at_seq)
        self.assertEqual(process.equipment["LEAK-1"].last_restart_result, "FIXED")

    def test_t91_check_order_with_seq_and_retest_request(self):
        process = RecipeProcess(MODELS, BOOK)
        apply_all(process, prepared(["p"]))
        decision = process.apply(row("x", "p", "INSPECT", "LEAK", "PASS", equipment="LEAK-1", value="abc"))
        self.assertEqual(decision.reason, "seq는 양의 정수여야 함")
        self.assertEqual(process.apply(leak(20, "p", "14")).result, "FAIL")
        self.assertTrue(process.apply(row(21, "p", "RETEST_REQUEST", "LEAK")).accepted)
        self.assertFalse(process.apply(leak(22, "p", "abc", "LEAK-2")).accepted)
        self.assertIn("LEAK", process.products["p"].open_requests)
        self.assertTrue(process.apply(leak(23, "p", "10", "LEAK-2")).accepted)
        self.assertEqual(process.products["p"].retest_counts, {"LEAK": 1})

    def test_t94_one_sided_specs(self):
        def models_with(lsl, usl):
            data = json.loads(RECIPE.read_text(encoding="utf-8-sig"))
            for body in data.values():
                for item in body["inspections"]:
                    item.update(lsl=lsl, usl=usl)
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "recipe.json"
                path.write_text(json.dumps(data), encoding="utf-8")
                return load_recipe(path).models

        for lsl, usl, values, expected in (
                (None, "13", ("-50", "13", "13.001"), ["PASS", "PASS", "FAIL"]),
                ("7", None, ("6.999", "7", "1000"), ["FAIL", "PASS", "PASS"])):
            models = models_with(lsl, usl)
            process = RecipeProcess(models, BOOK)
            products = ["a", "b", "c"]
            rows = prepared(products)
            apply_all(process, rows)
            names = ("LEAK-1", "LEAK-2", "LEAK-3")
            decisions = [process.apply(leak(50 + index, product_id, value, names[index]))
                         for index, (product_id, value) in enumerate(zip(products, values))]
            self.assertEqual([item.result for item in decisions], expected)

    def test_t95_retest_uses_values_and_stays_out_of_window(self):
        rows = prepared(["p"])
        rows += [leak(len(rows) + 1, "p", "14"), row(len(rows) + 2, "p", "RETEST_REQUEST", "LEAK"),
                 leak(len(rows) + 3, "p", "10")]
        analysis = build_analysis(rows, MODELS, BOOK)
        self.assertTrue(all(decision.accepted for decision in analysis.decisions))
        product = analysis.process.products["p"]
        self.assertEqual(product.inspections["LEAK"], "PASS")
        self.assertNotEqual(product.status, "보류")
        self.assertIn("value=14", product.history)
        self.assertIn("value=10", product.history)
        self.assertEqual(analysis.process.equipment["LEAK-1"].counted_results, 1)
        self.assertEqual(analysis.process.equipment["LEAK-1"].fail_count, 1)
        self.assertEqual([record.result for record in analysis.first_inspections], ["FAIL"])
        self.assertEqual([record.value for record in analysis.all_inspections], ["14", "10"])
        metrics = next(item for item in build_summary(analysis) if item["section"] == "inspection_metrics"
                       and item["key"] == "ALL")
        self.assertEqual((metrics["first_fail_count"], metrics["all_fail_count"]), (1, 1))

    def test_equipment_stops_from_computed_result(self):
        rows = prepared(["p", "q"])
        rows += [leak(len(rows) + 1, "p", "14"), leak(len(rows) + 2, "q", "14")]
        process = RecipeProcess(MODELS, BOOK)
        apply_all(process, rows)
        self.assertIsNotNone(process.equipment["LEAK-1"].stopped_at_seq)

    def test_stopped_equipment_keeps_open_request_for_retest(self):
        process = RecipeProcess(MODELS, BOOK)
        apply_all(process, prepared(["p", "q"]))
        process.apply(leak(20, "p", "14"))
        process.apply(row(21, "p", "RETEST_REQUEST", "LEAK"))
        process.apply(leak(22, "q", "14"))
        decision = process.apply(leak(23, "p", "10"))
        self.assertEqual(decision.reason, "정지된 설비")
        self.assertEqual(decision.result, "")
        self.assertIn("LEAK", process.products["p"].open_requests)


class RecipeTests(unittest.TestCase):
    def errors(self, change):
        data = json.loads(RECIPE.read_text(encoding="utf-8-sig"))
        change(data)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "recipe.json"
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(RecipeError) as caught:
                load_recipe(path)
        return "\n".join(caught.exception.errors)

    def test_t92_recipe_errors_show_location(self):
        def first(data):
            return data["A"]["inspections"][0]

        def update(**fields):
            return lambda data: first(data).update(fields)

        def remove_key(data):
            del data["B"]["inspections"][1]["unit"]

        def remove_all(data):
            for key in ("lsl", "usl", "unit"):
                del data["A"]["inspections"][1][key]

        def model_differs(data):
            first(data)["usl"] = "12.000"

        cases = (
            (update(lsl="13", usl="7"), "A.inspections[0]"),
            (update(lsl="13", usl="13.0"), "A.inspections[0]"),
            (update(lsl=None, usl=None), "A.inspections[0]"),
            (update(lsl=7), "A.inspections[0].lsl"),
            (update(lsl="NaN"), "A.inspections[0].lsl"),
            (update(usl="Infinity"), "A.inspections[0].usl"),
            (update(usl="1e1"), "A.inspections[0].usl"),
            (update(usl=True), "A.inspections[0].usl"),
            (remove_key, "B.inspections[1].unit"),
            (remove_all, "A.inspections[1].lsl"),
            (update(unit="   "), "A.inspections[0].unit"),
            (model_differs, "같은 검사 ID"),
            (update(usl="1" * 31), "A.inspections[0].usl"),
        )
        for change, location in cases:
            with self.subTest(location=location):
                self.assertIn(location, self.errors(change))

    def test_t92_cli_exits_3_without_reports(self):
        data = json.loads(RECIPE.read_text(encoding="utf-8-sig"))
        data["A"]["inspections"][0]["lsl"] = "NaN"
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            recipe = folder / "bad.json"
            recipe.write_text(json.dumps(data), encoding="utf-8")
            source = folder / "in.csv"
            write_csv(source, prepared(["p"]))
            result = run_cli("src.main", source, "--recipe", recipe, "--equipment", EQUIPMENT, cwd=folder)
            self.assertEqual(result.returncode, 3)
            self.assertFalse((folder / "reports").exists())

    def test_digit_limit_counts_only_digits(self):
        self.assertTrue(is_decimal_text("-" + "1" * 15 + "." + "2" * 15))
        self.assertFalse(is_decimal_text("-" + "1" * 15 + "." + "2" * 16))
        self.assertFalse(is_decimal_text("10\n"))

    def test_same_spec_in_other_notation_is_allowed(self):
        data = json.loads(RECIPE.read_text(encoding="utf-8-sig"))
        data["A"]["inspections"][0]["usl"] = "13"
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "recipe.json"
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            self.assertTrue(load_recipe(path).measured)


class HeaderTests(unittest.TestCase):
    def run_header(self, columns, rows, recipe=RECIPE, equipment=EQUIPMENT):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            source = folder / "in.csv"
            write_csv(source, rows, columns)
            arguments = [source, "--recipe", recipe]
            if equipment is not None:
                arguments += ["--equipment", equipment]
            return run_cli("src.main", *arguments, cwd=folder)

    def test_t93_headers(self):
        register = dict.fromkeys(input_columns(BOOK, True), "")
        register.update(seq="1", product_id="p", event="REGISTER", model="B")
        self.assertEqual(self.run_header(input_columns(BOOK, True), [register]).returncode, 0)
        lot_book = load_equipment(LOT_EQUIPMENT, MODELS)
        lot_row = dict(register, lot="LOT-1")
        self.assertEqual(self.run_header(input_columns(lot_book, True), [lot_row], equipment=LOT_EQUIPMENT).returncode, 0)
        plain = {key: register[key] for key in input_columns(BOOK)}
        self.assertEqual(self.run_header(input_columns(BOOK), [plain]).returncode, 2)
        self.assertEqual(self.run_header(input_columns(BOOK, True), [register], equipment=None).returncode, 2)
        self.assertEqual(self.run_header(input_columns(BOOK, True), [register], recipe=PLAIN_RECIPE).returncode, 2)

    def test_t93_lot_and_measured_columns_end_with_value(self):
        lot_book = load_equipment(LOT_EQUIPMENT, MODELS)
        self.assertEqual(input_columns(lot_book, True)[-2:], ("lot", MEASURE_COLUMN))
        self.assertEqual(len(input_columns(lot_book, True)), 9)
        self.assertEqual(len(input_columns(BOOK, True)), 8)

    def test_lot_is_checked_before_value(self):
        lot_book = load_equipment(LOT_EQUIPMENT, MODELS)
        process = RecipeProcess(MODELS, lot_book)
        event = dict.fromkeys(input_columns(lot_book, True), "")
        event.update(seq="1", product_id="p", event="INSPECT", lot="LOT-1", result="PASS", value="abc")
        self.assertEqual(process.apply(event).reason, "REGISTER 이외의 lot은 빈칸이어야 함")


class ReportTests(unittest.TestCase):
    def test_t109_summary_and_trace_use_computed_results(self):
        rows = prepared(["p", "q"])
        rows += [leak(len(rows) + 1, "p", "14"), leak(len(rows) + 2, "q", "10", "LEAK-2")]
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            source = folder / "in.csv"
            write_csv(source, rows)
            result = run_cli("src.main", source, "--recipe", RECIPE, "--equipment", EQUIPMENT, "--summary",
                             "--trace", "p", cwd=folder)
            self.assertEqual(result.returncode, 0, result.stderr)
            summary = read_csv(folder / "reports" / "in_summary.csv")
            metrics = next(item for item in summary if item["section"] == "inspection_metrics" and item["key"] == "ALL")
            self.assertEqual((metrics["first_count"], metrics["first_fail_count"], metrics["first_fail_rate"]),
                             ("2", "1", "0.5000"))
            trace = read_csv(folder / "reports" / "in_trace_p.csv")
            self.assertEqual(list(trace[0])[-3:], ["value", "lsl", "usl"])
            inspect = next(item for item in trace if "INSPECT" in item["input"])
            self.assertEqual((inspect["value"], inspect["lsl"], inspect["usl"]), ("14", "7.000", "13.000"))
            self.assertEqual(inspect["input"], "INSPECT LEAK FAIL @LEAK-1 value=14")
            self.assertIn("value=14", trace[-1]["history"])
            self.assertIn("value | lsl | usl", result.stdout)

    def test_history_without_retest_mode_shows_value(self):
        data = json.loads(RECIPE.read_text(encoding="utf-8-sig"))
        for body in data.values():
            del body["retest_limit"]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "recipe.json"
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            models = load_recipe(path).models
        book = load_equipment(EQUIPMENT, models)
        rows = prepared(["p"]) + [leak(10, "p", "12.300")]
        trace = build_trace(build_analysis(rows, models, book), "p")
        self.assertEqual(trace[-1]["history"], "LEAK: PASS@10[LEAK-1](value=12.300)")

    def test_measured_mode_summary_accepts_only_its_injection_codes(self):
        rows = prepared(["p"])
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            source = folder / "in.csv"
            write_csv(source, rows)
            meta = Path(str(source) + ".meta.json")
            meta.write_text(json.dumps({"normal_rows": 3, "injected_errors": {"PRESERVE_BAD_RESULT": 1}}), encoding="utf-8")
            arguments = (source, "--recipe", RECIPE, "--equipment", EQUIPMENT, "--summary")
            self.assertEqual(run_cli("src.main", *arguments, cwd=folder).returncode, 2)
            meta.write_text(json.dumps({"normal_rows": 3, "injected_errors": {"PRESERVE_BAD_VALUE": 1}}), encoding="utf-8")
            self.assertEqual(run_cli("src.main", *arguments, cwd=folder).returncode, 0)
            summary = read_csv(folder / "reports" / "in_summary.csv")
            keys = {item["key"] for item in summary if item["section"] == "injection_comparison"}
            self.assertTrue(set(MEASURED_INJECTED_ERROR_CODES) <= keys)
            self.assertNotIn("PRESERVE_BAD_RESULT", keys)


def stats(values, lsl="7", usl="13"):
    return capability([[Decimal(str(value)) for value in values]], lsl, usl)


class CapabilityFunctionTests(unittest.TestCase):
    BASE = [9, 10, 11, 10, 10, 10, 11, 9, 10, 10]

    def check(self, result, **expected):
        for name, value in expected.items():
            self.assertEqual(show(getattr(result, name)), value, name)

    def test_t96_two_subgroups(self):
        self.check(stats(self.BASE), xbarbar="10.0000", rbar="2.0000", sigma_within="0.8598", cpk="1.1630",
                   sample_sd="0.6667", ppk="1.5000")

    def test_t96_cpk_uses_unrounded_sigma(self):
        self.assertEqual(show(Decimal(3) / (3 * Decimal("0.8598"))), "1.1631")
        self.assertEqual(show(stats(self.BASE).cpk), "1.1630")

    def test_t97_remainder_counts_only_for_ppk(self):
        result = stats(self.BASE + [12])
        self.assertEqual((result.n, result.subgroups), (11, 2))
        self.check(result, cpk="1.1630", sample_sd="0.8739", ppk="1.0750")

    def test_t98_one_sided(self):
        self.check(stats(self.BASE, None, "13"), cpk="1.1630", ppk="1.5000")
        self.check(stats(self.BASE, "7", None), cpk="1.1630", ppk="1.5000")

    def test_t99_mean_outside_spec_is_negative(self):
        self.check(stats([14, 15, 16, 15, 15, 15, 16, 14, 15, 15]), cpk="-0.7753", ppk="-1.0000")

    def test_t100_wider_range(self):
        self.check(stats([8, 10, 12, 10, 10, 10, 12, 8, 10, 10]), rbar="4.0000", cpk="0.5815", ppk="0.7500")

    def test_t110_degenerate_inputs(self):
        for values in ([], [10]):
            result = stats(values)
            self.assertEqual(result.subgroups, 0)
            for name in ("xbarbar", "rbar", "sigma_within", "cpk", "sample_sd", "ppk"):
                self.assertIsNone(getattr(result, name), name)
        result = stats([9, 10, 11, 10])
        self.assertEqual(result.subgroups, 0)
        self.assertIsNone(result.xbarbar)
        self.assertIsNone(result.cpk)
        self.check(result, sample_sd="0.8165", ppk="1.2247")
        result = stats([9, 10, 11, 10, 10])
        self.assertEqual(result.subgroups, 1)
        self.assertIsNone(result.cpk)
        self.check(result, xbarbar="10.0000", rbar="2.0000", sample_sd="0.7071", ppk="1.4142")
        result = stats([10] * 10)
        self.assertEqual(result.subgroups, 2)
        self.assertEqual((result.sigma_within, result.sample_sd), (0, 0))
        self.assertIsNone(result.cpk)
        self.assertIsNone(result.ppk)

    def test_t110_large_spec_displays_fixed_point(self):
        result = stats(self.BASE, None, "1" + "0" * 29)
        for name in ("cpk", "ppk"):
            text = show(getattr(result, name))
            self.assertNotIn("E", text.upper())
            self.assertEqual(len(text.split(".")[1]), 4)

    def test_t110_negative_zero_is_display_only(self):
        result = stats(["12", "13", "14", "13", "13", "13", "14", "12", "13", "13.00002"])
        self.assertLess(result.cpk, 0)
        self.assertLess(result.ppk, 0)
        self.assertEqual((show(result.cpk), show(result.ppk)), ("0.0000", "0.0000"))


class CapabilityReportTests(unittest.TestCase):
    def report(self, rows, *extra):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            source = folder / "in.csv"
            write_csv(source, rows)
            result = run_cli("src.main", source, "--recipe", RECIPE, "--equipment", EQUIPMENT, "--capability",
                             *extra, cwd=folder)
            self.assertEqual(result.returncode, 0, result.stderr)
            names = sorted(path.name for path in (folder / "reports").iterdir())
            return read_csv(folder / "reports" / "in_capability.csv"), names

    def measured(self, values):
        products = ["p" + str(index) for index in range(len(values))]
        rows = prepared(products)
        rows += [leak(len(rows) + index + 1, product_id, str(value))
                 for index, (product_id, value) in enumerate(zip(products, values))]
        return rows

    def leak1(self, rows):
        return next(row for row in rows if row["equipment"] == "LEAK-1")

    def test_t101_restart_splits_subgroups(self):
        before = ["p" + str(index) for index in range(7)]
        after = ["q" + str(index) for index in range(8)]
        rows = prepared(before + after)
        values = [10, 10, 10, 10, 10, 14, 14]
        rows += [leak(len(rows) + index + 1, product_id, str(value))
                 for index, (product_id, value) in enumerate(zip(before, values))]
        rows.append(restart(len(rows) + 1))
        rows += [leak(len(rows) + index + 1, product_id, "10") for index, product_id in enumerate(after)]
        report, _ = self.report(rows)
        row = self.leak1(report)
        self.assertEqual((row["n"], row["subgroups"]), ("15", "2"))
        self.assertEqual((row["xbarbar"], row["rbar"], row["sample_sd"]), ("10.0000", "0.0000", "1.4075"))
        self.assertEqual((row["status"], row["cpk"], row["ppk"]), ("표본 부족", "", ""))

    def test_rejected_restart_keeps_segment(self):
        rows = self.measured([10, 10, 10, 10, 10])
        rows.insert(-2, restart(len(rows) + 1, "NO_FAULT"))
        report, _ = self.report(rows)
        self.assertEqual((self.leak1(report)["n"], self.leak1(report)["subgroups"]), ("5", "1"))

    def test_t102_retest_values_are_excluded(self):
        rows = prepared(["p", "q"])
        rows += [leak(len(rows) + 1, "p", "14"), row(len(rows) + 2, "p", "RETEST_REQUEST", "LEAK"),
                 leak(len(rows) + 3, "p", "10"), leak(len(rows) + 4, "q", "11")]
        report, _ = self.report(rows)
        leak1 = self.leak1(report)
        self.assertEqual((leak1["n"], leak1["subgroups"]), ("2", "0"))
        self.assertEqual(leak1["sample_sd"], "2.1213")

    def test_t103_status_rules(self):
        pattern = [9, 10, 11, 10, 10]
        report, _ = self.report(self.measured(pattern * 24))
        row = self.leak1(report)
        self.assertEqual((row["status"], row["n"], row["subgroups"], row["rbar"], row["cpk"], row["ppk"]),
                         ("표본 부족", "120", "24", "2.0000", "", ""))
        report, _ = self.report(self.measured(pattern * 25))
        row = self.leak1(report)
        self.assertEqual((row["status"], row["cpk"], row["sample_sd"], row["ppk"]),
                         ("계산됨", "1.1630", "0.6350", "1.5748"))
        other = next(item for item in report if item["equipment"] == "LEAK-3")
        self.assertEqual((other["status"], other["n"], other["xbarbar"], other["sample_sd"], other["cpk"]),
                         ("표본 부족", "0", "", "", ""))
        report, _ = self.report(self.measured([10] * 125))
        row = self.leak1(report)
        self.assertEqual((row["status"], row["cpk"], row["ppk"]), ("변동 없음", "", ""))
        report, _ = self.report(self.measured([9] * 65 + [11] * 60))
        row = self.leak1(report)
        self.assertEqual((row["status"], row["rbar"], row["cpk"], row["sample_sd"], row["ppk"]),
                         ("변동 없음", "0.0000", "", "1.0032", "0.9835"))

    def test_report_layout(self):
        report, _ = self.report(self.measured([10]))
        self.assertEqual(report[0]["section"], "notice")
        self.assertIn("구간을 합친 값이며 안정 공정의 능력을 보증하지 않는다", report[0]["value"])
        self.assertIn("생성 데이터의 확률은 가정이며", report[0]["value"])
        keys = [(item["inspection"], item["equipment"]) for item in report[1:]]
        self.assertEqual(keys, sorted(keys))
        self.assertEqual(len(keys), 7)
        self.assertEqual({item["unit"] for item in report[1:]}, {"가상 단위"})

    def test_t104_mode_and_combination(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            source = folder / "in.csv"
            write_csv(source, [], input_columns(BOOK))
            result = run_cli("src.main", source, "--recipe", PLAIN_RECIPE, "--equipment", EQUIPMENT, "--capability",
                             cwd=folder)
            self.assertEqual(result.returncode, 2)
            self.assertFalse((folder / "reports").exists())
        _, names = self.report(self.measured([10]), "--summary", "--containment")
        for suffix in ("capability", "summary", "containment"):
            self.assertIn("in_" + suffix + ".csv", names)


if __name__ == "__main__":
    unittest.main()

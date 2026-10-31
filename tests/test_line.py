import copy
import csv
from dataclasses import replace
from fractions import Fraction
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ElementTree

from src.line import (
    Element, Floor, LineError, Route, SimStation, _seconds, area_of, cycle_limits, fits, heuristic_balance, holdout_result,
    layout_of, load_line, machine_order, manual_bound, optimal_balance, product_routes, render_svg, select_combo, show,
    simulate, takt_of, target_uph, uph,
)
from src.generate import load_setup
from src.recipe import load_recipe


ROOT = Path(__file__).resolve().parents[1]
LINE = ROOT / "recipes" / "line_lamp.json"
RECIPE = ROOT / "recipes" / "lamp_models_measured.json"
MODELS = load_recipe(RECIPE).models
RATIOS = {"A": Fraction(1, 2), "B": Fraction(1, 2)}
BASE = load_line(LINE, MODELS)
RAW = json.loads(LINE.read_text(encoding="utf-8-sig"))


class LongValueTests(unittest.TestCase):
    def test_show_is_exact_past_decimal_precision(self):
        long_value = Fraction("123456789012345678901234567890.12345")
        self.assertEqual(show(long_value), "123456789012345678901234567890.1235")
        self.assertEqual(show(Fraction(1, 3)), "0.3333")
        self.assertEqual(show(Fraction(-1, 3)), "-0.3333")
        self.assertEqual(show(Fraction(-1, 1000000)), "0.0000")

    def test_long_period_runs_through_reports(self):
        data = copy.deepcopy(RAW)
        data["period_seconds"] = "123456789012345678901234567890.123"
        data["generator"] = str(ROOT / "recipes" / "generator_measured.json")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "line.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            result = run_cli(path, "--seeds", "0-0", "--holdout-seeds", "1000-1000", "--products", 1, cwd=folder)
            self.assertEqual(result.returncode, 0, result.stderr)


def manual(name, milliseconds, model="A"):
    return SimStation(name, 1, {model: milliseconds})


def check(name, model="A", **fields):
    return SimStation(name, fields.get("servers", 1), {model: fields.get("time", 10000)}, name)


def routes(count, model="A", **fields):
    return [Route("p" + str(index), model, **fields) for index in range(count)]


def run_cli(*arguments, cwd):
    environment = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, "-m", "src.line", *map(str, arguments)], cwd=cwd, env=environment,
                          capture_output=True, encoding="utf-8")


def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


class DefinitionTests(unittest.TestCase):
    def test_t130_definitions(self):
        self.assertEqual(BASE.net, 25_800_000)
        self.assertEqual(show(takt_of(BASE) / 1000), "19.8462")
        self.assertEqual(show(target_uph(BASE)), "181.3953")
        self.assertEqual(manual_bound(BASE.elements, BASE.net, BASE.demand), 4)

    def test_t131_optimal_balance(self):
        balance = optimal_balance(BASE.elements, RATIOS, BASE.net, BASE.demand)
        self.assertEqual((balance.manual_count, len(balance.stations)), (5, 8))
        self.assertEqual(balance.idle_cost / 1_000_000, Fraction(82551, 338))
        by_id = {element.id: element for element in BASE.elements}
        loads = {model: [sum(by_id[name].times[model] for name in members) // 1000 for members in balance.stations
                         if not by_id[members[0]].inspection] for model in ("A", "B")}
        self.assertEqual(loads["A"], [16, 17, 17, 10, 17])
        self.assertEqual(loads["B"], [16, 16, 14, 10, 6])

    def test_t132_heuristic_gap(self):
        elements = [Element("e" + str(index), "X", {"A": time * 1000}) for index, time in enumerate((4, 4, 3, 3, 3, 3))]
        ratios = {"A": Fraction(1)}
        best = optimal_balance(elements, ratios, 10_000, 1)
        greedy = heuristic_balance(elements, ratios, 10_000, 1)
        self.assertEqual((len(best.stations), len(greedy.stations)), (2, 3))
        by_id = {element.id: element.times["A"] for element in elements}
        for balance in (best, greedy):
            self.assertTrue(all(sum(by_id[name] for name in members) <= 10_000 for members in balance.stations))

    def test_default_line_heuristic_matches_constraints(self):
        balance = heuristic_balance(BASE.elements, RATIOS, BASE.net, BASE.demand)
        self.assertEqual(len(balance.stations), 8)

    def test_t133_mixed_and_fractional_takt(self):
        self.assertFalse(fits(25_000, 21_500, 1))
        self.assertTrue(fits(10_000, 21_500, 1))
        self.assertTrue(fits(19_846, 25_800_000, 1300))
        self.assertFalse(fits(19_847, 25_800_000, 1300))
        elements = [Element("a", "X", {"A": 25_000, "B": 10_000})]
        self.assertIsNone(optimal_balance(elements, RATIOS, 21_500, 1))

    def changed(self, change):
        data = copy.deepcopy(RAW)
        change(data)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "line.json"
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(LineError) as caught:
                load_line(path, MODELS)
        return "\n".join(caught.exception.errors)

    def test_t134_input_errors(self):
        def element(name):
            return lambda data: next(item for item in data["elements"] if item["id"] == name)

        def update(name, **fields):
            return lambda data: element(name)(data).update(fields)

        def seconds(name, model, value):
            return lambda data: element(name)(data)["seconds"].update({model: value})

        def drop(name):
            return lambda data: data["elements"].remove(element(name)(data))

        def more(data):
            data["elements"].append({"id": "X", "step": "P1", "seconds": {"A": "1.000", "B": "1.000"},
                                     "predecessors": ["P1-2"]})

        def no_model(data):
            del element("P1-1")(data)["seconds"]["B"]

        cases = (
            (update("P1-1", predecessors=["FINAL"]), "순환"),
            (update("P1-2", predecessors=["NOPE"]), "없는 선행"),
            (update("P1-2", step="P9"), "레시피에 없는"),
            (lambda data: [data["elements"].remove(item) for item in list(data["elements"]) if item["step"] == "P5"],
             "P5"),
            (seconds("P5-1", "A", "0.000"), "시간이 0"),
            (lambda data: element("P4-1")(data).update(step="P4") or element("P5-1")(data)["seconds"].update(B="1.000"),
             "없는 P5"),
            (update("LEAK", predecessors=["P2-2"]), "after"),
            (update("FINAL", predecessors=["P5-1"]), "검사 순서"),
            (lambda data: data["machines"]["LEAK"].update(counts=[2, 1]), "counts"),
            (lambda data: data["machines"]["LEAK"].update(counts=[]), "counts"),
            (seconds("P1-1", "A", "-1.000"), "문자열 초"),
            (seconds("P1-1", "A", "1.0001"), "문자열 초"),
            (lambda data: data.update(planned_stop_seconds="28800.000"), "planned_stop"),
            (more, "elements"),
            (no_model, "모델 키"),
            (lambda data: data.update(buffer_units=-1), "buffer_units"),
            (lambda data: data.update(buffer_units=1.5), "buffer_units"),
            (lambda data: data["machines"]["LEAK"].update(test="21.000"), "구간 합"),
            (lambda data: data.update(extra=1), "허용하지 않은 키"),
        )
        for index, (change, text) in enumerate(cases):
            with self.subTest(index=index):
                self.assertIn(text, self.changed(change))

    def test_t134_structure_errors_exit_3(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            no_generator = {key: value for key, value in RAW.items() if key != "generator"}
            bad_step = copy.deepcopy(RAW)
            bad_step["generator"] = str(ROOT / "recipes" / "generator_measured.json")
            bad_step["elements"][0]["step"] = ["P1"]
            for name, data in (("none", no_generator), ("list", []), ("number", dict(RAW, generator=1)), ("step", bad_step)):
                with self.subTest(name=name):
                    path = folder / (name + ".json")
                    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                    result = run_cli(path, "--seeds", "0-0", "--holdout-seeds", "1-1", "--products", 5, cwd=folder)
                    self.assertEqual(result.returncode, 3, result.stderr)
                    self.assertIn("$", result.stderr)
                    self.assertNotIn("Traceback", result.stderr)
            self.assertFalse((folder / "reports").exists())

    def test_t134_duplicate_predecessor_is_rejected(self):
        def change(data):
            data["elements"][1]["predecessors"] = ["P1-1", "P1-1"]

        self.assertIn("중복", self.changed(change))

    def test_seconds_keep_every_digit(self):
        errors = []
        self.assertEqual(_seconds("123456789012345678901234567890.123", "$", errors),
                         123456789012345678901234567890123)
        self.assertEqual((_seconds("1.5", "$", errors), _seconds("2", "$", errors)), (1500, 2000))
        self.assertEqual(errors, [])

    def test_t134_cli_exits_3_without_reports(self):
        data = copy.deepcopy(RAW)
        data["generator"] = str(ROOT / "recipes" / "generator_measured.json")
        data["buffer_units"] = -1
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            path = folder / "line.json"
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            result = run_cli(path, "--seeds", "0-0", "--holdout-seeds", "1-1", "--products", 5, cwd=folder)
            self.assertEqual(result.returncode, 3, result.stderr)
            self.assertFalse((folder / "reports").exists())

    def test_t135_argument_errors_exit_2(self):
        data = copy.deepcopy(RAW)
        data["generator"] = str(ROOT / "recipes" / "generator_restart.json")
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            plain = folder / "plain.json"
            plain.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            for arguments in ((plain, "--seeds", "0-0", "--holdout-seeds", "1-1", "--products", 5),
                              (LINE, "--seeds", "x", "--holdout-seeds", "1-1", "--products", 5),
                              (LINE, "--seeds", "0-0", "--holdout-seeds", "1-1", "--products", 0),
                              (LINE, "--seeds", "0-5", "--holdout-seeds", "5-6", "--products", 5)):
                self.assertEqual(run_cli(*arguments, cwd=folder).returncode, 2)
            self.assertFalse((folder / "reports").exists())

    def test_t144_t145_cycle_limits(self):
        nominal, adjusted = cycle_limits(Fraction(21500), 2, Fraction(110, 100), Fraction(8, 10))
        self.assertEqual((show(nominal / 1000), show(adjusted / 1000)), ("39.0909", "31.2727"))
        self.assertEqual(show((adjusted - 12000) / 1000), "19.2727")
        self.assertTrue(34000 <= nominal)
        self.assertFalse(34000 <= adjusted)
        self.assertIsNone(cycle_limits(Fraction(21500), 2, Fraction(0), Fraction(8, 10)))


class SimulationTests(unittest.TestCase):
    def test_t136_blocking_without_buffer(self):
        result = simulate([manual("S1", 10000), manual("S2", 20000)], routes(3), 0, 0)
        self.assertEqual(result.end, 70000)
        self.assertEqual(result.blocked["S1"], 20000)
        self.assertEqual(show(Fraction(result.work["S2"], result.end)), "0.8571")
        self.assertEqual(show(uph(result.good, result.end)), "154.2857")

    def test_t137_buffer_removes_blocking(self):
        result = simulate([manual("S1", 10000), manual("S2", 20000)], routes(3), 1, 0)
        self.assertEqual((result.end, result.blocked["S1"]), (70000, 0))

    def test_t138_retest_occupies_the_machine(self):
        items = [Route("a", "A", {"X": 1}), Route("b", "A", {"X": 2}), Route("c", "A", {"X": 1})]
        result = simulate([check("X")], items, 0, 0)
        self.assertEqual((result.end, result.good), (40000, 3))
        self.assertEqual(show(uph(result.good, result.end)), "270.0000")

    def test_t139_repair(self):
        items = [Route("a", "A", {"X": 1}, stops=frozenset({"X"})), Route("b", "A", {"X": 1})]
        result = simulate([check("X")], items, 0, 100000)
        self.assertEqual(result.end, 120000)
        self.assertEqual(show(Fraction(result.repair["X"], result.end)), "0.8333")
        result = simulate([check("X")], items[:1], 0, 100000)
        self.assertEqual((result.end, result.repair["X"]), (10000, 0))

    def test_t140_parallel_servers(self):
        station = [check("X", servers=2)]
        plain = [Route("p" + str(index), "A", {"X": 1}) for index in range(3)]
        self.assertEqual(simulate(station, plain, 0, 100000).end, 20000)
        one = [replace(plain[0], stops=frozenset({"X"}))] + plain[1:]
        self.assertEqual(simulate(station, one, 0, 100000).end, 20000)
        both = [replace(item, stops=frozenset({"X"})) for item in plain[:2]] + plain[2:]
        self.assertEqual(simulate(station, both, 0, 100000).end, 120000)

    def test_t141_skipped_station_keeps_blocking_upstream(self):
        stations = [manual("S1", 1000, "B"), SimStation("S2", 1, {"B": 0, "A": 5000}), manual("S3", 10000, "B")]
        result = simulate(stations, routes(3, "B"), 0, 0)
        self.assertEqual(result.end, 31000)
        self.assertEqual(result.work["S2"], 0)
        self.assertGreater(result.blocked["S1"], 0)

    def test_t142_end_inspection_leaves_the_line(self):
        stations = [check("LEAK"), manual("S2", 5000), manual("S3", 5000)]
        item = Route("a", "A", {"LEAK": 1}, completed=False, end_inspection="LEAK")
        result = simulate(stations, [item], 0, 0)
        self.assertEqual((result.end, result.work["S2"], result.work["S3"], result.good, result.passed),
                         (10000, 0, 0, 0, 0))

    def test_t143_good_excludes_escaped_defects(self):
        # tasks.md의 T143은 180·90이지만 제품 2개가 20초에 끝나므로 정의상 360·180이다. gpt-log에 명세 이견으로 남겼다.
        items = [Route("a", "A", defective=True), Route("b", "A")]
        result = simulate([manual("S1", 10000)], items, 0, 0)
        self.assertEqual((result.end, result.passed, result.good, result.escaped), (20000, 2, 1, 1))
        self.assertEqual(show(uph(result.passed, result.end)), "360.0000")
        self.assertEqual(show(uph(result.good, result.end)), "180.0000")

    def test_waiting_buffer_goes_first_and_is_fifo(self):
        result = simulate([manual("S1", 1000), manual("S2", 10000)], routes(4), 2, 0)
        self.assertEqual(result.end, 41000)
        self.assertGreater(result.wait, 0)

    def test_product_without_work_leaves_at_once(self):
        self.assertEqual(simulate([manual("S1", 0)], routes(1, "B"), 0, 0).end, 0)


class RouteTests(unittest.TestCase):
    def test_routes_follow_generation_order_past_9999(self):
        config, _, recipe, book = load_setup(ROOT / "recipes" / "generator_measured.json")
        numbers = [int(route.product_id[4:]) for route in product_routes(config, recipe, book, 0, 10001)]
        self.assertEqual(numbers, list(range(1, 10002)))


class SelectionTests(unittest.TestCase):
    def test_machine_key_order_does_not_change_combo_order(self):
        reordered = replace(BASE, machines=dict(reversed(list(BASE.machines.items()))))
        self.assertEqual(machine_order(reordered), ["LEAK", "LIGHT", "FINAL"])

    def test_t148_selection(self):
        self.assertEqual(select_combo([(10, 4, (2, 1, 1), True), (12, 3, (1, 1, 1), True)]), (2, 1, 1))
        self.assertEqual(select_combo([(10, 5, (2, 2, 1), True), (10, 4, (2, 1, 1), True)]), (2, 1, 1))
        self.assertEqual(select_combo([(10, 4, (2, 1, 1), True), (10, 4, (1, 2, 1), True)]), (1, 2, 1))
        self.assertIsNone(select_combo([(10, 4, (2, 1, 1), False)]))

    def test_t149_holdout(self):
        target = Fraction(1813953, 10000)
        self.assertEqual(holdout_result((2, 1, 1), target - 1, target), "미달")
        self.assertEqual(holdout_result((2, 1, 1), target, target), "확인")
        self.assertEqual(holdout_result(None, None, target), "검증할 선택 없음")


class LayoutTests(unittest.TestCase):
    def setUp(self):
        self.balance = optimal_balance(BASE.elements, RATIOS, BASE.net, BASE.demand)

    def combo(self, leak, light=1, final=1):
        return dict(LEAK=leak, LIGHT=light, FINAL=final)

    def test_t150_layout_numbers(self):
        for leak, width in ((1, 3500), (2, 5200), (3, 6900)):
            layout = layout_of(BASE, self.balance, self.combo(leak))
            self.assertEqual((layout["length"], layout["width"], layout["meets_floor"]), (14100, width, True))
        narrow = replace(BASE, floor=replace(BASE.floor, width=6000))
        self.assertFalse(layout_of(narrow, self.balance, self.combo(3))["meets_floor"])
        self.assertTrue(layout_of(narrow, self.balance, self.combo(2))["meets_floor"])
        self.assertEqual(area_of(BASE, self.combo(2)), 7_620_000)

    def test_t151_svg(self):
        layout = layout_of(BASE, self.balance, self.combo(2))
        text = render_svg(BASE, layout, self.combo(2), "선택 조합 2-1-1")
        root = ElementTree.fromstring(text)
        namespace = "{http://www.w3.org/2000/svg}"
        stations = [item for item in root.iter(namespace + "rect") if item.get("class") == "station"]
        self.assertEqual(len(stations), 8)
        for word in ("투입", "배출", "보전", "버퍼", "통로", "라인 길이 14100mm", "라인 폭 5200mm", "가상이며", "S4 ×2"):
            self.assertIn(word, text)
        height = float(root.get("height"))
        self.assertTrue(all(float(item.get("y")) <= height for item in root.iter(namespace + "text")))
        floor = BASE.floor
        narrow = replace(BASE, floor=Floor(floor.length, 4000, floor.aisle, floor.pitch, floor.gap))
        self.assertFalse(layout_of(narrow, self.balance, self.combo(2))["meets_floor"])


class CommandTests(unittest.TestCase):
    def execute(self, folder):
        return run_cli(LINE, "--seeds", "0-0", "--holdout-seeds", "1000-1000", "--products", 50, cwd=folder)

    def test_t146_t147_reports(self):
        outputs = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as folder:
                folder = Path(folder)
                result = self.execute(folder)
                self.assertEqual(result.returncode, 0, result.stderr)
                outputs.append({path.name: path.read_bytes() for path in (folder / "reports").iterdir()})
                compare = read_csv(folder / "reports" / "line_lamp_compare.csv")
                balance = read_csv(folder / "reports" / "line_lamp_balance.csv")
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(set(outputs[0]), {"line_lamp_balance.csv", "line_lamp_compare.csv", "line_lamp_layout.svg"})
        count = lambda section: sum(row["section"] == section for row in compare)
        self.assertEqual((count("development"), count("station"), count("selection")), (12, 96, 1))
        self.assertLessEqual(sum(row["selected"] == "선택" for row in compare), 1)
        self.assertTrue(any(row["section"] == "spec" and row["key"] == "LEAK:2" for row in balance))
        self.assertTrue(any(row["section"] == "visit" and row["key"] == "good_rate" for row in balance))
        self.assertTrue(any("조건부" in row["value"] for row in compare if row["section"] == "notice"))

    def test_infeasible_balance_lists_only_written_files(self):
        data = copy.deepcopy(RAW)
        data["generator"] = str(ROOT / "recipes" / "generator_measured.json")
        data["demand_units"] = 2600
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            path = folder / "tight.json"
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            result = run_cli(path, "--seeds", "0-0", "--holdout-seeds", "1-1", "--products", 5, cwd=folder)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("배치 불가", result.stdout)
            self.assertNotIn("layout.svg", result.stdout)
            self.assertEqual(sorted(item.name for item in (folder / "reports").iterdir()),
                             ["tight_balance.csv", "tight_compare.csv"])


if __name__ == "__main__":
    unittest.main()

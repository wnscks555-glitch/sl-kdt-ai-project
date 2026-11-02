import copy
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from src.line import Route, SimStation, simulate
from src.replay import ReplayError, check_events, load_settings, outcome, record


ROOT = Path(__file__).resolve().parents[1]


def run_cli(root, out="reports/line_replay.html", config=None):
    environment = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    config = config or str(ROOT / "recipes" / "line_replay.json")
    return subprocess.run([sys.executable, "-m", "src.replay", config, "--out", out, "--root", str(root)],
                          cwd=str(root), env=environment, capture_output=True, text=True, encoding="utf-8")


class Tags(HTMLParser):
    VOID = {"meta", "input", "br", "img"}

    def __init__(self):
        super().__init__()
        self.stack, self.broken, self.links = [], [], []

    def handle_starttag(self, tag, attrs):
        self.links += [value for name, value in attrs if name in ("src", "href") and value]
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack.pop() != tag:
            self.broken.append(tag)


def stations():
    return [SimStation("S1", 1, {"A": 10000}), SimStation("S2", 1, {"A": 20000}, "X")]


def routes():
    return [Route("a", "A", {"X": 1}, stops=frozenset({"X"})), Route("b", "A", {"X": 1}), Route("c", "A", {"X": 1})]


class EventTests(unittest.TestCase):
    def test_t297_hook_does_not_change_result(self):
        plain = simulate(stations(), routes(), 0, 5000)
        traced = simulate(stations(), routes(), 0, 5000, on_event=lambda *event: None)
        self.assertEqual(outcome(plain), outcome(traced))

    def test_t298_single_product_sequence(self):
        events = []
        simulate([SimStation("S1", 1, {"A": 10000})], [Route("a", "A")], 0, 0,
                 on_event=lambda clock, kind, index, number, route: events.append((clock, kind, index, number)))
        self.assertEqual(events, [(0, "begin", 0, 0), (10000, "done", 0, 0), (10000, "leave", -1, -1),
                                  (10000, "release", 0, 0)])

    def test_t298_blocking_and_repair_are_explained(self):
        result, events = record(stations(), routes(), 0, 5000)
        kinds = [event[1] for event in events]
        self.assertIn("down", kinds)
        self.assertIn("up", kinds)
        self.assertGreater(result.blocked["S1"], 0)

    def test_t299_missing_event_is_caught(self):
        result, events = record(stations(), routes(), 0, 5000)
        for kind in ("done", "release", "up", "begin"):
            with self.subTest(kind=kind):
                position = next(index for index, event in enumerate(events) if event[1] == kind)
                with self.assertRaises(ValueError):
                    check_events(events[:position] + events[position + 1:], stations(), result, 0)

    def test_t299_unfinished_repair_at_end_is_allowed(self):
        items = [Route("a", "A", {"X": 1}), Route("b", "A", {"X": 1}, stops=frozenset({"X"}))]
        result, events = record(stations(), items, 0, 50000)
        self.assertEqual([event[1] for event in events].count("up"), 0)
        self.assertIn("down", [event[1] for event in events])
        # 마지막 제품이 떠난 순간 시작한 수리는 종료 시각에서 잘려 0이다.
        self.assertEqual(result.repair["S2"], 0)

    def test_t300_leave_once_and_nothing_starts_after(self):
        result, events = record(stations(), routes(), 0, 5000)
        leaves = [event for event in events if event[1] == "leave"]
        self.assertEqual(sorted(event[4].product_id for event in leaves), ["a", "b", "c"])
        with self.assertRaises(ValueError):
            check_events(events + [leaves[0]], stations(), result, 0)
        late = (result.end, "begin", 0, 0, leaves[0][4])
        with self.assertRaises(ValueError):
            check_events(events + [late], stations(), result, 0)

    def test_t301_changed_result_is_caught(self):
        result, events = record(stations(), routes(), 0, 5000)
        changed = copy.deepcopy(result)
        changed.good += 1
        with self.assertRaises(ValueError):
            check_events(events, stations(), changed, 0)
        changed = copy.deepcopy(result)
        changed.work["S2"] += 1
        with self.assertRaises(ValueError):
            check_events(events, stations(), changed, 0)

    def test_buffer_bounds_are_checked(self):
        result, events = record(stations(), routes(), 1, 5000)
        queued = [event for event in events if event[1] == "queue"]
        self.assertTrue(queued)
        with self.assertRaises(ValueError):
            check_events(events + [queued[0]], stations(), result, 1)


class SettingsTests(unittest.TestCase):
    def test_bad_settings(self):
        base = json.loads((ROOT / "recipes" / "line_replay.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "replay.json"
            for broken in (dict(base, products=0), dict(base, products=501), dict(base, seed=True), dict(base, extra=1),
                           {key: value for key, value in base.items() if key != "line"}):
                path.write_text(json.dumps(broken), encoding="utf-8")
                with self.subTest(broken=broken), self.assertRaises(ReplayError):
                    load_settings(path)


class PageTests(unittest.TestCase):
    def test_t302_page(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "reports").mkdir()
            first = run_cli(folder)
            self.assertEqual(first.returncode, 0, first.stderr)
            path = Path(folder) / "reports" / "line_replay.html"
            data = path.read_bytes()
            second = run_cli(folder)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(path.read_bytes(), data)
            text = data.decode("utf-8")
            parser = Tags()
            parser.feed(text)
            parser.close()
            self.assertEqual((parser.broken, parser.stack), ([], []))
            self.assertEqual(parser.links, [])
            self.assertNotIn("http", text.replace("http-equiv", ""))
            static = text[:text.index("<script id=\"replay-data\"")]
            self.assertIn("스테이션별 시간 비율", static)
            payload = text[text.index("application/json\">") + len("application/json\">"):text.index("</script>")]
            data = json.loads(payload)
            self.assertEqual(data["products"], 60)
            self.assertEqual(sum(1 for event in data["events"] if event[1] == 7), 60)

    def test_t303_bad_out(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "reports").mkdir()
            for out in ("line_replay.html", "reports/line_replay.txt", "reports/sub/x.html"):
                with self.subTest(out=out):
                    self.assertEqual(run_cli(folder, out).returncode, 2)

    def test_t303_input_path_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "reports").mkdir()
            (root / "recipes").mkdir()
            for name in ("line_lamp.json", "generator_measured.json", "lamp_models_measured.json", "equipment_measured.json"):
                if (ROOT / "recipes" / name).exists():
                    shutil.copyfile(ROOT / "recipes" / name, root / "recipes" / name)
            shutil.copyfile(ROOT / "reports" / "line_lamp_compare.csv", root / "reports" / "line_lamp_compare.html")
            config = root / "recipes" / "replay.json"
            config.write_text(json.dumps({"line": "line_lamp.json", "line_report": "../reports/line_lamp_compare.html",
                                          "seed": 0, "products": 5}), encoding="utf-8")
            before = (root / "reports" / "line_lamp_compare.html").read_bytes()
            result = run_cli(root, "reports/line_lamp_compare.html", str(config))
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual((root / "reports" / "line_lamp_compare.html").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()

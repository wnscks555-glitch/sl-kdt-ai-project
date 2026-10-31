import unittest

from src.modbus import RELEASE_COIL, RESET_COIL, Table
from src.plc import (
    ALARM, CHECK, CLAMP, DISCHARGE, IDLE, INPUTS, MEASURE, OUTPUTS, PUBLISH, REG_COUNT, REG_HEARTBEAT, REG_MEASURE_ID,
    REG_VALUE_HIGH, REG_VALUE_LOW, UNCLAMP, WAIT_JUDGE, Plc, Timing, interlock,
)


TIMEOUTS = {"check_scans": 30, "clamp_scans": 20, "measure_scans": 50, "judge_scans": 30, "unclamp_scans": 20,
            "discharge_scans": 30}


class Rig:
    """정상 입력에서 시작해 스캔마다 PC 하트비트를 올리는 시험 장치다."""

    def __init__(self):
        self.table = Table()
        self.plc = Plc(self.table, Timing(10, TIMEOUTS))
        self.set(clamp_open=True, guard_closed=True)

    def set(self, **signals):
        for name, value in signals.items():
            self.table.discrete[INPUTS.index(name)] = value

    def scan(self, value="", beat=True):
        if beat:
            self.table.holding[0] = (self.table.holding[0] + 1) % 65536
        return self.plc.scan(value)

    def judge(self, judge_id, verdict):
        self.table.holding[1:3] = [judge_id, verdict]

    def reach(self, state):
        """정상 순서로 목표 상태까지 간다."""
        steps = [
            (CHECK, dict(part_present=True)),
            (CLAMP, dict(seated=True, direction_ok=True)),
            (MEASURE, dict(clamp_open=False, clamp_closed=True)),
            (PUBLISH, dict(measure_done=True)),
            (WAIT_JUDGE, dict(measure_done=False)),
            (UNCLAMP, dict()),
            (DISCHARGE, dict(clamp_closed=False, clamp_open=True)),
        ]
        for target, signals in steps:
            self.set(**signals)
            if target == UNCLAMP:
                self.judge(self.plc.measure_id, 1)
            self.scan("10.250" if target == PUBLISH else "")
            if target == state:
                return


def outputs(**fields):
    return {name: fields.get(name, False) for name in OUTPUTS}


def inputs(**fields):
    base = dict(clamp_open=True, guard_closed=True, seated=True, direction_ok=True)
    base.update(fields)
    return {name: base.get(name, False) for name in INPUTS}


class ScanTests(unittest.TestCase):
    def test_t153_snapshot_is_used_for_the_whole_scan(self):
        rig = Rig()
        rig.table.holding[0] = 1

        def change():
            rig.set(part_present=True)

        rig.plc.scan(after_snapshot=change)
        self.assertEqual(rig.plc.state, IDLE)
        self.assertEqual(rig.scan(), CHECK)

    def test_t154_full_sequence_one_transition_per_scan(self):
        rig = Rig()
        steps = [dict(part_present=True), dict(seated=True, direction_ok=True),
                 dict(clamp_open=False, clamp_closed=True), dict(measure_done=True), dict(measure_done=False),
                 None, dict(clamp_closed=False, clamp_open=True),
                 dict(part_present=False, seated=False, direction_ok=False)]
        states = []
        for number, signals in enumerate(steps, 1):
            if signals is None:
                rig.judge(1, 1)
            else:
                rig.set(**signals)
            states.append(rig.scan("10.250" if number == 4 else ""))
            if number == 5:
                self.assertEqual(rig.table.input_registers[REG_MEASURE_ID], 1)
                self.assertEqual((rig.table.input_registers[REG_VALUE_HIGH], rig.table.input_registers[REG_VALUE_LOW]),
                                 (0x0000, 0x280A))
                self.assertEqual(rig.table.holding[1:3], [0, 0])
        self.assertEqual(states, [1, 2, 3, 4, 5, 6, 7, 0])
        self.assertEqual(rig.table.input_registers[REG_COUNT], 1)
        self.assertEqual(rig.plc.ok_count, 1)

    def test_outputs_follow_each_state(self):
        rig = Rig()
        expected = {CLAMP: "10000", MEASURE: "11000", PUBLISH: "10000", WAIT_JUDGE: "10000", UNCLAMP: "00000",
                    DISCHARGE: "00100"}
        for state, bits in expected.items():
            rig = Rig()
            rig.reach(state)
            self.assertEqual("".join("1" if rig.plc.outputs[name] else "0" for name in OUTPUTS), bits, state)

    def test_ng_verdict_opens_ng_gate_only(self):
        rig = Rig()
        rig.reach(WAIT_JUDGE)
        rig.judge(1, 2)
        rig.scan()
        rig.set(clamp_closed=False, clamp_open=True)
        rig.scan()
        self.assertTrue(rig.plc.outputs["gate_ng"])
        self.assertFalse(rig.plc.outputs["gate_ok"])
        rig.set(part_present=False)
        rig.scan()
        self.assertEqual((rig.plc.ok_count, rig.plc.ng_count), (0, 1))

    def test_t155_timeout_boundary_and_transition_priority(self):
        rig = Rig()
        rig.set(part_present=True)
        rig.scan()
        for _ in range(30):
            self.assertEqual(rig.scan(), CHECK)
        self.assertEqual(rig.scan(), ALARM)
        self.assertEqual(rig.plc.alarm, 11)

        rig = Rig()
        rig.set(part_present=True)
        rig.scan()
        for _ in range(30):
            rig.scan()
        rig.set(seated=True, direction_ok=True)
        self.assertEqual(rig.scan(), CLAMP)
        self.assertEqual(rig.plc.alarm, 0)

    def test_every_timeout_has_its_alarm(self):
        for state, key, code in ((CLAMP, "clamp_scans", 12), (MEASURE, "measure_scans", 13),
                                 (WAIT_JUDGE, "judge_scans", 14), (UNCLAMP, "unclamp_scans", 15),
                                 (DISCHARGE, "discharge_scans", 16)):
            rig = Rig()
            rig.reach(state)
            if state == UNCLAMP:
                rig.set(clamp_open=False, clamp_closed=False)
            for _ in range(TIMEOUTS[key]):
                self.assertEqual(rig.scan(), state, key)
            self.assertEqual(rig.scan(), ALARM, key)
            self.assertEqual(rig.plc.alarm, code)

    def test_t156_interlock(self):
        clear = outputs()
        clamped = outputs(clamp_cmd=True)
        self.assertFalse(interlock(clamped, clear, inputs(seated=False), CLAMP)["clamp_cmd"])
        self.assertTrue(interlock(clamped, clamped, inputs(seated=False), MEASURE)["clamp_cmd"])
        measuring = outputs(clamp_cmd=True, measure_cmd=True)
        self.assertFalse(interlock(measuring, clamped, inputs(clamp_open=False), MEASURE)["measure_cmd"])
        self.assertFalse(interlock(measuring, clamped, inputs(clamp_closed=True), MEASURE)["measure_cmd"])
        both = interlock(outputs(gate_ok=True, gate_ng=True), clear, inputs(), DISCHARGE)
        self.assertFalse(both["gate_ok"] or both["gate_ng"])
        self.assertFalse(interlock(outputs(gate_ok=True), clear, inputs(clamp_open=False), DISCHARGE)["gate_ok"])
        self.assertFalse(interlock(outputs(gate_ok=True), clear, inputs(), ALARM)["gate_ok"])
        self.assertTrue(interlock(outputs(gate_ok=True), clear, inputs(), DISCHARGE)["gate_ok"])

    def test_t157_alarm_priority_and_first_alarm_kept(self):
        rig = Rig()
        for _ in range(10):
            rig.scan(beat=False)
        rig.set(guard_closed=False)
        rig.scan(beat=False)
        self.assertEqual(rig.plc.alarm, 22)

        rig = Rig()
        rig.reach(CLAMP)
        for _ in range(21):
            rig.scan()
        self.assertEqual(rig.plc.alarm, 12)
        rig.set(guard_closed=False)
        rig.scan()
        self.assertEqual(rig.plc.alarm, 12)

        rig = Rig()
        rig.set(clamp_closed=True)
        rig.scan()
        self.assertEqual(rig.plc.alarm, 24)

    def test_t157_measure_signal_alarms(self):
        rig = Rig()
        rig.reach(CLAMP)
        rig.set(measure_done=True)
        rig.scan("10.250")
        self.assertEqual(rig.plc.alarm, 25)
        self.assertEqual(rig.plc.value, "")

        rig = Rig()
        rig.reach(MEASURE)
        rig.set(measure_done=True, clamp_closed=False)
        rig.scan("10.250")
        self.assertEqual(rig.plc.alarm, 25)
        self.assertEqual(rig.plc.value, "")

    def test_t157_measure_done_before_command_cannot_pass(self):
        rig = Rig()
        rig.set(part_present=True)
        rig.scan()
        rig.set(measure_done=True)
        rig.scan()
        self.assertEqual(rig.plc.alarm, 25)

    def test_idle_waits_while_measure_done_is_held(self):
        rig = Rig()
        rig.set(part_present=True, measure_done=True)
        for _ in range(60):
            self.assertEqual(rig.scan(), IDLE)
        rig.set(measure_done=False)
        self.assertEqual(rig.scan(), CHECK)

    def test_t157_failed_conversion_keeps_measure_id(self):
        rig = Rig()
        rig.reach(MEASURE)
        rig.set(measure_done=True)
        rig.scan("1.2345")
        self.assertEqual(rig.plc.state, PUBLISH)
        rig.set(measure_done=False)
        rig.scan()
        self.assertEqual(rig.plc.alarm, 23)
        self.assertEqual(rig.plc.measure_id, 0)
        self.assertEqual(rig.table.input_registers[REG_MEASURE_ID], 0)

    def _alarm_12(self):
        rig = Rig()
        rig.reach(CLAMP)
        rig.scan()
        self.assertTrue(rig.plc.outputs["clamp_cmd"])
        for _ in range(20):
            rig.scan()
        self.assertEqual(rig.plc.alarm, 12)
        self.assertTrue(rig.plc.outputs["clamp_cmd"])
        return rig

    def test_t158_recovery_requires_safe_state_and_rising_edge(self):
        rig = self._alarm_12()
        rig.table.coils[RESET_COIL] = True
        rig.set(clamp_closed=True, clamp_open=False)
        rig.scan()
        self.assertEqual(rig.plc.state, ALARM)
        rig.table.coils[RESET_COIL] = False
        rig.scan()

        rig.table.coils[RELEASE_COIL] = True
        rig.scan()
        self.assertFalse(rig.plc.outputs["clamp_cmd"])
        rig.table.coils[RELEASE_COIL] = False
        rig.set(clamp_closed=False, clamp_open=True)
        rig.scan()
        self.assertFalse(rig.plc.outputs["clamp_cmd"])
        rig.table.coils[RESET_COIL] = True
        rig.scan()
        self.assertEqual(rig.plc.state, ALARM)

        rig.set(part_present=False, seated=False, direction_ok=False)
        rig.scan()
        self.assertEqual(rig.plc.state, ALARM)

        rig.table.coils[RESET_COIL] = False
        rig.scan()
        rig.table.coils[RESET_COIL] = True
        rig.judge(7, 1)
        rig.scan()
        self.assertEqual(rig.plc.state, IDLE)
        self.assertEqual(rig.plc.alarm, 0)
        self.assertEqual(rig.plc.counter, 0)
        self.assertEqual(rig.table.holding[1:3], [0, 0])
        self.assertFalse(rig.plc.release_latch)
        self.assertIn("aborted", rig.plc.events)

    def test_t158_measure_id_is_kept_and_published_value_is_cleared(self):
        rig = Rig()
        rig.reach(WAIT_JUDGE)
        self.assertEqual(rig.table.input_registers[REG_VALUE_LOW], 10250)
        for _ in range(31):
            rig.scan()
        self.assertEqual(rig.plc.alarm, 14)
        rig.table.coils[RELEASE_COIL] = True
        rig.scan()
        rig.set(clamp_closed=False, clamp_open=True, part_present=False, seated=False, direction_ok=False)
        rig.table.coils[RESET_COIL] = True
        rig.scan()
        self.assertEqual(rig.plc.state, IDLE)
        self.assertEqual(rig.plc.measure_id, 1)
        self.assertEqual(rig.table.input_registers[REG_MEASURE_ID], 1)
        self.assertEqual(rig.table.input_registers[REG_VALUE_HIGH:REG_VALUE_LOW + 1], [0, 0])
        self.assertTrue(rig.table.coils[RELEASE_COIL])

    def test_recovery_needs_living_heartbeat(self):
        rig = self._alarm_12()
        rig.table.coils[RELEASE_COIL] = True
        rig.scan()
        rig.set(clamp_closed=False, clamp_open=True, part_present=False, seated=False, direction_ok=False)
        for _ in range(11):
            rig.scan(beat=False)
        rig.table.coils[RESET_COIL] = True
        rig.scan(beat=False)
        self.assertEqual(rig.plc.state, ALARM)

    def test_manual_release_is_ignored_outside_alarm(self):
        rig = Rig()
        rig.table.coils[RELEASE_COIL] = True
        rig.reach(CLAMP)
        self.assertTrue(rig.plc.outputs["clamp_cmd"])
        for _ in range(21):
            rig.scan()
        self.assertEqual(rig.plc.alarm, 12)
        self.assertTrue(rig.plc.outputs["clamp_cmd"])

    def test_plc_heartbeat_wraps(self):
        rig = Rig()
        rig.table.input_registers[REG_HEARTBEAT] = 65535
        rig.scan()
        self.assertEqual(rig.table.input_registers[REG_HEARTBEAT], 0)


class JudgeTests(unittest.TestCase):
    def test_t165_measure_id_wraps_to_one(self):
        rig = Rig()
        rig.plc.measure_id = 65535
        rig.reach(WAIT_JUDGE)
        self.assertEqual(rig.plc.measure_id, 1)

    def test_t165_rejects_old_id_and_bad_value(self):
        rig = Rig()
        rig.reach(WAIT_JUDGE)
        rig.judge(rig.plc.measure_id + 1, 1)
        self.assertEqual(rig.scan(), WAIT_JUDGE)
        self.assertEqual(rig.plc.events, ["판정 거절: ID 불일치"])
        rig.judge(rig.plc.measure_id, 3)
        self.assertEqual(rig.scan(), WAIT_JUDGE)
        self.assertEqual(rig.plc.events, ["판정 거절: 판정 값 오류"])

    def test_t165_same_rejected_pair_is_recorded_once(self):
        rig = Rig()
        rig.reach(WAIT_JUDGE)
        rig.judge(9, 1)
        rig.scan()
        self.assertEqual(len(rig.plc.events), 1)
        rig.scan()
        self.assertEqual(rig.plc.events, [])

    def test_t165_returning_pair_is_not_recorded_again(self):
        rig = Rig()
        rig.reach(WAIT_JUDGE)
        recorded = []
        for pair in ((2, 1), (1, 3), (2, 1), (0, 0), (1, 3)):
            rig.judge(*pair)
            rig.scan()
            recorded.extend(rig.plc.events)
        self.assertEqual(len(recorded), 2)
        rig.judge(1, 1)
        self.assertEqual(rig.scan(), UNCLAMP)

    def test_t165_judge_written_after_entry_is_kept_and_accepted(self):
        rig = Rig()
        rig.reach(WAIT_JUDGE)
        self.assertEqual(rig.table.input_registers[REG_MEASURE_ID], 1)
        rig.judge(1, 1)
        self.assertEqual(rig.scan(), UNCLAMP)
        self.assertEqual(rig.plc.events, ["판정 접수"])

    def test_old_judge_is_cleared_on_entry(self):
        rig = Rig()
        rig.reach(PUBLISH)
        rig.judge(1, 1)
        rig.set(measure_done=False)
        rig.scan()
        self.assertEqual(rig.table.holding[1:3], [0, 0])
        self.assertEqual(rig.scan(), WAIT_JUDGE)


class HeartbeatTests(unittest.TestCase):
    def test_t166_alarm_after_last_change(self):
        rig = Rig()
        for _ in range(5):
            rig.scan()
        last = rig.plc.scan_number
        for _ in range(10):
            rig.scan(beat=False)
            self.assertEqual(rig.plc.alarm, 0)
        self.assertEqual(rig.plc.scan_number, last + 10)
        rig.scan(beat=False)
        self.assertEqual(rig.plc.alarm, 21)

    def test_t166_start_grace(self):
        rig = Rig()
        for _ in range(10):
            rig.scan(beat=False)
        self.assertEqual(rig.plc.alarm, 0)
        rig.scan(beat=False)
        self.assertEqual(rig.plc.alarm, 21)
        self.assertEqual(rig.plc.scan_number, 11)


if __name__ == "__main__":
    unittest.main()

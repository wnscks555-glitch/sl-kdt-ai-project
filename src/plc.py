"""LEAK 검사 스테이션 한 곳의 시퀀스를 스캔 주기 상태 기계로 모의한다. 실제 PLC 프로그램이 아니다."""

from dataclasses import dataclass
from typing import Mapping

from src.modbus import (
    HEARTBEAT_REGISTER, JUDGE_REGISTER, RELEASE_COIL, RESET_COIL, Table, ValueConversionError, to_words,
)


IDLE, CHECK, CLAMP, MEASURE, PUBLISH, WAIT_JUDGE, UNCLAMP, DISCHARGE, ALARM = range(9)
STATE_NAMES = ("IDLE", "CHECK", "CLAMP", "MEASURE", "PUBLISH", "WAIT_JUDGE", "UNCLAMP", "DISCHARGE", "ALARM")

INPUTS = ("part_present", "seated", "direction_ok", "clamp_closed", "clamp_open", "guard_closed", "measure_done")
OUTPUTS = ("clamp_cmd", "measure_cmd", "gate_ok", "gate_ng", "alarm_lamp")

ALARM_CHECK = 11
ALARM_CLAMP = 12
ALARM_MEASURE = 13
ALARM_JUDGE = 14
ALARM_UNCLAMP = 15
ALARM_DISCHARGE = 16
ALARM_HEARTBEAT = 21
ALARM_GUARD = 22
ALARM_CONVERSION = 23
ALARM_CLAMP_CONFLICT = 24
ALARM_MEASURE_SIGNAL = 25

TIMEOUT_ALARMS = {
    CHECK: ("check_scans", ALARM_CHECK),
    CLAMP: ("clamp_scans", ALARM_CLAMP),
    MEASURE: ("measure_scans", ALARM_MEASURE),
    WAIT_JUDGE: ("judge_scans", ALARM_JUDGE),
    UNCLAMP: ("unclamp_scans", ALARM_UNCLAMP),
    DISCHARGE: ("discharge_scans", ALARM_DISCHARGE),
}

REG_STATE, REG_ALARM, REG_MEASURE_ID, REG_VALUE_HIGH, REG_VALUE_LOW, REG_HEARTBEAT, REG_COUNT = range(7)
JUDGE_PASS = 1
JUDGE_FAIL = 2


@dataclass(frozen=True)
class Timing:
    heartbeat_scans: int
    timeouts: Mapping[str, int]


@dataclass(frozen=True)
class Snapshot:
    """스캔 시작 때 복사한 값이다. 스캔 중에는 이 값만 본다."""

    inputs: Mapping[str, bool]
    value: str
    reset: bool
    release: bool
    heartbeat: int
    judge: tuple


def interlock(requested, previous, inputs, state):
    """기본 출력에 인터록을 적용한다. 출력 갱신의 마지막 단계다."""
    outputs = dict(requested)
    if outputs["clamp_cmd"] and not previous["clamp_cmd"] and not (
            inputs["seated"] and inputs["direction_ok"] and inputs["guard_closed"]):
        outputs["clamp_cmd"] = False
    if outputs["measure_cmd"] and not (
            inputs["clamp_closed"] and not inputs["clamp_open"] and inputs["guard_closed"]):
        outputs["measure_cmd"] = False
    if outputs["gate_ok"] and outputs["gate_ng"]:
        outputs["gate_ok"] = outputs["gate_ng"] = False
    if not inputs["clamp_open"] or inputs["clamp_closed"]:
        outputs["gate_ok"] = outputs["gate_ng"] = False
    if state == ALARM:
        outputs["measure_cmd"] = outputs["gate_ok"] = outputs["gate_ng"] = False
    return outputs


class Plc:
    """주소표를 입출력으로 삼아 스캔을 돈다. `scan` 한 번이 스캔 하나다."""

    def __init__(self, table: Table, timing: Timing):
        self.table = table
        self.timing = timing
        self.scan_number = 0
        self.state = IDLE
        self.counter = 0
        self.alarm = 0
        self.outputs = {name: False for name in OUTPUTS}
        self.previous_reset = False
        self.previous_release = False
        self.previous_heartbeat = 0
        self.heartbeat_scan = 0
        self.release_latch = False
        self.measure_id = 0
        self.value = ""
        self.verdict = 0
        self.rejected = None
        self.processed = 0
        self.ok_count = 0
        self.ng_count = 0
        self.events = []

    def _snapshot(self, value):
        with self.table.lock:
            return Snapshot(
                dict(zip(INPUTS, self.table.discrete)), value, self.table.coils[RESET_COIL],
                self.table.coils[RELEASE_COIL], self.table.holding[HEARTBEAT_REGISTER],
                tuple(self.table.holding[JUDGE_REGISTER:JUDGE_REGISTER + 2]))

    def _go(self, state):
        self.state = state
        self.counter = 0
        return True

    def _raise(self, code):
        self.alarm = code
        self.events.append("알람 %d" % code)
        return self._go(ALARM)

    def _heartbeat_late(self):
        return self.scan_number - self.heartbeat_scan > self.timing.heartbeat_scans

    def _measure_ready(self, snap):
        return (self.outputs["measure_cmd"] and snap.inputs["clamp_closed"] and not snap.inputs["clamp_open"])

    def _immediate_alarm(self, snap):
        inputs = snap.inputs
        if not inputs["guard_closed"]:
            return ALARM_GUARD
        if self._heartbeat_late():
            return ALARM_HEARTBEAT
        if inputs["clamp_closed"] and inputs["clamp_open"]:
            return ALARM_CLAMP_CONFLICT
        if self.state in (CHECK, CLAMP) and inputs["measure_done"]:
            return ALARM_MEASURE_SIGNAL
        if self.state == MEASURE and inputs["measure_done"] and not self._measure_ready(snap):
            return ALARM_MEASURE_SIGNAL
        return 0

    def _publish(self):
        """변환이 성공하면 판정 지우기, 측정값 기록, ID 증가를 한 번에 한다."""
        try:
            high, low = to_words(self.value)
        except ValueConversionError:
            return self._raise(ALARM_CONVERSION)
        self.measure_id = self.measure_id % 65535 + 1
        with self.table.lock:
            self.table.holding[JUDGE_REGISTER:JUDGE_REGISTER + 2] = [0, 0]
            self.table.input_registers[REG_VALUE_HIGH] = high
            self.table.input_registers[REG_VALUE_LOW] = low
        self.rejected = None
        return self._go(WAIT_JUDGE)

    def _judge(self, snap):
        pair = snap.judge
        if pair == (0, 0):
            return False
        if pair[0] == self.measure_id and pair[1] in (JUDGE_PASS, JUDGE_FAIL):
            self.verdict = pair[1]
            self.events.append("판정 접수")
            return self._go(UNCLAMP)
        if pair != self.rejected:
            self.rejected = pair
            reason = "ID 불일치" if pair[0] != self.measure_id else "판정 값 오류"
            self.events.append("판정 거절: " + reason)
        return False

    def _discharged(self):
        self.processed = (self.processed + 1) % 65536
        if self.verdict == JUDGE_PASS:
            self.ok_count += 1
        else:
            self.ng_count += 1
        self.verdict = 0
        self.value = ""
        return self._go(IDLE)

    def _recoverable(self, snap):
        inputs = snap.inputs
        return (inputs["guard_closed"] and not self._heartbeat_late() and inputs["clamp_open"]
                and not inputs["clamp_closed"] and not inputs["part_present"])

    def _recover(self):
        self.alarm = 0
        self.value = ""
        self.verdict = 0
        self.release_latch = False
        self.events.append("aborted")
        with self.table.lock:
            self.table.holding[JUDGE_REGISTER:JUDGE_REGISTER + 2] = [0, 0]
        return self._go(IDLE)

    def _transition(self, snap, reset_edge):
        inputs = snap.inputs
        state = self.state
        if state == IDLE:
            return inputs["part_present"] and not inputs["measure_done"] and self._go(CHECK)
        if state == CHECK:
            return inputs["seated"] and inputs["direction_ok"] and self._go(CLAMP)
        if state == CLAMP:
            return inputs["clamp_closed"] and self._go(MEASURE)
        if state == MEASURE:
            if inputs["measure_done"]:
                self.value = snap.value
                return self._go(PUBLISH)
            return False
        if state == PUBLISH:
            return self._publish()
        if state == WAIT_JUDGE:
            return self._judge(snap)
        if state == UNCLAMP:
            return inputs["clamp_open"] and self._go(DISCHARGE)
        if state == DISCHARGE:
            return not inputs["part_present"] and self._discharged()
        return reset_edge and self._recoverable(snap) and self._recover()

    def _timeout(self):
        if self.state not in TIMEOUT_ALARMS:
            return
        key, code = TIMEOUT_ALARMS[self.state]
        self.counter += 1
        if self.counter > self.timing.timeouts[key]:
            self._raise(code)

    def _requested(self):
        state = self.state
        outputs = {name: False for name in OUTPUTS}
        outputs["clamp_cmd"] = state in (CLAMP, MEASURE, PUBLISH, WAIT_JUDGE)
        outputs["measure_cmd"] = state == MEASURE
        outputs["gate_ok"] = state == DISCHARGE and self.verdict == JUDGE_PASS
        outputs["gate_ng"] = state == DISCHARGE and self.verdict == JUDGE_FAIL
        if state == ALARM:
            outputs["alarm_lamp"] = True
            outputs["clamp_cmd"] = self.outputs["clamp_cmd"] and not self.release_latch
        return outputs

    def _write(self):
        with self.table.lock:
            self.table.coils[:len(OUTPUTS)] = [self.outputs[name] for name in OUTPUTS]
            registers = self.table.input_registers
            registers[REG_STATE] = self.state
            registers[REG_ALARM] = self.alarm
            registers[REG_MEASURE_ID] = self.measure_id
            registers[REG_HEARTBEAT] = (registers[REG_HEARTBEAT] + 1) % 65536
            registers[REG_COUNT] = self.processed

    def scan(self, value="", after_snapshot=None):
        """스캔 하나를 돈다. after_snapshot은 스냅샷 격리를 확인하는 시험용 훅이다."""
        self.scan_number += 1
        self.events = []
        snap = self._snapshot(value)
        if after_snapshot is not None:
            after_snapshot()
        if snap.heartbeat != self.previous_heartbeat:
            self.previous_heartbeat = snap.heartbeat
            self.heartbeat_scan = self.scan_number
        reset_edge = snap.reset and not self.previous_reset
        release_edge = snap.release and not self.previous_release
        self.previous_reset, self.previous_release = snap.reset, snap.release
        if self.state == ALARM and release_edge:
            self.release_latch = True
        code = 0 if self.state == ALARM else self._immediate_alarm(snap)
        if code:
            self._raise(code)
        elif not self._transition(snap, reset_edge):
            self._timeout()
        self.outputs = interlock(self._requested(), self.outputs, snap.inputs, self.state)
        self._write()
        return self.state

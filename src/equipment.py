"""검사 설비 설정 로딩과 전체 오류 검증."""

from dataclasses import dataclass, replace
import hashlib
import json
from pathlib import Path
import re
from typing import Dict, Mapping, Optional, Tuple

from .recipe import ModelRecipe


@dataclass(frozen=True)
class EquipmentBook:
    window: int
    fails: int
    equipment: Dict[str, str]
    sha256: str
    restart_enabled: bool = False


@dataclass(frozen=True)
class EquipmentState:
    counted_results: int = 0
    fail_count: int = 0
    recent_results: Tuple[str, ...] = ()
    stopped_at_seq: Optional[str] = None
    stop_count: int = 0
    restart_count: int = 0
    last_restart_result: str = ""

    @property
    def state(self) -> str:
        return "정지" if self.stopped_at_seq is not None else "가동"

    def record(self, result: str, seq: str, book: EquipmentBook):
        recent = (self.recent_results + (result,))[-book.window:]
        stopped = recent.count("FAIL") >= book.fails
        return replace(
            self, counted_results=self.counted_results + 1,
            fail_count=self.fail_count + (result == "FAIL"), recent_results=recent,
            stopped_at_seq=seq if stopped else None, stop_count=self.stop_count + stopped,
        )

    def restart(self, result: str):
        """정지 전 FAIL이 재가동 뒤 창에 남지 않게 한다. 누적 건수는 유지한다."""
        return replace(
            self, recent_results=(), stopped_at_seq=None,
            restart_count=self.restart_count + 1, last_restart_result=result,
        )


class EquipmentError(ValueError):
    def __init__(self, errors):
        self.errors = tuple(errors)
        super().__init__("\n".join(self.errors))


def load_equipment(path: Path, models: Mapping[str, ModelRecipe]) -> EquipmentBook:
    try:
        content = path.read_bytes()
        data = json.loads(content.decode("utf-8-sig"))
    except (OSError, UnicodeError, ValueError) as error:
        raise EquipmentError(["$: 설비 읽기 또는 JSON 오류: " + str(error)]) from error

    if not isinstance(data, dict):
        raise EquipmentError(["$: 최상위는 객체여야 함"])
    errors = []

    def check_keys(value, allowed, location):
        for key in value:
            if key not in allowed:
                errors.append(location + "." + key + ": 허용하지 않은 키")

    check_keys(data, ("stop_rule", "equipment", "restart_enabled"), "$")
    restart_enabled = data.get("restart_enabled", False)
    if type(restart_enabled) is not bool:
        errors.append("restart_enabled: true 또는 false여야 함 (문자열·숫자 불가)")
    elif restart_enabled:
        for model_id, model in models.items():
            if "EQUIP_RESTART" in model.steps:
                errors.append(model_id + ".steps: 재가동 모드에서 EQUIP_RESTART는 공정 ID로 사용할 수 없음")
    rule = data.get("stop_rule")
    if not isinstance(rule, dict):
        errors.append("stop_rule: 객체여야 함")
        rule = {}
    check_keys(rule, ("window", "fails"), "stop_rule")
    window, fails = rule.get("window"), rule.get("fails")
    for name, value in (("window", window), ("fails", fails)):
        if type(value) is not int or not 1 <= value <= 20:
            errors.append("stop_rule." + name + ": 1–20 정수여야 함 (bool·문자열 불가)")
    if type(window) is int and type(fails) is int and fails > window:
        errors.append("stop_rule.fails: window 이하여야 함")

    equipment = data.get("equipment")
    inspections = {item.id for model in models.values() for item in model.inspections}
    if not isinstance(equipment, dict) or not equipment:
        errors.append("equipment: 비어 있지 않은 객체여야 함")
    if isinstance(equipment, dict):
        for name, inspection in equipment.items():
            location = "equipment." + name
            if re.fullmatch(r"[A-Z][A-Z0-9_-]*", name) is None:
                errors.append(location + ": 설비 ID 형식은 ^[A-Z][A-Z0-9_-]*$ 이어야 함")
            if not isinstance(inspection, str) or inspection not in inspections:
                errors.append(location + ": 레시피에 없는 검사 ID")
    if errors:
        raise EquipmentError(errors)
    return EquipmentBook(window, fails, equipment, hashlib.sha256(content).hexdigest(), restart_enabled)

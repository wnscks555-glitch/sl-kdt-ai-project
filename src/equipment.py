"""검사 설비 설정 로딩과 전체 오류 검증."""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Dict, Mapping

from .recipe import ModelRecipe


@dataclass(frozen=True)
class EquipmentBook:
    window: int
    fails: int
    equipment: Dict[str, str]
    sha256: str


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

    check_keys(data, ("stop_rule", "equipment"), "$")
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
    return EquipmentBook(window, fails, equipment, hashlib.sha256(content).hexdigest())

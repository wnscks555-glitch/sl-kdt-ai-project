from dataclasses import dataclass
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
from typing import Dict, Mapping, Optional, Tuple


MAX_DECIMAL_DIGITS = 30
SPEC_KEYS = ("lsl", "usl", "unit")


def is_decimal_text(value) -> bool:
    """규격과 측정값의 공통 형식이다. 부호와 소수점을 뺀 숫자는 30자리까지다."""
    return (isinstance(value, str) and re.fullmatch(r"-?[0-9]+(\.[0-9]+)?", value) is not None
            and sum(character.isdigit() for character in value) <= MAX_DECIMAL_DIGITS)


@dataclass(frozen=True)
class Inspection:
    id: str
    after: str
    lsl: Optional[str] = None
    usl: Optional[str] = None
    unit: Optional[str] = None


@dataclass(frozen=True)
class ModelRecipe:
    steps: Tuple[str, ...]
    inspections: Tuple[Inspection, ...]
    retest_limit: Optional[int] = None


def is_measured(models: Mapping[str, ModelRecipe]) -> bool:
    return any(item.unit is not None for model in models.values() for item in model.inspections)


@dataclass(frozen=True)
class RecipeBook:
    models: Dict[str, ModelRecipe]
    sha256: str

    @property
    def retest_enabled(self) -> bool:
        return all(model.retest_limit is not None for model in self.models.values())

    @property
    def measured(self) -> bool:
        return is_measured(self.models)


class RecipeError(ValueError):
    def __init__(self, errors):
        self.errors = tuple(errors)
        super().__init__("\n".join(self.errors))


def load_recipe(path: Path) -> RecipeBook:
    try:
        content = path.read_bytes()
        data = json.loads(content.decode("utf-8-sig"))
    except (OSError, UnicodeError, ValueError) as error:
        raise RecipeError(["$: 레시피 읽기 또는 JSON 오류: " + str(error)]) from error

    errors = []

    def check_id(value, location):
        if not isinstance(value, str) or re.fullmatch(r"[A-Z][A-Z0-9_]*", value) is None:
            errors.append(location + ": ID 형식은 ^[A-Z][A-Z0-9_]*$ 이어야 함")
            return False
        return True

    def check_keys(value, allowed, location):
        for key in value:
            if key not in allowed:
                errors.append(location + "." + key + ": 허용하지 않은 키")

    def check_spec(item, location):
        missing = [key for key in SPEC_KEYS if key not in item]
        for key in missing:
            errors.append(location + "." + key + ": 규격을 쓰면 모든 검사 항목에 있어야 함")
        if missing:
            return
        limits = {}
        for key in ("lsl", "usl"):
            if item[key] is not None and not is_decimal_text(item[key]):
                errors.append(location + "." + key + ": null 또는 30자리 이하의 문자열 소수여야 함")
            elif item[key] is not None:
                limits[key] = Decimal(item[key])
        if item["lsl"] is None and item["usl"] is None:
            errors.append(location + ": lsl과 usl이 모두 null일 수 없음")
        if len(limits) == 2 and limits["lsl"] >= limits["usl"]:
            errors.append(location + ": lsl은 usl보다 작아야 함")
        if not isinstance(item["unit"], str) or not item["unit"].strip():
            errors.append(location + ".unit: 공백이 아닌 문자열이어야 함")

    if not isinstance(data, dict):
        raise RecipeError(["$: 최상위는 객체여야 함"])
    if not data:
        raise RecipeError(["$: 모델이 1개 이상 필요함"])

    retest_enabled = any(isinstance(body, dict) and "retest_limit" in body for body in data.values())
    measured = any(
        isinstance(item, dict) and any(key in item for key in SPEC_KEYS)
        for body in data.values() if isinstance(body, dict) and isinstance(body.get("inspections"), list)
        for item in body["inspections"]
    )
    specs = {}
    models = {}
    for model, body in data.items():
        check_id(model, model)
        if not isinstance(body, dict):
            errors.append(model + ": 모델 설정은 객체여야 함")
            continue
        check_keys(body, ("steps", "inspections", "retest_limit"), model)
        limit = body.get("retest_limit")
        if retest_enabled and "retest_limit" not in body:
            errors.append(model + ".retest_limit: 모든 모델에 설정해야 함")
        elif "retest_limit" in body and (type(limit) is not int or not 1 <= limit <= 5):
            errors.append(model + ".retest_limit: 1–5 정수여야 함 (bool·문자열 불가)")
        steps = body.get("steps")
        valid_steps = set()
        if not isinstance(steps, list) or not steps or any(
            not isinstance(step, str) for step in steps
        ):
            errors.append(model + ".steps: 비어 있지 않은 문자열 ID 배열이어야 함")
        if isinstance(steps, list):
            for index, step in enumerate(steps):
                location = model + ".steps[" + str(index) + "]"
                if not check_id(step, location):
                    continue
                if step in valid_steps:
                    errors.append(location + ": 공정 ID 중복 " + step)
                if step in ("REGISTER", "INSPECT", "RETEST_REQUEST"):
                    errors.append(location + ": 예약어는 공정 ID로 사용할 수 없음 " + step)
                valid_steps.add(step)

        inspections = body.get("inspections")
        seen = set()
        if not isinstance(inspections, list) or not inspections:
            errors.append(model + ".inspections: 비어 있지 않은 배열이어야 함")
        if isinstance(inspections, list):
            for index, item in enumerate(inspections):
                location = model + ".inspections[" + str(index) + "]"
                if not isinstance(item, dict):
                    errors.append(location + ": 검사 항목은 객체여야 함")
                    continue
                check_keys(item, ("id", "after") + SPEC_KEYS, location)
                name = item.get("id")
                if check_id(name, location + ".id"):
                    if name in seen:
                        errors.append(location + ".id: 검사 ID 중복 " + name)
                    seen.add(name)
                after = item.get("after")
                if check_id(after, location + ".after") and after not in valid_steps:
                    errors.append(location + ".after: 모델에 없는 공정 " + after)
                if measured:
                    before = len(errors)
                    check_spec(item, location)
                    if len(errors) == before and isinstance(name, str):
                        spec = tuple(None if item[key] is None else Decimal(item[key]) for key in ("lsl", "usl"))
                        spec += (item["unit"],)
                        if specs.setdefault(name, spec) != spec:
                            errors.append(location + ": 같은 검사 ID는 모델이 달라도 규격과 단위가 같아야 함")

        if not errors:
            models[model] = ModelRecipe(
                tuple(steps),
                tuple(Inspection(item["id"], item["after"], item.get("lsl"), item.get("usl"), item.get("unit"))
                      for item in inspections),
                limit,
            )

    if errors:
        raise RecipeError(errors)
    return RecipeBook(models, hashlib.sha256(content).hexdigest())

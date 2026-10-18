from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Dict, Tuple


@dataclass(frozen=True)
class Inspection:
    id: str
    after: str


@dataclass(frozen=True)
class ModelRecipe:
    steps: Tuple[str, ...]
    inspections: Tuple[Inspection, ...]


@dataclass(frozen=True)
class RecipeBook:
    models: Dict[str, ModelRecipe]
    sha256: str


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

    if not isinstance(data, dict):
        raise RecipeError(["$: 최상위는 객체여야 함"])
    if not data:
        raise RecipeError(["$: 모델이 1개 이상 필요함"])

    models = {}
    for model, body in data.items():
        check_id(model, model)
        if not isinstance(body, dict):
            errors.append(model + ": 모델 설정은 객체여야 함")
            continue
        check_keys(body, ("steps", "inspections"), model)
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
                if step in ("REGISTER", "INSPECT"):
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
                check_keys(item, ("id", "after"), location)
                name = item.get("id")
                if check_id(name, location + ".id"):
                    if name in seen:
                        errors.append(location + ".id: 검사 ID 중복 " + name)
                    seen.add(name)
                after = item.get("after")
                if check_id(after, location + ".after") and after not in valid_steps:
                    errors.append(location + ".after: 모델에 없는 공정 " + after)

        if not errors:
            models[model] = ModelRecipe(
                tuple(steps), tuple(Inspection(item["id"], item["after"]) for item in inspections)
            )

    if errors:
        raise RecipeError(errors)
    return RecipeBook(models, hashlib.sha256(content).hexdigest())

"""제품별 선형 레시피 판정. 파일과 터미널 입출력은 하지 않는다."""

from dataclasses import dataclass, field, replace
from typing import Dict, Mapping

from .recipe import ModelRecipe


INPUT_COLUMNS = ("seq", "product_id", "event", "inspection", "result", "model")
RULE_IDS = (
    "RULE_RECIPE",
    "RULE_SEQ",
    "RULE_INSP_PRE",
    "RULE_NOT_DONE",
    "RULE_FAIL_HOLD",
    "RULE_PRESERVE",
)


@dataclass(frozen=True)
class RecipeProduct:
    model: str
    recipe: ModelRecipe
    completed_steps: int = 0
    inspections: Dict[str, str] = field(default_factory=dict)

    @property
    def status(self) -> str:
        if "FAIL" in self.inspections.values():
            return "보류"
        if self.completed_steps == len(self.recipe.steps) and all(
            self.inspections.get(item.id) == "PASS" for item in self.recipe.inspections
        ):
            return "레시피 모의 흐름 완료"
        if self.completed_steps == 0:
            return "등록"
        if self.completed_steps < len(self.recipe.steps):
            return "공정 진행 중(" + self.recipe.steps[self.completed_steps - 1] + " 완료)"
        return "검사 대기"

    @property
    def incomplete_reason(self) -> str:
        reasons = [step + " 미완료" for step in self.recipe.steps[self.completed_steps:]]
        for item in self.recipe.inspections:
            result = self.inspections.get(item.id)
            if result is None:
                reasons.append(item.id + " 미실시")
            elif result == "FAIL":
                reasons.append(item.id + " FAIL")
        return "; ".join(reasons)


@dataclass(frozen=True)
class Decision:
    seq: str
    product_id: str
    input_text: str
    rule_id: str
    accepted: bool
    reason: str
    state: str


class RecipeProcess:
    def __init__(self, models: Mapping[str, ModelRecipe]) -> None:
        self.models = models
        self.products: Dict[str, RecipeProduct] = {}

    def apply(self, row: Mapping[str, str]) -> Decision:
        invalid = self._invalid_fields(row)
        if invalid:
            return self._decision(row, "RULE_PRESERVE", False, invalid)

        product_id = row["product_id"]
        event = row["event"]
        product = self.products.get(product_id)
        if event == "REGISTER":
            if product is not None:
                return self._decision(row, "RULE_PRESERVE", False, "이미 등록된 제품")
            model = row["model"]
            if model not in self.models:
                return self._decision(row, "RULE_RECIPE", False, "model이 비어 있거나 레시피에 없는 모델")
            updated = RecipeProduct(model, self.models[model])
            rule_id = "RULE_RECIPE"
        elif product is None:
            return self._decision(row, "RULE_PRESERVE", False, "미등록 제품")
        elif event == "INSPECT":
            inspection = row["inspection"]
            item = next((item for item in product.recipe.inspections if item.id == inspection), None)
            if item is None:
                return self._decision(row, "RULE_RECIPE", False, "제품 레시피에 없는 검사 " + inspection)
            if product.completed_steps <= product.recipe.steps.index(item.after):
                return self._decision(row, "RULE_INSP_PRE", False, item.after + " 미완료")
            if inspection in product.inspections:
                return self._decision(row, "RULE_PRESERVE", False, inspection + " 결과 이미 존재")
            updated = replace(product, inspections={**product.inspections, inspection: row["result"]})
            rule_id = (
                "RULE_FAIL_HOLD"
                if updated.status in ("보류", "레시피 모의 흐름 완료")
                else "RULE_NOT_DONE"
            )
        else:
            if event not in product.recipe.steps:
                return self._decision(row, "RULE_RECIPE", False, "제품 레시피에 없는 공정 " + event)
            target = product.recipe.steps.index(event)
            if target < product.completed_steps:
                return self._decision(row, "RULE_PRESERVE", False, "이미 지난 공정 재입력")
            if product.status == "보류":
                return self._decision(row, "RULE_FAIL_HOLD", False, "FAIL로 보류 중인 제품")
            if target != product.completed_steps:
                return self._decision(
                    row, "RULE_SEQ", False, product.recipe.steps[product.completed_steps] + " 미완료"
                )
            updated = replace(product, completed_steps=product.completed_steps + 1)
            rule_id = "RULE_SEQ"

        self.products[product_id] = updated
        return self._decision(row, rule_id, True, "")

    @staticmethod
    def _invalid_fields(row: Mapping[str, str]) -> str:
        if set(row) != set(INPUT_COLUMNS) or any(
            not isinstance(row.get(name), str) for name in INPUT_COLUMNS
        ):
            return "CSV 열 수 또는 값 누락"
        seq = row["seq"]
        if not seq.isascii() or not seq.isdigit() or int(seq) <= 0:
            return "seq는 양의 정수여야 함"
        if not row["product_id"].strip():
            return "product_id가 비어 있음"
        if not row["event"]:
            return "event가 비어 있음"
        if row["event"] != "REGISTER" and row["model"]:
            return "REGISTER 이외의 model은 빈칸이어야 함"
        if row["event"] == "INSPECT":
            if not row["inspection"]:
                return "inspection이 비어 있음"
            if row["result"] not in ("PASS", "FAIL"):
                return "잘못된 result (PASS 또는 FAIL 필요)"
        elif row["inspection"] or row["result"]:
            return "INSPECT 이외의 inspection과 result는 빈칸이어야 함"
        return ""

    def _decision(self, row: Mapping[str, str], rule_id: str, accepted: bool, reason: str) -> Decision:
        product_id = str(row.get("product_id") or "")
        product = self.products.get(product_id)
        return Decision(
            seq=str(row.get("seq") or ""),
            product_id=product_id,
            input_text=" ".join(
                str(row.get(name) or "") for name in ("event", "inspection", "result")
            ).rstrip(),
            rule_id=rule_id,
            accepted=accepted,
            reason=reason,
            state=product.status if product is not None else "미등록",
        )

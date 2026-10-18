"""제품별 선형 레시피 판정. 파일과 터미널 입출력은 하지 않는다."""

from dataclasses import dataclass, field, replace
from typing import Dict, FrozenSet, Mapping, Optional, Tuple

from .recipe import ModelRecipe
from .equipment import EquipmentBook, EquipmentState


INPUT_COLUMNS = ("seq", "product_id", "event", "inspection", "result", "model")
EQUIPMENT_INPUT_COLUMNS = INPUT_COLUMNS + ("equipment",)
RULE_IDS = (
    "RULE_RECIPE",
    "RULE_SEQ",
    "RULE_INSP_PRE",
    "RULE_NOT_DONE",
    "RULE_FAIL_HOLD",
    "RULE_PRESERVE",
)


@dataclass(frozen=True)
class InspectionAttempt:
    seq: str
    result: str
    retest_number: int = 0
    equipment: str = ""

    @property
    def text(self) -> str:
        suffix = "(재검사 " + str(self.retest_number) + ")" if self.retest_number else ""
        equipment = "[" + self.equipment + "]" if self.equipment else ""
        return self.result + "@" + self.seq + equipment + suffix


@dataclass(frozen=True)
class RecipeProduct:
    model: str
    recipe: ModelRecipe
    completed_steps: int = 0
    inspections: Dict[str, str] = field(default_factory=dict)
    open_requests: FrozenSet[str] = frozenset()
    retest_counts: Dict[str, int] = field(default_factory=dict)
    inspection_history: Dict[str, Tuple[InspectionAttempt, ...]] = field(default_factory=dict)
    discarded_inspection: Optional[str] = None

    @property
    def history(self) -> str:
        return "; ".join(
            item.id + ": " + " → ".join(attempt.text for attempt in self.inspection_history[item.id])
            for item in self.recipe.inspections if item.id in self.inspection_history
        )

    @property
    def status(self) -> str:
        if self.discarded_inspection is not None:
            return "폐기"
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
        if self.discarded_inspection is not None:
            return self.discarded_inspection + " 재검사 한도 " + str(self.recipe.retest_limit) + "회 초과 FAIL로 폐기"
        reasons = [step + " 미완료" for step in self.recipe.steps[self.completed_steps:]]
        for item in self.recipe.inspections:
            result = self.inspections.get(item.id)
            if result is None:
                reasons.append(item.id + " 미실시")
            elif result == "FAIL":
                suffix = "(재검사 요청됨)" if item.id in self.open_requests else ""
                reasons.append(item.id + " FAIL" + suffix)
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
    def __init__(self, models: Mapping[str, ModelRecipe], equipment_book: Optional[EquipmentBook] = None) -> None:
        self.models = models
        self.retest_enabled = all(model.retest_limit is not None for model in models.values())
        self.products: Dict[str, RecipeProduct] = {}
        self.equipment_book = equipment_book
        self.equipment = {name: EquipmentState() for name in equipment_book.equipment} if equipment_book else {}

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
        elif product.discarded_inspection is not None:
            return self._decision(row, "RULE_RETEST", False, "폐기된 제품")
        elif event in ("INSPECT", "RETEST_REQUEST"):
            if event == "RETEST_REQUEST" and not self.retest_enabled:
                return self._decision(row, "RULE_RECIPE", False, "재검사 모드가 아닌 레시피")
            inspection = row["inspection"]
            item = next((item for item in product.recipe.inspections if item.id == inspection), None)
            if item is None:
                return self._decision(row, "RULE_RECIPE", False, "제품 레시피에 없는 검사 " + inspection)
            if event == "RETEST_REQUEST":
                if inspection in product.open_requests:
                    return self._decision(row, "RULE_RETEST", False, "이미 열린 재검사 요청")
                if product.inspections.get(inspection) != "FAIL":
                    return self._decision(row, "RULE_RETEST", False, "미해결 FAIL 없음")
                updated = replace(product, open_requests=product.open_requests | {inspection})
                attempt = InspectionAttempt(row["seq"], "요청")
                rule_id = "RULE_RETEST"
            else:
                if self.equipment_book is not None:
                    equipment = row["equipment"]
                    if equipment not in self.equipment:
                        return self._decision(row, "RULE_EQUIP", False, "등록되지 않은 설비")
                    if self.equipment_book.equipment[equipment] != inspection:
                        return self._decision(row, "RULE_EQUIP", False, "검사 종류가 다른 설비")
                    if self.equipment[equipment].stopped_at_seq is not None:
                        return self._decision(row, "RULE_EQUIP", False, "정지된 설비")
                if product.completed_steps <= product.recipe.steps.index(item.after):
                    return self._decision(row, "RULE_INSP_PRE", False, item.after + " 미완료")
                result = row["result"]
                if inspection in product.inspections:
                    if inspection not in product.open_requests:
                        return self._decision(row, "RULE_PRESERVE", False, inspection + " 결과 이미 존재")
                    count = product.retest_counts.get(inspection, 0) + 1
                    updated = replace(
                        product, inspections={**product.inspections, inspection: result},
                        open_requests=product.open_requests - {inspection},
                        retest_counts={**product.retest_counts, inspection: count},
                        discarded_inspection=(
                            inspection if count >= product.recipe.retest_limit and result == "FAIL" else None
                        ),
                    )
                    attempt = InspectionAttempt(row["seq"], result, count, row.get("equipment", ""))
                    rule_id = "RULE_RETEST"
                else:
                    updated = replace(product, inspections={**product.inspections, inspection: result})
                    attempt = InspectionAttempt(row["seq"], result, equipment=row.get("equipment", ""))
                    rule_id = (
                        "RULE_FAIL_HOLD"
                        if updated.status in ("보류", "레시피 모의 흐름 완료")
                        else "RULE_NOT_DONE"
                    )
            if self.retest_enabled:
                updated = replace(updated, inspection_history={
                    **product.inspection_history,
                    inspection: product.inspection_history.get(inspection, ()) + (attempt,),
                })
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

        if self.equipment_book is not None and event == "INSPECT" and row["inspection"] not in product.inspections:
            equipment = row["equipment"]
            self.equipment[equipment] = self.equipment[equipment].record(row["result"], row["seq"], self.equipment_book)
        self.products[product_id] = updated
        return self._decision(row, rule_id, True, "")

    def _invalid_fields(self, row: Mapping[str, str]) -> str:
        columns = EQUIPMENT_INPUT_COLUMNS if self.equipment_book is not None else INPUT_COLUMNS
        if set(row) != set(columns) or any(
            not isinstance(row.get(name), str) for name in columns
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
        elif row["event"] == "RETEST_REQUEST":
            if not row["inspection"]:
                return "inspection이 비어 있음"
            if row["result"]:
                return "RETEST_REQUEST의 result는 빈칸이어야 함"
        elif row["inspection"] or row["result"]:
            return "INSPECT 이외의 inspection과 result는 빈칸이어야 함"
        if self.equipment_book is not None:
            if row["event"] == "INSPECT" and not row["equipment"]:
                return "equipment가 비어 있음"
            if row["event"] != "INSPECT" and row["equipment"]:
                return "INSPECT 이외의 equipment는 빈칸이어야 함"
        return ""

    def _decision(self, row: Mapping[str, str], rule_id: str, accepted: bool, reason: str) -> Decision:
        product_id = str(row.get("product_id") or "")
        product = self.products.get(product_id)
        equipment = ""
        if self.equipment_book is not None and row.get("event") == "INSPECT" and row.get("equipment"):
            equipment = " @" + str(row["equipment"])
        return Decision(
            seq=str(row.get("seq") or ""),
            product_id=product_id,
            input_text=" ".join(
                str(row.get(name) or "") for name in ("event", "inspection", "result")
            ).rstrip() + equipment,
            rule_id=rule_id,
            accepted=accepted,
            reason=reason,
            state=product.status if product is not None else "미등록",
        )

"""가상 공정 규칙. 파일이나 터미널에 접근하지 않는다."""

from dataclasses import dataclass, field, replace
from typing import Dict, Mapping


INPUT_COLUMNS = ("seq", "product_id", "event", "inspection", "result")
STAGES = ("REGISTER", "PRE_ASSEMBLY", "MAIN_ASSEMBLY")
INSPECTIONS = ("LIGHT", "LEAK")
RULE_IDS = (
    "RULE_SEQ",
    "RULE_INSP_PRE",
    "RULE_NOT_DONE",
    "RULE_FAIL_HOLD",
    "RULE_PRESERVE",
)


@dataclass(frozen=True)
class Product:
    stage: str = "REGISTER"
    inspections: Dict[str, str] = field(default_factory=dict)

    @property
    def status(self) -> str:
        if "FAIL" in self.inspections.values():
            return "보류"
        if self.stage == "REGISTER":
            return "등록"
        if self.stage == "PRE_ASSEMBLY":
            return "예비 조립"
        if all(self.inspections.get(name) == "PASS" for name in INSPECTIONS):
            return "선택한 두 검사까지의 모의 흐름 완료"
        return "검사 대기"

    @property
    def incomplete_reason(self) -> str:
        reasons = []
        if self.stage == "REGISTER":
            reasons.append("PRE_ASSEMBLY 미완료")
        if self.stage != "MAIN_ASSEMBLY":
            reasons.append("MAIN_ASSEMBLY 미완료")
        for name in INSPECTIONS:
            if name not in self.inspections:
                reasons.append(name + " 미실시")
            elif self.inspections[name] == "FAIL":
                reasons.append(name + " FAIL")
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


class Process:
    def __init__(self) -> None:
        self.products: Dict[str, Product] = {}

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
            updated = Product()
            rule_id = "RULE_SEQ"
        elif product is None:
            return self._decision(row, "RULE_PRESERVE", False, "미등록 제품")
        elif event in STAGES:
            current = STAGES.index(product.stage)
            target = STAGES.index(event)
            if current >= target:
                return self._decision(row, "RULE_PRESERVE", False, "중복 조립 이벤트")
            if current + 1 != target:
                return self._decision(
                    row, "RULE_SEQ", False, STAGES[target - 1] + " 미완료"
                )
            updated = replace(product, stage=event)
            rule_id = "RULE_SEQ"
        else:
            if product.stage != "MAIN_ASSEMBLY":
                return self._decision(row, "RULE_INSP_PRE", False, "MAIN_ASSEMBLY 미완료")
            inspection = row["inspection"]
            if inspection in product.inspections:
                return self._decision(row, "RULE_PRESERVE", False, inspection + " 결과 이미 존재")
            updated = replace(
                product, inspections={**product.inspections, inspection: row["result"]}
            )
            rule_id = (
                "RULE_NOT_DONE" if updated.status == "검사 대기" else "RULE_FAIL_HOLD"
            )

        # 모든 거절 조건을 확인한 뒤 새 상태를 한 번만 반영한다.
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
        event = row["event"]
        if event not in STAGES + ("INSPECT",):
            return "잘못된 event"
        if event == "INSPECT":
            if row["inspection"] not in INSPECTIONS:
                return "잘못된 inspection (LIGHT 또는 LEAK 필요)"
            if row["result"] not in ("PASS", "FAIL"):
                return "잘못된 result (PASS 또는 FAIL 필요)"
        elif row["inspection"] or row["result"]:
            return "INSPECT 이외의 inspection과 result는 빈칸이어야 함"
        return ""

    def _decision(
        self, row: Mapping[str, str], rule_id: str, accepted: bool, reason: str
    ) -> Decision:
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

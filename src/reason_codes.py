"""거절 사유의 고정 코드 표. 동적 ID는 명시된 템플릿만 허용한다."""


# (상세 코드, 규칙 ID, 판정기가 내는 정확한 문구 또는 ID 템플릿)
REASON_CODE_TABLE = (
    ("PRESERVE_COLUMNS", "RULE_PRESERVE", "CSV 열 수 또는 값 누락"),
    ("PRESERVE_BAD_SEQ", "RULE_PRESERVE", "seq는 양의 정수여야 함"),
    ("PRESERVE_EMPTY_PRODUCT", "RULE_PRESERVE", "product_id가 비어 있음"),
    ("PRESERVE_EMPTY_EVENT", "RULE_PRESERVE", "event가 비어 있음"),
    ("PRESERVE_MODEL_FIELD", "RULE_PRESERVE", "REGISTER 이외의 model은 빈칸이어야 함"),
    ("PRESERVE_EMPTY_INSPECTION", "RULE_PRESERVE", "inspection이 비어 있음"),
    ("PRESERVE_BAD_RESULT", "RULE_PRESERVE", "잘못된 result (PASS 또는 FAIL 필요)"),
    ("PRESERVE_RETEST_RESULT", "RULE_PRESERVE", "RETEST_REQUEST의 result는 빈칸이어야 함"),
    ("PRESERVE_INSPECTION_FIELDS", "RULE_PRESERVE", "INSPECT 이외의 inspection과 result는 빈칸이어야 함"),
    ("PRESERVE_EMPTY_EQUIPMENT", "RULE_PRESERVE", "equipment가 비어 있음"),
    ("PRESERVE_EQUIPMENT_FIELD", "RULE_PRESERVE", "INSPECT 이외의 equipment는 빈칸이어야 함"),
    ("PRESERVE_DUP_REGISTER", "RULE_PRESERVE", "이미 등록된 제품"),
    ("PRESERVE_UNREGISTERED", "RULE_PRESERVE", "미등록 제품"),
    ("PRESERVE_DUP_RESULT", "RULE_PRESERVE", "{inspection} 결과 이미 존재"),
    ("PRESERVE_PAST_STEP", "RULE_PRESERVE", "이미 지난 공정 재입력"),
    ("RECIPE_UNKNOWN_MODEL", "RULE_RECIPE", "model이 비어 있거나 레시피에 없는 모델"),
    ("RECIPE_RETEST_DISABLED", "RULE_RECIPE", "재검사 모드가 아닌 레시피"),
    ("RECIPE_UNKNOWN_INSPECTION", "RULE_RECIPE", "제품 레시피에 없는 검사 {inspection}"),
    ("RECIPE_UNKNOWN_STEP", "RULE_RECIPE", "제품 레시피에 없는 공정 {event}"),
    ("SEQ_SKIP", "RULE_SEQ", "{step} 미완료"),
    ("INSP_TOO_EARLY", "RULE_INSP_PRE", "{step} 미완료"),
    ("FAIL_HOLD", "RULE_FAIL_HOLD", "FAIL로 보류 중인 제품"),
    ("RETEST_DISCARDED", "RULE_RETEST", "폐기된 제품"),
    ("RETEST_ALREADY_OPEN", "RULE_RETEST", "이미 열린 재검사 요청"),
    ("RETEST_NO_FAIL", "RULE_RETEST", "미해결 FAIL 없음"),
    ("EQUIP_UNKNOWN", "RULE_EQUIP", "등록되지 않은 설비"),
    ("EQUIP_WRONG_INSPECTION", "RULE_EQUIP", "검사 종류가 다른 설비"),
    ("EQUIP_STOPPED", "RULE_EQUIP", "정지된 설비"),
    ("EQUIP_NOT_STOPPED", "RULE_EQUIP", "가동 중인 설비 재가동"),
    ("PRESERVE_BAD_LOT", "RULE_PRESERVE", "lot이 비어 있거나 형식이 잘못됨"),
    ("PRESERVE_LOT_FIELD", "RULE_PRESERVE", "REGISTER 이외의 lot은 빈칸이어야 함"),
    ("PRESERVE_RESTART_PRODUCT", "RULE_PRESERVE", "EQUIP_RESTART의 product_id는 빈칸이어야 함"),
    ("PRESERVE_RESTART_FIELDS", "RULE_PRESERVE", "EQUIP_RESTART의 inspection과 model은 빈칸이어야 함"),
    ("PRESERVE_BAD_RESTART_RESULT", "RULE_PRESERVE", "잘못된 재가동 결과 (FIXED 또는 NO_FAULT 필요)"),
)

REASON_CODES = {code: (rule, template) for code, rule, template in REASON_CODE_TABLE}
INJECTED_ERROR_CODES = (
    "SEQ_SKIP", "PRESERVE_BAD_RESULT", "PRESERVE_DUP_RESULT", "EQUIP_UNKNOWN", "RECIPE_UNKNOWN_STEP",
)


def rejection_code(decision, event, models):
    """알려진 문구와 규칙의 쌍만 변환한다. 새 문구는 조용히 묶지 않는다."""
    steps = {step for model in models.values() for step in model.steps}
    for code, rule, template in REASON_CODE_TABLE:
        if decision.rule_id != rule:
            continue
        if "{step}" in template:
            matches = any(decision.reason == template.format(step=step) for step in steps)
        elif "{inspection}" in template:
            inspection = event.get("inspection")
            matches = bool(inspection) and decision.reason == template.format(inspection=inspection)
        elif "{event}" in template:
            name = event.get("event")
            matches = bool(name) and decision.reason == template.format(event=name)
        else:
            matches = decision.reason == template
        if matches:
            return code
    raise ValueError("알 수 없는 거절 사유: " + decision.rule_id + " / " + decision.reason)

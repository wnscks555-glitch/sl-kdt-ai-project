"""v2 판정 결과를 결정적인 보고서 행으로 변환한다."""

from .recipe_rules import RULE_IDS, RecipeProcess


PRODUCT_COLUMNS = ("product_id", "model", "state", "incomplete_reason")


def build_recipe_reports(events, models):
    process = RecipeProcess(models)
    rows = []
    counts = dict.fromkeys(RULE_IDS, 0)
    for event in events:
        decision = process.apply(event)
        rows.append((
            decision.seq,
            decision.product_id,
            decision.input_text,
            decision.rule_id,
            "허용" if decision.accepted else "거절",
            decision.reason,
            decision.state,
        ))
        if not decision.accepted:
            counts[decision.rule_id] += 1
    products = [
        (product_id, product.model, product.status, product.incomplete_reason)
        for product_id, product in process.products.items()
    ]
    return rows, products, list(counts.items())

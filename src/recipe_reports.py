from .recipe_rules import RULE_IDS, RecipeProcess


PRODUCT_COLUMNS = ("product_id", "model", "state", "incomplete_reason")
RETEST_PRODUCT_COLUMNS = PRODUCT_COLUMNS + ("history",)
EQUIPMENT_COLUMNS = ("equipment", "inspection", "counted_results", "fail_count", "state", "stopped_at_seq")


def build_recipe_reports(events, models, equipment_book=None):
    process = RecipeProcess(models, equipment_book)
    rows = []
    rule_ids = RULE_IDS + ("RULE_RETEST",) if process.retest_enabled else RULE_IDS
    if equipment_book is not None:
        rule_ids += ("RULE_EQUIP",)
    counts = dict.fromkeys(rule_ids, 0)
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
        + ((product.history,) if process.retest_enabled else ())
        for product_id, product in process.products.items()
    ]
    reports = rows, products, list(counts.items())
    if equipment_book is not None:
        equipment = [
            (name, equipment_book.equipment[name], state.counted_results, state.fail_count,
             state.state, state.stopped_at_seq or "")
            for name, state in process.equipment.items()
        ]
        reports += (equipment,)
    return reports

"""시드·설정·버전으로 재현하는 교육용 생산 기록 생성기."""

import argparse
from collections import defaultdict
import csv
import hashlib
import json
from pathlib import Path
import random

from .equipment import EquipmentState, load_equipment
from .recipe import load_recipe
from .recipe_rules import EQUIPMENT_INPUT_COLUMNS, RecipeProcess
from .reason_codes import INJECTED_ERROR_CODES as ERROR_KINDS


GENERATOR_VERSION = "1.1.0"
DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "recipes/generator.json"


def event(product_id, name, inspection="", result="", model="", equipment=""):
    return dict(zip(EQUIPMENT_INPUT_COLUMNS,
                    ("", product_id, name, inspection, result, model, equipment)))


class Generator:
    def __init__(self, seed, config, models, equipment_book):
        self.rng = random.Random(seed)
        self.config = config
        self.models = models
        self.book = equipment_book
        self.equipment = {name: EquipmentState() for name in self.book.equipment}
        self.cursor = defaultdict(int)
        self.defective_products = []

    def choose_equipment(self, inspection, avoid=""):
        names = [name for name, kind in self.book.equipment.items() if kind == inspection]
        running = [name for name in names if self.equipment[name].stopped_at_seq is None]
        preferred = [name for name in running if name != avoid] or running
        for offset in range(len(names)):
            index = (self.cursor[inspection] + offset) % len(names)
            if names[index] in preferred:
                self.cursor[inspection] = (index + 1) % len(names)
                return names[index]
        return None

    def product(self, product_id, model):
        recipe = self.models[model]
        defective = self.rng.random() < self.config["defective_product_probability"]
        if defective:
            self.defective_products.append(product_id)
        yield event(product_id, "REGISTER", model=model), False
        for step in recipe.steps:
            yield event(product_id, step), False
            for item in recipe.inspections:
                if item.after != step:
                    continue
                first_equipment = ""
                for attempt in range(recipe.retest_limit + 1):
                    equipment = self.choose_equipment(item.id, first_equipment)
                    if equipment is None:
                        return
                    if defective:
                        probability = self.config["defective_fail_probability"]
                    else:
                        probability = self.config["faulty_equipment"].get(
                            equipment, self.config["normal_fail_probability"])
                    result = "FAIL" if self.rng.random() < probability else "PASS"
                    yield event(product_id, "INSPECT", item.id, result, equipment=equipment), attempt == 0
                    if result == "PASS":
                        break
                    if attempt == recipe.retest_limit or self.rng.random() >= self.config["retest_probability"]:
                        return
                    if attempt == 0:
                        first_equipment = equipment
                    yield event(product_id, "RETEST_REQUEST", item.id), False

    def normal_events(self, products):
        names = list(self.config["model_weights"])
        weights = list(self.config["model_weights"].values())
        active = [self.product("GEN_" + str(index + 1).zfill(4),
                               self.rng.choices(names, weights=weights)[0]) for index in range(products)]
        rows = []
        while active:
            following = []
            for flow in active:
                try:
                    row, initial = next(flow)
                except StopIteration:
                    continue
                row["seq"] = str(len(rows) + 1)
                rows.append(row)
                if initial:
                    name = row["equipment"]
                    self.equipment[name] = self.equipment[name].record(row["result"], row["seq"], self.book)
                following.append(flow)
            active = following
        return rows

    def inject_errors(self, normal):
        candidates = {kind: [] for kind in ERROR_KINDS}
        process = RecipeProcess(self.models, self.book)
        for position, row in enumerate(normal, 1):
            decision = process.apply(row)
            if not decision.accepted:
                raise ValueError("생성한 정상 행이 거절됨: " + decision.reason)
            product = process.products[row["product_id"]]
            if product.discarded_inspection is not None:
                continue
            pid = row["product_id"]
            if product.status != "보류" and product.completed_steps + 1 < len(product.recipe.steps):
                future = product.recipe.steps[product.completed_steps + 1]
                candidates["SEQ_SKIP"].append((position, event(pid, future)))
            if product.model == "B" and "P5" not in product.recipe.steps:
                candidates["RECIPE_UNKNOWN_STEP"].append((position, event(pid, "P5")))
            item = product.recipe.inspections[0]
            available = [name for name, kind in self.book.equipment.items()
                         if kind == item.id and process.equipment[name].stopped_at_seq is None]
            if available:
                candidates["PRESERVE_BAD_RESULT"].append(
                    (position, event(pid, "INSPECT", item.id, "OK", equipment=available[0])))
            candidates["EQUIP_UNKNOWN"].append(
                (position, event(pid, "INSPECT", item.id, "PASS", equipment="LEAK-9")))
            for inspection in product.inspections:
                if inspection in product.open_requests:
                    continue
                names = [name for name, kind in self.book.equipment.items()
                         if kind == inspection and process.equipment[name].stopped_at_seq is None]
                if names:
                    candidates["PRESERVE_DUP_RESULT"].append(
                        (position, event(pid, "INSPECT", inspection, "PASS", equipment=names[0])))
        count = int(len(normal) * self.config["error_rate"])
        kinds = list(ERROR_KINDS)
        self.rng.shuffle(kinds)
        counts = {kind: count // len(kinds) for kind in ERROR_KINDS}
        for kind in kinds[:count % len(kinds)]:
            counts[kind] += 1
        insertions = defaultdict(list)
        for kind in ERROR_KINDS:
            if counts[kind] and not candidates[kind]:
                reason = "현재 제품·공정·검사·설비 상태에 유효한 주입 위치가 없음"
                if kind == "RECIPE_UNKNOWN_STEP" and not any(
                        row["event"] == "REGISTER" and row["model"] == "B" for row in normal):
                    reason = "B 제품 없음: B 제품의 P5 행을 주입할 수 없음"
                raise ValueError(f"오류 주입 위치 없음: {kind} (배정 {counts[kind]}건, 후보 0개; {reason})")
            for _ in range(counts[kind]):
                position, row = self.rng.choice(candidates[kind])
                insertions[position].append(dict(row))
        rows = []
        for position, row in enumerate(normal, 1):
            rows.append(dict(row))
            rows.extend(insertions[position])
        for seq, row in enumerate(rows, 1):
            row["seq"] = str(seq)
        return rows, counts


def generate(seed=42, products=500, out=Path("data/generated/gen_seed42.csv"), config_path=DEFAULT_CONFIG):
    if products < 1:
        raise ValueError("products는 양의 정수여야 함")
    config_path, out = Path(config_path), Path(out)
    content = config_path.read_bytes()
    config = json.loads(content.decode("utf-8-sig"))
    recipe_path = config_path.parent / config["recipe"]
    equipment_path = config_path.parent / config["equipment"]
    recipe = load_recipe(recipe_path)
    equipment = load_equipment(equipment_path, recipe.models)
    generator = Generator(seed, config, recipe.models, equipment)
    normal = generator.normal_events(products)
    rows, counts = generator.inject_errors(normal)
    meta = {
        "seed": seed, "products": products, "generator_version": GENERATOR_VERSION,
        "sha256": {"config": hashlib.sha256(content).hexdigest(),
                   "recipe": recipe.sha256, "equipment": equipment.sha256},
        "normal_rows": len(normal), "rows": len(rows), "injected_errors": counts,
        "injection_rate": config["error_rate"],
        "defective_count": len(generator.defective_products),
        "defective_products": generator.defective_products,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=EQUIPMENT_INPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    Path(str(out) + ".meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return meta


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--products", type=int, default=500)
    parser.add_argument("--out", type=Path, default=Path("data/generated/gen_seed42.csv"))
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args(argv)
    try:
        meta = generate(args.seed, args.products, args.out, args.config)
    except (OSError, UnicodeError, ValueError, KeyError) as error:
        parser.exit(2, "오류: " + str(error) + "\n")
    print("생성: " + args.out.as_posix())
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

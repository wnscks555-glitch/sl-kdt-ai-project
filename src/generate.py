"""시드·설정·버전으로 재현하는 교육용 생산 기록 생성기."""

import argparse
from collections import defaultdict
import csv
from decimal import Decimal, ROUND_HALF_UP, localcontext
import hashlib
import json
import math
from pathlib import Path
import random

from .equipment import EquipmentState, load_equipment
from .recipe import is_decimal_text, is_measured, load_recipe
from .recipe_rules import (
    EQUIPMENT_INPUT_COLUMNS, MEASURE_COLUMN, RESTART_EVENT, RecipeProcess, input_columns, judge_value,
)
from .reason_codes import injected_error_codes


GENERATOR_VERSION = "1.1.0"
RESTART_GENERATOR_VERSION = "1.2.0"
LOT_GENERATOR_VERSION = "1.3.0"
MEASURED_GENERATOR_VERSION = "1.4.0"
MEASURED_CONFIG_KEYS = {
    "recipe", "equipment", "model_weights", "defective_product_probability", "retest_probability", "error_rate",
    "restart", "process_cpk", "fault_shift_sigma", "defect_shift_sigma",
}
DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "recipes/generator.json"


def event(product_id, name, inspection="", result="", model="", equipment=""):
    return dict(zip(EQUIPMENT_INPUT_COLUMNS,
                    ("", product_id, name, inspection, result, model, equipment)))


def confirm_value(number):
    """생성값을 CSV에 쓸 문자열로 확정한다. 이후 분기는 이 문자열만 쓴다."""
    if not math.isfinite(number):
        raise ValueError("측정값이 유한하지 않음")
    with localcontext() as context:
        context.prec = 100
        rounded = Decimal(repr(number)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        text = "0.000" if rounded == 0 else format(rounded, "f")
    if not is_decimal_text(text):
        raise ValueError("측정값이 value 자릿수 상한을 넘음: " + text)
    return text


class Generator:
    def __init__(self, seed, config, models, equipment_book):
        self.rng = random.Random(seed)
        self.config = config
        self.models = models
        self.book = equipment_book
        self.equipment = {name: EquipmentState() for name in self.book.equipment}
        self.measured = check_measured_config(config, models, equipment_book)
        self.faulty = config["fault_shift_sigma"] if self.measured else config["faulty_equipment"]
        self.cursor = defaultdict(int)
        self.defective_products = []
        self.restart_delay = restart_delay(config, equipment_book)
        self.pending_restarts = []
        self.repaired = set()
        check_lot_config(config, equipment_book)
        self.lot_size = config.get("lot_size")
        self.defective_lots = {}
        self.leaked_products = []

    def stamp(self, row):
        if self.lot_size is not None:
            row.setdefault("lot", "")
        if self.measured:
            row.setdefault(MEASURE_COLUMN, "")
        return row

    def spread(self, item):
        lsl, usl = float(item.lsl), float(item.usl)
        return (lsl + usl) / 2, (usl - lsl) / (6 * self.config["process_cpk"])

    def measure(self, item, equipment, defective):
        """수리 전 고장 설비와 결함품의 이동을 더한 분포에서 한 번 뽑아 확정한다."""
        center, sigma = self.spread(item)
        shift = self.config["defect_shift_sigma"] if defective else 0
        if equipment not in self.repaired:
            shift += self.faulty.get(equipment, 0)
        return confirm_value(self.rng.gauss(center + shift * sigma, sigma))

    def normal_value(self, item):
        return confirm_value(self.spread(item)[0])

    def inspect_event(self, product_id, item, equipment, value):
        row = event(product_id, "INSPECT", item.id, equipment=equipment)
        row[MEASURE_COLUMN] = value
        return row

    def draw_defective(self, number):
        if "defective_lot_probability" not in self.config:
            return self.rng.random() < self.config["defective_product_probability"]
        lot = (number - 1) // self.lot_size
        if lot not in self.defective_lots:
            self.defective_lots[lot] = self.rng.random() < self.config["defective_lot_probability"]
        return self.defective_lots[lot] and self.rng.random() < self.config["defective_in_lot_probability"]

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

    def product(self, product_id, model, number=0):
        recipe = self.models[model]
        defective = self.draw_defective(number)
        if defective:
            self.defective_products.append(product_id)
        register = event(product_id, "REGISTER", model=model)
        if self.lot_size is not None:
            register["lot"] = "LOT-" + str((number - 1) // self.lot_size + 1).zfill(4)
        yield register, False
        for step in recipe.steps:
            yield event(product_id, step), False
            for item in recipe.inspections:
                if item.after != step:
                    continue
                first_equipment = ""
                for attempt in range(recipe.retest_limit + 1):
                    equipment = self.choose_equipment(item.id, first_equipment)
                    if (equipment is None and self.restart_delay is not None
                            and item.id not in self.book.equipment.values()):
                        # 재가동으로도 생기지 않는 설비를 기다리면 생성이 끝나지 않는다.
                        raise ValueError("검사 " + item.id + "의 설비가 설비 파일에 없어 재가동 대기를 끝낼 수 없음")
                    while equipment is None and self.restart_delay is not None:
                        yield None
                        equipment = self.choose_equipment(item.id, first_equipment)
                    if equipment is None:
                        return
                    if self.measured:
                        value = self.measure(item, equipment, defective)
                        result = judge_value(value, item)
                        yield self.inspect_event(product_id, item, equipment, value), result if attempt == 0 else ""
                        if result == "PASS":
                            break
                        if attempt == recipe.retest_limit or self.rng.random() >= self.config["retest_probability"]:
                            return
                        if attempt == 0:
                            first_equipment = equipment
                        yield event(product_id, "RETEST_REQUEST", item.id), ""
                        continue
                    if defective:
                        probability = self.config["defective_fail_probability"]
                        if equipment not in self.repaired:
                            probability *= 1 - self.config.get("faulty_detection_loss", {}).get(equipment, 0)
                    elif equipment in self.repaired:
                        probability = self.config["normal_fail_probability"]
                    else:
                        probability = self.config["faulty_equipment"].get(
                            equipment, self.config["normal_fail_probability"])
                    result = "FAIL" if self.rng.random() < probability else "PASS"
                    if (defective and attempt == 0 and result == "PASS" and self.lot_size is not None
                            and equipment in self.config["faulty_equipment"] and equipment not in self.repaired):
                        self.leaked_products.append(product_id)
                    yield event(product_id, "INSPECT", item.id, result, equipment=equipment), result if attempt == 0 else ""
                    if result == "PASS":
                        break
                    if attempt == recipe.retest_limit or self.rng.random() >= self.config["retest_probability"]:
                        return
                    if attempt == 0:
                        first_equipment = equipment
                    yield event(product_id, "RETEST_REQUEST", item.id), False

    def add_restart(self, rows):
        """수리되지 않은 고장 설비만 FIXED다. 점검이 항상 맞다는 가정이며 난수를 쓰지 않는다."""
        _, name = self.pending_restarts.pop(0)
        result = "FIXED" if name in self.faulty and name not in self.repaired else "NO_FAULT"
        if result == "FIXED":
            self.repaired.add(name)
        row = self.stamp(event("", RESTART_EVENT, result=result, equipment=name))
        row["seq"] = str(len(rows) + 1)
        rows.append(row)
        self.equipment[name] = self.equipment[name].restart(result)

    def normal_events(self, products):
        names = list(self.config["model_weights"])
        weights = list(self.config["model_weights"].values())
        active = [self.product("GEN_" + str(index + 1).zfill(4),
                               self.rng.choices(names, weights=weights)[0], index + 1) for index in range(products)]
        rows = []
        while active:
            following = []
            progressed = False
            for flow in active:
                while self.pending_restarts and self.pending_restarts[0][0] <= len(rows):
                    self.add_restart(rows)
                try:
                    step = next(flow)
                except StopIteration:
                    continue
                if step is None:
                    following.append(flow)
                    continue
                row, recorded = step
                self.stamp(row)
                progressed = True
                row["seq"] = str(len(rows) + 1)
                rows.append(row)
                if recorded:
                    name = row["equipment"]
                    self.equipment[name] = self.equipment[name].record(recorded, row["seq"], self.book)
                    if self.restart_delay is not None and self.equipment[name].stopped_at_seq is not None:
                        self.pending_restarts.append((len(rows) + self.restart_delay, name))
                        self.pending_restarts.sort()
                following.append(flow)
            # 대기만 남은 라운드는 행이 늘지 않으므로 가장 이른 재가동을 앞당겨 교착을 막는다.
            if following and not progressed and self.pending_restarts:
                self.add_restart(rows)
            active = following
        return rows

    def inject_errors(self, normal):
        error_kinds = injected_error_codes(self.measured)
        candidates = {kind: [] for kind in error_kinds}
        process = RecipeProcess(self.models, self.book)
        for position, row in enumerate(normal, 1):
            decision = process.apply(row)
            if not decision.accepted:
                raise ValueError("생성한 정상 행이 거절됨: " + decision.reason)
            # 이전 모드에서는 EQUIP_RESTART가 합법적인 공정명이므로 재가동 모드에서만 건너뛴다.
            if self.book.restart_enabled and row["event"] == RESTART_EVENT:
                continue
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
            if available and self.measured:
                candidates["PRESERVE_BAD_VALUE"].append(
                    (position, self.inspect_event(pid, item, available[0], "abc")))
            elif available:
                candidates["PRESERVE_BAD_RESULT"].append(
                    (position, event(pid, "INSPECT", item.id, "OK", equipment=available[0])))
            candidates["EQUIP_UNKNOWN"].append((position, (
                self.inspect_event(pid, item, "LEAK-9", self.normal_value(item)) if self.measured
                else event(pid, "INSPECT", item.id, "PASS", equipment="LEAK-9"))))
            for inspection in product.inspections:
                if inspection in product.open_requests:
                    continue
                names = [name for name, kind in self.book.equipment.items()
                         if kind == inspection and process.equipment[name].stopped_at_seq is None]
                if names and self.measured:
                    done = next(entry for entry in product.recipe.inspections if entry.id == inspection)
                    candidates["PRESERVE_DUP_RESULT"].append(
                        (position, self.inspect_event(pid, done, names[0], self.normal_value(done))))
                elif names:
                    candidates["PRESERVE_DUP_RESULT"].append(
                        (position, event(pid, "INSPECT", inspection, "PASS", equipment=names[0])))
        count = int(len(normal) * self.config["error_rate"])
        kinds = list(error_kinds)
        self.rng.shuffle(kinds)
        counts = {kind: count // len(kinds) for kind in error_kinds}
        for kind in kinds[:count % len(kinds)]:
            counts[kind] += 1
        insertions = defaultdict(list)
        for kind in error_kinds:
            if counts[kind] and not candidates[kind]:
                reason = "현재 제품·공정·검사·설비 상태에 유효한 주입 위치가 없음"
                if kind == "RECIPE_UNKNOWN_STEP" and not any(
                        row["event"] == "REGISTER" and row["model"] == "B" for row in normal):
                    reason = "B 제품 없음: B 제품의 P5 행을 주입할 수 없음"
                raise ValueError(f"오류 주입 위치 없음: {kind} (배정 {counts[kind]}건, 후보 0개; {reason})")
            for _ in range(counts[kind]):
                position, row = self.rng.choice(candidates[kind])
                insertions[position].append(self.stamp(dict(row)))
        rows = []
        for position, row in enumerate(normal, 1):
            rows.append(dict(row))
            rows.extend(insertions[position])
        for seq, row in enumerate(rows, 1):
            row["seq"] = str(seq)
        return rows, counts


def restart_delay(config, book):
    if "restart" not in config:
        return None
    restart = config["restart"]
    if not book.restart_enabled:
        raise ValueError("restart 설정에는 restart_enabled 설비 파일이 필요함")
    if (not isinstance(restart, dict) or set(restart) != {"delay_rows"}
            or type(restart["delay_rows"]) is not int or restart["delay_rows"] < 0):
        raise ValueError("restart는 0 이상의 정수 delay_rows만 가져야 함")
    return restart["delay_rows"]


def unit(value):
    # 범위를 먼저 비교해야 큰 정수가 float 변환에서 OverflowError를 내지 않는다.
    return type(value) in (int, float) and 0 <= value <= 1 and math.isfinite(value)


def positive(value):
    if type(value) not in (int, float) or not value > 0:
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def check_measured_config(config, models, book):
    """측정 생성 설정을 파일을 만들기 전에 거른다. 측정 설정이면 True다."""
    measured = is_measured(models)
    shift_keys = {"fault_shift_sigma", "defect_shift_sigma"} & config.keys()
    if "process_cpk" not in config:
        if measured:
            raise ValueError("측정 레시피에는 process_cpk 설정이 필요함")
        if shift_keys:
            raise ValueError("fault_shift_sigma와 defect_shift_sigma에는 process_cpk가 필요함")
        return False
    if not measured:
        raise ValueError("process_cpk 설정에는 측정 레시피가 필요함")
    extra = sorted(config.keys() - MEASURED_CONFIG_KEYS)
    if extra:
        raise ValueError("측정 설정에서 허용하지 않은 키: " + ", ".join(extra))
    if len(shift_keys) != 2:
        raise ValueError("측정 설정에는 fault_shift_sigma와 defect_shift_sigma가 필요함")
    if book.lot_tracking:
        raise ValueError("측정 생성기는 lot_tracking 설비 파일을 지원하지 않음")
    if "restart" not in config:
        raise ValueError("측정 설정에는 restart가 필요함")
    if any(model.retest_limit is None for model in models.values()):
        raise ValueError("측정 생성 레시피에는 retest_limit이 필요함")
    faults = config["fault_shift_sigma"]
    if not isinstance(faults, dict) or not all(positive(value) for value in faults.values()):
        raise ValueError("fault_shift_sigma는 설비별 유한한 양수여야 함")
    if not set(faults) <= set(book.equipment):
        raise ValueError("fault_shift_sigma의 설비가 설비 파일에 없음")
    if not positive(config["process_cpk"]) or not positive(config["defect_shift_sigma"]):
        raise ValueError("process_cpk와 defect_shift_sigma는 유한한 양수여야 함")
    for key in ("defective_product_probability", "retest_probability", "error_rate"):
        if key not in config or not unit(config[key]):
            raise ValueError(key + "는 0–1 값이어야 함")
    shift = config["defect_shift_sigma"] + max(faults.values(), default=0)
    for model in models.values():
        for item in model.inspections:
            if item.lsl is None or item.usl is None:
                raise ValueError("측정 생성은 양측 규격만 지원함: " + item.id)
            lsl, usl = float(item.lsl), float(item.usl)
            divisor = 6 * config["process_cpk"]
            sigma = (usl - lsl) / divisor if divisor else math.inf
            if not math.isfinite(sigma) or not math.isfinite((lsl + usl) / 2 + shift * sigma):
                raise ValueError("규격과 process_cpk로 계산한 분포가 유한하지 않음: " + item.id)
    return True


def check_lot_config(config, book):
    lot_keys = {"defective_lot_probability", "defective_in_lot_probability"} & config.keys()
    if "lot_size" not in config:
        if book.lot_tracking:
            raise ValueError("lot_tracking 설비 파일에는 lot_size 설정이 필요함")
        if lot_keys or "faulty_detection_loss" in config:
            raise ValueError("faulty_detection_loss와 결함 로트 설정에는 lot_size가 필요함")
        return
    if type(config["lot_size"]) is not int or config["lot_size"] < 1:
        raise ValueError("lot_size는 양의 정수여야 함 (bool 불가)")
    if not book.lot_tracking:
        raise ValueError("lot_size 설정에는 lot_tracking 설비 파일이 필요함")
    if lot_keys and len(lot_keys) != 2:
        raise ValueError("defective_lot_probability와 defective_in_lot_probability는 함께 있어야 함")
    if not all(unit(config[key]) for key in lot_keys):
        raise ValueError("결함 로트 확률은 0–1 값이어야 함")
    loss = config.get("faulty_detection_loss", {})
    if not isinstance(loss, dict) or not all(unit(value) for value in loss.values()):
        raise ValueError("faulty_detection_loss는 설비별 0–1 값이어야 함")
    if not set(loss) <= set(config["faulty_equipment"]):
        raise ValueError("faulty_detection_loss의 설비는 faulty_equipment에 있어야 함")


def generator_version(config):
    if "process_cpk" in config:
        return MEASURED_GENERATOR_VERSION
    if "lot_size" in config:
        return LOT_GENERATOR_VERSION
    return RESTART_GENERATOR_VERSION if "restart" in config else GENERATOR_VERSION


def load_setup(config_path):
    """설정, 원문 SHA 계산용 바이트, 레시피, 설비를 함께 읽는다."""
    config_path = Path(config_path)
    content = config_path.read_bytes()
    config = json.loads(content.decode("utf-8-sig"))
    recipe = load_recipe(config_path.parent / config["recipe"])
    equipment = load_equipment(config_path.parent / config["equipment"], recipe.models)
    return config, content, recipe, equipment


def build_rows(seed, products, config, models, equipment):
    generator = Generator(seed, config, models, equipment)
    normal = generator.normal_events(products)
    rows, counts = generator.inject_errors(normal)
    return generator, normal, rows, counts


def generate(seed=42, products=500, out=Path("data/generated/gen_seed42.csv"), config_path=DEFAULT_CONFIG):
    if products < 1:
        raise ValueError("products는 양의 정수여야 함")
    out = Path(out)
    config, content, recipe, equipment = load_setup(config_path)
    generator, normal, rows, counts = build_rows(seed, products, config, recipe.models, equipment)
    meta = {
        "seed": seed, "products": products,
        "generator_version": generator_version(config),
        "sha256": {"config": hashlib.sha256(content).hexdigest(),
                   "recipe": recipe.sha256, "equipment": equipment.sha256},
        "normal_rows": len(normal), "rows": len(rows), "injected_errors": counts,
        "injection_rate": config["error_rate"],
        "defective_count": len(generator.defective_products),
        "defective_products": generator.defective_products,
    }
    if "lot_size" in config:
        meta.update(lot_size=config["lot_size"], leaked_products=sorted(generator.leaked_products))
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=input_columns(equipment, generator.measured))
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

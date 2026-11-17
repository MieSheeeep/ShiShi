"""每周饮食计划：与存储无关的周次计算、计划生成和采购清单聚合。

``generate_plan`` 目前是确定性的本地模拟实现，优先使用冰箱已有食材、
尽量错开重复菜品并兼顾三餐多样性。未来接入真实模型时，只需替换该函数
内部逻辑，保持入参（周次、食谱、冰箱食材）与返回值（七天三餐结构）不变。

``build_shopping_items`` 复用采购清单的合并与库存抵扣逻辑，保证与手动
勾选食谱生成的清单一致。
"""
from datetime import date, timedelta

from backend.core import merge_ingredients, normalize, pantry_shortfall, quantity

# 三餐固定顺序：键名用于存储，中文名用于界面展示。
MEALS = (('breakfast', '早餐'), ('lunch', '午餐'), ('dinner', '晚餐'))


def monday_of(day: date) -> date:
    """返回某天所在周的周一。"""
    return day - timedelta(days=day.weekday())


def week_key_for(day: date) -> str:
    """以周一日期（YYYY-MM-DD）作为一周的唯一键。"""
    return monday_of(day).isoformat()


def week_dates(week_key: str) -> list[date]:
    """由周键还原该周七天。"""
    monday = date.fromisoformat(week_key)
    return [monday + timedelta(days=index) for index in range(7)]


def empty_plan(week_key: str) -> dict:
    """返回一份尚未安排菜品的空计划。"""
    return {
        'week': week_key,
        'days': [
            {'date': day.isoformat(), 'meals': {key: None for key, _ in MEALS}}
            for day in week_dates(week_key)
        ],
    }


def generate_plan(week_key: str, recipes: list[dict], settings: dict) -> dict:
    """模拟生成一周饮食安排。

    策略：先按「冰箱食材命中率」给食谱排序（命中越高越优先），再沿一周的
    三餐槽位循环取用，从而让优先级高的食谱分散到不同天，且相邻槽位不重复。
    若食谱少于槽位（21 个），会按顺序重复使用；食谱为空则返回空计划。
    """
    staples = {normalize(item['name']) for item in settings.get('staples', [])}
    have = {normalize(item['name']) for item in settings.get('ingredients', [])}
    pantry_all = have | staples

    def pantry_match(recipe: dict) -> float:
        # 排除调料后，命中冰箱的食材占比越高越优先。
        names = [normalize(item['name']) for item in recipe.get('ingredients', []) if normalize(item['name']) not in staples]
        if not names:
            return 0.0
        return sum(1 for name in names if name in pantry_all) / len(names)

    ranked = sorted(recipes, key=lambda recipe: (-pantry_match(recipe), recipe.get('minutes') or 0, recipe.get('id', 0)))
    if not ranked:
        return empty_plan(week_key)

    total = len(ranked)
    days = []
    slot_index = 0
    for day in week_dates(week_key):
        meals = {}
        for key, _ in MEALS:
            meals[key] = ranked[slot_index % total]['id']
            slot_index += 1
        days.append({'date': day.isoformat(), 'meals': meals})
    return {'week': week_key, 'days': days}


def build_shopping_items(recipes: list[dict], settings: dict) -> list[dict]:
    """汇总食谱食材并扣除冰箱库存，返回待采购清单。"""
    pantry = {}
    for key in ('ingredients', 'staples'):
        for item in settings.get(key, []):
            raw = f"{item.get('amount', '')}{item.get('unit', '')}".strip()
            pantry.setdefault(normalize(item['name']), []).append(quantity(raw) if raw else None)
    items = merge_ingredients(recipes)
    for item in items:
        entries = pantry.get(item['name'])
        if not entries:
            continue
        short = pantry_shortfall(item['amount'], entries)
        if short is None:
            item['pantry'] = True
        else:
            item['amount'] = short
            item['pantryNote'] = f'冰箱里的用量已扣除，这里只买差额（还差 {short}）'
    return items

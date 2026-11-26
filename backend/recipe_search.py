"""按食材搜菜：确定性模糊匹配（免费）+ AI 推荐（按需、可缓存）。

复用 ``core.normalize``（食材归一，西红柿→番茄等）。模糊匹配不调用模型，
零模型成本；AI 推荐按「食材组合 + 已有食谱」缓存，命中缓存不再计费，并感知
用户已有食谱，优先推荐还没收藏的菜，避免重复推荐与重复计费。
"""
import json
import re

from backend import ai_recipe
from backend.core import normalize

# 自由文本里的数量词与连接词，解析食材时去掉，只留下食材名。
_QUANTIFIER = re.compile(
    r'(?:还有|家里有|手边有|冰箱有|一点|一些|适量|少许|几|半|[一二两三四五六七八九十]|\d+)'
    r'\s*(?:个|颗|根|把|块|片|斤|两|克|g|kg|袋|盒|瓶|勺|碗|份|只|条)?',
    re.IGNORECASE,
)
_SEPARATORS = re.compile(r'[，,、；;。！？!?\n+/|]+')


def parse_tokens(text):
    """把「鸡蛋 半颗白菜 挂面」解析成去重后的食材名列表，去掉数量词。"""
    cleaned = (text or '').replace('\u3000', ' ')
    cleaned = _QUANTIFIER.sub(' ', cleaned)
    cleaned = _SEPARATORS.sub(' ', cleaned)
    seen, tokens = set(), []
    for token in cleaned.split():
        token = token.strip()
        if token and token not in seen:
            seen.add(token)
            tokens.append(token)
    return tokens


def _hit(query, target):
    """归一后双向子串匹配，覆盖别名（西红柿/番茄）与部分名（鸡胸/鸡胸肉）。"""
    q, t = normalize(query), normalize(target)
    if not q or not t:
        return False
    return q == t or q in t or t in q


def fuzzy_rank(recipes, have, staples=()):
    """按食材命中给食谱排序，返回 ``[{recipe..., matched, missing, ratio}]``。

    ``matched`` 是命中的现有食材，``missing`` 是还没凑齐的食谱食材，``ratio``
    是主料（非调料）命中占比，用于排序：缺得越少、主料越齐越靠前。
    """
    have_norm = [normalize(h) for h in have]
    staples_norm = {normalize(s) for s in staples}
    ranked = []
    for recipe in recipes:
        ingredients = recipe.get('ingredients', [])
        names = [normalize(i.get('name', '')) for i in ingredients]
        matched = [h for h in have_norm if any(_hit(h, n) for n in names) or _hit(h, recipe.get('name', ''))]
        if not matched:
            continue
        missing = list(dict.fromkeys(n for n in names if n and not any(_hit(h, n) for h in have_norm)))
        mains = [normalize(i.get('name', '')) for i in ingredients if i.get('kind') != '调料' and normalize(i.get('name', '')) not in staples_norm]
        ratio = len([h for h in have_norm if any(_hit(h, m) for m in mains)]) / max(1, len(mains))
        ranked.append(dict(recipe, matched=matched, missing=missing, ratio=ratio))
    ranked.sort(key=lambda row: (len(row['missing']), -row['ratio']))
    return ranked


SUGGEST = """你是家常菜顾问。根据用户现有食材和调料，推荐 4 道现在就能做的菜。
只输出一个 JSON 对象，不要代码块、不要解释：
{"dishes":[{"name":"菜名","reason":"一句话说明为什么合适，点出用到的现有食材"}]}
要求：优先推荐用户还没有的菜，不要重复推荐用户已有的菜；菜名具体、可操作；
理由不超过 40 字；优先用现有食材就能做的菜，缺一两样常备调料也可以。"""


def _cache_key(recipes, ingredients, staples):
    names = sorted(dict.fromkeys(normalize(r.get('name', '')) for r in recipes if r.get('name')))
    ings = sorted(dict.fromkeys(normalize(i) for i in ingredients))
    stas = sorted(dict.fromkeys(normalize(s) for s in staples))
    return json.dumps({'recipes': names, 'ingredients': ings, 'staples': stas}, ensure_ascii=False)


_suggest_cache = {}
_suggest_order = []
_CACHE_MAX = 256


def _cache_store(cache, key, dishes):
    """写入缓存；模块级缓存做 LRU 上限，调用方传入的 dict 直接写。"""
    cache[key] = dishes
    if cache is _suggest_cache:
        if key in _suggest_order:
            _suggest_order.remove(key)
        _suggest_order.append(key)
        while len(_suggest_order) > _CACHE_MAX:
            _suggest_cache.pop(_suggest_order.pop(0), None)


def suggest_with_ai(settings, recipes, ingredients, staples, cache=None):
    """按食材推荐菜，返回 ``(dishes, from_cache)``。

    ``recipes`` 是用户已有食谱，用于避免重复推荐；``cache`` 默认用模块级缓存，
    命中时不再调用模型（成本与延迟都归零）。复用 ``ai_recipe`` 的调用与解析。
    """
    cache = cache if cache is not None else _suggest_cache
    key = _cache_key(recipes, ingredients, staples)
    if key in cache:
        return cache[key], True

    have = '、'.join(ingredients) or '（未记录）'
    condiments = '、'.join(staples) or '（未记录）'
    existing = '、'.join(dict.fromkeys(normalize(r.get('name', '')) for r in recipes if r.get('name'))) or '（还没有）'
    content = ai_recipe._chat(settings, [
        {'role': 'system', 'content': SUGGEST},
        {'role': 'user', 'content': '现有食材：%s\n常备调料：%s\n用户已有菜（不要重复推荐）：%s' % (have, condiments, existing)},
    ])
    dishes = ai_recipe._extract(content).get('dishes')
    if not isinstance(dishes, list) or not dishes:
        raise ValueError('AI 没有给出可用的菜名，请再试一次')
    picked = []
    for dish in dishes[:4]:
        if isinstance(dish, dict) and str(dish.get('name', '')).strip():
            picked.append({'name': str(dish['name']).strip()[:40], 'reason': str(dish.get('reason', '')).strip()[:160]})
    if not picked:
        raise ValueError('AI 没有给出可用的菜名，请再试一次')
    _cache_store(cache, key, picked)
    return picked, False

"""把采集正文（小红书笔记、豆果原文等）用 AI 整理成统一的 V2 食谱草稿。

复用 ``ai_recipe`` 的模型配置与 OpenAI 兼容调用，复用 ``core.normalize``（食材归一）、
``core.quantity``（用量解析）与 ``condiments.is_condiment``（调料分类）。

本模块只负责「提取与清洗」，不负责入库、下载图片等。核心约束：

- 只提取正文里明确出现的内容；缺失的字段保留为空字符串 / 空数组，并给出核对提示；
- 不补造、不推测正文没有的菜名、食材、用量或步骤；
- 一篇多道菜先拆分，再逐篇提取。
"""

from backend import ai_recipe
from backend.condiments import is_condiment
from backend.core import ALIASES, normalize, quantity

# 单篇提取：严格约束只提取正文已有内容。
EXTRACT_PROMPT = """你是食谱结构化提取助手。把用户给出的「采集正文」整理成规范食谱 JSON。

铁律：只提取正文里明确写出来的内容，绝不补造、推测或脑补正文没有的信息。
- name：正文明确的菜名（含"这道XX""XX的做法/配方"这类表述里的 XX）；正文确实没写菜名才留空字符串 ""，不得根据食材或做法推断菜名（例如正文只有"鸡翅""可乐"而没有标题时，不要写"可乐鸡翅"）。
- minutes：正文写了的耗时（如"20 分钟"）；没写就留空字符串 ""。
- servings：正文写了的份量（如"2 人份"）；没写就留空字符串 ""。
- ingredients：正文明确列出的食材和调料；每项 name 是食材名，amount 是正文里的用量原文（如"2 个""适量""500 克"）；正文没写用量就 amount 留空字符串 ""。
- steps：正文里明确的制作步骤，按原文顺序；正文没有步骤就返回空数组 []。
- notes：正文里的一条实用提醒或备注；没有就留空字符串 ""。

只输出一个 JSON 对象，不要代码块、不要解释：
{"name":"","minutes":"","servings":"","ingredients":[{"name":"","amount":""}],"steps":[""],"notes":""}"""

# 多道菜拆分：判断正文是否含多道独立的菜，按菜拆分。
SPLIT_PROMPT = """判断下面这段「采集正文」是否包含多道独立的菜（多道不同的菜）。
如果只有一道菜，把整段正文作为唯一片段返回：{"dishes":["整段正文"]}。
如果有多道菜，按菜拆成多个片段，每段是该道菜相关的完整正文（含菜名、材料、做法），
片段之间不重复也不遗漏，顺序按原文：{"dishes":["片段一","片段二",...]}。

拆分要点：
- 用「第一道/第二道」「1./2.」「【菜名】」「主菜/配菜/蘸料/主食/汤」等小标题分隔的，各算一道；
- 蘸料、配菜、主食、汤都各自算一道独立的菜，不要并进主菜；
- 只有一道完整菜谱（材料+做法）时才返回一个片段。

只输出一个 JSON 对象，不要代码块、不要解释。"""


def _chat(settings, messages, *, effort='low', max_tokens=4000):
    """复用 ai_recipe._chat，补上提取所需的 effort 与输出上限。"""
    return ai_recipe._chat(settings, messages, extra={'effort': effort, 'max_tokens': max_tokens})


def split_article(text, settings=None):
    """把正文按菜拆分，返回每道菜的正文片段列表；单道菜返回 [text]。

    拆分会调用一次模型。模型返回异常或无法解析时回退为整段单道菜，不阻断提取。
    """
    content = _chat(settings or ai_recipe.config(), [
        {'role': 'system', 'content': SPLIT_PROMPT},
        {'role': 'user', 'content': text},
    ])
    try:
        dishes = ai_recipe._extract(content).get('dishes')
    except ValueError:
        return [text]
    segments = []
    for dish in dishes or []:
        if isinstance(dish, str) and dish.strip():
            segments.append(dish.strip())
    return segments or [text]


def extract_one(text, settings=None):
    """把单道菜正文提取为结构化 dict（模型原始输出，仅做 JSON 解析与字段兜底）。"""
    content = _chat(settings or ai_recipe.config(), [
        {'role': 'system', 'content': EXTRACT_PROMPT},
        {'role': 'user', 'content': text},
    ])
    data = ai_recipe._extract(content)
    return {
        'name': str(data.get('name') or '').strip(),
        'minutes': str(data.get('minutes') or '').strip(),
        'servings': str(data.get('servings') or '').strip(),
        'ingredients': data.get('ingredients') or [],
        'steps': data.get('steps') or [],
        'notes': str(data.get('notes') or '').strip(),
    }


def _mentioned(text, name):
    """判断食材名是否在正文里出现（含别名反向匹配）。"""
    flat = ''.join(text.split())
    key = ''.join(name.split())
    if not key:
        return False
    if key in flat:
        return True
    for alias, target in ALIASES.items():
        if key == target and alias in flat:
            return True
    return False


def _clean_ingredients(raw_ingredients, text):
    """归一食材名、分类调料、校验用量，返回 (ingredients, warnings)。"""
    ingredients, warnings = [], []
    for item in raw_ingredients or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get('name') or '').strip()
        amount = str(item.get('amount') or '').strip()
        if not name:
            warnings.append('正文存在一项没有名称的食材，已跳过，请核对原文。')
            continue
        name = normalize(name)
        ingredients.append({
            'name': name,
            'amount': amount,
            'kind': '调料' if is_condiment(name) else '食材',
        })
        if not amount:
            warnings.append('食材「%s」正文未写用量，请核对补充。' % name)
        if not _mentioned(text, name):
            warnings.append('食材「%s」在正文里未找到，可能为补造，请核对。' % name)
    return ingredients, warnings


def _clean_steps(raw_steps):
    """清理步骤：去掉行首编号/符号，过滤空步骤。"""
    steps = []
    for step in raw_steps or []:
        if isinstance(step, dict):
            step = step.get('text') or ''
        step = str(step).strip()
        if step:
            steps.append(step)
    return steps


def _postprocess(data, text):
    """确定性后处理：归一、分类、校验，并产出核对提示。"""
    ingredients, warnings = _clean_ingredients(data.get('ingredients'), text)
    steps = _clean_steps(data.get('steps'))
    draft = {
        'name': data.get('name', ''),
        'minutes': data.get('minutes', ''),
        'servings': data.get('servings', ''),
        'ingredients': ingredients,
        'steps': steps,
        'notes': data.get('notes', ''),
    }
    if not draft['name']:
        warnings.append('正文未写菜名，请核对补充。')
    elif not _mentioned(text, draft['name']):
        warnings.append('菜名「%s」在正文里未直接出现，可能为推断，请核对。' % draft['name'])
    if not ingredients:
        warnings.append('正文未找到明确的食材，请对照原文补充。')
    if not steps:
        warnings.append('正文未找到明确的步骤，请对照原文补充做法。')
    draft['warnings'] = warnings
    return draft


def extract(text, settings=None):
    """把采集正文整理成统一食谱草稿：先拆分（多道菜）再逐篇提取。

    返回 ``{'recipes': [...], 'multi': bool}``；每篇草稿含 ``warnings`` 核对提示，
    缺失字段保留为空，不补造。
    """
    segments = split_article(text, settings)
    recipes = [_postprocess(extract_one(segment, settings), segment) for segment in segments]
    return {'recipes': recipes, 'multi': len(segments) > 1}

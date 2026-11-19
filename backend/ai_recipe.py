"""调用 OpenAI 兼容接口，把一句话要求写成可核对的食谱草稿。

配置来自环境变量，也兼容仓库根的 ``.env``：
``SHISHI_AI_BASE_URL``、``SHISHI_AI_API_KEY``、``SHISHI_AI_MODEL``。
"""
import json
import os

import httpx

from backend.deploy_guard import validate_ai_base_url

DEFAULT_BASE = 'https://api.deepseek.com/v1'
DEFAULT_MODEL = 'deepseek-chat'
TIMEOUT = 60
PROMPT = """你是中式家常菜谱作者。根据用户的要求写一道能照着做的食谱。
只输出一个 JSON 对象，不要代码块、不要解释：
{"name":"菜名","minutes":"30 分钟","servings":"2 人份",
 "ingredients":[{"name":"番茄","amount":"2 个"}],
 "steps":["先热锅倒油，中火炒散鸡蛋盛出。","..."],
 "notes":"一条实用提醒"}
要求：食材 4 到 15 种，包含调料；amount 必须带数量与单位，确实无法称量时写「适量」；
步骤 4 到 10 步，每步写清火候与时间；全部使用简体中文。"""


def _dotenv():
    """读取仓库根 .env 里的 SHISHI_AI_* 配置，环境变量优先。"""
    values = {}
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    try:
        with open(path, encoding='utf-8') as file:
            for line in file:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, value = line.split('=', 1)
                values[key.strip()] = value.strip().strip('"').strip("'")
    except OSError:
        pass
    return values


def config():
    file = _dotenv()
    pick = lambda key, default='': os.environ.get(key) or file.get(key) or default
    return {
        'base': pick('SHISHI_AI_BASE_URL', DEFAULT_BASE).rstrip('/'),
        'key': pick('SHISHI_AI_API_KEY'),
        'model': pick('SHISHI_AI_MODEL', DEFAULT_MODEL),
    }


def _extract(text):
    """模型偶尔会包一层 ```json，取第一个完整的 JSON 对象。"""
    body = text.strip()
    if body.startswith('```'):
        body = body.split('\n', 1)[-1]
        body = body.rsplit('```', 1)[0]
    start, end = body.find('{'), body.rfind('}')
    if start < 0 or end <= start:
        raise ValueError('AI 没有返回可解析的内容，请换个说法再试一次')
    try:
        data = json.loads(body[start:end + 1])
    except json.JSONDecodeError:
        raise ValueError('AI 返回的内容不是合法 JSON，请再试一次')
    if not isinstance(data, dict):
        raise ValueError('AI 返回的内容格式不对，请再试一次')
    return data


def read_json(text):
    data = _extract(text)
    for key in ('name', 'ingredients', 'steps'):
        if not data.get(key):
            raise ValueError('AI 返回的食谱缺少菜名、食材或步骤，请再试一次')
    return data


def _chat(settings, messages, extra=None):
    """调用 ``/chat/completions``，返回模型输出的文本。"""
    return _chat_usage(settings, messages, extra)[0]


def _chat_usage(settings, messages, extra=None):
    """调用 ``/chat/completions``，返回 ``(文本, usage 字典)``，供耗时与成本统计。"""
    if not settings.get('key'):
        raise ValueError('还没有配置 AI 接口，请填写 API Key 后再试')
    base = validate_ai_base_url(settings.get('base') or DEFAULT_BASE) or DEFAULT_BASE
    payload = {'model': settings.get('model') or DEFAULT_MODEL, 'messages': messages, 'temperature': 0.4}
    payload.update(extra or {})
    try:
        response = httpx.post(
            base + '/chat/completions',
            headers={'Authorization': 'Bearer ' + settings['key']},
            json=payload,
            timeout=TIMEOUT,
            follow_redirects=False,
        )
    except httpx.HTTPError as error:
        raise ValueError('连接 AI 接口失败：%s' % error)
    if response.status_code in (401, 403):
        raise ValueError('API Key 无效或没有权限，请检查后重新填写')
    if response.status_code >= 400:
        raise ValueError('AI 接口返回 %s：%s' % (response.status_code, response.text[:200]))
    try:
        body = response.json()
        return body['choices'][0]['message']['content'], body.get('usage') or {}
    except (KeyError, IndexError, TypeError, ValueError):
        raise ValueError('AI 接口返回的结构无法识别，请检查模型名与接口地址')


def verify(settings):
    """用一次极短的请求确认地址与 Key 是否可用。"""
    _chat(settings, [{'role': 'user', 'content': '回复 ok'}], {'max_tokens': 1})
    return True


def generate(prompt, settings=None, tags=None):
    messages = [
        {'role': 'system', 'content': PROMPT},
        {'role': 'user', 'content': prompt},
    ]
    if tags:
        messages[0]['content'] += '\n可选标签（只能从这里选）: %s。请在 tags 字段填 1-3 个标签名，没有合适的就留空数组。' % '、'.join(tags)
    content = _chat(settings or config(), messages)
    return read_json(content)


SUGGEST = """你是家常菜顾问。根据用户现有的食材和调料，推荐 4 道现在就能做的菜。
只输出一个 JSON 对象，不要代码块、不要解释：
{"dishes":[{"name":"菜名","reason":"一句话说明为什么合适，点出用到的现有食材"}]}
菜名要具体、可操作，理由不超过 40 字。"""


def suggest(settings, ingredients, staples):
    """按现有食材给出候选菜，只返回菜名与理由。"""
    have = '、'.join(ingredients) or '（未记录）'
    condiments = '、'.join(staples) or '（未记录）'
    content = _chat(settings, [
        {'role': 'system', 'content': SUGGEST},
        {'role': 'user', 'content': '现有食材：%s\n常备调料：%s' % (have, condiments)},
    ])
    dishes = _extract(content).get('dishes')
    if not isinstance(dishes, list) or not dishes:
        raise ValueError('AI 没有给出可用的菜名，请再试一次')
    picked = []
    for dish in dishes[:4]:
        if isinstance(dish, dict) and str(dish.get('name', '')).strip():
            picked.append({'name': str(dish['name']).strip()[:40], 'reason': str(dish.get('reason', '')).strip()[:160]})
    if not picked:
        raise ValueError('AI 没有给出可用的菜名，请再试一次')
    return picked

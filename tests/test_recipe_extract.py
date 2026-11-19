import pytest
from backend import recipe_extract as re


def _chat_split(dishes):
    import json as _json
    return lambda settings, messages, *, effort='low', max_tokens=4000: _json.dumps({'dishes': dishes}, ensure_ascii=False)


def _chat_extract(payload):
    import json as _json
    return lambda settings, messages, *, effort='low', max_tokens=4000: _json.dumps(payload, ensure_ascii=False)


# ---- 拆分 ----

def test_split_single_dish(monkeypatch):
    monkeypatch.setattr(re, '_chat', _chat_split(['整段正文']))
    assert re.split_article('任意正文', {'key': 'k'}) == ['整段正文']


def test_split_multi_dish(monkeypatch):
    monkeypatch.setattr(re, '_chat', _chat_split(['第一道菜', '第二道菜', '第三道菜']))
    assert re.split_article('x', {'key': 'k'}) == ['第一道菜', '第二道菜', '第三道菜']


def test_split_drops_empty_segments(monkeypatch):
    monkeypatch.setattr(re, '_chat', _chat_split(['第一道', '', '   ', '第三道']))
    assert re.split_article('x', {'key': 'k'}) == ['第一道', '第三道']


def test_split_falls_back_to_whole_text_on_bad_json(monkeypatch):
    monkeypatch.setattr(re, '_chat', lambda *a, **k: '抱歉，我无法完成')
    assert re.split_article('完整正文', {'key': 'k'}) == ['完整正文']


# ---- 单篇提取 ----

def test_extract_one_parses_and_fills_defaults(monkeypatch):
    monkeypatch.setattr(re, '_chat', _chat_extract({'name': '番茄炒蛋', 'ingredients': [{'name': '番茄', 'amount': '2个'}], 'steps': ['切块']}))
    data = re.extract_one('x', {'key': 'k'})
    assert data['name'] == '番茄炒蛋'
    assert data['minutes'] == '' and data['servings'] == '' and data['notes'] == ''
    assert data['ingredients'] == [{'name': '番茄', 'amount': '2个'}]
    assert data['steps'] == ['切块']


def test_extract_one_keeps_missing_fields_empty(monkeypatch):
    monkeypatch.setattr(re, '_chat', _chat_extract({'name': '', 'ingredients': [], 'steps': []}))
    data = re.extract_one('x', {'key': 'k'})
    assert data['name'] == '' and data['ingredients'] == [] and data['steps'] == []


# ---- 后处理：归一、分类、用量 ----

def test_postprocess_normalizes_names_and_classifies_condiments():
    draft = re._postprocess({
        'name': '菜', 'minutes': '', 'servings': '', 'notes': '',
        'ingredients': [
            {'name': '西红柿', 'amount': '2个'},
            {'name': '食盐', 'amount': '适量'},
            {'name': '食用油', 'amount': '适量'},
            {'name': '鸡蛋', 'amount': ''},
        ],
        'steps': ['切块'],
    }, '西红柿2个 食盐适量 食用油适量 鸡蛋')
    by_name = {i['name']: i for i in draft['ingredients']}
    assert set(by_name) == {'番茄', '盐', '油', '鸡蛋'}
    assert by_name['番茄']['kind'] == '食材'
    assert by_name['盐']['kind'] == '调料'
    assert by_name['油']['kind'] == '调料'
    assert by_name['鸡蛋']['kind'] == '食材'
    # 用量原文保留
    assert by_name['番茄']['amount'] == '2个'
    assert by_name['鸡蛋']['amount'] == ''


def test_postprocess_warns_missing_amount_and_keeps_empty():
    draft = re._postprocess({
        'name': '菜', 'minutes': '', 'servings': '', 'notes': '',
        'ingredients': [{'name': '鸡蛋', 'amount': ''}], 'steps': ['炒'],
    }, '鸡蛋炒熟')
    assert draft['ingredients'][0]['amount'] == ''
    assert any('未写用量' in w for w in draft['warnings'])


def test_postprocess_flags_unmentioned_ingredient_as_suspected_fabrication():
    draft = re._postprocess({
        'name': '菜', 'minutes': '', 'servings': '', 'notes': '',
        'ingredients': [{'name': '土豆', 'amount': '2个'}], 'steps': ['炒'],
    }, '只有鸡蛋和番茄')
    assert any('补造' in w for w in draft['warnings'])


def test_postprocess_flags_inferred_dish_name():
    draft = re._postprocess({
        'name': '可乐鸡翅', 'minutes': '', 'servings': '', 'notes': '',
        'ingredients': [{'name': '鸡翅', 'amount': '8个'}], 'steps': ['煎'],
    }, '材料：鸡翅8个、可乐一罐。做法：煎。')
    assert any('推断' in w for w in draft['warnings'])


def test_postprocess_keeps_mentioned_dish_name_without_warning():
    draft = re._postprocess({
        'name': '番茄炒蛋', 'minutes': '', 'servings': '', 'notes': '',
        'ingredients': [{'name': '番茄', 'amount': '2个'}], 'steps': ['炒'],
    }, '番茄炒蛋：番茄2个。')
    assert not any('推断' in w for w in draft['warnings'])


def test_postprocess_warns_missing_name_ingredients_steps():
    draft = re._postprocess({'name': '', 'minutes': '', 'servings': '', 'notes': '', 'ingredients': [], 'steps': []}, '')
    assert draft['name'] == '' and draft['ingredients'] == [] and draft['steps'] == []
    joined = ' '.join(draft['warnings'])
    assert '菜名' in joined and '食材' in joined and '步骤' in joined


def test_postprocess_skips_nameless_ingredient_and_warns():
    draft = re._postprocess({
        'name': '菜', 'minutes': '', 'servings': '', 'notes': '',
        'ingredients': [{'name': '', 'amount': '2个'}, {'name': '鸡蛋', 'amount': '2个'}], 'steps': ['炒'],
    }, '鸡蛋2个')
    assert [i['name'] for i in draft['ingredients']] == ['鸡蛋']
    assert any('没有名称' in w for w in draft['warnings'])


def test_postprocess_drops_empty_steps():
    draft = re._postprocess({
        'name': '菜', 'minutes': '', 'servings': '', 'notes': '',
        'ingredients': [{'name': '鸡蛋', 'amount': '2个'}],
        'steps': ['   ', {'text': '炒熟'}, ''],
    }, '鸡蛋2个 炒熟')
    assert draft['steps'] == ['炒熟']


# ---- 别名反向匹配（补造校验） ----

def test_mentioned_alias_reverse_match():
    assert re._mentioned('西红柿切块', '番茄')
    assert re._mentioned('食盐少许', '盐')
    assert not re._mentioned('鸡蛋番茄', '土豆')


# ---- 编排：多道菜 ----

def test_extract_splits_then_extracts_each(monkeypatch):
    monkeypatch.setattr(re, 'split_article', lambda text, settings=None: ['菜A 鸡蛋2个', '菜B 番茄1个'])
    calls = []
    def fake_extract_one(text, settings=None):
        calls.append(text)
        name = '菜A' if '菜A' in text else '菜B'
        return {'name': name, 'minutes': '', 'servings': '', 'notes': '',
                'ingredients': [{'name': '鸡蛋' if name == '菜A' else '番茄', 'amount': '2个'}], 'steps': ['炒']}
    monkeypatch.setattr(re, 'extract_one', fake_extract_one)
    result = re.extract('正文', {'key': 'k'})
    assert result['multi'] is True
    assert [r['name'] for r in result['recipes']] == ['菜A', '菜B']
    assert len(calls) == 2


def test_extract_single_recipe_not_multi(monkeypatch):
    monkeypatch.setattr(re, 'split_article', lambda text, settings=None: [text])
    monkeypatch.setattr(re, 'extract_one', lambda text, settings=None: {
        'name': '菜', 'minutes': '', 'servings': '', 'notes': '',
        'ingredients': [{'name': '鸡蛋', 'amount': '2个'}], 'steps': ['炒']})
    result = re.extract('正文', {'key': 'k'})
    assert result['multi'] is False and len(result['recipes']) == 1

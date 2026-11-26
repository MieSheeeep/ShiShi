import pytest
from backend import recipe_search


def _recipes():
    return [
        {'id': 1, 'name': '番茄炒蛋', 'ingredients': [
            {'name': '番茄', 'amount': '2个', 'kind': '食材'},
            {'name': '鸡蛋', 'amount': '3个', 'kind': '食材'},
            {'name': '盐', 'amount': '适量', 'kind': '调料'},
        ]},
        {'id': 2, 'name': '鸡胸肉沙拉', 'ingredients': [
            {'name': '鸡胸肉', 'amount': '1块', 'kind': '食材'},
            {'name': '生菜', 'amount': '1颗', 'kind': '食材'},
        ]},
    ]


# ---- 自由文本解析 ----

def test_parse_tokens_strips_quantities_and_units():
    assert recipe_search.parse_tokens('鸡蛋 半颗白菜 挂面') == ['鸡蛋', '白菜', '挂面']


def test_parse_tokens_dedup_and_separators():
    assert recipe_search.parse_tokens('鸡蛋，鸡蛋、番茄；番茄') == ['鸡蛋', '番茄']


def test_parse_tokens_keeps_pure_names():
    assert recipe_search.parse_tokens('西红柿 2个') == ['西红柿']


# ---- 模糊匹配 ----

def test_fuzzy_rank_alias_match():
    rows = recipe_search.fuzzy_rank(_recipes(), ['西红柿', '鸡蛋', '盐'])
    tomato = next(r for r in rows if r['name'] == '番茄炒蛋')
    assert tomato['missing'] == []          # 西红柿→番茄 命中
    assert '番茄' in tomato['matched']      # 归一后的名字


def test_fuzzy_rank_substring_match():
    rows = recipe_search.fuzzy_rank(_recipes(), ['鸡胸'])
    assert any(r['name'] == '鸡胸肉沙拉' for r in rows)


def test_fuzzy_rank_missing_and_ratio():
    rows = recipe_search.fuzzy_rank(_recipes(), ['番茄', '盐'], ['盐'])
    tomato = next(r for r in rows if r['name'] == '番茄炒蛋')
    assert tomato['missing'] == ['鸡蛋']
    assert tomato['ratio'] == 0.5          # 主料番茄+鸡蛋，命中番茄


def test_fuzzy_rank_skips_recipes_with_no_match():
    rows = recipe_search.fuzzy_rank(_recipes(), ['土豆'])
    assert all(r['name'] != '番茄炒蛋' for r in rows)
    assert all(r['name'] != '鸡胸肉沙拉' for r in rows)


def test_fuzzy_rank_sorts_fewer_missing_first():
    rows = recipe_search.fuzzy_rank(_recipes(), ['番茄', '鸡蛋', '盐'])
    assert rows[0]['name'] == '番茄炒蛋'   # 全命中排最前
    assert '鸡胸肉沙拉' not in [r['name'] for r in rows]


# ---- AI 推荐：缓存与食谱感知 ----

def test_suggest_with_ai_returns_and_caches(monkeypatch):
    calls = []
    def fake_chat(settings, messages, extra=None):
        calls.append(messages)
        return '{"dishes":[{"name":"番茄炒蛋","reason":"有番茄和鸡蛋"}]}'
    monkeypatch.setattr(recipe_search.ai_recipe, '_chat', fake_chat)
    settings = {'key': 'k'}
    recipes = [{'name': '番茄炒蛋', 'ingredients': []}]
    cache = {}
    d1, c1 = recipe_search.suggest_with_ai(settings, recipes, ['番茄'], ['盐'], cache)
    d2, c2 = recipe_search.suggest_with_ai(settings, recipes, ['番茄'], ['盐'], cache)
    assert c1 is False and c2 is True       # 第二次命中缓存
    assert len(calls) == 1                  # 只调用一次模型
    assert d1 == d2 == [{'name': '番茄炒蛋', 'reason': '有番茄和鸡蛋'}]


def test_suggest_with_ai_cache_key_varies_with_recipes(monkeypatch):
    calls = []
    monkeypatch.setattr(recipe_search.ai_recipe, '_chat',
                        lambda s, m, extra=None: (calls.append(m) or '{"dishes":[{"name":"菜","reason":"x"}]}'))
    cache = {}
    recipe_search.suggest_with_ai({'key': 'k'}, [{'name': '已有A', 'ingredients': []}], ['番茄'], [], cache)
    recipe_search.suggest_with_ai({'key': 'k'}, [{'name': '已有B', 'ingredients': []}], ['番茄'], [], cache)
    assert len(calls) == 2                  # 已有食谱不同 → 不同缓存键


def test_suggest_with_ai_passes_existing_recipes_to_model(monkeypatch):
    seen = {}
    def fake_chat(settings, messages, extra=None):
        seen['user'] = messages[-1]['content']
        return '{"dishes":[{"name":"新菜","reason":"用现有食材"}]}'
    monkeypatch.setattr(recipe_search.ai_recipe, '_chat', fake_chat)
    recipe_search.suggest_with_ai({'key': 'k'}, [{'name': '番茄炒蛋', 'ingredients': []}], ['番茄'], ['盐'], {})
    assert '不要重复推荐' in seen['user']
    assert '番茄炒蛋' in seen['user']


def test_suggest_with_ai_truncates_and_filters(monkeypatch):
    monkeypatch.setattr(recipe_search.ai_recipe, '_chat', lambda s, m, extra=None:
        '{"dishes":[{"name":" 番茄炒蛋 ","reason":"长理由"},{"name":""},{"reason":"没有菜名"}]}')
    dishes, _ = recipe_search.suggest_with_ai({'key': 'k'}, [], ['番茄'], ['盐'], {})
    assert dishes == [{'name': '番茄炒蛋', 'reason': '长理由'}]


def test_suggest_with_ai_surfaces_empty_answer(monkeypatch):
    monkeypatch.setattr(recipe_search.ai_recipe, '_chat', lambda s, m, extra=None: '{"dishes":[]}')
    with pytest.raises(ValueError, match='菜名'):
        recipe_search.suggest_with_ai({'key': 'k'}, [], [], [], {})

import pytest
from backend.core import parse_douguo, merge_ingredients, canonical_url

def test_douguo_table():
    html = '<h1 class="title">番茄炒蛋</h1><table class="retamr"><tr><td><span class="scname">西红柿</span></td><td><span class="scnum">两个</span></td></tr></table><div class="step"><p>1. 切块炒熟</p></div>'
    r = parse_douguo(html, 'https://www.douguo.com/cookbook/1.html')
    assert r['name'] == '番茄炒蛋'
    assert r['ingredients'][0]['name'] == '番茄'
    assert r['steps'] == ['切块炒熟']

def test_merge_units_and_uncertain():
    recipes = [{'name':'A','ingredients':[{'name':'面粉','amount':'500克'},{'name':'鸡蛋','amount':'2个'}]}, {'name':'B','ingredients':[{'name':'面粉','amount':'0.5千克'},{'name':'鸡蛋','amount':'100克'},{'name':'盐','amount':'适量'}]}]
    rows = merge_ingredients(recipes)
    assert next(x for x in rows if x['name']=='面粉')['amount'] == '1000克'
    assert len([x for x in rows if x['name']=='鸡蛋']) == 2
    assert next(x for x in rows if x['name']=='盐')['amount'] == '适量'

def test_url_restricted():
    assert canonical_url('https://www.douguo.com/cookbook/123.html?from=x').endswith('/123.html')
    for url in ['http://127.0.0.1/a','https://www.douguo.com.evil.com/cookbook/1.html','https://www.douguo.com/user/1']:
        with pytest.raises(ValueError): canonical_url(url)

def test_no_invented_recipe():
    with pytest.raises(ValueError): parse_douguo('<h1>验证页面</h1>', 'https://www.douguo.com/cookbook/1.html')

def test_jsonld_nested_steps_and_quantity():
    html = '<script type="application/ld+json">{"@graph":[{"@type":"Recipe","name":"蛋饼","recipeIngredient":["鸡蛋2个","面粉 100克"],"recipeInstructions":[{"@type":"HowToSection","itemListElement":[{"text":"搅拌"},{"text":"煎熟"}]}]}]}</script>'
    recipe = parse_douguo(html,'https://www.douguo.com/cookbook/1.html')
    assert recipe['ingredients'][0]['name']=='鸡蛋'
    assert recipe['ingredients'][0]['amount']=='2个'
    assert recipe['steps']==['搅拌','煎熟']

def test_step_number_does_not_remove_temperature_or_repeat_nested_text():
    html = '<h1>烤面包</h1><table class="retamr"><tr><td><span class="scname">面粉</span><span class="scnum">100克</span></td></tr></table><div class="step"><div class="stepinfo"><p>170度烘烤15分钟</p></div></div>'
    r=parse_douguo(html,'https://www.douguo.com/cookbook/1.html')
    assert r['steps']==['170度烘烤15分钟']

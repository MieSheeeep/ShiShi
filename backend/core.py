import json
import re
from decimal import Decimal
from urllib.parse import urlsplit
from bs4 import BeautifulSoup

ALIASES = {'西红柿':'番茄','马铃薯':'土豆','洋芋':'土豆','食盐':'盐','食用油':'油'}
def normalize(name):
    name = name.strip()
    return ALIASES.get(name, name)

def canonical_url(url):
    p = urlsplit(url.strip())
    if p.scheme not in ('http','https') or p.hostname not in ('www.douguo.com','douguo.com') or p.username or p.password or p.port not in (None,80,443) or not re.fullmatch(r'/cookbook/\d+\.html',p.path):
        raise ValueError('仅支持豆果菜谱链接：https://www.douguo.com/cookbook/数字.html')
    return 'https://www.douguo.com' + p.path

def quantity(raw):
    raw = raw.strip().replace(' ', '')
    digits = {'一':'1','二':'2','两':'2','三':'3','四':'4','五':'5','六':'6','七':'7','八':'8','九':'9','十':'10','半':'0.5'}
    raw = re.sub(r'^[一二两三四五六七八九十半](?=[^一二三四五六七八九十])',lambda m:digits[m[0]],raw)
    m = re.fullmatch(r'(\d+(?:\.\d+)?)\s*(千克|公斤|kg|克|g|毫升|ml|升|L|个|颗|根|片|勺)',raw,re.I)
    if not m: return None
    n,u = Decimal(m[1]),m[2].lower()
    factor, unit = {'千克':(1000,'克'),'公斤':(1000,'克'),'kg':(1000,'克'),'g':(1,'克'),'ml':(1,'毫升'),'升':(1000,'毫升'),'l':(1000,'毫升')}.get(u,(1,u))
    return n*factor,unit

def merge_ingredients(recipes):
    grouped = {}
    for recipe in recipes:
        for ing in recipe['ingredients']:
            name, raw = normalize(ing['name']), ing.get('amount','未注明') or '未注明'
            parsed = quantity(raw)
            key = (name,parsed[1] if parsed else 'text:'+raw)
            row = grouped.setdefault(key,{'name':name,'number':Decimal(0),'unit':parsed[1] if parsed else None,'amount':raw,'sources':[],'checked':False})
            if parsed: row['number'] += parsed[0]
            row['sources'].append({'recipe':recipe['name'],'original':ing['name']+' '+raw})
    rows = []
    for row in grouped.values():
        if row['unit']: row['amount'] = format(row['number'].normalize(),'f')+row['unit']
        del row['number']; del row['unit']
        rows.append(row)
    return rows

def parse_douguo(html, url):
    soup = BeautifulSoup(html,'html.parser')
    data = {'name':'','author':'','source':url,'minutes':'','servings':'','tags':['豆果导入'],'notes':'','ingredients':[],'steps':[]}
    def walk(value):
        if isinstance(value,list):
            for item in value: yield from walk(item)
        elif isinstance(value,dict):
            if 'Recipe' in value.get('@type',[]): yield value
            for v in value.values():
                if isinstance(v,(dict,list)): yield from walk(v)
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            recipe = next(walk(json.loads(script.string or script.get_text())),None)
        except (ValueError,TypeError): continue
        if not recipe: continue
        data['name'] = recipe.get('name','')
        author = recipe.get('author',{})
        if isinstance(author,list): author = author[0] if author else {}
        data['author'] = author.get('name','') if isinstance(author,dict) else str(author)
        def steps(items):
            if isinstance(items,str): return [items]
            out=[]
            for item in items or []:
                if isinstance(item,str): out.append(item)
                elif isinstance(item,dict):
                    if item.get('text'): out.append(item['text'])
                    else: out.extend(steps(item.get('itemListElement',[])))
            return out
        data['steps'] = steps(recipe.get('recipeInstructions',[]))
        for raw in recipe.get('recipeIngredient',[]):
            m = re.match(r'^(.+?)(?:\s+|(?=\d))(.+)$',raw.strip())
            data['ingredients'].append({'name':normalize(m[1] if m else raw),'amount':m[2] if m else '未注明','kind':'食材'})
        break
    title = soup.select_one('h1.title, h1')
    if title: data['name'] = title.get_text(' ',strip=True)
    author = soup.select_one('.author-info .nickname, .author .nickname, .author-info .nickname')
    if author: data['author'] = author.get_text(strip=True)
    table_items=[]
    for row in soup.select('table.retamr tr, .ingredients tr'):
        names, amounts = row.select('.scname'), row.select('.scnum')
        for idx,name in enumerate(names):
            table_items.append({'name':normalize(name.get_text(strip=True)),'amount':amounts[idx].get_text(strip=True) if idx<len(amounts) else '未注明','kind':'食材'})
    if table_items: data['ingredients'] = table_items
    steps = soup.select('.step .stepinfo, .step p')
    if steps:
        data['steps'] = [re.sub(r'^(?:步骤)?\s*\d+\s*[.、：:]?\s*','',x.get_text(' ',strip=True)) for x in steps]
        data['steps'] = [x for x in data['steps'] if x]
    if not data['name'] or not data['ingredients'] or not data['steps']:
        raise ValueError('未找到完整材料和步骤。页面可能需要验证、已失效或排版暂不支持，可手动录入。')
    return data

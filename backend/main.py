import json
import os
from pathlib import Path
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text
from backend.core import canonical_url, parse_douguo, merge_ingredients, normalize
from backend.seed import examples

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
DATA.mkdir(exist_ok=True)
engine = create_engine(os.getenv('SHISHI_DATABASE_URL',f'sqlite:///{DATA / "shishi.db"}'),connect_args={'check_same_thread':False})
with engine.begin() as db:
    db.execute(text('CREATE TABLE IF NOT EXISTS recipes (id INTEGER PRIMARY KEY, source TEXT UNIQUE, body TEXT NOT NULL)'))
    db.execute(text('CREATE TABLE IF NOT EXISTS shopping (id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL)'))
    db.execute(text('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, body TEXT NOT NULL)'))
    if not db.execute(text("SELECT key FROM settings WHERE key='seeded'")).first():
        for r in examples(): db.execute(text('INSERT INTO recipes(source,body) VALUES(NULL,:body)'),{'body':json.dumps(r,ensure_ascii=False)})
        db.execute(text("INSERT INTO settings VALUES('seeded','true')"))
app = FastAPI(title='食拾 · 本地食谱管理')

class Ingredient(BaseModel):
    name: str = Field(min_length=1,max_length=100)
    amount: str = Field(default='未注明',max_length=100)
    kind: str = '食材'
class Recipe(BaseModel):
    name: str = Field(min_length=1,max_length=200)
    author: str = ''
    source: str = ''
    minutes: str = ''
    servings: str = ''
    emoji: str = '🍲'
    tags: list[str] = []
    notes: str = ''
    ingredients: list[Ingredient] = Field(min_length=1,max_length=200)
    steps: list[str] = Field(min_length=1,max_length=200)
class Link(BaseModel):
    url: str
class Match(BaseModel):
    ingredients: list[str] = []
    staples: list[str] = []
class Selection(BaseModel):
    ids: list[int] = Field(min_length=1)
class Shopping(BaseModel):
    items: list[dict]

def all_recipes():
    with engine.connect() as db:
        return [dict(json.loads(row.body),id=row.id) for row in db.execute(text('SELECT id,body FROM recipes ORDER BY id DESC'))]

def validated(recipe):
    body = recipe.model_dump()
    body['name'] = body['name'].strip()
    if not body['name'] or any(not x.strip() for x in body['steps']) or any(not x['name'].strip() for x in body['ingredients']):
        raise HTTPException(422,'菜名、材料和步骤不能为空')
    if body['source']:
        try: body['source'] = canonical_url(body['source'])
        except ValueError as e: raise HTTPException(422,str(e))
    for item in body['ingredients']: item['name'] = normalize(item['name'])
    return body

@app.get('/api/recipes')
def recipes(): return all_recipes()

@app.post('/api/recipes')
def save(recipe:Recipe):
    body=validated(recipe)
    from sqlalchemy.exc import IntegrityError
    try:
        with engine.begin() as db:
            result=db.execute(text('INSERT INTO recipes(source,body) VALUES(:source,:body)'),{'source':body['source'] or None,'body':json.dumps(body,ensure_ascii=False)})
            return dict(body,id=result.lastrowid)
    except IntegrityError: raise HTTPException(409,'这个豆果链接已经收藏过了')

@app.put('/api/recipes/{rid}')
def update(rid:int,recipe:Recipe):
    body=validated(recipe)
    from sqlalchemy.exc import IntegrityError
    try:
        with engine.begin() as db:
            result=db.execute(text('UPDATE recipes SET source=:source,body=:body WHERE id=:id'),{'id':rid,'source':body['source'] or None,'body':json.dumps(body,ensure_ascii=False)})
            if not result.rowcount: raise HTTPException(404,'食谱不存在')
        return dict(body,id=rid)
    except IntegrityError: raise HTTPException(409,'这个豆果链接已经收藏过了')

@app.delete('/api/recipes/{rid}')
def delete(rid:int):
    with engine.begin() as db: db.execute(text('DELETE FROM recipes WHERE id=:id'),{'id':rid})
    return {'ok':True}

@app.post('/api/imports')
def import_recipe(link:Link):
    try: url=canonical_url(link.url)
    except ValueError as e: raise HTTPException(422,str(e))
    if any(r['source']==url for r in all_recipes()): raise HTTPException(409,'这个链接已经在你的食谱库中了')
    try:
        with httpx.Client(timeout=20,follow_redirects=False,headers={'User-Agent':'Mozilla/5.0 (compatible; ShiShi/0.1; personal recipe organizer)'}) as client:
            with client.stream('GET',url) as response:
                if response.is_redirect: raise ValueError('豆果返回了跳转页，请使用完整的菜谱链接')
                response.raise_for_status()
                chunks=[]; size=0
                for chunk in response.iter_bytes():
                    size+=len(chunk)
                    if size>3_000_000: raise ValueError('页面内容过大，暂不支持导入')
                    chunks.append(chunk)
                html=b''.join(chunks).decode('utf-8',errors='replace')
        return parse_douguo(html,url)
    except ValueError as e: raise HTTPException(422,str(e))
    except httpx.HTTPError: raise HTTPException(502,'暂时无法访问豆果，可能是网络、访问限制或验证页。请稍后重试，也可以手动录入。')

@app.post('/api/match')
def match(body:Match):
    have={normalize(x) for x in body.ingredients+body.staples}
    rows=[]
    for r in all_recipes():
        missing=list(dict.fromkeys(i['name'] for i in r['ingredients'] if normalize(i['name']) not in have))
        rows.append(dict(r,missing=missing))
    return sorted(rows,key=lambda r:(len(r['missing']),len(r['missing'])/len(r['ingredients'])))

@app.post('/api/shopping')
def create_shopping(body:Selection):
    rows=[r for r in all_recipes() if r['id'] in body.ids]
    if len(rows)!=len(set(body.ids)): raise HTTPException(404,'部分食谱不存在，请重新选择')
    items=merge_ingredients(rows)
    set_shopping(Shopping(items=items))
    return items

@app.get('/api/shopping')
def shopping():
    with engine.connect() as db: row=db.execute(text('SELECT body FROM shopping WHERE id=1')).first()
    return json.loads(row.body) if row else []

@app.put('/api/shopping')
def set_shopping(body:Shopping):
    with engine.begin() as db:
        db.execute(text('INSERT INTO shopping(id,body) VALUES(1,:body) ON CONFLICT(id) DO UPDATE SET body=excluded.body'),{'body':json.dumps(body.items,ensure_ascii=False)})
    return {'ok':True}

@app.get('/api/settings')
def settings():
    with engine.connect() as db: row=db.execute(text("SELECT body FROM settings WHERE key='pantry'")).first()
    return json.loads(row.body) if row else {'ingredients':[],'staples':['盐','油']}

@app.put('/api/settings')
def set_settings(body:Match):
    with engine.begin() as db: db.execute(text("INSERT INTO settings(key,body) VALUES('pantry',:body) ON CONFLICT(key) DO UPDATE SET body=excluded.body"),{'body':body.model_dump_json()})
    return {'ok':True}

dist=ROOT/'frontend'/'dist'
if dist.exists(): app.mount('/',StaticFiles(directory=dist,html=True),name='frontend')

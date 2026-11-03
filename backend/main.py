import json
import os
import re
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import create_engine, text
from backend.core import canonical_url, merge_ingredients, normalize
from backend.seed import examples
from backend.crawler import fetch_recipe
from backend.source_urls import import_url
from backend.media import download_recipe_images, MEDIA_DIR

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
    source_text: str = Field(default='',max_length=50000)
    source_images: list[str] = Field(default_factory=list,max_length=24)
    step_images: list[list[str]] = Field(default_factory=list,max_length=200)
    ingredients: list[Ingredient] = Field(min_length=1,max_length=200)
    steps: list[str] = Field(min_length=1,max_length=200)
    @field_validator('source_images','step_images')
    @classmethod
    def local_images_only(cls,value):
        urls=[url for group in value for url in group] if value and isinstance(value[0],list) else value
        if len(urls)>48 or any(not re.fullmatch(r'/api/media/[a-f0-9]{64}\.(?:jpg|png|webp|gif)',url) for url in urls):
            raise ValueError('图片必须是食拾已保存的本地图片')
        return value
class Link(BaseModel):
    url: str = Field(min_length=1,max_length=20000)
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
    except IntegrityError: raise HTTPException(409,'这个来源链接已经收藏过了')

@app.put('/api/recipes/{rid}')
def update(rid:int,recipe:Recipe):
    body=validated(recipe)
    from sqlalchemy.exc import IntegrityError
    try:
        with engine.begin() as db:
            result=db.execute(text('UPDATE recipes SET source=:source,body=:body WHERE id=:id'),{'id':rid,'source':body['source'] or None,'body':json.dumps(body,ensure_ascii=False)})
            if not result.rowcount: raise HTTPException(404,'食谱不存在')
        return dict(body,id=rid)
    except IntegrityError: raise HTTPException(409,'这个来源链接已经收藏过了')

@app.delete('/api/recipes/{rid}')
def delete(rid:int):
    with engine.begin() as db: db.execute(text('DELETE FROM recipes WHERE id=:id'),{'id':rid})
    return {'ok':True}

@app.post('/api/imports')
def import_recipe(link:Link):
    try:
        original=import_url(link.url)
        url=canonical_url(original)
    except ValueError as e: raise HTTPException(422,str(e))
    if any(r['source']==url for r in all_recipes()): raise HTTPException(409,'这个链接已经在你的食谱库中了')
    try:
        draft=fetch_recipe(original)
        if any(r['source']==draft['source'] for r in all_recipes()):
            raise HTTPException(409,'这篇笔记已经在你的食谱库中了')
        return download_recipe_images(draft)
    except ValueError as e: raise HTTPException(422,str(e))

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

MEDIA_DIR.mkdir(parents=True,exist_ok=True)
app.mount('/api/media',StaticFiles(directory=MEDIA_DIR),name='recipe-media')
dist=ROOT/'frontend'/'dist'
if dist.exists(): app.mount('/',StaticFiles(directory=dist,html=True),name='frontend')

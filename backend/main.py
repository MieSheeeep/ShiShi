import json
import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text
from backend.core import canonical_url, merge_ingredients, normalize
from backend.recipe_schema import Recipe, draft_v2
from backend import recipe_store as store
from backend.crawler import fetch_recipe
from backend.source_urls import import_url
from backend.media import download_recipe_images, MEDIA_DIR

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
DATA.mkdir(exist_ok=True)
engine = create_engine(os.getenv('SHISHI_DATABASE_URL',f'sqlite:///{DATA / "shishi.db"}'),connect_args={'check_same_thread':False})
store.initialize(engine)
app = FastAPI(title='食拾 · 本地食谱管理')

class Link(BaseModel):
    url: str = Field(min_length=1,max_length=20000)
class Match(BaseModel):
    ingredients: list[str] = []
    staples: list[str] = []
class Selection(BaseModel):
    ids: list[int] = Field(min_length=1)
class Shopping(BaseModel):
    items: list[dict]

def all_recipes(): return store.list_recipes(engine)

@app.get('/api/recipes')
def recipes(tag_id: list[str] = Query(default=[])):
    return [r for r in all_recipes() if set(tag_id).issubset(r['tag_ids'])]

def persist_recipe(recipe,rid=None):
    from sqlalchemy.exc import IntegrityError
    try:return store.write_recipe(engine,recipe,rid)
    except IntegrityError:raise HTTPException(409,'这个来源链接已经收藏过了')
    except LookupError as e:raise HTTPException(404,str(e))
    except ValueError as e:raise HTTPException(422,str(e))

@app.post('/api/recipes')
def save(recipe:Recipe):return persist_recipe(recipe)

@app.put('/api/recipes/{rid}')
def update(rid:int,recipe:Recipe):return persist_recipe(recipe,rid)

class NamedItem(BaseModel):
    name: str = Field(min_length=1,max_length=80)
class NewTag(NamedItem):
    group_id: str

def tag_action(action,*args):
    from sqlalchemy.exc import IntegrityError
    try:return action(engine,*args)
    except IntegrityError:raise HTTPException(409,'同一分组内已有这个名称')
    except LookupError as e:raise HTTPException(404,str(e))
    except ValueError as e:raise HTTPException(422,str(e))

@app.get('/api/tags')
def get_tags():return store.catalogue(engine)

@app.post('/api/tag-groups')
def add_group(item:NamedItem):return tag_action(store.create_group,item.name)

@app.post('/api/tags')
def add_tag(item:NewTag):return tag_action(store.create_tag,item.group_id,item.name)

@app.patch('/api/tag-groups/{gid}')
def rename_group(gid:str,item:NamedItem):return tag_action(store.rename_item,'tag_groups',gid,item.name)

@app.patch('/api/tags/{tid}')
def rename_tag(tid:str,item:NamedItem):return tag_action(store.rename_item,'tags',tid,item.name)

@app.delete('/api/tag-groups/{gid}')
def remove_group(gid:str):return tag_action(store.delete_item,'tag_groups',gid)

@app.delete('/api/tags/{tid}')
def remove_tag(tid:str):return tag_action(store.delete_item,'tags',tid)

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
    if any(r['source']['url']==url for r in all_recipes()): raise HTTPException(409,'这个链接已经在你的食谱库中了')
    try:
        draft=fetch_recipe(original)
        if any(r['source']['url']==draft['source'] for r in all_recipes()):
            raise HTTPException(409,'这篇笔记已经在你的食谱库中了')
        return draft_v2(download_recipe_images(draft))
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

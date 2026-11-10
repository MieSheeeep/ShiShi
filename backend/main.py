"""食拾接口：账号鉴权与按用户隔离的食谱管理。

所有 /api 业务接口都需要 ``Authorization: Bearer <token>``；账号与登录相关接口除外。
接口约定见 docs/api.md。
"""
import os
from pathlib import Path

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import create_engine

from backend import auth, recipe_store as store
from backend.core import canonical_url, merge_ingredients, normalize
from backend.crawler import fetch_recipe
from backend.media import MEDIA_DIR, download_recipe_images, save_upload
from backend.recipe_schema import Recipe, draft_v2
from backend.source_urls import import_url

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
DEMO_DIR = Path(__file__).resolve().parent / 'demo_images'
DATA.mkdir(exist_ok=True)
engine = create_engine(os.getenv('SHISHI_DATABASE_URL', f'sqlite:///{DATA / "shishi.db"}'), connect_args={'check_same_thread': False})
store.initialize(engine)
app = FastAPI(title='食拾 · 个人食谱管理', description='账号登录后管理自己的食谱、标签、常备食材与采购清单。')


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=6, max_length=128)
class Link(BaseModel):
    url: str = Field(min_length=1, max_length=20000)
class Match(BaseModel):
    ingredients: list[str] = []
    staples: list[str] = []
class Selection(BaseModel):
    ids: list[int] = Field(min_length=1)
class Shopping(BaseModel):
    items: list[dict]
class NamedItem(BaseModel):
    name: str = Field(min_length=1, max_length=80)
class NewTag(NamedItem):
    group_id: str


def bearer_token(authorization):
    """从 Authorization 头取出 Bearer 令牌。"""
    return authorization[7:].strip() if authorization.lower().startswith('bearer ') else ''


def current_user(authorization: str = Header(default='')) -> dict:
    """校验登录令牌，返回当前用户；缺失或失效返回 401。"""
    user = auth.resolve_token(engine, bearer_token(authorization))
    if not user:
        raise HTTPException(401, '请先登录', headers={'WWW-Authenticate': 'Bearer'})
    return user


@app.post('/api/auth/register')
def register(body: Credentials):
    """注册账号并直接返回登录令牌，新账号会得到默认分组与演示食谱。"""
    try:
        user = auth.create_user(engine, body.username, body.password)
    except LookupError as error:
        raise HTTPException(409, str(error))
    except ValueError as error:
        raise HTTPException(422, str(error))
    store.bootstrap_user(engine, user['id'])
    return {'token': auth.issue_token(engine, user['id']), 'user': user}


@app.post('/api/auth/login')
def login(body: Credentials):
    """账号密码登录，失败统一返回 401，不区分用户名不存在或密码错误。"""
    user = auth.authenticate(engine, body.username, body.password)
    if not user:
        raise HTTPException(401, '用户名或密码错误')
    return {'token': auth.issue_token(engine, user['id']), 'user': user}


@app.post('/api/auth/logout')
def logout(authorization: str = Header(default=''), user: dict = Depends(current_user)):
    """退出登录，当前令牌立即失效。"""
    auth.revoke_token(engine, bearer_token(authorization))
    return {'ok': True}


@app.get('/api/auth/me')
def me(user: dict = Depends(current_user)):
    """返回当前登录用户，用于前端恢复会话。"""
    return user


@app.post('/api/media')
def upload_media(file: UploadFile = File(...), user: dict = Depends(current_user)):
    """上传封面图，返回可在食谱中引用的本地地址。"""
    body = file.file.read(5_000_001)
    try:
        return {'url': save_upload(body)}
    except ValueError as error:
        raise HTTPException(422, str(error))


@app.get('/api/recipes')
def recipes(tag_id: list[str] = Query(default=[]), user: dict = Depends(current_user)):
    return [recipe for recipe in store.list_recipes(engine, user['id']) if set(tag_id).issubset(recipe['tag_ids'])]


def persist_recipe(recipe, user_id, rid=None):
    from sqlalchemy.exc import IntegrityError
    try:
        return store.write_recipe(engine, recipe, user_id, rid)
    except IntegrityError:
        raise HTTPException(409, '这个来源链接已经收藏过了')
    except LookupError as error:
        raise HTTPException(404, str(error))
    except ValueError as error:
        raise HTTPException(422, str(error))


@app.post('/api/recipes')
def save(recipe: Recipe, user: dict = Depends(current_user)):
    return persist_recipe(recipe, user['id'])


@app.put('/api/recipes/{rid}')
def update(rid: int, recipe: Recipe, user: dict = Depends(current_user)):
    return persist_recipe(recipe, user['id'], rid)


@app.delete('/api/recipes/{rid}')
def delete(rid: int, user: dict = Depends(current_user)):
    if not store.delete_recipe(engine, rid, user['id']):
        raise HTTPException(404, '食谱不存在')
    return {'ok': True}


def tag_action(action, *args):
    from sqlalchemy.exc import IntegrityError
    try:
        return action(engine, *args)
    except IntegrityError:
        raise HTTPException(409, '同一分组内已有这个名称')
    except LookupError as error:
        raise HTTPException(404, str(error))
    except ValueError as error:
        raise HTTPException(422, str(error))


@app.get('/api/tags')
def get_tags(user: dict = Depends(current_user)):
    return store.catalogue(engine, user['id'])


@app.post('/api/tag-groups')
def add_group(item: NamedItem, user: dict = Depends(current_user)):
    return tag_action(store.create_group, item.name, user['id'])


@app.post('/api/tags')
def add_tag(item: NewTag, user: dict = Depends(current_user)):
    return tag_action(store.create_tag, item.group_id, item.name, user['id'])


@app.patch('/api/tag-groups/{gid}')
def rename_group(gid: str, item: NamedItem, user: dict = Depends(current_user)):
    return tag_action(store.rename_item, 'tag_groups', gid, item.name, user['id'])


@app.patch('/api/tags/{tid}')
def rename_tag(tid: str, item: NamedItem, user: dict = Depends(current_user)):
    return tag_action(store.rename_item, 'tags', tid, item.name, user['id'])


@app.delete('/api/tag-groups/{gid}')
def remove_group(gid: str, user: dict = Depends(current_user)):
    return tag_action(store.delete_item, 'tag_groups', gid, user['id'])


@app.delete('/api/tags/{tid}')
def remove_tag(tid: str, user: dict = Depends(current_user)):
    return tag_action(store.delete_item, 'tags', tid, user['id'])


@app.post('/api/imports')
def import_recipe(link: Link, user: dict = Depends(current_user)):
    try:
        original = import_url(link.url)
        url = canonical_url(original)
    except ValueError as error:
        raise HTTPException(422, str(error))
    if any(recipe['source']['url'] == url for recipe in store.list_recipes(engine, user['id'])):
        raise HTTPException(409, '这个链接已经在你的食谱库中了')
    try:
        draft = fetch_recipe(original)
        if any(recipe['source']['url'] == draft['source'] for recipe in store.list_recipes(engine, user['id'])):
            raise HTTPException(409, '这篇笔记已经在你的食谱库中了')
        return draft_v2(download_recipe_images(draft))
    except ValueError as error:
        raise HTTPException(422, str(error))


@app.post('/api/match')
def match(body: Match, user: dict = Depends(current_user)):
    have = {normalize(item) for item in body.ingredients + body.staples}
    rows = []
    for recipe in store.list_recipes(engine, user['id']):
        missing = list(dict.fromkeys(item['name'] for item in recipe['ingredients'] if normalize(item['name']) not in have))
        rows.append(dict(recipe, missing=missing))
    return sorted(rows, key=lambda recipe: (len(recipe['missing']), len(recipe['missing']) / len(recipe['ingredients'])))


@app.post('/api/shopping')
def create_shopping(body: Selection, user: dict = Depends(current_user)):
    rows = [recipe for recipe in store.list_recipes(engine, user['id']) if recipe['id'] in body.ids]
    if len(rows) != len(set(body.ids)):
        raise HTTPException(404, '部分食谱不存在，请重新选择')
    items = merge_ingredients(rows)
    store.save_list(engine, user['id'], items)
    return items


@app.get('/api/shopping')
def shopping(user: dict = Depends(current_user)):
    return store.read_list(engine, user['id'])


@app.put('/api/shopping')
def set_shopping(body: Shopping, user: dict = Depends(current_user)):
    store.save_list(engine, user['id'], body.items)
    return {'ok': True}


@app.get('/api/settings')
def settings(user: dict = Depends(current_user)):
    return store.read_settings(engine, user['id'])


@app.put('/api/settings')
def set_settings(body: Match, user: dict = Depends(current_user)):
    store.save_settings(engine, user['id'], body)
    return {'ok': True}


MEDIA_DIR.mkdir(parents=True, exist_ok=True)
app.mount('/api/media', StaticFiles(directory=MEDIA_DIR), name='recipe-media')
DEMO_DIR.mkdir(parents=True, exist_ok=True)
app.mount('/api/demo', StaticFiles(directory=DEMO_DIR), name='demo-media')
dist = ROOT / 'frontend' / 'dist'
if dist.exists():
    app.mount('/', StaticFiles(directory=dist, html=True), name='frontend')
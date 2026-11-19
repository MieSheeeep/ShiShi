"""食拾接口：账号鉴权与按用户隔离的食谱管理。

所有 /api 业务接口都需要 ``Authorization: Bearer <token>``；账号与登录相关接口除外。
接口约定见 docs/api.md。
"""
import os
from pathlib import Path

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
import httpx
from sqlalchemy import create_engine, event, text

from backend import ai_recipe, auth, deploy_guard, douguo_search, fridge, meal_plan, recipe_store as store
from backend.core import canonical_url, merge_ingredients, normalize, pantry_shortfall, quantity
from backend.crawler import fetch_recipe
from backend.media import MEDIA_DIR, download_recipe_images, save_upload
from backend.recipe_schema import Recipe, draft_v2
from backend.source_urls import import_url

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
DEMO_DIR = Path(__file__).resolve().parent / 'demo_images'
DATA.mkdir(exist_ok=True)
engine = create_engine(os.getenv('SHISHI_DATABASE_URL', f'sqlite:///{DATA / "shishi.db"}'), connect_args={'check_same_thread': False})


@event.listens_for(engine, 'connect')
def configure_sqlite(dbapi_connection, _connection_record):
    deploy_guard.configure_sqlite_connection(dbapi_connection)


store.initialize(engine)
app = FastAPI(title='食拾 · 个人食谱管理', description='账号登录后管理自己的食谱、标签、常备食材与采购清单。')


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=6, max_length=128)
    invite_code: str = Field(default='', max_length=128)
class Link(BaseModel):
    url: str = Field(min_length=1, max_length=20000)
class ImportSearch(BaseModel):
    keyword: str = Field(min_length=1, max_length=30)
    index: int = 0
class AIPrompt(BaseModel):
    prompt: str = Field(min_length=2, max_length=300)
class AiConfig(BaseModel):
    base: str = Field(default='', max_length=300)
    model: str = Field(default='', max_length=100)
    key: str = Field(default='', max_length=400)
class XhsCookie(BaseModel):
    cookie: str = Field(default='', max_length=4000)
class PasswordChange(BaseModel):
    old_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=6, max_length=128)
class Secret(BaseModel):
    password: str = Field(min_length=1, max_length=128)
class PantryItem(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    amount: str = Field(default='', max_length=100)
    unit: str = Field(default='', max_length=10)
class Match(BaseModel):
    ingredients: list[PantryItem] = []
    staples: list[PantryItem] = []
    @field_validator('ingredients', 'staples', mode='before')
    @classmethod
    def legacy_names(cls, value):
        if not value:
            return []
        return [{'name': item} if isinstance(item, str) else item for item in value]
class Selection(BaseModel):
    ids: list[int] = Field(min_length=1)
class Shopping(BaseModel):
    items: list[dict]
class MealPlanBody(BaseModel):
    week: str = Field(min_length=10, max_length=10)
    days: list[dict]
class MealPlanGenerate(BaseModel):
    week: str = Field(min_length=10, max_length=10)
    preferences: list[str] = []
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


fridge.install(app, engine, current_user)


@app.get('/api/health')
def health():
    """健康检查：确认应用进程与 SQLite 数据库连接正常。"""
    with engine.connect() as db:
        db.execute(text('SELECT 1')).scalar()
    return {'status': 'ok', 'journal_mode': deploy_guard.sqlite_journal_mode()}


@app.get('/api/auth/policy')
def auth_policy():
    """返回当前站点的注册策略（是否开放注册、是否需要邀请码）。"""
    return deploy_guard.register_policy()


@app.post('/api/auth/register')
def register(body: Credentials):
    """注册账号并直接返回登录令牌，新账号会得到默认分组与演示食谱。"""
    try:
        deploy_guard.check_registration(body.invite_code)
        user = auth.create_user(engine, body.username, body.password)
    except PermissionError as error:
        raise HTTPException(403, str(error))
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


@app.patch('/api/auth/password')
def change_password(body: PasswordChange, authorization: str = Header(default=''), user: dict = Depends(current_user)):
    """校验旧密码后更新密码，并让该账号的其他会话全部失效。"""
    if not auth.authenticate(engine, user['username'], body.old_password):
        raise HTTPException(422, '当前密码不正确')
    try:
        auth.set_password(engine, user['id'], body.new_password)
    except ValueError as error:
        raise HTTPException(422, str(error))
    auth.revoke_user_tokens(engine, user['id'], keep=bearer_token(authorization))
    return {'ok': True}


@app.delete('/api/auth/account')
def delete_account(body: Secret, user: dict = Depends(current_user)):
    """确认密码后永久删除账号及其全部数据，不可恢复。"""
    if not auth.authenticate(engine, user['username'], body.password):
        raise HTTPException(422, '密码不正确，账号未删除')
    store.purge_user(engine, user['id'])
    return {'ok': True}


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
        draft = fetch_recipe(original, xhs_cookie=store.read_xhs_cookie(engine, user['id']))
        if any(recipe['source']['url'] == draft['source'] for recipe in store.list_recipes(engine, user['id'])):
            raise HTTPException(409, '这篇笔记已经在你的食谱库中了')
        return draft_v2(download_recipe_images(draft))
    except ValueError as error:
        raise HTTPException(422, str(error))


@app.post('/api/imports/search')
def search_recipe(body: ImportSearch, user: dict = Depends(current_user)):
    """按菜名搜索豆果，直接返回第 index 个未收藏的候选食谱。"""
    keyword = body.keyword.strip()
    if not keyword:
        raise HTTPException(422, '请输入菜名')
    try:
        candidates = douguo_search.search_candidates(keyword)
    except ValueError as error:
        raise HTTPException(422, str(error))
    owned = {recipe['source']['url'] for recipe in store.list_recipes(engine, user['id'])}
    index = max(body.index, 0)
    while index < len(candidates) and candidates[index]['url'] in owned:
        index += 1
    if index >= len(candidates):
        if body.index == 0:
            raise HTTPException(409, '这些搜索结果都已经在你的食谱库中了')
        raise HTTPException(409, '没有更多搜索结果了')
    try:
        draft = draft_v2(download_recipe_images(fetch_recipe(candidates[index]['url'])))
    except ValueError as error:
        raise HTTPException(422, str(error))
    return {'draft': draft, 'meta': {
        'keyword': keyword,
        'index': index,
        'total': len(candidates),
        'title': candidates[index]['title'],
        'cover': candidates[index]['cover'],
    }}


@app.post('/api/imports/generate')
def generate_recipe(body: AIPrompt, user: dict = Depends(current_user)):
    """按一句话要求让 AI 写一份食谱草稿，仍需用户在编辑器里核对后保存。"""
    catalogue = store.catalogue(engine, user['id'])
    groups = {group['id']: group['name'] for group in catalogue['groups']}
    choices = [{'id': tag['id'], 'name': tag['name'], 'group': groups.get(tag['group_id'], '')} for tag in catalogue['tags']]
    ai_tag = next((tag for tag in choices if tag['name'] == store.AI_TAG), None)
    try:
        raw = ai_recipe.generate(body.prompt.strip(), ai_settings(user['id']), [tag['name'] for tag in choices if tag is not ai_tag])
    except ValueError as error:
        raise HTTPException(422, str(error))
    raw.pop('source', None)
    raw['author'] = 'AI 生成草稿'
    names = [str(name).strip() for name in (raw.get('tags') or [])]
    picked = [tag for tag in choices if tag is not ai_tag and tag['name'] in names]
    raw['tags'] = ([ai_tag] if ai_tag else []) + picked
    if not raw.get('cover'):
        raw['cover'] = ai_cover(raw.get('name', ''))
    return draft_v2(raw, kind='ai_generated', platform='manual')


def ai_cover(name):
    """按菜名在豆果找一张成品图并保存到本地，失败时返回空串由前端回退图标。"""
    try:
        candidates = douguo_search.search_candidates(name)
    except (ValueError, httpx.HTTPError):
        return ''
    if not candidates or not candidates[0].get('cover'):
        return ''
    draft = {'source_images': [candidates[0]['cover']], 'step_images': []}
    try:
        download_recipe_images(draft)
    except (ValueError, OSError):
        return ''
    return (draft.get('source_images') or [''])[0]


def ai_settings(user_id):
    """合并账号内保存的配置与环境变量，账号配置优先。"""
    stored = store.read_ai_settings(engine, user_id)
    env = ai_recipe.config()
    return {
        'base': stored['base'] or env['base'],
        'model': stored['model'] or env['model'],
        'key': stored['key'] or env['key'],
        'own': bool(stored['key']),
    }


def ai_status(settings):
    key = settings['key']
    return {
        'configured': bool(key),
        'base': settings['base'],
        'model': settings['model'],
        'source': 'account' if settings['own'] else ('environment' if key else ''),
        'key_hint': ('••••' + key[-4:]) if key else '',
    }


@app.get('/api/ai/settings')
def get_ai_settings(user: dict = Depends(current_user)):
    return ai_status(ai_settings(user['id']))


@app.put('/api/ai/settings')
def save_ai_settings(body: AiConfig, user: dict = Depends(current_user)):
    """保存本账号的 AI 配置；key 留空表示沿用已保存的 key。"""
    try:
        base = deploy_guard.validate_ai_base_url(body.base)
    except ValueError as error:
        raise HTTPException(422, str(error))
    stored = store.read_ai_settings(engine, user['id'])
    store.save_ai_settings(engine, user['id'], {
        'base': base,
        'model': body.model.strip(),
        'key': body.key.strip() or stored['key'],
    })
    return ai_status(ai_settings(user['id']))


def xhs_status(user_id):
    """合并账号内保存的小红书登录态与环境变量，账号配置优先。"""
    saved = store.read_xhs_cookie(engine, user_id)
    env = os.environ.get('XHS_COOKIE', '').strip()
    cookie = saved or env
    return {
        'configured': bool(cookie),
        'source': 'account' if saved else ('environment' if env else ''),
        'cookie_hint': ('••••' + cookie[-6:]) if cookie else '',
    }


@app.get('/api/xhs/settings')
def get_xhs_settings(user: dict = Depends(current_user)):
    return xhs_status(user['id'])


@app.put('/api/xhs/settings')
def save_xhs_settings(body: XhsCookie, user: dict = Depends(current_user)):
    """保存或清空小红书登录态；提交空串表示退出登录。"""
    cookie = body.cookie.strip()
    if cookie and not any(name in cookie for name in ('web_session', 'a1=')):
        raise HTTPException(422, '这串内容不像小红书 Cookie，请复制完整的 Cookie 后再保存')
    store.save_xhs_cookie(engine, user['id'], cookie)
    return xhs_status(user['id'])


@app.post('/api/ai/verify')
def verify_ai(body: AiConfig, user: dict = Depends(current_user)):
    """用一次极短的请求验证地址与 key，可校验尚未保存的内容。"""
    stored = store.read_ai_settings(engine, user['id'])
    env = ai_recipe.config()
    settings = {
        'base': body.base.strip() or stored['base'] or env['base'],
        'model': body.model.strip() or stored['model'] or env['model'],
        'key': body.key.strip() or stored['key'] or env['key'],
    }
    try:
        ai_recipe.verify(settings)
    except ValueError as error:
        raise HTTPException(422, str(error))
    return {'ok': True}


@app.post('/api/ai/suggest')
def suggest_dishes(body: Match, user: dict = Depends(current_user)):
    """按冰箱现有食材给出候选菜名与理由，满意后再单独生成食谱。"""
    try:
        dishes = ai_recipe.suggest(ai_settings(user['id']), [item.name for item in body.ingredients], [item.name for item in body.staples])
    except ValueError as error:
        raise HTTPException(422, str(error))
    return {'dishes': dishes}


@app.post('/api/match')
def match(body: Match, user: dict = Depends(current_user)):
    have = {normalize(item.name) for item in body.ingredients + body.staples}
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
    settings = store.read_settings(engine, user['id'])
    pantry = {}
    for key in ('ingredients', 'staples'):
        for item in settings.get(key, []):
            raw = f"{item.get('amount', '')}{item.get('unit', '')}".strip()
            pantry.setdefault(normalize(item['name']), []).append(quantity(raw) if raw else None)
    items = merge_ingredients(rows)
    for item in items:
        entries = pantry.get(item['name'])
        if not entries:
            continue
        short = pantry_shortfall(item['amount'], entries)
        if short is None:
            item['pantry'] = True
        else:
            item['amount'] = short
            item['pantryNote'] = f'冰箱里的用量已扣除，这里只买差额（还差 {short}）'
    store.save_list(engine, user['id'], items)
    return items


@app.get('/api/shopping')
def shopping(user: dict = Depends(current_user)):
    return store.read_list(engine, user['id'])


@app.put('/api/shopping')
def set_shopping(body: Shopping, user: dict = Depends(current_user)):
    store.save_list(engine, user['id'], body.items)
    return {'ok': True}


@app.get('/api/meal-plan')
def get_meal_plan(week: str = Query(min_length=10, max_length=10), user: dict = Depends(current_user)):
    return store.read_plan(engine, user['id'], week) or meal_plan.empty_plan(week)


@app.put('/api/meal-plan')
def set_meal_plan(body: MealPlanBody, user: dict = Depends(current_user)):
    store.save_plan(engine, user['id'], body.week, {'week': body.week, 'days': body.days})
    return {'ok': True}


@app.post('/api/meal-plan/generate')
def generate_meal_plan(body: MealPlanGenerate, user: dict = Depends(current_user)):
    recipes = store.list_recipes(engine, user['id'])
    settings = store.read_settings(engine, user['id'])
    plan = meal_plan.generate_plan(body.week, recipes, settings)
    store.save_plan(engine, user['id'], body.week, plan)
    return plan


@app.post('/api/meal-plan/shopping')
def meal_plan_shopping(body: Selection, user: dict = Depends(current_user)):
    recipes = [recipe for recipe in store.list_recipes(engine, user['id']) if recipe['id'] in body.ids]
    if len(recipes) != len(set(body.ids)):
        raise HTTPException(404, '部分食谱不存在，请重新选择')
    settings = store.read_settings(engine, user['id'])
    items = meal_plan.build_shopping_items(recipes, settings)
    store.save_list(engine, user['id'], items)
    return items


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
dist = ROOT / '_runtime' / 'frontend-dist'
if dist.exists():
    app.mount('/', StaticFiles(directory=dist, html=True), name='frontend')

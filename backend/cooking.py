"""Account-scoped cooking journal API, installed independently of recipes."""
from copy import deepcopy
import json
import re
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import Depends, HTTPException, Path, Query
from sqlalchemy import text

from backend import cooking_schema as schema, cooking_store as store, media

SessionId = Annotated[int, Path(ge=1, le=2**63 - 1)]


def record_upload(engine, user_id, url):
    with engine.begin() as db:
        db.execute(text('INSERT OR IGNORE INTO cooking_uploads(user_id,url) VALUES(:user,:url)'),
                   {'user': user_id, 'url': url})


def new_dish(recipe_id, snapshot, key):
    return {'id': str(uuid4()), 'dish_key': key, 'recipe_id': recipe_id,
            'snapshot': snapshot, 'outcome': 'pending', 'note': '', 'photos': [], 'completed_steps': []}


def check_version(session, version):
    if session['version'] != version:
        raise HTTPException(409, '记录已更新，请刷新后重试；本次输入尚未保存')


def install(app, engine, current_user):
    store.initialize(engine)

    @app.post('/api/cooking-sessions')
    def create(body: schema.Create, user: dict = Depends(current_user)):
        with engine.begin() as db:
            db.exec_driver_sql('BEGIN IMMEDIATE')
            previous = db.execute(text('SELECT body FROM cooking_sessions WHERE user_id=:user AND client_id=:client'),
                                  {'user': user['id'], 'client': body.client_id}).first()
            if previous:
                return json.loads(previous.body)
            dishes = []
            for rid in body.recipe_ids:
                row = db.execute(text('SELECT body FROM recipes WHERE id=:id AND user_id=:user'),
                                 {'id': rid, 'user': user['id']}).first()
                if row is None:
                    raise HTTPException(404, '食谱不存在')
                snapshot = json.loads(row.body)
                snapshot['cover'] = snapshot.get('cover') or next(iter(snapshot.get('images', [])), '')
                key = store.recipe_instance(db, user['id'], rid)
                dishes.append(new_dish(rid, snapshot, key))
            if body.manual_name:
                if body.dish_key:
                    existing = next((d for s in reversed(store.all_sessions(db, user['id']))
                                     for d in s['dishes'] if d['dish_key'] == body.dish_key), None)
                    if existing is None:
                        raise HTTPException(404, '菜品不存在')
                    dishes.append(new_dish(existing['recipe_id'], deepcopy(existing['snapshot']), body.dish_key))
                else:
                    dishes.append(new_dish(None, {'name': body.manual_name.strip(), 'cover': '', 'emoji': '🍳',
                                                  'ingredients': [], 'steps': [], 'notes': ''}, f'manual:{uuid4()}'))
            number = db.execute(text('SELECT COALESCE(MAX(number),0)+1 FROM cooking_sessions WHERE user_id=:user'),
                                {'user': user['id']}).scalar_one()
            moment = store.now()
            session = {'number': number, 'client_id': body.client_id, 'version': 1, 'state': 'in_progress',
                       'cooked_on': body.cooked_on or schema.shanghai_today().isoformat(), 'meal_slot': body.meal_slot or '',
                       'title': '', 'note': '',
                       'started_at': moment, 'completed_at': None, 'updated_at': moment, 'dishes': dishes}
            result = db.execute(text('INSERT INTO cooking_sessions(user_id,number,client_id,version,state,cooked_on,'
                'started_at,completed_at,updated_at,body) VALUES(:user,:number,:client_id,:version,:state,:cooked_on,'
                ':started_at,:completed_at,:updated_at,:body)'), {**session, 'user': user['id'], 'body': '{}'})
            session['id'] = result.lastrowid
            store.save(db, user['id'], session)
            return session

    @app.get('/api/cooking-sessions')
    def listing(state: Literal['in_progress', 'completed', 'withdrawn'] | None = None,
                dish_key: str | None = None, month: str | None = None,
                page: int = Query(default=1, ge=1), page_size: int = Query(default=12, ge=1, le=50),
                user: dict = Depends(current_user)):
        if month is not None:
            if not re.fullmatch(r'\d{4}-(?:0[1-9]|1[0-2])', month) or month.startswith('0000'):
                raise HTTPException(422, '月份格式应为 YYYY-MM')
        with engine.connect() as db:
            items = [s for s in store.all_sessions(db, user['id'])
                     if (s['state'] == state if state else s['state'] != 'withdrawn')
                     and (not month or s['cooked_on'].startswith(month))
                     and (not dish_key or any(d['dish_key'] == dish_key for d in s['dishes']))]
        items.sort(key=lambda s: (s['cooked_on'], s['id']), reverse=True)
        return {'items': items[(page - 1) * page_size:page * page_size], 'total': len(items),
                'page': page, 'page_size': page_size}

    @app.get('/api/cooking-sessions/{sid}')
    def detail(sid: SessionId, user: dict = Depends(current_user)):
        with engine.connect() as db:
            return store.get(db, user['id'], sid)

    @app.patch('/api/cooking-sessions/{sid}')
    def patch(sid: SessionId, body: schema.Patch, user: dict = Depends(current_user)):
        with engine.begin() as db:
            db.exec_driver_sql('BEGIN IMMEDIATE')
            session = store.get(db, user['id'], sid)
            check_version(session, body.version)
            if session['state'] == 'withdrawn':
                raise HTTPException(409, '已撤回的记录不能修改')
            changes = body.model_dump(exclude_unset=True)
            edits = changes.pop('dishes', [])
            changes.pop('version')
            known = {d['id']: d for d in session['dishes']}
            ids = [d['id'] for d in edits]
            if len(set(ids)) != len(ids) or any(i not in known for i in ids):
                raise HTTPException(422, '菜品编号重复或不存在')
            for edit in edits:
                dish = known[edit.pop('id')]
                if 'completed_steps' in edit:
                    steps = edit['completed_steps']
                    allowed = {s['id'] for s in dish['snapshot']['steps']}
                    if len(set(steps)) != len(steps) or not set(steps).issubset(allowed):
                        raise HTTPException(422, '步骤重复或不存在')
                for photo in edit.get('photos', []):
                    if not re.fullmatch(r'/api/media/[a-f0-9]{64}\.(?:jpg|png|webp)', photo):
                        raise HTTPException(422, '成品照片必须是本人上传的本地图片')
                    owned = db.execute(text('SELECT 1 FROM cooking_uploads WHERE user_id=:user AND url=:url'),
                                       {'user': user['id'], 'url': photo}).first()
                    if not owned or not (media.MEDIA_DIR / photo.rsplit('/', 1)[-1]).is_file():
                        raise HTTPException(422, '请重新上传这张成品照片')
                dish.update(edit)
            session.update(changes)
            if session['state'] == 'completed':
                store.confirmed(session)
            session.update(version=session['version'] + 1, updated_at=store.now())
            store.save(db, user['id'], session)
            return session

    def transition(sid, body, user, target):
        with engine.begin() as db:
            db.exec_driver_sql('BEGIN IMMEDIATE')
            session = store.get(db, user['id'], sid)
            if session['state'] == target:
                return session
            if session['state'] == 'withdrawn':
                raise HTTPException(409, '已撤回的记录不能重新完成')
            check_version(session, body.version)
            if target == 'completed':
                store.confirmed(session)
                session['completed_at'] = store.now()
            session.update(state=target, version=session['version'] + 1, updated_at=store.now())
            store.save(db, user['id'], session)
            return session

    @app.post('/api/cooking-sessions/{sid}/complete')
    def complete(sid: SessionId, body: schema.Version, user: dict = Depends(current_user)):
        return transition(sid, body, user, 'completed')

    @app.post('/api/cooking-sessions/{sid}/withdraw')
    def withdraw(sid: SessionId, body: schema.Version, user: dict = Depends(current_user)):
        return transition(sid, body, user, 'withdrawn')

    @app.get('/api/cooking-summary')
    def summary(user: dict = Depends(current_user)):
        with engine.connect() as db:
            return store.summary(db, user['id'])

    @app.put('/api/cooking-dishes')
    def mark(body: schema.Mark, user: dict = Depends(current_user)):
        with engine.begin() as db:
            db.exec_driver_sql('BEGIN IMMEDIATE')
            if not any(d['dish_key'] == body.dish_key and d['outcome'] in ('success', 'practice')
                       for s in store.all_sessions(db, user['id']) if s['state'] == 'completed' for d in s['dishes']):
                raise HTTPException(404, '菜品不存在或尚无有效完成记录')
            db.execute(text('INSERT INTO cooking_dishes(user_id,dish_key,status) VALUES(:user,:key,:status) '
                            'ON CONFLICT(user_id,dish_key) DO UPDATE SET status=excluded.status'),
                       {'user': user['id'], 'key': body.dish_key, 'status': body.status})
            return body.model_dump()

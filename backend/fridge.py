"""Account-scoped inventory, with a compatible view for pantry consumers."""
import json
from typing import Literal
from uuid import uuid4

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text

from backend.core import normalize


class Food(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    amount: str = Field(default='', max_length=100)
    unit: str = Field(default='', max_length=10)
    kind: Literal['食材', '调料'] = '食材'
    category_id: str = Field(min_length=1, max_length=80)
    location: Literal['冷藏', '冷冻', '常温'] = '冷藏'
    status: Literal['active', 'used'] = 'active'
    notes: str = Field(default='', max_length=1000)

    @field_validator('name')
    @classmethod
    def clean_name(cls, value):
        if not value.strip():
            raise ValueError('食品名称不能为空')
        return normalize(value.strip())


class Category(BaseModel):
    name: str = Field(min_length=1, max_length=40)

    @field_validator('name')
    @classmethod
    def clean_name(cls, value):
        if not value.strip():
            raise ValueError('分类名称不能为空')
        return value.strip()


def read_document(db, key):
    row = db.execute(text('SELECT body FROM settings WHERE key=:key'), {'key': key}).first()
    return json.loads(row.body) if row else None


def write_document(db, key, body):
    db.execute(text('INSERT INTO settings(key,body) VALUES(:key,:body) '
                    'ON CONFLICT(key) DO UPDATE SET body=excluded.body'),
               {'key': key, 'body': json.dumps(body, ensure_ascii=False)})


def new_state():
    return {'schema_version': 2, 'categories': [
        {'id': uuid4().hex, 'name': name}
        for name in ('蔬菜', '水果', '肉禽', '水产', '蛋奶', '主食', '调料', '其他')
    ], 'items': []}


def legacy_items(body):
    for key, kind in (('ingredients', '食材'), ('staples', '调料')):
        for item in body.get(key, []) or []:
            item = {'name': item} if isinstance(item, str) else item
            if item.get('name', '').strip():
                yield {**item, 'name': normalize(item['name'].strip()), 'kind': kind}


def new_food(data, item):
    category = next((c for c in data['categories'] if c['name'] == ('调料' if item['kind'] == '调料' else '其他')), data['categories'][-1])
    return {'id': uuid4().hex, 'name': item['name'], 'amount': item.get('amount', ''),
            'unit': item.get('unit', ''), 'kind': item['kind'], 'category_id': category['id'],
            'location': '常温' if item['kind'] == '调料' else '冷藏', 'status': 'active', 'notes': ''}


def state(engine, user_id, change=None):
    """Serialize inventory changes; legacy pantry remains available for rollback."""
    with engine.begin() as db:
        db.exec_driver_sql('BEGIN IMMEDIATE')
        return change_state(db, user_id, change)


def change_state(db, user_id, change=None):
    """Read/migrate/write using the caller's already locked transaction."""
    key = f'{user_id}:fridge'
    data = read_document(db, key)
    if data is None or data.get('schema_version') == 1:
        old = read_document(db, f'{user_id}:pantry') or {'ingredients': [], 'staples': ['盐', '油']}
        if data is not None:
            write_document(db, f'{user_id}:fridge-pre-v2', data)
        data = data or new_state()
        for item in data['items']:
            item.setdefault('amount', item.get('quantity', ''))
            item.setdefault('unit', '')
            item.setdefault('kind', '食材')
        unmatched = list(data['items'])
        for item in legacy_items(old):
            existing = next((i for i in unmatched if normalize(i['name']) == item['name']), None)
            if existing is None:
                data['items'].append(new_food(data, item))
            else:
                unmatched.remove(existing)
                if existing['status'] == 'active' and not existing['amount']:
                    existing.update(amount=item.get('amount', ''), unit=item.get('unit', ''), kind=item['kind'])
        data['schema_version'] = 2
    if data.get('schema_version') != 2:
        raise HTTPException(422, '不支持的库存数据版本，请使用对应版本程序')
    result = change(data) if change else data
    write_document(db, key, data)
    return result


def pantry_view(data):
    return {key: [{'name': i['name'], 'amount': i['amount'], 'unit': i['unit']}
                  for i in data['items'] if i['status'] == 'active' and i['kind'] == kind]
            for key, kind in (('ingredients', '食材'), ('staples', '调料'))}


def replace_pantry(data, body):
    """Legacy clients can edit active stock without erasing metadata/used history."""
    active = [i for i in data['items'] if i['status'] == 'active']
    used = [i for i in data['items'] if i['status'] == 'used']
    result = []
    for incoming in legacy_items(body):
        existing = next((i for i in active if normalize(i['name']) == incoming['name'] and i['kind'] == incoming['kind']), None)
        if existing is not None:
            active.remove(existing)
            existing.update(amount=incoming.get('amount', ''), unit=incoming.get('unit', ''))
            result.append(existing)
        else:
            result.append(new_food(data, incoming))
    data['items'] = result + used


def find(rows, item_id):
    item = next((i for i in rows if i['id'] == item_id), None)
    if item is None:
        raise HTTPException(404, '记录不存在')
    return item


def install(app, engine, current_user):
    @app.get('/api/fridge')
    def read(user: dict = Depends(current_user)):
        return state(engine, user['id'])

    @app.post('/api/fridge/items')
    def add(body: Food, user: dict = Depends(current_user)):
        def change(data):
            if not any(c['id'] == body.category_id for c in data['categories']):
                raise HTTPException(422, '请选择有效分类')
            if len(data['items']) >= 1000:
                raise HTTPException(422, '最多保留 1000 条食品记录，请整理已用完的记录')
            item = dict(body.model_dump(), id=uuid4().hex)
            data['items'].insert(0, item)
            return item
        return state(engine, user['id'], change)

    @app.put('/api/fridge/items/{item_id}')
    def update(item_id: str, body: Food, user: dict = Depends(current_user)):
        def change(data):
            item = find(data['items'], item_id)
            if not any(c['id'] == body.category_id for c in data['categories']):
                raise HTTPException(422, '请选择有效分类')
            item.update(body.model_dump())
            return item
        return state(engine, user['id'], change)

    @app.delete('/api/fridge/items/{item_id}')
    def remove(item_id: str, user: dict = Depends(current_user)):
        def change(data):
            data['items'].remove(find(data['items'], item_id))
            return {'ok': True}
        return state(engine, user['id'], change)

    @app.post('/api/fridge/categories')
    def add_category(body: Category, user: dict = Depends(current_user)):
        def change(data):
            if any(c['name'] == body.name for c in data['categories']):
                raise HTTPException(409, '已有同名分类')
            if len(data['categories']) >= 60:
                raise HTTPException(422, '最多创建 60 个分类')
            category = {'id': uuid4().hex, 'name': body.name}
            data['categories'].append(category)
            return category
        return state(engine, user['id'], change)

    @app.patch('/api/fridge/categories/{category_id}')
    def rename_category(category_id: str, body: Category, user: dict = Depends(current_user)):
        def change(data):
            category = find(data['categories'], category_id)
            if any(c['name'] == body.name and c['id'] != category_id for c in data['categories']):
                raise HTTPException(409, '已有同名分类')
            category['name'] = body.name
            return category
        return state(engine, user['id'], change)

    @app.delete('/api/fridge/categories/{category_id}')
    def remove_category(category_id: str, user: dict = Depends(current_user)):
        def change(data):
            category = find(data['categories'], category_id)
            if any(i['category_id'] == category_id for i in data['items']):
                raise HTTPException(422, '请先移动或删除分类中的食品，包含已用完的记录')
            if len(data['categories']) == 1:
                raise HTTPException(422, '请至少保留一个分类')
            data['categories'].remove(category)
            return {'ok': True}
        return state(engine, user['id'], change)

import importlib
import json
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('SHISHI_DATABASE_URL', 'sqlite:///' + str(tmp_path / 'integration.db'))
    import backend.main as main
    main = importlib.reload(main)
    with TestClient(main.app) as c:
        auth = c.post('/api/auth/register', json={'username': 'fridge-user', 'password': 'secret123'}).json()
        c.headers['Authorization'] = 'Bearer ' + auth['token']
        yield c


def migrate(client):
    assert client.put('/api/settings', json={
        'ingredients': [{'name': '西红柿', 'amount': '300', 'unit': '克'}],
        'staples': [{'name': '盐', 'amount': '', 'unit': ''}],
    }).status_code == 200
    response = client.get('/api/fridge')
    assert response.status_code == 200
    return response.json()


def test_migration_keeps_quantity_stable_ids_and_shared_settings(client):
    state = migrate(client)
    food = next(i for i in state['items'] if i['name'] == '番茄')
    assert (food['amount'], food['unit'], food['kind']) == ('300', '克', '食材')
    assert client.get('/api/fridge').json() == state
    settings = client.get('/api/settings').json()
    assert settings['ingredients'][0]['amount'] == '300'
    assert settings['ingredients'][0]['name'] == '番茄'


def test_used_food_does_not_reduce_shopping_and_restore_recovers_quantity(client):
    state = migrate(client)
    food = next(i for i in state['items'] if i['name'] == '番茄')
    recipe = client.post('/api/recipes', json={'name': '库存测试菜', 'source': '',
        'ingredients': [{'name': '番茄', 'amount': '500克'}], 'steps': ['煮熟']}).json()
    url = '/api/fridge/items/' + food['id']
    assert client.post('/api/shopping', json={'ids': [recipe['id']]}).json()[0]['amount'] == '200克'
    assert client.put(url, json={**food, 'status': 'used'}).status_code == 200
    assert client.get('/api/settings').json()['ingredients'] == []
    assert client.post('/api/shopping', json={'ids': [recipe['id']]}).json()[0]['amount'] == '500克'
    assert client.put(url, json=food).status_code == 200
    assert client.post('/api/shopping', json={'ids': [recipe['id']]}).json()[0]['amount'] == '200克'


def test_legacy_settings_write_preserves_metadata_and_used_records(client):
    state = migrate(client)
    food = next(i for i in state['items'] if i['name'] == '番茄')
    assert client.put('/api/fridge/items/' + food['id'], json={**food, 'location': '冷冻', 'notes': '保留备注'}).status_code == 200
    old = client.get('/api/settings').json()
    old['ingredients'][0]['amount'] = '200'
    assert client.put('/api/settings', json=old).status_code == 200
    updated = next(i for i in client.get('/api/fridge').json()['items'] if i['id'] == food['id'])
    assert (updated['location'], updated['notes'], updated['amount']) == ('冷冻', '保留备注', '200')
    assert client.put('/api/fridge/items/' + food['id'], json={**updated, 'status': 'used'}).status_code == 200
    assert client.put('/api/settings', json=client.get('/api/settings').json()).status_code == 200
    assert any(i['id'] == food['id'] and i['status'] == 'used' for i in client.get('/api/fridge').json()['items'])


def test_categories_validation_and_account_isolation(client):
    state = migrate(client)
    category = client.post('/api/fridge/categories', json={'name': '烘焙'}).json()
    assert client.post('/api/fridge/categories', json={'name': '烘焙'}).status_code == 409
    food = {'name': '黄油', 'amount': '半', 'unit': '盒', 'kind': '调料', 'category_id': category['id'], 'location': '冷藏'}
    saved = client.post('/api/fridge/items', json=food).json()
    assert client.delete('/api/fridge/categories/' + category['id']).status_code == 422
    assert client.post('/api/fridge/items', json={**food, 'name': '   '}).status_code == 422
    assert client.post('/api/fridge/items', json={**food, 'category_id': 'unknown'}).status_code == 422
    auth = client.post('/api/auth/register', json={'username': 'another-user', 'password': 'secret123'}).json()
    client.headers['Authorization'] = 'Bearer ' + auth['token']
    assert client.put('/api/fridge/items/' + saved['id'], json=food).status_code == 404
    assert client.delete('/api/fridge/categories/' + category['id']).status_code == 404
    assert not any(i['name'] == '番茄' for i in client.get('/api/fridge').json()['items'])
    assert client.get('/api/ai/settings').status_code == 200
    assert client.get('/api/meal-plan?week=2026-11-16').status_code == 200


def test_fridge_requires_login(client):
    client.headers.clear()
    assert client.get('/api/fridge').status_code == 401


def test_old_enhancement_inventory_keeps_free_text_and_used_history(client):
    migrate(client)
    import backend.main as main
    uid = client.get('/api/auth/me').json()['id']
    old = {'schema_version': 1, 'categories': [{'id': 'old-category', 'name': '其他'}], 'items': [
        {'id': 'old-food', 'name': '土豆', 'quantity': '半袋', 'category_id': 'old-category',
         'location': '常温', 'status': 'used', 'notes': '旧分支备注'}]}
    with main.engine.begin() as db:
        db.execute(text('UPDATE settings SET body=:body WHERE key=:key'),
                   {'body': json.dumps(old), 'key': f'{uid}:fridge'})
    state = client.get('/api/fridge').json()
    item = next(i for i in state['items'] if i['id'] == 'old-food')
    assert item['amount'] == '半袋' and item['status'] == 'used'
    assert item['notes'] == '旧分支备注' and item['category_id'] == 'old-category'
    assert not any(i['name'] == '土豆' for i in client.get('/api/settings').json()['ingredients'])
    assert client.get('/api/fridge').json() == state
    with main.engine.connect() as db:
        backup = db.execute(text('SELECT body FROM settings WHERE key=:key'), {'key': f'{uid}:fridge-pre-v2'}).scalar_one()
    assert json.loads(backup) == old


def test_category_rename_and_deleted_items_stay_consistent(client):
    state = migrate(client)
    category = client.post('/api/fridge/categories', json={'name': '临时分类'}).json()
    food = {**state['items'][0], 'category_id': category['id']}
    saved = client.post('/api/fridge/items', json=food).json()
    assert client.patch('/api/fridge/categories/' + category['id'], json={'name': '新的分类'}).status_code == 200
    assert client.delete('/api/fridge/items/' + saved['id']).status_code == 200
    assert client.delete('/api/fridge/items/' + saved['id']).status_code == 404
    assert client.delete('/api/fridge/categories/' + category['id']).status_code == 200


def test_old_home_flags_are_compatible_with_current_shopping(client):
    items = [{'name': '鸡蛋', 'amount': '3个', 'at_home': True, 'checked': False, 'sources': []}]
    assert client.put('/api/shopping', json={'items': items}).status_code == 200
    assert client.get('/api/shopping').json()[0]['pantry'] is True


def test_migration_preserves_separate_batches_and_alias_quantities(client):
    rows = [{'name': '西红柿', 'amount': '100', 'unit': '克'},
            {'name': '番茄', 'amount': '2', 'unit': '个'}]
    assert client.put('/api/settings', json={'ingredients': rows, 'staples': []}).status_code == 200
    result = client.get('/api/fridge').json()['items']
    assert [(i['name'], i['amount'], i['unit']) for i in result] == [('番茄', '100', '克'), ('番茄', '2', '个')]
    assert len({i['id'] for i in result}) == 2


def test_legacy_save_that_overlaps_first_inventory_migration_is_not_lost(client, monkeypatch):
    import backend.main as main
    from backend.fridge import state
    uid = client.get('/api/auth/me').json()['id']
    begin = main.engine.begin
    pending = True

    @contextmanager
    def begin_after_migration(*args, **kwargs):
        nonlocal pending
        if pending:
            pending = False
            state(main.engine, uid)
        with begin(*args, **kwargs) as db:
            yield db

    monkeypatch.setattr(main.engine, 'begin', begin_after_migration)
    body = {'ingredients': [{'name': '番茄', 'amount': '200', 'unit': '克'}], 'staples': []}
    assert client.put('/api/settings', json=body).status_code == 200
    assert client.get('/api/settings').json() == body


def test_old_long_food_text_remains_editable_and_matchable(client):
    migrate(client)
    import backend.main as main
    uid = client.get('/api/auth/me').json()['id']
    old = {'schema_version': 1, 'categories': [{'id': 'long-category', 'name': '其他'}], 'items': [
        {'id': 'long-food', 'name': '某' * 70, 'quantity': '余' * 50, 'category_id': 'long-category',
         'location': '常温', 'status': 'active', 'notes': ''}]}
    with main.engine.begin() as db:
        db.execute(text('UPDATE settings SET body=:body WHERE key=:key'), {'body': json.dumps(old), 'key': f'{uid}:fridge'})
    food = next(i for i in client.get('/api/fridge').json()['items'] if i['id'] == 'long-food')
    assert client.post('/api/match', json=client.get('/api/settings').json()).status_code == 200
    assert client.put('/api/fridge/items/long-food', json={**food, 'status': 'used'}).status_code == 200

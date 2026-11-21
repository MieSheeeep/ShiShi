import importlib
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import BytesIO
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import text


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('SHISHI_DATABASE_URL', 'sqlite:///' + str(tmp_path / 'cooking.db'))
    import backend.main as main
    main = importlib.reload(main)
    with TestClient(main.app) as c:
        login = c.post('/api/auth/register', json={'username': 'cooking-user', 'password': 'secret123'}).json()
        c.headers['Authorization'] = 'Bearer ' + login['token']
        yield c


def create(client, **fields):
    response = client.post('/api/cooking-sessions', json={'client_id': str(uuid4()), 'manual_name': '家常菜', **fields})
    assert response.status_code == 200, response.text
    return response.json()


def test_create_idempotent_and_summary(client):
    key = str(uuid4())
    first = create(client, client_id=key)
    assert create(client, client_id=key) == first
    assert first['number'] == 1
    assert client.get('/api/cooking-summary').json()['meals'] == 0


def patch(client, session, **fields):
    return client.patch(f"/api/cooking-sessions/{session['id']}", json={'version': session['version'], **fields})


def finish(client, session, outcome='success'):
    session = patch(client, session, dishes=[{'id': d['id'], 'outcome': outcome} for d in session['dishes']]).json()
    response = client.post(f"/api/cooking-sessions/{session['id']}/complete", json={'version': session['version']})
    assert response.status_code == 200, response.text
    return response.json()


def recipe(client, name='测试菜'):
    response = client.post('/api/recipes', json={'name': name, 'source': '',
        'ingredients': [{'name': '番茄', 'amount': '1个'}], 'steps': ['煮熟', '装盘']})
    assert response.status_code == 200
    return response.json()


def from_recipes(client, ids, **fields):
    response = client.post('/api/cooking-sessions', json={'client_id': str(uuid4()), 'recipe_ids': ids, **fields})
    assert response.status_code == 200, response.text
    return response.json()


def other_account(client):
    original = client.headers['Authorization']
    login = client.post('/api/auth/register', json={'username': 'other-cook', 'password': 'secret123'}).json()
    client.headers['Authorization'] = 'Bearer ' + login['token']
    return original


def test_auth_and_account_isolation(client):
    food = recipe(client)
    session = finish(client, from_recipes(client, [food['id']]))
    key = session['dishes'][0]['dish_key']
    other_account(client)
    url = f"/api/cooking-sessions/{session['id']}"
    assert client.get(url).status_code == 404
    assert client.patch(url, json={'version': 1, 'note': 'x'}).status_code == 404
    for action in ('complete', 'withdraw'):
        assert client.post(url + '/' + action, json={'version': 1}).status_code == 404
    assert client.post('/api/cooking-sessions', json={'client_id': str(uuid4()), 'recipe_ids': [food['id']]}).status_code == 404
    assert client.post('/api/cooking-sessions', json={'client_id': str(uuid4()), 'manual_name': '假冒', 'dish_key': key}).status_code == 404
    assert client.put('/api/cooking-dishes', json={'dish_key': key, 'status': 'signature'}).status_code == 404
    assert client.get('/api/cooking-sessions').json()['total'] == 0
    assert client.get('/api/cooking-summary').json()['meals'] == 0
    client.headers.pop('Authorization')
    assert client.get('/api/cooking-summary').status_code == 401


def test_snapshot_survives_recipe_deletion_and_retry(client):
    source = recipe(client)
    session = from_recipes(client, [source['id']])
    snapshot = session['dishes'][0]['snapshot']
    assert snapshot['ingredients'] == source['ingredients']
    assert snapshot['steps'] == source['steps']
    assert client.delete(f"/api/recipes/{source['id']}").status_code == 200
    retry = client.post('/api/cooking-sessions', json={'client_id': session['client_id'], 'recipe_ids': [source['id']]})
    assert retry.json() == session
    assert client.get(f"/api/cooking-sessions/{session['id']}").json()['dishes'][0]['snapshot'] == snapshot
    assert create(client, dish_key=session['dishes'][0]['dish_key'])['dishes'][0]['snapshot'] == snapshot


@pytest.mark.parametrize('value', ['2025-02-29', '2026-13-01', '2026-2-01', '0000-01-01', '2026-11-21T00:00:00Z', None])
def test_reject_invalid_dates(client, value):
    assert client.post('/api/cooking-sessions', json={'client_id': str(uuid4()), 'manual_name': '菜', 'cooked_on': value}).status_code == 422
    session = create(client)
    assert patch(client, session, cooked_on=value).status_code == 422
    assert client.get(f"/api/cooking-sessions/{session['id']}").json() == session


def test_shanghai_date_and_future(client):
    from backend.cooking_schema import shanghai_today
    tomorrow = (shanghai_today() + timedelta(days=1)).isoformat()
    session = create(client, cooked_on='2024-02-29')
    assert session['cooked_on'] == '2024-02-29'
    assert patch(client, session, cooked_on=tomorrow).status_code == 422
    assert client.post('/api/cooking-sessions', json={'client_id': str(uuid4()), 'manual_name': '菜', 'cooked_on': tomorrow}).status_code == 422


def test_completion_version_and_withdrawal(client):
    session = create(client)
    url = f"/api/cooking-sessions/{session['id']}"
    assert client.post(url + '/complete', json={'version': 1}).status_code == 422
    assert patch(client, session, dishes=[{'id': session['dishes'][0]['id'], 'outcome': 'skipped'}]).status_code == 200
    assert patch(client, session, note='stale').status_code == 409
    session = client.get(url).json()
    assert client.post(url + '/complete', json={'version': session['version']}).status_code == 422
    completed = finish(client, session, 'practice')
    assert client.post(url + '/complete', json={'version': 1}).json() == completed
    assert patch(client, completed, dishes=[{'id': completed['dishes'][0]['id'], 'outcome': 'pending'}]).status_code == 422
    assert patch(client, completed, dishes=[{'id': completed['dishes'][0]['id'], 'outcome': 'skipped'}]).status_code == 422
    edited = patch(client, completed, note='记住盐量', cooked_on='2020-01-01').json()
    assert edited['completed_at'] == completed['completed_at']
    assert client.post(url + '/withdraw', json={'version': 1}).status_code == 409
    withdrawn = client.post(url + '/withdraw', json={'version': edited['version']}).json()
    assert client.post(url + '/withdraw', json={'version': 1}).json() == withdrawn
    assert client.post(url + '/complete', json={'version': withdrawn['version']}).status_code == 409
    assert patch(client, withdrawn, note='不能更改').status_code == 409
    assert client.get('/api/cooking-summary').json()['meals'] == 0
    assert client.get('/api/cooking-sessions').json()['total'] == 0
    assert client.get('/api/cooking-sessions?state=withdrawn').json()['total'] == 1
    assert create(client)['number'] == 2


def test_patch_rejects_unknown_duplicate_and_forged_fields(client):
    session = from_recipes(client, [recipe(client)['id']])
    dish = session['dishes'][0]
    bad_edits = [[{'id': 'missing', 'outcome': 'success'}], [{'id': dish['id']}, {'id': dish['id']}],
                 [{'id': dish['id'], 'snapshot': {'name': '伪造'}}],
                 [{'id': dish['id'], 'completed_steps': ['unknown']}],
                 [{'id': dish['id'], 'completed_steps': [dish['snapshot']['steps'][0]['id']] * 2}],
                 [{'id': dish['id'], 'outcome': 'failed'}], [{'id': dish['id'], 'note': None}]]
    for edits in bad_edits:
        assert patch(client, session, dishes=edits).status_code == 422
    good = patch(client, session, dishes=[{'id': dish['id'], 'completed_steps': [dish['snapshot']['steps'][0]['id']]}]).json()
    assert finish(client, good)['state'] == 'completed'  # unchecked final step is permitted


def upload(client, color='red'):
    body = BytesIO()
    Image.new('RGB', (2, 2), color).save(body, format='PNG')
    response = client.post('/api/media', files={'file': ('photo.png', body.getvalue(), 'image/png')})
    assert response.status_code == 200
    return response.json()['url']


def test_only_own_real_uploaded_media(client):
    session = create(client)
    dish_id = session['dishes'][0]['id']
    original = client.headers['Authorization']
    other_account(client)
    foreign_photo = upload(client, 'blue')
    client.headers['Authorization'] = original
    for photo in ('https://example.com/a.png', '/api/demo/egg.png', '/editorial/example.png',
                  '/api/media/' + 'a' * 64 + '.png', foreign_photo):
        assert patch(client, session, dishes=[{'id': dish_id, 'photos': [photo]}]).status_code == 422
    own = upload(client)
    assert patch(client, session, dishes=[{'id': dish_id, 'photos': [own] * 13}]).status_code == 422
    updated = patch(client, session, dishes=[{'id': dish_id, 'photos': [own]}]).json()
    assert updated['dishes'][0]['photos'] == [own]


def test_achievements_sources_repertoire_and_retraction(client):
    sources = [recipe(client, f'菜{i}') for i in range(3)]
    first = finish(client, from_recipes(client, [sources[0]['id']]), 'practice')
    again = finish(client, from_recipes(client, [sources[0]['id']], cooked_on='2020-01-01'))
    third = finish(client, from_recipes(client, [s['id'] for s in sources]))
    fourth = finish(client, from_recipes(client, [sources[0]['id']]))
    summary = client.get('/api/cooking-summary').json()
    assert (summary['meals'], summary['dishes']) == (4, 3)
    achievements = {a['id']: a for a in summary['achievements']}
    for key, source in [('first-fire', first), ('try-again', again), ('three-dishes', third), ('signature-dish', fourth)]:
        assert achievements[key]['session_id'] == source['id']
        assert achievements[key]['unlocked_at'] == source['completed_at']
    entry = next(d for d in summary['repertoire'] if d['dish_key'] == first['dishes'][0]['dish_key'])
    assert (entry['attempts'], entry['successes']) == (4, 3)
    assert entry['sessions'] == [s['id'] for s in (first, again, third, fourth)]
    assert client.put('/api/cooking-dishes', json={'dish_key': entry['dish_key'], 'status': 'signature'}).status_code == 200
    assert client.post(f"/api/cooking-sessions/{first['id']}/withdraw", json={'version': first['version']}).status_code == 200
    revised = client.get('/api/cooking-summary').json()
    assert not next(a for a in revised['achievements'] if a['id'] == 'try-again')['unlocked']
    assert next(a for a in revised['achievements'] if a['id'] == 'first-fire')['session_id'] == again['id']


def test_level_thresholds_and_manual_mark_does_not_award(client):
    expected = {0: (1, 1), 1: (2, 3), 3: (3, 7), 7: (4, 15), 15: (5, None)}
    first = None
    for count in range(16):
        summary = client.get('/api/cooking-summary').json()
        if count in expected:
            level, next_at = expected[count]
            assert summary['level']['number'] == level
            assert summary['level']['next_at'] == next_at
            assert summary['level']['remaining'] == (next_at - count if next_at else 0)
        if count == 15:
            break
        session = create(client, **({'dish_key': first['dishes'][0]['dish_key']} if first else {}))
        session = finish(client, session, 'practice')
        first = first or session
    key = first['dishes'][0]['dish_key']
    assert client.put('/api/cooking-dishes', json={'dish_key': key, 'status': 'signature'}).status_code == 200
    summary = client.get('/api/cooking-summary').json()
    assert summary['repertoire'][0]['status'] == 'signature'
    assert not next(a for a in summary['achievements'] if a['id'] == 'signature-dish')['unlocked']


def test_list_filters_and_limits(client):
    one = create(client, cooked_on='2024-02-29')
    two = finish(client, create(client, cooked_on='2024-03-01'))
    result = client.get('/api/cooking-sessions?page_size=1').json()
    assert result['total'] == 2 and result['items'][0]['id'] == two['id']
    assert client.get('/api/cooking-sessions?month=2024-02').json()['items'] == [one]
    assert client.get('/api/cooking-sessions', params={'dish_key': one['dishes'][0]['dish_key']}).json()['total'] == 1
    assert client.get('/api/cooking-sessions?state=completed').json()['total'] == 1
    for query in ('page=0', 'page_size=51', 'month=2024-13', 'month=0000-01', 'state=bad'):
        assert client.get('/api/cooking-sessions?' + query).status_code == 422
    assert patch(client, one, title='a' * 81).status_code == 422
    assert patch(client, one, note='a' * 1001).status_code == 422
    assert client.post('/api/cooking-sessions', json={'client_id': 'not-uuid', 'manual_name': '菜'}).status_code == 422
    assert client.post('/api/cooking-sessions', json={'client_id': str(uuid4()), 'manual_name': '菜', 'recipe_ids': [1]}).status_code == 422


def test_account_deletion_cleans_new_tables(client):
    import backend.main as main
    session = finish(client, create(client))
    upload(client)
    assert client.put('/api/cooking-dishes', json={'dish_key': session['dishes'][0]['dish_key'], 'status': 'practice'}).status_code == 200
    user_id = client.get('/api/auth/me').json()['id']
    assert client.request('DELETE', '/api/auth/account', json={'password': 'secret123'}).status_code == 200
    with main.engine.connect() as db:
        for table in ('cooking_sessions', 'cooking_dishes', 'cooking_uploads'):
            assert db.execute(text(f'SELECT COUNT(*) FROM {table} WHERE user_id=:user'), {'user': user_id}).scalar_one() == 0


def test_multi_dish_skipped_not_counted_and_edit_recalculates(client):
    foods = [recipe(client, f'混合菜{i}') for i in range(3)]
    session = from_recipes(client, [r['id'] for r in foods])
    outcomes = ['success', 'practice', 'skipped']
    session = patch(client, session, dishes=[{'id': d['id'], 'outcome': outcome}
                     for d, outcome in zip(session['dishes'], outcomes)]).json()
    session = client.post(f"/api/cooking-sessions/{session['id']}/complete", json={'version': session['version']}).json()
    summary = client.get('/api/cooking-summary').json()
    assert (summary['meals'], summary['dishes']) == (1, 2)
    assert sum(d['attempts'] for d in summary['repertoire']) == 2
    skipped_key = session['dishes'][2]['dish_key']
    assert client.put('/api/cooking-dishes', json={'dish_key': skipped_key, 'status': 'tried'}).status_code == 404
    session = patch(client, session, dishes=[{'id': session['dishes'][2]['id'], 'outcome': 'practice'}]).json()
    summary = client.get('/api/cooking-summary').json()
    assert summary['dishes'] == 3
    assert next(a for a in summary['achievements'] if a['id'] == 'three-dishes')['session_id'] == session['id']


def test_concurrent_creation_serializes_number_and_idempotency(client):
    same = str(uuid4())
    def send(key):
        response = client.post('/api/cooking-sessions', json={'client_id': key, 'manual_name': '并发菜'})
        assert response.status_code == 200, response.text
        return response.json()
    with ThreadPoolExecutor(max_workers=4) as pool:
        sessions = list(pool.map(send, [same, same, str(uuid4()), str(uuid4())]))
    assert sessions[0] == sessions[1]
    assert sorted({s['number'] for s in sessions}) == [1, 2, 3]
    assert client.get('/api/cooking-sessions').json()['total'] == 3

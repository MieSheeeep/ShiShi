import importlib

from fastapi.testclient import TestClient
from sqlalchemy import text


def client_for(tmp_path, monkeypatch):
    monkeypatch.setenv('SHISHI_DATABASE_URL', 'sqlite:///' + str(tmp_path / 'auth.db'))
    import backend.main as module
    module = importlib.reload(module)
    return module, TestClient(module.app)


def register(client, username='alice', password='secret123'):
    response = client.post('/api/auth/register', json={'username': username, 'password': password})
    assert response.status_code == 200
    return response.json()


def bearer(token):
    return {'Authorization': 'Bearer ' + token}


def test_business_endpoints_require_login(tmp_path, monkeypatch):
    module, client = client_for(tmp_path, monkeypatch)
    with client as c:
        for method, path in (('get', '/api/recipes'), ('get', '/api/tags'), ('get', '/api/shopping'), ('get', '/api/settings')):
            assert getattr(c, method)(path).status_code == 401
        assert c.post('/api/match', json={'ingredients': [], 'staples': []}).status_code == 401
        assert c.post('/api/recipes', json={}).status_code == 401
        assert c.get('/api/auth/me').status_code == 401


def test_register_login_and_session_recovery(tmp_path, monkeypatch):
    module, client = client_for(tmp_path, monkeypatch)
    with client as c:
        data = register(c)
        assert data['user']['username'] == 'alice'
        assert data['token']
        assert c.get('/api/auth/me', headers=bearer(data['token'])).json()['username'] == 'alice'
        assert len(c.get('/api/recipes', headers=bearer(data['token'])).json()) == 6
        assert c.get('/api/tags', headers=bearer(data['token'])).json()['groups'][0]['name'] == '我的分类'
        login = c.post('/api/auth/login', json={'username': 'alice', 'password': 'secret123'})
        assert login.status_code == 200 and login.json()['token'] != data['token']


def test_duplicate_username_and_wrong_password(tmp_path, monkeypatch):
    module, client = client_for(tmp_path, monkeypatch)
    with client as c:
        register(c)
        assert c.post('/api/auth/register', json={'username': 'alice', 'password': 'another1'}).status_code == 409
        assert c.post('/api/auth/login', json={'username': 'alice', 'password': 'wrong-pass'}).status_code == 401
        assert c.post('/api/auth/login', json={'username': 'nobody', 'password': 'secret123'}).status_code == 401


def test_password_is_hashed_in_database(tmp_path, monkeypatch):
    module, client = client_for(tmp_path, monkeypatch)
    with client as c:
        register(c, password='secret123')
        with module.engine.connect() as db:
            stored = db.execute(text('SELECT password_hash FROM users WHERE username=:name'), {'name': 'alice'}).scalar()
            session = db.execute(text('SELECT token_hash FROM sessions')).scalar()
        assert stored.startswith('scrypt$') and 'secret123' not in stored
        assert len(session) == 64 and ' ' not in session


def test_logout_invalidates_token(tmp_path, monkeypatch):
    module, client = client_for(tmp_path, monkeypatch)
    with client as c:
        token = register(c)['token']
        assert c.post('/api/auth/logout', headers=bearer(token)).status_code == 200
        assert c.get('/api/auth/me', headers=bearer(token)).status_code == 401
        assert c.get('/api/recipes', headers=bearer(token)).status_code == 401


def test_recipes_are_isolated_between_users(tmp_path, monkeypatch):
    module, client = client_for(tmp_path, monkeypatch)
    with client as c:
        alice = register(c)['token']
        recipe = {'name': '爱丽丝的菜', 'source': 'https://www.douguo.com/cookbook/777.html', 'ingredients': [{'name': '鸡蛋', 'amount': '2个'}], 'steps': ['打散']}
        created = c.post('/api/recipes', json=recipe, headers=bearer(alice)).json()
        bob = register(c, username='bob')['token']
        assert all(row['id'] != created['id'] for row in c.get('/api/recipes', headers=bearer(bob)).json())
        assert c.put('/api/recipes/' + str(created['id']), json=created, headers=bearer(bob)).status_code == 404
        assert c.delete('/api/recipes/' + str(created['id']), headers=bearer(bob)).status_code == 404
        assert c.get('/api/recipes', headers=bearer(alice)).json()[0]['id'] == created['id']
        same_source = c.post('/api/recipes', json=recipe, headers=bearer(bob))
        assert same_source.status_code == 200
        assert same_source.json()['id'] != created['id']


def test_tags_and_settings_are_isolated(tmp_path, monkeypatch):
    module, client = client_for(tmp_path, monkeypatch)
    with client as c:
        alice = register(c)['token']
        group = c.post('/api/tag-groups', json={'name': '我的厨具'}, headers=bearer(alice)).json()
        tag = c.post('/api/tags', json={'group_id': group['id'], 'name': '烤箱'}, headers=bearer(alice)).json()
        bob = register(c, username='bob')['token']
        assert all(item['id'] != tag['id'] for item in c.get('/api/tags', headers=bearer(bob)).json()['tags'])
        body = {'name': '偷用标签', 'source': '', 'tags': [tag], 'ingredients': [{'name': '鸡蛋', 'amount': '1个'}], 'steps': ['做']}
        assert c.post('/api/recipes', json=body, headers=bearer(bob)).status_code == 422
        assert c.patch('/api/tags/' + tag['id'], json={'name': '改名'}, headers=bearer(bob)).status_code == 404
        assert c.post('/api/shopping', json={'ids': [1]}, headers=bearer(alice)).status_code in (200, 404)
        c.put('/api/settings', json={'ingredients': ['番茄'], 'staples': ['盐']}, headers=bearer(alice))
        assert c.get('/api/settings', headers=bearer(bob)).json()['ingredients'] == []
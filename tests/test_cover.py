import importlib
import re
from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image


def client_for(tmp_path, monkeypatch):
    monkeypatch.setenv('SHISHI_DATABASE_URL', 'sqlite:///' + str(tmp_path / 'cover.db'))
    import backend.main as module
    module = importlib.reload(module)
    return TestClient(module.app)


def sign_in(client):
    token = client.post('/api/auth/register', json={'username': 'cover_user', 'password': 'shishi123'}).json()['token']
    client.headers.update({'Authorization': 'Bearer ' + token})
    return client


def image_bytes(fmt='PNG'):
    buffer = BytesIO()
    Image.new('RGB', (120, 80), (198, 120, 72)).save(buffer, fmt)
    return buffer.getvalue()


def recipe(body):
    return {'name': '封面测试菜', 'source': '', 'ingredients': [{'name': '鸡蛋', 'amount': '2个'}], 'steps': ['打散炒熟'], **body}


def test_demo_recipes_ship_with_photo_covers(tmp_path, monkeypatch):
    with client_for(tmp_path, monkeypatch) as c:
        sign_in(c)
        rows = c.get('/api/recipes').json()
        assert len(rows) == 6
        assert all(row['cover'].startswith('/api/demo/') for row in rows)
        assert all(any(tag['name'] == '快手菜' for tag in row['tags']) for row in rows if row['name'] == '番茄炒蛋')


def test_recipe_cover_roundtrip_and_rejects_external_urls(tmp_path, monkeypatch):
    with client_for(tmp_path, monkeypatch) as c:
        sign_in(c)
        created = c.post('/api/recipes', json=recipe({'cover': '/api/demo/tomato-egg.jpg'}))
        assert created.status_code == 200
        assert created.json()['cover'] == '/api/demo/tomato-egg.jpg'
        saved = created.json()
        saved['cover'] = '/api/media/' + 'b' * 64 + '.png'
        assert c.put('/api/recipes/' + str(saved['id']), json=saved).json()['cover'] == saved['cover']
        assert c.post('/api/recipes', json=recipe({'cover': 'https://example.com/a.jpg'})).status_code == 422
        assert c.post('/api/recipes', json=recipe({'cover': '/api/media/not-a-hash.jpg'})).status_code == 422


def test_cover_upload_requires_login_and_checks_image_type(tmp_path, monkeypatch):
    with client_for(tmp_path, monkeypatch) as c:
        assert c.post('/api/media', files={'file': ('cover.png', image_bytes(), 'image/png')}).status_code == 401
        sign_in(c)
        uploaded = c.post('/api/media', files={'file': ('cover.png', image_bytes(), 'image/png')})
        assert uploaded.status_code == 200
        url = uploaded.json()['url']
        assert re.fullmatch(r'/api/media/[a-f0-9]{64}\.png', url)
        assert c.get(url).status_code == 200
        assert c.post('/api/media', files={'file': ('notes.txt', b'not an image', 'text/plain')}).status_code == 422

def test_first_picture_becomes_default_cover(tmp_path, monkeypatch):
    from backend.recipe_schema import draft_v2
    local = '/api/media/' + 'c' * 64 + '.jpg'
    draft = draft_v2({'name': '导入草稿', 'source': '', 'source_images': [local], 'steps': ['做'], 'ingredients': [{'name': '鸡蛋'}]})
    assert draft['cover'] == local
    with client_for(tmp_path, monkeypatch) as c:
        sign_in(c)
        saved = c.post('/api/recipes', json={'name': '有图菜', 'source': '', 'source_images': [local], 'ingredients': [{'name': '鸡蛋', 'amount': '2个'}], 'steps': ['打散']}).json()
        assert saved['cover'] == local
        manual = c.post('/api/recipes', json={'name': '无图菜', 'source': '', 'ingredients': [{'name': '鸡蛋', 'amount': '2个'}], 'steps': ['打散']}).json()
        assert manual['cover'] == ''

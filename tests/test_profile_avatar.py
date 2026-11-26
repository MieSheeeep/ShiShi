import importlib
import io

from fastapi.testclient import TestClient
from PIL import Image


def client_for(tmp_path, monkeypatch):
    from backend import media
    monkeypatch.setattr(media, 'MEDIA_DIR', tmp_path / 'media')
    monkeypatch.setenv('SHISHI_DATABASE_URL', 'sqlite:///' + str(tmp_path / 'app.db'))
    import backend.main as module
    return TestClient(importlib.reload(module).app)


def sign_in(c, username='tester'):
    token = c.post('/api/auth/register', json={'username': username, 'password': 'shishi123'}).json()['token']
    c.headers.update({'Authorization': 'Bearer ' + token})
    return c


def png_bytes():
    buffer = io.BytesIO()
    Image.new('RGB', (8, 8), (120, 90, 60)).save(buffer, format='PNG')
    return buffer.getvalue()


def test_avatar_upload_save_and_reset(tmp_path, monkeypatch):
    c = sign_in(client_for(tmp_path, monkeypatch))
    assert c.get('/api/profile/avatar').json() == {'url': ''}
    uploaded = c.post('/api/media', files={'file': ('avatar.png', png_bytes(), 'image/png')}).json()['url']
    assert c.put('/api/profile/avatar', json={'url': uploaded}).json() == {'url': uploaded}
    assert c.get('/api/profile/avatar').json() == {'url': uploaded}
    assert c.put('/api/profile/avatar', json={'url': ''}).json() == {'url': ''}
    assert c.get('/api/profile/avatar').json() == {'url': ''}


def test_avatar_rejects_non_local_image(tmp_path, monkeypatch):
    c = sign_in(client_for(tmp_path, monkeypatch))
    assert c.put('/api/profile/avatar', json={'url': 'https://example.com/a.png'}).status_code == 422
    missing = '/api/media/' + 'a' * 64 + '.png'
    assert c.put('/api/profile/avatar', json={'url': missing}).status_code == 422
    assert c.get('/api/profile/avatar').json() == {'url': ''}


def test_avatar_is_isolated_per_account(tmp_path, monkeypatch):
    c = sign_in(client_for(tmp_path, monkeypatch))
    uploaded = c.post('/api/media', files={'file': ('avatar.png', png_bytes(), 'image/png')}).json()['url']
    c.put('/api/profile/avatar', json={'url': uploaded})
    other = sign_in(TestClient(c.app), username='second')
    assert other.get('/api/profile/avatar').json() == {'url': ''}


def test_nickname_save_and_reset(tmp_path, monkeypatch):
    c = sign_in(client_for(tmp_path, monkeypatch))
    assert c.get('/api/profile/nickname').json() == {'nickname': ''}
    assert c.put('/api/profile/nickname', json={'nickname': '  小厨房  '}).json() == {'nickname': '小厨房'}
    assert c.get('/api/profile/nickname').json() == {'nickname': '小厨房'}
    assert c.put('/api/profile/nickname', json={'nickname': '   '}).json() == {'nickname': ''}
    assert c.get('/api/profile/nickname').json() == {'nickname': ''}


def test_nickname_rejects_overlong_value(tmp_path, monkeypatch):
    c = sign_in(client_for(tmp_path, monkeypatch))
    assert c.put('/api/profile/nickname', json={'nickname': '名' * 25}).status_code == 422
    assert c.get('/api/profile/nickname').json() == {'nickname': ''}


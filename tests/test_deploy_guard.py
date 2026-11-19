import importlib

import pytest
from fastapi.testclient import TestClient

from backend import deploy_guard


def client_for(tmp_path, monkeypatch):
    monkeypatch.setenv('SHISHI_DATABASE_URL', 'sqlite:///' + str(tmp_path / 'deploy.db'))
    import backend.main as module
    module = importlib.reload(module)
    return module, TestClient(module.app)


def test_health_and_default_policy(tmp_path, monkeypatch):
    monkeypatch.delenv('SHISHI_ALLOW_REGISTER', raising=False)
    monkeypatch.delenv('SHISHI_INVITE_CODE', raising=False)
    _, client = client_for(tmp_path, monkeypatch)
    with client as c:
        health = c.get('/api/health')
        assert health.status_code == 200
        body = health.json()
        assert body['status'] == 'ok'
        assert body['journal_mode'] in {'WAL', 'MEMORY', 'DELETE'}

        policy = c.get('/api/auth/policy')
        assert policy.status_code == 200
        assert policy.json() == {'allow_register': True, 'invite_required': False}


def test_registration_invite_code_and_toggle(tmp_path, monkeypatch):
    monkeypatch.setenv('SHISHI_ALLOW_REGISTER', 'true')
    monkeypatch.setenv('SHISHI_INVITE_CODE', 'kitchen-2026')
    _, client = client_for(tmp_path, monkeypatch)
    with client as c:
        assert c.get('/api/auth/policy').json() == {'allow_register': True, 'invite_required': True}

        missing = c.post('/api/auth/register', json={'username': 'alice', 'password': 'secret123'})
        assert missing.status_code == 422

        wrong = c.post('/api/auth/register', json={'username': 'alice', 'password': 'secret123', 'invite_code': 'wrong'})
        assert wrong.status_code == 422

        ok = c.post('/api/auth/register', json={'username': 'alice', 'password': 'secret123', 'invite_code': 'kitchen-2026'})
        assert ok.status_code == 200

        monkeypatch.setenv('SHISHI_ALLOW_REGISTER', 'false')
        assert c.get('/api/auth/policy').json() == {'allow_register': False, 'invite_required': False}
        closed = c.post('/api/auth/register', json={'username': 'bob', 'password': 'secret123', 'invite_code': 'kitchen-2026'})
        assert closed.status_code == 403


@pytest.mark.parametrize('bad_url', [
    'http://127.0.0.1:8080/v1',
    'http://localhost:11434/v1',
    'http://169.254.169.254/latest/meta-data/',
    'http://10.0.0.1/v1',
    'http://192.168.1.5/v1',
    'http://[::1]/v1',
    'file:///etc/passwd',
    'https://user:pass@api.deepseek.com/v1',
])
def test_ai_base_url_blocks_private_and_invalid_targets(bad_url, monkeypatch):
    monkeypatch.delenv('SHISHI_ALLOW_PRIVATE_AI_URL', raising=False)
    with pytest.raises(ValueError):
        deploy_guard.validate_ai_base_url(bad_url)


def test_ai_base_url_allows_public_and_opt_in_private(monkeypatch):
    monkeypatch.delenv('SHISHI_ALLOW_PRIVATE_AI_URL', raising=False)
    assert deploy_guard.validate_ai_base_url('') == ''
    assert deploy_guard.validate_ai_base_url('https://api.deepseek.com/v1/') == 'https://api.deepseek.com/v1'

    monkeypatch.setenv('SHISHI_ALLOW_PRIVATE_AI_URL', '1')
    assert deploy_guard.validate_ai_base_url('http://127.0.0.1:11434/v1/') == 'http://127.0.0.1:11434/v1'


def test_ai_settings_endpoint_rejects_ssrf(tmp_path, monkeypatch):
    monkeypatch.delenv('SHISHI_ALLOW_REGISTER', raising=False)
    monkeypatch.delenv('SHISHI_INVITE_CODE', raising=False)
    monkeypatch.delenv('SHISHI_ALLOW_PRIVATE_AI_URL', raising=False)
    _, client = client_for(tmp_path, monkeypatch)
    with client as c:
        token = c.post('/api/auth/register', json={'username': 'alice', 'password': 'secret123'}).json()['token']
        headers = {'Authorization': 'Bearer ' + token}

        res = c.put('/api/ai/settings', headers=headers, json={'base': 'http://169.254.169.254/v1', 'model': 'x', 'key': 'sk-1'})
        assert res.status_code == 422

        verify = c.post('/api/ai/verify', headers=headers, json={'base': 'http://127.0.0.1:8000/v1', 'model': 'x', 'key': 'sk-1'})
        assert verify.status_code == 422


def test_sqlite_journal_mode_selection(monkeypatch):
    monkeypatch.setenv('SHISHI_SQLITE_JOURNAL_MODE', 'wal')
    assert deploy_guard.sqlite_journal_mode() == 'WAL'
    monkeypatch.setenv('SHISHI_SQLITE_JOURNAL_MODE', 'MEMORY')
    assert deploy_guard.sqlite_journal_mode() == 'MEMORY'
    monkeypatch.delenv('SHISHI_SQLITE_JOURNAL_MODE', raising=False)
    monkeypatch.setattr(deploy_guard.sys, 'platform', 'linux')
    assert deploy_guard.sqlite_journal_mode() == 'WAL'
    monkeypatch.setattr(deploy_guard.sys, 'platform', 'win32')
    assert deploy_guard.sqlite_journal_mode() == 'MEMORY'

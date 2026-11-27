import importlib
from io import BytesIO
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('SHISHI_DATABASE_URL', 'sqlite:///' + str(tmp_path / 'quests.db'))
    import backend.main as main
    main = importlib.reload(main)
    with TestClient(main.app) as c:
        login = c.post('/api/auth/register',
                       json={'username': f'quest-user-{uuid4().hex[:8]}', 'password': 'secret123'}).json()
        c.headers['Authorization'] = 'Bearer ' + login['token']
        yield c


def upload(client):
    buffer = BytesIO()
    Image.new('RGB', (2, 2), '#c6613f').save(buffer, 'PNG')
    response = client.post('/api/media', files={'file': ('step.png', buffer.getvalue(), 'image/png')})
    assert response.status_code == 200, response.text
    return response.json()['url']


def start(client, stage='s-1'):
    response = client.post('/api/cooking-sessions', json={'client_id': str(uuid4()), 'quest_stage': stage})
    assert response.status_code == 200, response.text
    return response.json()


def complete(client, stage='s-1', stars=3):
    session = start(client, stage)
    assert session['dishes'][0]['quest_stage'] == stage
    dish = session['dishes'][0]
    fields = {'id': dish['id'], 'outcome': 'success'}
    if stars >= 2:
        fields['note'] = '火候刚刚好，下次还这样做'
    if stars >= 3:
        fields['photos'] = [upload(client)]
    response = client.patch(f"/api/cooking-sessions/{session['id']}",
                            json={'version': session['version'], 'dishes': [fields]})
    assert response.status_code == 200, response.text
    session = response.json()
    response = client.post(f"/api/cooking-sessions/{session['id']}/complete",
                           json={'version': session['version']})
    assert response.status_code == 200, response.text
    return response.json()


def test_quest_catalog_is_playable_on_a_new_account(client):
    quest = client.get('/api/kitchen-quest').json()
    assert len(quest['chapters']) == 3
    assert quest['totals']['stages'] == 9
    assert quest['rank']['title'] == '青铜'
    assert len(quest['blind_box']['options']) == 3
    assert all('rows' not in stage for chapter in quest['chapters'] for stage in chapter['stages'])
    assert quest['chapters'][0]['unlocked'] is True
    assert quest['chapters'][1]['unlocked'] is False


def test_quest_session_scores_stars_and_secret(client):
    record = complete(client, 's-1', stars=3)
    quest = client.get('/api/kitchen-quest').json()
    stage = quest['chapters'][0]['stages'][0]
    assert stage['state'] == 'cleared'
    assert stage['stars'] == 3
    assert stage['secret_unlocked'] is True
    assert quest['totals']['stars'] == 3
    assert quest['rank']['points'] == 1
    secret = next(item for item in quest['secrets'] if item['stage_id'] == 's-1')
    assert secret['unlocked'] is True and secret['body']
    assert quest['blind_box']['options'][0]['completed'] is not None
    assert record['dishes'][0]['quest_stage'] == 's-1'


def test_three_stars_open_the_next_chapter(client):
    for stage in ('s-1', 's-2', 's-3'):
        complete(client, stage, stars=3)
    quest = client.get('/api/kitchen-quest').json()
    assert quest['totals']['stars'] == 9
    assert quest['chapters'][0]['completed'] is True
    assert quest['chapters'][1]['unlocked'] is True
    assert quest['chapters'][2]['unlocked'] is False


def test_quest_validation_and_unknown_stage(client):
    assert client.post('/api/cooking-sessions',
                       json={'client_id': str(uuid4()), 'quest_stage': 's-404'}).status_code == 404
    assert client.post('/api/cooking-sessions',
                       json={'client_id': str(uuid4())}).status_code == 422
    assert client.post('/api/cooking-sessions',
                       json={'client_id': str(uuid4()), 'manual_name': '补记',
                             'quest_stage': 's-1'}).status_code == 422
    assert client.post('/api/cooking-sessions',
                       json={'client_id': str(uuid4()), 'quest_stage': 'x' * 21}).status_code == 422

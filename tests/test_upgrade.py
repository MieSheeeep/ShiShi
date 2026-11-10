import importlib
import json

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text


def legacy_database(path):
    """构造升级前的单用户数据库：食谱、分组、清单与设置都没有账号归属。"""
    engine = create_engine('sqlite:///' + str(path))
    body = json.dumps({'name': '迁移前的红烧肉', 'source': '', 'tags': ['家常菜'], 'ingredients': [{'name': '五花肉', 'amount': '500克'}], 'steps': ['切块', '炖煮']}, ensure_ascii=False)
    with engine.begin() as db:
        db.execute(text('CREATE TABLE recipes (id INTEGER PRIMARY KEY,source TEXT UNIQUE,body TEXT NOT NULL)'))
        db.execute(text('INSERT INTO recipes VALUES(9,NULL,:body)'), {'body': body})
        db.execute(text('CREATE TABLE tag_groups (id TEXT PRIMARY KEY,name TEXT UNIQUE NOT NULL)'))
        db.execute(text("INSERT INTO tag_groups VALUES('g1','我的分类')"))
        db.execute(text('CREATE TABLE tags (id TEXT PRIMARY KEY,group_id TEXT NOT NULL,name TEXT NOT NULL,UNIQUE(group_id,name))'))
        db.execute(text('CREATE TABLE shopping (id INTEGER PRIMARY KEY CHECK(id=1),body TEXT NOT NULL)'))
        db.execute(text('INSERT INTO shopping VALUES(1,:body)'), {'body': json.dumps([{'name': '五花肉', 'amount': '500克', 'sources': [], 'checked': True}], ensure_ascii=False)})
        db.execute(text('CREATE TABLE settings (key TEXT PRIMARY KEY,body TEXT NOT NULL)'))
        db.execute(text("INSERT INTO settings VALUES('pantry',:body)"), {'body': json.dumps({'ingredients': ['番茄'], 'staples': ['盐']}, ensure_ascii=False)})
    return engine


def test_first_account_claims_data_and_later_accounts_start_fresh(tmp_path, monkeypatch):
    path = tmp_path / 'legacy.db'
    legacy_database(path)
    monkeypatch.setenv('SHISHI_DATABASE_URL', 'sqlite:///' + str(path))
    import backend.main as module
    module = importlib.reload(module)
    with TestClient(module.app) as c:
        token = c.post('/api/auth/register', json={'username': 'first', 'password': 'shishi123'}).json()['token']
        headers = {'Authorization': 'Bearer ' + token}
        rows = c.get('/api/recipes', headers=headers).json()
        assert [row['name'] for row in rows] == ['迁移前的红烧肉']
        assert rows[0]['id'] == 9
        assert c.get('/api/settings', headers=headers).json()['ingredients'] == ['番茄']
        assert c.get('/api/shopping', headers=headers).json()[0]['checked'] is True
        assert any(tag['name'] == '家常菜' for tag in c.get('/api/tags', headers=headers).json()['tags'])

        second = c.post('/api/auth/register', json={'username': 'second', 'password': 'shishi123'}).json()['token']
        other = c.get('/api/recipes', headers={'Authorization': 'Bearer ' + second}).json()
        assert len(other) == 6
        assert all(row['name'] != '迁移前的红烧肉' for row in other)
import copy
import json
import importlib
import pytest
from sqlalchemy import create_engine, text
from fastapi.testclient import TestClient
from backend.recipe_store import initialize, list_recipes
from backend.recipe_schema import Recipe

PHOTO='/api/media/'+'a'*64+'.jpg'

def legacy():
    return {'name':'测试食谱','source':'','author':'原作者','tags':['快手菜'],
            'ingredients':[{'name':'鸡蛋','amount':'2个'}], 'steps':['先打蛋','再炒熟'],
            'step_images':[[PHOTO],[]],'source_text':'原始文字','source_images':[PHOTO]}

def test_unknown_document_version_is_not_silently_downgraded():
    with pytest.raises(ValueError,match='版本'):
        Recipe.model_validate(dict(legacy(),schema_version=99))

def client_for(tmp_path,monkeypatch):
    monkeypatch.setenv('SHISHI_DATABASE_URL','sqlite:///'+str(tmp_path/'app.db'))
    import backend.main as module
    module=importlib.reload(module)
    return TestClient(module.app)

def test_migration_backs_up_and_preserves_old_image_pairing(tmp_path):
    path=tmp_path/'legacy.db';engine=create_engine('sqlite:///'+str(path))
    with engine.begin() as db:
        db.execute(text('CREATE TABLE recipes (id INTEGER PRIMARY KEY,source TEXT UNIQUE,body TEXT NOT NULL)'))
        db.execute(text('INSERT INTO recipes VALUES(42,NULL,:body)'),{'body':json.dumps(legacy())})
    initialize(engine,seed=False)
    row=list_recipes(engine)[0]
    assert row['id']==42 and row['schema_version']==2
    assert row['steps'][0]['images']==[PHOTO]
    assert row['steps'][1]['images']==[]
    assert row['source']['original_text']=='原始文字'
    assert row['original_snapshot']['kind']=='legacy_saved'
    assert row['tags'][0]['name']=='快手菜'
    before=[s['id'] for s in row['steps']]
    initialize(engine,seed=False)
    assert [s['id'] for s in list_recipes(engine)[0]['steps']]==before
    assert len(list(tmp_path.glob('legacy.db.pre-v2-*.bak')))==1

def test_reorder_preserves_ids_images_and_original(tmp_path,monkeypatch):
    with client_for(tmp_path,monkeypatch) as c:
        r=c.post('/api/recipes',json=legacy());assert r.status_code==200
        saved=r.json();original=copy.deepcopy(saved['original_snapshot'])
        first_id=saved['steps'][0]['id']
        saved['steps'].reverse()
        saved['steps'][0]['text']='我修改的做法'
        saved['source']['original_text']='不能覆盖原文'
        saved['original_snapshot']={'kind':'tampered'}
        r=c.put('/api/recipes/'+str(saved['id']),json=saved);assert r.status_code==200
        edited=r.json()
        assert edited['steps'][1]['id']==first_id and edited['steps'][1]['images']==[PHOTO]
        assert edited['steps'][0]['text']=='我修改的做法'
        assert edited['source']['original_text']=='原始文字'
        assert edited['original_snapshot']==original

def test_tags_are_user_defined_and_rename_updates_all_recipes(tmp_path,monkeypatch):
    with client_for(tmp_path,monkeypatch) as c:
        group=c.post('/api/tag-groups',json={'name':'厨具'}).json()
        tag=c.post('/api/tags',json={'group_id':group['id'],'name':'空气炸锅'}).json()
        taste=c.post('/api/tag-groups',json={'name':'口味'}).json()
        mild=c.post('/api/tags',json={'group_id':taste['id'],'name':'清淡'}).json()
        body=legacy();body['tags']=[tag,mild]
        a=c.post('/api/recipes',json=body).json()
        b=c.post('/api/recipes',json=dict(legacy(),name='第二道菜',tags=[tag])).json()
        renamed=c.patch('/api/tags/'+tag['id'],json={'name':'小空气炸锅'})
        assert renamed.status_code==200
        rows=c.get('/api/recipes',params=[('tag_id',tag['id']),('tag_id',mild['id'])]).json()
        assert [r['id'] for r in rows]==[a['id']]
        assert next(t for t in rows[0]['tags'] if t['id']==tag['id'])['name']=='小空气炸锅'
        other=next(r for r in c.get('/api/recipes').json() if r['id']==b['id'])
        assert other['tags'][0]['name']=='小空气炸锅'
        assert c.delete('/api/tags/'+tag['id']).status_code==200
        assert all(t['id']!=tag['id'] for r in c.get('/api/recipes').json() for t in r['tags'])
        import backend.main as module
        with module.engine.connect() as db:
            assert all(tag['id'] not in json.loads(row.body)['tag_ids'] for row in db.execute(text('SELECT body FROM recipes')))

def test_storage_document_tag_ids_survive_roundtrip(tmp_path,monkeypatch):
    with client_for(tmp_path,monkeypatch) as c:
        saved=c.post('/api/recipes',json=legacy()).json()
        ids=saved['tag_ids'][:]
        del saved['tags']
        response=c.put('/api/recipes/'+str(saved['id']),json=saved)
        assert response.status_code==200
        assert response.json()['tag_ids']==ids

def test_duplicate_step_ids_and_empty_steps_rejected(tmp_path,monkeypatch):
    with client_for(tmp_path,monkeypatch) as c:
        r=c.post('/api/recipes',json=legacy()).json()
        r['steps'][1]['id']=r['steps'][0]['id']
        assert c.put('/api/recipes/'+str(r['id']),json=r).status_code==422
        r['steps']=[{'id':'s1','text':'  ','images':[]}]
        assert c.put('/api/recipes/'+str(r['id']),json=r).status_code==422

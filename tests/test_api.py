import importlib
from fastapi.testclient import TestClient

def test_full_flow(tmp_path,monkeypatch):
    monkeypatch.setenv('SHISHI_DATABASE_URL','sqlite:///'+str(tmp_path/'test.db'))
    import backend.main as module
    module=importlib.reload(module)
    with TestClient(module.app) as c:
        assert len(c.get('/api/recipes').json()) == 6
        data={'name':'测试菜','source':'https://www.douguo.com/cookbook/123.html','ingredients':[{'name':'西红柿','amount':'2个'},{'name':'盐','amount':'适量'}],'steps':['切块','炒熟']}
        response=c.post('/api/recipes',json=data)
        assert response.status_code==200
        recipe=response.json()
        assert recipe['ingredients'][0]['name']=='番茄'
        assert c.post('/api/recipes',json=data).status_code==409
        assert c.post('/api/imports',json={'url':data['source']+'?from=x'}).status_code==409
        assert c.post('/api/imports',json={'url':'https://example.org'}).status_code==422
        results=c.post('/api/match',json={'ingredients':['西红柿'],'staples':['盐']}).json()
        assert next(x for x in results if x['id']==recipe['id'])['missing']==[]
        items=c.post('/api/shopping',json={'ids':[recipe['id']]}).json()
        assert items[0]['amount']=='2个'
        items[0]['checked']=True
        assert c.put('/api/shopping',json={'items':items}).status_code==200
        assert c.get('/api/shopping').json()[0]['checked']
        recipe['notes']='下次少放盐'
        assert c.put('/api/recipes/'+str(recipe['id']),json=recipe).json()['notes']=='下次少放盐'
        assert c.delete('/api/recipes/'+str(recipe['id'])).status_code==200
        assert len(c.get('/api/recipes').json())==6

import json
import httpx
import pytest
from backend.source_urls import canonical_url, import_url, xhs_fetch_url
from backend.xiaohongshu import parse_note, fetch_xiaohongshu

ID='0123456789abcdef01234567'
URL=f'https://www.xiaohongshu.com/explore/{ID}'
DESC='食材：\n西红柿 2个\n鸡蛋 3个\n做法：\n1. 切块。\n2. 炒熟。'

def page(desc=DESC,kind='normal'):
    state={'note':{'noteDetailMap':{ID:{'note':{'noteId':ID,'title':'番茄炒蛋','desc':desc,'type':kind,'user':{'nickname':'测试作者'},'tagList':[{'name':'家常菜'}]}}}}}
    return '<script>window.__INITIAL_STATE__='+json.dumps(state,ensure_ascii=False)+'</script>'

def test_share_text_and_canonical_dedup():
    signed=URL+'?xsec_token=abc%2Bdef&xsec_source=pc_feed&tracking=1'
    assert canonical_url(signed)==URL
    assert canonical_url(f'https://www.xiaohongshu.com/discovery/item/{ID}')==URL
    assert import_url('这是分享文案 '+signed+' 。')==signed
    assert canonical_url('http://xhslink.com/a/abc123')=='https://xhslink.com/a/abc123'

def test_fetch_keeps_original_share_path():
    original=f'https://www.xiaohongshu.com/discovery/item/{ID}?xsec_token=abc%2Bdef'
    assert xhs_fetch_url(original)==original

def test_access_error_redirect_has_readable_reason():
    transport=httpx.MockTransport(lambda req:httpx.Response(302,headers={'Location':'/404/sec_abcd?error_code=300013'}))
    with pytest.raises(ValueError,match='访问限制'):fetch_xiaohongshu(URL,transport=transport)

@pytest.mark.parametrize('bad',['https://www.xiaohongshu.com.evil.org/explore/'+ID,'https://127.0.0.1/explore/'+ID,'https://www.xiaohongshu.com:444/explore/'+ID,'https://www.xiaohongshu.com/user/profile/'+ID,'https://www.xiaohongshu.com@evil.com/explore/'+ID])
def test_reject_unsupported_urls(bad):
    with pytest.raises(ValueError):canonical_url(bad)

def test_recipe_sections_keep_original():
    r=parse_note(page(),URL)
    assert r['name']=='番茄炒蛋' and r['author']=='测试作者'
    assert r['source_text']==DESC
    assert r['ingredients'][0]=={'name':'西红柿','amount':'2个','kind':'食材'}
    assert r['steps']==['切块。','炒熟。']

def test_decorated_recipe_headings_pipes_and_circled_steps():
    desc='🌈【食材准备】\n鸡翅 | 可乐1罐 | 姜5片 | 生抽1大勺\n芝麻随意\n🔥【魔法步骤】\n❶ 准备鸡翅\n❷ 加入可乐\n❸ 炖15分钟\n💡【神仙Tips】\n✅ 原文的其他说明\n🌟#厨房[话题]#'
    r=parse_note(page(desc),URL)
    assert len(r['ingredients'])==5
    assert r['ingredients'][1]=={'name':'可乐','amount':'1罐','kind':'食材'}
    assert r['ingredients'][3]['name']=='生抽' and r['ingredients'][3]['amount']=='1大勺'
    assert r['ingredients'][4]['name']=='芝麻' and r['ingredients'][4]['amount']=='随意'
    assert r['steps']==['准备鸡翅','加入可乐','炖15分钟']
    assert r['source_text']==desc and not r['import_warnings']

def test_note_images_are_album_not_guessed_step_images():
    html=page().replace('"user":', '"imageList":[{"urlDefault":"https://sns-webpic-qc.xhscdn.com/picture.jpg"}],"user":')
    r=parse_note(html,URL)
    assert r['source_images']==['https://sns-webpic-qc.xhscdn.com/picture.jpg']
    assert r['step_images']==[]

def test_missing_sections_are_editable_not_invented():
    r=parse_note(page('今天的晚餐很好吃。食谱在图片里。'),URL)
    assert r['ingredients']==[{'name':'','amount':'','kind':'食材'}]
    assert r['steps']==[''] and r['import_warnings']

def test_undefined_inside_text_preserved_and_no_script_execution():
    html=page('undefined 是原文的一部分').replace('"type": "normal"','"unused": undefined, "type": "normal"')
    assert parse_note(html,URL)['source_text']=='undefined 是原文的一部分'
    with pytest.raises(ValueError):parse_note('<script>window.__INITIAL_STATE__=alert(1)</script>',URL)

def test_shortlink_cookie_isolation_and_signed_target(monkeypatch):
    monkeypatch.setenv('XHS_COOKIE','test_cookie=private')
    seen=[]
    def respond(req):
        seen.append(req)
        if req.url.host=='xhslink.com':return httpx.Response(302,headers={'Location':URL+'?xsec_token=abc%2Bdef'})
        return httpx.Response(200,text=page())
    r=fetch_xiaohongshu('https://xhslink.com/a/abc',transport=httpx.MockTransport(respond))
    assert 'cookie' not in seen[0].headers
    assert seen[1].headers['cookie']=='test_cookie=private'
    assert seen[1].url.params['xsec_token']=='abc+def'
    assert r['source']==URL and 'private' not in json.dumps(r)

def test_redirect_to_localhost_blocked_before_request():
    seen=[]
    def respond(req):
        seen.append(req)
        return httpx.Response(302,headers={'Location':'http://127.0.0.1:8000/api/recipes'})
    with pytest.raises(ValueError):fetch_xiaohongshu('https://xhslink.com/a/abc',transport=httpx.MockTransport(respond))
    assert len(seen)==1

@pytest.mark.parametrize('html,status',[('<h1>请登录</h1>',200),('<h1>安全验证</h1>',200),('',461),('',404)])
def test_login_captcha_and_missing_note_fail_clearly(html,status):
    with pytest.raises(ValueError):fetch_xiaohongshu(URL,transport=httpx.MockTransport(lambda req:httpx.Response(status,text=html)))

def test_video_rejected():
    with pytest.raises(ValueError,match='视频'):parse_note(page(kind='video'),URL)

def test_seasoning_section_kind_persists():
    r=parse_note(page('调料：\n盐 适量\n油 1勺\n步骤：\n1. 炒熟'),URL)
    assert all(i['kind']=='调料' for i in r['ingredients'])

def test_import_save_reload_and_duplicate_note(tmp_path,monkeypatch):
    import importlib
    from fastapi.testclient import TestClient
    monkeypatch.setenv('SHISHI_DATABASE_URL','sqlite:///'+str(tmp_path/'xhs.db'))
    import backend.main as module
    module=importlib.reload(module)
    transport=httpx.MockTransport(lambda req:httpx.Response(200,text=page()))
    monkeypatch.setattr(module,'fetch_recipe',lambda url:fetch_xiaohongshu(url,transport=transport))
    with TestClient(module.app) as c:
        draft=c.post('/api/imports',json={'url':'分享笔记 '+URL+'?xsec_token=demo'}).json()
        assert draft['source']['original_text']==DESC
        saved=c.post('/api/recipes',json=draft)
        assert saved.status_code==200
        body=saved.json()
        assert body['source']['url']==URL and body['ingredients'][0]['name']=='番茄'
        assert next(r for r in c.get('/api/recipes').json() if r['id']==body['id'])['source']['original_text']==DESC
        assert c.post('/api/imports',json={'url':URL+'?xsec_token=another'}).status_code==409
        assert c.post('/api/recipes',json=dict(draft,source=URL.replace('/explore/','/discovery/item/'))).status_code==409

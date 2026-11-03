import httpx
import pytest
from backend.crawler import fetch_recipe

HTML = '<h1>测试食谱</h1><table class="retamr"><tr><td><span class="scname">面粉</span><span class="scnum">100克</span></td></tr></table><div class="step"><div class="stepinfo"><p>步骤1</p>170度烘烤15分钟</div></div>'
URL = 'https://www.douguo.com/cookbook/3359224.html'

def test_retry_connection_failure_then_parse():
    calls=[]
    def respond(request):
        calls.append(request)
        if len(calls)==1: raise httpx.ConnectError('TLS EOF',request=request)
        return httpx.Response(200,text=HTML)
    r=fetch_recipe(URL,transport=httpx.MockTransport(respond))
    assert len(calls)==2
    assert r['name']=='测试食谱'
    assert r['steps']==['170度烘烤15分钟']

@pytest.mark.parametrize('status,message',[(404,'不存在'),(403,'限制'),(429,'频繁'),(302,'跳转')])
def test_http_errors_not_retried(status,message):
    calls=[]
    def respond(request):
        calls.append(request)
        return httpx.Response(status,headers={'Location':'http://127.0.0.1'} if status==302 else {})
    with pytest.raises(ValueError,match=message): fetch_recipe(URL,transport=httpx.MockTransport(respond))
    assert len(calls)==1

def test_connection_retry_is_bounded():
    calls=[]
    def respond(request):
        calls.append(request)
        raise httpx.ConnectError('TLS EOF',request=request)
    with pytest.raises(ValueError,match='已重试一次'): fetch_recipe(URL,transport=httpx.MockTransport(respond))
    assert len(calls)==2

def test_response_limit():
    transport=httpx.MockTransport(lambda r:httpx.Response(200,content=b'x'*3_000_001))
    with pytest.raises(ValueError,match='过大'): fetch_recipe(URL,transport=transport)

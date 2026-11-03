from io import BytesIO
import httpx
from PIL import Image
from backend.media import download_recipe_images
from backend.core import parse_douguo
from backend.xiaohongshu import parse_note

def test_douguo_step_images_align_without_labels():
    html='<h1>煎蛋</h1><table class="retamr"><tr><td><span class="scname">鸡蛋</span><span class="scnum">1个</span></td></tr></table><div class="step"><div class="stepcont"><img src="https://cp1.douguo.com/small.jpg" data-origin="https://cp1.douguo.com/original.jpg"><div class="stepinfo"><p>步骤1</p>打蛋</div></div><div class="stepcont"><div class="stepinfo"><p>步骤2</p>煎熟</div></div></div>'
    r=parse_douguo(html,'https://www.douguo.com/cookbook/1.html')
    assert r['step_images']==[['https://cp1.douguo.com/original.jpg'],[]]

def test_images_saved_locally_and_untrusted_hosts_not_requested(tmp_path):
    image=BytesIO();Image.new('RGB',(8,8),'green').save(image,format='PNG')
    seen=[]
    def respond(req):
        seen.append(req)
        return httpx.Response(200,content=image.getvalue(),headers={'Content-Type':'image/png'})
    url='https://cp1.douguo.com/test.png'
    draft={'source_images':[url,'http://127.0.0.1/private'],'step_images':[[url],[]]}
    r=download_recipe_images(draft,transport=httpx.MockTransport(respond),directory=tmp_path)
    assert len(seen)==1
    assert len(r['source_images'])==1
    assert r['source_images'][0].startswith('/api/media/')
    assert r['step_images'][0][0]==r['source_images'][0]
    assert len(list(tmp_path.glob('*.png')))==1
    assert r['import_warnings']

def test_bad_response_and_redirect_are_not_images(tmp_path):
    for response in [httpx.Response(200,text='<html>login</html>'),httpx.Response(302,headers={'Location':'http://127.0.0.1'})]:
        draft={'source_images':['https://cp1.douguo.com/test.jpg'],'step_images':[]}
        r=download_recipe_images(draft,transport=httpx.MockTransport(lambda req:response),directory=tmp_path)
        assert not r['source_images'] and r['import_warnings']
    assert not list(tmp_path.iterdir())

"""Keep recipe pictures locally; only fetch fixed platform image hosts."""
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import warnings
from urllib.parse import urlsplit
import httpx
from PIL import Image

MEDIA_DIR = Path(__file__).resolve().parents[1] / 'data' / 'media'
IMAGE_HOSTS = {
    'cp1.douguo.com','cp2.douguo.com','cp3.douguo.com','cp4.douguo.com','ci.xiaohongshu.com',
    'sns-img-qc.xhscdn.com','sns-img-bd.xhscdn.com','sns-img-hw.xhscdn.com',
    'sns-webpic-qc.xhscdn.com','sns-webpic-bd.xhscdn.com','sns-webpic-hw.xhscdn.com',
}

def image_url(value):
    if value.startswith('//'):value='https:'+value
    p=urlsplit(value)
    if p.scheme not in ('http','https') or p.hostname not in IMAGE_HOSTS or p.username or p.password or p.port not in (None,80,443):
        raise ValueError('不支持的图片地址')
    return value

def save_upload(body, directory=None):
    """保存用户上传的封面图，按内容哈希命名并返回本地访问地址。"""
    if not body:raise ValueError('请选择图片文件')
    if len(body)>5_000_000:raise ValueError('图片不能超过 5 MB')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            with Image.open(BytesIO(body)) as im:
                if im.width*im.height>30_000_000:raise ValueError('图片尺寸过大')
                extension={'JPEG':'jpg','PNG':'png','WEBP':'webp'}.get(im.format)
                if not extension:raise ValueError('只支持 JPG、PNG 或 WEBP 图片')
                im.verify()
    except (OSError,Image.DecompressionBombWarning,Image.DecompressionBombError):
        raise ValueError('无法识别这张图片，请换一张 JPG、PNG 或 WEBP 图片')
    directory=Path(directory) if directory is not None else MEDIA_DIR
    directory.mkdir(parents=True,exist_ok=True)
    name=sha256(body).hexdigest()+'.'+extension
    (directory/name).write_bytes(body)
    return '/api/media/'+name

def download_recipe_images(draft, *, transport=None, directory=None):
    directory=Path(directory) if directory is not None else MEDIA_DIR
    directory.mkdir(parents=True,exist_ok=True)
    source=draft.get('source_images',[])
    steps=draft.get('step_images',[])
    urls=list(dict.fromkeys(source+[u for group in steps for u in group if u]))
    accepted, failures = {}, 0
    with httpx.Client(timeout=8,follow_redirects=False,transport=transport,headers={'User-Agent':'Mozilla/5.0'}) as client:
        def fetch(url):
            try:
                url=image_url(url)
                referer='https://www.douguo.com/' if urlsplit(url).hostname.endswith('.douguo.com') else 'https://www.xiaohongshu.com/'
                with client.stream('GET',url,headers={'Referer':referer}) as response:
                    response.raise_for_status()
                    if response.is_redirect:raise ValueError('图片跳转不受支持')
                    chunks,size=[],0
                    for chunk in response.iter_bytes():
                        size+=len(chunk)
                        if size>5_000_000:raise ValueError('图片过大')
                        chunks.append(chunk)
                    body=b''.join(chunks)
                with warnings.catch_warnings():
                    warnings.simplefilter('error',Image.DecompressionBombWarning)
                    with Image.open(BytesIO(body)) as im:
                        if im.width*im.height>30_000_000:raise ValueError('图片尺寸过大')
                        extension={'JPEG':'jpg','PNG':'png','WEBP':'webp','GIF':'gif'}.get(im.format)
                        if not extension:raise ValueError('图片格式暂不支持')
                        im.verify()
                return body,extension
            except (httpx.HTTPError,ValueError,OSError,Image.DecompressionBombWarning,Image.DecompressionBombError):
                return None
        with ThreadPoolExecutor(max_workers=4) as executor:
            total=0
            for original,result in zip(urls[:24],executor.map(fetch,urls[:24])):
                if result is None:
                    failures+=1
                    continue
                body,ext=result
                if total+len(body)>30_000_000:
                    failures+=1
                    continue
                total+=len(body)
                name=sha256(body).hexdigest()+'.'+ext
                (directory/name).write_bytes(body)
                accepted[original]='/api/media/'+name
    failures+=max(0,len(urls)-24)
    draft['source_images']=[accepted[u] for u in source if u in accepted]
    draft['step_images']=[[accepted[u] for u in group if u in accepted] for group in steps]
    if failures:
        draft.setdefault('import_warnings',[]).append(f'{failures} 张图片未能保存，可能已失效、被限制或超出大小上限；文字草稿仍可核对保存。')
    return draft

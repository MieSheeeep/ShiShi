"""Single public note import, based on the MIT-licensed ReaJason/xhs HTML path."""
import os
import re
from urllib.parse import urljoin, urlsplit
import httpx
from bs4 import BeautifulSoup
from backend.source_urls import canonical_url, xhs_fetch_url
from backend.vendor.xhs_html import extract_note

def recipe_sections(desc):
    ingredients, steps = [], []
    section, kind = None, '食材'
    for raw in desc.splitlines():
        line = raw.strip().strip('【】').strip()
        if not line or re.match(r'^#[^\s]+\[话题\]', line):
            continue
        heading = re.match(r'^(?:[🥬🥚🍅🍳📝✅🔸🔹✨\s]*)(食材|用料|材料|调料|步骤|做法|制作步骤|制作方法|制作过程)\s*[：:]?\s*(.*)$', line)
        if heading:
            section = 'steps' if heading[1] in ('步骤','做法','制作步骤','制作方法','制作过程') else 'ingredients'
            kind = '调料' if heading[1] == '调料' else '食材'
            line = heading[2].strip('】 \t')
            if not line:
                continue
        elif re.match(r'^(?:小贴士|注意事项|心得|营养|热量|备注)\s*[：:]', line) or line.startswith('#'):
            section = None
            continue
        if section == 'ingredients':
            # Split only explicit ingredient lists; do not infer ingredients from prose.
            for item in re.split(r'[，,、；;]', line):
                item = re.sub(r'^[-•·\s]+', '', item).strip()
                if not item:
                    continue
                m = re.fullmatch(r'(.+?)(?:\s+|[：:]\s*|(?=[\d一二两三四五六七八九十半]+(?:个|克|千克|斤|根|勺|片|毫升|升|g|ml)))(.+)', item)
                name, amount = (m[1].strip(), m[2].strip()) if m else (item, '未注明')
                ingredients.append({'name':name, 'amount':amount, 'kind':kind})
        elif section == 'steps':
            steps.append(re.sub(r'^(?:步骤\s*\d+\s*[.、：:]?\s*|\d+\s*[.、：:](?!\d)\s*|[-•·]\s*)', '', line))
    return ingredients[:200], steps[:200]

def parse_note(html, url):
    source = canonical_url(url)
    text = BeautifulSoup(html, 'html.parser').get_text(' ', strip=True)
    if 'window.__INITIAL_STATE__' not in html:
        if any(x in text for x in ('安全验证','访问异常','滑块验证','验证码')):
            raise ValueError('小红书要求安全验证，请在浏览器中自行完成后再试，系统不自动处理验证码')
        if any(x in text for x in ('请登录','登录后查看','扫码登录')):
            raise ValueError('这篇小红书笔记需要登录；可在本机配置自己的 XHS_COOKIE 后重试')
    note = extract_note(html, urlsplit(source).path.rsplit('/',1)[-1])
    if note.get('type') == 'video':
        raise ValueError('当前只支持小红书图文笔记，不解析视频食谱')
    desc = note.get('desc') or ''
    if not isinstance(desc, str) or not desc.strip():
        raise ValueError('笔记没有可提取的文字正文，暂不识别图片中的食谱文字')
    ingredients, steps = recipe_sections(desc)
    warnings = []
    if not ingredients: warnings.append('原文未找到明确的食材段落，请对照原文补充食材。')
    if not steps: warnings.append('原文未找到明确的步骤段落，请对照原文补充做法。')
    user = note.get('user') or {}
    if not isinstance(user, dict):
        user = {}
    images=[]
    for img in note.get('image_list') or []:
        if not isinstance(img,dict):continue
        src=img.get('url_default') or img.get('url_pre')
        if not src:
            src=next((x.get('url') for x in img.get('info_list',[]) if isinstance(x,dict) and x.get('url')),None)
        if isinstance(src,str):images.append(src)
    return {'name':str(note.get('title') or ''), 'author':str(user.get('nickname') or ''),
            'source':source, 'source_text':desc[:50000], 'minutes':'', 'servings':'',
            'emoji':'🍲', 'tags':['小红书导入'], 'notes':'',
            'ingredients':ingredients or [{'name':'','amount':'','kind':'食材'}],
            'steps':steps or [''], 'import_warnings':warnings,
            'source_images':list(dict.fromkeys(images)), 'step_images':[]}

def fetch_xiaohongshu(value, *, transport=None):
    url = xhs_fetch_url(value)
    with httpx.Client(timeout=20, follow_redirects=False, transport=transport,
                      headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                               'Referer':'https://www.xiaohongshu.com/'}) as client:
        for hop in range(5):
            is_note = urlsplit(url).hostname == 'www.xiaohongshu.com'
            cookie = os.environ.get('XHS_COOKIE','').strip() if is_note else ''
            headers = {'Cookie':cookie} if cookie else {}
            try:
                with client.stream('GET',url,headers=headers) as response:
                    if response.is_redirect:
                        if hop == 4:
                            raise ValueError('小红书分享链接跳转次数过多')
                        location = response.headers.get('location','')
                        if not location:
                            raise ValueError('小红书返回了无效跳转')
                        target = urljoin(url,location)
                        if urlsplit(target).hostname in ('www.xiaohongshu.com','xiaohongshu.com') and urlsplit(target).path.startswith('/404'):
                            raise ValueError('小红书返回访问限制或笔记暂时无法浏览，请稍后重试或在本机配置登录态')
                        if urlsplit(target).hostname in ('www.xiaohongshu.com','xiaohongshu.com') and re.search(r'/(?:login|website-login|captcha|auth)(?:/|$)',urlsplit(target).path):
                            raise ValueError('小红书要求登录或安全验证，请在浏览器中自行处理后重试')
                        url = xhs_fetch_url(target)
                        continue
                    if response.status_code in (401,403,461,471):
                        raise ValueError('小红书要求登录或安全验证，暂时无法读取这篇笔记')
                    if response.status_code == 404:
                        raise ValueError('小红书笔记不存在或分享链接已失效')
                    if response.status_code == 429:
                        raise ValueError('小红书访问过于频繁，请稍后重试')
                    response.raise_for_status()
                    chunks, size = [], 0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > 3_000_000:
                            raise ValueError('小红书页面内容过大，暂不支持导入')
                        chunks.append(chunk)
                    html = b''.join(chunks).decode('utf-8',errors='replace')
                if not is_note:
                    raise ValueError('小红书短链未返回笔记地址，请复制完整分享链接')
                return parse_note(html,url)
            except httpx.TimeoutException as exc:
                raise ValueError('读取小红书超时，请稍后重试') from exc
            except httpx.HTTPError as exc:
                raise ValueError('无法连接小红书或读取页面，请检查网络后重试') from exc

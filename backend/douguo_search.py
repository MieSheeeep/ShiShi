"""按菜名在豆果搜索菜谱，返回候选列表供逐条导入。

豆果的搜索页需要先拿到会话 Cookie（laravel_session），否则直接请求会被 403
拦截，所以每次搜索先访问一次首页再请求 ``/caipu/{关键词}``。
"""
import html
import re
import time
import urllib.parse

import httpx

SEARCH_HOME = 'https://www.douguo.com/'
SEARCH_PATH = 'https://www.douguo.com/caipu/'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml',
    'Accept-Language': 'zh-CN,zh;q=0.9',
}
CACHE_TTL = 600
_cache = {}


def parse_candidates(page):
    """从搜索结果页里提取菜谱候选，按菜谱 ID 去重。"""
    items, seen = [], set()
    for block in re.findall(r'<li class="clearfix">(.*?)</li>', page, re.S):
        head = re.search(r'class="cook-img" href="/cookbook/(\d+)\.html"[^>]*title="([^"]*)"', block)
        if not head:
            continue
        recipe_id = head.group(1)
        if recipe_id in seen:
            continue
        seen.add(recipe_id)
        cover = re.search(r'<img src="(https://[^"]+)"', block)
        major = re.search(r'<p class="major">(.*?)</p>', block, re.S)
        likes = re.search(r'收藏人数\s*(\d+)', block)
        items.append({
            'url': f'https://www.douguo.com/cookbook/{recipe_id}.html',
            'title': html.unescape(head.group(2)).strip(),
            'cover': html.unescape(cover.group(1)) if cover else '',
            'ingredients': re.sub(r'<[^>]+>', '', major.group(1)).strip() if major else '',
            'likes': int(likes.group(1)) if likes else 0,
        })
    return items


def search_candidates(keyword, *, transport=None):
    """搜索菜名，返回候选列表；结果在进程内缓存 10 分钟。"""
    keyword = ' '.join(keyword.split())
    if not keyword:
        raise ValueError('请输入菜名')
    cached = _cache.get(keyword)
    if cached and time.time() - cached[0] < CACHE_TTL:
        return cached[1]
    with httpx.Client(timeout=20, follow_redirects=True, transport=transport, headers=HEADERS) as client:
        try:
            client.get(SEARCH_HOME)
            response = client.get(SEARCH_PATH + urllib.parse.quote(keyword))
        except httpx.TimeoutException as exc:
            raise ValueError('搜索豆果超时，请稍后重试') from exc
        except httpx.HTTPError as exc:
            raise ValueError('连接豆果失败，请检查网络后重试') from exc
        if response.status_code == 403:
            raise ValueError('豆果暂时限制了搜索访问，请稍后再试')
        if response.status_code == 429:
            raise ValueError('访问过于频繁，请稍后再试')
        if response.status_code >= 400:
            raise ValueError(f'豆果返回 HTTP {response.status_code}，请稍后重试')
        items = parse_candidates(response.text)
    if not items:
        raise ValueError('没有找到相关菜谱，换个菜名试试')
    _cache[keyword] = (time.time(), items)
    return items

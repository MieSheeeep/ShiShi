"""Allowlisted import URLs; note identity excludes temporary access tokens."""
import re
from urllib.parse import urlsplit, urlunsplit

XHS_HOSTS = {'www.xiaohongshu.com', 'xiaohongshu.com', 'xhslink.com', 'www.xhslink.com'}

def import_url(value):
    value = value.strip()
    if not value.startswith(('https://', 'http://')) or any(c.isspace() for c in value):
        match = re.search(r'https?://[^\s<>"\u3002\uff0c\uff01\uff09]+', value)
        if not match:
            raise ValueError('请粘贴豆果菜谱或小红书笔记链接')
        value = match[0].rstrip('.,;!，。；！）)')
    return value

def is_xiaohongshu(url):
    return urlsplit(url).hostname in XHS_HOSTS

def canonical_url(value):
    value = import_url(value)
    p = urlsplit(value)
    if p.scheme not in ('http', 'https') or p.username or p.password or p.port not in (None, 80, 443):
        raise ValueError('请使用受支持平台的 HTTP/HTTPS 链接')
    if p.hostname in ('www.douguo.com', 'douguo.com') and re.fullmatch(r'/cookbook/\d+\.html', p.path):
        return 'https://www.douguo.com' + p.path
    if p.hostname in ('www.xiaohongshu.com', 'xiaohongshu.com'):
        match = re.fullmatch(r'/(?:explore|discovery/item)/([a-fA-F0-9]{24})/?', p.path)
        if match:
            return 'https://www.xiaohongshu.com/explore/' + match[1].lower()
    if p.hostname in ('xhslink.com', 'www.xhslink.com') and re.fullmatch(r'/(?:[A-Za-z0-9]+/)?[A-Za-z0-9_-]{1,120}/?', p.path):
        return 'https://xhslink.com' + p.path.rstrip('/')
    raise ValueError('仅支持豆果菜谱、小红书 explore/discovery/item 笔记和 xhslink.com 分享短链')

def xhs_fetch_url(value):
    value = import_url(value)
    canonical = canonical_url(value)
    if not is_xiaohongshu(canonical):
        raise ValueError('小红书链接跳转到了不支持的平台')
    # Keep the original query byte-for-byte for signed share links, but never persist it.
    query = urlsplit(value).query
    p = urlsplit(canonical)
    return urlunsplit((p.scheme, p.netloc, urlsplit(value).path, query, ''))

"""Fetch one Douguo page; retry a transient connection failure once."""
import time
import httpx
from backend.core import canonical_url, parse_douguo


def fetch_recipe(url, *, transport=None):
    url = canonical_url(url)
    with httpx.Client(timeout=20, follow_redirects=False, transport=transport,
                      headers={'User-Agent':'ShiShi/0.1 (personal recipe organizer)'}) as client:
        for attempt in range(2):
            try:
                with client.stream('GET', url) as response:
                    if response.is_redirect:
                        raise ValueError('豆果返回了跳转页，请使用完整的菜谱链接')
                    if response.status_code == 404:
                        raise ValueError('这份豆果菜谱不存在或已删除，请检查链接')
                    if response.status_code == 403:
                        raise ValueError('豆果限制了本次访问，请稍后再试')
                    if response.status_code == 429:
                        raise ValueError('访问过于频繁，请稍后再试')
                    response.raise_for_status()
                    chunks, size = [], 0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > 3_000_000:
                            raise ValueError('页面内容过大，暂不支持导入')
                        chunks.append(chunk)
                    html = b''.join(chunks).decode('utf-8', errors='replace')
                return parse_douguo(html, url)
            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                if attempt == 1:
                    raise ValueError('连接豆果失败，已重试一次。请检查网络后重试；TLS 握手失败也会导致此错误。') from exc
                time.sleep(0.3)
            except httpx.TimeoutException as exc:
                raise ValueError('读取豆果页面超时，请稍后重试') from exc
            except httpx.HTTPStatusError as exc:
                raise ValueError(f'豆果返回 HTTP {exc.response.status_code}，请稍后重试') from exc
            except httpx.HTTPError as exc:
                raise ValueError('读取豆果页面失败，请检查网络后重试') from exc

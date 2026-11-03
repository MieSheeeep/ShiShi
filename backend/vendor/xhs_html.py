"""Adapted from ReaJason/xhs XhsClient.get_note_by_id_from_html.

Copyright (c) 2023 ReaJason. MIT License; see third_party/xhs-LICENSE.
Source revision: f4b62d9f8e4078e631fc6e4ec8e430bc711ee9f0, xhs/core.py.
Network, signing and session APIs are intentionally not included.
"""
import json
import re
from bs4 import BeautifulSoup


def camel_to_underscore(key):
    return re.sub(r'(?<!^)(?=[A-Z])', '_', key).lower()

def transform_json_keys(value):
    if isinstance(value, dict):
        return {camel_to_underscore(k): transform_json_keys(v) for k, v in value.items()}
    if isinstance(value, list):
        return [transform_json_keys(v) for v in value]
    return value

def extract_note(html, note_id):
    soup = BeautifulSoup(html, 'html.parser')
    for script in soup.find_all('script'):
        content = script.string or script.get_text()
        match = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.*\})\s*;?\s*$', content, re.S)
        if not match:
            continue
        # Unlike upstream's global replace, leave "undefined" inside JSON strings intact.
        raw = re.sub(r'"(?:\\.|[^"\\])*"|\bundefined\b',
                     lambda m: 'null' if m[0] == 'undefined' else m[0], match[1])
        try:
            state = transform_json_keys(json.loads(raw))
            note = state['note']['note_detail_map'][note_id]['note']
        except (ValueError, KeyError, TypeError):
            continue
        if isinstance(note, dict) and note:
            return note
    raise ValueError('未找到小红书笔记正文，可能需要登录、链接失效或页面结构已变化。请复制含 xsec_token 的完整分享链接后重试。')

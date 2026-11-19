"""生产部署防护：SQLite 日志模式、注册门槛与 AI 接口 SSRF 校验。

默认不设置任何环境变量时，与本地开发行为保持兼容：
- Windows 默认使用 MEMORY 日志模式，Linux/生产环境默认使用 WAL 并设置 busy_timeout；
- 默认开放注册、不要求邀请码；
- AI 接口地址默认禁止指向回环、内网和云主机元数据地址（如 169.254.169.254）。
"""
import ipaddress
import os
import secrets
import socket
import sys
from urllib.parse import urlparse

VALID_JOURNAL_MODES = {'WAL', 'MEMORY', 'DELETE'}
BLOCKED_HOSTS = {'localhost', 'metadata.google.internal', 'metadata'}
BLOCKED_SUFFIXES = ('.localhost', '.local', '.internal', '.localdomain')


def _env_bool(name, default):
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() not in {'0', 'false', 'no', 'off'}


def sqlite_journal_mode():
    """返回应启用的 SQLite journal_mode。"""
    configured = os.environ.get('SHISHI_SQLITE_JOURNAL_MODE', '').strip().upper()
    if configured in VALID_JOURNAL_MODES:
        return configured
    # Windows 本地环境保留 MEMORY 兼容；Linux/容器部署默认使用 WAL 防止断电或崩溃损库。
    return 'MEMORY' if sys.platform == 'win32' else 'WAL'


def configure_sqlite_connection(dbapi_connection):
    """在 SQLite 连接建立时设置日志模式与锁等待时间。"""
    mode = sqlite_journal_mode()
    dbapi_connection.execute(f'PRAGMA journal_mode={mode}')
    dbapi_connection.execute('PRAGMA busy_timeout=5000')
    if mode == 'WAL':
        dbapi_connection.execute('PRAGMA synchronous=NORMAL')


def register_policy():
    """返回当前站点的注册策略，供前端登录页展示使用。"""
    allow = _env_bool('SHISHI_ALLOW_REGISTER', True)
    invite = os.environ.get('SHISHI_INVITE_CODE', '').strip()
    return {'allow_register': allow, 'invite_required': bool(allow and invite)}


def check_registration(invite_code=''):
    """校验当前是否允许注册以及邀请码是否匹配。"""
    if not _env_bool('SHISHI_ALLOW_REGISTER', True):
        raise PermissionError('当前未开放公开注册，请联系管理员')
    expected = os.environ.get('SHISHI_INVITE_CODE', '').strip()
    if expected:
        provided = (invite_code or '').strip()
        if not provided or not secrets.compare_digest(provided, expected):
            raise ValueError('邀请码无效，请联系管理员获取')


FAKE_IP_NET = ipaddress.ip_network('198.18.0.0/15')


def _is_forbidden_ip(ip_obj, allow_fake_ip=False):
    if isinstance(ip_obj, ipaddress.IPv4Address) and ip_obj in FAKE_IP_NET:
        return not allow_fake_ip
    return (
        ip_obj.is_private
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_multicast
        or ip_obj.is_reserved
        or ip_obj.is_unspecified
    )


def validate_ai_base_url(url):
    """校验用户填写的 AI 接口 Base URL，防止 SSRF 探测本机、内网或云厂商元数据服务。

    传入空字符串时直接返回空字符串（表示清空配置或沿用默认值）。
    本地自建模型代理需要访问内网地址时，可显式设置 ``SHISHI_ALLOW_PRIVATE_AI_URL=1``。
    """
    cleaned = (url or '').strip()
    if not cleaned:
        return ''
    parsed = urlparse(cleaned)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname:
        raise ValueError('AI 接口地址必须是以 http:// 或 https:// 开头的完整网址')
    if parsed.username or parsed.password:
        raise ValueError('AI 接口地址不能包含内嵌账号密码')

    if _env_bool('SHISHI_ALLOW_PRIVATE_AI_URL', False):
        return cleaned.rstrip('/')

    host = parsed.hostname.strip().lower().rstrip('.')
    if host in BLOCKED_HOSTS or host.endswith(BLOCKED_SUFFIXES):
        raise ValueError('AI 接口地址不能指向本机或内网地址')

    try:
        ip_obj = ipaddress.ip_address(host)
    except ValueError:
        ip_obj = None

    if ip_obj is not None:
        if _is_forbidden_ip(ip_obj):
            raise ValueError('AI 接口地址不能指向本机、内网或云主机元数据地址')
        return cleaned.rstrip('/')

    try:
        infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == 'https' else 80), type=socket.SOCK_STREAM)
    except OSError:
        # 离线或临时 DNS 不可达时放行，交由后续 HTTP 请求返回明确网络错误。
        return cleaned.rstrip('/')

    for info in infos:
        addr = info[4][0].split('%')[0]
        try:
            resolved = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if _is_forbidden_ip(resolved, allow_fake_ip=True):
            raise ValueError('AI 接口地址解析到了本机或内网 IP，已拒绝访问')

    return cleaned.rstrip('/')

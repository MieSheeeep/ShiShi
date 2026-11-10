"""账号、密码哈希与登录会话令牌。

密码使用标准库 scrypt 加盐哈希，数据库只保存摘要；登录后在 sessions 表中
保存令牌的 SHA-256 摘要，明文令牌仅返回给客户端，服务端不落库。
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

SCRYPT_N, SCRYPT_R, SCRYPT_P = 2 ** 14, 8, 1
TOKEN_DAYS = 30
USERNAME_MIN, USERNAME_MAX = 3, 32
PASSWORD_MIN, PASSWORD_MAX = 6, 128


def _now():
    return datetime.now(timezone.utc)


def _clock(moment):
    return moment.isoformat()


def hash_password(password):
    """生成 ``scrypt$n$r$p$salt$digest`` 格式的密码摘要。"""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode('utf-8'), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32)
    return f'scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${digest.hex()}'


def verify_password(password, stored):
    """常量时间校验密码，摘要格式异常时按不匹配处理。"""
    try:
        algorithm, n, r, p, salt, digest = stored.split('$')
        if algorithm != 'scrypt':
            return False
        candidate = hashlib.scrypt(password.encode('utf-8'), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p), dklen=len(bytes.fromhex(digest)))
    except (AttributeError, TypeError, ValueError):
        return False
    return secrets.compare_digest(candidate.hex(), digest)


def _token_digest(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def _public(row):
    return {'id': row['id'], 'username': row['username'], 'created_at': row['created_at']}


def initialize(engine):
    """建立账号与会话表，可重复执行。"""
    with engine.begin() as db:
        db.execute(text('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT,username TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,created_at TEXT NOT NULL)'))
        db.execute(text('CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY,user_id INTEGER NOT NULL,created_at TEXT NOT NULL,expires_at TEXT NOT NULL)'))


def clean_username(username):
    name = (username or '').strip()
    if not USERNAME_MIN <= len(name) <= USERNAME_MAX:
        raise ValueError(f'用户名长度需在 {USERNAME_MIN} 到 {USERNAME_MAX} 个字符之间')
    if any(character.isspace() for character in name):
        raise ValueError('用户名不能包含空白字符')
    return name


def create_user(engine, username, password):
    """注册账号；用户名重复抛 LookupError，格式不合法抛 ValueError。"""
    name = clean_username(username)
    if not PASSWORD_MIN <= len(password) <= PASSWORD_MAX:
        raise ValueError(f'密码长度需在 {PASSWORD_MIN} 到 {PASSWORD_MAX} 个字符之间')
    created = _clock(_now())
    with engine.begin() as db:
        if db.execute(text('SELECT id FROM users WHERE username=:name'), {'name': name}).first():
            raise LookupError('这个用户名已经被注册')
        result = db.execute(text('INSERT INTO users(username,password_hash,created_at) VALUES(:name,:password,:created)'), {'name': name, 'password': hash_password(password), 'created': created})
        user_id = result.lastrowid
    return {'id': user_id, 'username': name, 'created_at': created}


def authenticate(engine, username, password):
    """校验账号密码，成功返回用户信息，失败返回 None。"""
    name = (username or '').strip()
    with engine.connect() as db:
        row = db.execute(text('SELECT id,username,password_hash,created_at FROM users WHERE username=:name'), {'name': name}).mappings().first()
    if not row or not verify_password(password, row['password_hash']):
        return None
    return _public(row)


def issue_token(engine, user_id):
    """签发新的登录令牌，并顺带清理过期会话。"""
    token = secrets.token_urlsafe(32)
    now = _now()
    with engine.begin() as db:
        db.execute(text('DELETE FROM sessions WHERE expires_at < :now'), {'now': _clock(now)})
        db.execute(text('INSERT INTO sessions(token_hash,user_id,created_at,expires_at) VALUES(:hash,:user,:created,:expires)'), {'hash': _token_digest(token), 'user': user_id, 'created': _clock(now), 'expires': _clock(now + timedelta(days=TOKEN_DAYS))})
    return token


def resolve_token(engine, token):
    """按令牌查找有效会话，过期或不存在返回 None。"""
    if not token:
        return None
    with engine.connect() as db:
        row = db.execute(text('SELECT u.id,u.username,u.created_at,s.expires_at FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=:hash'), {'hash': _token_digest(token)}).mappings().first()
    if not row:
        return None
    if row['expires_at'] <= _clock(_now()):
        revoke_token(engine, token)
        return None
    return _public(row)


def revoke_token(engine, token):
    """退出登录：删除令牌对应的会话。"""
    if not token:
        return
    with engine.begin() as db:
        db.execute(text('DELETE FROM sessions WHERE token_hash=:hash'), {'hash': _token_digest(token)})
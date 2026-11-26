"""Account-scoped profile settings: avatar picture and display nickname."""
import json
import re

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from backend import media

AVATAR_URL = re.compile(r'/api/media/[a-f0-9]{64}\.(?:jpg|png|webp)')


class Avatar(BaseModel):
    url: str = ''


class Nickname(BaseModel):
    nickname: str = Field(default='', max_length=24)


def install(app, engine, current_user):
    def key(user_id, name):
        return f'{user_id}:{name}'

    def read(user_id, name, field):
        with engine.connect() as db:
            row = db.execute(text('SELECT body FROM settings WHERE key=:key'), {'key': key(user_id, name)}).first()
        return json.loads(row.body).get(field, '') if row else ''

    def write(user_id, name, field, value):
        with engine.begin() as db:
            if value:
                db.execute(text('INSERT INTO settings(key,body) VALUES(:key,:body) '
                                'ON CONFLICT(key) DO UPDATE SET body=excluded.body'),
                           {'key': key(user_id, name), 'body': json.dumps({field: value}, ensure_ascii=False)})
            else:
                db.execute(text('DELETE FROM settings WHERE key=:key'), {'key': key(user_id, name)})

    @app.get('/api/profile/avatar')
    def read_avatar(user: dict = Depends(current_user)):
        """返回当前账号的头像地址，未设置时为空字符串。"""
        return {'url': read(user['id'], 'avatar', 'url')}

    @app.put('/api/profile/avatar')
    def save_avatar(body: Avatar, user: dict = Depends(current_user)):
        """更换头像；传空字符串恢复为用户名首字母。"""
        url = body.url.strip()
        if url and (not AVATAR_URL.fullmatch(url) or not (media.MEDIA_DIR / url.rsplit('/', 1)[-1]).is_file()):
            raise HTTPException(422, '请先通过上传接口保存头像图片')
        write(user['id'], 'avatar', 'url', url)
        return {'url': url}

    @app.get('/api/profile/nickname')
    def read_nickname(user: dict = Depends(current_user)):
        """返回当前账号的昵称，未设置时为空字符串，由前端回退显示用户名。"""
        return {'nickname': read(user['id'], 'nickname', 'nickname')}

    @app.put('/api/profile/nickname')
    def save_nickname(body: Nickname, user: dict = Depends(current_user)):
        """保存昵称；传空字符串恢复为用户名。"""
        nickname = body.nickname.strip()
        write(user['id'], 'nickname', 'nickname', nickname)
        return {'nickname': nickname}

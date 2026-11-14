"""SQLite 食谱文档、标签目录与按用户隔离的存储迁移。

存储层所有读写都带 ``user_id``：食谱、标签分组、采购清单和设置属于各自的账号，
不同用户看不到、也改不到对方的数据。升级前的单用户数据在首个账号注册时认领。
"""
import json
import sqlite3

from sqlalchemy import inspect, text

from backend import auth
from backend.recipe_schema import Recipe, first_picture, now, new_id, snapshot
from backend.seed import examples

SEASON_GROUP = '四季'
SEASONS = ('春天', '夏天', '秋天', '冬天')


def _columns(engine, table):
    inspector = inspect(engine)
    return [column['name'] for column in inspector.get_columns(table)] if inspector.has_table(table) else []


def _owned(user_id):
    """返回 (SQL 片段, 参数)，兼容尚未认领的旧数据（user_id 为空）。"""
    return ('user_id IS NULL', {}) if user_id is None else ('user_id=:user_id', {'user_id': user_id})


def _create_tables(db):
    db.execute(text('CREATE TABLE IF NOT EXISTS recipes (id INTEGER PRIMARY KEY,user_id INTEGER,source TEXT,body TEXT NOT NULL,UNIQUE(user_id,source))'))
    db.execute(text('CREATE TABLE IF NOT EXISTS tag_groups (id TEXT PRIMARY KEY,user_id INTEGER,name TEXT NOT NULL,UNIQUE(user_id,name))'))
    db.execute(text('CREATE TABLE IF NOT EXISTS tags (id TEXT PRIMARY KEY,group_id TEXT NOT NULL,name TEXT NOT NULL,UNIQUE(group_id,name))'))
    db.execute(text('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY,body TEXT NOT NULL)'))
    db.execute(text('CREATE TABLE IF NOT EXISTS shopping (user_id INTEGER PRIMARY KEY,body TEXT NOT NULL)'))


def _rebuild_single_user_tables(engine):
    """把旧版全局唯一的表改成按用户唯一，并补上 user_id 列。"""
    if 'user_id' not in _columns(engine, 'recipes'):
        with engine.begin() as db:
            db.execute(text('ALTER TABLE recipes RENAME TO recipes_single_user'))
            db.execute(text('CREATE TABLE recipes (id INTEGER PRIMARY KEY,user_id INTEGER,source TEXT,body TEXT NOT NULL,UNIQUE(user_id,source))'))
            db.execute(text('INSERT INTO recipes(id,user_id,source,body) SELECT id,NULL,source,body FROM recipes_single_user'))
            db.execute(text('DROP TABLE recipes_single_user'))
    if 'user_id' not in _columns(engine, 'tag_groups'):
        with engine.begin() as db:
            db.execute(text('ALTER TABLE tag_groups RENAME TO tag_groups_single_user'))
            db.execute(text('CREATE TABLE tag_groups (id TEXT PRIMARY KEY,user_id INTEGER,name TEXT NOT NULL,UNIQUE(user_id,name))'))
            db.execute(text('INSERT INTO tag_groups(id,user_id,name) SELECT id,NULL,name FROM tag_groups_single_user'))
            db.execute(text('DROP TABLE tag_groups_single_user'))
    if 'user_id' not in _columns(engine, 'shopping'):
        with engine.begin() as db:
            old = db.execute(text('SELECT body FROM shopping WHERE id=1')).first()
            db.execute(text('DROP TABLE shopping'))
            db.execute(text('CREATE TABLE shopping (user_id INTEGER PRIMARY KEY,body TEXT NOT NULL)'))
            if old:
                db.execute(text("INSERT INTO settings(key,body) VALUES('legacy:shopping',:body) ON CONFLICT(key) DO UPDATE SET body=excluded.body"), {'body': old.body})


def _group(db, name, user_id):
    """查找或创建用户自己的标签分组。"""
    name = name.strip()
    if not name or len(name) > 80:
        raise ValueError('标签分组名称不能为空且不超过 80 字')
    condition, params = _owned(user_id)
    row = db.execute(text(f'SELECT id,name FROM tag_groups WHERE name=:name AND {condition}'), dict(params, name=name)).mappings().first()
    if row:
        return dict(row)
    item = {'id': new_id(), 'name': name, 'user_id': user_id}
    db.execute(text('INSERT INTO tag_groups(id,user_id,name) VALUES(:id,:user_id,:name)'), item)
    return item


def _tag(db, group_id, name, user_id):
    """在指定分组下查找或创建标签，分组必须属于当前用户。"""
    name = name.strip()
    if not name or len(name) > 80:
        raise ValueError('标签名称不能为空且不超过 80 字')
    condition, params = _owned(user_id)
    if not db.execute(text(f'SELECT id FROM tag_groups WHERE id=:group_id AND {condition}'), dict(params, group_id=group_id)).first():
        raise ValueError('标签分组不存在')
    row = db.execute(text('SELECT id,group_id,name FROM tags WHERE group_id=:group_id AND name=:name'), {'group_id': group_id, 'name': name}).mappings().first()
    if row:
        return dict(row)
    item = {'id': new_id(), 'group_id': group_id, 'name': name}
    db.execute(text('INSERT INTO tags(id,group_id,name) VALUES(:id,:group_id,:name)'), item)
    return item


def tag_ids(db, choices, user_id):
    """把编辑器提交的标签选择解析成当前用户的标签 ID。"""
    ids = []
    condition, params = _owned(user_id)
    for choice in choices:
        if choice.get('id'):
            owned = db.execute(text(f'SELECT t.id FROM tags t JOIN tag_groups g ON t.group_id=g.id WHERE t.id=:id AND g.{condition}'), dict(params, id=choice['id'])).first()
            if not owned:
                raise ValueError('标签已被删除，请重新选择')
            tid = choice['id']
        else:
            group = _group(db, choice.get('group', '我的分类'), user_id)
            tid = _tag(db, group['id'], choice.get('name', ''), user_id)['id']
        if tid not in ids:
            ids.append(tid)
    return ids


def initialize(engine, seed=True):
    """建表、升级旧版单用户表，并把 V1 食谱文档迁移到 V2。"""
    with engine.begin() as db:
        _create_tables(db)
    _rebuild_single_user_tables(engine)
    auth.initialize(engine)
    with engine.connect() as db:
        old = [(row.id, json.loads(row.body)) for row in db.execute(text('SELECT id,body FROM recipes'))]
    pending = [(rid, body) for rid, body in old if body.get('schema_version') != 2]
    path = engine.url.database
    if pending and path and path != ':memory:':
        stamp = now().replace(':', '').replace('.', '')
        with sqlite3.connect(path) as source, sqlite3.connect(str(path) + '.pre-v2-' + stamp + '.bak') as backup:
            source.backup(backup)
    with engine.begin() as db:
        for rid, raw in pending:
            body = Recipe.model_validate(raw).model_dump()
            body['original_snapshot'] = snapshot(body, 'legacy_saved')
            body['tag_ids'] = tag_ids(db, body.pop('tags'), None)
            db.execute(text('UPDATE recipes SET body=:body WHERE id=:id'), {'id': rid, 'body': json.dumps(body, ensure_ascii=False)})
    backfill_demo_covers(engine)
    backfill_season_tags(engine)


def backfill_season_tags(engine):
    """为已有账号补上四季分组，并给内置演示食谱补四季标签。"""
    seasons = {item['name']: next(c['name'] for c in item['tags'] if c.get('group') == SEASON_GROUP) for item in examples()}
    with engine.begin() as db:
        users = [row['user_id'] for row in db.execute(text('SELECT DISTINCT user_id FROM tag_groups WHERE user_id IS NOT NULL')).mappings()]
        for user_id in users:
            group = _group(db, SEASON_GROUP, user_id)
            ids = {name: _tag(db, group['id'], name, user_id)['id'] for name in SEASONS}
            for row in db.execute(text('SELECT id,body FROM recipes WHERE user_id=:user_id'), {'user_id': user_id}).all():
                body = json.loads(row.body)
                if body.get('source', {}).get('author') != '食拾示例':
                    continue
                tid = ids.get(seasons.get(body.get('name')))
                if tid and tid not in body.get('tag_ids', []):
                    body['tag_ids'] = body.get('tag_ids', []) + [tid]
                    db.execute(text('UPDATE recipes SET body=:body WHERE id=:id'), {'id': row.id, 'body': json.dumps(body, ensure_ascii=False)})


def backfill_demo_covers(engine):
    """为升级前创建的内置演示食谱补上实物封面，不覆盖用户自己选的封面。"""
    covers = {item['name']: item['cover'] for item in examples()}
    with engine.begin() as db:
        for row in db.execute(text('SELECT id,body FROM recipes')):
            body = json.loads(row.body)
            if body.get('cover') or body.get('source', {}).get('author') != '食拾示例':
                continue
            cover = covers.get(body.get('name'))
            if not cover:
                continue
            body['cover'] = cover
            db.execute(text('UPDATE recipes SET body=:body WHERE id=:id'), {'id': row.id, 'body': json.dumps(body, ensure_ascii=False)})


def claim_legacy(engine, user_id):
    """把升级前没有归属的本地数据交给首个注册的账号。"""
    moved = 0
    with engine.begin() as db:
        moved = db.execute(text('UPDATE recipes SET user_id=:user_id WHERE user_id IS NULL'), {'user_id': user_id}).rowcount
        db.execute(text('UPDATE tag_groups SET user_id=:user_id WHERE user_id IS NULL'), {'user_id': user_id})
        for key in ('pantry', 'seeded'):
            row = db.execute(text('SELECT body FROM settings WHERE key=:key'), {'key': key}).first()
            if row:
                db.execute(text('DELETE FROM settings WHERE key=:key'), {'key': key})
                db.execute(text('INSERT INTO settings(key,body) VALUES(:key,:body) ON CONFLICT(key) DO UPDATE SET body=excluded.body'), {'key': f'{user_id}:{key}', 'body': row.body})
        row = db.execute(text("SELECT body FROM settings WHERE key='legacy:shopping'")).first()
        if row:
            db.execute(text("DELETE FROM settings WHERE key='legacy:shopping'"))
            db.execute(text('INSERT INTO shopping(user_id,body) VALUES(:user_id,:body) ON CONFLICT(user_id) DO UPDATE SET body=excluded.body'), {'user_id': user_id, 'body': row.body})
    return moved > 0


def seed_user(engine, user_id):
    """为新账号复制内置演示食谱，方便直接体验完整流程。"""
    with engine.begin() as db:
        for raw in examples():
            body = Recipe.model_validate(raw).model_dump()
            body['original_snapshot'] = snapshot(body, 'example')
            body['tag_ids'] = tag_ids(db, body.pop('tags'), user_id)
            db.execute(text('INSERT INTO recipes(user_id,source,body) VALUES(:user_id,NULL,:body)'), {'user_id': user_id, 'body': json.dumps(body, ensure_ascii=False)})


def bootstrap_user(engine, user_id):
    """注册成功后准备默认分组与演示食谱；认领到旧数据的账号不再重复导入。"""
    claimed = claim_legacy(engine, user_id)
    with engine.begin() as db:
        for name in ('我的分类', '厨具', '口味', SEASON_GROUP):
            group = _group(db, name, user_id)
            if name == SEASON_GROUP:
                for season in SEASONS:
                    _tag(db, group['id'], season, user_id)
    if not claimed:
        seed_user(engine, user_id)


def catalogue(engine, user_id=None):
    """返回用户自己的标签分组与标签目录。"""
    condition, params = _owned(user_id)
    with engine.connect() as db:
        groups = [dict(row) for row in db.execute(text(f'SELECT id,name FROM tag_groups WHERE {condition} ORDER BY rowid'), params).mappings()]
        tags = [dict(row) for row in db.execute(text(f'SELECT t.id,t.name,t.group_id,g.name AS "group" FROM tags t JOIN tag_groups g ON t.group_id=g.id WHERE g.{condition} ORDER BY t.rowid'), params).mappings()]
    return {'groups': groups, 'tags': tags}


def list_recipes(engine, user_id=None):
    """列出用户的食谱，并挂上当前有效的标签信息。"""
    tags = {tag['id']: tag for tag in catalogue(engine, user_id)['tags']}
    condition, params = _owned(user_id)
    rows = []
    with engine.connect() as db:
        for row in db.execute(text(f'SELECT id,body FROM recipes WHERE {condition} ORDER BY id DESC'), params):
            body = json.loads(row.body)
            body['tag_ids'] = [tid for tid in body.get('tag_ids', []) if tid in tags]
            body['tags'] = [tags[tid] for tid in body['tag_ids']]
            rows.append(dict(body, id=row.id))
    return rows


def write_recipe(engine, recipe, user_id, rid=None):
    """新增或更新食谱；更新时只允许修改自己的记录。"""
    body = recipe.model_dump()
    from backend.core import normalize
    for ingredient in body['ingredients']:
        ingredient['name'] = normalize(ingredient['name'])
    with engine.begin() as db:
        if rid is not None:
            row = db.execute(text('SELECT body FROM recipes WHERE id=:id AND user_id=:user_id'), {'id': rid, 'user_id': user_id}).first()
            if row is None:
                raise LookupError('食谱不存在')
            old = json.loads(row.body)
            body['original_snapshot'] = old.get('original_snapshot')
            body['created_at'] = old.get('created_at', body['created_at'])
            for key in ('original_text', 'original_images', 'imported_at'):
                body['source'][key] = old.get('source', {}).get(key, body['source'].get(key))
        if body.get('original_snapshot') is None:
            body['original_snapshot'] = snapshot(body, 'manual_entry' if not body['source']['url'] else 'saved')
        if not body.get('cover'):
            body['cover'] = first_picture(body)
        body['tag_ids'] = tag_ids(db, body.pop('tags'), user_id)
        body['updated_at'] = now()
        params = {'source': body['source']['url'] or None, 'body': json.dumps(body, ensure_ascii=False), 'user_id': user_id}
        if rid is None:
            result = db.execute(text('INSERT INTO recipes(user_id,source,body) VALUES(:user_id,:source,:body)'), params)
            rid = result.lastrowid
        else:
            db.execute(text('UPDATE recipes SET source=:source,body=:body WHERE id=:id AND user_id=:user_id'), dict(params, id=rid))
    return next(r for r in list_recipes(engine, user_id) if r['id'] == rid)


def delete_recipe(engine, rid, user_id):
    """删除自己的食谱，返回是否命中。"""
    with engine.begin() as db:
        result = db.execute(text('DELETE FROM recipes WHERE id=:id AND user_id=:user_id'), {'id': rid, 'user_id': user_id})
    return result.rowcount > 0


def create_group(engine, name, user_id):
    with engine.begin() as db:
        return _group(db, name, user_id)


def create_tag(engine, group_id, name, user_id):
    with engine.begin() as db:
        item = _tag(db, group_id, name, user_id)
    return next(tag for tag in catalogue(engine, user_id)['tags'] if tag['id'] == item['id'])


def rename_item(engine, table, item_id, name, user_id):
    """重命名自己的分组或标签；标签改名会同步到所有关联食谱读取结果。"""
    if table not in ('tags', 'tag_groups'):
        raise ValueError('无效标签类型')
    name = name.strip()
    if not name or len(name) > 80:
        raise ValueError('名称不能为空且不超过 80 字')
    condition, params = _owned(user_id)
    with engine.begin() as db:
        if table == 'tag_groups':
            result = db.execute(text(f'UPDATE tag_groups SET name=:name WHERE id=:id AND {condition}'), dict(params, id=item_id, name=name))
        else:
            result = db.execute(text(f'UPDATE tags SET name=:name WHERE id=:id AND group_id IN (SELECT id FROM tag_groups WHERE {condition})'), dict(params, id=item_id, name=name))
        if not result.rowcount:
            raise LookupError('标签或分组不存在')
    return catalogue(engine, user_id)


def delete_item(engine, table, item_id, user_id):
    """删除自己的分组或标签，并清理自己食谱中的引用。"""
    if table not in ('tags', 'tag_groups'):
        raise ValueError('无效标签类型')
    condition, params = _owned(user_id)
    with engine.begin() as db:
        if table == 'tag_groups':
            if db.execute(text(f'SELECT id FROM tags WHERE group_id=:id'), {'id': item_id}).first():
                raise ValueError('请先移除分组内的标签')
            result = db.execute(text(f'DELETE FROM tag_groups WHERE id=:id AND {condition}'), dict(params, id=item_id))
            if not result.rowcount:
                raise LookupError('标签或分组不存在')
        else:
            owned = db.execute(text(f'SELECT t.id FROM tags t JOIN tag_groups g ON t.group_id=g.id WHERE t.id=:id AND g.{condition}'), dict(params, id=item_id)).first()
            if not owned:
                raise LookupError('标签或分组不存在')
            rows = list(db.execute(text(f'SELECT id,body FROM recipes WHERE {condition}'), params))
            for row in rows:
                body = json.loads(row.body)
                if item_id in body.get('tag_ids', []):
                    body['tag_ids'] = [tid for tid in body['tag_ids'] if tid != item_id]
                    db.execute(text('UPDATE recipes SET body=:body WHERE id=:id'), {'id': row.id, 'body': json.dumps(body, ensure_ascii=False)})
            db.execute(text('DELETE FROM tags WHERE id=:id'), {'id': item_id})
    return {'ok': True}


def read_list(engine, user_id):
    """读取用户的采购清单。"""
    with engine.connect() as db:
        row = db.execute(text('SELECT body FROM shopping WHERE user_id=:user_id'), {'user_id': user_id}).first()
    return json.loads(row.body) if row else []


def save_list(engine, user_id, items):
    """覆盖保存用户的采购清单。"""
    with engine.begin() as db:
        db.execute(text('INSERT INTO shopping(user_id,body) VALUES(:user_id,:body) ON CONFLICT(user_id) DO UPDATE SET body=excluded.body'), {'user_id': user_id, 'body': json.dumps(items, ensure_ascii=False)})


def read_settings(engine, user_id):
    """读取用户的常备食材设置。"""
    with engine.connect() as db:
        row = db.execute(text('SELECT body FROM settings WHERE key=:key'), {'key': f'{user_id}:pantry'}).first()
    return json.loads(row.body) if row else {'ingredients': [], 'staples': ['盐', '油']}


def save_settings(engine, user_id, body):
    """保存用户的常备食材设置。"""
    with engine.begin() as db:
        db.execute(text('INSERT INTO settings(key,body) VALUES(:key,:body) ON CONFLICT(key) DO UPDATE SET body=excluded.body'), {'key': f'{user_id}:pantry', 'body': body.model_dump_json()})
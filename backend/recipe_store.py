"""SQLite recipe documents and reusable tag registry, with atomic V1 migration."""
import json
import sqlite3
from sqlalchemy import text, inspect
from backend.recipe_schema import Recipe, now, new_id, snapshot
from backend.seed import examples

def _group(db,name):
    name=name.strip()
    if not name or len(name)>80:raise ValueError('标签分组名称不能为空且不超过 80 字')
    row=db.execute(text('SELECT id,name FROM tag_groups WHERE name=:n'),{'n':name}).mappings().first()
    if row:return dict(row)
    item={'id':new_id(),'name':name}
    db.execute(text('INSERT INTO tag_groups(id,name) VALUES(:id,:name)'),item)
    return item

def _tag(db,group_id,name):
    name=name.strip()
    if not name or len(name)>80:raise ValueError('标签名称不能为空且不超过 80 字')
    if not db.execute(text('SELECT id FROM tag_groups WHERE id=:id'),{'id':group_id}).first():raise ValueError('标签分组不存在')
    row=db.execute(text('SELECT id,group_id,name FROM tags WHERE group_id=:g AND name=:n'),{'g':group_id,'n':name}).mappings().first()
    if row:return dict(row)
    item={'id':new_id(),'group_id':group_id,'name':name}
    db.execute(text('INSERT INTO tags(id,group_id,name) VALUES(:id,:group_id,:name)'),item)
    return item

def tag_ids(db,choices):
    ids=[]
    for choice in choices:
        if choice.get('id'):
            if not db.execute(text('SELECT id FROM tags WHERE id=:id'),{'id':choice['id']}).first():raise ValueError('标签已被删除，请重新选择')
            tid=choice['id']
        else:
            group=_group(db,choice.get('group','我的分类'))
            tid=_tag(db,group['id'],choice.get('name',''))['id']
        if tid not in ids:ids.append(tid)
    return ids

def initialize(engine,seed=True):
    has_recipes=inspect(engine).has_table('recipes')
    old=[]
    if has_recipes:
        with engine.connect() as db:
            old=[(r.id,json.loads(r.body)) for r in db.execute(text('SELECT id,body FROM recipes'))]
    pending=[(rid,body) for rid,body in old if body.get('schema_version')!=2]
    path=engine.url.database
    if pending and path and path!=':memory:':
        stamp=now().replace(':','').replace('.','')
        with sqlite3.connect(path) as source,sqlite3.connect(str(path)+'.pre-v2-'+stamp+'.bak') as backup:
            source.backup(backup)
    with engine.begin() as db:
        db.execute(text('CREATE TABLE IF NOT EXISTS recipes (id INTEGER PRIMARY KEY,source TEXT UNIQUE,body TEXT NOT NULL)'))
        db.execute(text('CREATE TABLE IF NOT EXISTS shopping (id INTEGER PRIMARY KEY CHECK(id=1),body TEXT NOT NULL)'))
        db.execute(text('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY,body TEXT NOT NULL)'))
        db.execute(text('CREATE TABLE IF NOT EXISTS tag_groups (id TEXT PRIMARY KEY,name TEXT UNIQUE NOT NULL)'))
        db.execute(text('CREATE TABLE IF NOT EXISTS tags (id TEXT PRIMARY KEY,group_id TEXT NOT NULL,name TEXT NOT NULL,UNIQUE(group_id,name))'))
        for name in ('我的分类','厨具','口味'):_group(db,name)
        for rid,raw in pending:
            body=Recipe.model_validate(raw).model_dump()
            body['original_snapshot']=snapshot(body,'legacy_saved')
            body['tag_ids']=tag_ids(db,body.pop('tags'))
            db.execute(text('UPDATE recipes SET body=:body WHERE id=:id'),{'id':rid,'body':json.dumps(body,ensure_ascii=False)})
        if seed and not db.execute(text("SELECT key FROM settings WHERE key='seeded'")).first():
            if not old:
                for raw in examples():
                    body=Recipe.model_validate(raw).model_dump()
                    body['original_snapshot']=snapshot(body,'example')
                    body['tag_ids']=tag_ids(db,body.pop('tags'))
                    db.execute(text('INSERT INTO recipes(source,body) VALUES(NULL,:body)'),{'body':json.dumps(body,ensure_ascii=False)})
            db.execute(text("INSERT INTO settings(key,body) VALUES('seeded','true')"))

def catalogue(engine):
    with engine.connect() as db:
        groups=[dict(r) for r in db.execute(text('SELECT id,name FROM tag_groups ORDER BY rowid')).mappings()]
        tags=[dict(r) for r in db.execute(text('SELECT t.id,t.name,t.group_id,g.name AS "group" FROM tags t JOIN tag_groups g ON t.group_id=g.id ORDER BY t.rowid')).mappings()]
    return {'groups':groups,'tags':tags}

def list_recipes(engine):
    tags={t['id']:t for t in catalogue(engine)['tags']}
    with engine.connect() as db:
        rows=[]
        for row in db.execute(text('SELECT id,body FROM recipes ORDER BY id DESC')):
            body=json.loads(row.body)
            body['tag_ids']=[tid for tid in body.get('tag_ids',[]) if tid in tags]
            body['tags']=[tags[tid] for tid in body['tag_ids']]
            rows.append(dict(body,id=row.id))
    return rows

def write_recipe(engine,recipe,rid=None):
    body=recipe.model_dump()
    from backend.core import normalize
    for ingredient in body['ingredients']:ingredient['name']=normalize(ingredient['name'])
    with engine.begin() as db:
        old=None
        if rid is not None:
            row=db.execute(text('SELECT body FROM recipes WHERE id=:id'),{'id':rid}).first()
            if row is None:raise LookupError('食谱不存在')
            old=json.loads(row.body)
            body['original_snapshot']=old.get('original_snapshot')
            body['created_at']=old.get('created_at',body['created_at'])
            for key in ('original_text','original_images','imported_at'):
                body['source'][key]=old.get('source',{}).get(key,body['source'].get(key))
        if body.get('original_snapshot') is None:body['original_snapshot']=snapshot(body,'manual_entry' if not body['source']['url'] else 'saved')
        body['tag_ids']=tag_ids(db,body.pop('tags'))
        body['updated_at']=now()
        params={'source':body['source']['url'] or None,'body':json.dumps(body,ensure_ascii=False)}
        if rid is None:
            result=db.execute(text('INSERT INTO recipes(source,body) VALUES(:source,:body)'),params);rid=result.lastrowid
        else:db.execute(text('UPDATE recipes SET source=:source,body=:body WHERE id=:id'),dict(params,id=rid))
    return next(r for r in list_recipes(engine) if r['id']==rid)

def create_group(engine,name):
    with engine.begin() as db:return _group(db,name)

def create_tag(engine,group_id,name):
    with engine.begin() as db:item=_tag(db,group_id,name)
    return next(t for t in catalogue(engine)['tags'] if t['id']==item['id'])

def rename_item(engine,table,item_id,name):
    if table not in ('tags','tag_groups'):raise ValueError('无效标签类型')
    name=name.strip()
    if not name or len(name)>80:raise ValueError('名称不能为空且不超过 80 字')
    with engine.begin() as db:
        result=db.execute(text(f'UPDATE {table} SET name=:name WHERE id=:id'),{'id':item_id,'name':name})
        if not result.rowcount:raise LookupError('标签或分组不存在')
    return catalogue(engine)

def delete_item(engine,table,item_id):
    if table not in ('tags','tag_groups'):raise ValueError('无效标签类型')
    with engine.begin() as db:
        if table=='tag_groups' and db.execute(text('SELECT id FROM tags WHERE group_id=:id'),{'id':item_id}).first():raise ValueError('请先移除分组内的标签')
        if table=='tags':
            rows=list(db.execute(text('SELECT id,body FROM recipes')))
            for row in rows:
                body=json.loads(row.body)
                if item_id in body.get('tag_ids',[]):
                    body['tag_ids']=[tid for tid in body['tag_ids'] if tid!=item_id]
                    db.execute(text('UPDATE recipes SET body=:body WHERE id=:id'),{'id':row.id,'body':json.dumps(body,ensure_ascii=False)})
        db.execute(text(f'DELETE FROM {table} WHERE id=:id'),{'id':item_id})
    return {'ok':True}

"""SQLite transactions and derived, retractable cooking milestones."""
import json
from datetime import datetime, timezone
from hashlib import sha256
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import text


def now():
    return datetime.now(timezone.utc).isoformat()


def initialize(engine):
    with engine.begin() as db:
        db.execute(text('CREATE TABLE IF NOT EXISTS cooking_sessions ('
                        'id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,'
                        'number INTEGER NOT NULL,client_id TEXT NOT NULL,version INTEGER NOT NULL,'
                        'state TEXT NOT NULL,cooked_on TEXT NOT NULL,started_at TEXT NOT NULL,'
                        'completed_at TEXT,updated_at TEXT NOT NULL,body TEXT NOT NULL,'
                        'UNIQUE(user_id,client_id),UNIQUE(user_id,number))'))
        db.execute(text('CREATE TABLE IF NOT EXISTS cooking_dishes ('
                        'user_id INTEGER NOT NULL,dish_key TEXT NOT NULL,status TEXT NOT NULL,'
                        'PRIMARY KEY(user_id,dish_key))'))
        db.execute(text('CREATE TABLE IF NOT EXISTS cooking_uploads ('
                        'user_id INTEGER NOT NULL,url TEXT NOT NULL,PRIMARY KEY(user_id,url))'))
        db.execute(text('CREATE TABLE IF NOT EXISTS cooking_recipe_instances ('
                        'user_id INTEGER NOT NULL,recipe_id INTEGER NOT NULL,instance_key TEXT UNIQUE NOT NULL,'
                        'PRIMARY KEY(user_id,recipe_id))'))
        db.execute(text('CREATE TRIGGER IF NOT EXISTS purge_cooking_recipe_instance AFTER DELETE ON recipes BEGIN '
                        'DELETE FROM cooking_recipe_instances WHERE user_id=OLD.user_id AND recipe_id=OLD.id; END'))
        db.execute(text('CREATE TRIGGER IF NOT EXISTS purge_cooking_user_instances AFTER DELETE ON users BEGIN '
                        'DELETE FROM cooking_recipe_instances WHERE user_id=OLD.id; END'))
        db.execute(text('CREATE TRIGGER IF NOT EXISTS purge_cooking AFTER DELETE ON users BEGIN '
                        'DELETE FROM cooking_sessions WHERE user_id=OLD.id; '
                        'DELETE FROM cooking_dishes WHERE user_id=OLD.id; '
                        'DELETE FROM cooking_uploads WHERE user_id=OLD.id; END'))


def recipe_instance(db, user_id, recipe_id):
    """Use the caller's write lock to allocate one server-owned recipe identity."""
    params = {'user': user_id, 'recipe': recipe_id}
    existing = db.execute(text('SELECT instance_key FROM cooking_recipe_instances '
                               'WHERE user_id=:user AND recipe_id=:recipe'), params).first()
    if existing:
        return existing.instance_key
    key = 'recipe:' + sha256(uuid4().bytes).hexdigest()
    db.execute(text('INSERT INTO cooking_recipe_instances(user_id,recipe_id,instance_key) '
                    'VALUES(:user,:recipe,:key)'), {**params, 'key': key})
    return key


def all_sessions(db, user_id):
    return [json.loads(row.body) for row in db.execute(text(
        'SELECT body FROM cooking_sessions WHERE user_id=:user'), {'user': user_id})]


def get(db, user_id, sid):
    row = db.execute(text('SELECT body FROM cooking_sessions WHERE user_id=:user AND id=:id'),
                     {'user': user_id, 'id': sid}).first()
    if row is None:
        raise HTTPException(404, '下厨记录不存在')
    return json.loads(row.body)


def save(db, user_id, session):
    db.execute(text('UPDATE cooking_sessions SET version=:version,state=:state,cooked_on=:cooked_on,'
                    'completed_at=:completed_at,updated_at=:updated_at,body=:body '
                    'WHERE id=:id AND user_id=:user'),
               {**{k: session[k] for k in ('version', 'state', 'cooked_on', 'completed_at', 'updated_at', 'id')},
                'user': user_id, 'body': json.dumps(session, ensure_ascii=False)})


def confirmed(session):
    outcomes = [dish['outcome'] for dish in session['dishes']]
    if 'pending' in outcomes or not any(o in ('success', 'practice') for o in outcomes):
        raise HTTPException(422, '请确认每道菜的结果，至少记录一道实际尝试')


def summary(db, user_id):
    sessions = sorted((s for s in all_sessions(db, user_id) if s['state'] == 'completed'),
                      key=lambda s: (s['completed_at'], s['id']))
    definitions = [('first-fire', '第一次开火', '留下一餐实际尝试'),
                   ('try-again', '再试一次', '同一道菜失手后再次尝试'),
                   ('three-dishes', '三道家常菜', '实际尝试三种菜'),
                   ('signature-dish', '我的拿手菜', '同一道菜在三餐中做成')]
    achievements = {key: {'id': key, 'title': title, 'description': desc, 'unlocked': False,
                           'session_id': None, 'unlocked_at': None} for key, title, desc in definitions}
    repertoire, practiced = {}, set()

    def unlock(key, session):
        if not achievements[key]['unlocked']:
            achievements[key].update(unlocked=True, session_id=session['id'], unlocked_at=session['completed_at'])

    for session in sessions:
        unlock('first-fire', session)
        for dish in session['dishes']:
            if dish['outcome'] not in ('success', 'practice'):
                continue
            key = dish['dish_key']
            if key in practiced:
                unlock('try-again', session)
            if dish['outcome'] == 'practice':
                practiced.add(key)
            entry = repertoire.setdefault(key, {'dish_key': key, 'name': dish['snapshot']['name'],
                'cover': dish['snapshot'].get('cover', ''), 'attempts': 0, 'successes': 0,
                'last_note': '', 'last_cooked_on': session['cooked_on'],
                'status': 'tried', 'sessions': []})
            entry['attempts'] += 1
            entry['successes'] += dish['outcome'] == 'success'
            entry['last_note'] = dish['note']
            entry['last_cooked_on'] = session['cooked_on']
            entry['sessions'].append(session['id'])
            if entry['successes'] >= 3:
                unlock('signature-dish', session)
            if len(repertoire) >= 3:
                unlock('three-dishes', session)
    for entry in repertoire.values():
        entry['status'] = ('signature' if entry['successes'] >= 3
                           else 'practice' if entry['successes'] < entry['attempts'] else 'tried')
    meals = len(sessions)
    return {'meals': meals, 'dishes': len(repertoire),
            'level': build_level(meals), 'percentile': account_percentile(db, user_id, meals),
            'achievements': list(achievements.values()), 'repertoire': list(repertoire.values())}


# 七档段位 + 无上限的巅峰星数，每档 3 星、每 2 餐一星；与 frontend/src/cookingLevels.js 必须同步。
TIERS = (('bronze', '倔强青铜', 0), ('silver', '秩序白银', 6), ('gold', '荣耀黄金', 12),
         ('platinum', '尊贵铂金', 18), ('diamond', '永恒钻石', 24), ('star', '至尊星耀', 30),
         ('king', '最强王者', 36), ('peak', '巅峰', 48))
STAR_STEP, STARS_PER_TIER = 2, 3


def build_level(meals):
    index = max(i for i, (_, _, low) in enumerate(TIERS) if meals >= low)
    tier_id, title, low = TIERS[index]
    peak = index == len(TIERS) - 1
    next_at = TIERS[index + 1][2] if not peak else None
    star = (meals - low) // STAR_STEP + 1
    return {'number': index + 1, 'tier': tier_id, 'title': title,
            'star': star if peak else min(STARS_PER_TIER, star),
            'next_at': next_at, 'remaining': max(0, next_at - meals) if next_at else 0}


def account_percentile(db, user_id, meals):
    """本机账号内的真实排名：统计有效餐次少于当前账号的账号占比。"""
    ids = [row[0] for row in db.execute(text('SELECT id FROM users')).all()]
    counts = dict(db.execute(text("SELECT user_id, COUNT(*) FROM cooking_sessions "
                                  "WHERE state='completed' GROUP BY user_id")).all())
    ahead = sum(1 for uid in ids if counts.get(uid, 0) < meals)
    return {'percent': round(ahead / len(ids) * 100) if ids else 0, 'accounts': len(ids), 'ahead': ahead}

"""Built-in kitchen quests: chapters, star rules, ranks, secrets and eggs.

The module deliberately owns the built-in content instead of the recipe table:
a quest must be playable on a brand-new account before the user imports a
single recipe. Sessions started from a quest carry ``quest_stage`` so later
edits to the catalog cannot rewrite somebody's cooking history.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256

from fastapi import Depends

from backend import cooking_store as store

SHANGHAI = timezone(timedelta(hours=8))

RANK_TIERS = (
    {'id': 'bronze', 'title': '青铜', 'min': 0},
    {'id': 'silver', 'title': '白银', 'min': 3},
    {'id': 'gold', 'title': '黄金', 'min': 7},
    {'id': 'platinum', 'title': '铂金', 'min': 12},
    {'id': 'diamond', 'title': '钻石', 'min': 18},
    {'id': 'star', 'title': '星耀', 'min': 25},
    {'id': 'king', 'title': '王者', 'min': 33},
)

STAR_RULES = (
    {'id': 'finish', 'title': '完成这一餐', 'detail': '把这道菜标记为「做成了」或「还想再练」并完成收尾。'},
    {'id': 'success', 'title': '把菜做成', 'detail': '至少有一次结果为「做成了」。'},
    {'id': 'memory', 'title': '留下色香味', 'detail': '做成的记录里至少有 1 张照片，并写下 8 个字以上的心得。'},
)

RANK_RULE = ('每完成一餐、其中有做成的菜 +1 分；整餐都标为「还想再练」，每累计 3 餐 +1 分；'
             '每集满 6 颗闯关星 +1 分。段位只升不降，新赛季重新起跑。')

BLIND_BOX_TWISTS = (
    '过程中随手拍 1 张灶台照',
    '出锅后给成品拍张俯拍大片',
    '留一句火候心得给下次的自己',
    '试着把台面顺手收拾干净再开吃',
    '挑战按步骤一口气做完不慌张',
)


def _ingredients(*rows):
    return [{'id': f'ing-{index}', 'name': name, 'amount': amount, 'kind': '食材'}
            for index, (name, amount) in enumerate(rows, 1)]


def _steps(*texts):
    return [{'id': f'st-{index}', 'text': text, 'images': []}
            for index, text in enumerate(texts, 1)]


CATALOG = (
    {
        'id': 'ch-1', 'number': 1, 'title': '初试灶火', 'subtitle': '10 分钟零门槛上手', 'badge': '灶台萌新',
        'stages': (
            {
                'id': 's-1', 'name': '番茄炒蛋', 'emoji': '🍅', 'cover': '/api/demo/tomato-egg.jpg',
                'minutes': 15, 'difficulty': 1, 'tip': '蛋液刚凝固就先盛出，最后回锅才够嫩滑。',
                'story': '第一口自己做的家常味，从一盘红黄相间开始。别急着追求完美，先把火点起来。',
                'secret': '蛋液里加一小勺清水，炒出来更蓬松；番茄先去皮，汤汁会更顺口。',
                'ingredients': _ingredients(('番茄', '2 个'), ('鸡蛋', '3 个'), ('小葱', '1 根'),
                                            ('盐', '2 g'), ('白糖', '3 g'), ('食用油', '15 ml')),
                'steps': _steps('番茄去蒂切块，小葱切葱花；鸡蛋加一小撮盐打散。',
                                '锅烧热倒油，蛋液下锅，凝固七成时先盛出。',
                                '原锅下番茄，中火炒出汁，加盐和白糖。',
                                '倒回鸡蛋快速翻匀，撒葱花出锅。'),
            },
            {
                'id': 's-2', 'name': '葱花鸡蛋饼', 'emoji': '🥞', 'cover': '/api/demo/scallion-egg-pancake.jpg',
                'minutes': 10, 'difficulty': 1, 'tip': '面糊调到能顺滑流下，小火摊平更不易糊。',
                'story': '一张饼，一把葱，十分钟就能端上桌。适合第一次独自掌控整口锅。',
                'secret': '面糊静置 5 分钟再摊，饼皮会更细腻；出锅前刷一点油，边缘更酥。',
                'ingredients': _ingredients(('鸡蛋', '2 个'), ('面粉', '80 g'), ('清水', '120 ml'),
                                            ('小葱', '2 根'), ('盐', '2 g'), ('食用油', '10 ml')),
                'steps': _steps('鸡蛋打散，加面粉、清水和盐，搅成顺滑面糊。',
                                '小葱切碎拌入面糊，静置 5 分钟。',
                                '平底锅刷薄油，小火倒入一勺面糊，转动锅摊平。',
                                '底面定型后翻面，两面微黄即可出锅。'),
            },
            {
                'id': 's-3', 'name': '清爽黄瓜拌豆腐', 'emoji': '🥒', 'cover': '/api/demo/cucumber-tofu-salad.jpg',
                'minutes': 10, 'difficulty': 1, 'tip': '豆腐沸水焯 30 秒去豆腥，放凉再拌更爽口。',
                'story': '不开大火也能完成的一道菜。把清爽和耐心一起拌进碗里。',
                'secret': '黄瓜先用盐腌 3 分钟倒掉水，拌出来不会出汤；最后淋香油再拌两下。',
                'ingredients': _ingredients(('黄瓜', '1 根'), ('嫩豆腐', '1 盒'), ('蒜', '2 瓣'),
                                            ('生抽', '10 ml'), ('香醋', '5 ml'), ('香油', '3 ml'), ('盐', '1 g')),
                'steps': _steps('豆腐切小块，沸水焯 30 秒后捞出放凉。',
                                '黄瓜拍裂切段，加一小撮盐腌 3 分钟，倒掉多余水分。',
                                '蒜切末，与生抽、香醋、香油调成料汁。',
                                '豆腐和黄瓜装盘，淋上料汁轻轻拌匀。'),
            },
        ),
    },
    {
        'id': 'ch-2', 'number': 2, 'title': '火候试炼', 'subtitle': '掌握煎、炒与焯水节奏', 'badge': '火候学徒',
        'stages': (
            {
                'id': 's-4', 'name': '香煎土豆', 'emoji': '🥔', 'cover': '/api/demo/pan-fried-potato.jpg',
                'minutes': 25, 'difficulty': 2, 'tip': '先煮到筷子能穿透，沥干小火慢煎才外脆里糯。',
                'story': '火候试炼的第一课：同样的土豆，快一点会焦，慢一点才香。',
                'secret': '土豆煮好后一定要沥干水，再下锅；煎的时候先别频繁翻面。',
                'ingredients': _ingredients(('土豆', '2 个'), ('盐', '3 g'), ('黑胡椒', '1 g'),
                                            ('食用油', '20 ml'), ('葱花', '少许')),
                'steps': _steps('土豆去皮切厚片，冷水下锅煮到筷子能穿透。',
                                '捞出沥干水分，平底锅倒油烧热。',
                                '土豆片下锅，中小火每面煎 3 分钟至金黄。',
                                '撒盐、黑胡椒和葱花，翻匀出锅。'),
            },
            {
                'id': 's-5', 'name': '蒜蓉西兰花', 'emoji': '🥦', 'cover': '/api/demo/garlic-broccoli.jpg',
                'minutes': 15, 'difficulty': 2, 'tip': '沸水加几滴油焯 1 分钟捞出，翠绿不发黄。',
                'story': '一盘绿意。学会焯水和爆香，素菜也能有锅气。',
                'secret': '焯水后立刻过凉水，颜色更绿；蒜末分两次下，一半爆香一半收尾。',
                'ingredients': _ingredients(('西兰花', '1 颗'), ('蒜', '4 瓣'), ('盐', '2 g'),
                                            ('蚝油', '10 ml'), ('食用油', '15 ml')),
                'steps': _steps('西兰花掰小朵，盐水浸泡 10 分钟后冲净。',
                                '沸水加几滴油，西兰花焯 1 分钟捞出过凉水。',
                                '锅中热油，下一半蒜末爆香。',
                                '倒入西兰花大火翻炒，加盐和蚝油，撒剩余蒜末出锅。'),
            },
            {
                'id': 's-6', 'name': '蒜香煎鸡胸', 'emoji': '🍗', 'cover': '',
                'minutes': 20, 'difficulty': 2, 'tip': '鸡胸划浅花刀腌 10 分钟，中小火每面煎 2 分钟。',
                'story': '把容易柴的鸡胸煎出汁水，是火候掌握得住的证明。',
                'secret': '腌的时候加一小勺淀粉和一点油，煎完静置 2 分钟再切，肉汁不会跑。',
                'ingredients': _ingredients(('鸡胸肉', '1 块'), ('蒜', '3 瓣'), ('生抽', '10 ml'),
                                            ('料酒', '5 ml'), ('黑胡椒', '1 g'), ('食用油', '15 ml')),
                'steps': _steps('鸡胸从中间片开，用刀背轻拍松，划几道浅花刀。',
                                '加蒜末、生抽、料酒、黑胡椒腌 10 分钟。',
                                '平底锅刷油，中小火每面煎 2 分钟。',
                                '关火盖盖焖 1 分钟，静置后切片。'),
            },
        ),
    },
    {
        'id': 'ch-3', 'number': 3, 'title': '慢火治愈', 'subtitle': '煮粥、焖炖与收汁功夫', 'badge': '烟火掌勺',
        'stages': (
            {
                'id': 's-7', 'name': '南瓜小米粥', 'emoji': '🥣', 'cover': '/api/demo/pumpkin-millet-porridge.jpg',
                'minutes': 35, 'difficulty': 2, 'tip': '水开后再下小米，转小火时不时搅底防粘锅。',
                'story': '慢火不是等待，是把时间也煮进味道里。',
                'secret': '小米先干炒 1 分钟再煮更香；南瓜后放，粥才不会浑成一团。',
                'ingredients': _ingredients(('小米', '80 g'), ('南瓜', '200 g'), ('清水', '900 ml'),
                                            ('冰糖', '少许')),
                'steps': _steps('小米淘洗两遍，南瓜去皮切小块。',
                                '锅中水烧开，下小米转小火煮 15 分钟。',
                                '加入南瓜继续煮 15 分钟，偶尔搅底。',
                                '南瓜软烂后按口味加冰糖，搅匀关火。'),
            },
            {
                'id': 's-8', 'name': '可乐鸡翅', 'emoji': '🍖', 'cover': '',
                'minutes': 30, 'difficulty': 3, 'tip': '鸡翅煎至两面微焦再倒可乐，最后大火收汁发亮。',
                'story': '甜咸交织的一锅，收汁的那一刻最有成就感。',
                'secret': '可乐分两次倒：第一次焖熟，第二次收汁；最后几秒一定要盯着锅。',
                'ingredients': _ingredients(('鸡翅中', '8 个'), ('可乐', '330 ml'), ('生抽', '15 ml'),
                                            ('姜', '3 片'), ('料酒', '10 ml'), ('食用油', '10 ml')),
                'steps': _steps('鸡翅两面划刀，冷水下锅加姜片和料酒焯水后擦干。',
                                '平底锅少油，鸡翅煎至两面微焦。',
                                '倒入可乐没过鸡翅，加生抽，中小火焖 15 分钟。',
                                '转大火收汁，不断翻动至汤汁发亮裹住鸡翅。'),
            },
            {
                'id': 's-9', 'name': '番茄炖牛腩', 'emoji': '🍲', 'cover': '',
                'minutes': 60, 'difficulty': 3, 'tip': '番茄先炒出浓汁，小火慢炖 50 分钟肉才软烂。',
                'story': '最后一关，把耐心交给小火。一锅炖好，整个厨房都会暖起来。',
                'secret': '牛腩焯水后用温水冲，别用冷水；番茄分两次放，一次炖底味，一次留果肉。',
                'ingredients': _ingredients(('牛腩', '500 g'), ('番茄', '3 个'), ('洋葱', '半个'),
                                            ('姜', '3 片'), ('生抽', '15 ml'), ('盐', '3 g'), ('食用油', '15 ml')),
                'steps': _steps('牛腩切块，冷水下锅焯水，捞出用温水冲净。',
                                '番茄切块，洋葱切丝；锅中热油炒香洋葱和姜片。',
                                '下番茄炒出浓汁，加入牛腩和生抽翻匀。',
                                '加热水没过食材，小火炖 50 分钟。',
                                '加盐调味，大火略收汁即可。'),
            },
        ),
    },
)


def _flat_stages():
    return tuple(stage for chapter in CATALOG for stage in chapter['stages'])


def find_stage(stage_id):
    for chapter in CATALOG:
        for stage in chapter['stages']:
            if stage['id'] == stage_id:
                return stage, chapter
    raise KeyError(stage_id)


def quest_snapshot(stage_id):
    """Return a self-contained cooking snapshot for one built-in stage."""
    stage, chapter = find_stage(stage_id)
    document = {
        'schema_version': 2,
        'name': stage['name'],
        'source': {'platform': 'shishi', 'url': '', 'author': '食拾',
                   'original_text': stage['story'], 'original_images': []},
        'minutes': str(stage['minutes']),
        'servings': '1-2 人',
        'emoji': stage['emoji'],
        'tags': [{'name': '厨房闯关', 'group': '内置'}],
        'tag_ids': [],
        'notes': stage['story'],
        'images': [],
        'cover': stage['cover'],
        'ingredients': deepcopy(stage['ingredients']),
        'steps': deepcopy(stage['steps']),
        'created_at': store.now(),
        'updated_at': store.now(),
        'quest_stage': stage_id,
        'quest_chapter': chapter['id'],
    }
    return document


def _effective_dishes(session):
    return [dish for dish in session.get('dishes', [])
            if dish.get('outcome') in ('success', 'practice')]


def _stage_dishes(sessions, stage):
    """Pair a stage with every completed attempt, including legacy records."""
    rows = []
    for session in sessions:
        for dish in _effective_dishes(session):
            if dish.get('quest_stage') == stage['id']:
                rows.append((session, dish))
            elif not dish.get('quest_stage') and dish.get('snapshot', {}).get('name') == stage['name']:
                # Before quest_stage existed, the built-in chapters launched
                # these dishes by name; keep that history in the new star map.
                rows.append((session, dish))
    rows.sort(key=lambda row: (row[0].get('completed_at') or '', row[0].get('id', 0)))
    return rows


def _dish_stars(dish):
    if dish.get('outcome') == 'practice':
        return 1
    if dish.get('outcome') != 'success':
        return 0
    photos = dish.get('photos') or []
    note = (dish.get('note') or '').strip()
    return 3 if photos and len(note) >= 8 else 2


def _rank(sessions, quest_stars):
    wins = sum(1 for session in sessions if any(d.get('outcome') == 'success' for d in _effective_dishes(session)))
    practice = len(sessions) - wins
    bonus = quest_stars // 6
    points = wins + practice // 3 + bonus
    index = max(i for i, tier in enumerate(RANK_TIERS) if points >= tier['min'])
    tier = RANK_TIERS[index]
    next_tier = RANK_TIERS[index + 1] if index + 1 < len(RANK_TIERS) else None
    stars = min(5, points - tier['min'] + 1) if next_tier else points - tier['min'] + 1
    span = (next_tier['min'] - tier['min']) if next_tier else 0
    progress = round((points - tier['min']) / span * 100) if span else 100
    return {
        'tier': tier['id'],
        'title': tier['title'],
        'stars': max(1, stars),
        'stars_max': 5,
        'points': points,
        'wins': wins,
        'practice_meals': practice,
        'quest_bonus': bonus,
        'courage': practice % 3,
        'courage_needed': 3,
        'next_title': next_tier['title'] if next_tier else '',
        'next_at': next_tier['min'] if next_tier else None,
        'remaining': max(0, next_tier['min'] - points) if next_tier else 0,
        'progress': progress,
        'season': f'S1 · {datetime.now(SHANGHAI).strftime("%Y-%m")}',
        'rule': RANK_RULE,
        'tiers': [dict(tier) for tier in RANK_TIERS],
    }


def _egg(egg_id, title, description, unlocked=False, session=None, unlocked_at=None, hint=''):
    return {
        'id': egg_id,
        'title': title,
        'description': description,
        'unlocked': bool(unlocked),
        'session_id': session.get('id') if session else None,
        'unlocked_at': unlocked_at or (session.get('completed_at') if session else None),
        'hint': hint,
    }


def _easter_eggs(sessions, stages, rank, secrets):
    night = next((session for session in sessions
                  if _shanghai_hour(session.get('completed_at')) is not None
                  and (_shanghai_hour(session.get('completed_at')) >= 21
                       or _shanghai_hour(session.get('completed_at')) < 5)), None)
    photos = next((session for session in sessions
                   if sum(len(dish.get('photos') or []) for dish in _effective_dishes(session)) >= 3), None)
    table = next((session for session in sessions if len(_effective_dishes(session)) >= 3), None)
    comeback_stage = None
    for stage in stages:
        outcomes = [dish.get('outcome') for _session, dish in stage['rows']]
        if 'success' in outcomes and 'practice' in outcomes:
            first_success = next((session for session, dish in stage['rows'] if dish.get('outcome') == 'success'), None)
            comeback_stage = (stage, first_success)
            break
    three_star = next((stage for stage in stages if stage['stars'] >= 3), None)
    three_star_session = next((session for session in sessions if three_star
                               and session.get('id') == three_star.get('best_session_id')), None)
    six_secrets = len([secret for secret in secrets if secret['unlocked']]) >= 6
    all_cleared = all(stage['state'] == 'cleared' for stage in stages)
    gold = rank['points'] >= 7
    return [
        _egg('night-owl', '深夜灶火', '在 21:00 之后完成一餐。', night, hint='夜里给自己做一顿热乎的。'),
        _egg('photo-three', '三连拍', '一餐里留下至少 3 张照片。', photos, hint='过程、灶台、成品都值得拍。'),
        _egg('table-three', '三菜一桌', '一餐同时做 3 道以上的菜。', table, hint='试试一次安排三道菜。'),
        _egg('comeback', '翻盘侠', '同一道菜先失手、后做成。', comeback_stage[1] if comeback_stage else None,
             hint='标为「还想再练」的菜，再战一次。'),
        _egg('three-star', '三星高照', '任意关卡拿到 3 颗星。', three_star_session,
             hint='做成 + 照片 + 8 字心得。'),
        _egg('secret-six', '秘籍收藏家', '收集 6 条以上秘籍。', unlocked=six_secrets,
             hint='把对应关卡做到 3 星。'),
        _egg('all-clear', '满汉全席', '通关全部 9 道内置关卡。', unlocked=all_cleared,
             hint='一章一章来，慢火也能炖出好味道。'),
        _egg('gold-seat', '黄金灶位', '段位达到黄金。', unlocked=gold,
             hint='稳定完成每一餐，段位自然上涨。'),
    ]


def _shanghai_hour(value):
    if not value:
        return None
    try:
        moment = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        return moment.astimezone(SHANGHAI).hour
    except (ValueError, TypeError):
        return None


def _blind_box(sessions, stages, user_id, today):
    unlocked = [stage for stage in stages if stage['unlocked']]
    pool = [stage for stage in unlocked if stage['state'] != 'cleared'] or unlocked or stages
    ordered = sorted(pool, key=lambda stage: sha256(f'{user_id}:{today}:{stage["id"]}'.encode()).hexdigest())
    options = []
    for stage in ordered[:3]:
        digest = sha256(f'{user_id}:{today}:twist:{stage["id"]}'.encode()).hexdigest()
        twist = BLIND_BOX_TWISTS[int(digest[:8], 16) % len(BLIND_BOX_TWISTS)]
        completed = any(
            session.get('cooked_on') == today
            and any(dish.get('quest_stage') == stage['id']
                    or (not dish.get('quest_stage')
                        and dish.get('snapshot', {}).get('name') == stage['name'])
                    for dish in _effective_dishes(session))
            for session in sessions
        )
        options.append({
            'stage_id': stage['id'],
            'name': stage['name'],
            'emoji': stage['emoji'],
            'chapter_title': stage['chapter_title'],
            'twist': twist,
            'tip': stage['tip'],
            'completed': completed,
        })
    return {'date': today, 'options': options}


def payload(db, user_id):
    sessions = sorted((session for session in store.all_sessions(db, user_id)
                       if session.get('state') == 'completed'),
                      key=lambda session: (session.get('completed_at') or '', session.get('id', 0)))
    stages = []
    for chapter in CATALOG:
        for stage in chapter['stages']:
            rows = _stage_dishes(sessions, stage)
            star_values = [_dish_stars(dish) for _session, dish in rows]
            stars = max(star_values, default=0)
            attempts = len(rows)
            successes = sum(1 for _session, dish in rows if dish.get('outcome') == 'success')
            best = max(rows, key=lambda row: (_dish_stars(row[1]), row[0].get('completed_at') or '',
                                              row[0].get('id', 0)), default=None)
            last = rows[-1] if rows else None
            stages.append({
                'id': stage['id'],
                'name': stage['name'],
                'emoji': stage['emoji'],
                'cover': stage['cover'],
                'minutes': stage['minutes'],
                'difficulty': stage['difficulty'],
                'tip': stage['tip'],
                'story': stage['story'],
                'secret': '',
                'secret_unlocked': stars >= 3,
                'ingredients': deepcopy(stage['ingredients']),
                'steps': [step['text'] for step in stage['steps']],
                'chapter_id': chapter['id'],
                'chapter_title': chapter['title'],
                'chapter_number': chapter['number'],
                'state': 'cleared' if successes else ('revenge' if attempts else 'ready'),
                'stars': stars,
                'attempts': attempts,
                'successes': successes,
                'last_session_id': last[0].get('id') if last else None,
                'best_session_id': best[0].get('id') if best else None,
                'best_at': best[0].get('completed_at') if best else None,
                'dish_key': last[1].get('dish_key', '') if last else '',
                'rows': rows,
            })

    by_chapter = {chapter['id']: [stage for stage in stages if stage['chapter_id'] == chapter['id']]
                  for chapter in CATALOG}
    chapter_stars = {chapter_id: sum(stage['stars'] for stage in rows)
                     for chapter_id, rows in by_chapter.items()}
    chapters = []
    unlocked_before = True
    for index, chapter in enumerate(CATALOG):
        rows = by_chapter[chapter['id']]
        stars = chapter_stars[chapter['id']]
        cleared = sum(1 for stage in rows if stage['state'] == 'cleared')
        unlocked = index == 0 or unlocked_before
        if index > 0:
            previous = chapters[-1]
            unlocked = chapter_stars[previous['id']] >= 3 or stars > 0
        hint = ''
        if not unlocked:
            previous = chapters[-1]
            need = max(0, 3 - chapter_stars[previous['id']])
            hint = f'在「{previous["title"]}」拿到 3 颗星解锁，还差 {need} 颗'
        for stage in rows:
            stage['unlocked'] = unlocked
            stage['unlock_hint'] = hint
            if stage['secret_unlocked']:
                stage['secret'] = next(item['secret'] for item in chapter['stages']
                                       if item['id'] == stage['id'])
        chapters.append({
            'id': chapter['id'],
            'number': chapter['number'],
            'title': chapter['title'],
            'subtitle': chapter['subtitle'],
            'badge': chapter['badge'],
            'stages': rows,
            'stars': stars,
            'max_stars': len(rows) * 3,
            'cleared_count': cleared,
            'completed': cleared == len(rows),
            'unlocked': unlocked,
            'unlock_hint': hint,
        })
        unlocked_before = unlocked

    total_stars = sum(stage['stars'] for stage in stages)
    totals = {
        'stars': total_stars,
        'max_stars': len(stages) * 3,
        'cleared': sum(1 for stage in stages if stage['state'] == 'cleared'),
        'stages': len(stages),
        'chapters_completed': sum(1 for chapter in chapters if chapter['completed']),
        'chapters': len(chapters),
    }

    secrets = []
    for stage in stages:
        unlocked = stage['stars'] >= 3
        secrets.append({
            'id': f'secret-{stage["id"]}',
            'stage_id': stage['id'],
            'title': f'{stage["name"]} · 秘籍',
            'body': stage['secret'] if unlocked else '',
            'unlocked': unlocked,
            'unlocked_at': stage['best_at'] if unlocked else None,
            'session_id': stage['best_session_id'] if unlocked else None,
            'hint': f'把「{stage["name"]}」做到 3 星解锁',
        })
    totals['secrets'] = sum(1 for secret in secrets if secret['unlocked'])
    totals['secrets_total'] = len(secrets)

    rank = _rank(sessions, total_stars)
    eggs = _easter_eggs(sessions, stages, rank, secrets)
    for stage in stages:
        stage.pop('rows', None)
    today = datetime.now(SHANGHAI).date().isoformat()
    return {
        'date': today,
        'chapters': chapters,
        'totals': totals,
        'rank': rank,
        'secrets': secrets,
        'easter_eggs': eggs,
        'blind_box': _blind_box(sessions, stages, user_id, today),
        'rules': {'stars': list(STAR_RULES), 'rank': RANK_RULE},
    }


def install(app, engine, current_user):
    @app.get('/api/kitchen-quest')
    def kitchen_quest(user: dict = Depends(current_user)):
        with engine.connect() as db:
            return payload(db, user['id'])

import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildQuestView, allStages, stageById, stageForDish, starGoalsForDish, noteLength,
  starPips, rankLine, questAwards, hasAwards, cheerFor, formatElapsed, blindBoxOptions
} from '../frontend/src/kitchenQuest.js'

const serverQuest = {
  date: '2026-11-27',
  totals: { stars: 4, max_stars: 27, cleared: 2, stages: 9, secrets: 1, secrets_total: 9 },
  rank: { tier: 'silver', title: '白银', stars: 2, points: 4, remaining: 3, next_title: '黄金', progress: 25 },
  chapters: [{
    id: 'ch-1', number: 1, title: '初试灶火', badge: '灶台萌新', unlocked: true, completed: false,
    stages: [
      { id: 's-1', name: '番茄炒蛋', state: 'cleared', stars: 3, last_session_id: 7, quest: true },
      { id: 's-2', name: '葱花鸡蛋饼', state: 'ready', stars: 0, last_session_id: null }
    ]
  }],
  secrets: [{ id: 'secret-s-1', stage_id: 's-1', unlocked: true, title: '番茄炒蛋 · 秘籍' }],
  easter_eggs: [{ id: 'photo-three', unlocked: true, title: '三连拍' }],
  blind_box: { date: '2026-11-27', options: [{ stage_id: 's-2', twist: '拍一张' }] }
}

test('buildQuestView prefers the server payload and keeps snake_case ids', () => {
  const view = buildQuestView(serverQuest, {}, [])
  assert.equal(view.server, true)
  assert.equal(view.totals.stars, 4)
  assert.equal(stageById(view, 's-1').last_session_id, 7)
  assert.equal(blindBoxOptions(serverQuest)[0].stage_id, 's-2')
})

test('buildQuestView falls back to the local chapter map when the API is unavailable', () => {
  const view = buildQuestView(null, { repertoire: [] }, [])
  assert.equal(view.server, false)
  assert.equal(view.chapters.length, 3)
  assert.equal(allStages(view).length, 9)
  assert.equal(allStages(view)[0].unlocked, true)
  assert.equal(allStages(view)[0].chapter_number, 1)
})

test('stageForDish resolves by quest_stage first and by name as a fallback', () => {
  const view = buildQuestView(serverQuest, {}, [])
  assert.equal(stageForDish(view, { quest_stage: 's-1' }).name, '番茄炒蛋')
  assert.equal(stageForDish(view, { snapshot: { name: '葱花鸡蛋饼' } }).id, 's-2')
  assert.equal(stageForDish(view, { snapshot: { name: '不存在的菜' } }), null)
})

test('star goals and note length follow the 3-star rules', () => {
  assert.deepEqual(starGoalsForDish({ outcome: 'practice' }).map(g => g.done), [true, false, false])
  assert.deepEqual(starGoalsForDish({ outcome: 'success', photos: [], note: '好吃' }).map(g => g.done), [true, true, false])
  const three = starGoalsForDish({ outcome: 'success', photos: ['/a.jpg'], note: '火候刚刚好，下次还这样做' })
  assert.deepEqual(three.map(g => g.done), [true, true, true])
  assert.equal(noteLength({ note: '  好吃  ' }), 2)
  assert.deepEqual(starPips(2), [true, true, false])
})

test('questAwards only reports genuinely new stars, ranks, secrets and eggs', () => {
  const before = {
    totals: { stars: 2 }, rank: { title: '青铜' },
    secrets: [{ id: 'secret-s-1', unlocked: true }],
    easter_eggs: [{ id: 'photo-three', unlocked: false }],
    chapters: [{ id: 'ch-1', completed: false }]
  }
  const after = {
    totals: { stars: 5 }, rank: { title: '白银' },
    secrets: [{ id: 'secret-s-1', unlocked: true }, { id: 'secret-s-2', unlocked: true }],
    easter_eggs: [{ id: 'photo-three', unlocked: true }],
    chapters: [{ id: 'ch-1', completed: true }]
  }
  const awards = questAwards(before, after)
  assert.equal(awards.stars, 3)
  assert.equal(awards.rankUp, '青铜 → 白银')
  assert.deepEqual(awards.secrets.map(item => item.id), ['secret-s-2'])
  assert.deepEqual(awards.eggs.map(item => item.id), ['photo-three'])
  assert.deepEqual(awards.chapters.map(item => item.id), ['ch-1'])
  assert.equal(hasAwards(awards), true)
  assert.equal(hasAwards(questAwards(after, after)), false)
})

test('cheer and elapsed helpers stay deterministic and readable', () => {
  assert.match(cheerFor(0, 4, '番茄炒蛋'), /开火/)
  assert.match(cheerFor(3, 4, '番茄炒蛋'), /最后一步/)
  assert.equal(formatElapsed(0), '00:00')
  assert.equal(formatElapsed(125), '02:05')
  assert.equal(rankLine({ title: '白银', stars: 2, remaining: 3, next_title: '黄金' }), '白银 2 星 · 再 3 分到 黄金')
})

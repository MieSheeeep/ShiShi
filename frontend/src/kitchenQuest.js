import { buildChapterMap } from './cookingJournal.js'

export const QUEST_STAR_RULES = [
  { id: 'finish', title: '完成这一餐', detail: '把这道菜标记为「做成了」或「还想再练」并完成收尾。' },
  { id: 'success', title: '把菜做成', detail: '至少有一次结果为「做成了」。' },
  { id: 'memory', title: '留下色香味', detail: '做成的记录里至少有 1 张照片，并写下 8 个字以上的心得。' }
]

export const RANK_TIERS = [
  { id: 'bronze', title: '青铜', min: 0 },
  { id: 'silver', title: '白银', min: 3 },
  { id: 'gold', title: '黄金', min: 7 },
  { id: 'platinum', title: '铂金', min: 12 },
  { id: 'diamond', title: '钻石', min: 18 },
  { id: 'star', title: '星耀', min: 25 },
  { id: 'king', title: '王者', min: 33 }
]

export const RANK_RULE = '每完成一餐、其中有做成的菜 +1 分；整餐都标为「还想再练」，每累计 3 餐 +1 分；每集满 6 颗闯关星 +1 分。段位只升不降，新赛季重新起跑。'

const emptyTotals = () => ({
  stars: 0, max_stars: 27, cleared: 0, stages: 9, chapters_completed: 0, chapters: 3,
  secrets: 0, secrets_total: 9
})

/** Server payload first; a local chapter map keeps the old UI usable offline. */
export function buildQuestView(quest, summary = {}, recipes = []) {
  if (quest && Array.isArray(quest.chapters) && quest.chapters.length) {
    return {
      server: true,
      date: quest.date || '',
      chapters: quest.chapters,
      totals: { ...emptyTotals(), ...(quest.totals || {}) },
      rank: quest.rank || null,
      secrets: quest.secrets || [],
      easterEggs: quest.easter_eggs || [],
      blindBox: quest.blind_box || null
    }
  }
  const map = buildChapterMap(summary, recipes)
  const chapters = map.chapters.map(chapter => {
    const stages = chapter.stages.map(stage => ({
      ...stage,
      unlocked: true,
      stars: stage.state === 'cleared' ? 2 : stage.attempts ? 1 : 0,
      secret_unlocked: false,
      secret: '',
      story: '',
      unlock_hint: '',
      chapter_number: chapter.number,
      chapter_title: chapter.title,
      last_session_id: stage.lastSessionId || null,
      best_session_id: stage.lastSessionId || null,
      ingredients: stage.ingredients || [],
      steps: stage.steps || []
    }))
    return {
      ...chapter,
      stages,
      stars: stages.reduce((total, stage) => total + stage.stars, 0),
      max_stars: stages.length * 3,
      cleared_count: chapter.clearedCount,
      unlocked: true,
      unlock_hint: ''
    }
  })
  const totals = emptyTotals()
  totals.stages = chapters.reduce((total, chapter) => total + chapter.stages.length, 0)
  totals.chapters = chapters.length
  totals.max_stars = totals.stages * 3
  totals.secrets_total = totals.stages
  totals.stars = chapters.reduce((total, chapter) => total + chapter.stars, 0)
  totals.cleared = chapters.reduce((total, chapter) => total + chapter.cleared_count, 0)
  totals.chapters_completed = chapters.filter(chapter => chapter.completed).length
  return { server: false, date: '', chapters, totals, rank: null, secrets: [], easterEggs: [], blindBox: null }
}

export const allStages = view => (view?.chapters || []).flatMap(chapter => chapter.stages || [])

export function stageById(view, id) {
  return allStages(view).find(stage => stage.id === id) || null
}

export function stageForDish(view, dish) {
  if (!dish) return null
  const stages = allStages(view)
  if (dish.quest_stage) {
    const exact = stages.find(stage => stage.id === dish.quest_stage)
    if (exact) return exact
  }
  return stages.find(stage => stage.name === dish.snapshot?.name) || null
}

export const isQuestDish = (view, dish) => Boolean(stageForDish(view, dish))

export function starGoalsForDish(dish) {
  const outcome = dish?.outcome
  const finished = outcome === 'success' || outcome === 'practice'
  const success = outcome === 'success'
  const memory = success && (dish?.photos || []).length > 0 && (dish?.note || '').trim().length >= 8
  return [
    { ...QUEST_STAR_RULES[0], done: finished },
    { ...QUEST_STAR_RULES[1], done: success },
    { ...QUEST_STAR_RULES[2], done: memory }
  ]
}

export function noteLength(dish) {
  return (dish?.note || '').trim().length
}

export function starPips(stars, max = 3) {
  return Array.from({ length: max }, (_, index) => index < (stars || 0))
}

export function rankTiers(rank) {
  return rank?.tiers?.length ? rank.tiers : RANK_TIERS
}

export function rankLine(rank) {
  if (!rank) return ''
  if (!rank.next_title) return `${rank.title} ${rank.stars} 星 · 本赛季最高段位`
  return `${rank.title} ${rank.stars} 星 · 再 ${rank.remaining} 分到 ${rank.next_title}`
}

export function questAwards(before, after) {
  if (!after) return null
  const previousStars = before?.totals?.stars || 0
  const stars = Math.max(0, (after.totals?.stars || 0) - previousStars)
  const rankUp = before?.rank?.title && after.rank?.title && before.rank.title !== after.rank.title
    ? `${before.rank.title} → ${after.rank.title}`
    : ''
  const knownSecrets = new Set((before?.secrets || []).filter(item => item.unlocked).map(item => item.id))
  const secrets = (after.secrets || []).filter(item => item.unlocked && !knownSecrets.has(item.id))
  const knownEggs = new Set((before?.easter_eggs || []).filter(item => item.unlocked).map(item => item.id))
  const eggs = (after.easter_eggs || []).filter(item => item.unlocked && !knownEggs.has(item.id))
  const knownChapters = new Set((before?.chapters || []).filter(item => item.completed).map(item => item.id))
  const chapters = (after.chapters || []).filter(item => item.completed && !knownChapters.has(item.id))
  return { stars, rankUp, secrets, eggs, chapters }
}

export function hasAwards(awards) {
  return Boolean(awards && (awards.stars || awards.rankUp || awards.secrets.length || awards.eggs.length || awards.chapters.length))
}

export function cheerFor(index, total, name = '') {
  if (!total) return '这道菜没有预设步骤，按自己的节奏来，做完直接出锅。'
  if (index <= 0) return `开火！先来第一步，${name || '这道菜'}马上就有香味了。`
  if (index >= total - 1) return '最后一步了，稳住火候，马上就能出锅。'
  const lines = [
    '不着急，好味道都是一步一步来的。',
    '手上稳一点，锅里就香一点。',
    `已经走到第 ${index + 1} 步了，节奏很好。`,
    '闻到了吗？这就是你自己做出来的烟火气。',
    '慢慢来，把这一步做扎实。',
    '灶台前认真做饭的你，已经很厉害了。'
  ]
  return lines[(index + (name?.length || 0)) % lines.length]
}

export function formatElapsed(seconds = 0) {
  const value = Math.max(0, Math.floor(Number(seconds) || 0))
  const minutes = Math.floor(value / 60)
  const rest = value % 60
  return `${String(minutes).padStart(2, '0')}:${String(rest).padStart(2, '0')}`
}

export function blindBoxOptions(quest) {
  return quest?.blind_box?.options || []
}

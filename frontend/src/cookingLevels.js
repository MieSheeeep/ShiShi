// 段位展示数据：七档 + 无上限的巅峰星数，每档 3 星、每 2 餐一星。
// 事实源在 backend/cooking_store.py 的 TIERS / STAR_STEP，改档位或门槛时两边必须同步。
export const COOKING_LEVELS = [
  { id: 'bronze', title: '倔强青铜', char: '青', minMeals: 0, note: '第一次把菜做完，先别管好不好吃。' },
  { id: 'silver', title: '秩序白银', char: '银', minMeals: 6, note: '开始有固定节奏，慢慢记住火候。' },
  { id: 'gold', title: '荣耀黄金', char: '金', minMeals: 12, note: '几道家常菜能稳定端上桌。' },
  { id: 'platinum', title: '尊贵铂金', char: '铂', minMeals: 18, note: '调味有准头，敢按口味微调。' },
  { id: 'diamond', title: '永恒钻石', char: '钻', minMeals: 24, note: '火候心里有数，硬菜也敢上手。' },
  { id: 'star', title: '至尊星耀', char: '耀', minMeals: 30, note: '手上有一批稳定招牌菜。' },
  { id: 'king', title: '最强王者', char: '王', minMeals: 36, note: '厨房里说一不二，随手就是一顿好饭。' },
  { id: 'peak', title: '巅峰', char: '峰', minMeals: 48, peak: true, note: '进入巅峰赛，星数不再封顶，做得越多星越高。' }
]

export const STAR_STEP = 2
export const STARS_PER_TIER = 3

// 只按有效餐次计算；升级条件若变复杂，改这里即可，组件不用动。
export function levelProgress(meals = 0) {
  const current = [...COOKING_LEVELS].reverse().find(level => meals >= level.minMeals) || COOKING_LEVELS[0]
  const index = COOKING_LEVELS.indexOf(current)
  const next = COOKING_LEVELS[index + 1] || null
  const raw = Math.floor((meals - current.minMeals) / STAR_STEP) + 1
  const star = current.peak ? raw : Math.min(STARS_PER_TIER, raw)
  const span = next ? next.minMeals - current.minMeals : 0
  const done = Math.max(0, meals - current.minMeals)
  return {
    current,
    next,
    star,
    percent: next && span ? Math.min(100, Math.round(done / span * 100)) : 100,
    text: current.peak ? '巅峰星数不封顶，继续做菜累积'
      : next ? `再完成 ${Math.max(0, next.minMeals - meals)} 餐升到「${next.title}」`
        : '已经是最高段位'
  }
}

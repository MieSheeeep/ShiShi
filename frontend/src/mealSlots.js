// 一餐所属的餐点。事实源在 backend/cooking_schema.py 的 MealSlot 取值，新增/改名需同步。
export const MEAL_SLOTS = [
  { id: 'breakfast', label: '早饭', range: '5–10 点' },
  { id: 'lunch', label: '午饭', range: '10–14 点' },
  { id: 'teatime', label: '下午茶', range: '14–17 点' },
  { id: 'dinner', label: '晚饭', range: '17–21 点' },
  { id: 'supper', label: '夜宵', range: '21 点后' }
]

export const MEAL_LABELS = Object.fromEntries(MEAL_SLOTS.map(slot => [slot.id, slot.label]))

// 打开选择时默认按当前时间预选，用户可以改。
export function defaultMealSlot(now = new Date()) {
  const hour = now.getHours()
  if (hour >= 5 && hour < 10) return 'breakfast'
  if (hour < 14) return 'lunch'
  if (hour < 17) return 'teatime'
  if (hour < 21) return 'dinner'
  return 'supper'
}

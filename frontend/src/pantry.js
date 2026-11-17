// 与 backend/condiments.py 保持同源；任一侧调整时需同步另一侧。
const CONDIMENTS = new Set([
  '盐', '糖', '白糖', '红糖', '冰糖', '生抽', '老抽', '酱油', '醋', '香醋', '米醋', '陈醋',
  '料酒', '黄酒', '蚝油', '香油', '麻油', '花椒', '胡椒', '黑胡椒', '白胡椒', '辣椒',
  '干辣椒', '豆瓣酱', '甜面酱', '番茄酱', '沙拉酱', '芝麻酱', '花生酱', '黄油', '奶油',
  '食用油', '橄榄油', '菜籽油', '花生油', '玉米油', '味精', '鸡精', '淀粉', '生粉',
  '孜然', '孜然粉', '五香粉', '十三香', '八角', '桂皮', '香叶', '蜂蜜', '味淋',
  '沙茶酱', '腐乳', '芥末', '咖喱', '鱼露', '葱', '姜', '蒜', '小葱', '大葱', '香菜',
])
const SUFFIXES = ['酱', '醋', '油', '精', '料酒', '黄酒']
const EXCEPTIONS = ['油菜', '油麦菜', '油条', '油豆腐', '油桃', '甘蓝', '糖醋里脊']

export const UNITS = ['个', '颗', '根', '块', '片', '把', '克', '毫升', '勺', '袋', '盒']

export function isCondiment(name) {
  const text = String(name || '').replace(/\s+/g, '')
  if (!text) return false
  if (CONDIMENTS.has(text)) return true
  if (EXCEPTIONS.some(word => text.endsWith(word))) return false
  return SUFFIXES.some(word => text.endsWith(word))
}

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ChevronLeft, ChevronRight, Plus, X, Search, Clock3, Users, Sparkles, ShoppingBasket, Trash2, RefreshCw, CalendarDays } from 'lucide-vue-next'
import { api } from '../recipeEditing'
import RecipeDetail from './RecipeDetail.vue'

const emit = defineEmits(['goto-shopping'])

const MEALS = [['breakfast', '早餐'], ['lunch', '午餐'], ['dinner', '晚餐']]
const WEEKDAYS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']

const recipes = ref([])
const week = ref(weekKeyOf(new Date()))
const plan = ref(null)
const loading = ref(false)
const generating = ref(false)
const shoppingBusy = ref(false)
const picker = ref(null)          // { date, meal }
const search = ref('')
const category = ref('全部')
const detail = ref(null)
const focusDate = ref('')
const toastMsg = ref('')

const recipeMap = computed(() => new Map(recipes.value.map(r => [r.id, r])))
const categories = computed(() => {
  const set = new Set()
  for (const r of recipes.value) for (const t of r.tags || []) if (t && t.name) set.add(t.name)
  return ['全部', ...Array.from(set)]
})
const filteredRecipes = computed(() => {
  const q = search.value.trim().toLowerCase()
  return recipes.value.filter(r => {
    const hitQ = !q || (r.name || '').toLowerCase().includes(q)
    const hitC = category.value === '全部' || (r.tags || []).some(t => t.name === category.value)
    return hitQ && hitC
  })
})
const dateRange = computed(() => {
  if (!plan.value) return ''
  const first = plan.value.days[0].date
  const last = plan.value.days[plan.value.days.length - 1].date
  return `${toDotted(first)} - ${toDotted(last)}`
})

function iso(date) {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}
function mondayOf(date) {
  const copy = new Date(date)
  copy.setDate(copy.getDate() - ((copy.getDay() + 6) % 7))
  return copy
}
function weekKeyOf(date) { return iso(mondayOf(date)) }
function shiftWeekKey(key, delta) {
  const [y, m, d] = key.split('-').map(Number)
  const date = new Date(y, m - 1, d)
  date.setDate(date.getDate() + delta * 7)
  return iso(date)
}
function toDotted(key) {
  const [y, m, d] = key.split('-').map(Number)
  return `${y}.${m}.${d}`
}
function introOf(recipe) {
  if (recipe.notes) return recipe.notes
  const step = (recipe.steps || []).find(s => s.text)
  if (step) return step.text
  const tag = (recipe.tags || []).find(t => t && t.name)
  return tag ? `${tag.name}·家常做法` : '一道简单的家常菜'
}
function mealLabel(key) { return (MEALS.find(m => m[0] === key) || ['', ''])[1] }

function toast(text) {
  toastMsg.value = text
  clearTimeout(toast._t)
  toast._t = setTimeout(() => { toastMsg.value = '' }, 2600)
}

async function loadPlan() {
  loading.value = true
  try {
    plan.value = await api(`/meal-plan?week=${week.value}`)
  } catch (error) {
    toast(error.message)
  } finally {
    loading.value = false
  }
}

async function save() {
  if (!plan.value) return
  try {
    await api('/meal-plan', 'PUT', { week: plan.value.week, days: plan.value.days })
  } catch (error) {
    toast(error.message)
  }
}

function currentWeek() { week.value = weekKeyOf(new Date()); loadPlan() }
function prevWeek() { week.value = shiftWeekKey(week.value, -1); loadPlan() }
function nextWeek() { week.value = shiftWeekKey(week.value, 1); loadPlan() }

function openPicker(date, meal) {
  search.value = ''
  category.value = '全部'
  picker.value = { date, meal }
}
function closePicker() { picker.value = null }

function choose(recipe) {
  const day = plan.value.days.find(d => d.date === picker.value.date)
  if (day) day.meals[picker.value.meal] = recipe.id
  closePicker()
  save()
  toast(`已安排「${recipe.name}」`)
}

function removeSlot(date, meal) {
  const day = plan.value.days.find(d => d.date === date)
  if (day) day.meals[meal] = null
  save()
  toast('已移除该餐次菜品')
}

async function generate() {
  generating.value = true
  try {
    plan.value = await api('/meal-plan/generate', 'POST', { week: week.value, preferences: [] })
    toast('已生成一周计划，可手动调整')
  } catch (error) {
    toast(error.message)
  } finally {
    generating.value = false
  }
}

function uniqueIds() {
  const ids = new Set()
  for (const day of plan.value.days) for (const [key] of MEALS) {
    const id = day.meals[key]
    if (id != null && recipeMap.value.has(id)) ids.add(id)
  }
  return Array.from(ids)
}

async function makeShopping() {
  const ids = uniqueIds()
  if (!ids.length) { toast('本周还没有安排菜品'); return }
  shoppingBusy.value = true
  try {
    await api('/meal-plan/shopping', 'POST', { ids })
    toast('已生成本周采购清单')
    emit('goto-shopping')
  } catch (error) {
    toast(error.message)
  } finally {
    shoppingBusy.value = false
  }
}

onMounted(async () => {
  try {
    recipes.value = await api('/recipes')
  } catch (error) {
    toast(error.message)
  }
  await loadPlan()
})
</script>

<template>
  <div class="meal-plan">
    <div class="page-heading">
      <div>
        <div class="eyebrow">WEEKLY MEAL PLAN</div>
        <h1>每周饮食计划<span class="title-dot">。</span></h1>
        <p>提前规划每一餐，让每天吃什么都变得简单。</p>
      </div>
      <div class="heading-actions">
        <button class="secondary" :disabled="generating" @click="generate">
          <Sparkles :size="15" />{{ generating ? '正在生成…' : 'AI 生成本周计划' }}
        </button>
        <button class="primary" :disabled="shoppingBusy" @click="makeShopping">
          <ShoppingBasket :size="15" />{{ shoppingBusy ? '正在汇总…' : '生成本周采购清单' }}
        </button>
      </div>
    </div>

    <div class="week-switcher">
      <button class="secondary" @click="prevWeek"><ChevronLeft :size="15" />上一周</button>
      <button class="week-current" @click="currentWeek">
        <CalendarDays :size="15" />
        <span>当前周</span>
      </button>
      <button class="secondary" @click="nextWeek">下一周<ChevronRight :size="15" /></button>
      <span class="week-range">{{ dateRange }}</span>
    </div>

    <div v-if="loading" class="empty-panel">
      <RefreshCw :size="38" class="spin" />
      <p>正在加载本周计划…</p>
    </div>

    <div v-else-if="plan" class="days">
      <section v-for="(day, index) in plan.days" :key="day.date" class="day" :class="{ focused: focusDate === day.date }">
        <button class="day-heading" @click="focusDate = focusDate === day.date ? '' : day.date">
          <span class="day-name">{{ WEEKDAYS[index] }}</span>
          <span class="day-date">{{ toDotted(day.date) }}</span>
        </button>
        <div class="meals">
          <div v-for="[key, label] in MEALS" :key="key" class="meal">
            <span class="meal-label">{{ label }}</span>
            <div v-if="day.meals[key] != null && recipeMap.has(day.meals[key])" class="meal-card filled" @click="detail = recipeMap.get(day.meals[key])">
              <div class="meal-art" :class="'tone-' + ((day.meals[key] % 5) + 1)">
                <img v-if="recipeMap.get(day.meals[key]).cover" :src="recipeMap.get(day.meals[key]).cover" :alt="recipeMap.get(day.meals[key]).name" />
                <span v-else class="food-emoji">{{ recipeMap.get(day.meals[key]).emoji || '🍲' }}</span>
              </div>
              <div class="meal-body">
                <strong class="meal-name">{{ recipeMap.get(day.meals[key]).name }}</strong>
                <p class="meal-intro">{{ introOf(recipeMap.get(day.meals[key])) }}</p>
                <div class="meal-meta">
                  <span><Clock3 :size="12" />{{ recipeMap.get(day.meals[key]).minutes ? recipeMap.get(day.meals[key]).minutes + ' 分钟' : '耗时未注明' }}</span>
                  <span v-if="recipeMap.get(day.meals[key]).servings"><Users :size="12" />{{ recipeMap.get(day.meals[key]).servings }} 人份</span>
                </div>
              </div>
              <div class="meal-tools" @click.stop>
                <button class="mini" @click="openPicker(day.date, key)"><RefreshCw :size="13" />更换</button>
                <button class="mini danger" @click="removeSlot(day.date, key)"><Trash2 :size="13" />移除</button>
              </div>
            </div>
            <button v-else class="meal-card empty" @click="openPicker(day.date, key)">
              <span class="plus"><Plus :size="17" /></span>
              添加菜品
            </button>
          </div>
        </div>
      </section>
    </div>

    <div v-else class="empty-panel">
      <CalendarDays :size="38" />
      <h2>还没有可安排的食谱</h2>
      <p>先在「首页」导入或创建食谱，再回来规划一周饮食。</p>
    </div>

    <div v-if="picker" class="overlay" @click.self="closePicker">
      <section class="modal picker-modal">
        <button class="close" @click="closePicker" aria-label="关闭"><X /></button>
        <div class="modal-icon"><Plus :size="24" /></div>
        <h2>选择菜品</h2>
        <p class="muted">为{{ picker.meal && mealLabel(picker.meal) }}挑选一道菜，点击即可加入计划。</p>
        <div class="picker-tools">
          <label class="search"><Search :size="15" /><input v-model="search" placeholder="搜索菜品名称" /></label>
          <div class="tags">
            <button v-for="c in categories" :key="c" :class="{ chosen: category === c }" @click="category = c">{{ c }}</button>
          </div>
        </div>
        <div v-if="filteredRecipes.length" class="picker-grid">
          <button v-for="r in filteredRecipes" :key="r.id" class="picker-item" @click="choose(r)">
            <div class="picker-art" :class="'tone-' + ((r.id % 5) + 1)">
              <img v-if="r.cover" :src="r.cover" :alt="r.name" />
              <span v-else class="food-emoji">{{ r.emoji || '🍲' }}</span>
            </div>
            <div class="picker-body">
              <strong>{{ r.name }}</strong>
              <p>{{ introOf(r) }}</p>
              <span class="picker-min"><Clock3 :size="12" />{{ r.minutes ? r.minutes + ' 分钟' : '耗时未注明' }}</span>
            </div>
          </button>
        </div>
        <div v-else class="empty">没有匹配的菜品，换个关键词试试。</div>
      </section>
    </div>

    <RecipeDetail v-if="detail" :key="detail.id" :recipe="detail" :done="{}" :selected="false" @close="detail = null" />

    <transition name="fade">
      <div v-if="toastMsg" class="toast">{{ toastMsg }}</div>
    </transition>
  </div>
</template>

<style scoped>
.meal-plan { min-height: 70vh; }
.heading-actions { display: flex; gap: 12px; align-items: center; }
.week-switcher { display: flex; align-items: center; gap: 10px; margin-bottom: 30px; }
.week-current { display: inline-flex; align-items: center; gap: 8px; padding: 10px 18px; border-radius: 7px; background: var(--green); color: var(--surface); font-size: 12px; }
.week-current:hover { background: var(--green-hover); }
.week-range { margin-left: auto; font-size: 12px; color: var(--muted); letter-spacing: 1px; }
.days { display: grid; gap: 18px; }
.day { background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 20px 22px; transition: box-shadow .2s, border-color .2s; }
.day.focused { border-color: var(--green); box-shadow: 0 0 0 3px #263f350f; }
.day-heading { display: flex; align-items: baseline; gap: 12px; margin-bottom: 16px; }
.day-name { font-family: 'Noto Serif SC', 'Songti SC', serif; font-size: 16px; color: var(--green); font-weight: 600; }
.day-date { font-size: 11px; color: var(--muted); letter-spacing: 1px; }
.meals { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
.meal { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
.meal-label { font-size: 10px; letter-spacing: 2px; color: var(--muted); }
.meal-card { border-radius: 10px; border: 1px solid var(--border); overflow: hidden; background: var(--surface); text-align: left; position: relative; }
.meal-card.filled { cursor: pointer; display: flex; flex-direction: column; transition: transform .2s, box-shadow .2s; }
.meal-card.filled:hover { transform: translateY(-3px); box-shadow: 0 8px 18px #29282310; }
.meal-art { height: 96px; display: grid; place-items: center; overflow: hidden; }
.meal-art img { width: 100%; height: 100%; object-fit: cover; }
.meal-art .food-emoji { font-size: 44px; }
.meal-body { padding: 12px 13px; }
.meal-name { display: block; font-size: 14px; color: var(--green); margin-bottom: 5px; }
.meal-intro { font-size: 10px; color: var(--muted); margin: 0 0 9px; line-height: 1.6; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.meal-meta { display: flex; gap: 14px; font-size: 9px; color: var(--muted); }
.meal-meta span { display: inline-flex; align-items: center; gap: 4px; }
.meal-tools { display: flex; gap: 6px; padding: 0 13px 12px; }
.mini { font-size: 10px; padding: 5px 9px; border-radius: 6px; border: 1px solid var(--border); color: var(--green); gap: 4px; }
.mini:hover { background: var(--soft); }
.mini.danger { color: var(--accent); }
.meal-card.empty { display: flex; align-items: center; justify-content: center; gap: 8px; flex: 1; min-height: 96px; border-style: dashed; color: var(--muted); font-size: 12px; }
.meal-card.empty:hover { background: var(--soft); }
.meal-card.empty .plus { width: 26px; height: 26px; border-radius: 50%; background: var(--soft); display: grid; place-items: center; color: var(--green); }
.picker-modal { width: 760px; max-height: 86vh; overflow: auto; }
.picker-tools { display: grid; gap: 14px; margin: 22px 0; }
.picker-tools .search { max-width: 340px; }
.picker-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
.picker-item { display: flex; flex-direction: column; border: 1px solid var(--border); border-radius: 10px; overflow: hidden; background: var(--surface); text-align: left; transition: transform .2s, box-shadow .2s; }
.picker-item:hover { transform: translateY(-3px); box-shadow: 0 8px 18px #29282310; }
.picker-art { height: 86px; display: grid; place-items: center; overflow: hidden; }
.picker-art img { width: 100%; height: 100%; object-fit: cover; }
.picker-art .food-emoji { font-size: 40px; }
.picker-body { padding: 11px 12px; }
.picker-body strong { display: block; font-size: 13px; color: var(--green); margin-bottom: 4px; }
.picker-body p { font-size: 10px; color: var(--muted); margin: 0 0 8px; line-height: 1.5; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.picker-min { display: inline-flex; align-items: center; gap: 4px; font-size: 9px; color: var(--muted); }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.fade-enter-active, .fade-leave-active { transition: opacity .25s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
@media (max-width: 1100px) {
  .meals { grid-template-columns: 1fr; }
  .picker-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 650px) {
  .heading-actions { flex-direction: column; align-items: stretch; }
  .week-switcher { flex-wrap: wrap; }
  .week-range { margin-left: 0; width: 100%; }
  .picker-grid { grid-template-columns: 1fr; }
}
</style>

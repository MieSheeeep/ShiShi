<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { Plus, Search, Refrigerator, Pencil, Check, Trash2, RotateCcw, X, SlidersHorizontal, Sparkles, Flame } from 'lucide-vue-next'
import { api } from '../recipeEditing'
import { UNITS, isCondiment } from '../pantry'
import { inventorySettings } from '../fridgeState'

const props = defineProps({
  selected: { type: Array, default: () => [] },
  initialView: { type: String, default: 'fuzzy' },
  recipes: { type: Array, default: () => [] }
})
const emit = defineEmits(['detail', 'select', 'change', 'cook', 'ai-cook'])

const mode = ref(props.initialView === 'inventory' ? 'fuzzy' : 'fuzzy')
const showInventory = ref(false)

// Fuzzy search state
const rawInput = ref('')
const quickPicks = ['鸡蛋', '番茄', '土豆', '豆腐', '西兰花', '青菜', '鸡胸肉', '五花肉', '挂面', '南瓜', '黄瓜', '大蒜']
const aiDishes = ref([])
const aiBusy = ref(false)
const aiError = ref('')

// Fridge inventory state (secondary drawer/view)
const stock = ref({ categories: [], items: [] })
const ready = ref(false)
const busy = ref(false)
const error = ref('')
const query = ref('')
const category = ref('')
const location = ref('')
const status = ref('active')
const stockPage = ref(1)
const PAGE_SIZE = 6
const editing = ref(null)
const managing = ref(false)
const newCategory = ref('')
const renames = ref({})
const deleting = ref('')
const categoryDelete = ref('')

const settings = computed(() => inventorySettings(stock.value.items))
const suggestions = computed(() => [...new Set((props.recipes || []).flatMap(r => r.ingredients.map(i => i.name)))].sort())
const locations = ['冷藏', '冷冻', '常温']
const active = computed(() => stock.value.items.filter(i => i.status === 'active'))
const used = computed(() => stock.value.items.filter(i => i.status === 'used').length)
const rows = computed(() => stock.value.items.filter(i => (!category.value || i.category_id === category.value) && (!location.value || i.location === location.value) && i.status === status.value && (i.name + i.notes).includes(query.value.trim())))
const categoryName = id => stock.value.categories.find(c => c.id === id)?.name || '未分类'
const visibleRows = computed(() => rows.value.slice((stockPage.value - 1) * PAGE_SIZE, stockPage.value * PAGE_SIZE))
const stockPages = computed(() => Math.max(1, Math.ceil(rows.value.length / PAGE_SIZE)))

function parseTokens(text) {
  const cleaned = (text || '')
    .replace(/[，,、；;。\n+]+/g, ' ')
    .replace(/(?:还有|家里有|手边有|冰箱有|一点|一些|适量|几|半|两|一|二|三|四|五|六|七|八|九|十|\d+)\s*(?:个|颗|根|把|块|片|斤|两|克|g|kg|袋|盒|瓶|勺|碗|份|只|条)?/gi, ' ')
  return [...new Set(cleaned.split(/\s+/).map(s => s.trim()).filter(s => s.length >= 1))]
}

const tokens = computed(() => parseTokens(rawInput.value))

function toggleQuick(word) {
  const list = rawInput.value.trim() ? rawInput.value.trim().split(/\s+/) : []
  const idx = list.indexOf(word)
  if (idx >= 0) list.splice(idx, 1)
  else list.push(word)
  rawInput.value = list.join(' ')
}

function fillFromFridge() {
  const names = [...new Set(active.value.map(i => i.name))].slice(0, 10)
  if (!names.length) return
  rawInput.value = names.join(' ')
}

const fuzzyMatches = computed(() => {
  const keys = tokens.value
  if (!keys.length) return []
  const scored = []
  for (const recipe of props.recipes || []) {
    const mainIngs = (recipe.ingredients || []).filter(i => i.kind !== '调料')
    const ingNames = mainIngs.map(i => i.name)
    const matched = []
    for (const k of keys) {
      if (recipe.name.includes(k) || ingNames.some(n => n.includes(k) || k.includes(n))) {
        matched.push(k)
      }
    }
    if (!matched.length) continue
    const missing = ingNames.filter(n => !keys.some(k => n.includes(k) || k.includes(n)))
    scored.push({ recipe, matched, missing, ratio: matched.length / Math.max(1, mainIngs.length) })
  }
  return scored.sort((a, b) => b.matched.length - a.matched.length || a.missing.length - b.missing.length || b.ratio - a.ratio)
})

async function askAi() {
  if (aiBusy.value) return
  const list = tokens.value.length ? tokens.value.map(name => ({ name, amount: '' })) : settings.value.ingredients
  if (!list.length) {
    aiError.value = '先随手输入一两样食材吧'
    return
  }
  aiBusy.value = true
  aiError.value = ''
  try {
    const data = await api('/ai/suggest', 'POST', { ingredients: list, staples: settings.value.staples })
    aiDishes.value = data.dishes || []
  } catch (e) {
    aiError.value = e.message
  } finally {
    aiBusy.value = false
  }
}

async function load() {
  stock.value = await api('/fridge')
  emit('change', settings.value)
  if (category.value && !stock.value.categories.some(c => c.id === category.value)) category.value = ''
}
onMounted(async () => {
  try { await load(); ready.value = true } catch (e) { error.value = e.message }
})

async function perform(path, method, body) {
  if (busy.value) return false
  busy.value = true; error.value = ''
  try { await api(path, method, body); await load(); deleting.value = ''; categoryDelete.value = ''; return true }
  catch (e) { error.value = e.message; return false }
  finally { busy.value = false }
}
async function edit(item) {
  editing.value = item ? { ...item } : { name: '', amount: '', unit: '', kind: '食材', category_id: category.value || stock.value.categories.find(c => c.name === '其他')?.id || stock.value.categories[0]?.id, location: location.value || '冷藏', status: 'active', notes: '' }
  error.value = ''; await nextTick(); document.querySelector('#fridge-food-name')?.focus()
}
function classify() {
  if (!editing.value.id && isCondiment(editing.value.name)) {
    editing.value.kind = '调料'; editing.value.location = '常温'
    editing.value.category_id = stock.value.categories.find(c => c.name === '调料')?.id || editing.value.category_id
  }
}
async function save() {
  const item = editing.value
  if (await perform('/fridge/items' + (item.id ? '/' + item.id : ''), item.id ? 'PUT' : 'POST', item)) {
    editing.value = null
    if (!item.id) stockPage.value = 1
  }
}
async function addCategory() {
  if (await perform('/fridge/categories', 'POST', { name: newCategory.value.trim() })) newCategory.value = ''
}

watch([query, category, location, status], () => { stockPage.value = 1 })
watch(stockPages, n => { stockPage.value = Math.min(stockPage.value, n) })
const dialogOpen = computed(() => !!editing.value || managing.value)
let priorFocus, priorOverflow
function closeDialog() { if (!busy.value) { editing.value = null; managing.value = false; error.value = '' } }
function dialogKeys(event) {
  if (!dialogOpen.value) return
  if (event.key === 'Escape') { event.preventDefault(); closeDialog() }
}
watch(dialogOpen, async open => {
  if (open) { priorFocus = document.activeElement; priorOverflow = document.body.style.overflow; document.body.style.overflow = 'hidden'; await nextTick(); document.querySelector('.fridge-dialog input')?.focus() }
  else { document.body.style.overflow = priorOverflow ?? ''; await nextTick(); if (priorFocus?.isConnected) priorFocus.focus() }
})
onMounted(() => document.addEventListener('keydown', dialogKeys))
onBeforeUnmount(() => { document.removeEventListener('keydown', dialogKeys); if (dialogOpen.value) document.body.style.overflow = priorOverflow ?? '' })
</script>

<template>
  <section class="kj kj-search-page">
    <header class="kj-compact-head">
      <h1>{{ showInventory ? '常备食材' : '按食材搜菜' }}<span class="title-dot">。</span></h1>
      <div class="kj-head-actions">
        <button v-if="showInventory" class="kj-primary" :disabled="!ready || busy" @click="edit()"><Plus :size="15" />添加</button>
        <button class="kj-soft-btn" @click="showInventory = !showInventory">
          <Refrigerator :size="15" /> {{ showInventory ? '返回搜菜' : `常备食材${active.length ? ' (' + active.length + ')' : ''}` }}
        </button>
      </div>
    </header>

    <p v-if="error && !dialogOpen" class="kj-error" role="alert">{{ error }}</p>

    <!-- Primary: Low-friction Fuzzy Ingredient Search + AI -->
    <template v-if="!showInventory">
      <div class="kj-card kj-fuzzy-box">
        <label class="kj-fuzzy-input">
          <Search :size="18" />
          <input
            v-model="rawInput"
            placeholder="手边有什么？随便打，如：鸡蛋 半颗白菜 挂面"
            aria-label="输入手边食材"
            @keydown.enter.prevent="askAi"
          />
          <button v-if="rawInput" type="button" class="kj-clear-btn" aria-label="清空" @click="rawInput = ''; aiDishes = []"><X :size="15" /></button>
        </label>

        <div class="kj-chip-strip" role="group" aria-label="常见食材快选">
          <button v-if="active.length" type="button" class="kj-chip-btn is-accent" @click="fillFromFridge">
            带入冰箱 ({{ active.length }})
          </button>
          <button
            v-for="word in quickPicks"
            :key="word"
            type="button"
            :class="['kj-chip-btn', { 'is-active': tokens.includes(word) }]"
            @click="toggleQuick(word)"
          >
            {{ word }}
          </button>
        </div>

        <div class="kj-fuzzy-bar">
          <span class="kj-muted" v-if="tokens.length">已识别：{{ tokens.join('、') }}</span>
          <span class="kj-muted" v-else>点上面标签或直接打字，不用填克数</span>
          <button class="kj-primary" :disabled="aiBusy || (!tokens.length && !active.length)" @click="askAi">
            <Sparkles :size="15" /> {{ aiBusy ? 'AI 正在想…' : 'AI 灵感推荐' }}
          </button>
        </div>
      </div>

      <!-- AI Suggestions -->
      <p v-if="aiError" class="kj-error" role="alert">{{ aiError }}</p>
      <section v-if="aiDishes.length" class="kj-fuzzy-section">
        <div class="kj-sub-head">
          <h2>AI 灵感推荐</h2>
          <button class="kj-link" @click="aiDishes = []">收起</button>
        </div>
        <div class="kj-ai-list">
          <article v-for="dish in aiDishes" :key="dish.name" class="kj-card kj-ai-card">
            <div>
              <h3>{{ dish.name }}</h3>
              <p class="kj-muted">{{ dish.reason }}</p>
            </div>
            <button class="kj-soft-btn" @click="emit('ai-cook', { dish, ingredients: tokens.join('、') })">生成食谱</button>
          </article>
        </div>
      </section>

      <!-- Fuzzy Local Matches -->
      <section class="kj-fuzzy-section">
        <div class="kj-sub-head">
          <h2>菜谱库匹配</h2>
          <span class="kj-muted" v-if="tokens.length">找到 {{ fuzzyMatches.length }} 道</span>
        </div>

        <div v-if="!tokens.length" class="kj-empty-quiet">
          <p>随便敲一两样手边食材，马上从你的菜谱库里挑出能做的菜，也可以让 AI 直接出主意。</p>
        </div>

        <div v-else-if="fuzzyMatches.length" class="kj-match-grid">
          <article v-for="item in fuzzyMatches" :key="item.recipe.id" class="kj-card kj-match-card">
            <div class="kj-match-top" @click="emit('detail', item.recipe)">
              <img v-if="item.recipe.cover" class="kj-match-thumb" :src="item.recipe.cover" :alt="item.recipe.name" loading="lazy" />
              <span v-else class="kj-match-emoji">{{ item.recipe.emoji || '🍲' }}</span>
              <div class="kj-match-info">
                <h3>{{ item.recipe.name }}</h3>
                <p class="kj-match-hit">命中：{{ item.matched.join('、') }}</p>
                <small v-if="item.missing.length" class="kj-muted">还差：{{ item.missing.slice(0, 3).join('、') }}{{ item.missing.length > 3 ? '等' : '' }}</small>
                <small v-else class="kj-hit-all">主料齐全，直接开火</small>
              </div>
            </div>
            <div class="kj-match-actions">
              <button class="kj-primary" @click="emit('cook', item.recipe.id)"><Flame :size="14" /> 开始做</button>
              <button @click="emit('select', item.recipe.id)">{{ selected.includes(item.recipe.id) ? '已选入' : '选入菜单' }}</button>
            </div>
          </article>
        </div>

        <div v-else class="kj-empty-quiet">
          <p>菜谱库里暂时没有包含「{{ tokens.join('、') }}」的菜，试试点上面的 <b>AI 灵感推荐</b> 现出一道。</p>
        </div>
      </section>
    </template>

    <!-- Secondary: Full Fridge Inventory -->
    <template v-else>
      <p v-if="!ready" class="kj-muted" role="status">正在读取常备食材…</p>
      <template v-else>
        <div class="fridge-toolbar">
          <div class="fridge-tabs">
            <button :class="{ chosen: status === 'active' }" @click="status = 'active'">在库 {{ active.length }}</button>
            <button :class="{ chosen: status === 'used' }" @click="status = 'used'">已用完 {{ used }}</button>
          </div>
          <button class="text-button" @click="managing = true; error = ''"><SlidersHorizontal :size="15" />管理分类</button>
        </div>
        <div class="fridge-filters">
          <label class="search"><Search :size="16" /><input v-model="query" placeholder="搜索食材" aria-label="搜索冰箱食品" /></label>
          <select v-model="location" aria-label="按存放位置筛选"><option value="">全部位置</option><option v-for="place in locations" :key="place">{{ place }}</option></select>
        </div>
        <div class="fridge-food-grid">
          <article v-for="item in visibleRows" :key="item.id" class="fridge-food" :class="{ 'food-used': item.status === 'used' }">
            <div class="fridge-food-top"><span>{{ categoryName(item.category_id) }} · {{ item.kind }}</span><span>{{ item.location }}</span></div>
            <h3>{{ item.name }}</h3>
            <p class="fridge-quantity">{{ item.amount || item.unit ? item.amount + item.unit : '数量未填' }}</p>
            <div class="fridge-food-actions">
              <button class="text-button" :disabled="busy" @click="edit(item)"><Pencil :size="13" />编辑</button>
              <button class="text-button" :disabled="busy" @click="perform('/fridge/items/' + item.id, 'PUT', { ...item, status: item.status === 'used' ? 'active' : 'used' })"><RotateCcw v-if="item.status === 'used'" :size="13" /><Check v-else :size="13" />{{ item.status === 'used' ? '恢复' : '用完' }}</button>
              <button class="icon-button danger" :disabled="busy" @click="deleting = deleting === item.id ? '' : item.id"><Trash2 :size="14" /></button>
            </div>
            <div v-if="deleting === item.id" class="fridge-confirm"><span>删除？</span><button :disabled="busy" @click="perform('/fridge/items/' + item.id, 'DELETE')">确定</button><button :disabled="busy" @click="deleting = ''">取消</button></div>
          </article>
        </div>
        <div v-if="!rows.length" class="kj-empty-quiet"><p>还没有记录常备食材，点右上角「添加」即可。</p></div>
        <div v-if="stockPages > 1" class="fridge-pagination"><button class="secondary" :disabled="stockPage === 1" @click="stockPage--">上一页</button><span>{{ stockPage }} / {{ stockPages }}</span><button class="secondary" :disabled="stockPage === stockPages" @click="stockPage++">下一页</button></div>
      </template>
    </template>

    <Teleport to="body">
      <div v-if="dialogOpen" class="overlay fridge-dialog-overlay" @click.self="closeDialog">
        <section class="modal fridge-dialog" role="dialog" aria-modal="true" aria-labelledby="fridge-dialog-title">
          <p v-if="error" class="alert" role="alert">{{ error }}</p>
          <form v-if="editing" class="fridge-editor" @submit.prevent="save">
            <div class="fridge-section-title"><h2 id="fridge-dialog-title">{{ editing.id ? '编辑食材' : '添加食材' }}</h2><button type="button" class="text-button" :disabled="busy" @click="closeDialog"><X :size="15" />取消</button></div>
            <div class="fridge-form-grid">
              <label>名称 <span>必填</span><input id="fridge-food-name" v-model="editing.name" required maxlength="100" list="fridge-ingredient-suggestions" placeholder="如：鸡蛋、西兰花" @change="classify" /><datalist id="fridge-ingredient-suggestions"><option v-for="name in suggestions" :key="name" :value="name" /></datalist></label>
              <label>数量<input v-model="editing.amount" maxlength="100" placeholder="可选" /></label>
              <label>单位<select v-model="editing.unit"><option value="">未填</option><option v-if="editing.unit && !UNITS.includes(editing.unit)" :value="editing.unit">{{ editing.unit }}</option><option v-for="unit in UNITS" :key="unit" :value="unit">{{ unit }}</option></select></label>
              <label>用途<select v-model="editing.kind"><option>食材</option><option>调料</option></select></label>
              <label>分类<select v-model="editing.category_id" required><option v-for="c in stock.categories" :key="c.id" :value="c.id">{{ c.name }}</option></select></label>
              <label>位置<select v-model="editing.location"><option v-for="place in locations" :key="place">{{ place }}</option></select></label>
            </div>
            <div class="fridge-form-footer"><button class="primary wide" :disabled="busy">{{ busy ? '保存中…' : '保存' }}<Check :size="16" /></button></div>
          </form>
          <section v-if="managing" class="fridge-categories">
            <div class="fridge-section-title"><h2 id="fridge-dialog-title">食材分类</h2><button type="button" class="text-button" :disabled="busy" @click="closeDialog">关闭</button></div>
            <div class="fridge-category-grid">
              <div v-for="c in stock.categories" :key="c.id" class="fridge-category-row">
                <input :value="renames[c.id] ?? c.name" maxlength="40" @input="renames[c.id] = $event.target.value" />
                <button class="icon-button" :disabled="busy" @click="perform('/fridge/categories/' + c.id, 'PATCH', { name: renames[c.id] ?? c.name })"><Check :size="16" /></button>
                <button class="icon-button danger" :disabled="busy" @click="categoryDelete = categoryDelete === c.id ? '' : c.id"><Trash2 :size="15" /></button>
                <div v-if="categoryDelete === c.id" class="fridge-confirm"><span>删除？</span><button :disabled="busy" @click="perform('/fridge/categories/' + c.id, 'DELETE')">确定</button><button :disabled="busy" @click="categoryDelete = ''">取消</button></div>
              </div>
            </div>
            <form class="fridge-new-category" @submit.prevent="addCategory"><input v-model="newCategory" required maxlength="40" placeholder="新建分类" /><button class="secondary" :disabled="busy || !newCategory.trim()"><Plus :size="15" />新建</button></form>
          </section>
        </section>
      </div>
    </Teleport>
  </section>
</template>

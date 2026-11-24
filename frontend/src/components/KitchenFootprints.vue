<script setup>
import { computed, ref, watch } from 'vue'
import { ArrowUpRight, Plus, ChevronLeft, ChevronRight, CalendarDays, BookMarked, History, Sparkles } from 'lucide-vue-next'
import { effectiveDishes, recordPhoto, buildCalendarMonth } from '../cookingJournal.js'
import CookingRecordDetail from './CookingRecordDetail.vue'
import '../kitchen-journal.css'

const props = defineProps({ journal: { type: Object, required: true } })
const emit = defineEmits(['browse', 'cook', 'manual'])

const today = new Date().toLocaleDateString('sv-SE', { timeZone: 'Asia/Shanghai' })
const currentYM = today.slice(0, 7)

const mode = ref('calendar')
const activeMonth = ref(currentYM)
const monthRecords = ref([])
const monthLoading = ref(false)
const selectedDate = ref(today)
const detail = ref(null)
const showManual = ref(false)
const manual = ref('')
const manualDate = ref(today)
const localError = ref('')

const repertoireFilter = ref('all')
const expandedDish = ref('')
const dishHistory = ref({})
const historyLoading = ref('')
let monthGeneration = 0

const calendar = computed(() => buildCalendarMonth(activeMonth.value, monthRecords.value, today))
const selectedDayCell = computed(() => calendar.value.cells.find(c => c.date === selectedDate.value) || null)
const selectedRecords = computed(() => selectedDayCell.value?.records || [])
const cookedCells = computed(() => calendar.value.cells.filter(c => c.inMonth && c.records.length).reverse())

const filteredRepertoire = computed(() => {
  const list = props.journal.summary.repertoire || []
  if (repertoireFilter.value === 'all') return list
  return list.filter(d => d.status === repertoireFilter.value)
})

const allPhotos = record => effectiveDishes(record).flatMap(d => d.photos || [])

const safely = async fn => {
  localError.value = ''
  try { return await fn() } catch (e) { localError.value = e.message }
}

async function fetchMonth(ym = activeMonth.value) {
  if (props.journal.accountId == null) return
  const gen = ++monthGeneration
  monthLoading.value = true
  try {
    const items = await props.journal.loadMonth(ym)
    if (gen !== monthGeneration) return
    monthRecords.value = items
    const datesWithRecords = items.map(r => r.cooked_on).filter(Boolean).sort()
    if (!selectedDate.value.startsWith(ym) || (!datesWithRecords.includes(selectedDate.value) && datesWithRecords.length)) {
      selectedDate.value = datesWithRecords.at(-1) || (ym === currentYM ? today : `${ym}-01`)
    }
  } catch (e) {
    if (gen === monthGeneration) localError.value = e.message
  } finally {
    if (gen === monthGeneration) monthLoading.value = false
  }
}

watch(() => [props.journal.accountId, activeMonth.value, props.journal.summary.meals], () => {
  fetchMonth(activeMonth.value)
}, { immediate: true })

function shiftMonth(delta) {
  const [y, m] = activeMonth.value.split('-').map(Number)
  const d = new Date(Date.UTC(y, m - 1 + delta, 1))
  activeMonth.value = `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}`
}

function goThisMonth() {
  activeMonth.value = currentYM
  selectedDate.value = today
}

function openManualFor(date = today) {
  manualDate.value = date || today
  showManual.value = true
}

async function open(id) {
  const record = await safely(() => props.journal.getRecord(id))
  if (record) detail.value = record
}

async function addManual() {
  await safely(async () => {
    const r = await props.journal.start({ manual_name: manual.value.trim(), cooked_on: manualDate.value || today })
    if (r) {
      manual.value = ''
      showManual.value = false
      emit('manual', r)
      emit('cook')
    }
  })
}

async function again(dish) {
  await safely(async () => {
    const r = await props.journal.start({ manual_name: '继续练习', dish_key: dish.dish_key })
    if (r) emit('cook')
  })
}

async function toggleEvolution(dish) {
  if (expandedDish.value === dish.dish_key) {
    expandedDish.value = ''
    return
  }
  expandedDish.value = dish.dish_key
  historyLoading.value = dish.dish_key
  await safely(async () => {
    const list = await props.journal.history(dish.dish_key)
    dishHistory.value = { ...dishHistory.value, [dish.dish_key]: list }
  })
  if (historyLoading.value === dish.dish_key) historyLoading.value = ''
}

function dishInRecord(record, dishKey) {
  return effectiveDishes(record).find(d => d.dish_key === dishKey)
}

function formatDayHeading(dateStr) {
  if (!dateStr) return ''
  const [, m, d] = dateStr.split('-').map(Number)
  return `${m} 月 ${d} 日`
}

function onDetailClosed() {
  detail.value = null
  fetchMonth(activeMonth.value)
}
</script>

<template>
  <section class="kj kj-footprints">
    <header class="kj-compact-head">
      <h1>下厨记录<span class="title-dot">。</span></h1>
      <button class="kj-soft-btn" @click="showManual ? (showManual = false) : openManualFor(selectedDate)">
        <Plus :size="15" /> 补记
      </button>
    </header>

    <form v-if="showManual" class="kj-card kj-manual-drawer" @submit.prevent="addManual">
      <div class="kj-spread">
        <strong>补记一餐</strong>
        <button type="button" class="kj-link" @click="showManual = false">收起</button>
      </div>
      <div class="kj-manual-fields">
        <label>菜名<input id="footprint-manual" v-model="manual" required maxlength="80" placeholder="写下做过的菜名" /></label>
        <label>日期<input v-model="manualDate" type="date" :max="today" /></label>
        <button class="kj-primary" :disabled="journal.finalizing || !manual.trim()">去记录</button>
      </div>
    </form>

    <p v-if="localError || journal.error" class="kj-error" role="alert">{{ localError || journal.error }}</p>

    <!-- Quiet Anthropic-style Metric Strip -->
    <section class="kj-metric-bar" aria-label="下厨统计">
      <div><strong>{{ journal.summary.meals }}</strong><span>累计餐次</span></div>
      <div><strong>{{ journal.summary.dishes }}</strong><span>尝试菜品</span></div>
      <div><strong>{{ journal.summary.level.title }}</strong><span>当前阶段</span></div>
    </section>

    <div class="kj-seg-tabs" role="tablist">
      <button :aria-pressed="mode === 'calendar'" @click="mode = 'calendar'">
        <CalendarDays :size="15" /> 食光月历
      </button>
      <button :aria-pressed="mode === 'repertoire'" @click="mode = 'repertoire'">
        <BookMarked :size="15" /> 拿手菜进化史
      </button>
    </div>

    <!-- View A: 食光月历 -->
    <div v-if="mode === 'calendar'" class="kj-calendar-layout">
      <article class="kj-card kj-calendar-card">
        <div class="kj-cal-head">
          <div class="kj-cal-nav">
            <button type="button" class="kj-icon-btn" aria-label="上个月" @click="shiftMonth(-1)"><ChevronLeft :size="17" /></button>
            <h2>{{ calendar.label }}</h2>
            <button type="button" class="kj-icon-btn" aria-label="下个月" @click="shiftMonth(1)"><ChevronRight :size="17" /></button>
          </div>
          <div class="kj-cal-meta">
            <span>开火 <b>{{ calendar.cookedDays }}</b> 天</span>
            <button v-if="activeMonth !== currentYM" type="button" class="kj-link" @click="goThisMonth">本月</button>
          </div>
        </div>

        <div class="kj-cal-weekdays" aria-hidden="true">
          <span>一</span><span>二</span><span>三</span><span>四</span><span>五</span><span>六</span><span>日</span>
        </div>

        <div class="kj-cal-grid" role="grid" :aria-label="calendar.label + '下厨日历'">
          <template v-for="(cell, idx) in calendar.cells" :key="cell.date || 'pad-' + idx">
            <div v-if="!cell.inMonth" class="kj-cal-cell is-pad" aria-hidden="true"></div>
            <button
              v-else
              type="button"
              :class="['kj-cal-cell', { 'has-meal': cell.records.length > 0, 'has-photo': !!cell.photo, 'is-selected': cell.date === selectedDate, 'is-today': cell.isToday }]"
              :aria-pressed="cell.date === selectedDate"
              :aria-label="`${cell.date}，${cell.records.length ? cell.records.length + ' 餐' : '无记录'}`"
              @click="selectedDate = cell.date"
            >
              <img v-if="cell.photo" class="kj-cal-thumb" :src="cell.photo" alt="" loading="lazy" />
              <span class="kj-cal-day">{{ cell.day }}</span>
              <span v-if="cell.records.length" class="kj-cal-dots" aria-hidden="true">
                <i v-for="n in Math.min(cell.records.length, 3)" :key="n"></i>
              </span>
            </button>
          </template>
        </div>

        <div v-if="cookedCells.length" class="kj-cal-quick">
          <button
            v-for="cell in cookedCells"
            :key="cell.date"
            type="button"
            :class="['kj-quick-day', { 'is-active': cell.date === selectedDate }]"
            @click="selectedDate = cell.date"
          >
            {{ cell.day }}日 · {{ effectiveDishes(cell.records[0]).map(d => d.snapshot.name).slice(0, 1).join('') || '一餐' }}
          </button>
        </div>
      </article>

      <aside class="kj-day-panel">
        <div class="kj-day-head">
          <h3>{{ formatDayHeading(selectedDate) }}</h3>
          <span class="kj-muted" v-if="selectedRecords.length">{{ selectedRecords.length }} 餐</span>
        </div>

        <p v-if="monthLoading" class="kj-muted" role="status">读取中…</p>

        <div v-else-if="selectedRecords.length" class="kj-day-meals">
          <article v-for="record in selectedRecords" :key="record.id" class="kj-card kj-meal-card">
            <img v-if="recordPhoto(record)" class="kj-meal-cover" :src="recordPhoto(record)" :alt="effectiveDishes(record).map(d => d.snapshot.name).join('、') + '成品照'" loading="lazy" />
            <div v-if="allPhotos(record).length > 1" class="kj-filmstrip">
              <img v-for="(url, i) in allPhotos(record).slice(1, 5)" :key="url" :src="url" :alt="`过程照${i + 1}`" loading="lazy" />
            </div>
            <div class="kj-meal-body">
              <div class="kj-spread">
                <h4>{{ record.title || effectiveDishes(record).map(d => d.snapshot.name).join('、') }}</h4>
                <span class="kj-muted">#{{ String(record.number).padStart(3, '0') }}</span>
              </div>
              <div class="kj-dish-tags">
                <span v-for="dish in record.dishes" :key="dish.id" :class="['kj-dish-chip', 'is-' + dish.outcome]">
                  {{ dish.snapshot.name }}
                  <em>{{ { success: '做成了', practice: '再练', skipped: '没做', pending: '待定' }[dish.outcome] }}</em>
                </span>
              </div>
              <p v-if="record.note || effectiveDishes(record).some(d => d.note)" class="kj-meal-note">
                {{ record.note || effectiveDishes(record).map(d => d.note).filter(Boolean).join(' · ') }}
              </p>
              <button class="kj-soft-btn kj-wide" @click="open(record.id)">
                查看详情与编辑 <ArrowUpRight :size="15" />
              </button>
            </div>
          </article>
        </div>

        <div v-else class="kj-card kj-day-empty">
          <Sparkles :size="22" stroke-width="1.5" />
          <p class="kj-muted">这一天还没有下厨记录</p>
          <button class="kj-primary" @click="openManualFor(selectedDate)">补记这一天</button>
        </div>
      </aside>
    </div>

    <!-- View C: 拿手菜进化史 -->
    <div v-else class="kj-repertoire-view">
      <div class="kj-chip-strip" role="group" aria-label="按熟练度筛选">
        <button
          v-for="tab in [{ id: 'all', label: '全部' }, { id: 'signature', label: '我的拿手菜' }, { id: 'practice', label: '练习中' }, { id: 'tried', label: '试过' }]"
          :key="tab.id"
          :class="['kj-chip-btn', { 'is-active': repertoireFilter === tab.id }]"
          @click="repertoireFilter = tab.id"
        >
          {{ tab.label }}
        </button>
      </div>

      <div v-if="filteredRepertoire.length" class="kj-repertoire-grid">
        <article v-for="dish in filteredRepertoire" :key="dish.dish_key" class="kj-card kj-dish-card">
          <div class="kj-spread">
            <div>
              <h3>{{ dish.name }}</h3>
              <small class="kj-muted">做过 {{ dish.attempts }} 次 · 做成 {{ dish.successes }} 次 · {{ dish.last_cooked_on }}</small>
            </div>
            <span :class="['kj-status-pill', 'is-' + dish.status]">
              {{ { tried: '试过', practice: '练习中', signature: '拿手菜' }[dish.status] }}
            </span>
          </div>

          <p v-if="dish.last_note" class="kj-quote">{{ dish.last_note }}</p>

          <div class="kj-dish-controls">
            <select class="kj-mini-select" aria-label="菜品状态" :disabled="journal.finalizing" :value="dish.status" @change="safely(() => journal.markDish(dish.dish_key, $event.target.value))">
              <option value="tried">试过</option>
              <option value="practice">练习中</option>
              <option value="signature">我的拿手菜</option>
            </select>
            <div class="kj-actions">
              <button @click="toggleEvolution(dish)">
                <History :size="14" /> {{ expandedDish === dish.dish_key ? '收起' : '进化史' }}
              </button>
              <button class="kj-primary" :disabled="journal.finalizing" @click="again(dish)">再做一次</button>
            </div>
          </div>

          <section v-if="expandedDish === dish.dish_key" class="kj-evolution" aria-live="polite">
            <p v-if="historyLoading === dish.dish_key" class="kj-muted">加载中…</p>
            <ol v-else-if="dishHistory[dish.dish_key]?.length" class="kj-evo-list">
              <li v-for="(item, idx) in dishHistory[dish.dish_key]" :key="item.id" class="kj-evo-step">
                <div class="kj-evo-dot"></div>
                <div class="kj-evo-content">
                  <div class="kj-spread">
                    <strong>第 {{ idx + 1 }} 次 · {{ item.cooked_on }}</strong>
                    <span :class="['kj-outcome-chip', 'is-' + (dishInRecord(item, dish.dish_key)?.outcome || 'success')]">
                      {{ dishInRecord(item, dish.dish_key)?.outcome === 'success' ? '做成了' : '再练' }}
                    </span>
                  </div>
                  <p v-if="dishInRecord(item, dish.dish_key)?.note">{{ dishInRecord(item, dish.dish_key).note }}</p>
                  <div v-if="dishInRecord(item, dish.dish_key)?.photos?.length" class="kj-evo-photos">
                    <img v-for="url in dishInRecord(item, dish.dish_key).photos.slice(0, 4)" :key="url" :src="url" :alt="`${dish.name}第${idx + 1}次`" loading="lazy" />
                  </div>
                  <button type="button" class="kj-link" @click="open(item.id)">查看这餐 →</button>
                </div>
              </li>
            </ol>
            <p v-else class="kj-muted">暂无更多历史。</p>
          </section>
        </article>
      </div>

      <div v-else class="kj-card kj-day-empty">
        <BookMarked :size="24" stroke-width="1.5" />
        <p class="kj-muted">{{ journal.summary.repertoire.length ? '该分类下暂无菜品' : '还没有做过的菜，去首页或闯关做第一顿吧' }}</p>
        <button class="kj-primary" @click="emit('browse')">去选一道菜</button>
      </div>
    </div>

    <CookingRecordDetail :journal="journal" :record="detail" @close="onDetailClosed" @cook="emit('cook')" />
  </section>
</template>

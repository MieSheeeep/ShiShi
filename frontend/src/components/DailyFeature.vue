<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { ArrowUpRight, ArrowRight, CalendarDays, Clock3, Users, X, BookmarkPlus, ChevronLeft, ChevronRight } from 'lucide-vue-next'
import { editions, shanghaiDate, selectEdition, publishedEditions, editionDraft, diaryFor } from '../dailyContent'

const emit = defineEmits(['collect'])
const today = ref(shanghaiDate())
const archive = ref(false)
const opened = ref(null)
const archiveButton = ref(null)
const viewButton = ref(null)
const closeButton = ref(null)

const current = computed(() => selectEdition(editions, today.value))
const diary = computed(() => diaryFor(today.value))
const isToday = computed(() => current.value?.date === today.value)
const history = computed(() => publishedEditions(editions, today.value).filter(e => e.date !== current.value?.date))
const dateNumber = date => date.slice(8)
const dateMonth = date => `${date.slice(0, 4)} / ${date.slice(5, 7)}`

let ticker
function syncDate() { today.value = shanghaiDate() }
async function showArchive() { archive.value = true; await nextTick(); closeButton.value?.focus() }
async function showEdition(edition) { opened.value = edition; await nextTick(); closeButton.value?.focus() }
async function close() {
  const fromArchive = archive.value
  opened.value = null
  archive.value = false
  await nextTick()
  ;(fromArchive ? archiveButton.value : viewButton.value)?.focus()
}
function keys(event) {
  if (event.key === 'Escape' && (archive.value || opened.value)) { event.stopPropagation(); close() }
  if (event.key === 'Tab' && (archive.value || opened.value)) {
    const nodes = [...document.querySelectorAll('.daily-overlay button:not(:disabled), .daily-overlay a[href]')].filter(el => el.getClientRects().length)
    const first = nodes[0], last = nodes.at(-1)
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
  }
}
function collect() {
  const draft = editionDraft(opened.value)
  opened.value = null
  archive.value = false
  emit('collect', draft)
}
onMounted(() => {
  ticker = setInterval(syncDate, 1000)
  document.addEventListener('visibilitychange', syncDate)
  document.addEventListener('keydown', keys)
})
onBeforeUnmount(() => {
  clearInterval(ticker)
  document.removeEventListener('visibilitychange', syncDate)
  document.removeEventListener('keydown', keys)
})
</script>

<template>
  <div v-if="current" class="daily-slit" role="region" aria-label="今日节气与推荐">
    <button ref="viewButton" type="button" class="daily-slit-main" @click="showEdition(current)">
      <span class="daily-slit-badge">{{ diary?.term || (isToday ? '今日' : '精选') }}</span>
      <span class="daily-slit-title">{{ current.name }} · {{ current.headline }}</span>
      <span class="daily-slit-go">查看<ChevronRight :size="15" /></span>
    </button>
    <button ref="archiveButton" type="button" class="daily-slit-archive" aria-label="往期精选" title="往期精选" @click="showArchive">
      <CalendarDays :size="15" />
    </button>
  </div>

  <Teleport to="body">
    <div v-if="archive || opened" class="overlay daily-overlay" @click.self="close">
      <section class="modal daily-modal" role="dialog" aria-modal="true" :aria-labelledby="opened ? 'edition-title' : 'archive-title'">
        <button ref="closeButton" class="close" aria-label="关闭精选" @click="close"><X /></button>
        <template v-if="opened">
          <button v-if="archive" class="text-button edition-back" @click="opened = null"><ChevronLeft :size="14" />返回往期</button>
          <div class="eyebrow">{{ opened.date }} · 第 {{ opened.issue }} 期</div>
          <h2 id="edition-title">{{ opened.name }}</h2>
          <p class="edition-lead">{{ opened.intro }}</p>
          <figure v-if="opened.image" class="edition-image"><img :src="opened.image" :alt="opened.imageAlt" /></figure>
          <div class="edition-meta"><span><Clock3 :size="15" />{{ opened.minutes }} 分钟</span><span><Users :size="15" />{{ opened.servings }}</span><span>{{ opened.tools }}</span></div>
          <section class="edition-reason"><span>为什么选这道</span><p>{{ opened.reason }}</p></section>
          <section v-if="opened.diary" class="edition-culture edition-diary">
            <span>节气日记 · {{ opened.diary.term }}</span>
            <h3>{{ opened.diary.title }}</h3>
            <p>{{ opened.diary.text }}</p>
            <p class="diary-background">{{ opened.diary.background }}</p>
            <a :href="opened.diary.reference.url" target="_blank" rel="noopener noreferrer">{{ opened.diary.reference.title }}<ArrowUpRight :size="13" /></a>
          </section>
          <h3>准备材料</h3>
          <div class="ingredient-line" v-for="[name, amount] in opened.ingredients" :key="name"><span>{{ name }}</span><strong>{{ amount }}</strong></div>
          <h3>一起做饭</h3>
          <ol class="edition-steps"><li v-for="step in opened.steps" :key="step">{{ step }}</li></ol>
          <section class="edition-pairing"><h3>这一餐，怎么搭</h3><p>{{ opened.pairing }}</p></section>
          <section class="edition-culture">
            <span>餐桌小记</span>
            <h3>{{ opened.cultureTitle }}</h3>
            <p>{{ opened.culture }}</p>
            <a v-for="source in opened.references" :key="source.url" :href="source.url" target="_blank" rel="noopener noreferrer">{{ source.title }}<ArrowUpRight :size="13" /></a>
            <small v-if="!opened.references.length">食拾原创餐桌随记</small>
          </section>
          <button class="primary wide" @click="collect"><BookmarkPlus :size="17" />编辑并收藏这道菜<ArrowRight :size="16" /></button>
        </template>
        <template v-else>
          <h2 id="archive-title">往期精选</h2>
          <p class="muted">挑一道合心意的，收进自己的菜谱库。</p>
          <button v-for="edition in history" :key="edition.date" class="edition-archive-row" @click="showEdition(edition)">
            <span class="archive-day"><strong>{{ dateNumber(edition.date) }}</strong><small>{{ dateMonth(edition.date) }}</small></span>
            <span class="archive-info"><small>{{ edition.theme }}</small><strong>{{ edition.name }}</strong><span>{{ edition.headline }}</span></span>
            <ArrowUpRight :size="19" />
          </button>
          <p v-if="!history.length" class="muted">这是第一期，往后的味道慢慢积攒。</p>
        </template>
      </section>
    </div>
  </Teleport>
</template>

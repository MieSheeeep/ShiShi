<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { ArrowUpRight, ArrowRight, CalendarDays, Clock3, Users, X, BookmarkPlus, ChevronLeft } from 'lucide-vue-next'
import { editions, shanghaiDate, selectEdition, publishedEditions, editionDraft, diaryFor } from '../dailyContent'
const emit=defineEmits(['collect'])
const today=ref(shanghaiDate()), archive=ref(false), opened=ref(null), archiveButton=ref(null), viewButton=ref(null), closeButton=ref(null)
const current=computed(()=>selectEdition(editions,today.value))
const diary=computed(()=>diaryFor(today.value))
const isToday=computed(()=>current.value?.date===today.value)
const history=computed(()=>publishedEditions(editions,today.value).filter(e=>e.date!==current.value?.date))
const dateText=date=>new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',month:'long',day:'numeric',weekday:'long'}).format(new Date(`${date}T12:00:00+08:00`))
const dateNumber=date=>date.slice(8)
const dateMonth=date=>`${date.slice(0,4)} / ${date.slice(5,7)}`
const todayParts=computed(()=>{
  const [year,month,day]=today.value.split('-')
  return {top:`${year} / ${month}`,day,weekday:new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',weekday:'long'}).format(new Date(`${today.value}T12:00:00+08:00`))}
})
let ticker
function syncDate(){today.value=shanghaiDate()}
async function showArchive(){archive.value=true;await nextTick();closeButton.value?.focus()}
async function showEdition(edition){opened.value=edition;await nextTick();closeButton.value?.focus()}
async function close(){const fromArchive=archive.value;opened.value=null;archive.value=false;await nextTick();(fromArchive?archiveButton.value:viewButton.value)?.focus()}
function keys(event){
  if(event.key==='Escape'&&(archive.value||opened.value)){event.stopPropagation();close()}
  if(event.key==='Tab'&&(archive.value||opened.value)){
    const nodes=[...document.querySelectorAll('.daily-overlay button:not(:disabled), .daily-overlay a[href]')].filter(el=>el.getClientRects().length)
    const first=nodes[0],last=nodes.at(-1)
    if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus()}
    else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus()}
  }
}
function collect(){const draft=editionDraft(opened.value);opened.value=null;archive.value=false;emit('collect',draft)}
onMounted(()=>{ticker=setInterval(syncDate,1000);document.addEventListener('visibilitychange',syncDate);document.addEventListener('keydown',keys)})
onBeforeUnmount(()=>{clearInterval(ticker);document.removeEventListener('visibilitychange',syncDate);document.removeEventListener('keydown',keys)})
</script>
<template>
<template v-if="current">
<section class="daily-feature" aria-labelledby="daily-heading">
  <div class="daily-copy">
    <div class="daily-topline"><span class="daily-kicker"><i></i>{{isToday?'今日精选':'最近精选'}}</span><span class="daily-season">{{current.theme}}</span></div>
    <h2 id="daily-heading">{{current.headline}}</h2>
    <p class="daily-intro">{{current.intro}}</p>
    <div class="daily-recipe-name"><span>{{current.name}}</span><span><Clock3 :size="13"/>{{current.minutes}} 分钟</span><span>{{current.servings}}</span></div>
    <div class="daily-actions"><button ref="viewButton" class="daily-read" @click="showEdition(current)">{{isToday?'看看今天的做法':'查看这期做法'}}<ArrowUpRight :size="17"/></button><button ref="archiveButton" class="daily-archive" @click="showArchive"><CalendarDays :size="14"/>往期精选</button></div>
    <div class="daily-footnote"><span>{{dateText(current.date)}}</span><span>食拾 · 每日一食</span></div>
  </div>
  <div class="daily-visual"><img v-if="current.image" :src="current.image" :alt="current.imageAlt" fetchpriority="high"/><div v-else class="daily-food-placeholder">{{current.emoji}}</div><div class="daily-date"><span>{{todayParts.top}}</span><strong>{{todayParts.day}}</strong><span>{{todayParts.weekday}}</span></div></div>
</section>
<section v-if="diary" class="solar-diary" aria-labelledby="solar-diary-title">
  <div class="solar-diary-label"><span>节气日记</span><strong>{{diary.term}}</strong><small>{{diary.date}}</small></div>
  <div class="solar-diary-copy"><h3 id="solar-diary-title">{{diary.title}}</h3><p>{{diary.text}}</p><div class="solar-diary-context"><span>{{diary.background}}</span><span>当季食材：{{diary.foods.join('、')}}</span><a :href="diary.reference.url" target="_blank" rel="noopener noreferrer">节气背景<ArrowUpRight :size="12"/></a></div></div>
</section>
</template>
<section v-else class="daily-empty"><h2>今天，也好好吃饭。</h2><p>精选内容尚未发布，先从自己的收藏里找一道喜欢的菜。</p></section>
<Teleport to="body"><div v-if="archive||opened" class="overlay daily-overlay" @click.self="close">
  <section class="modal daily-modal" role="dialog" aria-modal="true" :aria-labelledby="opened?'edition-title':'archive-title'">
    <button ref="closeButton" class="close" aria-label="关闭精选" @click="close"><X/></button>
    <template v-if="opened">
      <button v-if="archive" class="text-button edition-back" @click="opened=null"><ChevronLeft :size="14"/>返回往期</button>
      <div class="eyebrow">{{opened.date}} · 第 {{opened.issue}} 期</div><h2 id="edition-title">{{opened.name}}</h2><p class="edition-lead">{{opened.intro}}</p>
      <figure v-if="opened.image" class="edition-image"><img :src="opened.image" :alt="opened.imageAlt"/></figure>
      <div class="edition-meta"><span><Clock3 :size="15"/>{{opened.minutes}} 分钟</span><span><Users :size="15"/>{{opened.servings}}</span><span>{{opened.tools}}</span></div>
      <section class="edition-reason"><span>为什么选这道</span><p>{{opened.reason}}</p></section>
      <section v-if="opened.diary" class="edition-culture edition-diary"><span>节气日记 · {{opened.diary.term}}</span><h3>{{opened.diary.title}}</h3><p>{{opened.diary.text}}</p><p class="diary-background">{{opened.diary.background}}</p><a :href="opened.diary.reference.url" target="_blank" rel="noopener noreferrer">{{opened.diary.reference.title}}<ArrowUpRight :size="13"/></a></section>
      <h3>准备材料</h3><div class="ingredient-line" v-for="[name,amount] in opened.ingredients" :key="name"><span>{{name}}</span><strong>{{amount}}</strong></div>
      <h3>一起做饭</h3><ol class="edition-steps"><li v-for="step in opened.steps" :key="step">{{step}}</li></ol>
      <section class="edition-pairing"><h3>这一餐，怎么搭</h3><p>{{opened.pairing}}</p></section>
      <section class="edition-culture"><span>餐桌小记</span><h3>{{opened.cultureTitle}}</h3><p>{{opened.culture}}</p><a v-for="source in opened.references" :key="source.url" :href="source.url" target="_blank" rel="noopener noreferrer">{{source.title}}<ArrowUpRight :size="13"/></a><small v-if="!opened.references.length">食拾原创餐桌随记</small></section>
      <p class="edition-credit">食谱：食拾家常示范 · 可按人数与个人口味调整</p>
      <button class="primary wide" @click="collect"><BookmarkPlus :size="17"/>编辑并收藏这道菜<ArrowRight :size="16"/></button>
    </template>
    <template v-else>
      <div class="eyebrow">PREVIOUS SELECTIONS</div><h2 id="archive-title">往期精选</h2><p class="muted">把错过的好味道，再找回来。</p>
      <button v-for="edition in history" :key="edition.date" class="edition-archive-row" @click="showEdition(edition)"><span class="archive-day"><strong>{{dateNumber(edition.date)}}</strong><small>{{dateMonth(edition.date)}}</small></span><span class="archive-info"><small>{{edition.theme}}</small><strong>{{edition.name}}</strong><span>{{edition.headline}}</span></span><ArrowUpRight :size="19"/></button>
      <p v-if="!history.length" class="muted">这是我们的第一期，往后的味道慢慢积攒。</p>
    </template>
  </section>
</div></Teleport>
</template>

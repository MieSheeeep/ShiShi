<script setup>
import { computed, ref, watch, onBeforeUnmount } from 'vue'
import { Camera, Check, Flame, ArrowRight, Trophy, RotateCcw, Sparkles, Plus, Shuffle, ChevronLeft, ChevronRight, List, Layers, UtensilsCrossed, Lock, Star, BookOpen, X, Clock, Award, ChevronDown } from 'lucide-vue-next'
import { effectiveDishes, recordPhoto, previousAttempt, buildChapterMap, pickBlindBox, buildCelebration } from '../cookingJournal.js'
import { buildQuestView, allStages, stageById, stageForDish, starGoalsForDish, noteLength, starPips, rankTiers, rankLine, questAwards, hasAwards, cheerFor, formatElapsed, blindBoxOptions, RANK_RULE, QUEST_STAR_RULES, RANK_TIERS } from '../kitchenQuest.js'
import CookingRecordDetail from './CookingRecordDetail.vue'
import '../kitchen-journal.css'

const props = defineProps({
  journal: { type: Object, required: true },
  recipes: { type: Array, default: () => [] },
  pantryCount: { type: Number, default: 0 }
})
const emit = defineEmits(['browse', 'pantry', 'recorded', 'records', 'start-recipe'])

const manual = ref('')
const finishing = ref(false)
const viewMode = ref('card')
const activeDishIdx = ref(0)
const activeStepIdx = ref(0)
const showIngredients = ref(false)
const detail = ref(null)
const localError = ref('')
const blindBox = ref(null)
const blindIndex = ref(0)
const briefing = ref(null)
const showRules = ref(false)
const wasRevenge = ref(false)
const questBefore = ref(null)
const awardResult = ref(null)
const elapsed = ref(0)
let timer = null

const draft = computed(() => props.journal.draft)
const done = computed(() => props.journal.lastCompleted)
const priorNotes = ref({})
let historyGeneration = 0

const today = new Date().toLocaleDateString('sv-SE', { timeZone: 'Asia/Shanghai' })
const chapterMap = computed(() => buildChapterMap(props.journal.summary, props.recipes))
const questView = computed(() => buildQuestView(props.journal.quest, props.journal.summary, props.recipes))
const questChapters = computed(() => questView.value.chapters)
const questStages = computed(() => allStages(questView.value))
const rank = computed(() => questView.value.rank)
const rankProgress = computed(() => rank.value?.progress || 0)
const totals = computed(() => questView.value.totals)
const secrets = computed(() => questView.value.secrets)
const easterEggs = computed(() => questView.value.easterEggs)
const blindOptions = computed(() => blindBoxOptions(props.journal.quest))
const activeBlind = computed(() => blindOptions.value.length
  ? blindOptions.value[blindIndex.value % blindOptions.value.length]
  : blindBox.value)
const activeBlindStage = computed(() => {
  const option = activeBlind.value
  if (!option) return null
  return option.stage_id ? stageById(questView.value, option.stage_id) : option
})
const activeDish = computed(() => draft.value?.dishes?.[activeDishIdx.value] || draft.value?.dishes?.[0] || null)
const activeSteps = computed(() => activeDish.value?.snapshot?.steps || [])
const currentStep = computed(() => activeSteps.value[activeStepIdx.value] || null)
const activeQuestStage = computed(() => stageForDish(questView.value, activeDish.value))
const activeGoals = computed(() => starGoalsForDish(activeDish.value))
const cheer = computed(() => cheerFor(activeStepIdx.value, activeSteps.value.length, activeDish.value?.snapshot?.name || ''))
const awards = computed(() => awardResult.value)
const hasFreshAwards = computed(() => hasAwards(awardResult.value))

const celebration = computed(() => done.value ? buildCelebration(done.value, props.journal.summary, { wasRevenge: wasRevenge.value }) : null)

watch(() => [props.journal.accountId, draft.value?.id], async () => {
  const generation = ++historyGeneration
  const account = props.journal.accountId
  const session = draft.value
  priorNotes.value = {}
  activeDishIdx.value = 0
  activeStepIdx.value = 0
  showIngredients.value = false
  blindIndex.value = 0
  briefing.value = null
  if (!session) return
  await Promise.all(session.dishes.map(async dish => {
    try {
      const records = await props.journal.history(dish.dish_key)
      if (generation !== historyGeneration || account !== props.journal.accountId || session.id !== draft.value?.id) return
      const prior = previousAttempt(records, dish.dish_key, session.id)
      if (prior) priorNotes.value = { ...priorNotes.value, [dish.id]: prior }
    } catch { /* Optional history never prevents cooking. */ }
  }))
}, { immediate: true })

watch(activeDishIdx, () => { activeStepIdx.value = 0 })
watch(() => draft.value?.id, id => {
  if (id) {
    elapsed.value = 0
    clearInterval(timer)
    timer = setInterval(() => { elapsed.value++ }, 1000)
  } else {
    clearInterval(timer)
    timer = null
    elapsed.value = 0
  }
}, { immediate: true })
onBeforeUnmount(() => { historyGeneration++; clearInterval(timer) })

const attempt = async action => {
  localError.value = ''
  try { return await action() } catch (e) { localError.value = e.message }
}
function patch(value) { return attempt(() => props.journal.patch(value)) }
function dishPatch(dish, value) { return patch({ dishes: [{ id: dish.id, ...value }] }) }
function toggleStep(dish, id) {
  const steps = new Set(dish.completed_steps)
  steps.has(id) ? steps.delete(id) : steps.add(id)
  dishPatch(dish, { completed_steps: [...steps] })
}
function nextStep() {
  if (activeStepIdx.value < activeSteps.value.length - 1) {
    if (currentStep.value && activeDish.value && !activeDish.value.completed_steps.includes(currentStep.value.id)) {
      toggleStep(activeDish.value, currentStep.value.id)
    }
    activeStepIdx.value++
  } else {
    if (currentStep.value && activeDish.value && !activeDish.value.completed_steps.includes(currentStep.value.id)) {
      toggleStep(activeDish.value, currentStep.value.id)
    }
    finishing.value = true
  }
}
function prevStep() {
  if (activeStepIdx.value > 0) activeStepIdx.value--
}

async function upload(event, dish) {
  const files = [...event.target.files]
  event.target.value = ''
  for (const file of files) {
    if (dish.photos.length >= 12) break
    await attempt(async () => {
      const url = await props.journal.uploadPhoto(file)
      if (url && draft.value?.dishes.some(d => d.id === dish.id)) {
        await dishPatch(dish, { photos: [...dish.photos, url] })
      }
    })
  }
}

async function complete() {
  wasRevenge.value = Object.values(priorNotes.value).some(p => p?.dish?.outcome === 'practice')
  questBefore.value = props.journal.quest ? JSON.parse(JSON.stringify(props.journal.quest)) : null
  await attempt(async () => {
    const record = await props.journal.complete()
    if (record) {
      awardResult.value = questAwards(questBefore.value, props.journal.quest)
      finishing.value = false
      emit('recorded', record)
    }
  })
}

function openBriefing(stage) {
  if (!stage || stage.unlocked === false) return
  briefing.value = stage
}

async function startBriefing() {
  const stage = briefing.value
  if (!stage) return
  briefing.value = null
  awardResult.value = null
  questBefore.value = null
  if (questView.value.server && stage.id?.startsWith('s-')) {
    await attempt(() => props.journal.start({ quest_stage: stage.id }))
    return
  }
  if (stage.recipeId) {
    emit('start-recipe', stage.recipeId)
    return
  }
  if (stage.dishKey) {
    await attempt(() => props.journal.start({ manual_name: stage.name, dish_key: stage.dishKey }))
    return
  }
  await attempt(() => props.journal.start({ manual_name: stage.name }))
}

async function viewStageRecord(stage) {
  if (!stage.lastSessionId) return
  const record = await attempt(() => props.journal.getRecord(stage.lastSessionId))
  if (record) detail.value = record
}

function rollBlindBox() {
  if (blindOptions.value.length) {
    blindIndex.value = (blindIndex.value + 1) % blindOptions.value.length
    return
  }
  blindBox.value = pickBlindBox(props.recipes, props.journal.summary, Math.random())
}

function dismissDone() {
  props.journal.lastCompleted = null
  awardResult.value = null
  questBefore.value = null
}

const stageGoals = dish => starGoalsForDish(dish)

</script>

<template>
  <section class="kj kj-workspace">
    <!-- Compact 1-line Header when idle -->
    <header v-if="!draft" class="kj-compact-head">
      <h1>厨房闯关<span class="title-dot">。</span></h1>
      <div class="kj-head-badges">
        <button v-if="rank" type="button" class="kj-rank-chip" @click="showRules = true">
          <Award :size="14" /> {{ rank.title }} {{ rank.stars }}★
        </button>
        <div class="kj-level-chip" aria-label="当前阶段">
          <Trophy :size="14" />
          <span>Lv.{{ journal.summary.level.number }} {{ journal.summary.level.title }}</span>
          <small>{{ totals.cleared }}/{{ totals.stages }}</small>
        </div>
      </div>
    </header>

    <section v-if="!draft && rank" class="kj-card kj-rank-card" aria-label="段位赛进度">
      <div class="kj-rank-main">
        <div class="kj-rank-emblem">
          <Award :size="20" />
          <strong>{{ rank.title }}</strong>
          <span>{{ rank.stars }}★</span>
        </div>
        <div class="kj-rank-copy">
          <div class="kj-spread">
            <b>{{ rank.points }} 分</b>
            <small class="kj-muted">{{ rankLine(rank) }}</small>
          </div>
          <div class="kj-rank-track" role="progressbar" :aria-valuenow="rankProgress" aria-valuemin="0" aria-valuemax="100">
            <i :style="{ width: rankProgress + '%' }"></i>
          </div>
          <small class="kj-muted">{{ rank.season }} · 只升不降 · 闯关星 {{ totals.stars }}/{{ totals.max_stars }} · 再集 {{ rank.courage }}/3 餐 +1 分</small>
        </div>
      </div>
      <button type="button" class="kj-link" @click="showRules = true">段位规则 <ChevronDown :size="14" /></button>
    </section>

    <p v-if="journal.finalizing" class="kj-status-banner" role="status">正在保存这一餐，请稍候…</p>
    <div v-if="localError || journal.error" class="kj-error" role="alert">
      <p>{{ localError || journal.error }}</p>
      <div class="kj-actions" v-if="journal.conflict">
        <button :disabled="journal.finalizing" @click="attempt(() => journal.resolveConflict('reload'))">恢复服务端版本</button>
        <button @click="attempt(() => journal.resolveConflict('retry'))">保留输入重试</button>
      </div>
      <button v-else-if="journal.error" :disabled="journal.finalizing" @click="attempt(() => journal.retry())">重试保存</button>
    </div>

    <!-- Celebration Poster Card -->
    <article v-if="!draft && done && celebration" class="kj-card kj-celebrate" aria-live="polite">
      <div class="kj-confetti" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i><i></i></div>
      <div class="kj-celebrate-top">
        <span class="kj-seal kj-seal-land">{{ celebration.badge }}<small>{{ done.cooked_on }}</small></span>
        <span class="kj-muted">第 {{ String(done.number).padStart(3, '0') }} 餐</span>
      </div>
      <h2>{{ celebration.headline }}</h2>
      <p class="kj-muted">{{ celebration.subline }}</p>

      <img v-if="recordPhoto(done)" class="kj-celebrate-photo" :src="recordPhoto(done)" alt="这一餐的成品照" />
      <div class="kj-dish-tags">
        <span v-for="dish in effectiveDishes(done)" :key="dish.id" :class="['kj-dish-chip', 'is-' + dish.outcome]">
          {{ dish.snapshot.name }}
          <em>{{ dish.outcome === 'success' ? '做成了' : '还想再练' }}</em>
        </span>
      </div>
      <p v-if="done.note" class="kj-quote">{{ done.note }}</p>
      <div v-if="hasFreshAwards" class="kj-awards" aria-label="本关奖励">
        <p v-if="awards.stars" class="kj-award-stars"><Star :size="15" /> 本关 +{{ awards.stars }} 星</p>
        <p v-if="awards.rankUp"><Award :size="15" /> 段位晋升：{{ awards.rankUp }}</p>
        <p v-for="secret in awards.secrets" :key="secret.id"><BookOpen :size="15" /> 解锁秘籍：{{ secret.title }}</p>
        <p v-for="egg in awards.eggs" :key="egg.id"><Sparkles :size="15" /> 隐藏彩蛋：{{ egg.title }}</p>
        <p v-for="chapter in awards.chapters" :key="chapter.id"><Trophy :size="15" /> 获得称号「{{ chapter.badge }}」</p>
      </div>
      <div class="kj-actions">
        <button class="kj-primary" @click="emit('records')">去看下厨记录 <ArrowRight :size="15" /></button>
        <button @click="dismissDone">继续闯关</button>
      </div>
    </article>

    <!-- Idle: Blind Box + Built-in Recipe Chapters -->
    <template v-else-if="!draft">
      <section v-if="journal.drafts.length" class="kj-resume-banner">
        <strong>灶台还有未收尾的一餐</strong>
        <div class="kj-resume-list">
          <button v-for="item in journal.drafts" :key="item.id" class="kj-primary" @click="attempt(() => journal.resume(item.id))">
            <RotateCcw :size="14" /> 继续：{{ item.dishes.map(d => d.snapshot.name).join('、') }}
          </button>
        </div>
      </section>

      <!-- Today's Blind Box -->
      <section class="kj-card kj-blindbox">
        <div class="kj-spread">
          <div>
            <span class="kj-tag">今日盲盒{{ journal.quest?.blind_box?.date ? ' · ' + journal.quest.blind_box.date : '' }}</span>
            <h2 v-if="!activeBlind">不知道做什么？摇一道来闯关</h2>
            <h2 v-else>{{ activeBlind.emoji }} {{ activeBlind.name }}</h2>
          </div>
          <button class="kj-soft-btn" @click="rollBlindBox">
            <Shuffle :size="15" /> {{ activeBlind ? '换一个' : '摇一下' }}
          </button>
        </div>
        <template v-if="activeBlind">
          <p class="kj-blind-twist"><Sparkles :size="14" /> 附加小任务：{{ activeBlind.twist }}</p>
          <p class="kj-muted">主厨提示：{{ activeBlind.tip }}</p>
          <div class="kj-actions">
            <span v-if="activeBlind.completed" class="kj-tag">今天已完成 · 可再练</span>
            <button class="kj-primary" :disabled="!activeBlindStage || activeBlindStage.unlocked === false" @click="openBriefing(activeBlindStage)">
              <Flame :size="15" /> {{ activeBlind.completed ? '再练一次' : '接受挑战，现在开火' }}
            </button>
          </div>
        </template>
      </section>

      <!-- Chapters -->
      <div class="kj-chapters">
        <section v-for="chapter in questChapters" :key="chapter.id" :class="['kj-chapter', { 'is-locked': chapter.unlocked === false }]">
          <div class="kj-chapter-head">
            <div>
              <span class="kj-chapter-num">第 {{ chapter.number }} 章</span>
              <h2>{{ chapter.title }}</h2>
              <span class="kj-muted">{{ chapter.subtitle }}</span>
            </div>
            <span :class="['kj-chapter-progress', { 'is-done': chapter.completed }]">
              {{ chapter.completed ? `已获「${chapter.badge}」· ${chapter.stars}/${chapter.max_stars}★` : `${chapter.cleared_count} / ${chapter.stages.length} · ${chapter.stars}/${chapter.max_stars}★` }}
            </span>
          </div>
          <p v-if="chapter.unlocked === false" class="kj-lock-note"><Lock :size="14" /> {{ chapter.unlock_hint }}</p>

          <div class="kj-stage-grid">
            <article v-for="stage in chapter.stages" :key="stage.id" :class="['kj-card', 'kj-stage-card', 'is-' + stage.state, { 'is-locked': stage.unlocked === false }]">
              <div class="kj-stage-top">
                <img v-if="stage.cover" class="kj-stage-thumb" :src="stage.cover" :alt="stage.name" loading="lazy" />
                <span v-else class="kj-stage-emoji">{{ stage.emoji }}</span>
                <div class="kj-stage-meta">
                  <div class="kj-spread">
                    <h3>{{ stage.name }}</h3>
                    <span v-if="stage.state === 'cleared'" class="kj-seal-mini">已通关</span>
                    <span v-else-if="stage.state === 'revenge'" class="kj-revenge-tag">待复仇</span>
                  </div>
                  <small class="kj-muted">{{ stage.minutes }} 分钟 · {{ '★'.repeat(stage.difficulty) }}</small>
                  <span class="kj-stage-stars" :aria-label="`${stage.stars} 颗星`">
                    <Star v-for="(on, i) in starPips(stage.stars)" :key="i" :size="14" :class="{ 'is-on': on }" />
                  </span>
                </div>
              </div>
              <p class="kj-stage-tip">{{ stage.tip }}</p>
              <p v-if="stage.secret_unlocked" class="kj-stage-secret"><BookOpen :size="14" /> 秘籍已解锁：{{ stage.secret }}</p>
              <div class="kj-stage-foot">
                <button v-if="stage.state === 'cleared' && stage.last_session_id" class="kj-link" @click="viewStageRecord(stage)">回看记录</button>
                <span v-else class="kj-muted">{{ stage.unlocked === false ? '上一章 3 星后解锁' : stage.state === 'revenge' ? '再战一次翻盘' : '内置菜谱直开' }}</span>
                <button :class="stage.state === 'cleared' ? 'kj-soft-btn' : 'kj-primary'" :disabled="journal.finalizing || stage.unlocked === false" @click="openBriefing(stage)">
                  <Lock v-if="stage.unlocked === false" :size="14" />
                  <Flame v-else :size="14" />
                  {{ stage.unlocked === false ? '未解锁' : stage.state === 'cleared' ? '再练一次' : stage.state === 'revenge' ? '去复仇' : '开始闯关' }}
                </button>
              </div>
            </article>
          </div>
        </section>
      </div>

      <!-- Collectibles: secret recipes and hidden eggs -->
      <section class="kj-collect">
        <article class="kj-card">
          <div class="kj-spread">
            <span class="kj-tag"><BookOpen :size="14" /> 秘籍图鉴</span>
            <small class="kj-muted">{{ totals.secrets }}/{{ totals.secrets_total }}</small>
          </div>
          <div class="kj-secret-grid">
            <div v-for="secret in secrets" :key="secret.id" :class="['kj-secret', { 'is-locked': !secret.unlocked }]">
              <b>{{ secret.unlocked ? secret.title : '待解锁秘籍' }}</b>
              <p v-if="secret.unlocked">{{ secret.body }}</p>
              <small v-else><Lock :size="12" /> {{ secret.hint }}</small>
            </div>
          </div>
        </article>
        <article class="kj-card">
          <div class="kj-spread">
            <span class="kj-tag"><Sparkles :size="14" /> 彩蛋</span>
            <small class="kj-muted">{{ easterEggs.filter(egg => egg.unlocked).length }}/{{ easterEggs.length }}</small>
          </div>
          <div class="kj-egg-grid">
            <div v-for="egg in easterEggs" :key="egg.id" :class="['kj-egg', { 'is-unlocked': egg.unlocked }]">
              <b>{{ egg.unlocked ? egg.title : '???' }}</b>
              <small>{{ egg.unlocked ? egg.description : egg.hint }}</small>
            </div>
          </div>
        </article>
      </section>

      <!-- Compact Manual Quick-Log -->
      <form class="kj-card kj-quick-manual" @submit.prevent="attempt(() => journal.start({ manual_name: manual.trim() }))">
        <input id="workspace-manual" v-model="manual" maxlength="80" required placeholder="做过其他菜？输入菜名直接补记一餐" aria-label="补记一道做过的菜" />
        <button :disabled="!manual.trim() || journal.finalizing"><Plus :size="15" /> 补记</button>
      </form>
    </template>

    <!-- Active Cooking Flow: Card Stepper or List View + Process Photos + Finish -->
    <fieldset v-else class="kj-finalizing-fields kj-cook-flow" :disabled="journal.finalizing" :aria-busy="journal.finalizing">
      <header class="kj-cook-topbar">
        <div class="kj-cook-title">
          <strong>{{ activeDish?.snapshot?.name || '正在做菜' }}</strong>
          <small aria-live="polite"><Clock :size="12" /> {{ formatElapsed(elapsed) }} · {{ journal.uploading ? '照片上传中…' : journal.saving ? '保存中…' : '自动保存' }}</small>
        </div>
        <div class="kj-cook-switch" v-if="!finishing">
          <button type="button" :class="['kj-mode-btn', { 'is-active': viewMode === 'card' }]" @click="viewMode = 'card'"><Layers :size="14" /> 卡片</button>
          <button type="button" :class="['kj-mode-btn', { 'is-active': viewMode === 'list' }]" @click="viewMode = 'list'"><List :size="14" /> 全览</button>
        </div>
        <button v-if="!finishing" type="button" class="kj-primary" @click="finishing = true">出锅</button>
        <button v-else type="button" class="kj-soft-btn" @click="finishing = false">回步骤</button>
      </header>

      <!-- Multi-dish switcher -->
      <div v-if="!finishing && draft.dishes.length > 1" class="kj-chip-strip">
        <button v-for="(d, idx) in draft.dishes" :key="d.id" type="button" :class="['kj-chip-btn', { 'is-active': activeDishIdx === idx }]" @click="activeDishIdx = idx">
          {{ d.snapshot.name }}
        </button>
      </div>

      <section v-if="!finishing && activeQuestStage" class="kj-quest-banner" aria-label="本关目标">
        <div class="kj-spread">
          <span class="kj-tag">{{ activeQuestStage.emoji }} {{ activeQuestStage.chapter_title }} · {{ activeQuestStage.name }}</span>
          <span class="kj-stage-stars">
            <Star v-for="(on, i) in starPips(activeGoals.filter(g => g.done).length)" :key="i" :size="14" :class="{ 'is-on': on }" />
          </span>
        </div>
        <p class="kj-cheer">{{ cheer }}</p>
        <ul class="kj-goal-list">
          <li v-for="goal in activeGoals" :key="goal.id" :class="{ 'is-done': goal.done }">
            <Check v-if="goal.done" :size="14" /><span v-else class="kj-goal-dot"></span>
            <span><b>{{ goal.title }}</b><small>{{ goal.detail }}</small></span>
          </li>
        </ul>
        <p class="kj-muted">当前菜心得 {{ noteLength(activeDish) }}/8 字 · 本关最高 {{ activeQuestStage.stars }}★</p>
      </section>

      <!-- Step-by-step Card Mode -->
      <template v-if="!finishing && viewMode === 'card' && activeDish">
        <aside v-if="priorNotes[activeDish.id]" class="kj-prior-note">
          <small>上次给自己的提醒 ({{ priorNotes[activeDish.id].record.cooked_on }})</small>
          <p>{{ priorNotes[activeDish.id].dish.note || '上次没有写心得，这次可以顺手记一句。' }}</p>
        </aside>

        <div class="kj-card-meta-bar">
          <span v-if="activeSteps.length" class="kj-step-counter">第 <b>{{ activeStepIdx + 1 }}</b> / {{ activeSteps.length }} 步</span>
          <span v-else class="kj-step-counter">自由发挥模式</span>
          <button v-if="activeDish.snapshot.ingredients?.length" type="button" class="kj-soft-btn" @click="showIngredients = !showIngredients">
            <UtensilsCrossed :size="14" /> {{ showIngredients ? '收起备料' : `备料 (${activeDish.snapshot.ingredients.length})` }}
          </button>
        </div>

        <div v-if="showIngredients && activeDish.snapshot.ingredients?.length" class="kj-card kj-ing-drawer">
          <ul class="kj-ingredients">
            <li v-for="ing in activeDish.snapshot.ingredients" :key="ing.id">
              <span>{{ ing.name }}</span><strong>{{ ing.amount || '适量' }}</strong>
            </li>
          </ul>
        </div>

        <div v-if="activeSteps.length" class="kj-progress-dots" aria-hidden="true">
          <span v-for="(s, i) in activeSteps" :key="s.id" :class="{ 'is-current': i === activeStepIdx, 'is-done': activeDish.completed_steps.includes(s.id) }" @click="activeStepIdx = i"></span>
        </div>

        <article class="kj-card kj-step-stage">
          <template v-if="currentStep">
            <p class="kj-step-text">{{ currentStep.text }}</p>
            <div v-if="currentStep.images?.length" class="kj-stage-imgs">
              <img v-for="url in currentStep.images" :key="url" :src="url" :alt="`第${activeStepIdx + 1}步参考图`" />
            </div>
          </template>
          <p v-else class="kj-step-text">这道菜没有预设步骤，按自己的节奏来，做完直接点「出锅」拍成品照吧。</p>

          <!-- Process Photo Capture -->
          <div class="kj-process-cam">
            <label class="kj-cam-btn">
              <Camera :size="16" /> 拍下这一步（过程记录）
              <input type="file" accept="image/jpeg,image/png,image/webp" capture="environment" multiple :disabled="!!journal.uploading || activeDish.photos.length >= 12" @change="upload($event, activeDish)" />
            </label>
            <div v-if="activeDish.photos.length" class="kj-mini-strip">
              <img v-for="(url, i) in activeDish.photos" :key="url" :src="url" :alt="`过程照${i + 1}`" />
            </div>
          </div>
        </article>

        <div class="kj-stepper-bar">
          <button type="button" :disabled="activeStepIdx === 0" @click="prevStep"><ChevronLeft :size="18" /> 上一步</button>
          <button type="button" class="kj-primary" @click="nextStep">
            {{ activeStepIdx < activeSteps.length - 1 ? '下一步' : '出锅！拍成品照' }} <ChevronRight :size="18" />
          </button>
        </div>
      </template>

      <!-- List Overview Mode -->
      <template v-else-if="!finishing && viewMode === 'list'">
        <div class="kj-cook-main">
          <article v-for="dish in draft.dishes" :key="dish.id" class="kj-card">
            <div class="kj-spread">
              <h2>{{ dish.snapshot.name }}</h2>
              <label class="kj-cam-btn">
                <Camera :size="15" /> 拍过程
                <input type="file" accept="image/jpeg,image/png,image/webp" capture="environment" multiple :disabled="!!journal.uploading || dish.photos.length >= 12" @change="upload($event, dish)" />
              </label>
            </div>
            <aside v-if="priorNotes[dish.id]" class="kj-prior-note">
              <small>上次提醒 ({{ priorNotes[dish.id].record.cooked_on }})</small>
              <p>{{ priorNotes[dish.id].dish.note || '上次未写心得' }}</p>
            </aside>
            <details v-if="dish.snapshot.ingredients?.length" open class="kj-block-details">
              <summary>备料 ({{ dish.snapshot.ingredients.length }})</summary>
              <ul class="kj-ingredients">
                <li v-for="ing in dish.snapshot.ingredients" :key="ing.id"><span>{{ ing.name }}</span><strong>{{ ing.amount || '适量' }}</strong></li>
              </ul>
            </details>
            <ol v-if="dish.snapshot.steps?.length" class="kj-steps">
              <li v-for="(step, idx) in dish.snapshot.steps" :key="step.id" :class="{ 'is-done': dish.completed_steps.includes(step.id) }">
                <label>
                  <input type="checkbox" :checked="dish.completed_steps.includes(step.id)" @change="toggleStep(dish, step.id)" />
                  <div><b>{{ String(idx + 1).padStart(2, '0') }}</b><span>{{ step.text }}</span></div>
                </label>
              </li>
            </ol>
            <div v-if="dish.photos.length" class="kj-mini-strip" style="margin-top:12px">
              <img v-for="(url, i) in dish.photos" :key="url" :src="url" :alt="`过程照${i + 1}`" />
            </div>
          </article>
          <button type="button" class="kj-primary kj-wide" @click="finishing = true">出锅！拍张成品照 <ArrowRight :size="16" /></button>
        </div>
      </template>

      <!-- Finish & Final Dish Photo -->
      <div v-else class="kj-finish">
        <div class="kj-card kj-session-head">
          <div class="kj-form-row">
            <label>日期<input type="date" :max="today" :value="draft.cooked_on" @change="patch({ cooked_on: $event.target.value })" /></label>
            <label>这一餐的名字（可选）<input :value="draft.title" maxlength="80" placeholder="例如：周五晚上的番茄炒蛋" @input="patch({ title: $event.target.value })" /></label>
          </div>
        </div>

        <article v-for="dish in draft.dishes" :key="dish.id" class="kj-card">
          <h2>{{ dish.snapshot.name }}</h2>
          <div class="kj-finish-goals">
            <span v-for="goal in stageGoals(dish)" :key="goal.id" :class="{ 'is-done': goal.done }">
              <Star :size="13" /> {{ goal.title }}
            </span>
          </div>

          <!-- Prominent Final Photo Upload Box -->
          <label class="kj-photo-drop">
            <Camera :size="22" />
            <div>
              <strong>拍一张成品照（或选相册）</strong>
              <small>过程照与成品照都会留进你的下厨记录，最多 12 张</small>
            </div>
            <input type="file" accept="image/jpeg,image/png,image/webp" capture="environment" multiple :disabled="!!journal.uploading || dish.photos.length >= 12" @change="upload($event, dish)" />
          </label>

          <div v-if="dish.photos.length" class="kj-photo-strip">
            <figure v-for="(url, index) in dish.photos" :key="url">
              <img :src="url" :alt="`${dish.snapshot.name}照片${index + 1}`" />
              <button type="button" @click="dishPatch(dish, { photos: dish.photos.filter((_, i) => i !== index) })">移除</button>
            </figure>
          </div>

          <fieldset class="kj-outcomes">
            <legend>这道菜这次做得怎么样？</legend>
            <div class="kj-outcome-pills">
              <label v-for="option in [{ value: 'success', label: '做成了' }, { value: 'practice', label: '还想再练' }, { value: 'skipped', label: '这次没做' }]" :key="option.value" :class="['kj-pill', { 'is-active': dish.outcome === option.value }]">
                <input type="radio" :name="dish.id" :value="option.value" :checked="dish.outcome === option.value" @change="dishPatch(dish, { outcome: option.value })" />
                <span>{{ option.label }}</span>
              </label>
            </div>
          </fieldset>

          <label>留给下次的自己（可选）
            <textarea maxlength="1000" :value="dish.note" placeholder="火候、咸淡或一点小发现…" @input="dishPatch(dish, { note: $event.target.value })" />
          </label>
          <small class="kj-note-count">{{ noteLength(dish) }}/8 字解锁「留下色香味」</small>
        </article>

        <article class="kj-card kj-finish-foot">
          <label>关于这一餐（可选）
            <textarea :value="draft.note" maxlength="1000" placeholder="今天和谁一起吃、心情如何…" @input="patch({ note: $event.target.value })" />
          </label>
          <div class="kj-actions">
            <button type="button" @click="finishing = false">回步骤</button>
            <button type="button" class="kj-primary" :disabled="journal.saving || !!journal.uploading || draft.dishes.some(d => d.outcome === 'pending') || !effectiveDishes(draft).length" @click="complete">
              <Check :size="17" /> {{ journal.uploading ? '照片上传中…' : journal.saving ? '保存中…' : '完成并留下这一餐' }}
            </button>
          </div>
        </article>
      </div>
    </fieldset>

    <!-- Stage briefing: story, goals, secret and the final go -->
    <div v-if="briefing" class="kj-modal" @click.self="briefing = null">
      <article class="kj-card kj-briefing" role="dialog" aria-modal="true" aria-labelledby="kj-brief-title">
        <button type="button" class="kj-icon-btn kj-modal-close" aria-label="关闭" @click="briefing = null"><X :size="18" /></button>
        <span class="kj-tag">{{ briefing.emoji }} 第 {{ briefing.chapter_number }} 章 · {{ briefing.chapter_title }}</span>
        <h2 id="kj-brief-title">{{ briefing.name }}</h2>
        <p class="kj-brief-story">{{ briefing.story || briefing.tip }}</p>
        <div class="kj-brief-facts">
          <span><Clock :size="14" /> 约 {{ briefing.minutes }} 分钟</span>
          <span><Star :size="14" /> 难度 {{ '★'.repeat(briefing.difficulty || 1) }}</span>
          <span><Trophy :size="14" /> 最高 {{ briefing.stars || 0 }}/3 星</span>
        </div>
        <h3>本关目标</h3>
        <ul class="kj-goal-list">
          <li v-for="rule in QUEST_STAR_RULES" :key="rule.id">
            <span class="kj-goal-dot"></span>
            <span><b>{{ rule.title }}</b><small>{{ rule.detail }}</small></span>
          </li>
        </ul>
        <p v-if="briefing.secret_unlocked" class="kj-secret-hint"><BookOpen :size="14" /> 已解锁秘籍：{{ briefing.secret }}</p>
        <p v-else class="kj-muted">做到 3 星，会解锁这道菜的独门秘籍。</p>
        <div class="kj-actions">
          <button type="button" @click="briefing = null">再想想</button>
          <button type="button" class="kj-primary" :disabled="journal.finalizing" @click="startBriefing"><Flame :size="15" /> 开火，开始闯关</button>
        </div>
      </article>
    </div>

    <!-- Rank rules -->
    <div v-if="showRules" class="kj-modal" @click.self="showRules = false">
      <article class="kj-card kj-rules" role="dialog" aria-modal="true" aria-labelledby="kj-rules-title">
        <button type="button" class="kj-icon-btn kj-modal-close" aria-label="关闭" @click="showRules = false"><X :size="18" /></button>
        <span class="kj-tag"><Award :size="14" /> 段位赛</span>
        <h2 id="kj-rules-title">像打排位一样，慢慢变强</h2>
        <p class="kj-muted">{{ RANK_RULE }}</p>
        <div class="kj-tier-list">
          <div v-for="tier in rankTiers(rank)" :key="tier.id" :class="['kj-tier', { 'is-current': rank?.tier === tier.id }]">
            <b>{{ tier.title }}</b>
            <small>{{ tier.min }} 分起</small>
          </div>
        </div>
        <h3>星星怎么拿</h3>
        <ul class="kj-goal-list">
          <li v-for="rule in QUEST_STAR_RULES" :key="rule.id">
            <span class="kj-goal-dot"></span>
            <span><b>{{ rule.title }}</b><small>{{ rule.detail }}</small></span>
          </li>
        </ul>
        <p class="kj-muted">每章 3 关，每关 3 星。得到 3 星会解锁秘籍；章内拿满 3 星，下一章才会亮起。</p>
      </article>
    </div>

    <CookingRecordDetail :journal="journal" :record="detail" @close="detail = null" @cook="detail = null" />
  </section>
</template>

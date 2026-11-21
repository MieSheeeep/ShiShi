<script setup>
import { computed, ref, watch, onBeforeUnmount } from 'vue'
import { Camera, Check, Flame, ArrowRight } from 'lucide-vue-next'
import { effectiveDishes, recordPhoto, previousAttempt } from '../cookingJournal.js'
import '../kitchen-journal.css'
const props=defineProps({journal:{type:Object,required:true}})
const emit=defineEmits(['browse','recorded','records'])
const manual=ref(''),finishing=ref(false)
const draft=computed(()=>props.journal.draft)
const done=computed(()=>props.journal.lastCompleted)
const priorNotes=ref({})
let historyGeneration=0
watch(()=>[props.journal.accountId,draft.value?.id],async()=>{
  const generation=++historyGeneration,account=props.journal.accountId,session=draft.value
  priorNotes.value={}
  if(!session)return
  await Promise.all(session.dishes.map(async dish=>{
    try{
      const records=await props.journal.history(dish.dish_key)
      if(generation!==historyGeneration||account!==props.journal.accountId||session.id!==draft.value?.id)return
      const prior=previousAttempt(records,dish.dish_key,session.id)
      if(prior)priorNotes.value={...priorNotes.value,[dish.id]:prior}
    }catch{/* Optional history never prevents cooking; no invented note is shown. */}
  }))
},{immediate:true})
onBeforeUnmount(()=>{historyGeneration++})
const today=new Date().toLocaleDateString('sv-SE',{timeZone:'Asia/Shanghai'})
const attempt=async action=>{try{await action()}catch{/* journal exposes the real error */}}
function patch(value){return attempt(()=>props.journal.patch(value))}
function dishPatch(dish,value){return patch({dishes:[{id:dish.id,...value}]})}
function toggle(dish,id){const steps=new Set(dish.completed_steps);steps.has(id)?steps.delete(id):steps.add(id);dishPatch(dish,{completed_steps:[...steps]})}
async function upload(event,dish){const files=[...event.target.files];event.target.value='';for(const file of files){if(dish.photos.length>=12)break;await attempt(async()=>{const url=await props.journal.uploadPhoto(file);if(url&&draft.value?.dishes.some(d=>d.id===dish.id))await dishPatch(dish,{photos:[...dish.photos,url]})})}}
async function complete(){await attempt(async()=>{const record=await props.journal.complete();if(record){finishing.value=false;emit('recorded',record)}})}
</script>

<template>
  <section class="kj journal-workspace">
    <header class="kj-heading"><div><span class="kj-eyebrow">THE EVERYDAY KITCHEN · 下厨现场</span><h1>给这一餐，一点时间。</h1><p>做成也好，还想再练也好，都是你的烟火日常。</p></div><Flame class="kj-heading-icon" :size="38" /></header>
    <p v-if="journal.finalizing" class="kj-finalizing-status" role="status">正在确认保存这一餐，已暂时锁定编辑，请稍候。</p>
    <div v-if="journal.error" class="kj-error" role="alert"><p>{{ journal.error }}</p><div class="kj-actions" v-if="journal.conflict"><button :disabled="journal.finalizing" @click="attempt(()=>journal.resolveConflict('reload'))">放弃本次输入，恢复服务端版本</button><button @click="attempt(()=>journal.resolveConflict('retry'))">保留我的输入并重试</button></div><button v-else :disabled="journal.finalizing" @click="attempt(()=>journal.retry())">重试保存</button></div>
    <article v-if="!draft && done" class="kj-success kj-paper" aria-live="polite">
      <span class="kj-eyebrow">{{ done.cooked_on }} · 厨房足迹 {{ String(done.number).padStart(3,'0') }}</span>
      <h2>这一餐，留下来了。</h2><p>每一次认真尝试，都值得留在这里。</p>
      <img v-if="recordPhoto(done)" class="kj-developed" :src="recordPhoto(done)" alt="这一餐的成品照片" />
      <div v-else class="kj-word-art"><span>{{ effectiveDishes(done).map(d=>d.snapshot.name).join(' · ') }}</span><p>{{ done.note || '烟火有迹，来日可期。' }}</p></div>
      <span class="kj-stamp kj-stamp-land">已留印<br><small>{{ done.cooked_on }}</small></span>
      <div class="kj-actions"><button class="kj-primary" @click="emit('records')">去看厨房足迹 <ArrowRight :size="16" /></button><button @click="emit('browse')">再选一道菜</button></div>
    </article>
    <div v-else-if="!draft" class="kj-empty kj-paper"><span class="kj-empty-mark">灶</span><h2>第一餐，从这里开始</h2><p>选一道想做的菜，按自己的节奏来。已经做过的，也可以补记。</p><button class="kj-primary" @click="emit('browse')">去菜谱库选菜</button><form class="kj-manual" @submit.prevent="attempt(()=>journal.start({manual_name:manual.trim()}))"><label for="workspace-manual">补记一道做过的菜</label><div class="kj-actions"><input id="workspace-manual" v-model="manual" maxlength="80" required placeholder="菜名，例如：一碗热汤" /><button :disabled="!manual.trim()">开始补记</button></div></form><div v-if="journal.drafts.length" class="kj-draft-list"><h3>还没收尾的烟火</h3><button v-for="item in journal.drafts" :key="item.id" @click="attempt(()=>journal.resume(item.id))">{{ item.cooked_on }} · {{ item.dishes.map(d=>d.snapshot.name).join('、') }} →</button></div></div>
    <fieldset v-else class="kj-finalizing-fields" :disabled="journal.finalizing" :aria-busy="journal.finalizing">
      <div class="kj-session-head kj-paper"><span class="kj-eyebrow">这一餐 · No. {{ String(draft.number).padStart(3,'0') }}</span><div class="kj-form-row"><label>日期<input type="date" :max="today" :value="draft.cooked_on" @change="patch({cooked_on:$event.target.value})" /></label><label>给这一餐起个名字（可选）<input :value="draft.title" maxlength="80" placeholder="这一天的烟火" @input="patch({title:$event.target.value})" /></label></div><p class="kj-muted" aria-live="polite">{{ journal.finalizing ? '正在确认这一餐…' : journal.uploading ? '照片上传中…' : journal.saving ? '正在保存…' : journal.error ? '输入已保留，等待重试' : '草稿会随操作保存' }}</p></div>
      <div class="kj-tabs"><button :aria-pressed="!finishing" @click="finishing=false">01 跟着做</button><button :aria-pressed="finishing" @click="finishing=true">02 收尾留念</button></div>
      <div v-if="!finishing" class="kj-cook-grid"><article v-for="dish in draft.dishes" :key="dish.id" class="kj-paper kj-recipe"><span class="kj-eyebrow">{{ dish.snapshot.emoji }} 这一道</span><h2>{{ dish.snapshot.name }}</h2><aside v-if="priorNotes[dish.id]" class="kj-prior-note"><span class="kj-eyebrow">上一次的自己 · {{ priorNotes[dish.id].record.cooked_on }}</span><p v-if="priorNotes[dish.id].dish.note" class="kj-own-note">{{ priorNotes[dish.id].dish.note }}</p><p v-else class="kj-muted">上次没有留下心得。这次，慢慢试。</p></aside><details open><summary>准备食材</summary><ul class="kj-ingredients"><li v-for="ingredient in dish.snapshot.ingredients" :key="ingredient.id"><span>{{ ingredient.name }}</span><span>{{ ingredient.amount }}</span></li></ul></details><ol class="kj-steps"><li v-for="(step,index) in dish.snapshot.steps" :key="step.id"><label><input type="checkbox" :checked="dish.completed_steps.includes(step.id)" @change="toggle(dish,step.id)" /><span><b>{{ String(index+1).padStart(2,'0') }}</b>{{ step.text }}</span></label><div v-if="step.images?.length" class="kj-step-images"><img v-for="url in step.images" :key="url" :src="url" :alt="`第${index+1}步参考配图`" loading="lazy" /></div></li></ol><p v-if="!dish.snapshot.steps?.length" class="kj-muted">这道菜没有步骤。按自己的方式做，直接到收尾留下结果。</p><details v-if="dish.snapshot.notes"><summary>食谱提示</summary><p>{{ dish.snapshot.notes }}</p></details></article><aside class="kj-paper kj-terms"><h3>灶边小注</h3><details><summary>“焯水”是什么？</summary><p>食材在沸水中短暂加热后捞出，具体时长以食谱为准。</p></details><details><summary>“收汁”是什么？</summary><p>继续加热让部分水分蒸发，汤汁逐渐浓稠；留意翻动，避免烧干。</p></details><button class="kj-primary" @click="finishing=true">做好了，去收尾 <ArrowRight :size="16" /></button><p class="kj-muted">步骤没有全部勾完，也能记录这一餐。</p></aside></div>
      <div v-else class="kj-finish"><article v-for="dish in draft.dishes" :key="dish.id" class="kj-paper"><h2>{{ dish.snapshot.name }}</h2><fieldset class="kj-outcomes"><legend>这道菜，做得怎么样？</legend><label v-for="option in [{value:'success',label:'做成了'},{value:'practice',label:'还想再练'},{value:'skipped',label:'这次没做'}]" :key="option.value"><input type="radio" :name="dish.id" :value="option.value" :checked="dish.outcome===option.value" @change="dishPatch(dish,{outcome:option.value})" />{{ option.label }}</label></fieldset><label>留给下次的自己（可选）<textarea maxlength="1000" :value="dish.note" placeholder="火候、味道，或一点小发现…" @input="dishPatch(dish,{note:$event.target.value})" /></label><div class="kj-photo-strip"><figure v-for="(url,index) in dish.photos" :key="url"><img :src="url" :alt="`${dish.snapshot.name}成品${index+1}`" /><button :aria-label="`移除成品照片${index+1}`" @click="dishPatch(dish,{photos:dish.photos.filter((_,i)=>i!==index)})">移除</button></figure></div><label class="kj-upload"><Camera :size="18" /> 留一张我的成品照（可选，最多12张）<input type="file" accept="image/jpeg,image/png,image/webp" multiple :disabled="!!journal.uploading||dish.photos.length>=12" @change="upload($event,dish)" /></label></article><article class="kj-paper"><label>关于这一餐（可选）<textarea :value="draft.note" maxlength="1000" placeholder="想记什么，就写什么。" @input="patch({note:$event.target.value})" /></label><p class="kj-muted">至少做成或练习了一道菜，即可留下一餐。照片和心得都可以跳过。</p><button class="kj-primary" :disabled="journal.saving||!!journal.uploading||draft.dishes.some(d=>d.outcome==='pending')||!effectiveDishes(draft).length" @click="complete"><Check :size="18" /> {{ journal.uploading ? '等待照片上传' : journal.saving ? '正在保存这一餐…' : '留下这一餐' }}</button></article></div>
    </fieldset>
  </section>
</template>

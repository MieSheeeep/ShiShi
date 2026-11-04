<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { X, Plus, Check, Trash2, ImagePlus, RotateCcw } from 'lucide-vue-next'
import OrderButtons from './OrderButtons.vue'
import TagPicker from './TagPicker.vue'
import { moveItem, attachImage, newStep, newIngredient } from '../recipeEditing'
const props=defineProps({recipe:Object,catalog:Object,busy:Boolean,error:String})
const emit=defineEmits(['cancel','save','catalog-change','manage-tags'])
const copy=value=>JSON.parse(JSON.stringify(value))
const model=ref(copy(props.recipe)),initial=JSON.stringify(props.recipe),picking=ref(null)
const dirty=computed(()=>JSON.stringify(model.value)!==initial)
const snapshot=computed(()=>model.value.original_snapshot?.recipe)
const availableImages=computed(()=>[...new Set([
  ...(model.value.source.original_images||[]),...(model.value.images||[]),
  ...model.value.steps.flatMap(s=>s.images||[]),...(snapshot.value?.images||[]),
  ...(snapshot.value?.steps||[]).flatMap(s=>s.images||[])
])])
function close(){if(!props.busy&&(!dirty.value||confirm('还有未保存的修改，确定放弃吗？')))emit('cancel')}
function reset(){if(confirm('恢复到本次打开编辑器时的内容？'))model.value=JSON.parse(initial)}
function removeStep(index){if(model.value.steps.length>1)model.value.steps.splice(index,1)}
function toggleImage(step,url){const i=step.images.indexOf(url);if(i<0)attachImage(step,url);else step.images.splice(i,1)}
function guard(event){if(dirty.value){event.preventDefault();event.returnValue=''}}
onMounted(()=>window.addEventListener('beforeunload',guard))
onBeforeUnmount(()=>window.removeEventListener('beforeunload',guard))
</script>
<template>
<div class="overlay" @click.self="close"><section class="modal recipe-editor-v2">
  <button class="close" @click="close" :disabled="busy" aria-label="关闭食谱编辑器"><X/></button>
  <div class="eyebrow">MAKE IT YOUR OWN</div><h2>{{model.id?'编辑我的食谱':'核对并保存食谱'}}</h2>
  <p class="muted">顺序不对就调整。步骤移动时，配图会一起移动；保存前所有修改都可撤回。</p>
  <div v-if="model.import_warnings?.length" class="alert"><div><p v-for="warning in model.import_warnings">{{warning}}</p></div></div>
  <details v-if="model.source.original_text||snapshot" class="source-text"><summary>{{model.original_snapshot?.kind==='legacy_saved'?'查看迁移时保留的原始记录':'对照导入原文与原始记录'}}</summary><p v-if="model.source.original_text" class="original-body">{{model.source.original_text}}</p><template v-else-if="snapshot"><strong>{{snapshot.name}}</strong><p>{{snapshot.ingredients?.map(i=>i.name+' '+i.amount).join('；')}}</p><p v-for="(step,index) in snapshot.steps" :key="step.id">{{index+1}}. {{step.text}}</p></template><p class="muted">这里只用于对照，编辑不会覆盖这份记录。</p></details>
  <form @submit.prevent="emit('save',copy(model))">
    <div class="form-row"><label class="grow">菜名<input v-model="model.name" required maxlength="200"/></label><label class="emoji-field">图标<input v-model="model.emoji" maxlength="8"/></label></div>
    <div class="form-row"><label>耗时（分钟）<input v-model="model.minutes" placeholder="未注明"/></label><label>份数<input v-model="model.servings" placeholder="未注明"/></label></div>
    <TagPicker v-model="model.tags" :catalog="catalog" @changed="emit('catalog-change')" @manage="emit('manage-tags')"/>
    <details class="source-text"><summary>来源信息</summary><label>作者<input v-model="model.source.author"/></label><label>来源链接<input v-model="model.source.url" placeholder="手动录入可留空"/></label></details>
    <div class="edit-section-heading"><h3>食材与用量</h3><span class="muted">上下移动，调整备料顺序</span></div>
    <div v-for="(item,index) in model.ingredients" :key="item.id" class="ingredient-row-v2">
      <OrderButtons :index="index" :total="model.ingredients.length" :label="'食材'+(index+1)" @move="moveItem(model.ingredients,index,$event)"/>
      <div class="ingredient-fields"><input v-model="item.name" required placeholder="食材" :aria-label="'食材'+(index+1)+'名称'"/><input v-model="item.amount" placeholder="未注明" :aria-label="'食材'+(index+1)+'用量'"/><select v-model="item.kind" :aria-label="'食材'+(index+1)+'类别'"><option>食材</option><option>调料</option></select></div>
      <button type="button" class="icon-button danger" :aria-label="'删除食材'+(index+1)" :disabled="model.ingredients.length===1" @click="model.ingredients.splice(index,1)"><Trash2 :size="15"/></button>
    </div>
    <button class="text-button" type="button" @click="model.ingredients.push(newIngredient())"><Plus :size="15"/>添加食材</button>
    <div class="edit-section-heading"><h3>制作步骤</h3><span class="muted">可以插入、删除、排序和重新配图</span></div>
    <article v-for="(step,index) in model.steps" :key="step.id" class="editable-step">
      <div class="editable-step-heading"><strong>步骤 {{String(index+1).padStart(2,'0')}}</strong><OrderButtons :index="index" :total="model.steps.length" :label="'步骤'+(index+1)" @move="moveItem(model.steps,index,$event)"/><button type="button" class="icon-button danger" :disabled="model.steps.length===1" :aria-label="'删除步骤'+(index+1)" @click="removeStep(index)"><Trash2 :size="15"/></button></div>
      <textarea v-model="step.text" required placeholder="写下这一步的做法" :aria-label="'步骤'+(index+1)+'内容'"/>
      <div v-if="step.images.length" class="editor-picture-grid"><div v-for="(url,pictureIndex) in step.images" :key="url" class="editable-picture"><a :href="url" target="_blank" rel="noopener noreferrer"><img :src="url" :alt="'步骤'+(index+1)+'配图'+(pictureIndex+1)" loading="lazy"/></a><div class="picture-actions"><OrderButtons :index="pictureIndex" :total="step.images.length" :label="'步骤'+(index+1)+'配图'+(pictureIndex+1)" @move="moveItem(step.images,pictureIndex,$event)"/><button class="icon-button" type="button" :aria-label="'移除步骤'+(index+1)+'配图'+(pictureIndex+1)" @click="step.images.splice(pictureIndex,1)"><X :size="14"/></button></div></div></div>
      <div class="step-actions"><button type="button" class="text-button" @click="picking=picking===step.id?null:step.id"><ImagePlus :size="15"/>{{picking===step.id?'收起图片选择':'选择 / 调整配图'}}</button><button type="button" class="text-button" @click="model.steps.splice(index+1,0,newStep())"><Plus :size="15"/>在下方插入步骤</button></div>
      <div v-if="picking===step.id" class="image-selector"><p class="muted">从现有原图选择，可为一个步骤关联多张图片。再次点击可取消。</p><div class="image-grid"><button v-for="(url,pictureIndex) in availableImages" :key="url" type="button" :class="{picked:step.images.includes(url)}" :aria-label="'将原图'+(pictureIndex+1)+'关联步骤'+(index+1)" :aria-pressed="step.images.includes(url)" @click="toggleImage(step,url)"><img :src="url" :alt="'原图'+(pictureIndex+1)" loading="lazy"/><Check v-if="step.images.includes(url)" :size="20"/></button></div><p v-if="!availableImages.length" class="muted">这份食谱还没有可关联的图片。</p></div>
    </article>
    <button class="text-button" type="button" @click="model.steps.push(newStep())"><Plus :size="15"/>在末尾添加步骤</button>
    <section v-if="availableImages.length" class="original-gallery"><h3>食谱图集 <span>可排序或移除展示，原图仍保留用于对照</span></h3><div class="editor-picture-grid"><div v-for="(url,index) in model.images" :key="url" class="editable-picture"><img :src="url" :alt="'图集图片'+(index+1)" loading="lazy"/><div class="picture-actions"><OrderButtons :index="index" :total="model.images.length" :label="'图集图片'+(index+1)" @move="moveItem(model.images,index,$event)"/><button type="button" class="icon-button" :aria-label="'移除图集图片'+(index+1)" @click="model.images.splice(index,1)"><X :size="14"/></button></div></div></div><details class="source-text"><summary>从原图补回图集</summary><div class="image-grid"><button v-for="(url,index) in availableImages" :key="url" type="button" :disabled="model.images.includes(url)" :aria-label="'将原图'+(index+1)+'加入图集'" @click="model.images.push(url)"><img :src="url" :alt="'可恢复原图'+(index+1)" loading="lazy"/></button></div></details></section>
    <label>我的备注<textarea v-model="model.notes" placeholder="口味调整、实践心得…"/></label>
    <p v-if="error" class="alert" role="alert">{{error}}</p>
    <div class="editor-footer"><button type="button" class="secondary" :disabled="busy||!dirty" @click="reset"><RotateCcw :size="15"/>撤回本次修改</button><button class="primary" :disabled="busy">{{busy?'正在保存…':'保存食谱'}}<Check :size="17"/></button></div>
  </form>
</section></div>
</template>

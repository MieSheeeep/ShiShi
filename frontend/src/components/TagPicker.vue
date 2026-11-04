<script setup>
import { ref, computed, watch } from 'vue'
import { Plus, X } from 'lucide-vue-next'
import { api, tagKey } from '../recipeEditing'
const props=defineProps({modelValue:Array,catalog:Object})
const emit=defineEmits(['update:modelValue','changed','manage'])
const groupId=ref(''), name=ref(''), localError=ref(''), adding=ref(false)
const selected=computed(()=>props.modelValue.map(t=>props.catalog.tags.find(k=>t.id?k.id===t.id:k.name===t.name&&k.group===(t.group||'我的分类'))||t))
watch(()=>props.catalog.tags,rows=>{const next=props.modelValue.filter(t=>!t.id||rows.some(row=>row.id===t.id));if(next.length!==props.modelValue.length)emit('update:modelValue',next)})
function toggle(tag){const key=tagKey(tag);emit('update:modelValue',selected.value.some(t=>tagKey(t)===key)?selected.value.filter(t=>tagKey(t)!==key):[...selected.value,tag])}
async function add(){
  if(!name.value.trim())return
  adding.value=true;localError.value=''
  try{const tag=await api('/tags','POST',{group_id:groupId.value||props.catalog.groups[0]?.id,name:name.value.trim()});if(!selected.value.some(t=>t.id===tag.id))emit('update:modelValue',[...selected.value,tag]);name.value='';emit('changed')}
  catch(e){localError.value=e.message}finally{adding.value=false}
}
</script>
<template><section class="tag-picker"><div class="edit-section-heading"><h3>我的标签</h3><button type="button" class="text-button" @click="emit('manage')">管理分组与标签</button></div><div class="selected-tags"><span v-for="tag in selected" :key="tagKey(tag)" class="selected-tag">{{tag.group}} · {{tag.name}}<button type="button" :aria-label="'移除标签'+tag.name" @click="toggle(tag)"><X :size="13"/></button></span><p v-if="!selected.length" class="muted">选择或新建标签，例如“厨具 · 空气炸锅”“口味 · 清淡”。</p></div><div v-for="group in catalog.groups" :key="group.id" class="tag-choice-group"><strong>{{group.name}}</strong><div class="tag-options"><button v-for="tag in catalog.tags.filter(t=>t.group_id===group.id)" type="button" :class="{chosen:selected.some(t=>t.id===tag.id)}" @click="toggle(tag)">{{tag.name}}</button><span v-if="!catalog.tags.some(t=>t.group_id===group.id)" class="muted">还没有标签</span></div></div><div class="new-tag-row"><select v-model="groupId" aria-label="新标签分组"><option value="">{{catalog.groups[0]?.name||'选择分组'}}</option><option v-for="group in catalog.groups" :value="group.id">{{group.name}}</option></select><input v-model="name" maxlength="80" aria-label="新标签名称" placeholder="输入自己的标签" @keydown.enter.prevent="add"/><button class="secondary" type="button" :disabled="adding||!name.trim()" @click="add"><Plus :size="15"/>添加</button></div><p v-if="localError" class="alert">{{localError}}</p></section></template>

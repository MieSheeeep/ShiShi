<script setup>
import { ref, watch } from 'vue'
import { Plus, ArrowRight, X } from 'lucide-vue-next'
const props=defineProps({recipes:Array,busy:Boolean,hasList:Boolean})
const emit=defineEmits(['remove','browse','match','generate','detail','shopping'])
const replacing=ref(false)
watch(()=>props.recipes,()=>{replacing.value=false})
function generate(){if(props.hasList)replacing.value=true;else emit('generate')}
</script>
<template>
<section class="menu-review">
  <div class="page-heading"><div><div class="eyebrow">PLAN BEFORE YOU SHOP</div><h1>本次菜单<span class="title-dot">。</span></h1><p>先确认要做的菜，再整理需要买的材料。</p></div><button class="secondary" @click="emit('browse')"><Plus :size="15"/>继续选菜</button></div>
  <div class="meal-steps"><span>1 选菜</span><strong>2 确认菜单</strong><span>3 核对采购</span></div>
  <template v-if="recipes.length">
    <div class="menu-heading"><h2>这次准备做 {{recipes.length}} 道菜</h2><span class="muted">生成清单前，可以随时调整</span></div>
    <article v-for="recipe in recipes" :key="recipe.id" class="menu-recipe"><button class="menu-recipe-info" @click="emit('detail',recipe)"><img v-if="recipe.cover" :src="recipe.cover" :alt="recipe.name"/><span v-else class="menu-emoji">{{recipe.emoji||'🍲'}}</span><span><strong>{{recipe.name}}</strong><small>{{recipe.ingredients.length}} 项材料<span v-if="recipe.minutes"> · {{recipe.minutes}} 分钟</span></small></span></button><button class="text-button" :disabled="busy" :aria-label="'移出菜单'+recipe.name" @click="emit('remove',recipe.id)"><X :size="14"/>移出菜单</button></article>
    <section class="menu-next"><h2>接下来，核对要买的东西</h2><p>系统会合并这些菜的重复用料。系统会按在库数量核对采购差额；无法比较的用量需要你继续核对。</p><button v-if="!replacing" class="primary" :disabled="busy" @click="generate">{{busy?'正在生成…':'确认菜单，生成采购清单'}}<ArrowRight :size="16"/></button><div v-else class="menu-replace-confirm" role="alert"><p>生成新清单会替换当前采购清单，包括已修改的用量和购买进度。</p><button class="primary" :disabled="busy" @click="emit('generate')">{{busy?'正在生成…':'确认替换并生成'}}</button><button class="secondary" :disabled="busy" @click="replacing=false">取消</button></div></section>
  </template>
  <div v-else class="empty-panel"><h2>先选几道想做的菜</h2><p>在食谱库或库存找菜结果中，点击“选入菜单”。<br/>选好后回到这里确认，再生成采购清单。</p><div class="menu-empty-actions"><button class="primary" @click="emit('browse')">去食谱库选菜</button><button class="secondary" @click="emit('match')">用库存找菜</button><button v-if="hasList" class="text-button" @click="emit('shopping')">查看已有采购清单</button></div></div>
</section>
</template>

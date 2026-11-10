<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import RecipeEditor from './components/RecipeEditor.vue'
import RecipeDetail from './components/RecipeDetail.vue'
import TagManager from './components/TagManager.vue'
import DailyFeature from './components/DailyFeature.vue'
import { blankRecipe, api } from './recipeEditing'
import { Leaf, BookOpen, Refrigerator, ShoppingBasket, Plus, Search, ArrowUpRight, Clock3, Users, X, Check, Link, Pencil, Trash2, ArrowRight, ChefHat, Download, CircleHelp } from 'lucide-vue-next'
const page=ref('recipes'), recipes=ref([]), query=ref(''), activeTags=ref([]), catalog=ref({groups:[],tags:[]}), tagManager=ref(false), selected=ref([]), detail=ref(null), editor=ref(null), importer=ref(false), url=ref(''), busy=ref(false), notice=ref(''), error=ref(''), shopping=ref([]), have=ref(''), staples=ref('盐、油'), matches=ref([]), matched=ref(false), done=ref({})
const nav=[['recipes','首页',BookOpen],['pantry','冰箱里有什么',Refrigerator],['shopping','采购清单',ShoppingBasket]]
watch(page,()=>window.scrollTo({top:0}))
const filterGroups=computed(()=>catalog.value.groups.map(g=>({...g,tags:catalog.value.tags.filter(t=>t.group_id===g.id)})).filter(g=>g.tags.length))
function toggleTag(id){activeTags.value=activeTags.value.includes(id)?activeTags.value.filter(t=>t!==id):[...activeTags.value,id]}
const filtered=computed(()=>recipes.value.filter(r=>activeTags.value.every(id=>r.tag_ids.includes(id))&&(r.name+r.ingredients.map(i=>i.name).join('')+r.tags.map(t=>t.group+t.name).join('')).includes(query.value)))
const completed=computed(()=>shopping.value.filter(i=>i.checked).length)
function flash(msg){notice.value=msg;setTimeout(()=>notice.value='',3500)}
async function load(){const [rows,tags]=await Promise.all([api('/recipes'),api('/tags')]);recipes.value=rows;catalog.value=tags;activeTags.value=activeTags.value.filter(id=>tags.tags.some(t=>t.id===id));if(detail.value)detail.value=rows.find(r=>r.id===detail.value.id)||null}
onMounted(async()=>{try{await load();shopping.value=await api('/shopping');const s=await api('/settings');have.value=s.ingredients.join('、');staples.value=s.staples.join('、')}catch(e){error.value=e.message}})
function sourceLabel(recipe){return recipe.source.platform==='xiaohongshu'?'小红书':recipe.source.platform==='douguo'?'豆果美食':recipe.source.author==='食拾示例'?'内置示例':recipe.source.author==='食拾精选'?'食拾精选':'手动录入'}
function edit(r){editor.value=JSON.parse(JSON.stringify(r||blankRecipe()));detail.value=null;error.value=''}
async function importLink(){busy.value=true;error.value='';try{editor.value=await api('/imports','POST',{url:url.value});importer.value=false;flash('已提取，请核对材料和步骤后保存')}catch(e){error.value=e.message}finally{busy.value=false}}
async function save(value){busy.value=true;error.value='';try{const r=value||editor.value;await api('/recipes'+(r.id?'/'+r.id:''),r.id?'PUT':'POST',r);editor.value=null;await load();matched.value=false;flash('已保存到我的食谱')}catch(e){error.value=e.message}finally{busy.value=false}}
async function remove(r){if(!confirm('确定删除「'+r.name+'」吗？'))return;try{await api('/recipes/'+r.id,'DELETE');detail.value=null;selected.value=selected.value.filter(id=>id!==r.id);await load();matched.value=false;flash('食谱已删除')}catch(e){error.value=e.message}}
function toggle(id){selected.value=selected.value.includes(id)?selected.value.filter(x=>x!==id):[...selected.value,id]}
async function generate(){busy.value=true;try{shopping.value=await api('/shopping','POST',{ids:selected.value});page.value='shopping';detail.value=null;flash('已合并采购清单')}catch(e){error.value=e.message}finally{busy.value=false}}
const split=t=>t.split(/[、,，\s]+/).filter(Boolean)
async function match(){try{const body={ingredients:split(have.value),staples:split(staples.value)};matches.value=await api('/match','POST',body);await api('/settings','PUT',body);matched.value=true}catch(e){error.value=e.message}}
async function persist(){try{await api('/shopping','PUT',{items:shopping.value})}catch(e){error.value='清单保存失败：'+e.message}}
function exportList(){const text=shopping.value.map(i=>`${i.checked?'☑':'☐'} ${i.name} ${i.amount}`).join('\n');const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([text],{type:'text/plain;charset=utf-8'}));a.download='食拾采购清单.txt';a.click();URL.revokeObjectURL(a.href)}
</script>

<template>
<div class="layout" :class="{'has-selection':selected.length}">
  <aside class="sidebar">
    <a class="brand" href="#" @click.prevent="page='recipes'"><span class="brand-symbol"><Leaf :size="25"/></span><span>食拾<small>SHI SHI</small></span></a>
    <p class="sidebar-label">我的厨房</p>
    <nav aria-label="厨房导航"><button v-for="[id,label,icon] in nav" :key="id" :class="{active:page===id}" :aria-current="page===id?'page':undefined" @click="page=id;error='' "><component :is="icon" :size="19"/>{{label}}<span v-if="id==='recipes'" class="nav-count">{{recipes.length}}</span><span v-if="id==='shopping'&&shopping.length" class="nav-dot"></span></button></nav>
    <div class="sidebar-note"><span>一餐一饭，好好生活。</span><p>把散落的好味道，<br>收进自己的小厨房。</p><Leaf :size="40" stroke-width="1"/></div>
    <div class="profile"><span class="avatar">拾</span><div>我的本地厨房<small><i></i> 数据保存在本机</small></div><span class="version">v0.1</span></div>
  </aside>
  <main>
    <header class="topbar"><span>我的厨房 <span class="slash">/</span> {{nav.find(n=>n[0]===page)?.[1]}}</span><span class="top-tip"><Leaf :size="14"/> 每一份收藏，都是下一餐的灵感</span></header>
    <div class="content">
      <div v-if="error&&!editor&&!importer" class="alert" role="alert">{{error}}<button @click="error=''">×</button></div>
      <template v-if="page==='recipes'">
        <section class="page-heading"><div><div class="eyebrow">A TASTE OF EVERYDAY</div><h1>今天，吃点好的<span class="title-dot">。</span></h1><p>顺着时令，发现一道好味道。</p></div><button class="primary" @click="importer=true;error='' "><Plus :size="18"/> 导入食谱</button></section>
        <DailyFeature @collect="edit"/>
        <section class="library-tools"><div class="section-title"><h2>收藏的好味道</h2><span>{{recipes.length}} 道食谱</span></div><label class="search"><Search :size="17"/><input v-model="query" placeholder="搜索菜名、食材或标签" aria-label="搜索食谱"/></label></section>
        <div class="filter-row"><span class="muted">已选 {{activeTags.length}} 个标签 · 同时满足</span><div class="library-actions"><button class="text-button" @click="tagManager=true">管理标签</button><button class="text-button" @click="edit()"><Plus :size="15"/>手动录入</button></div></div>
        <div class="filter-groups"><div v-for="group in filterGroups" :key="group.id" class="tag-choice-group"><strong>{{group.name}}</strong><div class="tag-options"><button v-for="tag in group.tags" :key="tag.id" :class="{chosen:activeTags.includes(tag.id)}" :aria-pressed="activeTags.includes(tag.id)" @click="toggleTag(tag.id)">{{tag.name}}</button></div></div><button v-if="activeTags.length" class="text-button" @click="activeTags=[]">清除标签筛选</button></div>
        <div class="recipe-grid"><article v-for="(r,index) in filtered" :key="r.id" class="recipe-card" @click="detail=r"><div class="card-art" :class="'tone-'+(index%6)"><span class="food-emoji">{{r.emoji||'🍲'}}</span><span class="card-source">{{sourceLabel(r)}}</span><button class="select-recipe" :class="{checked:selected.includes(r.id)}" @click.stop="toggle(r.id)" :aria-label="'选择'+r.name"><Check v-if="selected.includes(r.id)" :size="16"/><Plus v-else :size="16"/></button></div><div class="card-body"><div class="card-title"><h3>{{r.name}}</h3><ArrowUpRight :size="17"/></div><p>{{r.ingredients.slice(0,3).map(i=>i.name).join(' · ')}}</p><div class="card-bottom"><span class="small-tag">{{r.tags.slice(0,2).map(t=>t.name).join(' · ')||'未分类'}}</span><span><Clock3 :size="13"/>{{r.minutes? r.minutes+' 分钟':'耗时未注明'}}</span></div></div></article><button class="add-card" @click="importer=true;error='' "><span><Plus :size="25"/></span><strong>收藏下一份美味</strong><p>收藏豆果与小红书里的做法</p></button></div>
        <p v-if="!filtered.length" class="empty">还没有匹配的食谱，换个关键词或收藏一道新菜吧。</p>
        <footer class="page-footer"><span><Leaf :size="14"/> 认真做饭，也是认真生活。</span><span>食拾 · 你的个人食谱手帐</span></footer>
      </template>
      <template v-if="page==='pantry'"><section class="page-heading"><div><div class="eyebrow">COOK WITH WHAT YOU HAVE</div><h1>冰箱里有什么<span class="title-dot">?</span></h1><p>告诉食拾手边的食材，从收藏里找下一餐。</p></div><Refrigerator :size="45" stroke-width="1"/></section><section class="pantry-form"><label>现有食材<textarea v-model="have" placeholder="例如：番茄、鸡蛋、土豆"/></label><label>常备调料<input v-model="staples" placeholder="盐、油"/></label><p class="muted">用顿号、逗号或空格分隔。只比较食材种类，不判断数量是否足够。</p><button class="primary" @click="match"><Search :size="17"/> 找找能做什么</button></section><div v-if="matched" class="match-list"><div v-for="r in matches" class="match-item"><span class="match-emoji">{{r.emoji||'🍲'}}</span><div @click="detail=r" class="clickable"><h3>{{r.name}}</h3><p :class="{available:!r.missing.length}">{{r.missing.length?'还缺：'+r.missing.join('、'):'食材种类已齐全，可以开做！'}}</p></div><button class="secondary" @click="toggle(r.id)">{{selected.includes(r.id)?'已选中':'选入菜单'}}</button></div><p v-if="!matches.length" class="empty">先去收藏一些食谱吧。</p></div></template>
      <template v-if="page==='shopping'"><section class="page-heading"><div><div class="eyebrow">A LITTLE PREPARATION</div><h1>采购清单<span class="title-dot">.</span></h1><p>把几道菜的材料，整理成一次从容的采购。</p></div><button v-if="shopping.length" class="secondary" @click="exportList"><Download :size="17"/> 导出清单</button></section><section v-if="shopping.length" class="shopping-panel"><div class="shopping-heading"><strong>这次要买的材料</strong><span>{{completed}} / {{shopping.length}} 已备齐</span></div><div class="progress"><span :style="{width:completed/shopping.length*100+'%'}"></span></div><div v-for="(item,index) in shopping" :key="index" class="shopping-row" :class="{isdone:item.checked}"><input type="checkbox" v-model="item.checked" @change="persist" :aria-label="'已备齐'+item.name"/><div><strong>{{item.name}}</strong><details><summary>{{item.sources.length}} 份用料来源</summary><p v-for="s in item.sources">{{s.recipe}}：{{s.original}}</p></details></div><input class="amount-input" v-model="item.amount" @change="persist" :aria-label="item.name+'用量'"/></div><p class="muted">用量可直接修改；不同计量类别和模糊用量分别保留。</p></section><div v-else class="empty-panel"><ShoppingBasket :size="54" stroke-width="1"/><h2>下一餐，从选几道菜开始</h2><p>在食谱卡片上点「＋」，再生成合并采购清单。</p><button class="primary" @click="page='recipes'">去选菜 <ArrowRight :size="16"/></button></div></template>
    </div>
  </main>
  <div v-if="selected.length" class="selection-bar"><span><strong>{{selected.length}}</strong> 道菜已选好</span><button class="text-button" @click="selected=[]">清空</button><button class="primary" :disabled="busy" @click="generate">生成采购清单 <ArrowRight :size="16"/></button></div>
  <div v-if="notice" class="toast" role="status"><Check :size="17"/>{{notice}}</div>
  <div v-if="importer" class="overlay" @click.self="!busy&&(importer=false)"><section class="modal import-modal"><button class="close" @click="importer=false" :disabled="busy" aria-label="关闭"><X/></button><span class="modal-icon"><Link :size="27"/></span><div class="eyebrow">SAVE YOUR NEXT FAVORITE</div><h2>留住一道好味道</h2><p class="muted">粘贴豆果菜谱或小红书图文笔记，提取后核对并保存。</p><form @submit.prevent="importLink"><label>链接或分享文案<textarea v-model="url" required placeholder="粘贴豆果菜谱链接、小红书完整分享链接或 xhslink.com 短链"/></label><div v-if="error" class="alert">{{error}}</div><button class="primary wide" :disabled="busy">{{busy?'正在读取页面并提取…':'提取食谱'}} <ArrowRight :size="17"/></button></form><p class="import-note"><CircleHelp :size="15"/> 支持豆果菜谱和小红书文字正文；图片或视频中的做法暂不识别。</p><button class="text-button" @click="importer=false;edit()">也可以手动录入一道菜 <Pencil :size="14"/></button></section></div>
  <RecipeEditor v-if="editor" :recipe="editor" :catalog="catalog" :busy="busy" :error="error" @cancel="editor=null" @save="save" @catalog-change="load" @manage-tags="tagManager=true"/>
  <RecipeDetail v-if="detail" :key="detail.id" :recipe="detail" :done="done" :selected="selected.includes(detail.id)" @close="detail=null" @edit="edit" @remove="remove" @toggle="toggle"/>
  <TagManager v-if="tagManager" :catalog="catalog" @close="tagManager=false" @changed="load"/>
</div>
</template>

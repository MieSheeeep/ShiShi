<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import RecipeEditor from './components/RecipeEditor.vue'
import RecipeDetail from './components/RecipeDetail.vue'
import TagManager from './components/TagManager.vue'
import LoginView from './components/LoginView.vue'
import DailyFeature from './components/DailyFeature.vue'
import AiSetup from './components/AiSetup.vue'
import AccountPanel from './components/AccountPanel.vue'
import { blankRecipe, api, clearToken, getToken, onUnauthorized } from './recipeEditing'
import { isCondiment, UNITS } from './pantry'
import { Leaf, BookOpen, Refrigerator, ShoppingBasket, Plus, Search, ArrowUpRight, Clock3, Users, X, Check, Link, Pencil, Trash2, ArrowRight, ChefHat, Flame, Download, Sparkles, Settings } from 'lucide-vue-next'
const page=ref('recipes'), recipes=ref([]), query=ref(''), activeTags=ref([]), catalog=ref({groups:[],tags:[]}), tagManager=ref(false), selected=ref([]), detail=ref(null), editor=ref(null), importer=ref(false), url=ref(''), keyword=ref(''), aiPrompt=ref(''), importMeta=ref(null), busy=ref(false), notice=ref(''), error=ref(''), shopping=ref([]), have=ref([]), staples=ref([]), pickName=ref(''), pickAmount=ref(''), pickUnit=ref(''), pantryPick=ref(''), matches=ref([]), matched=ref(false), done=ref({}), barClosed=ref(false)
const menu=ref([])
const aiSetup=ref(false), accountOpen=ref(false), aiDishes=ref([]), aiBusy=ref(false), aiError=ref(''), aiOpen=ref(true)
const cookRecipes=computed(()=>recipes.value.filter(r=>menu.value.includes(r.id)))
const cookTotal=computed(()=>cookRecipes.value.reduce((sum,r)=>sum+r.steps.length,0))
const cookDone=computed(()=>cookRecipes.value.reduce((sum,r)=>sum+r.steps.filter(s=>done.value[s.id]).length,0))
const user=ref(null), authReady=ref(false)
const nav=[['recipes','首页',BookOpen],['pantry','冰箱里有什么',Refrigerator],['today','今天做什么',ChefHat],['shopping','采购清单',ShoppingBasket]]
watch(page,()=>window.scrollTo({top:0}))
const filterGroups=computed(()=>catalog.value.groups.map(g=>({...g,tags:catalog.value.tags.filter(t=>t.group_id===g.id)})).filter(g=>g.tags.length))
function toggleTag(id){activeTags.value=activeTags.value.includes(id)?activeTags.value.filter(t=>t!==id):[...activeTags.value,id]}
const filtered=computed(()=>recipes.value.filter(r=>activeTags.value.every(id=>r.tag_ids.includes(id))&&(r.name+r.ingredients.map(i=>i.name).join('')+r.tags.map(t=>t.group+t.name).join('')).includes(query.value)))
const PAGE_SIZE=11, listPage=ref(1)
const pageCount=computed(()=>Math.max(1,Math.ceil(filtered.value.length/PAGE_SIZE)))
const pagedRecipes=computed(()=>filtered.value.slice((listPage.value-1)*PAGE_SIZE,listPage.value*PAGE_SIZE))
watch([query,activeTags],()=>{listPage.value=1})
watch(pageCount,()=>{if(listPage.value>pageCount.value)listPage.value=pageCount.value})
function gotoPage(n){listPage.value=Math.min(Math.max(1,n),pageCount.value);document.querySelector('.library-tools')?.scrollIntoView({behavior:'smooth',block:'start'})}
const buyList=computed(()=>shopping.value.filter(i=>!i.pantry))
const pantryList=computed(()=>shopping.value.filter(i=>i.pantry))
const completed=computed(()=>buyList.value.filter(i=>i.checked).length)
const clearConfirm=ref(false),cancelConfirm=ref(false)
watch(completed,()=>{if(completed.value!==buyList.value.length)clearConfirm.value=false})
function flash(msg){notice.value=msg;setTimeout(()=>notice.value='',3500)}
async function load(){const [rows,tags]=await Promise.all([api('/recipes'),api('/tags')]);recipes.value=rows;catalog.value=tags;activeTags.value=activeTags.value.filter(id=>tags.tags.some(t=>t.id===id));if(detail.value)detail.value=rows.find(r=>r.id===detail.value.id)||null}
async function start(){try{await load();shopping.value=await api('/shopping');const s=await api('/settings');have.value=s.ingredients;staples.value=s.staples}catch(e){error.value=e.message}}
async function savePantry(){try{await api('/settings','PUT',{ingredients:have.value,staples:staples.value})}catch(e){error.value=e.message}}
function entry(name,amount,unit){return {name,amount:amount.trim(),unit}}
function pushNames(list,names,amount,unit){
  for(const raw of split(names)){
    let target=list, note=''
    if(pantryPick.value==='have'&&isCondiment(raw)){target=staples.value;note=`「${raw}」按调料处理，已加入常备调料`}
    if(!target.some(i=>i.name===raw))target.push(entry(raw,amount,unit))
    if(note)flash(note)
  }
  matched.value=false
}
function removeItem(list,index){list.splice(index,1);savePantry();matched.value=false}
const ingredientLibrary=computed(()=>{const set=new Set();for(const r of recipes.value)for(const i of (r.ingredients||[]))if(i.kind!=='调料'&&i.name&&!isCondiment(i.name))set.add(i.name);return [...set].sort()})
const stapleLibrary=computed(()=>{const set=new Set();for(const r of recipes.value)for(const i of (r.ingredients||[]))if((i.kind==='调料'||isCondiment(i.name))&&i.name)set.add(i.name);return [...set].sort()})
const pickerList=computed(()=>pantryPick.value==='have'?have.value:staples.value)
const pickerLibrary=computed(()=>pantryPick.value==='have'?ingredientLibrary.value:stapleLibrary.value)
function openPicker(kind){pantryPick.value=kind;pickName.value='';pickAmount.value='';pickUnit.value=''}
function pickItem(name){const target=pantryPick.value==='have'&&isCondiment(name)?staples.value:(pantryPick.value==='have'?have.value:staples.value);if(!target.some(i=>i.name===name)){target.push(entry(name,pickAmount.value,pickUnit.value));savePantry();matched.value=false}}
function addFromPicker(){pushNames(pickerList.value,pickName.value,pickAmount.value,pickUnit.value);pickName.value='';pickAmount.value='';savePantry()}
function removePickerItem(index){removeItem(pickerList.value,index)}
function leave(){user.value=null;recipes.value=[];catalog.value={groups:[],tags:[]};shopping.value=[];selected.value=[];menu.value=[];done.value={};managing.value=false;picked.value=[];deleteConfirm.value=false;showMenu.value=false;detail.value=null;editor.value=null;tagManager.value=false;importer.value=false;matches.value=[];matched.value=false;have.value=[];staples.value=[];pickName.value='';pickAmount.value='';pickUnit.value='';error.value='';activeTags.value=[];query.value='';listPage.value=1;barClosed.value=false;aiSetup.value=false;accountOpen.value=false;aiDishes.value=[];aiError.value=''}
async function checkAi(){try{const data=await api('/ai/settings');aiSetup.value=!data.configured}catch{}}
function authenticated(data){user.value=data.user;start().then(checkAi)}
async function boot(){if(!getToken()){authReady.value=true;return}try{user.value=await api('/auth/me')}catch{clearToken()}authReady.value=true;if(user.value){await start();await checkAi()}}
async function signOut(){try{await api('/auth/logout','POST')}catch{}clearToken();leave()}
onUnauthorized(leave)
onMounted(boot)
function sourceLabel(recipe){return recipe.source.platform==='xiaohongshu'?'小红书':recipe.source.platform==='douguo'?'豆果美食':recipe.source.author==='食拾示例'?'内置示例':recipe.source.author==='食拾精选'?'食拾精选':recipe.source.author==='AI 生成草稿'?'AI 生成':'手动录入'}
function edit(r){editor.value=JSON.parse(JSON.stringify(r||blankRecipe()));importMeta.value=null;detail.value=null;error.value=''}
async function importLink(){busy.value=true;error.value='';try{editor.value=await api('/imports','POST',{url:url.value});importMeta.value=null;importer.value=false;flash('已提取，请核对材料和步骤后保存')}catch(e){error.value=e.message}finally{busy.value=false}}
async function searchImport(){busy.value=true;error.value='';try{const r=await api('/imports/search','POST',{keyword:keyword.value});editor.value=r.draft;importMeta.value=r.meta;importer.value=false;flash('已提取，请核对材料和步骤后保存')}catch(e){error.value=e.message}finally{busy.value=false}}
async function nextImport(){busy.value=true;error.value='';try{const r=await api('/imports/search','POST',{keyword:importMeta.value.keyword,index:importMeta.value.index+1});editor.value=r.draft;importMeta.value=r.meta}catch(e){error.value=e.message}finally{busy.value=false}}
async function aiGenerate(){busy.value=true;error.value='';try{editor.value=await api('/imports/generate','POST',{prompt:aiPrompt.value});importMeta.value=null;importer.value=false;flash('AI 已生成草稿，请核对后保存')}catch(e){error.value=e.message}finally{busy.value=false}}
async function save(value){busy.value=true;error.value='';try{const r=value||editor.value;await api('/recipes'+(r.id?'/'+r.id:''),r.id?'PUT':'POST',r);editor.value=null;importMeta.value=null;await load();matched.value=false;flash('已保存到我的食谱')}catch(e){error.value=e.message}finally{busy.value=false}}
async function remove(r){if(!confirm('确定删除「'+r.name+'」吗？'))return;try{await api('/recipes/'+r.id,'DELETE');detail.value=null;selected.value=selected.value.filter(id=>id!==r.id);menu.value=menu.value.filter(id=>id!==r.id);await load();matched.value=false;flash('食谱已删除')}catch(e){error.value=e.message}}
function toggle(id){
  if(selected.value.includes(id)){selected.value=selected.value.filter(x=>x!==id);return}
  selected.value=[...selected.value,id];barClosed.value=false
}
function closeBar(){barClosed.value=true}
const showMenu=ref(false)
const selectedRecipes=computed(()=>recipes.value.filter(r=>selected.value.includes(r.id)))
function removeSelected(id){selected.value=selected.value.filter(x=>x!==id);if(!selected.value.length)showMenu.value=false}
function clearSelected(){selected.value=[];showMenu.value=false}
const managing=ref(false), picked=ref([]), deleteConfirm=ref(false)
function startManage(){managing.value=true;picked.value=[];deleteConfirm.value=false}
function exitManage(){managing.value=false;picked.value=[];deleteConfirm.value=false}
function pickRecipe(id){picked.value=picked.value.includes(id)?picked.value.filter(x=>x!==id):[...picked.value,id];deleteConfirm.value=false}
async function removePicked(){busy.value=true;error.value='';try{const ids=picked.value.slice();for(const id of ids)await api('/recipes/'+id,'DELETE');selected.value=selected.value.filter(id=>!ids.includes(id));menu.value=menu.value.filter(id=>!ids.includes(id));exitManage();await load();matched.value=false;flash(`已删除 ${ids.length} 道食谱`)}catch(e){error.value=e.message}finally{busy.value=false}}
function clearToday(){menu.value=[];done.value={};flash('这顿饭已清空')}
function finishCooking(){menu.value=[];done.value={};flash('这顿饭做好了，开饭吧')}
function goPantry(){page.value='pantry';if(have.value.length||staples.value.length)match()}
async function generate(){busy.value=true;clearConfirm.value=false;cancelConfirm.value=false;try{shopping.value=await api('/shopping','POST',{ids:selected.value});page.value='shopping';detail.value=null;flash('已合并采购清单')}catch(e){error.value=e.message}finally{busy.value=false}}
const split=t=>t.split(/[、,，\s]+/).filter(Boolean)
async function aiSuggest(){aiBusy.value=true;aiError.value='';try{const data=await api('/ai/suggest','POST',{ingredients:have.value,staples:staples.value});aiDishes.value=data.dishes;aiOpen.value=true}catch(e){aiError.value=e.message}finally{aiBusy.value=false}}
async function aiCook(dish){busy.value=true;aiError.value='';try{const names=[...have.value,...staples.value].map(i=>i.name).join('、').slice(0,120);editor.value=await api('/imports/generate','POST',{prompt:`用厨房现有的${names||'食材'}，做一道「${dish.name}」。${dish.reason||''}`.slice(0,300)});importMeta.value=null}catch(e){aiError.value=e.message}finally{busy.value=false}}
async function match(){try{matches.value=await api('/match','POST',{ingredients:have.value,staples:staples.value});matched.value=true}catch(e){error.value=e.message}}
async function persist(){try{await api('/shopping','PUT',{items:shopping.value})}catch(e){error.value='清单保存失败：'+e.message}}
async function finishShopping(){try{await api('/shopping','PUT',{items:[]});shopping.value=[];clearConfirm.value=false;cancelConfirm.value=false;flash('采购完成，清单已清空')}catch(e){error.value=e.message}}
async function cancelShopping(){try{await api('/shopping','PUT',{items:[]});shopping.value=[];clearConfirm.value=false;cancelConfirm.value=false;flash('已取消本次采购，清单已清空')}catch(e){error.value=e.message}}
function exportList(){const text=buyList.value.map(i=>`${i.checked?'☑':'☐'} ${i.name} ${i.amount}`).join('\n');const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([text],{type:'text/plain;charset=utf-8'}));a.download='食拾采购清单.txt';a.click();URL.revokeObjectURL(a.href)}
</script>

<template>
<div v-if="!authReady" class="auth-screen"><span class="muted">正在恢复会话…</span></div>
<LoginView v-else-if="!user" @authenticated="authenticated"/>
<div v-else class="layout" :class="{'has-selection':selected.length}">
  <aside class="sidebar">
    <a class="brand" href="#" @click.prevent="page='recipes'"><span class="brand-symbol"><Leaf :size="25"/></span><span>食拾<small>SHI SHI</small></span></a>
    <p class="sidebar-label">我的厨房</p>
    <nav aria-label="厨房导航"><button v-for="[id,label,icon] in nav" :key="id" :class="{active:page===id}" :aria-current="page===id?'page':undefined" @click="page=id;error='' "><component :is="icon" :size="19"/>{{label}}<span v-if="id==='recipes'" class="nav-count">{{recipes.length}}</span><span v-if="id==='shopping'&&shopping.length" class="nav-dot"></span></button></nav>
    <div class="sidebar-note"><span>一餐一饭，好好生活。</span><p>把散落的好味道，<br>收进自己的小厨房。</p><Leaf :size="40" stroke-width="1"/></div>
    <div class="profile"><span class="avatar">{{user.username.slice(0,1)}}</span><div>{{user.username}}<small><i></i> 已登录 · 数据保存在本机</small></div><button class="icon-button" @click="accountOpen=true" aria-label="账号管理" title="账号管理"><Settings :size="16"/></button></div>
  </aside>
  <main>
    <header class="topbar"><span>我的厨房 <span class="slash">/</span> {{nav.find(n=>n[0]===page)?.[1]}}</span><span class="top-right"><span class="top-tip"><Leaf :size="14"/> 每一份收藏，都是下一餐的灵感</span><span class="top-account"><i></i>{{user.username}}</span></span></header>
    <div class="content">
      <div v-if="error&&!editor&&!importer" class="alert" role="alert">{{error}}<button @click="error=''">×</button></div>
      <template v-if="page==='recipes'">
        <section class="page-heading"><div><div class="eyebrow">A TASTE OF EVERYDAY</div><h1>今天，吃点好的<span class="title-dot">。</span></h1><p>顺着时令，发现一道好味道。</p></div><button class="primary" @click="importer=true;error='' "><Plus :size="18"/> 导入食谱</button></section>
        <DailyFeature @collect="edit"/>
        <section class="library-tools"><div class="section-title"><h2>收藏的好味道</h2><span>{{recipes.length}} 道食谱</span></div><label class="search"><Search :size="17"/><input v-model="query" placeholder="搜索菜名、食材或标签" aria-label="搜索食谱"/></label></section>
        <div class="filter-toolbar"><div class="filter-groups"><div v-for="group in filterGroups" :key="group.id" class="tag-choice-group"><strong>{{group.name}}</strong><div class="tag-options"><button v-for="tag in group.tags" :key="tag.id" :class="{chosen:activeTags.includes(tag.id)}" :aria-pressed="activeTags.includes(tag.id)" @click="toggleTag(tag.id)">{{tag.name}}</button></div></div><button v-if="activeTags.length" class="text-button" @click="activeTags=[]">清除标签筛选</button></div><div class="library-actions"><button class="text-button" @click="tagManager=true">管理标签</button><button class="text-button" @click="edit()"><Plus :size="15"/>手动录入食谱</button></div></div>
        <div class="filter-row"><span class="muted">已选 {{activeTags.length}} 个标签 · 同时满足</span><button v-if="!managing" class="secondary" @click="startManage"><Trash2 :size="15"/> 批量删除</button></div>
        <div class="recipe-grid"><article v-for="(r,index) in pagedRecipes" :key="r.id" class="recipe-card" :class="{picked:picked.includes(r.id)}" @click="managing?pickRecipe(r.id):detail=r"><div class="card-art" :class="['tone-'+(index%6),{'has-cover':r.cover}]"><img v-if="r.cover" class="card-cover" :src="r.cover" :alt="r.name+'成品图'" loading="lazy"/><span v-else class="food-emoji">{{r.emoji||'🍲'}}</span><span class="card-source">{{sourceLabel(r)}}</span><button class="select-recipe" :class="{checked:managing?picked.includes(r.id):selected.includes(r.id)}" @click.stop="managing?pickRecipe(r.id):toggle(r.id)" :aria-label="(managing?'选择删除':'选择')+r.name"><Check v-if="managing?picked.includes(r.id):selected.includes(r.id)" :size="16"/><Plus v-else :size="16"/></button></div><div class="card-body"><div class="card-title"><h3>{{r.name}}</h3><ArrowUpRight :size="17"/></div><p>{{r.ingredients.slice(0,3).map(i=>i.name).join(' · ')}}</p><div class="card-bottom"><span class="small-tag">{{r.tags.slice(0,2).map(t=>t.name).join(' · ')||'未分类'}}</span><span><Clock3 :size="13"/>{{r.minutes? r.minutes+' 分钟':'耗时未注明'}}</span></div></div></article><button class="add-card" @click="importer=true;error='' "><span><Plus :size="25"/></span><strong>收藏下一份美味</strong><p>收藏豆果与小红书里的做法</p></button></div>
        <div class="recipe-pager" v-if="pageCount>1"><button class="text-button" :disabled="listPage<=1" @click="gotoPage(listPage-1)">上一页</button><span class="pager-info">第 {{listPage}} / {{pageCount}} 页</span><button class="text-button" :disabled="listPage>=pageCount" @click="gotoPage(listPage+1)">下一页</button></div>
        <p v-if="!filtered.length" class="empty">还没有匹配的食谱，换个关键词或收藏一道新菜吧。</p>
        <footer class="page-footer"><span><Leaf :size="14"/> 认真做饭，也是认真生活。</span><span>食拾 · 你的个人食谱手帐</span></footer>
      </template>
      <template v-if="page==='pantry'"><section class="page-heading"><div><div class="eyebrow">COOK WITH WHAT YOU HAVE</div><h1>冰箱里有什么<span class="title-dot">?</span></h1><p>告诉食拾手边的食材，从收藏里找下一餐。</p></div><Refrigerator :size="45" stroke-width="1"/></section><section class="pantry-form"><div class="pantry-actions"><button class="secondary" @click="openPicker('have')"><Plus :size="16"/> 添加已有食材</button><button class="secondary" @click="openPicker('staples')"><Plus :size="16"/> 添加常备调料</button><button class="secondary" @click="flash('食材库导入功能待接入')"><BookOpen :size="16"/> 从食材库导入</button></div><div class="pantry-block"><div class="pantry-block-head"><strong>厨房已有食材</strong><span class="muted">{{have.length}} 种</span></div><div class="chip-row"><span v-for="(item,index) in have" :key="item.name" class="pantry-chip">{{item.name}}<em v-if="item.amount||item.unit">{{item.amount}}{{item.unit}}</em><button type="button" @click="removeItem(have,index)" :aria-label="'移除'+item.name">×</button></span><span v-if="!have.length" class="muted">还没有添加食材，点上方「添加已有食材」</span></div></div><div class="pantry-block"><div class="pantry-block-head"><strong>常备调料</strong><span class="muted">{{staples.length}} 种</span></div><div class="chip-row"><span v-for="(item,index) in staples" :key="item.name" class="pantry-chip">{{item.name}}<em v-if="item.amount||item.unit">{{item.amount}}{{item.unit}}</em><button type="button" @click="removeItem(staples,index)" :aria-label="'移除'+item.name">×</button></span><span v-if="!staples.length" class="muted">还没有添加调料，点上方「添加常备调料」</span></div></div><p class="muted">数量与单位只作记录；匹配只比较食材种类。</p><div class="pantry-run"><button class="primary" @click="match"><Search :size="17"/> 找找能做什么</button><button class="primary" :disabled="aiBusy" @click="aiSuggest"><Sparkles :size="17"/> {{aiBusy?'AI 正在想…':'让 AI 想想做什么'}}</button></div><div v-if="aiError" class="alert" role="alert">{{aiError}}</div><div v-if="aiDishes.length" class="ai-dishes"><div class="ai-dishes-head"><strong>AI 推荐</strong><button class="text-button" @click="aiOpen=!aiOpen">{{aiOpen?'收起':'展开'}}</button></div><template v-if="aiOpen"><article v-for="dish in aiDishes" :key="dish.name" class="ai-dish"><div><h3>{{dish.name}}</h3><p>{{dish.reason}}</p></div><button class="secondary" :disabled="busy" @click="aiCook(dish)">生成食谱</button></article></template></div></section><div v-if="matched" class="match-list"><div v-for="r in matches" class="match-item"><span class="match-emoji">{{r.emoji||'🍲'}}</span><div @click="detail=r" class="clickable"><h3>{{r.name}}</h3><p :class="{available:!r.missing.length}">{{r.missing.length?'还缺：'+r.missing.join('、'):'食材种类已齐全，可以开做！'}}</p></div><button class="secondary" @click="toggle(r.id)">{{selected.includes(r.id)?'已选中':'选入菜单'}}</button></div><p v-if="!matches.length" class="empty">先去收藏一些食谱吧。</p></div></template>
      <template v-if="page==='today'"><section class="page-heading"><div><div class="eyebrow">COOK TODAY</div><h1>今天做什么<span class="title-dot">.</span></h1><p>把选好的菜放到灶台边，一步一步往下做。</p></div><ChefHat :size="45" stroke-width="1"/></section><section v-if="!menu.length" class="empty-panel"><ChefHat :size="54" stroke-width="1"/><h2>还没有选菜</h2><p>在首页或「冰箱里有什么」里勾选几道菜，再点底部的「去做饭」。</p><div class="empty-actions"><button class="primary" @click="page='recipes'">去选菜 <ArrowRight :size="16"/></button><button class="primary" @click="goPantry"><Refrigerator :size="16"/> 去冰箱看看能做什么</button></div></section><template v-else><section class="today-card"><div class="today-head"><div><div class="eyebrow">YOUR MENU</div><h2>今天这 {{menu.length}} 道</h2></div><span class="muted">已勾选 {{cookDone}} / {{cookTotal}} 步</span></div><div class="chip-row"><span v-for="r in cookRecipes" :key="r.id" class="pantry-chip">{{r.name}}</span></div><div class="today-actions"><button class="text-button" @click="page='recipes'">换几道菜</button></div></section><section v-for="r in cookRecipes" :key="r.id" class="today-card cook-dish"><div class="today-head"><div><div class="eyebrow">DISH</div><h2>{{r.name}}</h2></div><span class="muted">已勾选 {{r.steps.filter(s=>done[s.id]).length}} / {{r.steps.length}} 步</span></div><h3>备料 <span>{{r.ingredients.length}} 项</span></h3><div v-for="item in r.ingredients" :key="item.id" class="ingredient-line"><span>{{item.name}}<small v-if="item.kind==='调料'">调料</small></span><strong>{{item.amount || '未注明'}}</strong></div><h3>开始下厨 <span>点一下勾掉一步</span></h3><label v-for="(step,stepIndex) in r.steps" :key="step.id" class="cooking-step" :class="{isdone:done[step.id]}"><input type="checkbox" v-model="done[step.id]"/><span class="step-number">{{String(stepIndex + 1).padStart(2, '0')}}</span><div class="cooking-step-content"><p>{{step.text}}</p></div></label><div v-if="r.notes" class="recipe-note"><strong>我的厨房笔记</strong><p>{{r.notes}}</p></div></section><p v-if="cookDone===cookTotal&&cookTotal" class="cook-finish"><Flame :size="16"/> 全部步骤都完成了，关火开吃。</p><div class="today-footer"><span class="muted">菜品和勾选都还留着，随时可以回来接着做。</span><div class="today-footer-actions"><button class="primary" :disabled="!cookTotal||cookDone!==cookTotal" @click="finishCooking">完成制作</button><button class="primary" @click="clearToday">清空这顿饭</button></div></div></template></template>
      <template v-if="page==='shopping'"><section class="page-heading"><div><div class="eyebrow">A LITTLE PREPARATION</div><h1>采购清单<span class="title-dot">.</span></h1><p>把几道菜的材料，整理成一次从容的采购。</p></div><div class="heading-actions"><button v-if="buyList.length" class="secondary" @click="exportList"><Download :size="17"/> 导出清单</button></div></section><section v-if="shopping.length" class="shopping-panel"><div class="shopping-heading"><strong>这次要买的材料</strong><span>{{completed}} / {{buyList.length}} 已备齐</span></div><div class="progress"><span :style="{width:(buyList.length?completed/buyList.length*100:0)+'%'}"></span></div><div v-for="(item,index) in buyList" :key="index" class="shopping-row" :class="{isdone:item.checked}"><input type="checkbox" v-model="item.checked" @change="persist" :aria-label="'已备齐'+item.name"/><div><strong>{{item.name}}</strong><details><summary>{{item.sources.length}} 份用料来源</summary><p v-for="s in item.sources">{{s.recipe}}：{{s.original}}</p></details><p v-if="item.pantryNote" class="pantry-note">{{item.pantryNote}}</p></div><input class="amount-input" v-model="item.amount" @change="persist" :aria-label="item.name+'用量'"/></div><p v-if="!buyList.length" class="empty">这次的材料冰箱里都有了，不用再买。</p><div v-if="pantryList.length" class="pantry-have"><strong>冰箱里已有，不计入清单</strong><div class="chip-row"><span v-for="item in pantryList" :key="item.name" class="pantry-chip">{{item.name}}<em v-if="item.amount">{{item.amount}}</em></span></div></div><p class="muted">用量可直接修改；不同计量类别和模糊用量分别保留。</p><div class="shopping-foot"><button v-if="!clearConfirm&&!cancelConfirm" class="primary" :disabled="!buyList.length||completed!==buyList.length" @click="clearConfirm=true"><Check :size="16"/> 完成并清空清单</button><button v-if="!clearConfirm&&!cancelConfirm" class="primary" @click="cancelConfirm=true">取消采购</button><template v-if="clearConfirm"><span class="muted">确认清空？已买的记录会一起移除。</span><button class="primary" @click="finishShopping">确定清空</button><button class="text-button" @click="clearConfirm=false">再想想</button></template><template v-else-if="cancelConfirm"><span class="muted">确认取消这次采购？清单会被清空。</span><button class="primary" @click="cancelShopping">确定取消</button><button class="text-button" @click="cancelConfirm=false">再想想</button></template></div></section><div v-else class="empty-panel"><ShoppingBasket :size="54" stroke-width="1"/><h2>下一餐，从选几道菜开始</h2><p>在食谱卡片上点「＋」，再生成合并采购清单。</p><div class="empty-actions"><button class="primary" @click="page='recipes'">去选菜 <ArrowRight :size="16"/></button><button class="primary" @click="goPantry"><Refrigerator :size="16"/> 去冰箱看看能做什么</button></div></div></template>
    </div>
  </main>
  <div v-if="managing&&page==='recipes'" class="selection-bar"><span><strong>{{picked.length}}</strong> 道食谱已选</span><template v-if="!deleteConfirm"><button class="text-button" @click="exitManage">取消</button><button class="danger-button" :disabled="!picked.length||busy" @click="deleteConfirm=true">删除所选</button></template><template v-else><span>确认删除？删除后无法恢复。</span><button class="danger-button" :disabled="busy" @click="removePicked">确定删除</button><button class="text-button" @click="deleteConfirm=false">再想想</button></template></div>
  <Transition name="tab-pop"><button v-if="selected.length&&barClosed&&!managing" class="bar-tab" @click="barClosed=false" :aria-label="`展开已选菜单，${selected.length} 道`"><ShoppingBasket :size="18"/><span>{{selected.length}}</span></button></Transition>
  <Transition name="fade-up"><div v-if="selected.length&&!barClosed&&!managing&&showMenu" class="selection-preview"><div class="preview-head"><strong>已选 {{selected.length}} 道</strong><div class="preview-head-actions"><button class="text-button danger-text" @click="clearSelected">清空</button><button class="text-button" @click="showMenu=false">关闭</button></div></div><div class="chip-row"><span v-for="r in selectedRecipes" :key="r.id" class="pantry-chip">{{r.name}}<button type="button" @click="removeSelected(r.id)" :aria-label="'移除'+r.name">×</button></span></div></div></Transition>
  <Transition name="bar-collapse"><div v-if="selected.length&&!barClosed&&!managing" class="selection-bar"><span><strong>{{selected.length}}</strong> 道菜已选好</span><button class="text-button" @click="showMenu=!showMenu">{{showMenu?'隐藏':'查看'}}</button><button class="text-button" @click="closeBar">收起</button><button class="primary" :disabled="busy" @click="generate">生成采购清单 <ArrowRight :size="16"/></button><button class="primary" @click="menu=[...selected];page='today'">去做饭 <ChefHat :size="16"/></button></div></Transition>
  <div v-if="notice" class="toast" role="status"><Check :size="17"/>{{notice}}</div>
  <div v-if="importer" class="overlay" @click.self="!busy&&(importer=false)"><section class="modal import-modal"><button class="close" @click="importer=false" :disabled="busy" aria-label="关闭"><X/></button><span class="modal-icon"><Link :size="27"/></span><div class="eyebrow">SAVE YOUR NEXT FAVORITE</div><h2>留住一道好味道</h2><form @submit.prevent="importLink"><label>链接或分享文案<textarea v-model="url" required rows="2" placeholder="粘贴豆果菜谱链接、小红书完整分享链接或 xhslink.com 短链"/></label><button class="primary wide" :disabled="busy||!url.trim()">{{busy?'正在读取页面并提取…':'提取食谱'}} <ArrowRight :size="17"/></button></form><form class="import-search" @submit.prevent="searchImport"><label>按菜名在豆果搜索<textarea v-model="keyword" required maxlength="30" rows="2" placeholder="例如：番茄炒蛋"/></label><button class="primary wide" :disabled="busy||!keyword.trim()">{{busy?'正在搜索并提取…':'搜索豆果'}} <Search :size="17"/></button></form><form class="import-ai" @submit.prevent="aiGenerate"><label>让 AI 写一道菜<small>描述口味、人数或手边食材，AI 生成草稿后仍需你核对</small><textarea v-model="aiPrompt" required maxlength="120" rows="2" placeholder="例如：30 分钟能做完的两人份下饭菜"/></label><button class="primary wide" :disabled="busy||!aiPrompt.trim()">{{busy?'AI 正在写…':'AI 生成食谱'}} <Sparkles :size="17"/></button></form><div v-if="error" class="alert">{{error}}</div><button class="text-button" @click="importer=false;edit()">也可以手动录入一道菜 <Pencil :size="14"/></button></section></div>
  <RecipeEditor v-if="editor" :key="importMeta?importMeta.index:'editor'" :recipe="editor" :catalog="catalog" :busy="busy" :error="error" :search-meta="importMeta" @cancel="editor=null;importMeta=null" @save="save" @next="nextImport" @catalog-change="load" @manage-tags="tagManager=true"/>
  <RecipeDetail v-if="detail" :key="detail.id" :recipe="detail" :done="done" :selected="selected.includes(detail.id)" @close="detail=null" @edit="edit" @remove="remove" @toggle="toggle"/>
  <TagManager v-if="tagManager" :catalog="catalog" @close="tagManager=false" @changed="load"/>
  <AiSetup v-if="aiSetup" @close="aiSetup=false" @saved="aiSetup=false;flash('AI 已启用，可以去导入页试试')"/>
  <AccountPanel v-if="accountOpen" :username="user.username" @close="accountOpen=false" @logout="signOut"/>
  <div v-if="pantryPick" class="overlay" @click.self="pantryPick=''"><section class="modal pantry-picker"><button class="close" @click="pantryPick=''" aria-label="关闭"><X/></button><span class="modal-icon"><Refrigerator :size="26"/></span><div class="eyebrow">KEEP TRACK</div><h2>{{pantryPick==='have'?'添加已有食材':'添加常备调料'}}</h2><form class="pantry-add" @submit.prevent="addFromPicker"><input v-model="pickName" :placeholder="pantryPick==='have'?'例如：番茄、鸡蛋':'例如：盐、黄油'"/><input v-model="pickAmount" class="pantry-amount" inputmode="decimal" placeholder="数量"/><select v-model="pickUnit" class="pantry-unit"><option value="">单位</option><option v-for="u in UNITS" :key="u" :value="u">{{u}}</option></select><button class="secondary" :disabled="!pickName.trim()"><Plus :size="15"/> 添加</button></form><p class="muted">可一次输入多个，用顿号、逗号或空格分隔；数量与单位会应用到这一批。</p><div class="pantry-block-head"><strong>{{pantryPick==='have'?'食谱里出现过的食材':'食谱里出现过的调料'}}</strong><span class="muted">{{pickerLibrary.length}} 项可点选</span></div><div class="chip-row picker-row"><button v-for="name in pickerLibrary" :key="name" type="button" class="picker-chip" :class="{picked:pickerList.some(i=>i.name===name)}" @click="pickItem(name)">{{name}}</button><span v-if="!pickerLibrary.length" class="muted">收藏几道食谱后，这里会出现可点选的内容。</span></div><div class="picker-current"><div class="pantry-block-head"><strong>已添加</strong><span class="muted">{{pickerList.length}} 种</span></div><div class="chip-row"><span v-for="(item,index) in pickerList" :key="item.name" class="pantry-chip">{{item.name}}<em v-if="item.amount||item.unit">{{item.amount}}{{item.unit}}</em><button type="button" @click="removePickerItem(index)" :aria-label="'移除'+item.name">×</button></span><span v-if="!pickerList.length" class="muted">还没有添加</span></div></div><button class="primary wide" @click="pantryPick=''">完成</button></section></div>
</div>
</template>
<style>
.import-modal{padding:32px 34px}
.import-modal .close{border:1.5px solid #93a583;background:#fff}
.import-modal form{margin-top:16px}
.import-modal textarea{min-height:56px}
.import-modal label small{font-size:11px;color:#98a08e;letter-spacing:0;line-height:1.6;margin-top:-3px}
.provider-picks{display:flex;flex-wrap:wrap;gap:8px;margin:16px 0 4px}
.provider-pick{display:inline-flex;align-items:center;gap:5px;padding:8px 14px;border:1px solid var(--border);border-radius:999px;background:#fff;font:inherit;font-size:12px;font-weight:600;color:#4d5745;cursor:pointer}
.provider-pick.picked{border-color:#5e7a4e;background:#f2f5e6;color:#3f5334}
.provider-hint{margin:8px 0 0;font-size:11px;color:#8b937f}
.ai-actions{display:flex;gap:10px;margin-top:14px}
.ai-actions .primary,.ai-actions .secondary{flex:1}
.ai-ok{margin:10px 0 0;font-size:12px;color:#5e7a4e;font-weight:600}
.pantry-run{display:flex;gap:12px;margin-top:6px}
.pantry-run button{flex:1;justify-content:center}
.ai-dishes{margin-top:18px;padding-top:16px;border-top:1px dashed #e3e7d8}
.ai-dishes-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:4px}
.ai-dish{display:flex;align-items:center;justify-content:space-between;gap:14px;margin-top:10px;padding:12px 14px;border:1px solid #e6eadb;border-radius:10px;background:#fbfcf6}
.ai-dish h3{margin:0;font-size:15px}
.ai-dish p{margin:4px 0 0;font-size:12px;line-height:1.6;color:#7c8571}
.ai-setup{padding:34px 36px;max-height:88vh;overflow:auto}
.ai-setup label{margin-top:12px}
.ai-later{display:block;margin:14px auto 0;font-size:12px}
.account-panel{padding:34px 36px;max-height:88vh;overflow:auto}
.account-block{margin-top:22px;padding-top:18px;border-top:1px solid #eceee5}
.account-block h3{display:flex;align-items:center;gap:8px;margin:0 0 6px;font-size:15px}
.account-block label{margin-top:10px}
.account-block .small{margin:0 0 10px;font-size:11px;color:#8b937f}
.danger-block h3{color:#a4442f}
.danger-outline{width:100%;margin-top:8px;padding:12px;border:1.5px solid #c96a52;border-radius:8px;background:#fff;color:#a4442f;font:inherit;font-size:13px;font-weight:600;cursor:pointer}
.danger-solid{flex:1;padding:12px;border:0;border-radius:8px;background:#b4543c;color:#fff;font:inherit;font-size:13px;font-weight:700;cursor:pointer}
.danger-solid:disabled{opacity:.45;cursor:not-allowed}
.top-right{display:flex;align-items:center;gap:18px}
.top-account{display:flex;align-items:center;gap:8px;font-size:11px;color:#5d6f5f}
.top-account i{display:inline-block;width:6px;height:6px;background:#73976b;border-radius:50%}
.profile{flex-wrap:wrap}
.auth-screen{min-height:100vh;display:grid;place-items:center;background:#f8f9f5}
.card-art.has-cover{background:#e9ece2}
.card-cover{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;z-index:1}
.card-art.has-cover .card-source{z-index:3}
.card-art.has-cover .select-recipe{z-index:4}
.detail-cover{height:210px;border-radius:10px;overflow:hidden;margin-bottom:24px;background:#edf0e3}
.detail-cover img{width:100%;height:100%;object-fit:cover;display:block}
@media(max-width:650px){.top-account{display:none}}
.import-search{margin-top:20px}
.pantry-form{display:grid;gap:14px}
.pantry-block{display:grid;gap:10px;padding:16px 18px;border:1px solid #c3cdae;border-radius:14px;background:#f2f5e6}
.pantry-block-head strong{font-size:13px;color:#3f4735}
.pantry-actions{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:6px}
.pantry-actions button{display:inline-flex;align-items:center;justify-content:center;gap:9px;margin:0;padding:16px 20px;font-size:14px;font-weight:600;border:1.5px solid #8a9a74;border-radius:12px;background:#fff;color:#3f4735;box-shadow:0 1px 3px rgba(76,83,58,.08)}
.pantry-actions button:hover{background:#eef2e3;border-color:#6f7f59}
@media(max-width:650px){.pantry-actions{grid-template-columns:1fr}}
.pantry-block-head{display:flex;align-items:baseline;justify-content:space-between;gap:12px}
.pantry-block-head .muted{font-size:11px;margin:0}
.picker-row{max-height:220px;overflow:auto;padding:12px;border:1px solid #c3cdae;border-radius:12px;background:#f2f5e6}
.picker-chip{border:1px solid #dfe4d5;background:#fff;border-radius:999px;padding:6px 12px;font-size:12px;cursor:pointer;color:#4c5340}
.picker-chip:hover{border-color:#9aa88a}
.picker-chip.picked{background:#eef2e3;border-color:#9aa88a;color:#6b7a52}
.picker-current{display:grid;gap:10px;margin-top:16px;padding-top:14px;border-top:1px dashed #e2e6d8}
.pantry-picker{max-height:86vh;overflow:auto}
.pantry-add{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.today-card{margin-top:22px;padding:26px 30px;background:#fff;border:1px solid var(--border);border-radius:12px}
.today-head{display:flex;align-items:flex-end;justify-content:space-between;gap:14px;margin-bottom:14px}
.today-head h2{margin:4px 0 0;font-size:24px}
.today-progress{margin:12px 0 0;font-size:12px;color:#5e7a4e;font-weight:600}
.today-actions{display:flex;align-items:center;gap:16px;margin-top:18px;flex-wrap:wrap}
@media (max-width:650px){.today-card{padding:20px 18px}}
.cook-finish{display:flex;align-items:center;gap:8px;margin:18px 0 0;font-size:13px;color:#5e7a4e;font-weight:600}
.empty-actions{display:flex;gap:12px;justify-content:center;flex-wrap:wrap;margin-top:20px}
.empty-panel .empty-actions .primary{margin-top:0}
.today-footer{margin-top:22px;padding-top:18px;border-top:1px solid var(--border)}
.today-footer .muted{margin:0 0 4px}
.today-footer-actions{display:flex;gap:10px;margin-top:12px;flex-wrap:wrap}
.today-footer-actions .primary{flex:1;min-width:140px;margin-top:0;justify-content:center}
.today-footer-actions .primary:disabled{opacity:.45;cursor:not-allowed}
.heading-actions{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.pantry-have{display:grid;gap:10px;margin-top:18px;padding:16px 18px;border:1px dashed #c3cdae;border-radius:12px;background:#f2f5e6}
.pantry-have strong{font-size:12px;color:#5e6d4c}
.pantry-note{margin:4px 0 0;font-size:12px;color:#7a8468}
.shopping-foot{display:flex;align-items:center;gap:10px;margin-top:16px;flex-wrap:wrap}
.shopping-foot .primary{flex:1;min-width:150px;margin-top:0;justify-content:center}
.shopping-foot .primary:disabled{opacity:.45;cursor:not-allowed}
.shopping-foot .muted{margin:0}
.bar-tab{position:fixed;left:260px;bottom:24px;z-index:40;display:flex;align-items:center;gap:7px;padding:11px 15px;border:none;border-radius:999px;background:var(--green);color:#fff;font-size:14px;font-weight:600;cursor:pointer;box-shadow:0 10px 24px rgba(46,61,38,.28)}
.bar-tab:hover{transform:translateY(-1px)}
.bar-tab span{display:inline-flex;min-width:18px;align-items:center;justify-content:center;font-variant-numeric:tabular-nums}
.selection-preview{position:fixed;left:calc(50% + 118px);bottom:88px;transform:translateX(-50%);z-index:21;background:#fff;border:2px solid #8fa676;border-radius:12px;box-shadow:0 14px 44px rgba(46,61,38,.22);padding:14px 18px;width:min(440px,calc(100vw - 48px));display:grid;gap:10px}
.preview-head{display:flex;align-items:center;justify-content:space-between;gap:12px}
.preview-head strong{font-size:13px;color:#41523c}
.preview-head-actions{display:flex;align-items:center;gap:12px}
.danger-text{color:#8c3f34}
.danger-text:hover{color:#6f3128}
.tab-pop-enter-active,.tab-pop-leave-active{transition:opacity .2s ease,transform .2s ease}
.tab-pop-enter-from,.tab-pop-leave-to{opacity:0;transform:translateY(10px) scale(.85)}
.bar-collapse-enter-active,.bar-collapse-leave-active{transition:opacity .18s ease,transform .18s ease}
.bar-collapse-enter-from,.bar-collapse-leave-to{opacity:0;transform:translateX(-50%) translateY(12px) scale(.94)}
.fade-up-enter-active,.fade-up-leave-active{transition:opacity .16s ease,transform .16s ease}
.fade-up-enter-from,.fade-up-leave-to{opacity:0;transform:translateX(-50%) translateY(8px)}
@media(max-width:1150px){.bar-tab{left:224px}.selection-preview{left:calc(50% + 100px)}}
@media(max-width:650px){.bar-tab{left:18px;bottom:18px}}
.recipe-card.picked{outline:2px solid var(--green);outline-offset:-2px}
.selection-bar .danger-button{background:#8c3f34;color:#fff;border:none;border-radius:999px;padding:10px 18px;font-size:13px;font-weight:600;cursor:pointer}
.selection-bar .danger-button:disabled{opacity:.45;cursor:not-allowed}
.pantry-add input{flex:1;min-width:170px;margin:0}
.pantry-add .pantry-amount{flex:none;width:76px;min-width:0}
.pantry-add .pantry-unit{flex:none;width:78px;margin:0;padding:10px 8px;border:1px solid #dfe4d5;border-radius:8px;background:#fff;font-size:13px;color:#4c5340}
.pantry-add button{flex:none;display:inline-flex;align-items:center;gap:6px;margin:0}
.chip-row{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.pantry-chip{display:inline-flex;align-items:center;gap:6px;padding:6px 10px;border:1px solid #dfe4d5;border-radius:999px;background:#f7f8f2;font-size:12px}
.pantry-chip em{font-style:normal;color:#6b7a52;font-size:11px}
.pantry-chip button{border:0;background:none;padding:0;cursor:pointer;color:#8a9078;font-size:14px;line-height:1}
.pantry-chip button:hover{color:#b4552f}
</style>

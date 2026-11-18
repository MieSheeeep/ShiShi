<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { Plus, Search, Refrigerator, Pencil, Check, Trash2, RotateCcw, ArrowRight, X, SlidersHorizontal } from 'lucide-vue-next'
import { api } from '../recipeEditing'
import { UNITS, isCondiment } from '../pantry'
import { inventorySettings } from '../fridgeState'
const props=defineProps({selected:Array,initialView:String,recipes:Array})
const emit=defineEmits(['detail','select','change'])
const stock=ref({categories:[],items:[]}),ready=ref(false),busy=ref(false),error=ref(''),query=ref(''),category=ref(''),location=ref(''),status=ref('active')
const view=ref(props.initialView||'inventory'),stockPage=ref(1),matchPage=ref(1),PAGE_SIZE=6
const editing=ref(null),managing=ref(false),newCategory=ref(''),renames=ref({}),deleting=ref(''),categoryDelete=ref('')
const matches=ref([]),matched=ref(false),matching=ref(false)
const settings=computed(()=>inventorySettings(stock.value.items))
const suggestions=computed(()=>[...new Set((props.recipes||[]).flatMap(r=>r.ingredients.map(i=>i.name)))].sort())
const locations=['冷藏','冷冻','常温']
const active=computed(()=>stock.value.items.filter(i=>i.status==='active'))
const used=computed(()=>stock.value.items.filter(i=>i.status==='used').length)
const rows=computed(()=>stock.value.items.filter(i=>(!category.value||i.category_id===category.value)&&(!location.value||i.location===location.value)&&i.status===status.value&&(i.name+i.notes).includes(query.value.trim())))
const categoryName=id=>stock.value.categories.find(c=>c.id===id)?.name||'未分类'
async function load(){
  stock.value=await api('/fridge')
  emit('change',settings.value)
  if(category.value&&!stock.value.categories.some(c=>c.id===category.value))category.value=''
}
onMounted(async()=>{try{await load();ready.value=true;if(view.value==='match'&&active.value.length)await findRecipes()}catch(e){error.value=e.message}})
async function perform(path,method,body){
  if(busy.value||matching.value)return false
  busy.value=true;error.value=''
  try{await api(path,method,body);await load();matched.value=false;deleting.value='';categoryDelete.value='';return true}
  catch(e){error.value=e.message;return false}finally{busy.value=false}
}
async function edit(item){
  editing.value=item?{...item}:{name:'',amount:'',unit:'',kind:'食材',category_id:category.value||stock.value.categories.find(c=>c.name==='其他')?.id||stock.value.categories[0]?.id,location:location.value||'冷藏',status:'active',notes:''}
  error.value='';await nextTick();document.querySelector('#fridge-food-name')?.focus()
}
function classify(){
  if(!editing.value.id&&isCondiment(editing.value.name)){
    editing.value.kind='调料';editing.value.location='常温'
    editing.value.category_id=stock.value.categories.find(c=>c.name==='调料')?.id||editing.value.category_id
  }
}
async function save(){const item=editing.value;if(await perform('/fridge/items'+(item.id?'/'+item.id:''),item.id?'PUT':'POST',item)){editing.value=null;if(!item.id)stockPage.value=1}}
async function addCategory(){if(await perform('/fridge/categories','POST',{name:newCategory.value.trim()}))newCategory.value=''}
async function findRecipes(){
  if(matching.value||busy.value||!active.value.length)return
  matching.value=true;error.value=''
  try{
    matches.value=await api('/match','POST',settings.value);matched.value=true
  }catch(e){error.value=e.message}finally{matching.value=false}
}

const visibleRows=computed(()=>rows.value.slice((stockPage.value-1)*PAGE_SIZE,stockPage.value*PAGE_SIZE))
const stockPages=computed(()=>Math.max(1,Math.ceil(rows.value.length/PAGE_SIZE)))
const visibleMatches=computed(()=>matches.value.slice((matchPage.value-1)*PAGE_SIZE,matchPage.value*PAGE_SIZE))
const matchPages=computed(()=>Math.max(1,Math.ceil(matches.value.length/PAGE_SIZE)))
watch([query,category,location,status],()=>{stockPage.value=1})
watch(stockPages,n=>{stockPage.value=Math.min(stockPage.value,n)})
watch(matches,()=>{matchPage.value=1})
watch(view,()=>window.scrollTo({top:0}))
function openMatching(){view.value='match';findRecipes()}
function openCategories(){error.value='';managing.value=true}
const dialogOpen=computed(()=>!!editing.value||managing.value)
let priorFocus,priorOverflow
function closeDialog(){if(!busy.value){editing.value=null;managing.value=false;error.value=''}}
function dialogKeys(event){
  if(!dialogOpen.value)return
  if(event.key==='Escape'){event.preventDefault();closeDialog()}
  if(event.key==='Tab'){
    const controls=[...document.querySelectorAll('.fridge-dialog input,.fridge-dialog select,.fridge-dialog button:not(:disabled)')].filter(el=>el.getClientRects().length)
    const first=controls[0],last=controls.at(-1)
    if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus()}
    else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus()}
  }
}
watch(dialogOpen,async open=>{
  if(open){priorFocus=document.activeElement;priorOverflow=document.body.style.overflow;document.body.style.overflow='hidden';await nextTick();document.querySelector('.fridge-dialog input')?.focus()}
  else{document.body.style.overflow=priorOverflow??'';await nextTick();if(priorFocus?.isConnected)priorFocus.focus()}
})
onMounted(()=>document.addEventListener('keydown',dialogKeys))
onBeforeUnmount(()=>{document.removeEventListener('keydown',dialogKeys);if(dialogOpen.value)document.body.style.overflow=priorOverflow??''})
</script>
<template>
<div class="fridge-page">
  <section class="page-heading"><div><div class="eyebrow">KEEP A LITTLE FRESHNESS</div><h1>{{view==='inventory'?'我的冰箱':'按库存找菜'}}<span class="title-dot">。</span></h1><p>{{view==='inventory'?'管理食品，留住新鲜。':'从现有食材出发，安排下一餐。'}}</p></div><button v-if="view==='inventory'" class="primary" :disabled="!ready||busy" @click="edit()"><Plus :size="17"/>添加食品</button><button v-else class="secondary" @click="view='inventory'">返回冰箱</button></section>
  <div class="fridge-view-nav" aria-label="冰箱功能"><button :aria-pressed="view==='inventory'" :class="{chosen:view==='inventory'}" @click="view='inventory'"><Refrigerator :size="16"/>库存管理</button><button :aria-pressed="view==='match'" :class="{chosen:view==='match'}" @click="view='match'"><Search :size="16"/>库存找菜</button></div>
  <p v-if="!ready" class="muted" role="status">正在打开冰箱…</p>
  <p v-if="error&&!dialogOpen" class="alert" role="alert">{{error}}</p>
  <template v-if="ready">
    <template v-if="view==='inventory'">
<section class="fridge-summary"><div><Refrigerator :size="26" stroke-width="1.4"/><span><strong>{{active.length}}</strong> 项在库食品<small>冷藏 {{active.filter(i=>i.location==='冷藏').length}} · 冷冻 {{active.filter(i=>i.location==='冷冻').length}} · 常温 {{active.filter(i=>i.location==='常温').length}}</small></span></div><button class="secondary" :disabled="!active.length||matching" @click="openMatching">{{matching?'正在找菜…':'用库存找菜'}}<ArrowRight :size="15"/></button></section>
<div class="fridge-toolbar"><div class="fridge-tabs"><button :class="{chosen:status==='active'}" @click="status='active'">在库 {{active.length}}</button><button :class="{chosen:status==='used'}" @click="status='used'">已用完 {{used}}</button></div><button class="text-button" @click="openCategories"><SlidersHorizontal :size="15"/>管理分类</button></div>

<div class="fridge-filters"><label class="search"><Search :size="16"/><input v-model="query" placeholder="搜索食品或备注" aria-label="搜索冰箱食品"/></label><select v-model="location" aria-label="按存放位置筛选"><option value="">全部位置</option><option v-for="place in locations" :key="place">{{place}}</option></select></div>
    <div class="fridge-category-pills"><button :class="{chosen:!category}" @click="category=''">全部分类</button><button v-for="c in stock.categories" :key="c.id" :class="{chosen:category===c.id}" @click="category=c.id">{{c.name}}</button></div>
    <div class="fridge-food-grid"><article v-for="item in visibleRows" :key="item.id" class="fridge-food" :class="{'food-used':item.status==='used'}"><div class="fridge-food-top"><span>{{categoryName(item.category_id)}} · {{item.kind}}</span><span>{{item.location}}</span></div><h3>{{item.name}}</h3><p class="fridge-quantity">{{item.amount||item.unit?item.amount+item.unit:'数量未填写'}}</p><p class="fridge-food-note">{{item.notes||'留好食材，慢慢做饭。'}}</p><div class="fridge-food-actions"><button class="text-button" :disabled="busy" :aria-label="'编辑食品'+item.name" @click="edit(item)"><Pencil :size="13"/>编辑</button><button class="text-button" :disabled="busy" @click="perform('/fridge/items/'+item.id,'PUT',{...item,status:item.status==='used'?'active':'used'})"><RotateCcw v-if="item.status==='used'" :size="13"/><Check v-else :size="13"/>{{item.status==='used'?'恢复在库':'标记用完'}}</button><button class="icon-button danger" :disabled="busy" :aria-label="'删除食品'+item.name" @click="deleting=deleting===item.id?'':item.id"><Trash2 :size="14"/></button></div><div v-if="deleting===item.id" class="fridge-confirm"><span>删除这条食品记录？</span><button :disabled="busy" @click="perform('/fridge/items/'+item.id,'DELETE')">确定</button><button :disabled="busy" @click="deleting=''">取消</button></div></article></div>
    <div v-if="!rows.length" class="fridge-empty"><Refrigerator :size="33" stroke-width="1"/><h3>{{status==='used'?'还没有已用完的记录':stock.items.length?'没有符合筛选的食品':'给冰箱添一点新鲜'}}</h3><p>{{stock.items.length?'试试其他分类、位置或搜索词。':'记下食品名称，数量和备注可以之后再补。'}}</p><button v-if="!stock.items.length" class="secondary" @click="edit()"><Plus :size="15"/>录入第一份食品</button></div>

<div v-if="stockPages>1" class="fridge-pagination"><button class="secondary" :disabled="stockPage===1" @click="stockPage--">上一页</button><span>{{stockPage}} / {{stockPages}} 页 · 共 {{rows.length}} 项</span><button class="secondary" :disabled="stockPage===stockPages" @click="stockPage++">下一页</button></div>
    </template>
    <template v-else>
      <slot name="suggestions"/><div class="fridge-stock-preview"><span>当前在库 · {{active.length}} 项</span><p>{{active.map(item=>item.name).filter((name,index,all)=>all.indexOf(name)===index).slice(0,8).join('、')||'还没有在库食品'}}{{active.length>8?' …':''}}</p><button v-if="!active.length" class="text-button" @click="view='inventory';edit()">先添加食品</button></div>
<section class="fridge-match"><div class="fridge-section-title"><h2>今晚，用这些做点什么？</h2><span class="muted">使用全部在库食材</span></div><div class="fridge-match-controls"><p class="muted">{{settings.ingredients.length}} 项食材 · {{settings.staples.length}} 项调料</p><button class="primary" :disabled="matching||!active.length||busy" @click="findRecipes"><Search :size="16"/>{{matching?'正在找菜…':'找找能做什么'}}</button></div><p class="muted">已用完的食品不参与匹配；匹配比较食材种类；采购清单沿用现有数量和单位计算差额，无法比较的用量需手动核对。</p><div v-if="!matched" class="fridge-match-intro"><p>使用在库的 {{active.length}} 项食品与常备调料，从收藏中找下一餐。</p></div><div v-if="matched" class="match-list"><div v-for="recipe in visibleMatches" :key="recipe.id" class="match-item"><span class="match-emoji">{{recipe.emoji||'🍲'}}</span><div class="clickable" @click="emit('detail',recipe)"><h3>{{recipe.name}}</h3><p :class="{available:!recipe.missing.length}">{{recipe.missing.length?'还缺：'+recipe.missing.join('、'):'食材种类已齐全，可以开做！'}}</p></div><button class="secondary" @click="emit('select',recipe.id)">{{selected.includes(recipe.id)?'已选中':'选入菜单'}}</button></div><p v-if="!matches.length" class="muted">先去首页收藏几道食谱，再用库存找菜。</p></div></section><div v-if="matched&&matchPages>1" class="fridge-pagination"><button class="secondary" :disabled="matchPage===1" @click="matchPage--">上一页</button><span>{{matchPage}} / {{matchPages}} 页 · 共 {{matches.length}} 道</span><button class="secondary" :disabled="matchPage===matchPages" @click="matchPage++">下一页</button></div>
    </template>
  </template>
  <Teleport to="body"><div v-if="dialogOpen" class="overlay fridge-dialog-overlay" @click.self="closeDialog"><section class="modal fridge-dialog" role="dialog" aria-modal="true" aria-labelledby="fridge-dialog-title"><p v-if="error" class="alert" role="alert">{{error}}</p>
<form v-if="editing" class="fridge-editor" @submit.prevent="save">
      <div class="fridge-section-title"><h2 id="fridge-dialog-title">{{editing.id?'编辑食品':'放进冰箱'}}</h2><button type="button" class="text-button" :disabled="busy" @click="closeDialog"><X :size="15"/>取消</button></div>
      <div class="fridge-form-grid"><label>食品名称 <span>必填</span><input id="fridge-food-name" v-model="editing.name" required maxlength="100" list="fridge-ingredient-suggestions" placeholder="例如：鸡蛋、西兰花" @change="classify"/><datalist id="fridge-ingredient-suggestions"><option v-for="name in suggestions" :key="name" :value="name"/></datalist></label><label>数量 / 余量<input v-model="editing.amount" maxlength="100" placeholder="例如：6、半、200"/></label><label>单位<select v-model="editing.unit"><option value="">未填写</option><option v-if="editing.unit&&!UNITS.includes(editing.unit)" :value="editing.unit">{{editing.unit}}</option><option v-for="unit in UNITS" :key="unit" :value="unit">{{unit}}</option></select></label><label>用途<select v-model="editing.kind"><option>食材</option><option>调料</option></select></label><label>食品分类<select v-model="editing.category_id" required><option v-for="c in stock.categories" :key="c.id" :value="c.id">{{c.name}}</option></select></label><label>存放位置<select v-model="editing.location"><option v-for="place in locations" :key="place">{{place}}</option></select></label><label class="fridge-notes">备注<input v-model="editing.notes" maxlength="1000" placeholder="可选，例如：周末做饼干用"/></label></div>
      <div class="fridge-form-footer"><span class="muted">同一种食品可以分条记录，数量留空也能保存。</span><button class="primary" :disabled="busy">{{busy?'正在保存…':'保存食品'}}<Check :size="16"/></button></div>
    </form>
<section v-if="managing" class="fridge-categories"><div class="fridge-section-title"><h2 id="fridge-dialog-title">食品分类</h2><button type="button" class="text-button" :disabled="busy" @click="closeDialog">关闭</button></div><p class="muted">分类名称由你定义。改名会同步显示，删除前请先移走其中的食品。</p><div class="fridge-category-grid"><div v-for="c in stock.categories" :key="c.id" class="fridge-category-row"><input :value="renames[c.id]??c.name" maxlength="40" :aria-label="'分类名称'+c.name" @input="renames[c.id]=$event.target.value"/><button class="icon-button" :disabled="busy" :aria-label="'保存分类'+c.name" @click="perform('/fridge/categories/'+c.id,'PATCH',{name:renames[c.id]??c.name})"><Check :size="16"/></button><button class="icon-button danger" :disabled="busy" :aria-label="'删除分类'+c.name" @click="categoryDelete=categoryDelete===c.id?'':c.id"><Trash2 :size="15"/></button><div v-if="categoryDelete===c.id" class="fridge-confirm"><span>删除“{{c.name}}”分类？</span><button :disabled="busy" @click="perform('/fridge/categories/'+c.id,'DELETE')">确定</button><button :disabled="busy" @click="categoryDelete=''">取消</button></div></div></div><form class="fridge-new-category" @submit.prevent="addCategory"><input v-model="newCategory" required maxlength="40" aria-label="新分类名称" placeholder="例如：烘焙材料、速冻食品"/><button class="secondary" :disabled="busy||!newCategory.trim()"><Plus :size="15"/>新建分类</button></form></section>
  </section></div></Teleport>
</div>
</template>

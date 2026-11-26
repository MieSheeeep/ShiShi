import { defaultMealSlot } from './mealSlots.js'
import { COOKING_LEVELS } from './cookingLevels.js'

export const effectiveDishes = record => (record?.dishes || []).filter(d => ['success','practice'].includes(d.outcome))
export const recordPhoto = record => effectiveDishes(record).flatMap(d=>d.photos || [])[0] || ''
export function previousAttempt(records,key,currentId) {
  const attempts=sameDishAttempts(records,key),current=attempts.findIndex(r=>r.id===currentId)
  const record=(current>=0?attempts.slice(0,current):attempts).at(-1)
  return record?{record,dish:effectiveDishes(record).find(d=>d.dish_key===key)}:null
}
export function groupMonths(records) {
  const groups = new Map()
  for (const record of records) { const month=record.cooked_on.slice(0,7); if(!groups.has(month))groups.set(month,[]);groups.get(month).push(record) }
  return [...groups].sort(([a],[b])=>b.localeCompare(a)).map(([month,items])=>({month,items}))
}
export const sameDishAttempts = (records,key) => records.filter(r=>r.state==='completed'&&effectiveDishes(r).some(d=>d.dish_key===key)).sort((a,b)=>a.cooked_on.localeCompare(b.cooked_on)||a.id-b.id)
export function buildCalendarMonth(yearMonth, records = [], today = '') {
  const [y, m] = yearMonth.split('-').map(Number)
  const firstDay = new Date(Date.UTC(y, m - 1, 1))
  const startOffset = (firstDay.getUTCDay() + 6) % 7
  const daysInMonth = new Date(Date.UTC(y, m, 0)).getUTCDate()
  const byDate = new Map()
  for (const record of records) {
    if (!record?.cooked_on?.startsWith(yearMonth)) continue
    if (!byDate.has(record.cooked_on)) byDate.set(record.cooked_on, [])
    byDate.get(record.cooked_on).push(record)
  }
  const cells = []
  for (let i = 0; i < startOffset; i++) cells.push({ date: '', day: 0, inMonth: false, isToday: false, records: [], photo: '' })
  for (let day = 1; day <= daysInMonth; day++) {
    const date = `${yearMonth}-${String(day).padStart(2, '0')}`
    const dayRecords = byDate.get(date) || []
    const photo = dayRecords.map(recordPhoto).find(Boolean) || ''
    cells.push({ date, day, inMonth: true, isToday: date === today, records: dayRecords, photo })
  }
  while (cells.length % 7 !== 0) cells.push({ date: '', day: 0, inMonth: false, isToday: false, records: [], photo: '' })
  return { year: y, month: m, yearMonth, label: `${y} 年 ${m} 月`, cookedDays: byDate.size, totalMeals: [...byDate.values()].reduce((s, a) => s + a.length, 0), cells }
}
export function buildChallenges(summary = {}, context = {}) {
  const meals = summary.meals || 0
  const dishes = summary.dishes || 0
  const repertoire = summary.repertoire || []
  const byId = new Map((summary.achievements || []).map(a => [a.id, a]))
  const practiceDish = repertoire.find(d => d.status === 'practice') || repertoire.find(d => d.attempts > d.successes) || null
  const bestDish = [...repertoire].sort((a, b) => b.successes - a.successes || b.attempts - a.attempts)[0] || null
  const ach = id => byId.get(id) || { id, unlocked: false, session_id: null, unlocked_at: null }
  const first = ach('first-fire'), retry = ach('try-again'), three = ach('three-dishes'), sig = ach('signature-dish')
  return [
    {
      id: 'first-fire', tag: '新手启程', title: '第一次开火',
      description: '从菜谱库选一道喜欢的菜，亲手完成并留下第一餐记录。',
      progress: Math.min(meals, 1), target: 1, progressText: `${Math.min(meals, 1)} / 1 餐`,
      unlocked: first.unlocked, sessionId: first.session_id, unlockedAt: first.unlocked_at,
      actionType: 'browse', actionLabel: '去首页选一道菜'
    },
    {
      id: 'try-again', tag: '复盘进阶', title: '不服输 · 再试一次',
      description: practiceDish ? `带着上次的心得，再挑战一次「${practiceDish.name}」。` : '把一道之前标为「还想再练」的菜再做一次，看看这次的进步。',
      progress: retry.unlocked ? 1 : 0, target: 1, progressText: retry.unlocked ? '已达成' : (practiceDish ? `待再练：${practiceDish.name}` : '待触发'),
      unlocked: retry.unlocked, sessionId: retry.session_id, unlockedAt: retry.unlocked_at,
      actionType: practiceDish ? 'dish' : 'browse', dishKey: practiceDish?.dish_key || '', actionLabel: practiceDish ? `再做「${practiceDish.name}」` : '去选菜试做'
    },
    {
      id: 'three-dishes', tag: '丰富菜单', title: '解锁三道家常菜',
      description: '尝试 3 种不同的菜品，慢慢拼出属于自己的日常菜单。',
      progress: Math.min(dishes, 3), target: 3, progressText: `${Math.min(dishes, 3)} / 3 道菜`,
      unlocked: three.unlocked, sessionId: three.session_id, unlockedAt: three.unlocked_at,
      actionType: 'browse', actionLabel: '去菜谱库挑新菜'
    },
    {
      id: 'signature-dish', tag: '熟能生巧', title: '练成一道拿手菜',
      description: bestDish && !sig.unlocked ? `「${bestDish.name}」已做成 ${bestDish.successes} 次，做成 3 次就能收进拿手菜印章。` : '把同一道菜在 3 餐中稳定做成，它就真正成了你的拿手菜。',
      progress: sig.unlocked ? 3 : Math.min(bestDish?.successes || 0, 3), target: 3,
      progressText: sig.unlocked ? '3 / 3 次' : `${Math.min(bestDish?.successes || 0, 3)} / 3 次`,
      unlocked: sig.unlocked, sessionId: sig.session_id, unlockedAt: sig.unlocked_at,
      actionType: bestDish ? 'dish' : 'browse', dishKey: bestDish?.dish_key || '', actionLabel: bestDish ? `再练「${bestDish.name}」` : '去选菜开始'
    },
    {
      id: 'pantry-quest', tag: '随时可玩', title: '冰箱清库存实战',
      description: context.pantryCount ? `冰箱里现在有 ${context.pantryCount} 样食材，看看能凑出什么好菜。` : '登记手边现有的食材，按食材搜菜并现做一顿。',
      progress: context.pantryCount ? 1 : 0, target: 1, progressText: context.pantryCount ? `已有 ${context.pantryCount} 样食材` : '去登记食材',
      unlocked: false, sessionId: null, unlockedAt: null, repeatable: true,
      actionType: 'pantry', actionLabel: '去按食材搜菜'
    }
  ]
}

export const KITCHEN_CHAPTERS = [
  {
    id: 'ch-1', number: 1, title: '初试灶火', subtitle: '10 分钟零门槛上手', badge: '灶台萌新',
    stages: [
      { id: 's-1', name: '番茄炒蛋', emoji: '🍅', minutes: 15, difficulty: 1, tip: '蛋液刚凝固就先盛出，最后回锅才够嫩滑。' },
      { id: 's-2', name: '葱花鸡蛋饼', emoji: '🥞', minutes: 10, difficulty: 1, tip: '面糊调到能顺滑流下，小火摊平更不易糊。' },
      { id: 's-3', name: '清爽黄瓜拌豆腐', emoji: '🥒', minutes: 10, difficulty: 1, tip: '豆腐沸水焯 30 秒去豆腥，放凉再拌更爽口。' }
    ]
  },
  {
    id: 'ch-2', number: 2, title: '火候试炼', subtitle: '掌握煎、炒与焯水节奏', badge: '火候学徒',
    stages: [
      { id: 's-4', name: '香煎土豆', emoji: '🥔', minutes: 25, difficulty: 2, tip: '先煮到筷子能穿透，沥干小火慢煎才外脆里糯。' },
      { id: 's-5', name: '蒜蓉西兰花', emoji: '🥦', minutes: 15, difficulty: 2, tip: '沸水加几滴油焯 1 分钟捞出，翠绿不发黄。' },
      { id: 's-6', name: '蒜香煎鸡胸', emoji: '🍗', minutes: 20, difficulty: 2, tip: '鸡胸划浅花刀腌 10 分钟，中小火每面煎 2 分钟。' }
    ]
  },
  {
    id: 'ch-3', number: 3, title: '慢火治愈', subtitle: '煮粥、焖炖与收汁功夫', badge: '烟火掌勺',
    stages: [
      { id: 's-7', name: '南瓜小米粥', emoji: '🥣', minutes: 35, difficulty: 2, tip: '水开后再下小米，转小火时不时搅底防粘锅。' },
      { id: 's-8', name: '可乐鸡翅', emoji: '🍖', minutes: 30, difficulty: 3, tip: '鸡翅煎至两面微焦再倒可乐，最后大火收汁发亮。' },
      { id: 's-9', name: '番茄炖牛腩', emoji: '🍲', minutes: 60, difficulty: 3, tip: '番茄先炒出浓汁，小火慢炖 50 分钟肉才软烂。' }
    ]
  }
]

export const BLIND_BOX_TWISTS = [
  '过程中随手拍 1 张灶台照',
  '出锅后给成品拍张俯拍大片',
  '留一句火候心得给下次的自己',
  '试着把台面顺手收拾干净再开吃',
  '挑战按步骤一口气做完不慌张'
]

export function buildChapterMap(summary = {}, recipes = []) {
  const repertoire = summary.repertoire || []
  const byName = new Map(repertoire.map(d => [d.name, d]))
  const recipeByName = new Map((recipes || []).map(r => [r.name, r]))
  let totalCleared = 0
  let totalStages = 0
  const chapters = KITCHEN_CHAPTERS.map(ch => {
    const stages = ch.stages.map(stage => {
      totalStages++
      const rep = byName.get(stage.name) || null
      const recipe = recipeByName.get(stage.name) || null
      const state = rep ? (rep.successes > 0 ? 'cleared' : 'revenge') : 'ready'
      if (state === 'cleared') totalCleared++
      return {
        ...stage,
        state,
        attempts: rep?.attempts || 0,
        successes: rep?.successes || 0,
        lastSessionId: rep?.sessions?.at(-1) || null,
        dishKey: rep?.dish_key || '',
        recipeId: recipe?.id || null,
        cover: recipe?.cover || ''
      }
    })
    const clearedCount = stages.filter(s => s.state === 'cleared').length
    return { ...ch, stages, clearedCount, completed: clearedCount === stages.length }
  })
  return { chapters, totalCleared, totalStages }
}

export function pickBlindBox(recipes = [], summary = {}, seed = Math.random()) {
  const map = buildChapterMap(summary, recipes)
  const pool = map.chapters.flatMap(c => c.stages).filter(s => s.state !== 'cleared')
  const fallback = map.chapters.flatMap(c => c.stages)
  const candidates = pool.length ? pool : fallback
  const idx = Math.floor(seed * candidates.length) % candidates.length
  const twistIdx = Math.floor(seed * 97) % BLIND_BOX_TWISTS.length
  const pick = candidates[idx]
  return { ...pick, twist: BLIND_BOX_TWISTS[twistIdx] }
}

export function buildCelebration(record, summary = {}, options = {}) {
  const dishes = effectiveDishes(record)
  const hasSuccess = dishes.some(d => d.outcome === 'success')
  const hasPhoto = Boolean(recordPhoto(record))
  const hour = options.hour ?? new Date().getHours()
  if (options.wasRevenge && hasSuccess) {
    return { badge: '复仇成功', headline: '上次的遗憾，今天一锅翻盘！', subline: '同一道菜敢再战一次还做成了，手艺肉眼可见在涨。' }
  }
  if ((summary.meals || 0) <= 1) {
    return { badge: '初次开火', headline: '第一把火点亮了！', subline: '从这一餐开始，你的个人厨房档案正式开张。' }
  }
  if (!hasSuccess) {
    return { badge: '认真修炼中', headline: '敢下锅，就已经赢过一半人。', subline: '这次的火候和咸淡都记下来了，下次一定更顺手。' }
  }
  if (hour >= 21 || hour < 5) {
    return { badge: '深夜食堂掌勺人', headline: '夜深了，热乎的一餐最治愈。', subline: '愿意在这么晚还认真喂饱自己，你已经很厉害了。' }
  }
  if (hasPhoto) {
    return { badge: '色香味认证', headline: '出锅大吉，这张成品太有烟火气了！', subline: `累计已留下 ${summary.meals || 1} 餐，每一张照片都是好手艺的证据。` }
  }
  const pool = [
    { badge: '完美出锅', headline: '今天的灶台，被你拿捏住了！', subline: `这是你的第 ${summary.meals || 1} 餐，离拿手大厨又近一步。` },
    { badge: '烟火满分', headline: '热气腾腾，开饭！', subline: '自己亲手做出来的味道，怎么吃都比外卖香。' },
    { badge: '稳稳拿下', headline: '火候刚好，功力见长！', subline: `已经尝试过 ${summary.dishes || dishes.length} 道不同的菜了，继续解锁下一道。` }
  ]
  return pool[(record?.id || 0) % pool.length]
}
const copy = value => JSON.parse(JSON.stringify(value))
const blankSummary = () => ({meals:0,dishes:0,level:{number:1,title:'初入厨房',remaining:1,next_at:1},achievements:[],repertoire:[]})
const initial = () => ({accountId:null,draft:null,drafts:[],records:[],total:0,page:1,summary:blankSummary(),loading:false,saving:false,finalizing:false,uploading:0,error:'',conflict:null,lastCompleted:null,recentRecord:null,feedback:null,mealSlot:defaultMealSlot()})
const mergePatch = (a,b) => ({...a,...b,...((a?.dishes||b.dishes)?{dishes:[...new Map([...(a?.dishes||[]),...(b.dishes||[])].map(d=>[d.id,{...(a?.dishes||[]).find(x=>x.id===d.id),...d}])).values()]}:{})})
const applyLocal = (record,patch) => {for(const [key,value] of Object.entries(patch)){if(key==='dishes'){for(const d of value){const target=record.dishes.find(x=>x.id===d.id);if(target)Object.assign(target,copy(d))}}else record[key]=copy(value)}}

// 收尾时的即时反馈：本餐加了几星、是否升段、还差几餐到下一段。
export function levelFeedback(before, after, meals = 0) {
  if (!before || !after) return null
  const levelUp = (after.number || 1) > (before.number || 1)
  const next = COOKING_LEVELS.find(level => level.minMeals > meals) || null
  return {
    meals, title: after.title, star: after.star || 1, tier: after.tier,
    starGained: levelUp ? 0 : Math.max(0, (after.star || 1) - (before.star || 1)),
    levelUp: levelUp ? { from: before.title, to: after.title } : null,
    nextTitle: next?.title || null,
    remaining: after.remaining || 0
  }
}

// Transport injection lets the same queue run in Vue and in independent Node tests.
export function createJournal(request, reactive = value=>value) {
  const state=reactive(initial())
  let epoch=0,queue=Promise.resolve(),completing=null,starting=null,pendingStart=null,filter={page:1,state:'completed'},listEpoch=0
  const cache=new Map(),versions=new Map(),dirty=new Map()
  const alive=e=>e===epoch
  const requireEditable=()=>{if(state.finalizing)throw new Error('正在确认保存这一餐，请稍候再编辑或切换草稿。')}
  const remember=record=>{const observed=cache.get(record.id)||reactive(record);if(record.version<(versions.get(record.id)||0))return observed;if(observed!==record)Object.assign(observed,record);cache.set(record.id,observed);versions.set(record.id,record.version);return observed}
  const fail=(error,e,id)=>{if(alive(e)){state.error=error.status===409?'这条记录已在别处更新。你的输入已保留，请选择恢复服务端版本或用当前输入重试。':error.message||'保存失败，请重试';if(error.status===409)state.conflict={id}}throw error}
  const enqueue=work=>{const next=queue.catch(()=>{}).then(work);queue=next;return next}
  const upsert=record=>{const index=state.records.findIndex(r=>r.id===record.id);if(index>=0)state.records[index]=record;state.drafts=state.drafts.map(r=>r.id===record.id?record:r)}
  async function refresh(){
    const e=epoch;if(state.accountId==null)return
    state.loading=true
    try {const [summary,drafts,recent]=await Promise.all([request('/cooking-summary'),request('/cooking-sessions?state=in_progress&page_size=50'),request('/cooking-sessions?state=completed&page_size=1')]);if(!alive(e))return;state.summary=summary;state.recentRecord=recent.items[0]||null;state.drafts=drafts.items.map(r=>dirty.has(r.id)?cache.get(r.id):remember(r));await state.loadRecords(filter)}catch(error){if(alive(e))state.error=error.message}finally{if(alive(e))state.loading=false}
  }
  Object.assign(state,{
    reset(){epoch++;listEpoch++;Object.assign(state,initial());cache.clear();versions.clear();dirty.clear();queue=Promise.resolve();completing=null;starting=null;pendingStart=null;filter={page:1,state:'completed'}},
    async loadAccount(id){if(state.accountId===id)return;state.reset();state.accountId=id;if(id!=null)await refresh()},
    refresh,
    async loadRecords(options={}){filter={...filter,...options};const e=epoch,l=++listEpoch;const query=new URLSearchParams(Object.entries({...filter,page_size:12}).filter(([,v])=>v!==''&&v!=null));try{const result=await request('/cooking-sessions?'+query);if(alive(e)&&l===listEpoch){state.records=result.items.map(r=>dirty.has(r.id)?cache.get(r.id):remember(r));state.total=result.total;state.page=result.page}return result}catch(error){return fail(error,e)}},
    async getRecord(id){const e=epoch;try{const record=await request('/cooking-sessions/'+id);if(!alive(e))return null;return dirty.has(id)?cache.get(id):remember(record)}catch(error){return fail(error,e)}},
    async history(key){const e=epoch;let page=1,items=[];do{const result=await request('/cooking-sessions?'+new URLSearchParams({state:'completed',dish_key:key,page,page_size:50}));if(!alive(e))return [];items.push(...result.items);if(items.length>=result.total)break;page++}while(true);return sameDishAttempts(items,key)},
    async loadMonth(month){const e=epoch;let page=1,items=[];do{const result=await request('/cooking-sessions?'+new URLSearchParams({state:'completed',month,page,page_size:50}));if(!alive(e))return [];items.push(...result.items.map(r=>dirty.has(r.id)?cache.get(r.id):remember(r)));if(items.length>=result.total)break;page++}while(true);return items},
    async start(input){requireEditable();if(starting)return starting;const e=epoch;const payload={...input};if(payload.meal_slot==null)payload.meal_slot=state.mealSlot;const signature=JSON.stringify(payload);if(!pendingStart||pendingStart.signature!==signature)pendingStart={signature,body:{client_id:crypto.randomUUID(),...payload}};const body=pendingStart.body;starting=(async()=>{try{const result=await request('/cooking-sessions','POST',body);if(!alive(e))return null;pendingStart=null;state.draft=remember(result);state.lastCompleted=null;state.feedback=null;state.error='';if(!state.drafts.some(r=>r.id===result.id))state.drafts.unshift(state.draft);return state.draft}catch(error){return fail(error,e)}finally{if(alive(e))starting=null}})();return starting},
    setMealSlot(id){state.mealSlot=id},
    async resume(id){requireEditable();const record=await state.getRecord(id);requireEditable();if(record?.state==='in_progress'){state.draft=record;state.lastCompleted=null}return record},
    patch(patch,id=state.draft?.id){
      try{requireEditable()}catch(error){return Promise.reject(error)}
      const record=cache.get(id)||state.draft;if(!record||record.id!==id)return Promise.reject(new Error('请先选择一餐'))
      const e=epoch,incoming=copy(patch),payload=mergePatch(dirty.get(id),incoming);applyLocal(record,incoming);dirty.set(id,payload);upsert(record)
      return enqueue(async()=>{if(!alive(e))return null;if(state.conflict)throw new Error(state.error);state.saving=true;try{const result=await request('/cooking-sessions/'+id,'PATCH',{...payload,version:versions.get(id)});if(!alive(e))return null;versions.set(id,result.version);record.version=result.version;state.error='';return record}catch(error){return fail(error,e,id)}finally{if(alive(e))state.saving=false}}).then(result=>{if(alive(e)&&result&&JSON.stringify(dirty.get(id))===JSON.stringify(payload))dirty.delete(id);return result})
    },
    async retry(id=state.conflict?.id||state.draft?.id){requireEditable();if(state.conflict)throw new Error(state.error);const payload=dirty.get(id);if(payload)return state.patch(payload,id);state.error=''},
    async resolveConflict(choice){requireEditable();const id=state.conflict?.id;if(!id)return;const e=epoch,payload=copy(dirty.get(id)||{});const server=await request('/cooking-sessions/'+id);if(!alive(e))return null;state.conflict=null;state.error='';versions.set(id,server.version);if(choice==='retry')return state.patch(payload,id);dirty.delete(id);const restored=remember(server);if(state.draft?.id===id)state.draft=restored;upsert(restored);return restored},
    complete(){if(completing)return completing;if(starting)return Promise.reject(new Error('正在切换草稿，请稍候再保存这一餐。'));const e=epoch,id=state.draft?.id;if(!id)return Promise.reject(new Error('没有进行中的一餐'));if(state.uploading)return Promise.reject(new Error('照片仍在上传，请稍候'));state.finalizing=true;completing=(async()=>{try{await queue;if(!alive(e))return null;if(dirty.has(id))throw new Error('还有输入尚未保存，请先重试保存。');if(state.conflict)throw new Error(state.error);state.saving=true;const before=state.summary?.level;const result=await request(`/cooking-sessions/${id}/complete`,'POST',{version:versions.get(id)});if(!alive(e))return null;remember(result);dirty.delete(id);state.draft=null;state.lastCompleted=result;state.drafts=state.drafts.filter(r=>r.id!==id);state.error='';await refresh();if(alive(e))state.feedback=levelFeedback(before,state.summary?.level,state.summary?.meals);return result}catch(error){return fail(error,e,id)}finally{if(alive(e)){state.saving=false;state.finalizing=false;completing=null}}})();return completing},
    async withdraw(id,version){requireEditable();const e=epoch;try{await queue;if(!alive(e))return null;const result=await request(`/cooking-sessions/${id}/withdraw`,'POST',{version:versions.get(id)||version});if(!alive(e))return null;cache.delete(id);dirty.delete(id);if(state.draft?.id===id)state.draft=null;state.feedback=null;await refresh();return result}catch(error){return fail(error,e,id)}},
    async uploadPhoto(file){requireEditable();const e=epoch;state.uploading++;try{const form=new FormData();form.append('file',file);const result=await request('/media','POST',form);return alive(e)?result.url:null}catch(error){return fail(error,e)}finally{if(alive(e))state.uploading--}},
  })
  return state
}

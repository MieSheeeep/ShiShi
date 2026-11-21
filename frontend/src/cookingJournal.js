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
const copy = value => JSON.parse(JSON.stringify(value))
const blankSummary = () => ({meals:0,dishes:0,level:{number:1,title:'初入厨房',remaining:1,next_at:1},achievements:[],repertoire:[]})
const initial = () => ({accountId:null,draft:null,drafts:[],records:[],total:0,page:1,summary:blankSummary(),loading:false,saving:false,uploading:0,error:'',conflict:null,lastCompleted:null,recentRecord:null})
const mergePatch = (a,b) => ({...a,...b,...((a?.dishes||b.dishes)?{dishes:[...new Map([...(a?.dishes||[]),...(b.dishes||[])].map(d=>[d.id,{...(a?.dishes||[]).find(x=>x.id===d.id),...d}])).values()]}:{})})
const applyLocal = (record,patch) => {for(const [key,value] of Object.entries(patch)){if(key==='dishes'){for(const d of value){const target=record.dishes.find(x=>x.id===d.id);if(target)Object.assign(target,copy(d))}}else record[key]=copy(value)}}

// Transport injection lets the same queue run in Vue and in independent Node tests.
export function createJournal(request, reactive = value=>value) {
  const state=reactive(initial())
  let epoch=0,queue=Promise.resolve(),completing=null,starting=null,pendingStart=null,filter={page:1,state:'completed'},listEpoch=0
  const cache=new Map(),versions=new Map(),dirty=new Map()
  const alive=e=>e===epoch
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
    async start(input){if(starting)return starting;const e=epoch;const signature=JSON.stringify(input);if(!pendingStart||pendingStart.signature!==signature)pendingStart={signature,body:{client_id:crypto.randomUUID(),...input}};const body=pendingStart.body;starting=(async()=>{try{const result=await request('/cooking-sessions','POST',body);if(!alive(e))return null;pendingStart=null;state.draft=remember(result);state.lastCompleted=null;state.error='';if(!state.drafts.some(r=>r.id===result.id))state.drafts.unshift(state.draft);return state.draft}catch(error){return fail(error,e)}finally{if(alive(e))starting=null}})();return starting},
    async resume(id){const record=await state.getRecord(id);if(record?.state==='in_progress'){state.draft=record;state.lastCompleted=null}return record},
    patch(patch,id=state.draft?.id){
      const record=cache.get(id)||state.draft;if(!record||record.id!==id)return Promise.reject(new Error('请先选择一餐'))
      const e=epoch,payload=copy(patch);applyLocal(record,payload);dirty.set(id,mergePatch(dirty.get(id),payload));upsert(record)
      return enqueue(async()=>{if(!alive(e))return null;if(state.conflict)throw new Error(state.error);state.saving=true;try{const result=await request('/cooking-sessions/'+id,'PATCH',{...payload,version:versions.get(id)});if(!alive(e))return null;versions.set(id,result.version);record.version=result.version;state.error='';return record}catch(error){return fail(error,e,id)}finally{if(alive(e))state.saving=false}}).then(result=>{if(alive(e)&&result&&JSON.stringify(dirty.get(id))===JSON.stringify(payload))dirty.delete(id);return result})
    },
    async retry(id=state.conflict?.id||state.draft?.id){if(state.conflict)throw new Error(state.error);const payload=dirty.get(id);if(payload)return state.patch(payload,id);state.error=''},
    async resolveConflict(choice){const id=state.conflict?.id;if(!id)return;const e=epoch,payload=copy(dirty.get(id)||{});const server=await request('/cooking-sessions/'+id);if(!alive(e))return null;state.conflict=null;state.error='';versions.set(id,server.version);if(choice==='retry')return state.patch(payload,id);dirty.delete(id);const restored=remember(server);if(state.draft?.id===id)state.draft=restored;upsert(restored);return restored},
    complete(){if(completing)return completing;const e=epoch,id=state.draft?.id;if(!id)return Promise.reject(new Error('没有进行中的一餐'));if(state.uploading)return Promise.reject(new Error('照片仍在上传，请稍候'));completing=(async()=>{try{await queue;if(!alive(e))return null;if(dirty.has(id))await state.retry(id);if(state.conflict)throw new Error(state.error);state.saving=true;const result=await request(`/cooking-sessions/${id}/complete`,'POST',{version:versions.get(id)});if(!alive(e))return null;remember(result);dirty.delete(id);state.draft=null;state.lastCompleted=result;state.drafts=state.drafts.filter(r=>r.id!==id);state.error='';await refresh();return result}catch(error){return fail(error,e,id)}finally{if(alive(e)){state.saving=false;completing=null}}})();return completing},
    async withdraw(id,version){const e=epoch;try{await queue;if(!alive(e))return null;const result=await request(`/cooking-sessions/${id}/withdraw`,'POST',{version:versions.get(id)||version});if(!alive(e))return null;cache.delete(id);dirty.delete(id);if(state.draft?.id===id)state.draft=null;await refresh();return result}catch(error){return fail(error,e,id)}},
    async markDish(dish_key,status){const e=epoch;try{await request('/cooking-dishes','PUT',{dish_key,status});if(alive(e))await refresh()}catch(error){return fail(error,e)}},
    async uploadPhoto(file){const e=epoch;state.uploading++;try{const form=new FormData();form.append('file',file);const result=await request('/media','POST',form);return alive(e)?result.url:null}catch(error){return fail(error,e)}finally{if(alive(e))state.uploading--}},
  })
  return state
}

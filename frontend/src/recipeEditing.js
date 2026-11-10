export function moveItem(rows,index,delta){
  const target=index+delta
  if(index<0||index>=rows.length||target<0||target>=rows.length)return
  const [item]=rows.splice(index,1);rows.splice(target,0,item)
}
export function attachImage(step,url){if(!step.images.includes(url))step.images.push(url)}
export const newId=()=>crypto.randomUUID()
export const newStep=()=>({id:newId(),text:'',images:[]})
export const newIngredient=()=>({id:newId(),name:'',amount:'',kind:'食材'})
export function blankRecipe(){return {schema_version:2,name:'',emoji:'🍲',cover:'',source:{platform:'manual',url:'',author:'',original_text:'',original_images:[]},minutes:'',servings:'',tags:[],notes:'',images:[],ingredients:[newIngredient()],steps:[newStep()]}}
export const tagKey=t=>t.id||`${t.group||'我的分类'}:${t.name}`

const TOKEN_KEY='shishi_token'
export const getToken=()=>localStorage.getItem(TOKEN_KEY)
export const setToken=value=>localStorage.setItem(TOKEN_KEY,value)
export const clearToken=()=>localStorage.removeItem(TOKEN_KEY)
export function onUnauthorized(handler){
  window.addEventListener('shishi:unauthorized',handler)
  return ()=>window.removeEventListener('shishi:unauthorized',handler)
}

export async function api(path,method='GET',body){
  const headers={}
  const token=getToken()
  if(token)headers.Authorization='Bearer '+token
  let payload=body
  if(body!==undefined&&!(body instanceof FormData)){headers['Content-Type']='application/json';payload=JSON.stringify(body)}
  const response=await fetch('/api'+path,{method,headers,body:payload})
  if(response.status===401&&!path.startsWith('/auth/')){clearToken();window.dispatchEvent(new Event('shishi:unauthorized'))}
  const data=await response.json().catch(()=>({}))
  if(!response.ok){
    const error=Error(typeof data.detail==='string'?data.detail:'请检查材料、步骤、标签和图片是否填写正确')
    error.status=response.status
    throw error
  }
  return data
}
export function moveItem(rows,index,delta){
  const target=index+delta
  if(index<0||index>=rows.length||target<0||target>=rows.length)return
  const [item]=rows.splice(index,1);rows.splice(target,0,item)
}
export function attachImage(step,url){if(!step.images.includes(url))step.images.push(url)}
export const newId=()=>crypto.randomUUID()
export const newStep=()=>({id:newId(),text:'',images:[]})
export const newIngredient=()=>({id:newId(),name:'',amount:'',kind:'食材'})
export function blankRecipe(){return {schema_version:2,name:'',emoji:'🍲',source:{platform:'manual',url:'',author:'',original_text:'',original_images:[]},minutes:'',servings:'',tags:[],notes:'',images:[],ingredients:[newIngredient()],steps:[newStep()]}}
export const tagKey=t=>t.id||`${t.group||'我的分类'}:${t.name}`
export async function api(path,method='GET',body){
  const response=await fetch('/api'+path,{method,headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)})
  const data=await response.json()
  if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'请检查材料、步骤、标签和图片是否填写正确')
  return data
}

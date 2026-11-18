export function menuRecipes(recipes,ids){
  const byId=new Map(recipes.map(r=>[r.id,r]))
  return [...new Set(ids)].map(id=>byId.get(id)).filter(Boolean)
}
export function restoreMenu(storage,userId){
  try{
    const ids=JSON.parse(storage.getItem(`shishi-menu:${userId}`)||'[]')
    return Array.isArray(ids)?[...new Set(ids.filter(id=>Number.isSafeInteger(id)&&id>0))].slice(0,200):[]
  }catch{return []}
}
export function saveMenu(storage,userId,ids){
  try{storage.setItem(`shishi-menu:${userId}`,JSON.stringify(ids))}catch{}
}

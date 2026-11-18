// The same active inventory is used by matching, AI and the pantry API.
export function inventorySettings(items){
  const rows=kind=>items.filter(i=>i.status==='active'&&i.kind===kind)
    .map(({name,amount,unit})=>({name,amount,unit}))
  return {ingredients:rows('食材'),staples:rows('调料')}
}

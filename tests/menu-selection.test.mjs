import test from 'node:test'
import assert from 'node:assert/strict'
import { menuRecipes, restoreMenu, saveMenu } from '../frontend/src/menuSelection.js'

test('menu keeps selection order, removes duplicates and ignores deleted recipes',()=>{
  assert.deepEqual(menuRecipes([{id:1},{id:2}],[2,1,2,99]),[{id:2},{id:1}])
})
test('menu drafts are isolated by account and tolerate unavailable storage',()=>{
  const rows=new Map(),storage={getItem:k=>rows.get(k),setItem:(k,v)=>rows.set(k,v)}
  saveMenu(storage,1,[2,3])
  assert.deepEqual(restoreMenu(storage,1),[2,3])
  assert.deepEqual(restoreMenu(storage,2),[])
  storage.getItem=()=>{throw Error('blocked')}
  assert.deepEqual(restoreMenu(storage,1),[])
  storage.setItem=()=>{throw Error('blocked')}
  assert.doesNotThrow(()=>saveMenu(storage,1,[2]))
})

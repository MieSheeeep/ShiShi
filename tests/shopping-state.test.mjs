import test from 'node:test'
import assert from 'node:assert/strict'
import { setAtHome, editAmount } from '../frontend/src/shoppingState.js'

test('moving ingredients between home and purchase resets bought state and keeps provenance',()=>{
  const item={name:'鸡蛋',amount:'3个',checked:true,pantry:false,sources:[{recipe:'炒蛋'}]}
  const home=setAtHome(item,true)
  assert.equal(home.pantry,true)
  assert.equal(home.checked,false)
  assert.deepEqual(home.sources,item.sources)
  assert.equal(setAtHome(home,false).pantry,false)
  assert.equal(item.checked,true)
})
test('editing an amount invalidates a previous purchase confirmation',()=>{
  assert.deepEqual(editAmount({amount:'2个',checked:true},'5个'),{amount:'5个',checked:false})
})

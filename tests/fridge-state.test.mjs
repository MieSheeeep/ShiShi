import test from 'node:test'
import assert from 'node:assert/strict'
import { inventorySettings } from '../frontend/src/fridgeState.js'

test('matching and AI use active stock with original quantities and separate condiments',()=>{
  const items=[
    {name:'番茄',amount:'300',unit:'克',kind:'食材',status:'active'},
    {name:'鸡蛋',amount:'2',unit:'个',kind:'食材',status:'used'},
    {name:'盐',amount:'半',unit:'袋',kind:'调料',status:'active'},
  ]
  const before=structuredClone(items)
  assert.deepEqual(inventorySettings(items),{
    ingredients:[{name:'番茄',amount:'300',unit:'克'}],
    staples:[{name:'盐',amount:'半',unit:'袋'}],
  })
  assert.deepEqual(items,before)
})

import test from 'node:test'
import assert from 'node:assert/strict'
import { moveItem, attachImage } from '../frontend/src/recipeEditing.js'

test('moving a step keeps its stable identity and pictures attached',()=>{
  const rows=[{id:'one',text:'first',images:['/a.jpg']},{id:'two',text:'second',images:[]}]
  moveItem(rows,0,1)
  assert.deepEqual(rows.map(s=>s.id),['two','one'])
  assert.deepEqual(rows[1].images,['/a.jpg'])
  moveItem(rows,1,1)
  assert.equal(rows[1].id,'one')
})
test('assigning an image is idempotent and does not delete the original gallery',()=>{
  const gallery=['/a.jpg','/b.jpg'], step={id:'one',images:[]}
  attachImage(step,gallery[1]);attachImage(step,gallery[1])
  assert.deepEqual(step.images,['/b.jpg'])
  assert.deepEqual(gallery,['/a.jpg','/b.jpg'])
})

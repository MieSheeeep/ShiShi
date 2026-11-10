import test from 'node:test'
import assert from 'node:assert/strict'
import { shanghaiDate, selectEdition, publishedEditions, editionDraft, editions } from '../frontend/src/dailyContent.js'

test('daily selection follows Shanghai midnight rather than UTC',()=>{
  assert.equal(shanghaiDate(new Date('2026-11-09T15:59:00Z')),'2026-11-09')
  assert.equal(shanghaiDate(new Date('2026-11-09T16:00:00Z')),'2026-11-10')
})
test('exact date wins; unscheduled days show the latest published edition honestly',()=>{
  const rows=[{date:'2026-11-10'},{date:'2026-11-08'},{date:'2026-11-09'}]
  assert.equal(selectEdition(rows,'2026-11-09').date,'2026-11-09')
  assert.equal(selectEdition(rows,'2026-11-11').date,'2026-11-10')
  assert.equal(selectEdition(rows,'2026-11-07'),null)
  assert.deepEqual(publishedEditions(rows,'2026-11-09').map(r=>r.date),['2026-11-09','2026-11-08'])
})
test('collecting a curated recipe creates an independent editable V2 document',()=>{
  const edition=editions.find(e=>e.date==='2026-11-10')
  const before=JSON.stringify(edition)
  const draft=editionDraft(edition)
  const second=editionDraft(edition)
  assert.equal(draft.schema_version,2)
  assert.deepEqual(draft.images,[edition.image])
  assert.ok(draft.ingredients.length&&draft.steps.length)
  assert.equal(new Set(draft.steps.map(s=>s.id)).size,draft.steps.length)
  assert.notEqual(draft.steps[0].id,second.steps[0].id)
  draft.steps.reverse();draft.ingredients[0].name='修改'
  assert.equal(JSON.stringify(edition),before)
  assert.equal(draft.source.url,'')
  assert.ok(draft.notes.includes('食拾'))
})

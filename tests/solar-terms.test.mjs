import test from 'node:test'
import assert from 'node:assert/strict'
import { solarTermOf, solarTermsOfYear } from '../frontend/src/solarTerms.js'
import { SOLAR_DIARIES } from '../frontend/src/solarDiaries.js'
import { diaryFor } from '../frontend/src/dailyContent.js'

// 2026 年 24 节气日期，对照公开日历（交节时刻换算为北京时间当天）。
test('2026 solar term dates follow the published calendar',()=>{
  const dates=solarTermsOfYear(2026).map(t=>t.date)
  assert.deepEqual(dates,['2026-01-05','2026-01-20','2026-02-04','2026-02-18','2026-03-05','2026-03-20','2026-04-05','2026-04-20','2026-05-05','2026-05-21','2026-06-05','2026-06-21','2026-07-07','2026-07-23','2026-08-07','2026-08-23','2026-09-07','2026-09-23','2026-10-08','2026-10-23','2026-11-07','2026-11-22','2026-12-07','2026-12-22'])
})

test('term switches on the term day and spans the new year',()=>{
  assert.equal(solarTermOf('2026-11-06').name,'霜降')
  assert.equal(solarTermOf('2026-11-07').name,'立冬')
  assert.equal(solarTermOf('2026-11-22').name,'小雪')
  assert.equal(solarTermOf('2026-01-02').name,'冬至')
  assert.equal(solarTermOf('2026-12-22').name,'冬至')
  assert.equal(solarTermOf('2026-11-14').end,'2026-11-22')
})

test('every solar term has a diary with seasonal foods and a source',()=>{
  assert.equal(Object.keys(SOLAR_DIARIES).length,24)
  for(const [term,entry] of Object.entries(SOLAR_DIARIES)){
    assert.ok(entry.title && entry.text && entry.background,term)
    assert.ok(entry.foods.length>=3,term)
    assert.ok(entry.reference.url.startsWith('https://'),term)
  }
  assert.equal(SOLAR_DIARIES['立冬'].title,'天渐寒，晨粥正暖')
})

test('homepage diary follows the current solar term',()=>{
  const today=diaryFor('2026-11-14')
  assert.equal(today.term,'立冬')
  assert.equal(today.date,'2026-11-14')
  assert.equal(diaryFor('2026-12-22').term,'冬至')
  assert.equal(diaryFor('2027-02-05').term,'立春')
})

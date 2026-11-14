// 二十四节气：按太阳视黄经每 15° 一个节气，用低精度天文公式求交节时刻，按 Asia/Shanghai 取日期。
const NAMES = ['小寒','大寒','立春','雨水','惊蛰','春分','清明','谷雨','立夏','小满','芒种','夏至','小暑','大暑','立秋','处暑','白露','秋分','寒露','霜降','立冬','小雪','大雪','冬至']
const RAD = Math.PI / 180
const cache = new Map()

function sunLongitude(jd) {
  const t = (jd - 2451545) / 36525
  const l0 = 280.46646 + 36000.76983 * t + 0.0003032 * t * t
  const m = (357.52911 + 35999.05029 * t - 0.0001537 * t * t) * RAD
  const c = (1.914602 - 0.004817 * t - 0.000014 * t * t) * Math.sin(m)
    + (0.019993 - 0.000101 * t) * Math.sin(2 * m) + 0.000289 * Math.sin(3 * m)
  const omega = (125.04 - 1934.136 * t) * RAD
  return ((l0 + c - 0.00569 - 0.00478 * Math.sin(omega)) % 360 + 360) % 360
}

function termDay(year, index) {
  const target = (285 + 15 * index) % 360
  let jd = Date.UTC(year, 0, 6) / 86400000 + 2440587.5 + index * 15.2184
  for (let i = 0; i < 6; i += 1) {
    const delta = ((target - sunLongitude(jd) + 540) % 360) - 180
    jd += delta / 0.9856474
  }
  return new Date((jd - 2440587.5) * 86400000 + 8 * 3600000).toISOString().slice(0, 10)
}

export function solarTermsOfYear(year) {
  if (!cache.has(year)) cache.set(year, NAMES.map((name, i) => ({ name, date: termDay(year, i) })))
  return cache.get(year)
}

export function solarTermOf(date) {
  const year = Number(date.slice(0, 4))
  const rows = [...solarTermsOfYear(year - 1), ...solarTermsOfYear(year), ...solarTermsOfYear(year + 1)]
  let hit = rows[0]
  for (const row of rows) if (row.date <= date) hit = row
  const next = rows.find(row => row.date > date)
  return { name: hit.name, start: hit.date, end: next ? next.date : '' }
}

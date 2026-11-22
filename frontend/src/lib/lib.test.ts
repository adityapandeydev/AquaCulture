import { describe, expect, it } from 'vitest'
import type { Hour, Summary } from '../api/types'
import { nights, runs, share, ticks, timeTicks, top } from './scale'
import { percent, reasonText, stateOf, toneOf } from './status'
import { ago, clock, HOUR, hourStart, localHour } from './time'

const IST = 'Asia/Kolkata'
const at = Date.parse('2026-01-24T00:44:59Z')

const summary = (over: Partial<Summary>): Summary => ({
  id: 'x', name: 'P', timezone: IST, species: 'rohu_catla', mode: 'live', sampling_minutes: 15, created_at: '', do_low: 4, do_critical: 3,
  ph_low: null, ph_high: null, temperature_low: null, temperature_high: null, alert_probability: 0.5, latest_at: new Date(at).toISOString(),
  latest_do_mgL: 6, latest_ph: null, latest_temperature_c: null, open_alerts: 0, critical_alerts: 0, forecast_issue: null, forecast_status: null,
  highest_probability: null, trend_end: null, trend_do_mgL: null, ...over,
})

describe('time', () => {
  it('uses the pond clock, including half-hour zones', () => {
    expect(clock(at, IST)).toBe('06:14')
    expect(localHour(at, IST)).toBe(6)
    expect(new Date(hourStart(at, IST)).toISOString()).toBe('2026-01-24T00:30:00.000Z')
    expect(localHour(Date.parse('2026-01-23T18:30:00Z'), IST)).toBe(0)
  })
  it('keeps both copies of a repeated hour', () => {
    const first = Date.parse('2026-11-01T05:30:00Z')
    expect(hourStart(first + HOUR, 'America/New_York') - hourStart(first, 'America/New_York')).toBe(HOUR)
  })
  it('describes age', () => {
    const now = Date.parse('2026-01-24T12:00:00Z')
    expect(ago('2026-01-24T12:00:30Z', now)).toBe('just now')
    expect(ago('2026-01-24T11:15:00Z', now)).toBe('45 min ago')
    expect(ago('2026-01-23T11:00:00Z', now)).toBe('25 h ago')
    expect(ago('2026-01-20T11:00:00Z', now)).toBe('4 days ago')
  })
})

describe('states', () => {
  it('ranks critical alerts first and never claims safety', () => {
    const labels = [
      stateOf(summary({ critical_alerts: 1, open_alerts: 2 }), at), stateOf(summary({}), at + 3 * HOUR), stateOf(summary({ open_alerts: 1 }), at),
      stateOf(summary({ do_low: null }), at), stateOf(summary({ latest_at: null }), at), stateOf(summary({}), at),
    ]
    expect(labels.map((l) => l.rank)).toEqual([0, 1, 2, 3, 4, 5])
    for (const l of labels) expect(l.label).not.toMatch(/safe|good|healthy|fine/i)
  })
  it('shows a critical alert even when data is old, and never calls a demo stale', () => {
    expect(stateOf(summary({ critical_alerts: 1 }), at + 9 * HOUR).tone).toBe('critical')
    expect(stateOf(summary({ mode: 'demo' }), at + 900 * HOUR).label).toBe('No open alerts')
  })
  it('judges readings only against chosen limits', () => {
    expect(toneOf(5, { do_low: 4, do_critical: 3 })).toBe('none')
    expect(toneOf(3.5, { do_low: 4, do_critical: 3 })).toBe('warning')
    expect(toneOf(2.9, { do_low: 4, do_critical: 3 })).toBe('critical')
    expect(toneOf(0.5, { do_low: null, do_critical: null })).toBe('none')
    expect(toneOf(0, { do_low: null, do_critical: null })).toBe('critical')
    expect(toneOf(null, { do_low: 4, do_critical: 3 })).toBe('none')
  })
  it('never rounds a chance to certainty', () => {
    expect([percent(0.001), percent(0.5), percent(0.998)]).toEqual(['<1%', '50%', '>99%'])
    expect(reasonText('something_new')).toContain('something_new')
  })
})

describe('charts', () => {
  const hour = (k: number, v: number | null): Hour => ({ start: new Date(at + k * HOUR).toISOString(), do_mgL: v, do_min_mgL: v, ph: null, temperature_c: null, coverage: 1, zero_readings: 0 })
  it('breaks the line at missing hours', () => {
    expect(runs([hour(0, 5), hour(1, 6), hour(2, null), hour(3, 4), hour(6, 3)]).map((r) => r.length)).toEqual([2, 1, 1])
    expect(runs([])).toEqual([])
    expect(runs([hour(0, 5), { ...hour(1, 3), coverage: 0.25 }, hour(2, 5)]).map((r) => r.length)).toEqual([1, 1])
  })
  it('uses clean axes', () => {
    expect(top([3.2, null])).toBe(6)
    expect(top([20.4])).toBe(24)
    expect(ticks(6)).toEqual([0, 2, 4, 6])
    expect(ticks(24)).toEqual([0, 4, 8, 12, 16, 20, 24])
  })
  it('marks local nights', () => {
    const from = Date.parse('2026-01-23T06:30:00Z') // noon in India
    expect(nights(from, from + 24 * HOUR, IST)).toEqual([[from + 6 * HOUR, from + 18 * HOUR]])
    expect(timeTicks(from, from + 24 * HOUR, IST, 600).map((t) => clock(t, IST))).toEqual(['12:00', '18:00', '00:00', '06:00', '12:00'])
  })
  it('limits the column', () => {
    expect([share(-1), share(6), share(30)]).toEqual([0, 0.5, 1])
  })
})

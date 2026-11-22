import type { Hour } from '../api/types'
import { HOUR, localHour } from './time'

export type Point = { t: number; v: number }

/** An hour needs three quarters of its readings to count, as in the forecast model. */
export const FULL = 0.75

/** Split hourly means into unbroken runs. A missing or partial hour is a gap, never a joined line. */
export function runs(hours: Hour[]): Point[][] {
  const out: Point[][] = []
  let last = -Infinity
  for (const h of hours) {
    if (h.do_mgL === null || h.coverage < FULL) continue
    const t = Date.parse(h.start) + HOUR / 2
    if (t - last > HOUR * 1.01) out.push([])
    out[out.length - 1].push({ t, v: h.do_mgL })
    last = t
  }
  return out
}

/** Clean axis ticks from zero. */
export function ticks(max: number): number[] {
  const step = max <= 5 ? 1 : max <= 12 ? 2 : max <= 24 ? 4 : 8
  const out = []
  for (let v = 0; v <= max + 1e-9; v += step) out.push(v)
  return out
}

export function top(values: (number | null)[]): number {
  const max = Math.max(6, ...values.filter((v): v is number => v !== null))
  const step = max <= 12 ? 2 : max <= 24 ? 4 : 8
  return Math.ceil(max / step) * step
}

/** Stretches of the plot that lie between 18:00 and 06:00 local time. */
export function nights(from: number, to: number, zone: string): [number, number][] {
  const out: [number, number][] = []
  for (let t = from; t < to; t += HOUR) {
    const h = localHour(t, zone)
    if (h >= 18 || h < 6) {
      const end = Math.min(t + HOUR, to)
      if (out.length && out[out.length - 1][1] === t) out[out.length - 1][1] = end
      else out.push([t, end])
    }
  }
  return out
}

/** Hour marks for the time axis, spaced to fit. */
export function timeTicks(from: number, to: number, zone: string, width: number): number[] {
  const span = (to - from) / HOUR
  const room = Math.max(2, Math.floor(width / 84))
  const step = [3, 6, 12, 24, 48].find((s) => span / s <= room) ?? 96
  const out = []
  for (let t = from; t <= to; t += HOUR) {
    const h = localHour(t, zone)
    if (step <= 24 ? h % step === 0 : h === 0 && Math.round((t - from) / (24 * HOUR)) % (step / 24) === 0) out.push(t)
  }
  return out
}

/** Depth of the water column, as the share of a full column. */
export const COLUMN_TOP = 12
export const share = (v: number) => Math.max(0, Math.min(1, v / COLUMN_TOP))

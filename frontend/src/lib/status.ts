import type { Limits, Summary } from '../api/types'
import { HOUR } from './time'

export const STALE = 2 * HOUR

export type Tone = 'neutral' | 'warning' | 'critical' | 'demo'
export type State = { label: string; tone: Tone; rank: number }

/** Colour of one reading against the operator's own limits. No limit means no judgement. */
export function toneOf(value: number | null, limits: Pick<Limits, 'do_low' | 'do_critical'>): 'none' | 'warning' | 'critical' {
  if (value === null) return 'none'
  if (value === 0 || (limits.do_critical !== null && value < limits.do_critical)) return 'critical'
  return limits.do_low !== null && value < limits.do_low ? 'warning' : 'none'
}

/** A pond's headline state. None of these says that a pond is safe. */
export function stateOf(p: Summary, now: number): State {
  if (p.latest_at === null) return { label: 'Waiting for a first reading', tone: 'neutral', rank: 4 }
  if (p.critical_alerts > 0) return { label: p.critical_alerts > 1 ? `${p.critical_alerts} critical alerts` : 'Critical alert', tone: 'critical', rank: 0 }
  if (p.mode === 'live' && now - Date.parse(p.latest_at) >= STALE) return { label: 'No recent data', tone: 'warning', rank: 1 }
  if (p.open_alerts > 0) return { label: p.open_alerts > 1 ? `${p.open_alerts} open alerts` : 'Open alert', tone: 'warning', rank: 2 }
  if (p.do_low === null) return { label: 'No oxygen limit set', tone: 'neutral', rank: 3 }
  return { label: 'No open alerts', tone: 'neutral', rank: 5 }
}

const reasons: Record<string, string> = {
  insufficient_do_history: 'At least 20 of the last 24 hours need oxygen readings.',
  insufficient_ph_history: 'At least 20 of the last 24 hours need pH readings.',
  insufficient_temperature_history: 'At least 20 of the last 24 hours need temperature readings.',
  recent_do_gap: 'The last 3 hours must all have oxygen readings.',
  no_history: 'There are no readings in the 24 hours before this time.',
  unsupported_species: 'There is no forecast model for this species.',
  issue_window_passed: 'The forecast could not be made within its hour, so it was skipped.',
  model_unavailable: 'The forecast service did not answer.',
}

export const reasonText = (code: string) => reasons[code] ?? 'The forecast service refused the request (' + code + ').'

const rejections: Record<string, string> = {
  invalid_time: 'The time cannot be read',
  future_time: 'The time is in the future',
  no_values: 'There are no values',
  do_out_of_bounds: 'Oxygen is outside 0 to 40 mg/L',
  ph_out_of_bounds: 'pH is outside 0 to 14',
  temperature_out_of_bounds: 'Temperature is outside -5 to 50 °C',
  conflicting_values_for_time: 'Two rows give different values for this time',
}

export const rejectionText = (code: string) => rejections[code] ?? (code.startsWith('invalid_number_') ? 'A number cannot be read' : code)

export function warningText(code: string): string {
  if (code === 'outside_training_season') return 'The model was trained on November to January only. Treat this forecast with extra care.'
  if (code.startsWith('outside_training_range:')) {
    const name = { do_mgL: 'Oxygen', ph: 'pH', temperature_c: 'Temperature' }[code.split(':')[1]] ?? 'A value'
    return `${name} is outside the range the model was trained on.`
  }
  return code
}

export const percent = (p: number) => (p < 0.01 ? '<1%' : p > 0.99 ? '>99%' : `${Math.round(p * 100)}%`)
export const fixed = (v: number | null | undefined, digits = 2) => (v === null || v === undefined ? '–' : v.toFixed(digits))

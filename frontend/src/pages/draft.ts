import type { Limits } from '../api/types'

export const limitKeys = ['do_low', 'do_critical', 'ph_low', 'ph_high', 'temperature_low', 'temperature_high'] as const

export type Draft = Record<(typeof limitKeys)[number], string> & { alert_probability: number }

export function draftOf(p?: Limits): Draft {
  const text = Object.fromEntries(limitKeys.map((k) => [k, p?.[k]?.toString() ?? ''])) as Record<(typeof limitKeys)[number], string>
  return { ...text, alert_probability: p?.alert_probability ?? 0.5 }
}

/** An empty field means no limit, never zero. */
export function limitsOf(d: Draft): Limits {
  const values = Object.fromEntries(limitKeys.map((k) => [k, d[k].trim() === '' ? null : Number(d[k])])) as Record<(typeof limitKeys)[number], number | null>
  return { ...values, alert_probability: d.alert_probability }
}

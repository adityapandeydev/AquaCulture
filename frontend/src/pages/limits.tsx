import type { Limits, Species } from '../api/types'
import { Button, Field } from '../ui/kit'
import { limitKeys, type Draft } from './draft'

const fields: { key: (typeof limitKeys)[number]; label: string; step: string; hint?: string }[] = [
  { key: 'do_low', label: 'Low oxygen, mg/L', step: '0.1', hint: 'Below this, a warning opens.' },
  { key: 'do_critical', label: 'Critical oxygen, mg/L', step: '0.1', hint: 'Below this, a critical alert opens.' },
  { key: 'ph_low', label: 'Lowest pH', step: '0.1' },
  { key: 'ph_high', label: 'Highest pH', step: '0.1' },
  { key: 'temperature_low', label: 'Lowest temperature, °C', step: '0.5' },
  { key: 'temperature_high', label: 'Highest temperature, °C', step: '0.5' },
]

/** Limits are always the operator's choice. A suggestion shows its source and is applied only on request. */
export function LimitFields({ draft, onChange, species }: { draft: Draft; onChange: (d: Draft) => void; species?: Species }) {
  const s = species?.suggested_thresholds
  return (
    <div className="stack">
      {s && (
        <div className="stack tight">
          <p className="note">Suggested for {species!.name}: oxygen below {s.do_low} mg/L, pH {s.ph_low} to {s.ph_high}. Source: {s.source} ({s.strength}).</p>
          <div><Button look="quiet" onClick={() => onChange({ ...draft, do_low: String(s.do_low), ph_low: String(s.ph_low), ph_high: String(s.ph_high) })}>Use these values</Button></div>
        </div>
      )}
      {species && !s && <p className="note">There is no suggestion for this species. Use limits from your own advisor.</p>}
      <div className="grid2">
        {fields.map((f) => <Field key={f.key} label={f.label} hint={f.hint} type="number" step={f.step} inputMode="decimal" placeholder="No limit" value={draft[f.key]} onChange={(e) => onChange({ ...draft, [f.key]: e.target.value })} />)}
      </div>
      <div className="field">
        <label htmlFor="chance">Warn when the low-oxygen chance reaches {Math.round(draft.alert_probability * 100)}%</label>
        <input id="chance" type="range" min="0.05" max="0.95" step="0.05" value={draft.alert_probability} onChange={(e) => onChange({ ...draft, alert_probability: Number(e.target.value) })} />
        <span className="hint">A lower value warns earlier and more often, with more false alarms. At 50%, the model missed 40 to 55% of new drops in unseen ponds.</span>
      </div>
    </div>
  )
}

export type { Limits }

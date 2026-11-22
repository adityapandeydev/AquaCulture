import type { Limits } from '../api/types'
import { useSeen } from '../lib/motion'
import { COLUMN_TOP, share } from '../lib/scale'
import { toneOf } from '../lib/status'
import { Icon } from '../ui/kit'

type Props = { value: number | null; limits: Pick<Limits, 'do_low' | 'do_critical'>; big?: boolean; dim?: boolean }

/** Oxygen drawn as water in a column, against the operator's own limits. Full is 12 mg/L. */
export function Column({ value, limits, big, dim }: Props) {
  const ref = useSeen<HTMLDivElement>()
  const tone = toneOf(value, limits)
  const marks = big
    ? [{ v: limits.do_low, name: 'low' }, { v: limits.do_critical, name: 'critical' }].filter((m): m is { v: number; name: string } => m.v !== null)
    : limits.do_low !== null ? [{ v: limits.do_low, name: 'low' }] : []
  const label = value === null ? 'No oxygen reading' : `Oxygen ${value.toFixed(2)} mg/L${tone === 'none' ? '' : `, ${tone === 'critical' ? 'critically low' : 'below the low limit'}`}`
  return (
    <div ref={ref} className={'column' + (big ? ' big' : '')} data-tone={tone} role="img" aria-label={label} style={dim ? { opacity: 0.55 } : undefined}>
      {value === null
        ? <div className="empty"><Icon name="drop" /></div>
        : <div className="level" style={{ transform: `translateY(${(1 - share(value)) * 100}%)` }}>
            <svg className="wave" viewBox="0 0 400 10" preserveAspectRatio="none"><path fill="currentColor" d="M0 6c25-6 50-6 75 0s25 5 50 0 50-6 75 0 50 5 75 0 25-5 50 0 50 6 75 0v4H0z" /></svg>
            <div className="body" />
          </div>}
      {marks.map((m) => <div key={m.name} className="limit" style={{ bottom: `${Math.min(1, m.v / COLUMN_TOP) * 100}%` }}>{big && <span>{m.v}</span>}</div>)}
    </div>
  )
}

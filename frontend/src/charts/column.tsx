import type { Limits } from '../api/types'
import { useSeen } from '../lib/motion'
import { COLUMN_TOP, share } from '../lib/scale'
import { toneOf } from '../lib/status'
import { Icon } from '../ui/kit'
import { cx } from '../ui/styles'

type Props = { value: number | null; limits: Pick<Limits, 'do_low' | 'do_critical'>; big?: boolean; dim?: boolean; className?: string }

const water = {
  none: { body: 'bg-linear-to-b from-water to-water-deep', wave: 'text-water' },
  warning: { body: 'bg-linear-to-b from-amber to-amber-deep', wave: 'text-amber' },
  critical: { body: 'bg-linear-to-b from-red to-red-deep', wave: 'text-red' },
}

/** Oxygen drawn as water in a column, against the operator's own limits. Full is 12 mg/L. */
export function Column({ value, limits, big, dim, className }: Props) {
  const ref = useSeen<HTMLDivElement>()
  const tone = toneOf(value, limits)
  const marks = big
    ? [{ v: limits.do_low, name: 'low' }, { v: limits.do_critical, name: 'critical' }].filter((m): m is { v: number; name: string } => m.v !== null)
    : limits.do_low !== null ? [{ v: limits.do_low, name: 'low' }] : []
  const label = value === null ? 'No oxygen reading' : `Oxygen ${value.toFixed(2)} mg/L${tone === 'none' ? '' : `, ${tone === 'critical' ? 'critically low' : 'below the low limit'}`}`
  return (
    <div
      ref={ref} role="img" aria-label={label}
      className={cx('column relative w-full overflow-hidden bg-sunken', big ? 'h-full min-h-60 rounded-panel [contain:layout_paint]' : 'h-18 rounded-[10px] [contain:strict]', dim && 'opacity-55', className)}
    >
      {value === null
        ? <div className="absolute inset-0 grid place-items-center text-ink-3"><Icon name="drop" /></div>
        : <div className="level absolute inset-0" style={{ transform: `translateY(${(1 - share(value)) * 100}%)` }}>
            <svg className={cx('wave absolute bottom-[calc(100%-1px)] left-0 h-2.5 w-[200%]', water[tone].wave)} viewBox="0 0 400 10" preserveAspectRatio="none"><path fill="currentColor" d="M0 6c25-6 50-6 75 0s25 5 50 0 50-6 75 0 50 5 75 0 25-5 50 0 50 6 75 0v4H0z" /></svg>
            <div className={cx('absolute inset-0', water[tone].body)} />
          </div>}
      {marks.map((m) => (
        <div key={m.name} className="absolute inset-x-0 h-0 border-t-2 border-ink opacity-75" style={{ bottom: `${Math.min(1, m.v / COLUMN_TOP) * 100}%` }}>
          {big && <span className="absolute right-2 bottom-0.5 rounded-[5px] bg-surface px-1.5 text-[0.8rem]/[1.35] font-semibold text-ink">{m.v}</span>}
        </div>
      ))}
    </div>
  )
}

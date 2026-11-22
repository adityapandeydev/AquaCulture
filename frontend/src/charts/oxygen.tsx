import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent, type PointerEvent } from 'react'
import type { Forecast, Hour, Pond } from '../api/types'
import { FULL, nights, runs, ticks, timeTicks, top } from '../lib/scale'
import { fixed, percent } from '../lib/status'
import { clock, day, dayClock, HOUR, localHour } from '../lib/time'
import * as ui from '../ui/styles'

const H = 300
const axis = 'fill-ink-3 text-xs tabular-nums'
const M = { top: 14, right: 14, bottom: 30, left: 36 }

type Props = { pond: Pond; hours: Hour[]; forecast: Forecast | null; from: number; to: number; drawKey: string }

/** Observed hourly oxygen and one forecast. The +1 h range is the only range that passed its test. */
export function OxygenChart({ pond, hours, forecast, from, to, drawKey }: Props) {
  const box = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(0)
  const [at, setAt] = useState<number | null>(null)
  const [table, setTable] = useState(false)
  const clip = useId()
  useEffect(() => {
    if (!box.current) return
    const observer = new ResizeObserver(([entry]) => setWidth(Math.round(entry.contentRect.width)))
    observer.observe(box.current)
    return () => observer.disconnect()
  }, [])

  const points = useMemo(() => (forecast?.status === 'ok' ? forecast.values.filter((v) => v.point_mgL !== null) : []), [forecast])
  const model = useMemo(() => {
    const lines = runs(hours)
    const max = top([...hours.map((h) => h.do_mgL), ...points.map((p) => p.point_mgL), ...points.map((p) => p.high_mgL), pond.do_low])
    return { lines, max, nights: nights(from, to, pond.timezone) }
  }, [hours, points, from, to, pond.timezone, pond.do_low])

  const w = Math.max(0, width - M.left - M.right)
  const h = H - M.top - M.bottom
  const x = (t: number) => M.left + ((t - from) / (to - from)) * w
  const y = (v: number) => M.top + h - (v / model.max) * h
  const middle = (t: string) => Date.parse(t) + HOUR / 2

  const slots = useMemo(() => {
    const map = new Map<number, Slot[1]>()
    for (const o of hours) map.set(middle(o.start), { observed: o.do_mgL, partial: o.coverage < FULL, forecast: null, low: null, high: null, chance: null, horizon: null })
    if (forecast?.status === 'ok') for (const v of forecast.values) {
      const t = middle(v.target_start)
      const old = map.get(t)
      map.set(t, { observed: old?.observed ?? null, partial: old?.partial ?? false, forecast: v.point_mgL, low: v.low_mgL, high: v.high_mgL, chance: v.probability, horizon: v.horizon_hours })
    }
    return [...map.entries()].filter(([t]) => t >= from && t <= to).sort((a, b) => a[0] - b[0])
  }, [hours, forecast, from, to])

  const pick = (e: PointerEvent) => {
    if (!slots.length || !w) return
    const t = from + ((e.clientX - box.current!.getBoundingClientRect().left - M.left) / w) * (to - from)
    let best = 0
    for (let i = 1; i < slots.length; i++) if (Math.abs(slots[i][0] - t) < Math.abs(slots[best][0] - t)) best = i
    setAt(best)
  }
  const step = (e: KeyboardEvent) => {
    const move = { ArrowLeft: -1, ArrowRight: 1, Home: -1e6, End: 1e6 }[e.key]
    if (!move || !slots.length) return
    e.preventDefault()
    setAt((i) => Math.max(0, Math.min(slots.length - 1, (i ?? slots.length) + move)))
  }

  const slot = at !== null && at < slots.length ? slots[at] : null
  const before = forecast ? [...hours].reverse().find((o) => o.do_mgL !== null && o.coverage >= FULL && Date.parse(o.start) < Date.parse(forecast.issue_time)) : undefined
  const joined = before && forecast && Date.parse(forecast.issue_time) - Date.parse(before.start) <= HOUR ? [{ t: middle(before.start), v: before.do_mgL! }] : []
  const path = [...joined, ...points.map((p) => ({ t: middle(p.target_start), v: p.point_mgL! }))].map((p, i) => `${i ? 'L' : 'M'}${x(p.t)} ${y(p.v)}`).join('')
  const limits = [{ v: pond.do_low, name: 'Low limit' }, { v: pond.do_critical, name: 'Critical limit' }].filter((l): l is { v: number; name: string } => l.v !== null && l.v <= model.max)
  const shownTicks = w ? timeTicks(from, to, pond.timezone, w) : []

  return (
    <figure className={ui.tight}>
      <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3">
        <div className="flex flex-wrap gap-x-4.5 gap-y-1.5 text-sm text-ink-2 [&>span]:inline-flex [&>span]:items-center [&>span]:gap-2">
          <span><i className="h-[3px] w-[1.1rem] rounded-[2px]" style={{ background: 'var(--series-observed)' }} />Observed hourly mean</span>
          {points.length > 0 && <span><i className="h-[3px] w-[1.1rem] rounded-[2px]" style={{ background: 'var(--series-forecast)' }} />Forecast</span>}
          {points.some((p) => p.low_mgL !== null) && <span><i className="h-[0.7rem] w-[1.1rem] rounded-[3px]" style={{ background: 'var(--series-forecast)', opacity: 0.4 }} />90% range, +1 h only</span>}
          {hours.some((o) => o.do_mgL !== null && o.coverage < FULL) && <span><svg width="12" height="12" aria-hidden="true"><circle cx="6" cy="6" r="4" fill="none" stroke="var(--series-observed)" strokeWidth="2" /></svg>Partial hour</span>}
          <span><i className="h-[0.7rem] w-[1.1rem] rounded-[3px]" style={{ background: 'var(--night)', outline: '1px solid var(--line)' }} />18:00 to 06:00</span>
        </div>
        <button type="button" className={ui.btn('quiet')} onClick={() => setTable(!table)} aria-pressed={table}><span className={ui.face}>{table ? 'Show chart' : 'Show table'}</span></button>
      </div>
      {table ? <DataTable slots={slots} zone={pond.timezone} /> : (
        <div ref={box} className="chart relative min-w-0 touch-pan-y" style={{ height: H }} tabIndex={0} role="group" aria-label="Oxygen over time. Use the arrow keys to read values." onPointerMove={pick} onPointerDown={pick} onPointerLeave={() => setAt(null)} onKeyDown={step} onBlur={() => setAt(null)}>
          {w > 0 && <>
            <svg className="absolute inset-0 block overflow-visible" width={width} height={H} aria-hidden="true">
              {model.nights.map(([a, b]) => <rect key={a} x={x(a)} width={x(b) - x(a)} y={M.top} height={h} fill="var(--night)" />)}
              {ticks(model.max).map((v) => <g key={v}><line className="stroke-line" x1={M.left} x2={M.left + w} y1={y(v)} y2={y(v)} /><text className={axis} x={M.left - 8} y={y(v) + 4} textAnchor="end">{v}</text></g>)}
              {shownTicks.map((t) => <text className={axis} key={t} x={x(t)} y={H - 8} textAnchor="middle">{localHour(t, pond.timezone) === 0 ? day(t, pond.timezone) : clock(t, pond.timezone)}</text>)}
              {forecast && <line className="stroke-ink-3" x1={x(Date.parse(forecast.issue_time))} x2={x(Date.parse(forecast.issue_time))} y1={M.top} y2={M.top + h} />}
              {forecast && <text className={axis} x={x(Date.parse(forecast.issue_time)) - 6} y={M.top + 12} textAnchor="end">Forecast made</text>}
            </svg>
            <svg key={drawKey} className="pointer-events-none absolute inset-0 block overflow-visible draw" width={width} height={H} aria-hidden="true">
              <clipPath id={clip}><rect x={M.left} y={0} width={w} height={H} /></clipPath>
              <g clipPath={`url(#${clip})`}>
                {model.lines.map((run) => run.length === 1
                  ? <circle key={run[0].t} className="fill-observed" cx={x(run[0].t)} cy={y(run[0].v)} r="3" />
                  : <path key={run[0].t} className="fill-none stroke-observed stroke-2 [stroke-linecap:round] [stroke-linejoin:round]" d={run.map((p, i) => `${i ? 'L' : 'M'}${x(p.t)} ${y(p.v)}`).join('')} />)}
              </g>
              {hours.filter((o) => o.do_mgL !== null && o.coverage < FULL).map((o) => <circle key={'p' + o.start} className="fill-surface stroke-observed stroke-2" cx={x(middle(o.start))} cy={y(o.do_mgL!)} r="4" />)}
              {path && <path className="fill-none stroke-forecast stroke-2 [stroke-linejoin:round]" d={path} />}
            </svg>
            <svg className="pointer-events-none absolute inset-0 block overflow-visible" width={width} height={H} aria-hidden="true">
              {limits.map((l) => <g key={l.name}><line className="stroke-ink-2 [stroke-width:1.5]" x1={M.left} x2={M.left + w} y1={y(l.v)} y2={y(l.v)} /><text className="fill-ink-2 stroke-surface text-xs font-semibold tabular-nums [paint-order:stroke] [stroke-width:4px]" x={M.left + w - 4} y={l.name === 'Critical limit' ? y(l.v) + 14 : y(l.v) - 5} textAnchor="end">{l.name} {l.v}</text></g>)}
              {points.map((p) => p.low_mgL !== null && p.high_mgL !== null && <line key={'r' + p.horizon_hours} className="range stroke-forecast stroke-8 opacity-28 [stroke-linecap:round] pop" x1={x(middle(p.target_start))} x2={x(middle(p.target_start))} y1={y(p.low_mgL)} y2={y(p.high_mgL)} />)}
              {points.map((p, i) => <circle key={forecast!.id + p.horizon_hours} className="fill-forecast stroke-surface stroke-2 pop" style={{ '--i': i } as React.CSSProperties} cx={x(middle(p.target_start))} cy={y(p.point_mgL!)} r="5" />)}
              <line className="stroke-ink-3 cross" x1="0" x2="0" y1={M.top} y2={M.top + h} style={{ transform: `translateX(${slot ? x(slot[0]) : 0}px)`, opacity: slot ? 1 : 0 }} />
              {slot && slot[1].observed !== null && <circle cx={x(slot[0])} cy={y(slot[1].observed)} r="5" fill="var(--series-observed)" stroke="var(--surface)" strokeWidth="2" />}
            </svg>
            {slot && <div className="tip pointer-events-none absolute top-0 left-0 min-w-38 rounded-[10px] bg-ink px-3 py-2 text-[0.85rem]/[1.45] text-page shadow-float" style={{ transform: `translate(${Math.max(0, Math.min(width - 168, x(slot[0]) + (x(slot[0]) > width - 190 ? -180 : 12)))}px, 8px)` }}>
              <Values slot={slot} zone={pond.timezone} />
            </div>}
          </>}
        </div>
      )}
      <div className="sr-only" role="status" aria-live="polite">{slot && <Values slot={slot} zone={pond.timezone} />}</div>
      <figcaption className="text-sm text-ink-3">Oxygen in mg/L, as reported by the sensor. Times are in {pond.timezone.replace('_', ' ')}.</figcaption>
    </figure>
  )
}

type Slot = [number, { observed: number | null; partial: boolean; forecast: number | null; low: number | null; high: number | null; chance: number | null; horizon: number | null }]

function Values({ slot: [t, s], zone }: { slot: Slot; zone: string }) {
  return (
    <>
      <div><b>{dayClock(t - HOUR / 2, zone)} to {clock(t + HOUR / 2, zone)}</b></div>
      {(s.observed !== null || s.horizon === null) && <div>Observed {s.observed === null ? 'missing' : fixed(s.observed) + ' mg/L'}{s.partial && s.observed !== null && ', partial hour'}</div>}
      {s.horizon !== null && <div>Forecast +{s.horizon} h {s.forecast === null ? 'not shown' : fixed(s.forecast) + ' mg/L'}</div>}
      {s.low !== null && <div>90% range {fixed(s.low)} to {fixed(s.high)}</div>}
      {s.chance !== null && <div>Chance of low oxygen {percent(s.chance)}</div>}
    </>
  )
}

function DataTable({ slots, zone }: { slots: Slot[]; zone: string }) {
  return (
    <div className="overflow-x-auto arrive" style={{ maxHeight: H, overflowY: 'auto' }} tabIndex={0} role="region" aria-label="Chart data">
      <table>
        <thead><tr><th>Hour</th><th className="text-right">Observed</th><th className="text-right">Forecast</th><th className="text-right">90% range</th><th className="text-right">Low-oxygen chance</th></tr></thead>
        <tbody>
          {[...slots].reverse().map(([t, s]) => (
            <tr key={t}><td>{dayClock(t - HOUR / 2, zone)}</td><td className="text-right">{fixed(s.observed)}{s.partial && s.observed !== null && ' (partial)'}</td><td className="text-right">{s.horizon ? (s.forecast === null ? 'not shown' : fixed(s.forecast)) : ''}</td><td className="text-right">{s.low === null ? '' : `${fixed(s.low)} to ${fixed(s.high)}`}</td><td className="text-right">{s.chance === null ? '' : percent(s.chance)}</td></tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

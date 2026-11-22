import type { CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import { useSummary } from '../api/queries'
import type { Summary } from '../api/types'
import { Column } from '../charts/column'
import { Trend } from '../charts/trend'
import { useNow } from '../lib/motion'
import { percent, STALE, stateOf } from '../lib/status'
import { ago, dayClock } from '../lib/time'
import { Badge, Empty, Failed, Icon, Roll, Skeleton } from '../ui/kit'
import * as ui from '../ui/styles'

export function Component() {
  const q = useSummary()
  const now = useNow()
  const ponds = q.data ? [...q.data.ponds].sort((a, b) => stateOf(a, now).rank - stateOf(b, now).rank) : []
  return (
    <>
      <div className={ui.head}>
        <div><h1>Ponds</h1>{ponds.length > 0 && <p>Ponds that need attention come first.</p>}</div>
        {ponds.length > 0 && <Link to="/ponds/new" viewTransition className={ui.btn()}><span className={ui.face}><Icon name="plus" />Add a pond</span></Link>}
      </div>
      {q.isPending && <div className="grid gap-3">{[0, 1, 2].map((i) => <Skeleton key={i} height="6.4rem" />)}</div>}
      {q.isError && !q.data && <Failed error={q.error} retry={() => q.refetch()} />}
      {q.data && ponds.length === 0 && (
        <div className={ui.panel}><Empty title="Add your first pond">
          <p className={ui.note}>Connect a sensor to a live pond, or import recorded readings into a demo pond.</p>
          <Link to="/ponds/new" viewTransition className={ui.btn()}><span className={ui.face}><Icon name="plus" />Add a pond</span></Link>
        </Empty></div>
      )}
      <div className="grid gap-3">{ponds.map((p, i) => <Row key={p.id} pond={p} now={now} index={i} />)}</div>
      {ponds.length > 0 && <p className={ui.note} style={{ marginTop: '1.25rem' }}>No open alerts means that no limit you set was crossed in the readings received. It does not mean that a pond is safe.</p>}
    </>
  )
}

function Row({ pond: p, now, index }: { pond: Summary; now: number; index: number }) {
  const state = stateOf(p, now)
  const old = p.mode === 'live' && p.latest_at !== null && now - Date.parse(p.latest_at) >= STALE
  const chance = p.forecast_status === 'ok' && p.highest_probability !== null && !old ? p.highest_probability : null
  return (
    <Link to={`/ponds/${p.id}`} viewTransition className="row relative grid grid-cols-[4.5rem_minmax(10rem,1.3fr)_minmax(8rem,1fr)_minmax(12rem,1.6fr)_auto] items-center gap-5 rounded-panel border border-line bg-surface px-[1.1rem] py-[0.9rem] text-inherit no-underline [contain:layout_paint] after:pointer-events-none after:absolute after:-inset-px after:rounded-[inherit] after:border after:border-accent max-lg:grid-cols-[3.75rem_minmax(0,1fr)_auto] max-md:grid-cols-[3.75rem_minmax(0,1fr)] max-md:gap-x-4 max-md:gap-y-2.5 [&_h2]:wrap-anywhere arrive" style={{ '--i': index } as CSSProperties}
      onClick={(e) => { const name = e.currentTarget.querySelector('h2'); if (name) name.style.setProperty('view-transition-name', 'pond-name') }}>
      <Column value={p.latest_do_mgL} limits={p} dim={old} className="max-md:row-span-3 max-md:h-full max-md:min-h-18" />
      <div>
        <h2>{p.name}</h2>
        <p className="text-sm text-ink-3">{p.latest_at === null ? 'No readings yet' : p.mode === 'demo' ? `Recorded ${dayClock(p.latest_at, p.timezone)}` : ago(p.latest_at, now)}</p>
      </div>
      <div className="text-2xl/[1.15] font-[650] tracking-[-0.02em]"><Roll value={p.latest_do_mgL} /> <small className="text-sm font-medium tracking-normal text-ink-3">mg/L oxygen</small></div>
      <div className={ui.cx(ui.tight, 'max-lg:col-[2/-1] max-md:col-[2]')}>
        <span className={ui.actions}>{p.mode === 'demo' && <Badge tone="demo">Demo</Badge>}<Badge tone={state.tone}>{state.label}</Badge></span>
        {chance !== null && <span className="text-sm text-ink-3">Highest low-oxygen chance in the latest forecast: {percent(chance)}</span>}
        {p.trend_do_mgL && p.trend_do_mgL.filter((v) => v !== null).length > 1 && <span className="block max-lg:hidden"><Trend values={p.trend_do_mgL} low={p.do_low} /></span>}
      </div>
      <Icon name="arrow" className="nudge max-md:hidden" />
    </Link>
  )
}

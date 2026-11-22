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

export function Component() {
  const q = useSummary()
  const now = useNow()
  const ponds = q.data ? [...q.data.ponds].sort((a, b) => stateOf(a, now).rank - stateOf(b, now).rank) : []
  return (
    <>
      <div className="head">
        <div><h1>Ponds</h1>{ponds.length > 0 && <p>Ponds that need attention come first.</p>}</div>
        {ponds.length > 0 && <Link to="/ponds/new" viewTransition className="btn"><span className="face"><Icon name="plus" />Add a pond</span></Link>}
      </div>
      {q.isPending && <div className="ponds">{[0, 1, 2].map((i) => <Skeleton key={i} height="6.4rem" />)}</div>}
      {q.isError && !q.data && <Failed error={q.error} retry={() => q.refetch()} />}
      {q.data && ponds.length === 0 && (
        <div className="panel"><Empty title="Add your first pond">
          <p className="note">Connect a sensor to a live pond, or import recorded readings into a demo pond.</p>
          <Link to="/ponds/new" viewTransition className="btn"><span className="face"><Icon name="plus" />Add a pond</span></Link>
        </Empty></div>
      )}
      <div className="ponds">{ponds.map((p, i) => <Row key={p.id} pond={p} now={now} index={i} />)}</div>
      {ponds.length > 0 && <p className="note" style={{ marginTop: '1.25rem' }}>No open alerts means that no limit you set was crossed in the readings received. It does not mean that a pond is safe.</p>}
    </>
  )
}

function Row({ pond: p, now, index }: { pond: Summary; now: number; index: number }) {
  const state = stateOf(p, now)
  const old = p.mode === 'live' && p.latest_at !== null && now - Date.parse(p.latest_at) >= STALE
  const chance = p.forecast_status === 'ok' && p.highest_probability !== null && !old ? p.highest_probability : null
  return (
    <Link to={`/ponds/${p.id}`} viewTransition className="row arrive" style={{ '--i': index } as CSSProperties}
      onClick={(e) => { const name = e.currentTarget.querySelector('h2'); if (name) name.style.setProperty('view-transition-name', 'pond-name') }}>
      <Column value={p.latest_do_mgL} limits={p} dim={old} />
      <div>
        <h2>{p.name}</h2>
        <p className="small muted">{p.latest_at === null ? 'No readings yet' : p.mode === 'demo' ? `Recorded ${dayClock(p.latest_at, p.timezone)}` : ago(p.latest_at, now)}</p>
      </div>
      <div className="value"><Roll value={p.latest_do_mgL} /> <small>mg/L oxygen</small></div>
      <div className="state-cell stack tight">
        <span className="actions">{p.mode === 'demo' && <Badge tone="demo">Demo</Badge>}<Badge tone={state.tone}>{state.label}</Badge></span>
        {chance !== null && <span className="small muted">Highest low-oxygen chance in the latest forecast: {percent(chance)}</span>}
        {p.trend_do_mgL && p.trend_do_mgL.filter((v) => v !== null).length > 1 && <span className="trend-cell"><Trend values={p.trend_do_mgL} low={p.do_low} /></span>}
      </div>
      <Icon name="arrow" className="nudge" />
    </Link>
  )
}

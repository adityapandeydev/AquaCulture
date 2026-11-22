import { useState, type CSSProperties } from 'react'
import { useForecasts, useHours, useSpecies } from '../api/queries'
import type { Forecast, Overview } from '../api/types'
import { Column } from '../charts/column'
import { OxygenChart } from '../charts/oxygen'
import { useNow } from '../lib/motion'
import { fixed, percent, reasonText, STALE, toneOf, warningText } from '../lib/status'
import { ago, dayClock, clock, HOUR, hourStart } from '../lib/time'
import { Badge, Button, Roll, Segments, Skeleton } from '../ui/kit'
import { AlertList } from './alertlist'
import { usePond } from './pond'

type Span = '24' | '48' | '168'

export function Component() {
  const o = usePond()
  const { pond } = o
  const now = useNow()
  const [span, setSpan] = useState<Span>('48')
  const [chosen, setChosen] = useState<string | null>(null)
  const forecasts = useForecasts(pond.id)
  const list = forecasts.data ?? []
  const index = Math.max(0, chosen === null ? 0 : list.findIndex((f) => f.id === chosen))
  const forecast: Forecast | null = list[index] ?? o.forecast

  // A live chart ends at the present. A demo chart is centred on the forecast being replayed.
  const anchor = forecast && (pond.mode === 'demo' || chosen !== null) ? Date.parse(forecast.issue_time)
    : pond.mode === 'live' ? hourStart(now, pond.timezone)
    : o.latest ? hourStart(Date.parse(o.latest.observed_at), pond.timezone) + HOUR : null
  const from = anchor === null ? null : anchor - Number(span) * HOUR
  const to = anchor === null ? null : anchor + 13 * HOUR
  const hours = useHours(pond.id, from === null ? null : new Date(from).toISOString(), to === null ? null : new Date(to).toISOString())

  return (
    <div className="stack">
      <div className="now">
        <section className="panel arrive" aria-label="Latest reading"><Latest o={o} now={now} /></section>
        <section className="panel arrive" style={{ '--i': 1 } as CSSProperties}>
          <div className="panel-head">
            <h2>Oxygen</h2>
            <div className="actions">
              {list.length > 1 && <>
                <Button look="quiet" aria-label="Earlier forecast" disabled={index >= list.length - 1} onClick={() => setChosen(list[index + 1].id)}>Earlier</Button>
                <Button look="quiet" aria-label="Later forecast" disabled={index === 0} onClick={() => setChosen(index === 1 ? null : list[index - 1].id)}>Later</Button>
              </>}
              <Segments legend="History" hidden value={span} onChange={setSpan} options={[{ value: '24', label: '24 h' }, { value: '48', label: '48 h' }, { value: '168', label: '7 days' }]} />
            </div>
          </div>
          {anchor === null || from === null || to === null ? <p className="note">The chart appears after the first reading.</p>
            : hours.data ? <OxygenChart pond={pond} hours={hours.data} forecast={forecast} from={from} to={to} drawKey={pond.id + span} />
            : hours.isError ? <p className="note">The hourly values could not be loaded.</p> : <Skeleton height="22rem" />}
        </section>
      </div>
      <div className="two">
        <section className="panel arrive" style={{ '--i': 2 } as CSSProperties}><h2>Low-oxygen chance</h2><Chances o={o} forecast={forecast} now={now} /></section>
        <section className="panel arrive" style={{ '--i': 3 } as CSSProperties}><h2>Open alerts</h2><AlertList alerts={o.alerts} zone={pond.timezone} empty="No limit you set is crossed in the latest reading. This does not mean that the pond is safe." /></section>
      </div>
    </div>
  )
}

function Latest({ o: { pond, latest }, now }: { o: Overview; now: number }) {
  if (!latest) return <p className="note">No reading has arrived yet. {pond.mode === 'live' ? 'Add a device, then send its first reading.' : 'Import recorded readings on the Data tab.'}</p>
  const old = pond.mode === 'live' && now - Date.parse(latest.observed_at) >= STALE
  const tone = toneOf(latest.do_mgL, pond)
  return (
    <div className="gauge">
      <Column value={latest.do_mgL} limits={pond} big dim={old} />
      <div className="reading">
        <span className="small muted">Oxygen</span>
        <span className="hero"><Roll value={latest.do_mgL} digits={1} /></span>
        <span className="muted">mg/L</span>
        {tone !== 'none' && <span><Badge tone={tone}>{latest.do_mgL === 0 ? 'Zero, check the sensor' : tone === 'critical' ? 'Critical' : 'Low'}</Badge></span>}
        {old && <span><Badge tone="warning">Old reading</Badge></span>}
        <dl className="facts">
          <div><dt>pH</dt><dd>{fixed(latest.ph)}</dd></div>
          <div><dt>Temperature</dt><dd>{latest.temperature_c === null ? '–' : fixed(latest.temperature_c, 1) + ' °C'}</dd></div>
          <div><dt>{pond.mode === 'demo' ? 'Recorded' : 'Received'}</dt><dd>{pond.mode === 'demo' ? dayClock(latest.observed_at, pond.timezone) : ago(latest.observed_at, now)}</dd></div>
        </dl>
      </div>
    </div>
  )
}

function Chances({ o: { pond }, forecast, now }: { o: Overview; forecast: Forecast | null; now: number }) {
  const species = useSpecies()
  const supported = species.data?.find((s) => s.id === pond.species)?.forecasts
  if (supported === false) return <p className="note">There is no forecast model for this species. Readings and your own limits are still watched.</p>
  if (!forecast) return <p className="note">{pond.mode === 'live' ? 'The first forecast is made after 20 of 24 hours have readings.' : 'Make a forecast for a past hour on the Data tab.'}</p>
  if (forecast.status === 'unavailable') return (
    <div className="stack tight">
      <p className="note">No forecast was made at {dayClock(forecast.issue_time, pond.timezone)}.</p>
      <ul className="stack tight">{forecast.reasons.map((r) => <li key={r} className="note">{reasonText(r)}</li>)}</ul>
    </div>
  )
  const age = now - Date.parse(forecast.issue_time)
  const threshold = forecast.values.find((v) => v.threshold_mgL !== null)?.threshold_mgL
  return (
    <div className="stack">
      <p className="note">Made {dayClock(forecast.issue_time, pond.timezone)}. The chance that the sensor’s hourly mean is below {threshold} mg/L.{pond.mode === 'live' && age >= STALE ? ' This forecast is old.' : ''}</p>
      <div className="chances">
        {forecast.values.map((v) => (
          <div className="chance" key={v.horizon_hours}>
            <span className="small"><b>+{v.horizon_hours} h</b><br /><span className="muted">{clock(v.target_end, pond.timezone)}</span></span>
            <span className="track" role="img" aria-label={v.probability === null ? 'Not available' : percent(v.probability)}><span className="grow" style={{ transform: `scaleX(${v.probability ?? 0})` }} /></span>
            <b>{v.probability === null ? '–' : percent(v.probability)}</b>
            {v.withheld.includes('point') && <p>No value is forecast this far ahead. It failed its test.</p>}
          </div>
        ))}
      </div>
      {forecast.warnings.map((w) => <p key={w} className="note"><Badge tone="warning">Outside training</Badge> {warningText(w)}</p>)}
      <p className="note small">For research and demonstration. In tests at a 50% chance, 40 to 55% of new drops in unseen ponds were missed. A low chance does not mean that the pond is safe.</p>
    </div>
  )
}

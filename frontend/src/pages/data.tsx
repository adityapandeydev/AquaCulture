import { useState, type CSSProperties } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { refreshPond, useReadings, useSpecies } from '../api/queries'
import type { ImportReport, Overview } from '../api/types'
import { fixed, rejectionText } from '../lib/status'
import { dayClock, fullDay, HOUR, hourStart } from '../lib/time'
import { messageOf, useAction } from '../lib/action'
import { Badge, Button, Icon, Skeleton } from '../ui/kit'
import { toast } from '../ui/toast'
import { usePond } from './pond'

export function Component() {
  const o = usePond()
  return (
    <div className="stack">
      <Import o={o} />
      {o.pond.mode === 'demo' && o.extent.first && o.extent.last && <Replay o={o} />}
      <Recent o={o} />
    </div>
  )
}

function Import({ o: { pond } }: { o: Overview }) {
  const [file, setFile] = useState<File | null>(null)
  const [over, setOver] = useState(false)
  const [preview, setPreview] = useState<ImportReport | null>(null)
  const [checking, setChecking] = useState(false)
  const [problem, setProblem] = useState('')
  const check = async (f: File | undefined) => {
    if (!f) return
    setFile(f)
    setPreview(null)
    setProblem('')
    setChecking(true)
    try {
      setPreview(await api<ImportReport>(`/ponds/${pond.id}/imports`, { method: 'POST', csv: f }))
    } catch (error) {
      setProblem(messageOf(error))
    }
    setChecking(false)
  }
  const save = useAction(async () => {
    const report = await api<ImportReport>(`/ponds/${pond.id}/imports?commit=true`, { method: 'POST', csv: file! })
    toast(`${report.stored} readings were stored`)
    setPreview(null)
    setFile(null)
    await refreshPond(pond.id)
  })
  const fresh = preview ? preview.valid - preview.duplicate - preview.conflict : 0
  return (
    <section className="panel arrive">
      <h2>Import readings</h2>
      <div className="stack">
        <div className="drop" data-over={over ? '' : undefined} onDragOver={(e) => { e.preventDefault(); setOver(true) }} onDragLeave={() => setOver(false)} onDrop={(e) => { e.preventDefault(); setOver(false); void check(e.dataTransfer.files[0]) }}>
          <span className="lift"><Icon name="upload" /></span>
          <b>{file ? file.name : 'Drop a CSV file here, or choose one'}</b>
          <span className="small muted">Columns: timestamp, do_mgl, and if available ph and temperature_c. Times without an offset are read as {pond.timezone.replaceAll('_', ' ')}.</span>
          <input type="file" accept=".csv,text/csv" aria-label="CSV file" onChange={(e) => { void check(e.target.files?.[0]); e.target.value = '' }} />
        </div>
        {checking && <Skeleton height="5rem" />}
        {problem && <p className="form problem arrive" role="alert">{problem}</p>}
        {preview && (
          <div className="stack arrive">
            <dl className="figures">
              <div><dt>New readings</dt><dd>{fresh.toLocaleString()}</dd></div>
              <div><dt>Already stored</dt><dd>{preview.duplicate.toLocaleString()}</dd></div>
              <div><dt>Different from stored</dt><dd>{preview.conflict.toLocaleString()}</dd></div>
              <div><dt>Rejected rows</dt><dd>{preview.rejected.toLocaleString()}</dd></div>
            </dl>
            {preview.first && preview.last && <p className="note">From {dayClock(preview.first, pond.timezone)} to {dayClock(preview.last, pond.timezone)}, {fullDay(preview.last, pond.timezone)}. Nothing is stored yet.</p>}
            {preview.conflict > 0 && <p className="note"><Badge tone="warning">Kept as stored</Badge> Readings that differ from stored values are not replaced.</p>}
            {preview.rejections.length > 0 && <details><summary>Rejected rows</summary><ul className="small">{preview.rejections.map((r) => <li key={r.line}>Line {r.line}: {rejectionText(r.reason)}</li>)}</ul></details>}
            {save.problem && <p className="form problem" role="alert">{save.problem}</p>}
            <div className="actions"><Button state={save.state} disabled={fresh === 0} onClick={save.run}>Store {fresh.toLocaleString()} readings</Button><Button look="quiet" onClick={() => { setPreview(null); setFile(null) }}>Cancel</Button></div>
          </div>
        )}
      </div>
    </section>
  )
}

/** Replay forecasts for past hours of a demo pond. */
function Replay({ o: { pond, extent } }: { o: Overview }) {
  const navigate = useNavigate()
  const species = useSpecies()
  const first = hourStart(Date.parse(extent.first!), pond.timezone) + 24 * HOUR
  const last = hourStart(Date.parse(extent.last!), pond.timezone) + HOUR
  const steps = Math.max(0, Math.round((last - first) / HOUR))
  const [at, setAt] = useState(Math.max(0, steps - 12))
  const [count, setCount] = useState(6)
  const issue = first + Math.min(at, steps) * HOUR
  const hours = Math.max(1, Math.min(count, steps - Math.min(at, steps) + 1))
  const ask = useAction(async () => {
    const r = await api<{ queued: number }>(`/ponds/${pond.id}/forecasts`, { method: 'POST', json: { issue_time: new Date(issue).toISOString(), hours } })
    toast(r.queued ? `${r.queued} forecasts are being made` : 'These forecasts were already made', r.queued ? 'play' : 'check')
    for (const wait of [1500, 4000, 8000]) setTimeout(() => void refreshPond(pond.id), wait)
    navigate(`/ponds/${pond.id}`, { viewTransition: true })
  })
  if (steps < 1) return <section className="panel arrive"><h2>Replay a forecast</h2><p className="note">A forecast needs at least 24 hours of readings.</p></section>
  if (species.data?.find((s) => s.id === pond.species)?.forecasts === false) return null
  return (
    <section className="panel arrive" style={{ '--i': 1 } as CSSProperties}>
      <h2>Replay a forecast</h2>
      <div className="form">
        <p className="note">Choose a past hour. The forecast uses only readings from before it, so you can compare it with what happened.</p>
        <div className="field"><label htmlFor="issue">Make it at {dayClock(issue, pond.timezone)}</label><input id="issue" type="range" min={0} max={steps} value={Math.min(at, steps)} onChange={(e) => setAt(Number(e.target.value))} /></div>
        <div className="field"><label htmlFor="count">{hours === 1 ? 'One forecast' : `${hours} forecasts, one per hour`}</label><input id="count" type="range" min={1} max={24} value={count} onChange={(e) => setCount(Number(e.target.value))} /></div>
        {ask.problem && <p className="problem" role="alert">{ask.problem}</p>}
        <div><Button icon="play" state={ask.state} onClick={ask.run}>Make {hours === 1 ? 'the forecast' : 'the forecasts'}</Button></div>
      </div>
    </section>
  )
}

function Recent({ o: { pond, extent, latest } }: { o: Overview }) {
  const end = latest ? Date.parse(latest.observed_at) : null
  const q = useReadings(pond.id, end === null ? null : new Date(end - 24 * HOUR).toISOString(), end === null ? null : new Date(end + 1000).toISOString())
  return (
    <section className="panel arrive" style={{ '--i': 2 } as CSSProperties}>
      <div className="panel-head"><h2>Latest readings</h2><span className="muted">{extent.count.toLocaleString()} stored</span></div>
      {!latest ? <p className="note">No readings are stored yet.</p> : q.data ? (
        <div className="scroll tall" tabIndex={0} role="region" aria-label="Latest readings">
          <table>
            <thead><tr><th>Time</th><th className="num">Oxygen, mg/L</th><th className="num">pH</th><th className="num">Temperature, °C</th><th>Source</th></tr></thead>
            <tbody>{q.data.map((r) => <tr key={r.observed_at}><td>{dayClock(r.observed_at, pond.timezone)}</td><td className="num">{fixed(r.do_mgL)}</td><td className="num">{fixed(r.ph)}</td><td className="num">{fixed(r.temperature_c, 1)}</td><td>{r.source === 'device' ? 'Device' : 'Import'}</td></tr>)}</tbody>
          </table>
        </div>
      ) : <Skeleton height="12rem" />}
    </section>
  )
}

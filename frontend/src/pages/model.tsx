import type { CSSProperties } from 'react'
import { useModel } from '../api/queries'
import { Badge, Icon, Skeleton } from '../ui/kit'
import * as ui from '../ui/styles'

// Copied from docs/models/results.md, the one-time test of 22 November 2026.
const test = [
  { h: 1, naive: 0.742, model: 0.662, gain: 10.7, range: '8.0 to 13.9%', need: 5, recall: 45, drops: 11 },
  { h: 3, naive: 1.34, model: 1.078, gain: 19.6, range: '15.2 to 23.7%', need: 10, recall: 50, drops: 28 },
  { h: 6, naive: 1.603, model: 1.379, gain: 14.0, range: '2.7 to 24.2%', need: 10, recall: 60, drops: 35 },
  { h: 12, naive: 1.601, model: 1.536, gain: 4.1, range: '-9.7 to 17.0%', need: 10, recall: 58, drops: 36 },
]
const released: Record<number, { point: boolean; interval: boolean; alert: boolean }> = {
  1: { point: true, interval: true, alert: true }, 3: { point: true, interval: false, alert: true }, 6: { point: true, interval: false, alert: true }, 12: { point: false, interval: false, alert: true },
}

const Mark = ({ ok }: { ok: boolean }) => <span className={ui.badge(ok ? 'good' : 'neutral')}><Icon name={ok ? 'check' : 'cross'} />{ok ? 'Shown' : 'Withheld'}</span>

export function Component() {
  const q = useModel()
  return (
    <>
      <div className={ui.head}>
        <div><h1>Forecast model</h1><p>What it may show, how it was tested and where it falls short.</p></div>
        {q.isPending ? <Skeleton height="2rem" width="12rem" /> : q.data?.available ? <Badge tone="neutral">Running, {q.data.model?.model_id}</Badge> : <Badge tone="warning">Forecast service is not answering</Badge>}
      </div>
      <div className={ui.stack}>
        <section className={ui.cx(ui.panel, 'arrive')}>
          <h2>What is shown</h2>
          <div className="overflow-x-auto"><table>
            <thead><tr><th>Ahead</th><th>Oxygen value</th><th>90% range</th><th>Low-oxygen chance</th></tr></thead>
            <tbody>{Object.entries(released).map(([h, r]) => <tr key={h}><td>+{h} h</td><td><Mark ok={r.point} /></td><td><Mark ok={r.interval} /></td><td><Mark ok={r.alert} /></td></tr>)}</tbody>
          </table></div>
          <p className={ui.note} style={{ marginTop: '0.9rem' }}>An output is shown only if it passed limits that were fixed before the test. The forecast service enforces this.</p>
        </section>
        <section className={ui.cx(ui.panel, 'arrive')} style={{ '--i': 1 } as CSSProperties}>
          <h2>Test on ponds it had never seen</h2>
          <div className="overflow-x-auto"><table>
            <thead><tr><th>Ahead</th><th className="text-right">Best simple method, mg/L</th><th className="text-right">Model, mg/L</th><th className="text-right">Gain</th><th className="text-right">Likely range of gain</th><th className="text-right">Required</th></tr></thead>
            <tbody>{test.map((r) => <tr key={r.h}><td>+{r.h} h</td><td className="text-right">{r.naive.toFixed(2)}</td><td className="text-right">{r.model.toFixed(2)}</td><td className="text-right"><b>{r.gain.toFixed(1)}%</b></td><td className="text-right">{r.range}</td><td className="text-right">{r.need}%</td></tr>)}</tbody>
          </table></div>
          <p className={ui.note} style={{ marginTop: '0.9rem' }}>Four carp ponds, 24 to 30 January 2026. Values are mean absolute errors against the sensor. The test was run once.</p>
        </section>
        <div className={ui.two}>
          <section className={ui.cx(ui.panel, 'arrive')} style={{ '--i': 2 } as CSSProperties}>
            <h2>New low-oxygen drops caught</h2>
            <div className={ui.chances}>{test.map((r) => (
              <div className={ui.chance} key={r.h}><b>+{r.h} h</b><span className={ui.track} role="img" aria-label={`${r.recall}% of ${r.drops} drops`}><span className={ui.bar} style={{ transform: `scaleX(${r.recall / 100})` }} /></span><b>{r.recall}%</b><p>of {r.drops} drops below 3 mg/L</p></div>
            ))}</div>
            <p className={ui.cx(ui.note, 'text-sm')} style={{ marginTop: '0.9rem' }}>At a 50% chance. The rest were missed, so a missing warning never means that a pond is safe.</p>
          </section>
          <section className={ui.cx(ui.panel, 'arrive')} style={{ '--i': 3 } as CSSProperties}>
            <h2>Limits</h2>
            <ul className={ui.cx(ui.tight, ui.note)}>
              <li>Trained on Rohu and Catla ponds in one district, during one winter. Other species, places and seasons are untested.</li>
              <li>It forecasts what the sensor will report. Against 39 Winkler titrations, those sensors differed by 2.73 mg/L on average.</li>
              <li>It needs oxygen, pH and temperature readings.</li>
              <li>At +6 h the gain varies by pond. One pond it already knew was forecast 29% worse than by a simple method.</li>
              <li>It is for research and demonstration. It cannot replace checking the pond.</li>
            </ul>
          </section>
        </div>
      </div>
    </>
  )
}

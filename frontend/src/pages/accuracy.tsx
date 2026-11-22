import { useAccuracy, usePondAlerts } from '../api/queries'
import { fixed } from '../lib/status'
import { Empty, Failed, Skeleton } from '../ui/kit'
import { AlertList } from './alertlist'
import { usePond } from './pond'
import type { CSSProperties } from 'react'

export function Component() {
  const { pond } = usePond()
  const q = useAccuracy(pond.id)
  const history = usePondAlerts(pond.id)
  return (
    <div className="stack">
      <section className="panel arrive">
        <h2>Past forecasts against the sensor</h2>
        {q.isPending ? <Skeleton height="10rem" /> : q.isError ? <Failed error={q.error} retry={() => q.refetch()} /> : q.data.length === 0
          ? <Empty title="Nothing to compare yet"><p className="note">Results appear once the forecast hours have been observed.</p></Empty>
          : <div className="stack">
              <div className="scroll"><table>
                <thead><tr><th>Ahead</th><th className="num">Compared</th><th className="num">Mean error, mg/L</th><th className="num">“No change” error, mg/L</th><th className="num">Inside 90% range</th><th className="num">Low-oxygen hours</th></tr></thead>
                <tbody>{q.data.map((r) => (
                  <tr key={r.horizon_hours}><td>+{r.horizon_hours} h</td><td className="num">{r.compared}</td><td className="num">{r.points ? fixed(r.mae_mgL) : 'not shown'}</td><td className="num">{r.points ? fixed(r.persistence_mae_mgL) : ''}</td><td className="num">{r.interval_coverage === null ? '' : Math.round(r.interval_coverage * 100) + '%'}</td><td className="num">{r.events}</td></tr>
                ))}</tbody>
              </table></div>
              <p className="note">“No change” assumes that oxygen stays at its last hourly value. Both are compared with the sensor, whose own error is not included. {Math.min(...q.data.map((r) => r.compared)) < 30 ? 'There are few comparisons so far, so these numbers can change a lot.' : ''}</p>
            </div>}
      </section>
      <section className="panel arrive" style={{ '--i': 1 } as CSSProperties}>
        <h2>Alert history</h2>
        {history.data ? <AlertList alerts={history.data} zone={pond.timezone} empty="No alert has been opened for this pond." /> : <Skeleton height="6rem" />}
      </section>
    </div>
  )
}

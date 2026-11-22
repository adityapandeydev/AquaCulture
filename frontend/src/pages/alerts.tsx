import { useOpenAlerts, useSummary } from '../api/queries'
import { Failed, Skeleton } from '../ui/kit'
import { AlertList } from './alertlist'

export function Component() {
  const q = useOpenAlerts()
  const ponds = useSummary()
  const pond = (id: string) => ponds.data?.ponds.find((p) => p.id === id)
  return (
    <>
      <div className="head"><div><h1>Open alerts</h1><p>Across all your ponds. Alerts close by themselves when a new reading is back within your limits.</p></div></div>
      <section className="panel arrive">
        {q.isPending ? <div className="stack"><Skeleton height="3.5rem" /><Skeleton height="3.5rem" /></div>
          : q.isError && !q.data ? <Failed error={q.error} retry={() => q.refetch()} />
          : <AlertList alerts={q.data ?? []} zone={(a) => pond(a.pond_id)?.timezone ?? 'UTC'} pondName={(a) => { const p = pond(a.pond_id); return p && (p.mode === 'demo' ? `${p.name} (demo)` : p.name) }} empty="No limit you set is crossed in the latest readings. This does not mean that your ponds are safe." />}
      </section>
    </>
  )
}

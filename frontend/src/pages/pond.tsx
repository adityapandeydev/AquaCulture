import { NavLink, Outlet, useOutletContext, useParams } from 'react-router-dom'
import { useOverview, useSpecies } from '../api/queries'
import type { Overview } from '../api/types'
import { Badge, Failed, Skeleton } from '../ui/kit'
import { BackLink } from '../ui/shell'
import * as ui from '../ui/styles'

// eslint-disable-next-line react-refresh/only-export-components
export const usePond = () => useOutletContext<Overview>()

export function Component() {
  const { id = '' } = useParams()
  // The key gives each pond its own page state.
  return <Page key={id} id={id} />
}

function Page({ id }: { id: string }) {
  const q = useOverview(id)
  const species = useSpecies()
  if (q.isError && !q.data) return <Failed error={q.error} retry={() => q.refetch()} />
  const pond = q.data?.pond
  const tabs = [{ to: '', label: 'Now' }, { to: 'data', label: 'Data' }, ...(pond?.mode === 'live' ? [{ to: 'devices', label: 'Devices' }] : []), { to: 'accuracy', label: 'Accuracy' }, { to: 'settings', label: 'Settings' }]
  return (
    <>
      <div className={ui.head}>
        <div>
          <h1 className="hero-name">{pond?.name ?? 'Pond'}</h1>
          {pond && <p className={ui.actions}>
            {pond.mode === 'demo' && <Badge tone="demo">Demo, recorded data</Badge>}
            <span>{species.data?.find((s) => s.id === pond.species)?.name}</span>
          </p>}
        </div>
        <BackLink to="/">All ponds</BackLink>
      </div>
      <nav className="mb-6 flex gap-1 overflow-x-auto border-b border-line [scrollbar-width:none]" aria-label="Pond">
        {tabs.map((t) => (
          <NavLink key={t.to} to={t.to || `/ponds/${id}`} end={!t.to} viewTransition className={({ isActive }) => ui.cx('relative px-3.5 py-2.5 font-[570] whitespace-nowrap no-underline', isActive ? 'text-ink' : 'text-ink-2')}>
            {({ isActive }) => <>{t.label}{isActive && <span className="tab-mark absolute inset-x-2.5 bottom-0 h-[3px] rounded-t-[3px] bg-accent" />}</>}
          </NavLink>
        ))}
      </nav>
      {q.data ? <Outlet context={q.data} /> : <div className={ui.now}><Skeleton height="20rem" /><Skeleton height="20rem" /></div>}
    </>
  )
}

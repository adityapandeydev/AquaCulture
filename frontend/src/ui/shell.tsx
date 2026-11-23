import { useEffect, useState } from 'react'
import { NavLink, Navigate, Outlet, ScrollRestoration, useLocation, useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { api } from '../api/client'
import { queryClient, useMe, useOpenAlerts } from '../api/queries'
import { finishBoot } from '../lib/motion'
import { Failed, Icon, type IconName } from './kit'
import * as ui from './styles'

export const Drop = () => (
  <svg width="26" height="26" viewBox="0 0 32 32" aria-hidden="true"><path fill="#bdf0e4" d="M16 3c5 7 9 11 9 16.500a9 9 0 0 1-18 0C7 14 11 10 16 3z" /><path fill="#2c8f8c" d="M7.300 18c3-1.700 5.700-1.700 8.700 0s5.700 1.700 8.700 0c.2.600.3 1 .3 1.500a9 9 0 0 1-18 0c0-.5.1-.9.3-1.500z" /></svg>
)

const away = 'opacity-0 [transform:rotate(60deg)_scale(0.7)]'

function useTheme() {
  const [dark, setDark] = useState(() => {
    const chosen = document.documentElement.dataset.theme
    return chosen ? chosen === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches
  })
  const toggle = () => {
    const next = dark ? 'light' : 'dark'
    document.documentElement.dataset.theme = next
    try { localStorage.setItem('theme', next) } catch { /* private mode */ }
    setDark(!dark)
  }
  return { dark, toggle }
}

function ThemeButton() {
  const { dark, toggle } = useTheme()
  return (
    <button type="button" className={ui.cx(ui.btn('ghost'), 'justify-start max-md:px-2.5')} onClick={toggle} aria-label={dark ? 'Use the light theme' : 'Use the dark theme'}>
      <span className={ui.face}><span className="relative inline-block size-[1.15em]"><Icon name="sun" className={ui.cx('sun absolute inset-0', !dark && away)} /><Icon name="moon" className={ui.cx('moon absolute inset-0', dark && away)} /></span><span className="max-md:hidden">{dark ? 'Light theme' : 'Dark theme'}</span></span>
    </button>
  )
}

function Item({ to, icon, label, count, also }: { to: string; icon: IconName; label: string; count?: number; also?: string }) {
  const { pathname } = useLocation()
  const inside = also !== undefined && pathname.startsWith(also)
  return (
    <NavLink to={to} end viewTransition className={({ isActive }) => ui.cx('press relative flex items-center gap-3 rounded-small px-3 py-2.5 font-[550] no-underline hover:text-rail-ink max-md:flex-col max-md:gap-0.5 max-md:px-1 max-md:py-1.5 max-md:text-xs', isActive || inside ? 'text-rail-ink' : 'text-rail-muted')}>
      {({ isActive }) => <>
        {(isActive || inside) && <span className="rail-mark absolute inset-0 rounded-[inherit] bg-rail-mark" />}
        <Icon name={icon} className="relative" /><span className="relative">{label}</span>
        {!!count && <span className="relative ml-auto min-w-6 rounded-full bg-critical px-1.5 text-center text-[0.8rem] leading-6 text-white tabular-nums max-md:absolute max-md:top-0.5 max-md:right-[18%] max-md:m-0 max-md:min-w-5 max-md:leading-5 beacon" key={count}>{count}<span className="sr-only"> open</span></span>}
      </>}
    </NavLink>
  )
}

function useOnline() {
  const [online, setOnline] = useState(navigator.onLine)
  useEffect(() => {
    const update = () => setOnline(navigator.onLine)
    addEventListener('online', update)
    addEventListener('offline', update)
    return () => { removeEventListener('online', update); removeEventListener('offline', update) }
  }, [])
  return online
}

export function Shell() {
  const me = useMe()
  const location = useLocation()
  useEffect(() => { if (!me.isPending) finishBoot() }, [me.isPending])
  if (me.isPending) return null
  if (me.isError) return <main className={ui.page}><Failed error={me.error} retry={() => me.refetch()} /></main>
  if (!me.data) return <Navigate to="/sign-in" replace state={{ from: location.pathname }} />
  return <Inside name={me.data.name} />
}

function Inside({ name }: { name: string }) {
  const alerts = useOpenAlerts()
  const online = useOnline()
  const navigate = useNavigate()
  const out = useMutation({
    mutationFn: () => api('/auth/logout', { method: 'POST' }),
    onSuccess: () => { queryClient.clear(); queryClient.setQueryData(['me'], null); navigate('/sign-in', { viewTransition: true }) },
  })
  const urgent = alerts.data?.filter((a) => a.acknowledged_at === null).length
  return (
    <div className="grid min-h-dvh grid-cols-[15rem_minmax(0,1fr)] max-md:grid-cols-1 max-md:pb-17">
      <aside className="sticky top-0 flex h-dvh flex-col gap-7 bg-rail px-3.5 py-5 text-rail-ink max-md:fixed max-md:inset-x-0 max-md:top-auto max-md:bottom-0 max-md:z-20 max-md:h-auto max-md:flex-row max-md:items-center max-md:gap-1 max-md:px-2 max-md:pt-1.5 max-md:pb-[calc(0.35rem+env(safe-area-inset-bottom))] [&_:focus-visible]:outline-rail-ink">
        <NavLink to="/" className={ui.cx(ui.brand, 'max-md:hidden')} viewTransition><Drop />AquaTech</NavLink>
        <nav aria-label="Main" className="grid gap-0.5 max-md:flex-1 max-md:auto-cols-fr max-md:grid-flow-col">
          <Item to="/" icon="ponds" label="Ponds" also="/ponds" />
          <Item to="/alerts" icon="bell" label="Alerts" count={urgent} />
          <Item to="/model" icon="model" label="Model" />
        </nav>
        <div className="mt-auto grid gap-2 max-md:m-0 max-md:grid-flow-col max-md:gap-0">
          <span className="truncate px-3 text-sm text-rail-muted max-md:hidden">{name}</span>
          <ThemeButton />
          <button type="button" className={ui.cx(ui.btn('ghost'), 'justify-start max-md:px-2.5')} onClick={() => out.mutate()} disabled={out.isPending} aria-label="Sign out"><span className={ui.face}><Icon name="exit" /><span className="max-md:hidden">Sign out</span></span></button>
        </div>
      </aside>
      <div>
        {!online && <p className="bg-warning-wash px-4 py-2 text-center font-[550] text-warning-ink arrive" role="status">You are offline. Values on screen may be old.</p>}
        <main className={ui.page}><Outlet /></main>
      </div>
      <ScrollRestoration />
    </div>
  )
}

export const BackLink = ({ to, children }: { to: string; children: string }) => (
  <NavLink to={to} viewTransition className={ui.btn('quiet')}><span className={ui.face}><Icon name="back" />{children}</span></NavLink>
)


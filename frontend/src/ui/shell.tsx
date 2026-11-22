import { useEffect, useState } from 'react'
import { NavLink, Navigate, Outlet, ScrollRestoration, useLocation, useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { api } from '../api/client'
import { queryClient, useMe, useOpenAlerts } from '../api/queries'
import { finishBoot } from '../lib/motion'
import { Button, Failed, Icon, type IconName } from './kit'

export const Drop = () => (
  <svg width="26" height="26" viewBox="0 0 32 32" aria-hidden="true"><path fill="#bdf0e4" d="M16 3c5 7 9 11 9 16.500a9 9 0 0 1-18 0C7 14 11 10 16 3z" /><path fill="#2c8f8c" d="M7.300 18c3-1.700 5.700-1.700 8.700 0s5.700 1.700 8.700 0c.2.600.3 1 .3 1.500a9 9 0 0 1-18 0c0-.5.1-.9.3-1.500z" /></svg>
)

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

export function ThemeButton() {
  const { dark, toggle } = useTheme()
  return (
    <button type="button" className="btn ghost" onClick={toggle} aria-label={dark ? 'Use the light theme' : 'Use the dark theme'}>
      <span className="face"><span className="theme" data-dark={dark}><Icon name="sun" className="sun" /><Icon name="moon" className="moon" /></span><span className="label">{dark ? 'Light theme' : 'Dark theme'}</span></span>
    </button>
  )
}

function Item({ to, icon, label, count, also }: { to: string; icon: IconName; label: string; count?: number; also?: string }) {
  const { pathname } = useLocation()
  const inside = also !== undefined && pathname.startsWith(also)
  return (
    <NavLink to={to} end viewTransition className={({ isActive }) => 'press' + (isActive || inside ? ' active' : '')}>
      {({ isActive }) => <>
        {(isActive || inside) && <span className="rail-mark" />}
        <Icon name={icon} /><span>{label}</span>
        {!!count && <span className="count beacon" key={count}>{count}<span className="sr"> open</span></span>}
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
  if (me.isError) return <main><Failed error={me.error} retry={() => me.refetch()} /></main>
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
    <div className="shell">
      <aside className="rail">
        <NavLink to="/" className="brand" viewTransition><Drop />AquaTech</NavLink>
        <nav aria-label="Main">
          <Item to="/" icon="ponds" label="Ponds" also="/ponds" />
          <Item to="/alerts" icon="bell" label="Alerts" count={urgent} />
          <Item to="/model" icon="model" label="Model" />
        </nav>
        <div className="foot">
          <span className="who">{name}</span>
          <ThemeButton />
          <button type="button" className="btn ghost" onClick={() => out.mutate()} disabled={out.isPending} aria-label="Sign out"><span className="face"><Icon name="exit" /><span className="label">Sign out</span></span></button>
        </div>
      </aside>
      <div>
        {!online && <p className="offline arrive" role="status">You are offline. Values on screen may be old.</p>}
        <main><Outlet /></main>
      </div>
      <ScrollRestoration />
    </div>
  )
}

export const PageFailed = ({ error }: { error: unknown }) => (
  <main><Failed error={error} retry={() => location.reload()} /></main>
)

export const BackLink = ({ to, children }: { to: string; children: string }) => (
  <NavLink to={to} viewTransition className="btn quiet"><span className="face"><Icon name="back" />{children}</span></NavLink>
)

export { Button }

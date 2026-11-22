import { Link, useRouteError } from 'react-router-dom'
import { finishBoot } from '../lib/motion'
import * as ui from './styles'

export function Broken() {
  const error = useRouteError()
  console.error(error)
  finishBoot()
  return (
    <main className={ui.page}><div className={ui.cx(ui.emptyState, 'arrive')} role="alert">
      <h1>This page could not be shown</h1>
      <p className={ui.note}>Reload to try again. If it keeps happening, the app may have been updated.</p>
      <button type="button" className={ui.btn()} onClick={() => location.reload()}><span className={ui.face}>Reload</span></button>
    </div></main>
  )
}

export const Missing = () => (
  <div className={ui.cx(ui.emptyState, 'arrive')}><h1>Nothing is here</h1><Link to="/" viewTransition className={ui.btn()}><span className={ui.face}>All ponds</span></Link></div>
)

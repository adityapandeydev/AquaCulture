import { Link, useRouteError } from 'react-router-dom'
import { finishBoot } from '../lib/motion'

export function Broken() {
  const error = useRouteError()
  console.error(error)
  finishBoot()
  return (
    <main><div className="empty-state arrive" role="alert">
      <h1>This page could not be shown</h1>
      <p className="note">Reload to try again. If it keeps happening, the app may have been updated.</p>
      <button type="button" className="btn" onClick={() => location.reload()}><span className="face">Reload</span></button>
    </div></main>
  )
}

export const Missing = () => (
  <div className="empty-state arrive"><h1>Nothing is here</h1><Link to="/" viewTransition className="btn"><span className="face">All ponds</span></Link></div>
)

import { useState, type CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { refreshPond } from '../api/queries'
import type { Alert } from '../api/types'
import { dayClock } from '../lib/time'
import { messageOf } from '../lib/action'
import { Button, Icon } from '../ui/kit'
import { toast } from '../ui/toast'
import * as ui from '../ui/styles'

const origins = { observed: 'From a reading', forecast: 'From a forecast', system: 'From data checks' }

export function AlertList({ alerts, zone, empty, pondName }: { alerts: Alert[]; zone: string | ((a: Alert) => string); empty: string; pondName?: (a: Alert) => string | undefined }) {
  if (alerts.length === 0) return <p className={ui.note}>{empty}</p>
  return <ul>{alerts.map((a, i) => <Item key={a.id} alert={a} zone={typeof zone === 'string' ? zone : zone(a)} pond={pondName?.(a)} index={i} />)}</ul>
}

function Item({ alert: a, zone, pond, index }: { alert: Alert; zone: string; pond?: string; index: number }) {
  const [state, setState] = useState<'idle' | 'busy'>('idle')
  const acknowledge = async () => {
    setState('busy')
    try {
      await api(`/alerts/${a.id}/acknowledge`, { method: 'POST' })
      await refreshPond(a.pond_id)
    } catch (error) {
      toast(messageOf(error), 'warn')
    }
    setState('idle')
  }
  const open = a.resolved_at === null
  return (
    <li className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-start gap-3.5 border-b border-line py-3.5 last:border-b-0 max-md:grid-cols-[auto_minmax(0,1fr)] max-md:[&>.btn]:col-[2] max-md:[&>.btn]:justify-self-start arrive" style={{ '--i': index } as CSSProperties}>
      <span className={ui.cx('grid size-8.5 place-items-center rounded-full', open && !a.acknowledged_at && 'beacon', !open ? 'bg-sunken text-ink-3' : a.severity === 'critical' ? 'bg-critical-wash text-critical-ink' : 'bg-warning-wash text-warning-ink')}><Icon name={a.origin === 'forecast' ? 'model' : a.origin === 'system' ? 'clock' : 'warn'} /></span>
      <div>
        {pond && <Link to={`/ponds/${a.pond_id}`} viewTransition><b>{pond}</b></Link>}
        <p>{a.message}</p>
        <p className="text-sm text-ink-3">{a.severity === 'critical' ? 'Critical. ' : 'Warning. '}{origins[a.origin]}. Opened {dayClock(a.opened_at, zone)}{a.resolved_at && `, closed ${dayClock(a.resolved_at, zone)}`}{a.acknowledged_at && '. Acknowledged'}</p>
      </div>
      {open && !a.acknowledged_at && <Button look="quiet" state={state} onClick={acknowledge}>Acknowledge</Button>}
    </li>
  )
}

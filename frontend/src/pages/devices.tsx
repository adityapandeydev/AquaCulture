import { useState, type CSSProperties, type FormEvent } from 'react'
import { api } from '../api/client'
import { queryClient, useDevices } from '../api/queries'
import type { Device } from '../api/types'
import { useNow } from '../lib/motion'
import { ago, dayClock } from '../lib/time'
import { messageOf, useAction } from '../lib/action'
import { Badge, Button, Dialog, Empty, Failed, Field, Skeleton } from '../ui/kit'
import { toast } from '../ui/toast'
import { usePond } from './pond'
import * as ui from '../ui/styles'

export function Component() {
  const { pond } = usePond()
  const q = useDevices(pond.id)
  const now = useNow()
  const [name, setName] = useState('')
  const [key, setKey] = useState<string | null>(null)
  const [revoking, setRevoking] = useState<Device | null>(null)
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['pond', pond.id, 'devices'] })
  const add = useAction(async () => {
    const r = await api<{ key: string }>(`/ponds/${pond.id}/devices`, { method: 'POST', json: { name } })
    setKey(r.key)
    setName('')
    await refresh()
  })
  const revoke = useAction(async () => {
    await api(`/devices/${revoking!.id}`, { method: 'DELETE' })
    toast(`${revoking!.name} was revoked`)
    setRevoking(null)
    await refresh()
  })
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(key!)
      toast('The key was copied')
    } catch (error) {
      toast(error instanceof Error ? 'Copying is blocked. Select the key instead.' : messageOf(error), 'warn')
    }
  }
  return (
    <div className={ui.stack}>
      <section className={ui.cx(ui.panel, 'arrive')}>
        <h2>Add a device</h2>
        <form className={ui.form} onSubmit={(e: FormEvent) => { e.preventDefault(); void add.run() }}>
          <Field label="Device name" required maxLength={80} value={name} onChange={(e) => setName(e.target.value)} hint="The device gets its own key, which can be revoked." problem={add.problem} />
          <div><Button type="submit" icon="plus" state={add.state}>Add device</Button></div>
        </form>
      </section>
      <section className={ui.cx(ui.panel, 'arrive')} style={{ '--i': 1 } as CSSProperties}>
        <h2>Devices</h2>
        {q.isPending ? <Skeleton height="6rem" /> : q.isError ? <Failed error={q.error} retry={() => q.refetch()} /> : q.data.length === 0
          ? <Empty title="No devices yet"><p className={ui.note}>Add one, then have it post readings with its key.</p></Empty>
          : <div className="overflow-x-auto"><table>
              <thead><tr><th>Name</th><th>Last contact</th><th>State</th><th /></tr></thead>
              <tbody>{q.data.map((d) => (
                <tr key={d.id}><td>{d.name}</td><td>{d.last_seen_at ? ago(d.last_seen_at, now) : 'Never'}</td>
                  <td>{d.revoked_at ? <Badge>Revoked {dayClock(d.revoked_at, pond.timezone)}</Badge> : <Badge tone={d.last_seen_at ? 'neutral' : 'warning'}>{d.last_seen_at ? 'Active' : 'Waiting'}</Badge>}</td>
                  <td className="text-right">{!d.revoked_at && <Button look="quiet" onClick={() => setRevoking(d)}>Revoke</Button>}</td></tr>
              ))}</tbody>
            </table></div>}
      </section>
      <section className={ui.cx(ui.panel, 'arrive')} style={{ '--i': 2 } as CSSProperties}>
        <h2>Send a reading</h2>
        <p className={ui.note}>Post to <code>/api/v1/ingest</code> with the header <code>Authorization: Device</code> and the key. Sending the same reading again is harmless.</p>
        <code className={ui.secret} style={{ marginTop: '0.75rem' }}>{'{"readings":[{"observed_at":"2026-01-24T00:30:00Z","do_mgL":5.4,"ph":8.1,"temperature_c":25.3}]}'}</code>
      </section>
      <Dialog open={key !== null} onClose={() => setKey(null)} title="Save this key now">
        <p className={ui.note}>It is shown only once. Anyone with it can send readings to this pond.</p>
        <code className={ui.secret}>{key}</code>
        <div className={ui.actions}><Button onClick={copy}>Copy key</Button><Button look="quiet" onClick={() => setKey(null)}>I saved it</Button></div>
      </Dialog>
      <Dialog open={revoking !== null} onClose={() => setRevoking(null)} title={`Revoke ${revoking?.name ?? 'device'}?`}>
        <p className={ui.note}>It can no longer send readings. Readings already stored are kept. This cannot be undone.</p>
        {revoke.problem && <p className={ui.cx(ui.form, ui.problem)} role="alert">{revoke.problem}</p>}
        <div className={ui.actions}><Button look="danger" state={revoke.state} onClick={revoke.run}>Revoke device</Button><Button look="quiet" onClick={() => setRevoking(null)}>Keep it</Button></div>
      </Dialog>
    </div>
  )
}

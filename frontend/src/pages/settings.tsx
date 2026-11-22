import { useState, type CSSProperties, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { queryClient, refreshPond, useSpecies } from '../api/queries'
import { useAction } from '../lib/action'
import { Button, Dialog, Field, Select } from '../ui/kit'
import { toast } from '../ui/toast'
import { draftOf, limitsOf } from './draft'
import { LimitFields } from './limits'
import { usePond } from './pond'
import * as ui from '../ui/styles'

export function Component() {
  const { pond } = usePond()
  const navigate = useNavigate()
  const species = useSpecies()
  const [name, setName] = useState(pond.name)
  const [kind, setKind] = useState(pond.species)
  const [draft, setDraft] = useState(() => draftOf(pond))
  const [asking, setAsking] = useState(false)
  const [typed, setTyped] = useState('')
  const save = useAction(async () => {
    await api(`/ponds/${pond.id}`, { method: 'PATCH', json: { name, species: kind, ...limitsOf(draft) } })
    await refreshPond(pond.id)
  })
  const remove = useAction(async () => {
    await api(`/ponds/${pond.id}`, { method: 'DELETE' })
    toast(`${pond.name} was deleted`)
    navigate('/', { viewTransition: true })
    queryClient.removeQueries({ queryKey: ['pond', pond.id] })
    await queryClient.invalidateQueries({ queryKey: ['summary'] })
    await queryClient.invalidateQueries({ queryKey: ['alerts'] })
  })
  return (
    <div className={ui.stack}>
      <form className={ui.stack} onSubmit={(e: FormEvent) => { e.preventDefault(); void save.run() }}>
        <div className={ui.two}>
        <section className={ui.cx(ui.panel, 'arrive')}>
          <h2>Pond</h2>
          <div className={ui.form}>
            <Field label="Name" required maxLength={80} value={name} onChange={(e) => setName(e.target.value)} />
            <Select label="Species" value={kind} onChange={(e) => setKind(e.target.value)}>{species.data?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</Select>
            <p className={ui.note}>{pond.mode === 'live' ? 'Live sensor' : 'Recorded demo'}, {pond.timezone.replaceAll('_', ' ')}, one reading every {pond.sampling_minutes} min. These are fixed.</p>
          </div>
        </section>
        <section className={ui.cx(ui.panel, 'arrive')} style={{ '--i': 1 } as CSSProperties}>
          <h2>Your limits</h2>
          <div className={ui.form}><LimitFields draft={draft} onChange={setDraft} species={species.data?.find((s) => s.id === kind)} /></div>
        </section>
        </div>
        {save.problem && <p className={ui.cx(ui.form, ui.problem, 'arrive')} role="alert">{save.problem}</p>}
        <div><Button type="submit" state={save.state}>Save changes</Button></div>
      </form>
      <section className={ui.cx(ui.panel, 'arrive')} style={{ '--i': 2 } as CSSProperties}>
        <h2>Delete pond</h2>
        <div className={ui.tight}><p className={ui.note}>This removes its readings, forecasts, alerts and devices for good.</p><div><Button look="quiet" onClick={() => setAsking(true)}>Delete this pond</Button></div></div>
      </section>
      <Dialog open={asking} onClose={() => { setAsking(false); setTyped('') }} title={`Delete ${pond.name}?`}>
        <p className={ui.note}>All its data is removed and cannot be brought back.</p>
        <Field label={`Type ${pond.name} to confirm`} value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" />
        {remove.problem && <p className={ui.cx(ui.form, ui.problem)} role="alert">{remove.problem}</p>}
        <div className={ui.actions}><Button look="danger" state={remove.state} disabled={typed !== pond.name} onClick={remove.run}>Delete pond</Button><Button look="quiet" onClick={() => { setAsking(false); setTyped('') }}>Keep it</Button></div>
      </Dialog>
    </div>
  )
}

import { useState, type CSSProperties, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { queryClient, useSpecies } from '../api/queries'
import type { Pond } from '../api/types'
import { useAction } from '../lib/action'
import { Button, Field, Segments, Select } from '../ui/kit'
import { BackLink } from '../ui/shell'
import { toast } from '../ui/toast'
import { draftOf, limitsOf } from './draft'
import { LimitFields } from './limits'
import * as ui from '../ui/styles'

const zones = Intl.supportedValuesOf('timeZone')
const here = Intl.DateTimeFormat().resolvedOptions().timeZone
// Some systems still report India's old zone name.
const home = here === 'Asia/Calcutta' ? 'Asia/Kolkata' : here

export function Component() {
  const navigate = useNavigate()
  const species = useSpecies()
  const [name, setName] = useState('')
  const [kind, setKind] = useState('rohu_catla')
  const [mode, setMode] = useState<'live' | 'demo'>('live')
  const [zone, setZone] = useState(home)
  const [sampling, setSampling] = useState('15')
  const [draft, setDraft] = useState(draftOf())
  const chosen = species.data?.find((s) => s.id === kind)
  const save = useAction(async () => {
    const pond = await api<Pond>('/ponds', { method: 'POST', json: { name, species: kind, mode, timezone: zone, sampling_minutes: Number(sampling), ...limitsOf(draft) } })
    await queryClient.invalidateQueries({ queryKey: ['summary'] })
    toast(`${pond.name} was added`)
    navigate(`/ponds/${pond.id}/${mode === 'live' ? 'devices' : 'data'}`, { viewTransition: true })
  })
  const list = zones.includes(zone) ? zones : [zone, ...zones]
  return (
    <>
      <div className={ui.head}><h1>Add a pond</h1><BackLink to="/">All ponds</BackLink></div>
      <form className={ui.stack} onSubmit={(e: FormEvent) => { e.preventDefault(); void save.run() }}>
        <div className={ui.two}>
        <section className={ui.cx(ui.panel, 'arrive')}>
          <h2>About the pond</h2>
          <div className={ui.form}>
            <Field label="Name" required maxLength={80} value={name} onChange={(e) => setName(e.target.value)} />
            <Segments legend="Data" value={mode} onChange={setMode} options={[{ value: 'live', label: 'Live sensor' }, { value: 'demo', label: 'Recorded demo' }]} />
            <p className={ui.note}>{mode === 'live' ? 'A live pond receives device readings and a forecast each hour.' : 'A demo pond replays imported readings. It is always labelled as a demo.'} This cannot be changed later.</p>
            <Select label="Species" value={kind} onChange={(e) => setKind(e.target.value)} hint={chosen && !chosen.forecasts ? 'Monitoring and limit alerts only. There is no forecast model for this species.' : chosen ? 'Forecasts are available. They are for research and demonstration.' : undefined}>
              {species.data?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </Select>
            <div className={ui.grid2}>
              <Select label="Timezone" value={zone} onChange={(e) => setZone(e.target.value)} hint="Fixed after creation.">{list.map((z) => <option key={z} value={z}>{z.replaceAll('_', ' ')}</option>)}</Select>
              <Select label="Time between readings" value={sampling} onChange={(e) => setSampling(e.target.value)} hint="Fixed after creation.">{['1', '5', '10', '15', '20', '30'].map((m) => <option key={m} value={m}>{m} min</option>)}</Select>
            </div>
          </div>
        </section>
        <section className={ui.cx(ui.panel, 'arrive')} style={{ '--i': 1 } as CSSProperties}>
          <h2>Your limits</h2>
          <div className={ui.form}><LimitFields draft={draft} onChange={setDraft} species={chosen} /></div>
        </section>
        </div>
        {save.problem && <p className={ui.cx(ui.form, ui.problem, 'arrive')} role="alert">{save.problem}</p>}
        <div><Button type="submit" state={save.state} icon="plus">Add pond</Button></div>
      </form>
    </>
  )
}

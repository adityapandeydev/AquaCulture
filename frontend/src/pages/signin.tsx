import { useEffect, useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { meQuery, queryClient, useMe } from '../api/queries'
import { finishBoot } from '../lib/motion'
import { messageOf } from '../lib/action'
import { Button, Field, Segments } from '../ui/kit'
import { Drop } from '../ui/shell'

export function Component() {
  const me = useMe()
  const navigate = useNavigate()
  const location = useLocation()
  const [mode, setMode] = useState<'in' | 'up'>('in')
  const [form, setForm] = useState({ name: '', email: '', password: '' })
  const [state, setState] = useState<'idle' | 'busy' | 'done'>('idle')
  const [problem, setProblem] = useState('')
  useEffect(() => { if (!me.isPending) finishBoot() }, [me.isPending])
  const to = (location.state as { from?: string } | null)?.from ?? '/'
  if (me.data && state === 'idle') return <Navigate to={to} replace />

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setState('busy')
    setProblem('')
    try {
      await (mode === 'in'
        ? api('/auth/login', { method: 'POST', json: { email: form.email, password: form.password } })
        : api('/auth/register', { method: 'POST', json: form }))
      const user = await queryClient.fetchQuery({ ...meQuery, staleTime: 0 })
      if (!user) throw new Error('no session')
      setState('done')
      navigate(to, { viewTransition: true, replace: true })
    } catch (error) {
      setState('idle')
      setProblem(error instanceof Error && error.message === 'no session' ? 'Your browser blocked the sign-in cookie. Allow cookies for this site.' : messageOf(error))
    }
  }
  const input = (key: keyof typeof form) => ({ value: form[key], onChange: (e: { target: { value: string } }) => setForm({ ...form, [key]: e.target.value }) })

  return (
    <div className="gate">
      <div className="side">
        <div className="sea" aria-hidden="true">
          <svg viewBox="0 0 1200 40" preserveAspectRatio="none"><path fill="#135a5c" d="M0 22c75-18 150-18 225 0s150 18 225 0 100-18 150 0 150 18 225 0 150-18 225 0 100 18 150 0v18H0z" /></svg><i />
        </div>
        <span className="brand"><Drop />AquaTech</span>
        <h1 className="arrive">Your ponds, through the night.</h1>
        <p className="arrive" style={{ '--i': 2 } as React.CSSProperties}>Oxygen falls after dark. See the readings, the hours ahead and the warnings in one place.</p>
      </div>
      <div className="form-side">
        <div>
          <div className="arrive" style={{ '--i': 1 } as React.CSSProperties}>
            <Segments legend="Account" hidden value={mode} onChange={(m) => { setMode(m); setProblem('') }} options={[{ value: 'in', label: 'Sign in' }, { value: 'up', label: 'Create account' }]} />
          </div>
          <form className="form arrive" style={{ '--i': 2 } as React.CSSProperties} onSubmit={submit}>
            {mode === 'up' && <div className="arrive"><Field label="Name" autoComplete="name" required maxLength={80} {...input('name')} /></div>}
            <Field label="Email" type="email" autoComplete="email" required {...input('email')} />
            <Field label="Password" type="password" autoComplete={mode === 'in' ? 'current-password' : 'new-password'} required minLength={mode === 'up' ? 10 : undefined} hint={mode === 'up' ? 'At least 10 characters.' : undefined} {...input('password')} />
            {problem && <p className="problem arrive" role="alert">{problem}</p>}
            <Button type="submit" state={state}>{mode === 'in' ? 'Sign in' : 'Create account'}</Button>
          </form>
        </div>
      </div>
    </div>
  )
}

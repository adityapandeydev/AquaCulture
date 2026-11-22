import { useEffect, useRef, useState } from 'react'
import { ApiError } from '../api/client'

/** Run an action and expose its button state. A short tick confirms success. */
export function useAction(action: () => Promise<unknown>) {
  const [state, setState] = useState<'idle' | 'busy' | 'done'>('idle')
  const [problem, setProblem] = useState('')
  const alive = useRef(true)
  useEffect(() => { alive.current = true; return () => { alive.current = false } }, [])
  const run = async () => {
    setState('busy')
    setProblem('')
    try {
      await action()
      if (!alive.current) return
      setState('done')
      setTimeout(() => alive.current && setState('idle'), 1100)
    } catch (error) {
      if (!alive.current) return
      setState('idle')
      setProblem(messageOf(error))
    }
  }
  return { state, problem, run, setProblem }
}

export const messageOf = (error: unknown) => (error instanceof ApiError ? error.message : 'Something went wrong. Try again.')

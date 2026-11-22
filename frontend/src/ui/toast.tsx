import { useSyncExternalStore } from 'react'
import { Icon, type IconName } from './kit'

type Toast = { id: number; text: string; icon: IconName; leaving: boolean }

let list: Toast[] = []
let next = 1
const listeners = new Set<() => void>()
const set = (value: Toast[]) => { list = value; listeners.forEach((l) => l()) }

// eslint-disable-next-line react-refresh/only-export-components
export function toast(text: string, icon: IconName = 'check') {
  const id = next++
  set([...list.slice(-2), { id, text, icon, leaving: false }])
  setTimeout(() => set(list.map((t) => (t.id === id ? { ...t, leaving: true } : t))), 4200)
  setTimeout(() => set(list.filter((t) => t.id !== id)), 4500)
}

export function Toasts() {
  const items = useSyncExternalStore((l) => { listeners.add(l); return () => listeners.delete(l) }, () => list)
  return (
    <div className="toasts" role="status" aria-live="polite">
      {items.map((t) => <div key={t.id} className="toast" data-leaving={t.leaving ? '' : undefined}><Icon name={t.icon} /><span>{t.text}</span></div>)}
    </div>
  )
}

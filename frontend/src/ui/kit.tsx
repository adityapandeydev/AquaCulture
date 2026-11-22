import { useEffect, useId, useRef, type ButtonHTMLAttributes, type CSSProperties, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes } from 'react'
import { messageOf } from '../lib/action'
import type { Tone } from '../lib/status'
import * as ui from './styles'

const paths = {
  ponds: 'M3 8c2.500-1.600 4.500-1.600 6 0s3.500 1.600 6 0 4.500-1.600 6 0M3 13c2.500-1.600 4.500-1.600 6 0s3.500 1.600 6 0 4.500-1.600 6 0M3 18c2.500-1.600 4.500-1.600 6 0s3.500 1.600 6 0 4.500-1.600 6 0',
  bell: 'M6 9a6 6 0 1 1 12 0c0 6 2 7 2 7H4s2-1 2-7M10 20a2.200 2.200 0 0 0 4 0',
  model: 'M4 19V5M4 19h16M8 15l4-5 3 3 5-7',
  plus: 'M12 5v14M5 12h14',
  arrow: 'M5 12h14M13 6l6 6-6 6',
  back: 'M19 12H5M11 6l-6 6 6 6',
  check: 'M5 12.500l4.500 4.500L19 7.500',
  cross: 'M6 6l12 12M18 6L6 18',
  warn: 'M12 4L2.800 20h18.400zM12 10v4.500M12 17.300v.2',
  clock: 'M12 7v5l3.500 2M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18',
  upload: 'M12 16V5M7 9.500L12 5l5 4.500M5 19h14',
  chip: 'M8 8h8v8H8zM5 5h14v14H5zM9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3',
  play: 'M8 5.500v13l11-6.500z',
  exit: 'M14 4h5v16h-5M10 8l-4 4 4 4M6 12h9',
  sun: 'M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8M12 2.500v2M12 19.500v2M2.500 12h2M19.500 12h2M5.300 5.300l1.400 1.400M17.300 17.300l1.400 1.400M5.300 18.700l1.400-1.400M17.300 6.700l1.400-1.400',
  moon: 'M20 14.500A8.500 8.500 0 1 1 9.500 4a7 7 0 0 0 10.500 10.500',
  drop: 'M12 3c3.500 4.500 6 7.700 6 11a6 6 0 0 1-12 0c0-3.300 2.500-6.500 6-11',
}
export type IconName = keyof typeof paths

export const Icon = ({ name, className = '' }: { name: IconName; className?: string }) => (
  <svg className={ui.cx('inline-block size-[1.15em] flex-none align-[-0.2em]', className)} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]} /></svg>
)

const Spinner = () => (
  <svg className="spin inline-block size-[1.15em]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" aria-hidden="true"><path d="M12 3a9 9 0 0 1 9 9" /></svg>
)

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { look?: ui.Look; state?: 'idle' | 'busy' | 'done'; icon?: IconName }

/** The width never changes between states, so nothing around the button moves. */
export function Button({ look = '', state = 'idle', icon, className = '', children, disabled, type = 'button', ...rest }: ButtonProps) {
  return (
    <button {...rest} type={type} className={ui.cx(ui.btn(look), className)} data-state={state} disabled={disabled || state === 'busy'} aria-busy={state === 'busy' || undefined}>
      <span className={ui.face}>{icon && <Icon name={icon} />}{children}</span>
      <span className="busy" aria-hidden="true">{state === 'busy' && <Spinner />}</span>
      <span className="tick" aria-hidden="true">{state === 'done' && <Icon name="check" />}</span>
    </button>
  )
}

const control = 'min-h-[2.65rem] w-full border-0 bg-transparent px-3 py-1.5 outline-none [&_option]:bg-surface [&_option]:text-ink'

type FieldProps = { label: string; hint?: ReactNode; problem?: string }

export function Field({ label, hint, problem, ...rest }: FieldProps & InputHTMLAttributes<HTMLInputElement>) {
  const id = useId()
  return (
    <div className={ui.field}>
      <label htmlFor={id}>{label}</label>
      <div className={ui.cx('relative overflow-hidden rounded-small border bg-surface focus-within:border-accent', problem ? 'border-critical-ink' : 'border-line-strong')}><input className={control} id={id} aria-invalid={problem ? true : undefined} aria-describedby={id + 'n'} {...rest} /><span className="rule absolute inset-x-0 bottom-0 h-[3px] origin-left bg-accent" /></div>
      <span id={id + 'n'}>{problem ? <span className={ui.problem}>{problem}</span> : hint && <span className={ui.hint}>{hint}</span>}</span>
    </div>
  )
}

export function Select({ label, hint, children, ...rest }: FieldProps & SelectHTMLAttributes<HTMLSelectElement>) {
  const id = useId()
  return (
    <div className={ui.field}>
      <label htmlFor={id}>{label}</label>
      <div className="relative overflow-hidden rounded-small border border-line-strong bg-surface focus-within:border-accent"><select className={control} id={id} {...rest}>{children}</select><span className="rule absolute inset-x-0 bottom-0 h-[3px] origin-left bg-accent" /></div>
      {hint && <span className={ui.hint}>{hint}</span>}
    </div>
  )
}

export function Segments<T extends string>({ legend, hidden, options, value, onChange }: { legend: string; hidden?: boolean; options: { value: T; label: string }[]; value: T; onChange: (v: T) => void }) {
  const name = useId()
  const at = Math.max(0, options.findIndex((o) => o.value === value))
  return (
    <fieldset className="grid min-w-0 gap-2">
      <legend className={hidden ? 'sr-only' : 'text-[0.925rem] font-semibold'}>{legend}</legend>
      <div className="segments relative grid auto-cols-fr grid-flow-col rounded-small bg-sunken p-[3px]" style={{ '--n': options.length, '--at': at } as CSSProperties}>
        <span className="thumb absolute inset-y-[3px] left-[3px] w-[calc((100%-6px)/var(--n))] rounded-[7px] bg-thumb shadow-thumb [transform:translateX(calc(var(--at)*100%))]" />
        {options.map((o) => (
          <label key={o.value} className="relative cursor-pointer px-3.5 py-1.5 text-center font-[570] whitespace-nowrap has-focus-visible:rounded-[7px] has-focus-visible:outline-3 has-focus-visible:outline-offset-1 has-focus-visible:outline-accent"><input className="absolute inset-0 cursor-pointer opacity-0" type="radio" name={name} checked={o.value === value} onChange={() => onChange(o.value)} /><span className="relative">{o.label}</span></label>
        ))}
      </div>
    </fieldset>
  )
}

/** Digits roll to a new value. Screen readers get the plain number. */
export function Roll({ value, digits = 2 }: { value: number | null; digits?: number }) {
  if (value === null) return <span>–</span>
  const text = value.toFixed(digits)
  return (
    <span><span className="sr-only">{text}</span><span className="roll" aria-hidden="true">
      {[...text].map((c, i) => {
        const key = text.length - i
        return /\d/.test(c)
          ? <span key={key} style={{ transform: `translateY(${-Number(c) * 1.1}em)` }}>{'0123456789'.split('').map((d) => <i key={d}>{d}</i>)}</span>
          : <span key={key}><i>{c}</i></span>
      })}
    </span></span>
  )
}

const toneIcon: Record<Tone, IconName | null> = { neutral: null, warning: 'warn', critical: 'warn', demo: 'play' }
export const Badge = ({ tone = 'neutral', children }: { tone?: Tone; children: ReactNode }) => (
  <span className={ui.badge(tone)}>{toneIcon[tone] && <Icon name={toneIcon[tone]} />}{children}</span>
)

export const Skeleton = ({ height, width = '100%' }: { height: string; width?: string }) => <div className="skeleton relative overflow-hidden rounded-small bg-sunken" style={{ height, width }} aria-hidden="true" />

export function Failed({ error, retry }: { error: unknown; retry: () => void }) {
  return (
    <div className={ui.cx(ui.emptyState, 'arrive')} role="alert">
      <Icon name="warn" />
      <p>{messageOf(error)}</p>
      <Button look="quiet" onClick={retry}>Try again</Button>
    </div>
  )
}

export const Empty = ({ title, children }: { title: string; children?: ReactNode }) => (
  <div className={ui.cx(ui.emptyState, 'arrive')}><Icon name="drop" /><h2>{title}</h2>{children}</div>
)

export function Dialog({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null)
  const id = useId()
  useEffect(() => {
    const d = ref.current
    if (!d) return
    if (open && !d.open) d.showModal()
    if (!open && d.open) d.close()
  }, [open])
  return (
    <dialog className="m-auto w-[min(30rem,calc(100vw-2rem))] rounded-panel border-0 bg-surface p-6 text-ink shadow-float" ref={ref} aria-labelledby={id} onClose={onClose} onClick={(e) => e.target === ref.current && onClose()}>
      <div className={ui.stack}><h2 id={id}>{title}</h2>{children}</div>
    </dialog>
  )
}

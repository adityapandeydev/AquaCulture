/** Utility groups used in more than one place. Single uses stay in the markup. */

export const cx = (...parts: (string | false | null | undefined)[]) => parts.filter(Boolean).join(' ')

// Layout
export const page = 'mx-auto w-full min-w-0 max-w-[82rem] p-[clamp(1.25rem,3vw,2.5rem)]'
export const head = 'mb-7 flex flex-wrap items-end justify-between gap-x-8 gap-y-4 [&_p]:mt-1.5 [&_p]:text-ink-2'
export const actions = 'flex flex-wrap items-center gap-2.5'
export const stack = 'grid grid-cols-1 content-start gap-5'
export const tight = 'grid grid-cols-1 content-start gap-2.5'
export const two = 'grid grid-cols-2 items-start gap-5 max-lg:grid-cols-1'
export const now = 'grid grid-cols-[15rem_minmax(0,1fr)] gap-5 max-lg:grid-cols-1'
export const panel = 'min-w-0 rounded-panel border border-line bg-surface p-[clamp(1rem,2vw,1.5rem)] [&>h2]:mb-3'
export const panelHead = 'mb-3.5 flex flex-wrap items-center justify-between gap-x-5 gap-y-3'
export const emptyState = 'grid justify-items-center gap-3 px-4 py-12 text-center'

// Text
export const note = 'max-w-[68ch] text-[0.925rem] text-ink-2'
export const hint = 'text-[0.85rem] text-ink-3'
export const problem = 'problem text-[0.9rem] font-[550] text-critical-ink'
export const secret = 'secret block rounded-small bg-sunken p-3 font-mono text-[0.9rem] wrap-anywhere select-all'
export const brand = 'flex items-center gap-2.5 px-2.5 py-1 text-[1.2rem] font-[680] tracking-[-0.02em] text-inherit no-underline'

// Forms
export const form = 'grid max-w-xl gap-[1.1rem]'
export const grid2 = 'grid grid-cols-2 gap-4 max-md:grid-cols-1'
export const field = 'field grid min-w-0 gap-1 [&>label]:text-[0.925rem] [&>label]:font-semibold'
export const figures = 'grid grid-cols-[repeat(auto-fit,minmax(8rem,1fr))] gap-4 [&_dd]:text-2xl [&_dd]:font-[650] [&_dd]:tracking-[-0.02em] [&_dt]:text-sm [&_dt]:text-ink-3'

// Chances
export const chances = 'grid gap-4'
export const chance = 'chance grid grid-cols-[4rem_minmax(0,1fr)_3.2rem] items-center gap-3.5 [&>b]:tabular-nums [&>b:nth-child(3)]:text-right [&>p]:col-[2/-1] [&>p]:-mt-2.5 [&>p]:text-[0.85rem] [&>p]:text-ink-3'
export const track = 'relative h-2.5 overflow-hidden rounded-full bg-sunken'
export const bar = 'bar absolute inset-0 bg-forecast'

// Buttons. "btn" is also the hook for press, hover and ripple motion.
const looks = {
  '': 'border-transparent bg-accent text-accent-ink',
  quiet: 'border-line-strong bg-surface text-ink',
  ghost: 'border-transparent bg-transparent text-inherit',
  danger: 'border-transparent bg-critical-ink text-danger-ink',
}
export type Look = keyof typeof looks
export const btn = (look: Look = '') => cx(
  'btn relative isolate inline-flex min-h-[2.65rem] cursor-pointer touch-manipulation items-center justify-center gap-2 overflow-hidden rounded-small border px-[1.05rem] py-[0.45rem] font-semibold no-underline [-webkit-tap-highlight-color:transparent] disabled:cursor-not-allowed disabled:opacity-55',
  looks[look],
)
export const face = 'face inline-flex items-center gap-2'

// Badges
const tones = {
  neutral: 'bg-sunken text-ink-2',
  warning: 'bg-warning-wash text-warning-ink',
  critical: 'bg-critical-wash text-critical-ink',
  good: 'bg-good-wash text-good-ink',
  demo: 'bg-accent-wash text-accent',
}
export const badge = (tone: keyof typeof tones) => cx('inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-sm font-semibold whitespace-nowrap', tones[tone])

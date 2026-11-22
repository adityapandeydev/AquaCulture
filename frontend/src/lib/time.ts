const cache = new Map<string, Intl.DateTimeFormat>()

function formatter(zone: string, options: Intl.DateTimeFormatOptions): Intl.DateTimeFormat {
  const key = zone + JSON.stringify(options)
  let f = cache.get(key)
  if (!f) cache.set(key, (f = new Intl.DateTimeFormat('en-GB', { timeZone: zone, hourCycle: 'h23', ...options })))
  return f
}

export const HOUR = 3_600_000

export const clock = (t: number | string, zone: string) => formatter(zone, { hour: '2-digit', minute: '2-digit' }).format(new Date(t))
export const dayClock = (t: number | string, zone: string) =>
  formatter(zone, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }).format(new Date(t)).replace(',', '')
export const day = (t: number | string, zone: string) => formatter(zone, { day: 'numeric', month: 'short' }).format(new Date(t))
export const fullDay = (t: number | string, zone: string) => formatter(zone, { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(t))

/** Hour of the day, 0 to 23, in the pond's timezone. */
export const localHour = (t: number, zone: string) => Number(formatter(zone, { hour: '2-digit' }).format(new Date(t)))

/** Start of the local clock hour that contains t. Works for zones at half past, such as India. */
export function hourStart(t: number, zone: string): number {
  const parts = formatter(zone, { minute: '2-digit', second: '2-digit' }).formatToParts(new Date(t))
  const part = (type: string) => Number(parts.find((p) => p.type === type)?.value ?? 0)
  return Math.floor(t / 1000) * 1000 - part('minute') * 60_000 - part('second') * 1000
}

/** "12 min ago". Future times from small clock differences read as "just now". */
export function ago(t: string, now: number): string {
  const minutes = Math.floor((now - Date.parse(t)) / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 48) return `${hours} h ago`
  return `${Math.floor(hours / 24)} days ago`
}

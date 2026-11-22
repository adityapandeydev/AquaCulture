import { top } from '../lib/scale'

/** The last 24 stored hours. Gaps stay gaps. */
export function Trend({ values, low }: { values: (number | null)[]; low: number | null }) {
  const max = top([...values, low])
  const x = (i: number) => (i / Math.max(1, values.length - 1)) * 200
  const y = (v: number) => 44 - (v / max) * 44
  let path = ''
  values.forEach((v, i) => {
    if (v !== null) path += `${i === 0 || values[i - 1] === null ? 'M' : 'L'}${x(i).toFixed(1)} ${y(v).toFixed(1)}`
  })
  const known = values.filter((v): v is number => v !== null)
  const label = known.length ? `Last 24 hours: ${Math.min(...known).toFixed(1)} to ${Math.max(...known).toFixed(1)} mg/L` : 'No hourly values'
  return (
    <svg className="block h-11 w-full overflow-visible draw" viewBox="0 0 200 44" preserveAspectRatio="none" role="img" aria-label={label}>
      {low !== null && <line x1="0" x2="200" y1={y(low)} y2={y(low)} stroke="var(--line-strong)" vectorEffect="non-scaling-stroke" />}
      <path d={path} fill="none" stroke="var(--series-observed)" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
    </svg>
  )
}

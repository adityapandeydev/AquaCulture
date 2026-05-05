export default function RiskSummary({ data }: any) {
  if (!data.length) return null

  const counts = {
    low: 0,
    medium: 0,
    high: 0,
  }

  data.forEach((d: any) => {
    counts[d.risk]++
  })

  return (
    <div className="bg-surface p-4 rounded-xl">
      <h2 className="mb-4 font-semibold">Risk Distribution</h2>

      <div className="flex gap-4">
        <div className="bg-accent px-4 py-2 rounded">
          Low: {counts.low}
        </div>

        <div className="bg-warning px-4 py-2 rounded">
          Medium: {counts.medium}
        </div>

        <div className="bg-danger px-4 py-2 rounded">
          High: {counts.high}
        </div>
      </div>
    </div>
  )
}
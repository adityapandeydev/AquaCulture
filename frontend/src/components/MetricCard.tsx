interface MetricCardProps {
  label: string
  value: number | null | undefined
}

export default function MetricCard({ label, value }: MetricCardProps) {
  return (
    <div className="bg-card p-4 rounded-xl border border-border shadow-sm">
      <p className="text-muted text-sm">{label}</p>
      <h2 className="text-2xl font-semibold mt-1">
        {typeof value === "number" ? value.toFixed(2) : "--"}
      </h2>
    </div>
  )
}
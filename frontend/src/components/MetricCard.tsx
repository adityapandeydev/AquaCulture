export default function MetricCard({ label, value, color }: any) {
  return (
    <div className="bg-card p-4 rounded-xl border border-border shadow-sm">
      <p className="text-muted text-sm">{label}</p>
      <h2 className="text-2xl font-semibold mt-1">{value ?? "--"}</h2>
    </div>
  )
}
export default function RiskBadge({ level }: { level: string }) {
  const color =
    level === "low"
      ? "bg-accent"
      : level === "medium"
      ? "bg-warning"
      : "bg-danger"

  return (
    <div className={`px-3 py-1 rounded-full text-xs ${color}`}>
      {level.toUpperCase()}
    </div>
  )
}
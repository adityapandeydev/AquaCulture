import type { AlertItem } from "../types/domain"

interface AlertsPanelProps {
  alerts: AlertItem[]
}

export default function AlertsPanel({ alerts }: AlertsPanelProps) {
  return (
    <div className="bg-surface p-4 rounded-xl">
      <h2 className="mb-4 font-semibold">Alerts</h2>

      <div className="space-y-2 max-h-64 overflow-y-auto">
        {alerts.length === 0 && (
          <p className="text-textSecondary text-sm">No alerts</p>
        )}

        {alerts.map((alert) => (
          <div
            key={alert.id}
            className="p-3 rounded-lg border border-primary/10 bg-background"
          >
            <div className="flex justify-between items-center">
              <span className="text-sm">{alert.message}</span>

              <span
                className={`text-xs px-2 py-1 rounded ${
                  alert.severity === "low"
                    ? "bg-accent"
                    : alert.severity === "medium"
                    ? "bg-warning"
                    : "bg-danger"
                }`}
              >
                {alert.severity}
              </span>
            </div>

            <p className="text-xs text-textSecondary mt-1">
              {new Date(alert.timestamp).toLocaleString()}
            </p>
          </div>
        ))}
      </div>
    </div>
  )
}
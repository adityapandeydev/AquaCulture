import { useState } from "react"
import { simulatePond } from "../api/sensor"
import { transformPredictions, getLatestMetrics } from "../utils/transform"
import PredictionChart from "../components/PredictionChart"
import MetricCard from "../components/MetricCard"
import RiskSummary from "../components/RiskSummary"
import RiskBadge from "../components/RiskBadge"
import { getCurrentRisk } from "../utils/transform"
import { fetchAlerts } from "../api/alerts"
import AlertsPanel from "../components/AlertsPanel"
import Button from "../components/Button"

export default function Dashboard() {
  const [pondId, setPondId] = useState("")
  const [chartData, setChartData] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const currentRisk = getCurrentRisk(chartData)
  const [alerts, setAlerts] = useState<any[]>([])

  const runSimulation = async () => {
    setLoading(true)

    try {
      const res = await simulatePond(pondId)

      const transformed = transformPredictions(res.hourly_predictions)
      setChartData(transformed)

      // 🔥 Fetch alerts
      const alertsRes = await fetchAlerts(pondId)
      setAlerts(alertsRes)

    } catch (err) {
      console.error(err)
      alert("Simulation failed")
    }

    setLoading(false)
  }

  const metrics = getLatestMetrics(chartData)

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Aquaculture Dashboard</h1>

      {/* Input */}
      <div className="bg-surface p-4 rounded-xl flex gap-2">
        <input
          placeholder="Enter Pond ID"
          className="w-full px-3 py-2 rounded-lg 
             bg-surface border border-border 
             focus:outline-none focus:ring-2 focus:ring-primary
             placeholder:text-muted"
          onChange={(e) => setPondId(e.target.value)}
        />

        <Button onClick={runSimulation} loading={loading}>
          {loading ? "Running..." : "Run"}
        </Button>
      </div>

      {/* Metrics */}
      {metrics && (
        <div className="grid grid-cols-4 gap-4">
          <MetricCard label="DO" value={metrics.do} color="#14B8A6" />
          <MetricCard label="Temperature" value={metrics.temperature} color="#F59E0B" />
          <MetricCard label="Ammonia" value={metrics.ammonia} color="#EF4444" />
          <MetricCard label="Nitrate" value={metrics.nitrate} color="#84CC16" />
        </div>
      )}

      {/* Current Risk */}
      {chartData.length > 0 && (
        <div className="flex items-center gap-3">
          <span className="text-textSecondary">Current Risk:</span>
          <RiskBadge level={currentRisk} />
        </div>
      )}

      {/* Charts */}
      {chartData.length > 0 && (
        <div className="grid grid-cols-2 gap-4">
          <PredictionChart data={chartData} dataKey="do" color="#14B8A6" />
          <PredictionChart data={chartData} dataKey="temperature" color="#F59E0B" />
          <PredictionChart data={chartData} dataKey="ammonia" color="#EF4444" />
          <PredictionChart data={chartData} dataKey="nitrate" color="#84CC16" />
        </div>
      )}

      <RiskSummary data={chartData} />
      <AlertsPanel alerts={alerts} />
    </div>
  )
}
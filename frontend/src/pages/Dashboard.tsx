import { useCallback, useEffect, useMemo, useState } from "react"
import {
  fetchCleanData,
  fetchForecastLogs,
  fetchRawData,
  simulateFeed,
  simulatePond,
} from "../api/sensor"
import { createPond, deletePond, listPonds } from "../api/ponds"
import { transformPredictions, getCurrentRisk, getLatestMetrics } from "../utils/transform"
import PredictionChart from "../components/PredictionChart"
import MetricCard from "../components/MetricCard"
import RiskSummary from "../components/RiskSummary"
import RiskBadge from "../components/RiskBadge"
import { fetchAlerts } from "../api/alerts"
import AlertsPanel from "../components/AlertsPanel"
import Button from "../components/Button"
import { clearToken } from "../utils/auth"
import { useNavigate } from "react-router-dom"
import type { AlertItem, ChartPoint, ForecastLog, Pond, SensorPoint } from "../types/domain"

export default function Dashboard() {
  const navigate = useNavigate()
  const [ponds, setPonds] = useState<Pond[]>([])
  const [selectedPondId, setSelectedPondId] = useState("")
  const [newPondName, setNewPondName] = useState("")
  const [chartData, setChartData] = useState<ChartPoint[]>([])
  const [alerts, setAlerts] = useState<AlertItem[]>([])
  const [rawData, setRawData] = useState<SensorPoint[]>([])
  const [cleanData, setCleanData] = useState<SensorPoint[]>([])
  const [forecastLogs, setForecastLogs] = useState<ForecastLog[]>([])
  const [loading, setLoading] = useState(false)
  const [feedLoading, setFeedLoading] = useState(false)
  const [crudLoading, setCrudLoading] = useState(false)
  const [error, setError] = useState("")
  const [tab, setTab] = useState<"forecast" | "raw" | "clean" | "alerts">("forecast")
  const [forecastWindowHours, setForecastWindowHours] = useState<12 | 24 | 48>(24)
  const [dismissedFaultyAlertIds, setDismissedFaultyAlertIds] = useState<string[]>([])

  const currentRisk = getCurrentRisk(chartData)
  const filteredChartData = useMemo(() => {
    return chartData.slice(-forecastWindowHours)
  }, [chartData, forecastWindowHours])

  const selectedPond = useMemo(
    () => ponds.find((pond) => pond.id === selectedPondId) || null,
    [ponds, selectedPondId]
  )

  const loadPonds = useCallback(async () => {
    const data = await listPonds()
    setPonds(data)
    if (!selectedPondId && data.length > 0) {
      setSelectedPondId(data[0].id)
    }
    if (selectedPondId && !data.some((pond) => pond.id === selectedPondId)) {
      setSelectedPondId(data[0]?.id || "")
    }
  }, [selectedPondId])

  useEffect(() => {
    loadPonds().catch(() => setError("Failed to load ponds"))
  }, [loadPonds])

  useEffect(() => {
    setDismissedFaultyAlertIds([])
  }, [selectedPondId])

  const loadPondData = async (pondId: string) => {
    const [alertsRes, rawRes, cleanRes, forecastRes] = await Promise.all([
      fetchAlerts(pondId),
      fetchRawData(pondId, 50),
      fetchCleanData(pondId, 50),
      fetchForecastLogs(pondId, 50),
    ])

    setAlerts(alertsRes)
    setRawData(rawRes)
    setCleanData(cleanRes)
    setForecastLogs(forecastRes)
  }

  const runSimulation = async () => {
    if (!selectedPondId) {
      setError("Create or select a pond first.")
      return
    }

    setLoading(true)
    setError("")

    try {
      const res = await simulatePond(selectedPondId)
      const transformed = transformPredictions(res.hourly_predictions)
      setChartData(transformed)
      await loadPondData(selectedPondId)
    } catch {
      setError("Simulation failed for selected pond.")
    } finally {
      setLoading(false)
    }
  }

  const runFeedSimulation = async () => {
    if (!selectedPondId) {
      setError("Create or select a pond first.")
      return
    }

    setFeedLoading(true)
    setError("")
    try {
      await simulateFeed(selectedPondId, 48)
      await loadPondData(selectedPondId)
    } catch {
      setError("Failed to generate simulated sensor feed.")
    } finally {
      setFeedLoading(false)
    }
  }

  const createNewPond = async () => {
    if (!newPondName.trim()) return
    setCrudLoading(true)
    setError("")
    try {
      const pond = await createPond(newPondName.trim(), "UTC")
      setNewPondName("")
      await loadPonds()
      setSelectedPondId(pond.id)
    } catch {
      setError("Failed to create pond.")
    } finally {
      setCrudLoading(false)
    }
  }

  const removeSelectedPond = async () => {
    if (!selectedPondId) return
    setCrudLoading(true)
    setError("")
    try {
      await deletePond(selectedPondId)
      setChartData([])
      setAlerts([])
      setRawData([])
      setCleanData([])
      setForecastLogs([])
      await loadPonds()
    } catch {
      setError("Failed to delete pond.")
    } finally {
      setCrudLoading(false)
    }
  }

  const logout = () => {
    clearToken()
    navigate("/")
  }

  const metrics = getLatestMetrics(chartData)
  const faultySensorAlerts = useMemo(
    () =>
      alerts
        .filter(
          (alert) =>
            alert.alert_type === "sensor_faulty_consecutive" &&
            !dismissedFaultyAlertIds.includes(alert.id)
        )
        .slice(0, 3),
    [alerts, dismissedFaultyAlertIds]
  )

  const dismissFaultyAlert = (alertId: string) => {
    setDismissedFaultyAlertIds((prev) => [...prev, alertId])
  }

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {faultySensorAlerts.length > 0 && (
        <div className="fixed top-4 right-4 z-50 space-y-2 w-80">
          {faultySensorAlerts.map((alert) => (
            <div
              key={alert.id}
              className="bg-danger/20 border border-danger text-text rounded-lg p-3 shadow-lg"
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-sm font-semibold">Faulty Sensor Alert</p>
                  <p className="text-xs mt-1">{alert.message}</p>
                  <p className="text-[11px] mt-1 text-muted">
                    {new Date(alert.timestamp).toLocaleString()}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => dismissFaultyAlert(alert.id)}
                  className="text-xs px-2 py-1 rounded bg-bg border border-border hover:bg-surface"
                >
                  Dismiss
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">AquaTech Dashboard</h1>
          <p className="text-muted mt-1">Manage ponds, simulate sensors, and run forecasts.</p>
        </div>
        <Button onClick={logout} variant="secondary">
          Logout
        </Button>
      </div>

      <div className="bg-surface p-4 rounded-xl border border-border space-y-4">
        <div className="flex flex-wrap gap-3">
          <select
            value={selectedPondId}
            onChange={(e) => setSelectedPondId(e.target.value)}
            className="px-3 py-2 rounded-lg bg-bg border border-border min-w-64"
          >
            <option value="">Select pond</option>
            {ponds.map((pond) => (
              <option key={pond.id} value={pond.id}>
                {pond.name}
              </option>
            ))}
          </select>

          <input
            value={newPondName}
            onChange={(e) => setNewPondName(e.target.value)}
            placeholder="New pond name"
            className="px-3 py-2 rounded-lg bg-bg border border-border min-w-64"
          />

          <Button onClick={createNewPond} loading={crudLoading}>
            Add Pond
          </Button>
          <Button onClick={removeSelectedPond} loading={crudLoading} variant="danger">
            Remove Pond
          </Button>
        </div>

        <div className="flex flex-wrap gap-3">
          <Button onClick={runFeedSimulation} loading={feedLoading} variant="secondary">
            Simulate 48h Sensor Feed
          </Button>
          <Button onClick={runSimulation} loading={loading}>
            Run Forecast
          </Button>
          {selectedPond && (
            <div className="px-3 py-2 rounded-lg bg-bg border border-border text-sm text-muted">
              Active pond: <span className="text-text font-medium">{selectedPond.name}</span>
            </div>
          )}
        </div>
      </div>

      {error && <p className="text-danger text-sm">{error}</p>}

      {metrics && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
          <MetricCard label="DO" value={metrics.do} />
          <MetricCard label="Temperature" value={metrics.temperature} />
          <MetricCard label="Ammonia" value={metrics.ammonia} />
          <MetricCard label="Nitrate" value={metrics.nitrate} />
        </div>
      )}

      {chartData.length > 0 && (
        <div className="flex items-center gap-3">
          <span className="text-muted">Current Risk:</span>
          <RiskBadge level={currentRisk} />
        </div>
      )}

      <div className="bg-surface p-4 rounded-xl border border-border">
        <div className="flex gap-2 mb-4">
          {(["forecast", "raw", "clean", "alerts"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-3 py-1.5 rounded-lg text-sm ${
                tab === t ? "bg-primary text-white" : "bg-bg text-muted hover:text-text"
              }`}
            >
              {t.toUpperCase()}
            </button>
          ))}
        </div>

        {tab === "forecast" && (
          <>
            <div className="mb-4 flex items-center gap-2">
              <span className="text-sm text-muted">Show last:</span>
              <select
                value={forecastWindowHours}
                onChange={(e) => setForecastWindowHours(Number(e.target.value) as 12 | 24 | 48)}
                className="px-3 py-1.5 rounded-lg bg-bg border border-border text-sm"
              >
                <option value={12}>12 hours</option>
                <option value={24}>24 hours</option>
                <option value={48}>48 hours</option>
              </select>
            </div>

            {filteredChartData.length > 0 ? (
              <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                <PredictionChart data={filteredChartData} dataKey="do" color="#14B8A6" />
                <PredictionChart data={filteredChartData} dataKey="temperature" color="#F59E0B" />
                <PredictionChart data={filteredChartData} dataKey="ammonia" color="#EF4444" />
                <PredictionChart data={filteredChartData} dataKey="nitrate" color="#84CC16" />
              </div>
            ) : (
              <p className="text-muted text-sm">No forecast data yet. Run sensor feed and forecast.</p>
            )}
            <div className="mt-4">
              <RiskSummary data={chartData} />
            </div>
            {forecastLogs.length > 0 && (
              <p className="text-xs text-muted mt-3">Stored forecast rows: {forecastLogs.length}</p>
            )}
          </>
        )}

        {tab === "raw" && (
          <div className="space-y-2">
            {rawData.slice(0, 12).map((row) => (
              <div key={row.id} className="text-sm bg-bg border border-border rounded-lg p-3">
                {new Date(row.timestamp).toLocaleString()} | DO: {row.do ?? "--"} | Temp:{" "}
                {row.temperature ?? "--"} | NH3: {row.ammonia ?? "--"} | NO3: {row.nitrate ?? "--"}
              </div>
            ))}
            {rawData.length === 0 && <p className="text-muted text-sm">No raw data found.</p>}
          </div>
        )}

        {tab === "clean" && (
          <div className="space-y-2">
            {cleanData.slice(0, 12).map((row) => (
              <div key={row.id} className="text-sm bg-bg border border-border rounded-lg p-3">
                {new Date(row.timestamp).toLocaleString()} | DO: {row.do ?? "--"} | Temp:{" "}
                {row.temperature ?? "--"} | Flag: {row.quality_flag || "valid"}
              </div>
            ))}
            {cleanData.length === 0 && <p className="text-muted text-sm">No clean data found.</p>}
          </div>
        )}

        {tab === "alerts" && <AlertsPanel alerts={alerts} />}
      </div>
    </div>
  )
}
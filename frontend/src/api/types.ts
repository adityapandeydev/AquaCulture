export type User = { id: string; email: string; name: string }

export type Limits = {
  do_low: number | null
  do_critical: number | null
  ph_low: number | null
  ph_high: number | null
  temperature_low: number | null
  temperature_high: number | null
  alert_probability: number
}

export type Pond = Limits & {
  id: string
  name: string
  timezone: string
  species: string
  mode: 'live' | 'demo'
  sampling_minutes: number
  created_at: string
}

export type Summary = Pond & {
  latest_at: string | null
  latest_do_mgL: number | null
  latest_ph: number | null
  latest_temperature_c: number | null
  open_alerts: number
  critical_alerts: number
  forecast_issue: string | null
  forecast_status: 'ok' | 'unavailable' | null
  highest_probability: number | null
  trend_end: string | null
  trend_do_mgL: (number | null)[] | null
}

export type Species = {
  id: string
  name: string
  forecasts: boolean
  suggested_thresholds: { do_low: number; ph_low: number; ph_high: number; source: string; strength: string } | null
}

export type Reading = { observed_at: string; do_mgL: number | null; ph: number | null; temperature_c: number | null; source: 'device' | 'import' }

export type Hour = {
  start: string
  do_mgL: number | null
  do_min_mgL: number | null
  ph: number | null
  temperature_c: number | null
  coverage: number
  zero_readings: number
}

export type ForecastValue = {
  horizon_hours: number
  target_start: string
  target_end: string
  point_mgL: number | null
  low_mgL: number | null
  high_mgL: number | null
  threshold_mgL: number | null
  probability: number | null
  withheld: string[]
}

export type Forecast = {
  id: string
  issue_time: string
  status: 'ok' | 'unavailable'
  model_id: string | null
  reasons: string[]
  warnings: string[]
  created_at: string
  values: ForecastValue[]
}

export type Alert = {
  id: string
  pond_id: string
  kind: string
  origin: 'observed' | 'forecast' | 'system'
  severity: 'warning' | 'critical'
  message: string
  opened_at: string
  last_seen_at: string
  acknowledged_at: string | null
  resolved_at: string | null
}

export type Overview = {
  pond: Pond
  now: string
  extent: { first: string | null; last: string | null; count: number }
  latest: Reading | null
  forecast: Forecast | null
  alerts: Alert[]
}

export type Device = { id: string; pond_id: string; name: string; created_at: string; last_seen_at: string | null; revoked_at: string | null }

export type ImportReport = {
  rows: number
  valid: number
  repeated: number
  rejected: number
  rejections: { line: number; reason: string }[]
  duplicate: number
  conflict: number
  committed: boolean
  stored?: number
  first?: string
  last?: string
}

export type Accuracy = {
  horizon_hours: number
  compared: number
  points: number
  mae_mgL: number | null
  persistence_mae_mgL: number | null
  intervals: number
  interval_coverage: number | null
  events: number
  brier: number | null
}

export type ModelInfo = { available: boolean; model?: { model_id: string; released: Record<string, { point: boolean; interval: boolean; alert: boolean }> } }

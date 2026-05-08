export type RiskLevel = "low" | "medium" | "high"

export interface Pond {
  id: string
  name: string
  owner_id: string
  timezone: string
  created_at: string
}

export interface SensorPoint {
  id: string
  pond_id: string
  timestamp: string
  do: number | null
  temperature: number | null
  ph: number | null
  turbidity: number | null
  ammonia: number | null
  nitrate: number | null
  is_processed?: boolean
  is_imputed?: boolean
  quality_flag?: string
}

export interface AlertItem {
  id: string
  pond_id: string
  alert_type: string
  severity: RiskLevel
  message: string
  timestamp: string
  resolved: boolean
}

export interface ForecastLog {
  id: string
  pond_id: string
  forecast_for: string
  horizon_step: number
  pred_do: number | null
  pred_temperature: number | null
  pred_ammonia: number | null
  pred_nitrate: number | null
  risk_state: RiskLevel
}

export interface SimulationResponse {
  status: string
  total_hourly_predictions: number
  hourly_predictions: Array<{
    window_end: string
    water_forecast: number[][]
    nitrogen_forecast: number[][]
    risk?: {
      risk_states?: RiskLevel[]
    }
  }>
}

export interface ChartPoint {
  time: string
  do: number
  temperature: number
  ammonia: number
  nitrate: number
  risk: RiskLevel
}

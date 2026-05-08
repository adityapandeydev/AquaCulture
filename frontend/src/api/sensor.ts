import API from "./client"
import type { ForecastLog, SensorPoint, SimulationResponse } from "../types/domain"

export const simulatePond = async (pondId: string): Promise<SimulationResponse> => {
  const res = await API.post(`/sensor/simulate/${pondId}`)
  return res.data
}

export const simulateFeed = async (
  pondId: string,
  hours = 24
): Promise<{ status: string; rows_created: number }> => {
  const res = await API.post(`/sensor/simulate-feed/${pondId}?hours=${hours}`)
  return res.data
}

export const fetchRawData = async (pondId: string, limit = 100): Promise<SensorPoint[]> => {
  const res = await API.get(`/sensor/pond/${pondId}/raw?limit=${limit}`)
  return res.data
}

export const fetchCleanData = async (pondId: string, limit = 100): Promise<SensorPoint[]> => {
  const res = await API.get(`/sensor/pond/${pondId}/clean?limit=${limit}`)
  return res.data
}

export const fetchForecastLogs = async (
  pondId: string,
  limit = 100
): Promise<ForecastLog[]> => {
  const res = await API.get(`/sensor/pond/${pondId}/forecasts?limit=${limit}`)
  return res.data
}
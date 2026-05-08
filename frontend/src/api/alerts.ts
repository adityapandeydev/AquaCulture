import API from "./client"
import type { AlertItem } from "../types/domain"

export const fetchAlerts = async (pondId: string): Promise<AlertItem[]> => {
  const res = await API.get(`/alerts/${pondId}`)
  return res.data
}
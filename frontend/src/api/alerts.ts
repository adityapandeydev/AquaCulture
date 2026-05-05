import API from "./client"

export const fetchAlerts = async (pondId: string) => {
  const res = await API.get(`/alerts/${pondId}`)
  return res.data
}
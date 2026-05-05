import API from "./client"

export const simulatePond = async (pondId: string) => {
  const res = await API.post(`/sensor/simulate/${pondId}`)
  return res.data
}
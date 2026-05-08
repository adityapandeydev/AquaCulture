import API from "./client"
import type { Pond } from "../types/domain"

export const listPonds = async (): Promise<Pond[]> => {
  const res = await API.get("/ponds/")
  return res.data
}

export const createPond = async (name: string, timezone = "UTC"): Promise<Pond> => {
  const res = await API.post("/ponds/", { name, timezone })
  return res.data
}

export const deletePond = async (pondId: string): Promise<{ status: string }> => {
  const res = await API.delete(`/ponds/${pondId}`)
  return res.data
}

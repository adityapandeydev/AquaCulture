import { QueryCache, QueryClient, useQuery } from '@tanstack/react-query'
import { api, ApiError } from './client'
import type { Accuracy, Alert, Device, Forecast, Hour, ModelInfo, Overview, Reading, Species, Summary, User } from './types'

const LIVE = 30_000

export const queryClient: QueryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: (error, query) => {
      // A session that ends while working returns the visitor to sign-in.
      if (error instanceof ApiError && error.status === 401 && query.queryKey[0] !== 'me') queryClient.setQueryData(['me'], null)
    },
  }),
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      retry: (count, error) => count < 2 && !(error instanceof ApiError && error.status >= 400 && error.status < 500),
    },
  },
})

export const meQuery = {
  queryKey: ['me'],
  queryFn: async ({ signal }: { signal: AbortSignal }): Promise<User | null> => {
    try {
      return await api<User>('/auth/me', { signal })
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) return null
      throw error
    }
  },
  staleTime: 5 * 60_000,
}

export const useMe = () => useQuery(meQuery)
export const useSummary = () =>
  useQuery({ queryKey: ['summary'], queryFn: ({ signal }) => api<{ now: string; ponds: Summary[] }>('/summary', { signal }), refetchInterval: LIVE })
export const useOpenAlerts = () => useQuery({ queryKey: ['alerts'], queryFn: ({ signal }) => api<Alert[]>('/alerts', { signal }), refetchInterval: LIVE })
export const useSpecies = () => useQuery({ queryKey: ['species'], queryFn: ({ signal }) => api<Species[]>('/species', { signal }), staleTime: Infinity })
export const useModel = () => useQuery({ queryKey: ['model'], queryFn: ({ signal }) => api<ModelInfo>('/model', { signal }), refetchInterval: 60_000 })

/** Every pond query starts with its pond, so one pond's data can never appear on another. */
export const useOverview = (id: string) =>
  useQuery({ queryKey: ['pond', id, 'overview'], queryFn: ({ signal }) => api<Overview>(`/ponds/${id}/overview`, { signal }), refetchInterval: LIVE })
export const useForecasts = (id: string, poll = false) =>
  useQuery({ queryKey: ['pond', id, 'forecasts'], queryFn: ({ signal }) => api<Forecast[]>(`/ponds/${id}/forecasts?limit=100`, { signal }), refetchInterval: poll ? 2000 : LIVE })
export const useHours = (id: string, from: string | null, to: string | null) =>
  useQuery({
    queryKey: ['pond', id, 'hours', from, to],
    queryFn: ({ signal }) => api<Hour[]>(`/ponds/${id}/hours?from=${encodeURIComponent(from!)}&to=${encodeURIComponent(to!)}`, { signal }),
    enabled: from !== null && to !== null,
    refetchInterval: LIVE,
    placeholderData: (previous, query) => (query?.queryKey[1] === id ? previous : undefined),
  })
export const useReadings = (id: string, from: string | null, to: string | null) =>
  useQuery({
    queryKey: ['pond', id, 'readings', from, to],
    queryFn: ({ signal }) => api<Reading[]>(`/ponds/${id}/readings?limit=48&from=${encodeURIComponent(from!)}&to=${encodeURIComponent(to!)}`, { signal }),
    enabled: from !== null && to !== null,
  })
export const useDevices = (id: string) => useQuery({ queryKey: ['pond', id, 'devices'], queryFn: ({ signal }) => api<Device[]>(`/ponds/${id}/devices`, { signal }), refetchInterval: LIVE })
export const usePondAlerts = (id: string) => useQuery({ queryKey: ['pond', id, 'alerts'], queryFn: ({ signal }) => api<Alert[]>(`/ponds/${id}/alerts?limit=100`, { signal }), refetchInterval: LIVE })
export const useAccuracy = (id: string) => useQuery({ queryKey: ['pond', id, 'accuracy'], queryFn: ({ signal }) => api<Accuracy[]>(`/ponds/${id}/accuracy`, { signal }) })

export const refreshPond = (id: string) =>
  Promise.all([
    queryClient.invalidateQueries({ queryKey: ['pond', id] }),
    queryClient.invalidateQueries({ queryKey: ['summary'] }),
    queryClient.invalidateQueries({ queryKey: ['alerts'] }),
  ])


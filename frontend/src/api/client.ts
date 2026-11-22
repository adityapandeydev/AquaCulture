export class ApiError extends Error {
  readonly status: number
  readonly code: string
  constructor(status: number, code: string, message: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

type Options = { method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'; json?: unknown; csv?: Blob; signal?: AbortSignal }

export async function api<T>(path: string, { method = 'GET', json, csv, signal }: Options = {}): Promise<T> {
  const headers: Record<string, string> = {}
  if (csv) headers['Content-Type'] = 'text/csv'
  else if (method !== 'GET') headers['Content-Type'] = 'application/json'
  let response: Response
  try {
    response = await fetch('/api/v1' + path, {
      method, headers, signal, credentials: 'same-origin',
      body: csv ?? (method === 'GET' ? undefined : JSON.stringify(json ?? {})),
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError(0, 'offline', 'The server cannot be reached. Check that it is running and try again.')
  }
  const body = await response.json().catch(() => null)
  if (response.ok && body !== null) return body as T
  const problem = body?.error
  if (problem) throw new ApiError(response.status, problem.code, problem.message)
  throw new ApiError(response.status, 'unreadable', 'The server is not answering properly. Try again in a moment.')
}

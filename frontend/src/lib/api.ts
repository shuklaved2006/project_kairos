import type { ApiErrorBody, Entry, Window } from './types'

export const API_BASE = '/api'
export const API_VERSION = '0.2.0'

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message)
  }
}

function errorMessage(body: ApiErrorBody | null, status: number) {
  if (Array.isArray(body?.detail)) return body.detail.map((item) => item.msg).filter(Boolean).join(', ')
  if (typeof body?.detail === 'string') return body.detail
  return body?.message || `Request failed (${status})`
}

export async function apiRequest<T>(
  path: string,
  token: string,
  init: RequestInit & { idempotencyKey?: string } = {},
): Promise<T> {
  const headers = new Headers(init.headers)
  headers.set('Authorization', `Bearer ${token}`)
  headers.set('Accept', 'application/json')
  if (init.body) headers.set('Content-Type', 'application/json')
  if (init.idempotencyKey) headers.set('Idempotency-Key', init.idempotencyKey)

  const response = await fetch(`${API_BASE}${path}`, { ...init, headers })
  if (response.status === 401) throw new ApiError('Your session expired. Please sign in again.', 401)
  const body = (await response.json().catch(() => null)) as T | ApiErrorBody | null
  if (!response.ok) throw new ApiError(errorMessage(body as ApiErrorBody | null, response.status), response.status)
  return body as T
}

export async function captureAndInterpret(text: string, token: string, horizon: Window) {
  const capture = await apiRequest<Record<string, unknown>>('/captures', token, {
    method: 'POST',
    body: JSON.stringify({ text }),
    idempotencyKey: crypto.randomUUID(),
  })
  const captureId = String(capture.id ?? capture.identifier ?? '')
  if (!captureId) throw new ApiError('The capture was saved but no capture ID was returned.', 502)
  return apiRequest<Record<string, unknown>>('/intelligence/interpret', token, {
    method: 'POST',
    body: JSON.stringify({ capture_id: captureId, horizon }),
  })
}

export function acceptEntry(
  entry: Entry,
  token: string,
  capacity: { start: string; end: string; available: Window[]; buffer_minutes: number },
  override?: { acknowledge_risk: boolean; reason: string },
) {
  return apiRequest(`/entries/${encodeURIComponent(entry.id)}/accept`, token, {
    method: 'POST',
    body: JSON.stringify({
      version: entry.version,
      capacity,
      acknowledge_risk: override?.acknowledge_risk ?? false,
      reason: override?.reason || null,
    }),
  })
}

export function reminderAction(
  id: string,
  action: 'displayed' | 'acknowledged' | 'snoozed' | 'dismissed',
  token: string,
  snoozeUntil?: string,
) {
  return apiRequest(`/reminders/${encodeURIComponent(id)}/actions`, token, {
    method: 'POST',
    body: JSON.stringify({ action, snooze_until: snoozeUntil ?? null }),
  })
}

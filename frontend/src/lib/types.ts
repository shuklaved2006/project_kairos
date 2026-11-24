export type EntryKind = 'TASK' | 'RECURRING_HABIT' | 'CALENDAR_EVENT'
export type EntryStatus = 'draft' | 'accepted' | 'completed' | 'deferred'
export type ValueSource = 'explicit' | 'derived' | 'suggested' | 'unknown'

export type Window = { start: string; end: string }

export type Entry = {
  id: string
  title: string
  kind: EntryKind
  status: EntryStatus
  version: number
  deadline: string | null
  start: string | null
  end: string | null
  estimated_minutes: number | null
  effort_type?: 'per_item' | 'total'
  estimate_type?: 'approximate' | 'minimum'
  quantity?: number | null
  priority: number
  recurrence: 'daily' | 'weekly' | null
  category: string | null
  evidence?: string | null
  missing_fields?: string[]
  sources?: Partial<Record<'title' | 'timing' | 'effort' | 'recurrence' | 'priority', ValueSource>>
}

export type CapacityResult = {
  state: 'fits' | 'overloaded' | 'conflicting' | 'incomplete'
  label: string
  detail: string
  availableMinutes?: number
  plannedMinutes?: number
}

export type Reminder = {
  id: string
  entry_id: string
  title: string
  due_at: string
  displayed?: boolean
}

export type ApiErrorBody = {
  detail?: Array<{ msg?: string }> | string
  message?: string
}

import type { CapacityResult, Entry, Reminder } from '../lib/types'

const now = new Date()
const at = (dayOffset: number, hour: number, minute = 0) => {
  const value = new Date(now)
  value.setDate(value.getDate() + dayOffset)
  value.setHours(hour, minute, 0, 0)
  return value.toISOString()
}

export const sampleEntries: Entry[] = [
  {
    id: 'sample-brief',
    title: 'Finish the research brief',
    kind: 'TASK',
    status: 'accepted',
    version: 2,
    deadline: at(0, 17),
    start: at(0, 14),
    end: at(0, 15, 30),
    estimated_minutes: 90,
    effort_type: 'total',
    estimate_type: 'approximate',
    quantity: 1,
    priority: 82,
    recurrence: null,
    category: 'Deep work',
    evidence: '“finish the brief before the review at five”',
    sources: { title: 'explicit', timing: 'derived', effort: 'suggested', priority: 'derived' },
  },
  {
    id: 'sample-walk',
    title: 'Take an evening walk',
    kind: 'RECURRING_HABIT',
    status: 'accepted',
    version: 1,
    deadline: null,
    start: at(0, 18, 30),
    end: at(0, 19),
    estimated_minutes: 30,
    effort_type: 'per_item',
    estimate_type: 'minimum',
    quantity: 1,
    priority: 45,
    recurrence: 'daily',
    category: 'Wellbeing',
    evidence: '“walk for at least half an hour every day”',
    sources: { title: 'explicit', timing: 'suggested', effort: 'explicit', recurrence: 'explicit' },
  },
  {
    id: 'sample-review',
    title: 'Project review',
    kind: 'CALENDAR_EVENT',
    status: 'accepted',
    version: 1,
    deadline: null,
    start: at(0, 17),
    end: at(0, 17, 45),
    estimated_minutes: 45,
    effort_type: 'total',
    estimate_type: 'approximate',
    quantity: 1,
    priority: 75,
    recurrence: null,
    category: 'Meeting',
    evidence: '“review at five”',
    sources: { title: 'derived', timing: 'explicit', effort: 'derived' },
  },
  {
    id: 'sample-call',
    title: 'Call the dentist',
    kind: 'TASK',
    status: 'draft',
    version: 1,
    deadline: null,
    start: null,
    end: null,
    estimated_minutes: null,
    quantity: 1,
    priority: 30,
    recurrence: null,
    category: 'Personal',
    missing_fields: ['Timing', 'Effort'],
    evidence: '“also call the dentist”',
    sources: { title: 'explicit', timing: 'unknown', effort: 'unknown' },
  },
]

export const sampleCapacity: CapacityResult = {
  state: 'overloaded',
  label: 'Today is over capacity',
  detail: '45 minutes more work than the available focus windows. Nothing has been moved.',
  availableMinutes: 210,
  plannedMinutes: 255,
}

export const sampleReminders: Reminder[] = [
  {
    id: 'sample-reminder',
    entry_id: 'sample-brief',
    title: 'Research brief focus block',
    due_at: new Date(Date.now() - 60_000).toISOString(),
  },
]

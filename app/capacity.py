from datetime import timedelta
from .schemas import Entry, Capacity

def occurrences(entry, start, end):
    if not entry.start:
        return []
    left, right = entry.start, entry.end
    step = timedelta(days=1 if entry.recurrence == 'daily' else 7) if entry.recurrence else None
    if step and right <= start:
        jumps = max(0, (start - right) // step)
        left, right = left + jumps * step, right + jumps * step
    result = []
    while left < end:
        if right > start:
            result.append((left, right))
        if step is None:
            break
        left, right = left + step, right + step
    return result

def merge(intervals):
    result = []
    for left, right in sorted(intervals):
        if left >= right:
            continue
        if result and left <= result[-1][1]:
            result[-1] = (result[-1][0], max(right, result[-1][1]))
        else:
            result.append((left, right))
    return result

def calculate(entries, request: Capacity):
    available = merge([(max(w.start, request.start), min(w.end, request.end)) for w in request.available])
    blocks = []
    unknown = []
    demands = []
    unscheduled_habits = []
    unscheduled_tasks = []
    for item in entries:
        entry = Entry.model_validate(item['data'])
        if entry.status != 'accepted':
            continue
        occurrences_here = occurrences(entry, request.start, request.end)
        blocks.extend((max(a, request.start), min(b, request.end), item['id']) for a,b in occurrences_here)
        if entry.kind == 'RECURRING_HABIT' and not entry.start:
            unscheduled_habits.append(item['id'])
        if entry.kind != 'TASK':
            continue
        # Count only tasks due in/before this window or blocks in this window.
        if not entry.start and entry.deadline is None:
            unscheduled_tasks.append(item['id'])
        if not occurrences_here and (entry.deadline is None or entry.deadline > request.end):
            continue
        if entry.estimated_minutes is None:
            unknown.append(item['id'])
        else:
            reserved = sum((b-a).total_seconds()/60 for a,b in occurrences_here)
            remaining = max(0, entry.estimated_minutes - reserved)
            if remaining:
                demands.append((min(entry.deadline or request.end, request.end), remaining))
    busy = merge([(a,b) for a,b,_ in blocks])
    def free_until(limit):
        total = 0
        for a,b in available:
            b = min(b, limit)
            if b <= a:
                continue
            total += (b-a).total_seconds()/60
            for x,y in busy:
                total -= max(0, (min(b,y)-max(a,x)).total_seconds()/60)
        return max(0, total-request.buffer_minutes)
    conflicts = []
    for index,(a,b,identifier) in enumerate(blocks):
        for x,y,other in blocks[index+1:]:
            if max(a,x) < min(b,y):
                conflicts.append([identifier,other])
    required = sum(minutes for _,minutes in demands)
    shortfall = max([0] + [sum(m for d,m in demands if d <= deadline)-free_until(deadline) for deadline,_ in demands])
    state = 'overloaded' if shortfall > 0 or conflicts else 'incomplete' if unknown or unscheduled_habits or unscheduled_tasks else 'fits_estimates'
    return {'state':state, 'available_minutes':free_until(request.end), 'unscheduled_effort_minutes':required,
            'shortfall_minutes':shortfall, 'unknown_duration_ids':unknown, 'unscheduled_habit_ids':unscheduled_habits,
            'conflicts':conflicts, 'unscheduled_task_ids':unscheduled_tasks, 'basis':'Known commitments and supplied availability only; flexible work is assumed splittable.'}

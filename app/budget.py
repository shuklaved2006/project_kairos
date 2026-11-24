from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import select, insert, update
from .database import records


def reserve_ai_request(conn, now=None, daily_limit=100, timezone_name='Asia/Kolkata'):
    """Call inside the application's serialized transaction BEFORE every provider attempt.

    Reservations are never refunded: failures/retries consume budget too.
    This is a server-side service, not an unauthenticated client endpoint.
    """
    now = now or datetime.now(timezone.utc)
    key = 'ai-budget:' + now.astimezone(ZoneInfo(timezone_name)).date().isoformat()
    row = conn.execute(select(records).where(records.c.id == key)).mappings().first()
    used = row['data']['used'] if row else 0
    if used >= daily_limit:
        raise ValueError('Daily AI request budget exhausted')
    data = {'used':used+1, 'limit':daily_limit, 'reset_timezone':timezone_name}
    if row:
        conn.execute(update(records).where(records.c.id == key).values(data=data, version=row['version']+1))
    else:
        conn.execute(insert(records).values(id=key, kind='ai_budget', version=1, data=data))
    return data

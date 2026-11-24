from datetime import datetime, timedelta
from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field, AwareDatetime, model_validator

class Kind(str, Enum):
    TASK = 'TASK'
    RECURRING_HABIT = 'RECURRING_HABIT'
    CALENDAR_EVENT = 'CALENDAR_EVENT'

class Entry(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    kind: Kind
    status: Literal['draft', 'accepted', 'completed', 'deferred'] = 'draft'
    deadline: AwareDatetime | None = None
    start: AwareDatetime | None = None
    end: AwareDatetime | None = None
    estimated_minutes: int | None = Field(default=None, ge=1, le=10080)
    priority: int = Field(default=0, ge=0, le=100)
    recurrence: Literal['daily', 'weekly'] | None = None
    category: str | None = Field(default=None, max_length=100)
    source_text: str | None = Field(default=None, max_length=10000)

    @model_validator(mode='after')
    def valid(self):
        if not self.title.strip():
            raise ValueError('Title cannot be blank')
        if (self.start is None) != (self.end is None):
            raise ValueError('Supply both start and end')
        if self.start and self.end <= self.start:
            raise ValueError('End must follow start')
        if self.status == 'accepted' and self.kind == Kind.CALENDAR_EVENT and not self.start:
            raise ValueError('Accepted events require start and end')
        if self.status == 'accepted' and self.kind == Kind.RECURRING_HABIT and not self.recurrence:
            raise ValueError('Accepted habits require recurrence')
        if self.recurrence and self.kind == Kind.TASK:
            raise ValueError('Tasks cannot recur; use a habit or event')
        if self.recurrence and not self.start:
            raise ValueError('Recurrence requires an anchor start/end')
        if self.recurrence and self.end - self.start >= timedelta(days=1 if self.recurrence == 'daily' else 7):
            raise ValueError('Occurrence must be shorter than recurrence interval')
        if self.kind == Kind.TASK and self.deadline and self.end and self.end > self.deadline:
            raise ValueError('Task block ends after deadline')
        return self

class Revision(BaseModel):
    version: int = Field(ge=1)
    entry: Entry
    reason: str | None = Field(default=None, max_length=500)

class Window(BaseModel):
    start: AwareDatetime
    end: AwareDatetime
    @model_validator(mode='after')
    def valid(self):
        if self.end <= self.start or self.end - self.start > timedelta(days=31):
            raise ValueError('Window must be positive and at most 31 days')
        return self

class Capacity(Window):
    available: list[Window] = Field(max_length=100)
    buffer_minutes: int = Field(default=0, ge=0, le=44640)

class Acceptance(BaseModel):
    version: int = Field(ge=1)
    capacity: Capacity
    acknowledge_risk: bool = False
    reason: str | None = Field(default=None, max_length=500)

class Completion(BaseModel):
    version: int = Field(ge=1)
    actual_minutes: int = Field(ge=1, le=10080)

class Reminder(BaseModel):
    entry_id: str
    due_at: AwareDatetime

class ReminderAction(BaseModel):
    action: Literal['displayed', 'acknowledged', 'snoozed', 'dismissed']
    snooze_until: AwareDatetime | None = None

class Capture(BaseModel):
    text: str = Field(min_length=1, max_length=10000)

class FocusStart(BaseModel):
    entry_id: str
    planned_minutes: int = Field(ge=1, le=240)

class Profile(BaseModel):
    timezone: str = 'Asia/Kolkata'
    availability: list[Window] = Field(default_factory=list, max_length=100)
    buffer_minutes: int = Field(default=0, ge=0, le=1440)
    @model_validator(mode='after')
    def valid_timezone(self):
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError('Unknown IANA timezone')
        return self

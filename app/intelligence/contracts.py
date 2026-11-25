from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, AwareDatetime, model_validator
from ..schemas import Window

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')

class Evidence(StrictModel):
    field: Literal['title','kind','deadline','start','end','estimated_minutes','priority','recurrence','category','quantity','estimate_qualifier','estimate_basis','anchor_date']
    origin: Literal['explicit','derived','suggested','unknown']
    quote: str = Field(max_length=1000)
    reason: str = Field(max_length=500)

class Proposal(StrictModel):
    temp_id: str = Field(min_length=1,max_length=40)
    operation: Literal['create_draft']
    title: str = Field(min_length=1,max_length=300)
    kind: Literal['TASK','RECURRING_HABIT','CALENDAR_EVENT']
    source_quote: str = Field(min_length=1,max_length=1000)
    deadline: AwareDatetime | None
    start: AwareDatetime | None
    end: AwareDatetime | None
    estimated_minutes: int | None = Field(ge=1,le=10080)
    priority: int | None = Field(ge=0,le=100)
    recurrence: Literal['daily','weekly'] | None
    category: str | None = Field(max_length=100)
    anchor_date: date | None = None
    quantity: int = Field(default=1,ge=1,le=100)
    estimate_qualifier: Literal['approximate','minimum','unspecified'] = 'unspecified'
    estimate_basis: Literal['per_item','total'] = 'total'
    evidence: list[Evidence] = Field(min_length=2,max_length=13)
    missing_fields: list[Literal['deadline','start','end','estimated_minutes','priority','recurrence']] = Field(max_length=6)

    @model_validator(mode='after')
    def consistent(self):
        if not self.title.strip():
            raise ValueError('Blank title')
        if self.start and self.end and self.end <= self.start:
            raise ValueError('End must follow start')
        if self.kind == 'TASK' and self.recurrence:
            raise ValueError('Task cannot recur')
        if self.kind == 'TASK' and self.deadline and self.end and self.end > self.deadline:
            raise ValueError('Task block exceeds deadline')
        if len(set(self.missing_fields)) != len(self.missing_fields):
            raise ValueError('Duplicate missing fields')
        return self

class Question(StrictModel):
    item_id: str | None
    question: str = Field(min_length=1,max_length=300)

class Unfiled(StrictModel):
    source_quote: str = Field(min_length=1,max_length=1000)
    reason: str = Field(min_length=1,max_length=300)

class Amendment(StrictModel):
    amendment_id: str = Field(min_length=1,max_length=40)
    entry_id: str
    version: int = Field(ge=1)
    action: Literal['reschedule','defer']
    start: AwareDatetime | None
    end: AwareDatetime | None
    source_quote: str = Field(min_length=1,max_length=1000)
    reason: str = Field(max_length=500)

class Interpretation(StrictModel):
    message: str = Field(default='',max_length=1800)
    amendments: list[Amendment] = Field(default_factory=list,max_length=5)
    items: list[Proposal] = Field(max_length=20)
    questions: list[Question] = Field(max_length=3)
    unfiled: list[Unfiled] = Field(max_length=20)

class InterpretRequest(StrictModel):
    capture_id: str = Field(min_length=1,max_length=128)
    horizon: Window
    demo_stage: Literal[1,2,3] = 1

class TradeoffChange(StrictModel):
    entry_id: str
    version: int = Field(ge=1)
    operation: Literal['defer','move','reduce_scope']
    start: AwareDatetime | None = None
    end: AwareDatetime | None = None
    estimated_minutes: int | None = Field(default=None,ge=1,le=10080)
    scope_description: str | None = Field(default=None,min_length=1,max_length=500)

class Tradeoff(StrictModel):
    changes: list[TradeoffChange] = Field(min_length=1,max_length=5)

from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class TimelineEventBase(BaseModel):
    date: str
    title: str
    description: str
    image_url: Optional[str] = None
    media_type: str = "photo"

class TimelineEventCreate(TimelineEventBase):
    pass

class TimelineEvent(TimelineEventBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True

class TimeCapsuleBase(BaseModel):
    author: str
    message: str
    open_date: str

class TimeCapsuleCreate(TimeCapsuleBase):
    pass

class TimeCapsule(TimeCapsuleBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True

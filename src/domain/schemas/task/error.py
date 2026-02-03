from datetime import datetime

from pydantic import BaseModel


class TaskCreateErrorDTO(BaseModel):
    can_create: bool = True
    detail: str | None = None
    available_start: datetime | None = None
    available_end: datetime | None = None
from datetime import datetime

from pydantic import BaseModel, field_validator

from domain.schemas.task.common import StatusRetriveDTO, SprintRetriveDTO, CategoryRetriveDTO, TagRetrieveDTO, \
    SubtaskRetrieveDTO
from domain.schemas.user.main import UserRetriveDTO


class TaskCreateDTO(BaseModel):
    name: str
    description: str = ""
    started_at: datetime | None = None
    finished_at: datetime | None = None
    deadline_at: datetime | None = None
    status_id: int | None = None
    sprint_id: int | None = None
    category_id: int | None = None

    @field_validator("started_at", "finished_at", "deadline_at", mode="before")
    @staticmethod
    def _empty_datetime_to_none(value):
        if value == "" or value == "null" or value == "undefined":
            return None
        return value


class TaskLifecycleSegment(BaseModel):
    status: str
    color: str
    duration: str
    duration_seconds: int
    percent: float
    start: datetime
    end: datetime


class TaskRetrieveDTO(BaseModel):
    id: int
    name: str
    description: str = ""
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    deadline_at: datetime | None = None
    status: StatusRetriveDTO | None = None
    sprint: SprintRetriveDTO | None = None
    category: CategoryRetriveDTO | None = None
    user: UserRetriveDTO | None = None
    tags: list[TagRetrieveDTO] = []
    subtasks: list[SubtaskRetrieveDTO] = []
    lifecycle: list[TaskLifecycleSegment] = []
    total_duration: str = ""

    @field_validator("subtasks", "tags", mode="before")
    @staticmethod
    def validate_subtask_field(value) -> list:
        return value.all()

    class Config:
        from_attributes = True


class TaskUpdateDTO(TaskCreateDTO):
    id: int


class TaskStatusUpdateDTO(BaseModel):
    status_id: int


class TaskTimingUpdateDTO(BaseModel):
    started_at: datetime
    finished_at: datetime


class TaskShortRetriveDTO(BaseModel):
    id: int
    name: str
    description: str = ""
    started_at: datetime | None = None
    finished_at: datetime | None = None
    deadline_at: datetime | None = None
    tags: list[TagRetrieveDTO] = []
    subtasks: list[SubtaskRetrieveDTO] = []

    @field_validator("subtasks", "tags", mode="before")
    @staticmethod
    def validate_subtask_field(value) -> list:
        return value.all()

    class Config:
        from_attributes = True

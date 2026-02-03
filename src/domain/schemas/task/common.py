from datetime import datetime

from pydantic import BaseModel

from domain.enums.status_type import StatusType


class StatusRetriveDTO(BaseModel):
    id: int
    name: str
    type: StatusType
    color: str

    class Config:
        from_attributes = True
        use_enum_values = True


class SprintRetriveDTO(BaseModel):
    id: int
    name: str
    started_at: datetime
    ended_at: datetime
    active: bool

    class Config:
        from_attributes = True


class CategoryRetriveDTO(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class CategoryCreateDTO(BaseModel):
    name: str


class TagRetrieveDTO(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class TagCreateDTO(BaseModel):
    name: str


class SubtaskCreateDTO(BaseModel):
    name: str
    completed: bool = False


class SubtaskBulkCreateDTO(BaseModel):
    subtasks: list[SubtaskCreateDTO] = []


class SubtaskRetrieveDTO(BaseModel):
    id: int
    name: str
    completed: bool

    class Config:
        from_attributes = True


class SubtaskCompletedUpdateDTO(BaseModel):
    completed: bool | None = None


class CommentCreateDTO(BaseModel):
    text: str


class CommentRetrieveDTO(BaseModel):
    id: int
    text: str
    created_at: datetime
    user_id: int
    user_name: str

    class Config:
        from_attributes = True


class TaskHistoryRetrieveDTO(BaseModel):
    id: int
    field: str
    old_value: str
    new_value: str
    created_at: datetime
    user_id: int | None = None
    user_name: str | None = None

    class Config:
        from_attributes = True


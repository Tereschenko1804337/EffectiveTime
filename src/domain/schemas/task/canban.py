from pydantic import BaseModel, Field, field_validator

from domain.schemas.task.main import TaskShortRetriveDTO


class CanbanColumnRetriveDTO(BaseModel):
    id: int
    name: str
    color: str
    tasks: list[TaskShortRetriveDTO] = Field(alias='task_set', default=[])

    @field_validator('tasks', mode='before')
    @staticmethod
    def tasks_validator(value) -> list[TaskShortRetriveDTO]:
        return value.all()

    class Config:
        from_attributes = True
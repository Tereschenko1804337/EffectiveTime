from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator


class UserRetriveDTO(BaseModel):
    id: int
    username: str
    photo_url: str | None = None

    class Config:
        from_attributes = True


class SleepSettingsRetrieveDTO(BaseModel):
    wake_up_time: str
    bed_time: str


class SleepSettingsUpdateDTO(BaseModel):
    wake_up_time: str
    bed_time: str

    @field_validator("wake_up_time", "bed_time")
    @classmethod
    def _validate_hhmm(cls, v: str) -> str:
        datetime.strptime(v, "%H:%M")
        return v


class ThemeRetrieveDTO(BaseModel):
    theme: str


class ThemeUpdateDTO(BaseModel):
    theme: str


class ChangePasswordDTO(BaseModel):
    old_password: str
    new_password: str
    confirm_password: str

    @field_validator('confirm_password')
    def passwords_match(cls, v, values):
        if 'new_password' in values.data and v != values.data['new_password']:
            raise ValueError('Пароли не совпадают')
        return v

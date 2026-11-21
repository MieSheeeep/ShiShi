"""Strict request boundaries for the cooking journal."""
from datetime import date, datetime, timedelta, timezone
from typing import Literal
from uuid import UUID
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def shanghai_today():
    return datetime.now(timezone(timedelta(hours=8))).date()


class Request(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class Dated(Request):
    cooked_on: str | None = None

    @field_validator('cooked_on')
    @classmethod
    def valid_date(cls, value):
        if value is None or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            raise ValueError('请填写真实日期')
        if date.fromisoformat(value) > shanghai_today():
            raise ValueError('不能记录未来的下厨日期')
        return value


class Create(Dated):
    client_id: str
    recipe_ids: list[int] = Field(default_factory=list, max_length=20)
    manual_name: str | None = Field(default=None, min_length=1, max_length=80)
    dish_key: str | None = Field(default=None, min_length=1, max_length=100)

    @field_validator('client_id')
    @classmethod
    def valid_uuid(cls, value):
        return str(UUID(value))

    @field_validator('manual_name')
    @classmethod
    def nonblank_name(cls, value):
        if value is None or not value.strip():
            raise ValueError('补记菜名不能为空')
        return value.strip()

    @model_validator(mode='after')
    def selection(self):
        if bool(self.recipe_ids) == bool(self.manual_name):
            raise ValueError('请选择食谱或填写补记菜名')
        if len(set(self.recipe_ids)) != len(self.recipe_ids) or any(not 1 <= i <= 2**63 - 1 for i in self.recipe_ids):
            raise ValueError('食谱编号重复或无效')
        if self.dish_key and not self.manual_name:
            raise ValueError('继续练习需填写菜名')
        return self


class DishPatch(Request):
    id: str = Field(min_length=1)
    outcome: Literal['pending', 'success', 'practice', 'skipped'] | None = None
    note: str | None = Field(default=None, max_length=1000)
    photos: list[str] | None = Field(default=None, max_length=12)
    completed_steps: list[str] | None = None

    @model_validator(mode='after')
    def no_null(self):
        if any(getattr(self, key) is None for key in self.model_fields_set):
            raise ValueError('字段不能为空')
        return self


class Version(Request):
    version: int = Field(ge=1)


class Patch(Dated, Version):
    title: str | None = Field(default=None, max_length=80)
    note: str | None = Field(default=None, max_length=1000)
    dishes: list[DishPatch] | None = Field(default=None, max_length=20)

    @model_validator(mode='after')
    def no_null(self):
        if any(getattr(self, key) is None for key in self.model_fields_set):
            raise ValueError('字段不能为空')
        return self


class Mark(Request):
    dish_key: str = Field(min_length=1, max_length=100)
    status: Literal['tried', 'practice', 'signature']

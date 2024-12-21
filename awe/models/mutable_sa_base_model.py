from pydantic import BaseModel
from sqlalchemy.ext.mutable import Mutable
from typing import Any
from typing_extensions import Self
from .json_pydantic_field import JsonPydanticField

class MutableSABaseModel(BaseModel, Mutable):

    def __setattr__(self, name: str, value: Any) -> None:
        """Allows SQLAlchmey Session to track mutable behavior"""
        self.changed()
        return super().__setattr__(name, value)

    @classmethod
    def coerce(cls, key: str, value: Any) -> Self | None:
        """Convert JSON to pydantic model object allowing for mutable behavior"""
        if isinstance(value, cls) or value is None:
            return value

        if isinstance(value, str):
            return cls.model_validate_json(value)

        if isinstance(value, dict):
            return cls(**value)

        return super().coerce(key, value)

    @classmethod
    def to_sa_type(cls):
        return cls.as_mutable(JsonPydanticField(cls))

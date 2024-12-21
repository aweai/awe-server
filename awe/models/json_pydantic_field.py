from sqlalchemy import types, JSON
from pydantic import BaseModel

class JsonPydanticField(types.TypeDecorator):
    impl = JSON

    def __init__(self, pydantic_model=None):
        super().__init__()
        self.pydantic_model = pydantic_model

    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value: BaseModel, _):
        return value.model_dump() if value is not None else None

    def process_result_value(self, value, _):
        return self.pydantic_model.model_validate(value) if value is not None else None

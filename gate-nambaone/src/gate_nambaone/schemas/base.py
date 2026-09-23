from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Модель с полями в camelCase, как в API Namba One. В коде используются snake_case имена."""

    model_config = ConfigDict(alias_generator=to_camel, validate_by_name=True, validate_by_alias=True)

    def to_json(self) -> str:
        """JSON для тела запроса: camelCase и без незаполненных полей."""
        return self.model_dump_json(by_alias=True, exclude_none=True)

from pydantic import (
    GetCoreSchemaHandler,
    GetJsonSchemaHandler
)
from pydantic_core import core_schema
from pydantic.json_schema import JsonSchemaValue

from numpy import datetime64, datetime_data, dtypes, datetime_as_string
from typing import Any, Annotated

from neo4j.time import DateTime as Neo4jDateTime
from pydantic_core.core_schema import ValidationInfo


# https://docs.pydantic.dev/latest/concepts/types/#handling-third-party-types
class _DT64PydanticAnnotation:

    @classmethod
    def __get_pydantic_core_schema__(
            cls,
            _source_type: Any,
            _handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:

        def validate_from_str(value: str) -> datetime64:
            return datetime64(value)

        from_str_schema = core_schema.chain_schema(
            [
                core_schema.str_schema(),
                core_schema.no_info_plain_validator_function(validate_from_str)
            ]
        )

        def validate_from_dict(value: dict) -> datetime64:
            return datetime64(value['str'], (value['unit'], value['step']))

        from_dict_schema = core_schema.chain_schema(
            [
                core_schema.dict_schema(),
                core_schema.no_info_plain_validator_function(validate_from_dict)
            ]
        )

        def validate_from_neo4j(value: Neo4jDateTime, info: ValidationInfo) -> datetime64:
            iso = value.isoformat()
            return datetime64(iso)

        from_neo4j_schema = core_schema.chain_schema(
            [
                core_schema.is_instance_schema(Neo4jDateTime),
                core_schema.with_info_plain_validator_function(validate_from_neo4j)
            ]
        )

        def serialize_time_to_dict(dt64: datetime64) -> dict:
            return {'str': str(datetime_as_string(dt64))} | {i: j for i, j in zip(('unit', 'step'), datetime_data(dt64))}

        return core_schema.json_or_python_schema(
            json_schema=from_str_schema,
            python_schema=core_schema.union_schema(
                [
                    core_schema.is_instance_schema(datetime64),
                    from_str_schema,
                    from_dict_schema,
                    from_neo4j_schema
                ]
            ),
            serialization=core_schema.plain_serializer_function_ser_schema(
                serialize_time_to_dict
            )
        )

    @classmethod
    def __get_pydantic_json_schema__(
            cls, _core_schema: core_schema.CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        return handler(core_schema.int_schema())

PyDT64 = Annotated[datetime64|str|Neo4jDateTime, _DT64PydanticAnnotation]


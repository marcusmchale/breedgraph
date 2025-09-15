import warnings
from pydantic import (
    GetCoreSchemaHandler,
    GetJsonSchemaHandler, BaseModel
)
from pydantic_core import core_schema
from pydantic.json_schema import JsonSchemaValue

from dataclasses import dataclass
import numpy as np
from typing import Any, Annotated, TypeAlias, Dict

from datetime import datetime, timezone
from neo4j.time import DateTime as Neo4jDateTime
from pydantic_core.core_schema import ValidationInfo

@dataclass
class WriteStamp:
    user: int  # user id
    time: np.datetime64

def serialize_npdt64(dt64: np.datetime64|None, to_neo4j:bool = False) -> Dict[str, str|int|None]:
    if dt64 is None:
        return {
            'time' : None,
            'unit': None,
            'step': None
        }
    else:
        return (
            {'time': npdt64_to_neo4j(dt64) if to_neo4j else str(np.datetime_as_string(dt64))} |
            {i: j for i, j in zip(('unit', 'step'), np.datetime_data(dt64))}
        )

def deserialize_time(time: Neo4jDateTime | str | None, unit:str = None, step:str = None) -> np.datetime64 | datetime | None:
    if time is None:
        return None
    elif isinstance(time, Neo4jDateTime):
        if unit is None:
            # should be a timezone aware transaction timestamp
            return time.to_native()
        else:
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', UserWarning)
                return np.datetime64(time.isoformat(), (unit, step))
    else:
        import pdb; pdb.set_trace()

def npdt64_to_pydt(ts: np.datetime64) -> datetime:
    # Convert to ns, then Python datetime via integer timestamp
    ns = ts.astype('datetime64[ns]').astype('int')  # nanoseconds since epoch
    py_dt = datetime.fromtimestamp(ns / 1_000_000_000, tz=timezone.utc)
    return py_dt

def npdt64_to_neo4j(npdt: np.datetime64) -> Neo4jDateTime|None:
    # Convert to Python datetime
    if npdt is None:
        return None
    py_dt = npdt64_to_pydt(npdt)
    # Ensure timezone-aware (Neo4j prefers that)
    if py_dt.tzinfo is None:
        py_dt = py_dt.replace(tzinfo=timezone.utc)
    # Wrap in neo4j.time.DateTime
    return Neo4jDateTime(
        py_dt.year, py_dt.month, py_dt.day,
        py_dt.hour, py_dt.minute, py_dt.second,
        py_dt.microsecond * 1000,
        tzinfo=py_dt.tzinfo
    )


# https://docs.pydantic.dev/latest/concepts/types/#handling-third-party-types
class _DT64PydanticAnnotation:

    @classmethod
    def __get_pydantic_core_schema__(
            cls,
            _source_type: Any,
            _handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:

        def validate_from_datetime(value: datetime) -> np.datetime64:
            return np.datetime64(value)

        from_datetime_schema = core_schema.chain_schema(
            [
                core_schema.is_instance_schema(datetime),
                core_schema.no_info_plain_validator_function(validate_from_datetime)
            ]
        )

        def validate_from_str(value: str) -> np.datetime64:
            return np.datetime64(value)

        from_str_schema = core_schema.chain_schema(
            [
                core_schema.str_schema(),
                core_schema.no_info_plain_validator_function(validate_from_str)
            ]
        )

        def validate_from_dict(value: dict) -> np.datetime64:
            return np.datetime64(value['str'], (value['unit'], value['step']))

        from_dict_schema = core_schema.chain_schema(
            [
                core_schema.dict_schema(),
                core_schema.no_info_plain_validator_function(validate_from_dict)
            ]
        )

        def validate_from_neo4j(value: Neo4jDateTime, _: ValidationInfo) -> np.datetime64:
            iso = value.isoformat()
            return np.datetime64(iso)

        from_neo4j_schema = core_schema.chain_schema(
            [
                core_schema.is_instance_schema(Neo4jDateTime),
                core_schema.with_info_plain_validator_function(validate_from_neo4j)
            ]
        )

        def serialize_time_to_dict(dt64: np.datetime64) -> dict:
            return {'str': str(np.datetime_as_string(dt64))} | {i: j for i, j in zip(('unit', 'step'), np.datetime_data(dt64))}

        return core_schema.json_or_python_schema(
            json_schema=from_str_schema,
            python_schema=core_schema.union_schema(
                [
                    core_schema.is_instance_schema(np.datetime64),
                    from_datetime_schema,
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

PyDT64: TypeAlias = Annotated[
    datetime|np.datetime64|str|Neo4jDateTime,
    _DT64PydanticAnnotation
]
"""
A flexible datetime type that accepts:
- Python datetime objects
- NumPy datetime64 objects  
- ISO format strings
- Neo4j DateTime objects
- Dict format: {'str': 'datetime_string', 'unit': 'D', 'step': 1}

All inputs are normalized to numpy.datetime64 for consistent handling.
"""

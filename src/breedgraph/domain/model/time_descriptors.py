import re
from pydantic import (
    GetCoreSchemaHandler,
    GetJsonSchemaHandler, BaseModel
)
from pydantic_core import core_schema
from pydantic.json_schema import JsonSchemaValue

from dataclasses import dataclass
import numpy as np
from typing import Any, Annotated, TypeAlias, Dict

from datetime import date, datetime
from neo4j.time import DateTime as Neo4jDateTime
from pydantic_core.core_schema import ValidationInfo

@dataclass
class WriteStamp:
    user: int  # user id
    time: datetime | None  # the transaction time, None where hidden

# Observation times (of records, studies, trials, positions and germplasm) are the wall-clock time at the location,
# at the precision they were given: numpy datetime64 values, stored as Neo4j LocalDateTime with their unit and step.
# A time given to a unit stands for that whole period, so as an end it reaches the start of the next (see upper).

# A trailing Z or offset on a time of day, e.g. 2021-05-03T10:30Z or 2021-05-03T10:30+02:00
_OFFSET = re.compile(r'[T ]\d[^Z+-]*(Z|[+-]\d{2}(:?\d{2})?)$')

class TimeZoneGivenError(ValueError):
    pass

def parse_local_datetime(value: str) -> np.datetime64:
    """A time as entered, at the precision given, e.g. '2021', '2021-05' or '2021-05-03T10:30'; offsets are refused"""
    if _OFFSET.search(value.strip()):
        raise TimeZoneGivenError(
            f"Times are local to the location, so are given without a time zone or offset: {value}"
        )
    return np.datetime64(value.strip())

def local_datetime64(value: np.datetime64 | datetime | str) -> np.datetime64:
    """A local time as datetime64, refusing time zone aware input"""
    if isinstance(value, np.datetime64):
        return value
    if isinstance(value, str):
        return parse_local_datetime(value)
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            raise TimeZoneGivenError(
                f"Times are local to the location, so are given without a time zone or offset: {value.isoformat()}"
            )
        return np.datetime64(value)
    if isinstance(value, date):
        return np.datetime64(value)
    raise TypeError(f"Cannot read a time from {type(value)}")

def upper(dt64: np.datetime64) -> np.datetime64:
    """The end (exclusive) of the period a time stands for: 2021 -> 2022, 2021-05 -> 2021-06, 2021-05-03 -> 2021-05-04"""
    unit, step = np.datetime_data(dt64)
    return dt64 + np.timedelta64(step, unit)

def same_time(time: np.datetime64 | None, other: np.datetime64 | None) -> bool:
    """Whether two times are the same as entered: numpy counts 2021-05 and 2021-05-01 as equal, this does not"""
    if time is None or other is None:
        return time is None and other is None
    return time == other and np.datetime_data(time) == np.datetime_data(other)

def serialize_npdt64(dt64: np.datetime64|None, to_neo4j:bool = False) -> Dict[str, str|int|None]:
    if dt64 is None:
        return {
            'time' : None,
            'unit': None,
            'step': None
        }
    else:
        return (
            {'time': npdt64_to_local(dt64) if to_neo4j else str(np.datetime_as_string(dt64))} |
            {i: j for i, j in zip(('unit', 'step'), np.datetime_data(dt64))}
        )

def deserialize_time(time: Neo4jDateTime | str | None, unit:str = None, step:str = None) -> np.datetime64 | datetime | None:
    """
    A stored time: an observation time (a LocalDateTime with its unit and step) as datetime64 at its precision,
    or a timestamp, e.g. of a transaction, as a timezone aware datetime
    """
    if time is None:
        return None
    elif isinstance(time, Neo4jDateTime):
        if unit is None:
            return time.to_native()
        else:
            return np.datetime64(time.isoformat(), (unit, step))
    elif isinstance(time, str):
        return datetime.fromisoformat(time)
    else:
        raise NotImplementedError(f"Cannot deserialize time from type {type(time)}")



def npdt64_to_local(ts: np.datetime64) -> Neo4jDateTime:
    """A local time as a Neo4j LocalDateTime (a DateTime without a time zone), to the microsecond"""
    py_obj = ts.astype('datetime64[us]').astype(object)
    return Neo4jDateTime(
        py_obj.year, py_obj.month, py_obj.day, py_obj.hour, py_obj.minute, py_obj.second, py_obj.microsecond * 1000
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
            return local_datetime64(value)

        from_datetime_schema = core_schema.chain_schema(
            [
                core_schema.is_instance_schema(datetime),
                core_schema.no_info_plain_validator_function(validate_from_datetime)
            ]
        )

        def validate_from_str(value: str) -> np.datetime64:
            return parse_local_datetime(value)

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
            return local_datetime64(value.to_native())

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

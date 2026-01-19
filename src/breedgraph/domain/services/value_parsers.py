import re

from numpy import datetime64, float64

from src.breedgraph.custom_exceptions import NoResultFoundError

from src.breedgraph.domain.model.ontology import  ScaleStored, ScaleType, ScaleCategoryStored

from typing import List


class ValueParser:

    def parse(
            self,
            value: str|int,
            scale: ScaleStored,
            categories: List[ScaleCategoryStored]
    ) -> str|int|None:
        if scale.scale_type == ScaleType.COMPLEX:
            return None

        if isinstance(value, str):
            if scale.scale_type == ScaleType.DATETIME:
                return self._parse_datetime(value)
            elif scale.scale_type == ScaleType.DURATION:
                return self._parse_duration(value)
            elif scale.scale_type == ScaleType.NUMERICAL:
                return self._parse_numeric(value)
            elif scale.scale_type == ScaleType.TEXT:
                return self._parse_text(value)
            elif scale.scale_type in [ScaleType.NOMINAL, ScaleType.ORDINAL]:
                return self._parse_category_text(value, categories)
            else:
                raise ValueError("String value provided for the wrong scale type")

        elif isinstance(value, int):
            if scale.scale_type in [ScaleType.NOMINAL, ScaleType.ORDINAL]:
                return self._parse_category_int(value, categories)
            else:
                raise ValueError("Integer values are only supported for nominal and ordinal scales")

        else:
            raise ValueError("Only str and int values may be parsed as values")

    @staticmethod
    def _parse_datetime(value:str) -> str:
        value = value.strip()
        datetime64(value)
        return value

    @staticmethod
    def _parse_duration(value:str) -> str:
        # ISO8601 duration format is: P(n)Y(n)M(n)DT(n)H(n)M(n)S

        def remove_match(string:str, pattern: str):
            if match := re.search(f'^([0-9]+){pattern}', string):
                string = string[len(match.group(1)) + 1:]
            return string

        value = "".join(value.split())
        if not len(value) >= 2:
            raise ValueError(
                "ISO8601 durations must be at least 2 characters in length"
            )
        if not value[0] == "P":
            raise ValueError("ISO8601 durations must start with 'P'")

        if "T" in value:
            date, time = value.split("T")
            for p in ["H", "M", "S"]:
                remove_match(time, p)
            if len(time) != 0:
                raise ValueError("Duration must be formatted according to ISO860 duration")
        else:
            date = value

        date = date[1:]
        for p in ["Y", "M", "W", "D"]:
            remove_match(date, p)
        if len(date) != 0:
            raise ValueError("Duration must be formatted according to ISO860 duration")

        return value

    @staticmethod
    def _parse_numeric(value: str) -> str:
        float64(value.replace(',', '.'))
        return value.strip() # keep in format as submitted, see ISO 80000-1

    @staticmethod
    def _parse_text(value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Text values may not be empty strings")
        return value

    @staticmethod
    def _parse_category_text(value: str, categories: List[ScaleCategoryStored]) -> str:
        matches = [c for c in categories if value.casefold() in [n.casefold() for n in c.names]]
        if len(matches) == 0:
            raise ValueError("String doesn't match a category name")
        elif len(matches) == 1:
            return matches[0].name
        else:
            raise ValueError(f"String matches multiple categories {matches}")


    @staticmethod
    def _parse_category_int(value: int, categories: List[ScaleCategoryStored]):
        for c in categories:
            if c.id == value:
                return value
        else:
            raise NoResultFoundError(f"Matching category not found for scale: {value}")

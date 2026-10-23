import re

from numpy import float64

from breedgraph.domain.model.time_descriptors import parse_local_datetime

from breedgraph.domain.model.ontology import ScaleStored, ScaleType, ScaleCategory

from typing import List


class ValueParser:

    def parse(
            self,
            value: str|None,
            scale: ScaleStored
    ) -> str|None:
        """The value as stored, checked against the scale: a category's name as the scale has it"""
        if scale.scale_type == ScaleType.COMPLEX:
            return None

        if isinstance(value, str):
            if scale.scale_type == ScaleType.DATE:
                return self._parse_datetime(value)
            elif scale.scale_type == ScaleType.DURATION:
                return self._parse_duration(value)
            elif scale.scale_type == ScaleType.NUMERICAL:
                return self._parse_numeric(value)
            elif scale.scale_type == ScaleType.TEXT:
                return self._parse_text(value)
            elif scale.scale_type in [ScaleType.NOMINAL, ScaleType.ORDINAL]:
                return self._parse_category(value, scale.categories)
            else:
                raise ValueError("String value provided for the wrong scale type")

        else:
            raise ValueError("Only text values may be parsed as values")

    @staticmethod
    def _parse_datetime(value:str) -> str:
        """A date or time as entered, local like record times, so without an offset"""
        value = value.strip()
        parse_local_datetime(value)
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
    def _parse_category(value: str, categories: List[ScaleCategory]) -> str:
        """A category's name, matched ignoring case: names on a scale differ ignoring case"""
        value = value.strip().casefold()
        for category in categories:
            if category.name.casefold() == value:
                return category.name
        raise ValueError("Value doesn't match a category name of the scale")

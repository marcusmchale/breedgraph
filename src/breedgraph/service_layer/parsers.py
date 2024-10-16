from abc import ABC
import re

from numpy import datetime64, float64

from src.breedgraph.custom_exceptions import NoResultFoundError

from src.breedgraph.domain.model.ontology import  Scale, ScaleType, ScaleCategory
from src.breedgraph.domain.model.germplasm import Germplasm, GermplasmEntryStored


from typing import List, Set

class ValueParser(ABC):

    def parse(
            self,
            value:str|int,
            scale: Scale,
            categories: List[ScaleCategory],
            germplasms: List[Germplasm]

    ) -> str|int:
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
            elif scale.scale_type == ScaleType.GERMPLASM:
                return self._parse_germplasm_text(value, germplasms)

        elif isinstance(value, int):
            if scale.scale_type in [ScaleType.NOMINAL, ScaleType.ORDINAL]:
                return self._parse_category_int(value, categories)
            elif scale.scale_type == ScaleType.GERMPLASM:
                return self._parse_germplasm_int(value, germplasms)
            else:
                raise ValueError("Integer values are only supported for nominal, ordinal or germplasm scales")
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
    def _parse_category_text(value: str, categories: List[ScaleCategory]) -> str:
        matches = [c for c in categories if value.casefold() in [n.casefold() for n in c.names]]
        if len(matches) == 0:
            raise ValueError("String doesn't match a category name")
        elif len(matches) == 1:
            return matches[0].name
        else:
            raise ValueError(f"String matches multiple categories {matches}")

    @staticmethod
    def _parse_germplasm_text(value: str, germplasms: List[Germplasm]) -> str:
        separators = GermplasmEntryStored.protected_characters
        # first split on graft and hybrid descriptors (protected characters):
        values_and_separators = re.split(f"({'|'.join([re.escape(x) for x in separators])})", value)
        output_list = list()
        for v in values_and_separators:
            v = v.strip()
            if v in separators:
                if len(output_list) == 0:
                    raise ValueError(f"Separator '{v}' should be preceded by a germplasm name or identifier")
                elif output_list[-1] in separators:
                    raise ValueError(f"Multiple separators '{output_list[-1], v} may not appear consecutively")
                else:
                    output_list.append(v)
            try:
                # raise ValueError if not integer
                for germplasm in germplasms:
                    if int(v) in germplasm.entries:
                        output_list.append(v)
                        break  # if we have a matching entry we can break to process the next value
                else:
                    raise ValueError(f"The provided integer value does not match a stored germplasm entry: {v}")
            except ValueError:
                matches: Set[int] = set()
                for germplasm in germplasms:
                    for entry_id in germplasm.yield_entry_id_by_name(v):
                        matches.add(entry_id)
                if len(matches) == 0:
                    raise ValueError(f"No matching germplasm found for provided name: {v}")
                elif len(matches) == 1:
                    output_list.append(v)
                elif len(matches) >1:
                    raise ValueError(f"The provided name matches multiple entries, please use Germplasm ID")
        return " ".join(output_list)

    @staticmethod
    def _parse_category_int(value: int, categories: List[ScaleCategory]):
        for c in categories:
            if c.id == value:
                return value
        else:
            raise NoResultFoundError(f"Matching category not found for scale: {value}")

    @staticmethod
    def _parse_germplasm_int(value: int, germplasms: List[Germplasm]):
        for g in germplasms:
            if value in g.entries:
                return value
        else:
            raise NoResultFoundError(f"Matching entry not found in relevant germplasms: {value}")


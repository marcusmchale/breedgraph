from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from typing import Any, Callable

from numpy import datetime64

from breedgraph.domain.model.analysis import Binning, BinningBoundary


@dataclass
class Bin:
    index: int
    label: str
    lower: Any | None  # None: unbounded
    upper: Any | None


class Binner:
    """Assigns values to the bins of a binning configuration, with boundaries parsed by value type."""

    def __init__(self, binning: Binning, parse: Callable[[str], Any]):
        """
        :raises ValueError: if a boundary cannot be parsed or boundaries are not strictly increasing
        """
        self.binning = binning
        self.boundaries = [parse(b) for b in binning.boundaries]
        if any(a >= b for a, b in zip(self.boundaries, self.boundaries[1:])):
            raise ValueError("Bin boundaries must be strictly increasing")

    @property
    def labels(self) -> list[str]:
        return list(self.binning.labels)

    def bin(self, value) -> Bin:
        if self.binning.boundary == BinningBoundary.LEFT:
            # a value equal to a boundary belongs to the lower bin
            index = bisect_left(self.boundaries, value)
        else:
            index = bisect_right(self.boundaries, value)
        return Bin(
            index=index,
            label=self.binning.labels[index],
            lower=self.boundaries[index - 1] if index > 0 else None,
            upper=self.boundaries[index] if index < len(self.boundaries) else None
        )


def parse_datetime(value: str) -> datetime64:
    return datetime64(value, 'ms')

def parse_number(value: str) -> float:
    """Numeric values are stored as submitted (ISO 80000-1): spaces may group digits, comma may be decimal."""
    return float(str(value).strip().replace(' ', '').replace(',', '.'))

from src.breedgraph.domain.model.time_descriptors import PyDT64

from .base import Command

class CreateDataSet(Command):
    user: int
    term: int

class AddRecord(Command):
    user: int
    dataset: int
    unit: int
    value: str|int|float|None = None
    start: PyDT64|None = None
    end: PyDT64|None = None
    references: list[int]|None = None

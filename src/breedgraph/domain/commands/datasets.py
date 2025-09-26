from src.breedgraph.domain.model.time_descriptors import PyDT64

from .base import Command

class CreateDataSet(Command):
    agent_id: int
    concept_id: int

class AddRecord(Command):
    agent_id: int
    dataset_id: int
    unit_id: int

    value: str|int|float|None = None
    start: PyDT64|None = None
    end: PyDT64|None = None
    references: list[int]|None = None

from dataclasses import dataclass
from numpy import datetime64
from typing import List

@dataclass
class DatasetSummary:
    id: int
    concept_id: int
    subject_ids: List[int]
    location_ids: List[int]
    block_ids: List[int]
    unit_count: int
    record_count: int
    start: datetime64
    end: datetime64

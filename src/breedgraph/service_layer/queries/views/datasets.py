from abc import ABC, abstractmethod

from breedgraph.service_layer.queries.read_models import DatasetSummary, DatasetRead, DatasetDimensions, DatasetsUnit
from numpy import datetime64
from breedgraph.domain.model.unit_graphs import UnitOutput

from typing import List, Dict, AsyncGenerator, AbstractSet

class AbstractDatasetsView(ABC):
    user_id: int|None
    read_teams: List[int]

    async def get_dataset_summaries(
            self,
            study_id: int,
            fields: AbstractSet[str] | None = None
    ) -> List[DatasetSummary]:
        """
        The summaries of a study's readable datasets. Pass the DatasetSummary fields to read beyond id and
        concept_id (subject_ids, location_ids, unit_root_ids, unit_count, record_count, start, end) to skip the
        rest, which keep their defaults; None reads them all.
        """
        return await self._get_dataset_summaries(study_id=study_id, fields=fields)

    @abstractmethod
    async def _get_dataset_summaries(
            self,
            study_id: int,
            fields: AbstractSet[str] | None = None
    ) -> List[DatasetSummary]:
        ...

    async def get_datasets(
            self,
            dataset_ids: List[int] | None = None,
            study_ids: List[int] | None = None,
            concept_ids: List[int] | None = None
    ) -> List[DatasetRead]:
        """
        Dataset headers selected by any combination of ids, studies and concepts (no selection means all of them),
        read without building the aggregate. A dataset the user cannot read is a placeholder (DatasetRead.redacted)
        when asked for by id alone, and is otherwise left out (see docs/read-access.md).
        """
        return await self._get_datasets(dataset_ids=dataset_ids, study_ids=study_ids, concept_ids=concept_ids)

    async def get_records(
            self,
            dataset_id: int,
            unit_ids: List[int] | None = None,
            start: datetime64 | None = None,
            end: datetime64 | None = None,
            offset: int = 0,
            limit: int | None = None,
            include_below: bool = True
    ) -> List[dict]:
        """
        A page of a readable dataset's records in submission order, as dicts with the record fields.
        unit_ids narrow them to the records of those units and of every unit below them, or without include_below, of
        exactly those units; start and end to records whose own period overlaps the window.
        """
        if unit_ids is not None:
            unit_ids = [unit_id for unit_id in dict.fromkeys(unit_ids) if unit_id is not None]
        return await self._get_records(
            dataset_id=dataset_id, unit_ids=unit_ids, start=start, end=end, offset=max(offset or 0, 0), limit=limit,
            include_below=include_below
        )

    async def count_records(
            self,
            dataset_id: int,
            unit_ids: List[int] | None = None,
            start: datetime64 | None = None,
            end: datetime64 | None = None
    ) -> int:
        """The number of a readable dataset's records, narrowed the same way as get_records"""
        if unit_ids is not None:
            unit_ids = [unit_id for unit_id in dict.fromkeys(unit_ids) if unit_id is not None]
        return await self._count_records(dataset_id=dataset_id, unit_ids=unit_ids, start=start, end=end)

    async def get_unit_ids(
            self,
            dataset_id: int,
            unit_ids: List[int] | None = None,
            start: datetime64 | None = None,
            end: datetime64 | None = None
    ) -> List[int]:
        """The ids of the units a readable dataset has records for, in id order, narrowed the same way as get_records"""
        if unit_ids is not None:
            unit_ids = [unit_id for unit_id in dict.fromkeys(unit_ids) if unit_id is not None]
        return await self._get_unit_ids(dataset_id=dataset_id, unit_ids=unit_ids, start=start, end=end)

    async def get_unit_level(
            self,
            dataset_ids: List[int],
            parent_ids: List[int] | None = None,
            start: datetime64 | None = None,
            end: datetime64 | None = None
    ) -> List[DatasetsUnit]:
        """
        One level of the tree of units readable datasets have records for, narrowed by time the same way as
        get_records: the children of parent_ids, or the roots when parent_ids is None. The tree holds the recorded
        units, hidden ones as placeholders, and the readable units above them; each hangs from its nearest readable
        ancestor, and a hidden unit holds nothing below it. Readable units in name order, then placeholders.
        """
        dataset_ids = [dataset_id for dataset_id in dict.fromkeys(dataset_ids) if dataset_id is not None]
        if not dataset_ids:
            return []
        if parent_ids is not None:
            parent_ids = [parent_id for parent_id in dict.fromkeys(parent_ids) if parent_id is not None]
            if not parent_ids:
                return []
        return await self._get_unit_level(dataset_ids=dataset_ids, parent_ids=parent_ids, start=start, end=end)

    async def get_units_by_subject(
            self,
            dataset_ids: List[int],
            unit_ids: List[int] | None = None,
            start: datetime64 | None = None,
            end: datetime64 | None = None
    ) -> Dict[int | None, List[UnitOutput]]:
        """
        Every unit readable datasets have records for, narrowed the same way as get_records (unit_ids to those
        units and, for readable ones, everything below them), as id, name and subject keyed by subject id; hidden
        units are placeholders keyed by None. For selecting all the recorded units of a subject at once.
        """
        dataset_ids = [dataset_id for dataset_id in dict.fromkeys(dataset_ids) if dataset_id is not None]
        if not dataset_ids:
            return {}
        if unit_ids is not None:
            unit_ids = [unit_id for unit_id in dict.fromkeys(unit_ids) if unit_id is not None]
            if not unit_ids:
                return {}
        return await self._get_units_by_subject(dataset_ids=dataset_ids, unit_ids=unit_ids, start=start, end=end)

    async def get_dimensions(self, dataset_id: int) -> DatasetDimensions:
        """
        What a readable dataset's records span without reading them: counts, the time range, the record times and
        values at each percentile, and the record group codes by grouping
        """
        return await self._get_dimensions(dataset_id=dataset_id)

    @abstractmethod
    async def _get_dimensions(self, dataset_id: int) -> DatasetDimensions:
        ...

    @abstractmethod
    async def _get_unit_level(
            self,
            dataset_ids: List[int],
            parent_ids: List[int] | None,
            start: datetime64 | None,
            end: datetime64 | None
    ) -> List[DatasetsUnit]:
        ...

    @abstractmethod
    async def _get_units_by_subject(
            self,
            dataset_ids: List[int],
            unit_ids: List[int] | None,
            start: datetime64 | None,
            end: datetime64 | None
    ) -> Dict[int | None, List[UnitOutput]]:
        ...

    @abstractmethod
    async def _get_datasets(
            self,
            dataset_ids: List[int] | None = None,
            study_ids: List[int] | None = None,
            concept_ids: List[int] | None = None
    ) -> List[DatasetRead]:
        ...

    @abstractmethod
    async def _get_records(
            self,
            dataset_id: int,
            unit_ids: List[int] | None,
            start: datetime64 | None,
            end: datetime64 | None,
            offset: int,
            limit: int | None,
            include_below: bool = True
    ) -> List[dict]:
        ...

    @abstractmethod
    async def _get_unit_ids(
            self,
            dataset_id: int,
            unit_ids: List[int] | None,
            start: datetime64 | None,
            end: datetime64 | None
    ) -> List[int]:
        ...

    @abstractmethod
    async def _count_records(
            self,
            dataset_id: int,
            unit_ids: List[int] | None,
            start: datetime64 | None,
            end: datetime64 | None
    ) -> int:
        ...

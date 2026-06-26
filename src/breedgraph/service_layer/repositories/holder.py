from abc import ABC

from breedgraph.service_layer.repositories.base import BaseRepository
from breedgraph.service_layer.repositories.controlled import ControlledRepository

from breedgraph.domain.model.accounts import AccountInput, AccountStored
from breedgraph.domain.model.arrangements import LayoutInput, Arrangement
from breedgraph.domain.model.blocks import UnitInput, Block
from breedgraph.domain.model.datasets import DatasetInput, DatasetStored
from breedgraph.domain.model.organisations import TeamInput, Organisation
from breedgraph.domain.model.people import PersonInput, PersonStored
from breedgraph.domain.model.programs import ProgramInput, ProgramStored
from breedgraph.domain.model.references import ReferenceBase, ReferenceStoredBase
from breedgraph.domain.model.regions import LocationInput, Region

class AbstractRepoHolder(ABC):

    accounts: BaseRepository[AccountInput, AccountStored]
    organisations: BaseRepository[TeamInput, Organisation]

    arrangements: ControlledRepository[LayoutInput, Arrangement]
    datasets: ControlledRepository[DatasetInput, DatasetStored]
    people: ControlledRepository[PersonInput, PersonStored]
    programs: ControlledRepository[ProgramInput, ProgramStored]
    references: ControlledRepository[ReferenceBase, ReferenceStoredBase]
    regions: ControlledRepository[LocationInput, Region]
    blocks: ControlledRepository[UnitInput, Block]

    def collect_events(self):
        for attr, value in self.__dict__.items():
            if isinstance(value, BaseRepository):
                for aggregate in value.seen:
                    while aggregate.events:
                        yield aggregate.events.pop(0)
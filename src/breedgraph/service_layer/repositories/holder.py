from abc import ABC

from src.breedgraph.service_layer.repositories.base import BaseRepository
from src.breedgraph.service_layer.repositories.controlled import ControlledRepository

from src.breedgraph.domain.model.accounts import AccountInput, AccountStored
from src.breedgraph.domain.model.arrangements import LayoutInput, Arrangement
from src.breedgraph.domain.model.blocks import UnitInput, Block
from src.breedgraph.domain.model.datasets import DatasetInput, DatasetStored
from src.breedgraph.domain.model.organisations import TeamInput, Organisation
from src.breedgraph.domain.model.people import PersonInput, PersonStored
from src.breedgraph.domain.model.programs import ProgramInput, ProgramStored
from src.breedgraph.domain.model.references import ReferenceBase, ReferenceStoredBase
from src.breedgraph.domain.model.regions import LocationInput, Region

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
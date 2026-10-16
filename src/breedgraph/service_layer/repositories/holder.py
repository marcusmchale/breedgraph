from abc import ABC

from breedgraph.service_layer.repositories.base import BaseRepository
from breedgraph.service_layer.repositories.controlled import ControlledRepository

from breedgraph.domain.model.accounts import AccountInput, AccountStored
from breedgraph.domain.model.layout_trees import LayoutInput, LayoutTree
from breedgraph.domain.model.unit_graphs import UnitInput, UnitGraph
from breedgraph.domain.model.datasets import DatasetInput, DatasetStored
from breedgraph.domain.model.invitations import InvitationInput, InvitationStored
from breedgraph.domain.model.team_trees import TeamInput, TeamTree
from breedgraph.domain.model.people import PersonInput, PersonStored
from breedgraph.domain.model.programs import ProgramInput, ProgramStored
from breedgraph.domain.model.references import ReferenceBase, ReferenceStoredBase
from breedgraph.domain.model.location_trees import LocationInput, LocationTree

class AbstractRepoHolder(ABC):

    accounts: BaseRepository[AccountInput, AccountStored]
    team_trees: BaseRepository[TeamInput, TeamTree]
    invitations: BaseRepository[InvitationInput, InvitationStored]

    layout_trees: ControlledRepository[LayoutInput, LayoutTree]
    datasets: ControlledRepository[DatasetInput, DatasetStored]
    people: ControlledRepository[PersonInput, PersonStored]
    programs: ControlledRepository[ProgramInput, ProgramStored]
    references: ControlledRepository[ReferenceBase, ReferenceStoredBase]
    location_trees: ControlledRepository[LocationInput, LocationTree]
    unit_graphs: ControlledRepository[UnitInput, UnitGraph]

    def collect_events(self):
        for attr, value in self.__dict__.items():
            if isinstance(value, BaseRepository):
                for aggregate in [*value.seen, *value.removed]:
                    while aggregate.events:
                        yield aggregate.events.pop(0)
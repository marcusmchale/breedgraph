from abc import ABC

from src.breedgraph.service_layer.repositories.base import BaseRepository
from src.breedgraph.service_layer.repositories.controlled import ControlledRepository


class AbstractRepoHolder(ABC):

    accounts: BaseRepository
    organisations: BaseRepository
    ontologies: BaseRepository
    germplasm: ControlledRepository
    arrangements: ControlledRepository
    datasets: ControlledRepository
    germplasms: ControlledRepository
    people: ControlledRepository
    programs: ControlledRepository
    references: ControlledRepository
    regions: ControlledRepository
    blocks: ControlledRepository

    def collect_events(self):
        for attr, value in self.__dict__.items():
            if isinstance(value, BaseRepository):
                for aggregate in value.seen:
                    while aggregate.events:
                        yield aggregate.events.pop(0)

    def update_all_seen(self):
        raise NotImplementedError
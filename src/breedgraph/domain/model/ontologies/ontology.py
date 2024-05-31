from pydantic import BaseModel, computed_field

from src.breedgraph.domain.model.base import Entity, Aggregate

from .entries import OntologyEntry


from typing import Dict, Generator, Type

class Version(BaseModel):
    major: int = 0
    minor: int = 0
    patch: int = 0
    comment: str = ''

    @property
    def name(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}-{self.comment}"

class VersionStored(Version, Entity):
    """
        Ontology version is associated with it's respective entries.
        When a new term is added, this means a new version, but may be a minor/patch version
        Major version changes should reflect a curated commit.
    """
    pass


class Ontology(Aggregate):
    version: Version|VersionStored
    entries: Dict[int, OntologyEntry] = dict()

    licence: int | None = None  # id for internal LegalReference
    copyright: int|None = None  # id for internal LegalReference

    @computed_field
    @property
    def root(self) -> Entity:
        return self.version

    @property
    def protected(self) -> [str|bool]:
        if isinstance(self.version, VersionStored):
            return "Stored ontology is protected"
        else:
            return False

    def add_entry(self, entry: OntologyEntry):
        if entry.children:
            raise ValueError("An entry cannot be added with children")
        for parent_id in entry.parents:
            if not parent_id in self.entries:
                raise ValueError(f"A defined parent ID was not found in this ontology: {parent_id}")
        if entry.id <= 0:
            # Adding a new entry, default is 0 for ID,
            # replaced with a negative value to allow multiple new before commit
            # will be replaced with positive when committed
            entry.id = -len(self.entries) - 1

        self.entries[entry.id] = entry

    def remove_entry(self, entry_id):
        entry = self.entries[entry_id]
        if entry.children:
            raise ValueError("Cannot remove an entry with children")
        self.entries.pop(entry_id)

    def get_by_name(self, name: str) -> Generator:
        """ Yield matches by casefold name """
        for entry in self.entries.values():
            if entry.name.casefold() == name.casefold():
                yield entry

    def get_by_class(self, cls: Type[OntologyEntry]):
        """ Yield matches by class """
        for entry in self.entries.values():
            if isinstance(entry, cls):
                yield entry


from dataclasses import dataclass, field
from typing import Iterable, List, Self


@dataclass
class Contribution:
    """
    A Person credited for a dataset, Program or Trial, with the roles they had (docs/contributions.md).
    The roles are Role ontology entries, declared rather than exhaustive: a contribution may have none.
    """
    person: int
    roles: List[int] = field(default_factory=list)

    @classmethod
    def from_value(cls, value: 'Contribution | dict') -> Self:
        if isinstance(value, Contribution):
            return cls(person=value.person, roles=list(value.roles))
        return cls(person=value['person'], roles=list(value.get('roles') or []))

    def model_dump(self) -> dict:
        return {'person': self.person, 'roles': list(self.roles)}


def contributions_from(values: Iterable['Contribution | dict'] | None) -> List[Contribution]:
    """Contributions from stored or submitted values, one per Person"""
    contributions = [Contribution.from_value(value) for value in values or []]
    persons = [contribution.person for contribution in contributions]
    if len(persons) != len(set(persons)):
        raise ValueError("A Person is credited once, with all their roles")
    return contributions

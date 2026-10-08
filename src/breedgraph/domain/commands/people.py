from breedgraph.domain.model.controls import ReadRelease, ControlledModelLabel
from breedgraph.domain.model.people import LawfulBasis

from .base import Command

from typing import List


class CreatePerson(Command):
    agent_id: int
    write_team: int
    release: ReadRelease = ReadRelease.PRIVATE

    name: str
    teams: List[int] | None = None
    basis: LawfulBasis = LawfulBasis.PUBLIC_TASK
    informed_attestation: bool = False  # the person was informed that this record is held


class UpdatePerson(Command):
    agent_id: int
    person_id: int

    name: str | None = None
    teams: List[int] | None = None
    basis: LawfulBasis | None = None


class ErasePerson(Command):
    agent_id: int
    person_id: int


class RequestPersonClaim(Command):
    """A registered user asks to be linked to a Person"""
    agent_id: int
    person_id: int


class WithdrawPersonClaim(Command):
    agent_id: int
    person_id: int


class ApprovePersonClaim(Command):
    agent_id: int
    person_id: int
    user_id: int


class RejectPersonClaim(Command):
    agent_id: int
    person_id: int
    user_id: int


class UnlinkPerson(Command):
    agent_id: int
    person_id: int


class RemoveSelfAsContact(Command):
    """The linked user removes their Person as a contact of a Program or Trial"""
    agent_id: int
    entity_label: ControlledModelLabel
    entity_id: int


class ContactPerson(Command):
    """Send a message to a contact of a Program or Trial the sender can read"""
    agent_id: int
    person_id: int
    entity_label: ControlledModelLabel
    entity_id: int
    subject: str
    message: str


class StartOrcidLink(Command):
    """Returns the ORCID sign-in URL for the linked user to verify their ORCID iD"""
    agent_id: int


class CompleteOrcidLink(Command):
    """With the code and state ORCID adds to the redirect URI"""
    agent_id: int
    code: str
    state: str


class RemoveOrcid(Command):
    agent_id: int

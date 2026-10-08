from breedgraph.domain.model.controls import Access

from pydantic import BaseModel

from .base import Command

from typing import List

class CreateAccount(Command):
    name: str
    fullname: str|None = None
    email: str
    password_hash: str
    # Required for all but the first account. The email must be the address invited.
    invitation_token: str|None = None
    # The affiliations offered with the invitation that the user accepts
    accept_team_ids: List[int]|None = None
    # Link the Person offered with the invitation to the new account
    link_person: bool = False

class UpdateUser(Command):
    user_id: int
    name: str|None = None
    fullname: str|None = None
    email: str|None = None
    password_hash: str|None = None

class VerifyEmail(Command):
    token: str

class Login(Command):
    user_id: int

class TeamInvitationInput(BaseModel):
    team_id: int
    access: Access

class InviteUser(Command):
    agent_id: int
    email: str
    # Affiliations offered for teams the inviter administers
    teams: List[TeamInvitationInput]|None = None
    # A Person controlled by a team the inviter administers, offered for the user to link to their account
    person_id: int|None = None

class CancelInvitation(Command):
    agent_id: int
    invitation_id: int

class ResendInvitation(Command):
    agent_id: int
    invitation_id: int

class RemoveExpiredInvitations(Command):
    pass

class RequestOntologyRole(Command):
    user_id: int
    ontology_role: str

class SetOntologyRole(Command):
    agent_id: int

    user_id: int
    ontology_role: str

class SetWriteTeam(Command):
    user_id: int
    team_id: int

class RequestAffiliation(Command):
    user_id: int
    team_id: int
    access: Access
    heritable: bool

class ApproveAffiliation(Command):
    agent_id: int

    user_id: int
    team_id: int
    access: Access
    heritable: bool

class RemoveAffiliation(Command):
    agent_id: int

    user_id: int
    team_id: int
    access: Access

class RevokeAffiliation(Command):
    agent_id: int

    user_id: int
    team_id: int
    access: Access

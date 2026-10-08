from datetime import datetime, timedelta, timezone

import pytest

from breedgraph.custom_exceptions import IllegalOperationError, UnauthorisedOperationError
from breedgraph.domain.model.controls import Access
from breedgraph.domain.model.invitations import InvitationInput, InvitationStored, TeamInvitation

NOW = datetime(2026, 10, 1, tzinfo=timezone.utc)


def stored(**kwargs) -> InvitationStored:
    fields = dict(
        id=1, email='Invited@Example.org', invited_by=1,
        teams=[TeamInvitation(10, Access.READ), TeamInvitation(11, Access.WRITE)],
        expires_at=NOW + timedelta(days=1)
    )
    fields.update(kwargs)
    return InvitationStored(**fields)


@pytest.mark.parametrize("email", ['', 'not an email'])
def test_input_requires_email(email):
    with pytest.raises(IllegalOperationError, match="email"):
        InvitationInput(email=email, invited_by=1)


def test_input_offers_each_team_once():
    with pytest.raises(IllegalOperationError, match="once"):
        InvitationInput(email='a@b.org', invited_by=1, teams=[TeamInvitation(1, 'READ'), TeamInvitation(1, 'WRITE')])


def test_inviter_administers_offered_teams():
    invitation = InvitationInput(email='a@b.org', invited_by=1, teams=[TeamInvitation(1, 'READ')])
    invitation.check_inviter(admin_teams={1, 2})
    with pytest.raises(UnauthorisedOperationError):
        invitation.check_inviter(admin_teams={2})


def test_expiry():
    assert not stored().is_expired(now=NOW)
    assert stored(expires_at=NOW).is_expired(now=NOW)
    invitation = stored(expires_at=NOW - timedelta(days=1))
    invitation.extend(days=30, now=NOW)
    assert invitation.expires_at == NOW + timedelta(days=30)


def test_matches_email_case_insensitively():
    assert stored().matches_email(' invited@example.org ')
    assert not stored().matches_email('other@example.org')


def test_accepted_teams():
    invitation = stored()
    assert invitation.accepted_teams(None) == []
    assert invitation.accepted_teams({11}) == [TeamInvitation(11, Access.WRITE)]
    with pytest.raises(IllegalOperationError, match="not offered"):
        invitation.accepted_teams({12})

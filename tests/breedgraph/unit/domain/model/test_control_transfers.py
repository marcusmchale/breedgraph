import pytest

from breedgraph.custom_exceptions import IllegalOperationError, UnauthorisedOperationError
from breedgraph.domain.model.control_transfers import (
    ControlTransferInput, ControlTransferStored, ControlTransferStatus, ControlledEntity
)
from breedgraph.domain.model.controls import ControlledModelLabel, ReadRelease

OFFERING_USER = 1
RECEIVING_USER = 2

FROM_TEAM = 10
RECIPIENT_ROOT = 20
RECIPIENT_CHILD = 21
OTHER_TEAM = 30

PROGRAM = ControlledEntity(label=ControlledModelLabel.PROGRAM, id=100)


def pending_transfer(keep_from_teams: bool = False) -> ControlTransferStored:
    return ControlTransferStored(
        id=1,
        entities=[PROGRAM],
        from_teams=[FROM_TEAM],
        recipient_team=RECIPIENT_ROOT,
        keep_from_teams=keep_from_teams,
        offered_by=OFFERING_USER
    )


@pytest.mark.parametrize("missing", ["entities", "from_teams", "recipient_team", "offered_by"])
def test_offer_requires_fields(missing):
    fields = dict(entities=[PROGRAM], from_teams=[FROM_TEAM], recipient_team=RECIPIENT_ROOT, offered_by=OFFERING_USER)
    fields[missing] = None if missing in ("recipient_team", "offered_by") else type(fields[missing])()
    with pytest.raises(IllegalOperationError):
        ControlTransferInput(**fields)


def test_offer_requires_admin_of_every_from_team():
    transfer = ControlTransferInput(
        entities=[PROGRAM], from_teams=[FROM_TEAM, OTHER_TEAM], recipient_team=RECIPIENT_ROOT, offered_by=OFFERING_USER
    )
    transfer.check_offer(admin_teams={FROM_TEAM, OTHER_TEAM})
    with pytest.raises(UnauthorisedOperationError):
        transfer.check_offer(admin_teams={FROM_TEAM})


def test_accept_into_child_of_recipient():
    transfer = pending_transfer()
    transfer.accept(
        agent_id=RECEIVING_USER,
        admin_teams={RECIPIENT_ROOT, RECIPIENT_CHILD},
        recipient_teams={RECIPIENT_ROOT, RECIPIENT_CHILD},
        to_teams={RECIPIENT_CHILD},
        release=ReadRelease.REGISTERED
    )
    assert transfer.status is ControlTransferStatus.ACCEPTED
    assert transfer.to_teams == [RECIPIENT_CHILD]
    assert transfer.release is ReadRelease.REGISTERED
    assert transfer.accepted_by == RECEIVING_USER
    assert transfer.teams_to_end == {FROM_TEAM}


def test_accept_defaults_to_private():
    transfer = pending_transfer()
    transfer.accept(
        agent_id=RECEIVING_USER,
        admin_teams={RECIPIENT_ROOT},
        recipient_teams={RECIPIENT_ROOT},
        to_teams={RECIPIENT_ROOT}
    )
    assert transfer.release is ReadRelease.PRIVATE


def test_shared_control_ends_no_teams():
    transfer = pending_transfer(keep_from_teams=True)
    transfer.accept(
        agent_id=RECEIVING_USER,
        admin_teams={RECIPIENT_ROOT},
        recipient_teams={RECIPIENT_ROOT},
        to_teams={RECIPIENT_ROOT}
    )
    assert transfer.teams_to_end == set()


def test_accept_requires_admin_of_recipient_team():
    # An admin of a child team only cannot accept an offer made to the root
    transfer = pending_transfer()
    with pytest.raises(UnauthorisedOperationError):
        transfer.accept(
            agent_id=RECEIVING_USER,
            admin_teams={RECIPIENT_CHILD},
            recipient_teams={RECIPIENT_ROOT, RECIPIENT_CHILD},
            to_teams={RECIPIENT_CHILD}
        )
    assert transfer.status is ControlTransferStatus.PENDING


def test_accept_requires_admin_of_every_to_team():
    transfer = pending_transfer()
    with pytest.raises(UnauthorisedOperationError):
        transfer.accept(
            agent_id=RECEIVING_USER,
            admin_teams={RECIPIENT_ROOT},
            recipient_teams={RECIPIENT_ROOT, RECIPIENT_CHILD},
            to_teams={RECIPIENT_CHILD}
        )


def test_accept_requires_to_teams_within_recipient():
    transfer = pending_transfer()
    with pytest.raises(IllegalOperationError):
        transfer.accept(
            agent_id=RECEIVING_USER,
            admin_teams={RECIPIENT_ROOT, OTHER_TEAM},
            recipient_teams={RECIPIENT_ROOT, RECIPIENT_CHILD},
            to_teams={OTHER_TEAM}
        )


def test_accept_requires_to_teams():
    transfer = pending_transfer()
    with pytest.raises(IllegalOperationError):
        transfer.accept(
            agent_id=RECEIVING_USER,
            admin_teams={RECIPIENT_ROOT},
            recipient_teams={RECIPIENT_ROOT},
            to_teams=set()
        )


def test_accept_refuses_from_teams_as_to_teams():
    transfer = ControlTransferStored(
        id=1, entities=[PROGRAM], from_teams=[RECIPIENT_CHILD], recipient_team=RECIPIENT_ROOT, offered_by=OFFERING_USER
    )
    with pytest.raises(IllegalOperationError):
        transfer.accept(
            agent_id=RECEIVING_USER,
            admin_teams={RECIPIENT_ROOT, RECIPIENT_CHILD},
            recipient_teams={RECIPIENT_ROOT, RECIPIENT_CHILD},
            to_teams={RECIPIENT_CHILD}
        )


def test_reject():
    transfer = pending_transfer()
    with pytest.raises(UnauthorisedOperationError):
        transfer.reject(agent_id=OFFERING_USER, admin_teams={FROM_TEAM})
    transfer.reject(agent_id=RECEIVING_USER, admin_teams={RECIPIENT_ROOT})
    assert transfer.status is ControlTransferStatus.REJECTED
    assert transfer.rejected_by == RECEIVING_USER


def test_cancel():
    transfer = pending_transfer()
    with pytest.raises(UnauthorisedOperationError):
        transfer.cancel(agent_id=RECEIVING_USER, admin_teams={RECIPIENT_ROOT})
    transfer.cancel(agent_id=OFFERING_USER, admin_teams={FROM_TEAM})
    assert transfer.status is ControlTransferStatus.CANCELLED
    assert transfer.cancelled_by == OFFERING_USER


@pytest.mark.parametrize("close", [
    lambda t: t.reject(agent_id=RECEIVING_USER, admin_teams={RECIPIENT_ROOT}),
    lambda t: t.cancel(agent_id=OFFERING_USER, admin_teams={FROM_TEAM}),
    lambda t: t.accept(agent_id=RECEIVING_USER, admin_teams={RECIPIENT_ROOT}, recipient_teams={RECIPIENT_ROOT}, to_teams={RECIPIENT_ROOT})
])
def test_only_pending_transfers_change(close):
    transfer = pending_transfer()
    close(transfer)
    status = transfer.status
    with pytest.raises(IllegalOperationError, match="not pending"):
        transfer.accept(agent_id=RECEIVING_USER, admin_teams={RECIPIENT_ROOT}, recipient_teams={RECIPIENT_ROOT}, to_teams={RECIPIENT_ROOT})
    with pytest.raises(IllegalOperationError, match="not pending"):
        transfer.reject(agent_id=RECEIVING_USER, admin_teams={RECIPIENT_ROOT})
    with pytest.raises(IllegalOperationError, match="not pending"):
        transfer.cancel(agent_id=OFFERING_USER, admin_teams={FROM_TEAM})
    assert transfer.status is status


def test_transfers_are_protected_from_deletion():
    assert pending_transfer().protected


def test_cancel_for_deleted_team():
    for team_id in (FROM_TEAM, RECIPIENT_ROOT):
        transfer = pending_transfer()
        transfer.cancel_for_deleted_team(agent_id=RECEIVING_USER, team_id=team_id)
        assert transfer.status is ControlTransferStatus.CANCELLED
        assert transfer.cancelled_by == RECEIVING_USER

    with pytest.raises(IllegalOperationError):
        pending_transfer().cancel_for_deleted_team(agent_id=RECEIVING_USER, team_id=OTHER_TEAM)

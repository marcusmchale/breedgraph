import pytest
from numpy import datetime64

from breedgraph.custom_exceptions import IllegalOperationError, UnauthorisedOperationError
from breedgraph.domain.model.controls import Control, Controller, ControlledModelLabel, ReadRelease
from breedgraph.domain.model.people import PersonInput, PersonStored, PersonOutput, LawfulBasis

CONTROL_TEAM = 10
OTHER_TEAM = 20
ADMIN_USER = 1
SUBJECT_USER = 2
OTHER_USER = 3


def controllers(person: PersonStored, release: ReadRelease = ReadRelease.PRIVATE) -> dict:
    controller = Controller(controls={
        CONTROL_TEAM: Control(user_id=ADMIN_USER, team_id=CONTROL_TEAM, release=release, time=datetime64('now'))
    })
    return {ControlledModelLabel.PERSON: {person.id: controller}}


def stored_person(**kwargs) -> PersonStored:
    fields = dict(
        id=1,
        name='A Technician',
        teams=[CONTROL_TEAM],
        basis=LawfulBasis.PUBLIC_TASK,
        informed_attestation=True,
        user=SUBJECT_USER,
        recorded_by=ADMIN_USER
    )
    fields.update(kwargs)
    return PersonStored(**fields)


def test_input_requires_name():
    with pytest.raises(IllegalOperationError, match="name"):
        PersonInput(name='  ', informed_attestation=True)


def test_input_requires_informed_attestation():
    with pytest.raises(IllegalOperationError, match="informed"):
        PersonInput(name='A Technician')


def test_input_basis_from_value():
    person = PersonInput(name=' A Technician ', informed_attestation=True, basis='LEGITIMATE_INTEREST')
    assert person.name == 'A Technician'
    assert person.basis is LawfulBasis.LEGITIMATE_INTEREST


def test_readers_see_the_full_record():
    person = stored_person()
    assert person.redacted(controllers(person), user_id=OTHER_USER, read_teams={CONTROL_TEAM}) is person


def test_subject_sees_the_full_record_without_read_access():
    person = stored_person()
    assert person.redacted(controllers(person), user_id=SUBJECT_USER, read_teams=set()) is person


def test_registered_users_without_access_see_id_only():
    person = stored_person()
    redacted = person.redacted(controllers(person), user_id=OTHER_USER, read_teams={OTHER_TEAM})
    assert redacted.id == person.id
    assert redacted.name is None
    assert redacted.teams == []
    assert redacted.user is None
    assert redacted.recorded_by is None


def test_anonymous_users_see_nothing():
    person = stored_person()
    assert person.redacted(controllers(person), user_id=None) is None


def test_released_records_are_visible():
    person = stored_person()
    assert person.redacted(controllers(person, ReadRelease.REGISTERED), user_id=OTHER_USER) is person
    assert person.redacted(controllers(person, ReadRelease.PUBLIC), user_id=None) is person


@pytest.mark.parametrize("agent_id, admin_teams", [(ADMIN_USER, {CONTROL_TEAM}), (SUBJECT_USER, set())])
def test_erase(agent_id, admin_teams):
    person = stored_person(orcid='0000-0002-1825-0097')
    controller = controllers(person)[ControlledModelLabel.PERSON][person.id]
    person.erase(agent_id=agent_id, controller=controller, admin_teams=admin_teams)

    assert person.erased
    assert person.name is None
    assert person.teams == []
    assert person.orcid is None
    assert person.user is None
    # kept: id, basis and record of who recorded it
    assert person.id == 1
    assert person.basis is LawfulBasis.PUBLIC_TASK
    assert person.recorded_by == ADMIN_USER


def test_erase_requires_admin_or_subject():
    person = stored_person()
    controller = controllers(person)[ControlledModelLabel.PERSON][person.id]
    with pytest.raises(UnauthorisedOperationError):
        person.erase(agent_id=OTHER_USER, controller=controller, admin_teams={OTHER_TEAM})
    assert not person.erased


def test_erase_only_once():
    person = stored_person()
    controller = controllers(person)[ControlledModelLabel.PERSON][person.id]
    person.erase(agent_id=ADMIN_USER, controller=controller, admin_teams={CONTROL_TEAM})
    with pytest.raises(IllegalOperationError, match="already erased"):
        person.erase(agent_id=ADMIN_USER, controller=controller, admin_teams={CONTROL_TEAM})


def test_persons_are_protected_from_removal():
    assert stored_person().protected


def test_to_output():
    output = stored_person().to_output()
    assert isinstance(output, PersonOutput)
    assert output.id == 1
    assert output.name == 'A Technician'
    assert output.teams == [CONTROL_TEAM]
    assert output.erased_at is None

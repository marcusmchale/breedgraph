from datetime import datetime, timezone

import pytest

from breedgraph.domain.commands.people import CreatePerson
from breedgraph.domain.events.people import PersonErased
from breedgraph.service_layer.log_safety import loggable, describe_exception


def test_loggable_keeps_ids_only():
    command = CreatePerson(agent_id=1, write_team=2, name='Secret Name', teams=[3], informed_attestation=True)
    assert loggable(command) == "CreatePerson(agent_id=1, write_team=2, teams=[3])"

    event = PersonErased(person_id=4, erased_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert loggable(event) == "PersonErased(person_id=4)"


def test_describe_validation_error_without_input():
    with pytest.raises(Exception) as error:
        CreatePerson(agent_id='not an id', write_team=2, name='Secret Name')
    description = describe_exception(error.value)
    assert 'agent_id' in description
    assert 'not an id' not in description
    assert 'Secret Name' not in description


def test_describe_other_exceptions():
    assert describe_exception(ValueError("Person 4 not found")) == "ValueError: Person 4 not found"

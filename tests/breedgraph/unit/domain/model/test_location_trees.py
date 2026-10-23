from numpy import datetime64

from breedgraph.domain.model.controls import Controller, Control, ReadRelease
from breedgraph.domain.model.location_trees import LocationStored


def test_redacted_location_keeps_no_details():
    location = LocationStored(
        id=1,
        name="Field",
        synonyms=["Plot"],
        type=2,
        description="A field",
        code="F1",
        address="Somewhere"
    )
    controller = Controller(controls={1: Control(user_id=1, team_id=1, release=ReadRelease.PRIVATE, time=datetime64('now'))})
    redacted = location.redacted(controller=controller, user_id=2, read_teams=set())
    assert redacted.id == 1
    assert redacted.name == LocationStored.redacted_str
    assert redacted.synonyms == [LocationStored.redacted_str]
    assert redacted.type is None
    assert all(value == LocationStored.redacted_str for value in [redacted.description, redacted.code, redacted.address])

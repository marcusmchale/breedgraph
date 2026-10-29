from numpy import datetime64

from breedgraph.domain.model.controls import Access, Control, Controller, ReadRelease


def test_a_controller_without_controls_is_fixed():
    """Everyone can read a fixed model, and no one can change it, whatever teams they belong to"""
    controller = Controller()
    assert controller.fixed
    assert controller.release is ReadRelease.PUBLIC
    assert controller.has_access(Access.READ)
    for access in (Access.WRITE, Access.CURATE, Access.ADMIN):
        assert not controller.has_access(access, user_id=1, access_teams={1, 2})


def test_a_controlled_model_is_not_fixed():
    controller = Controller(controls={1: Control(user_id=1, team_id=1, release=ReadRelease.PRIVATE, time=datetime64('now'))})
    assert not controller.fixed
    assert not controller.has_access(Access.READ, user_id=2, access_teams=set())
    assert controller.has_access(Access.CURATE, user_id=1, access_teams={1})

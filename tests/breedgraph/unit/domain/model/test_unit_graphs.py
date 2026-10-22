import pytest
from numpy import datetime64
from breedgraph.domain.model.unit_graphs import (
    Position,
    UnitInput,
    UnitStored,
    UnitGraph
)
from breedgraph.domain.model.controls import Controller, Control, ReadRelease
from tests.breedgraph.conftest import lorem_text_generator


def get_unit_input(lorem_text_generator):
    return UnitInput(
        subject=1,
        name=lorem_text_generator.new_text(5),
        description=lorem_text_generator.new_text(10),
        positions=[Position(location_id=1, start='2001', end='2004'), Position(location_id=1, layout_id=2, coordinates=[1,1], start='2001', end='2004')]
    )

@pytest.fixture
def unit_stored(lorem_text_generator) -> UnitStored:
    return UnitStored(
        **get_unit_input(lorem_text_generator).model_dump(),
        id=1
    )

def test_graph_redaction(unit_stored):
    ug = UnitGraph(nodes=[unit_stored])
    assert ug.root.id == unit_stored.id
    assert ug.root.name == unit_stored.name

    private_controllers = {
        'Unit': {
            ug.root.id: Controller(controls={1:Control(team_id=1, release=ReadRelease.PRIVATE, user_id=1, time=datetime64('now'))}),
        }
    }
    ug_red = ug.redacted(controllers=private_controllers, user_id=1, read_teams=None)
    assert ug_red.root.name == unit_stored.redacted_str

def test_insert_root(lorem_text_generator, unit_stored):
    ug = UnitGraph(nodes=[unit_stored])
    new_input = get_unit_input(lorem_text_generator)
    ug.add_unit(new_input)
    assert new_input.name == ug.root.name
    assert ug.get_sinks(ug.get_root_id())

def test_add_unit(lorem_text_generator, unit_stored):
    ug = UnitGraph(nodes=[unit_stored])
    existing_root_name = ug.root.name
    new_input = get_unit_input(lorem_text_generator)
    ug.add_unit(new_input, [ug.root.id])
    assert existing_root_name == ug.root.name
    new_child_id = list(ug.get_sinks(ug.root.id).keys())[0]
    assert ug.get_entry(new_child_id).name == new_input.name
    assert ug.get_entry(new_input.name)

def test_merge_unit_graphs(lorem_text_generator, unit_stored):
    ug = UnitGraph(nodes=[unit_stored])
    new_input = get_unit_input(lorem_text_generator)
    new_unit_graph = UnitGraph(nodes=[new_input])
    ug.merge_unit_graph(new_unit_graph, [ug.get_root_id()])
    assert ug.get_sinks(ug.get_root_id())


def test_stored_unit_with_id_zero_keeps_its_id():
    """Id 0 is a stored id, not a missing one: it must not be given a temporary id"""
    unit = UnitStored(id=0, name="First unit", subject=1)
    unit_graph = UnitGraph(nodes=[unit])
    assert unit_graph.get_root_id() == 0
    assert unit_graph.get_unit(0) is unit


from breedgraph.custom_exceptions import IllegalOperationError
from breedgraph.domain.model.unit_graphs import same_position


def _graph(edges):
    """A unit graph of stored units 1..n with the given (parent, child) edges; unit 1 is the root"""
    ids = sorted({i for edge in edges for i in edge} | {1})
    units = [UnitStored(id=i, name=f"Unit {i}", subject=10 + i) for i in ids]
    return UnitGraph(nodes=units, edges=[(parent, child, None) for parent, child in edges])


def test_can_split_only_where_nothing_below_has_another_parent():
    # 1 -> 2 -> 4, 1 -> 3 -> 4: unit 4 has a parent outside 2's branch
    unit_graph = _graph([(1, 2), (1, 3), (2, 4), (3, 4)])
    assert not unit_graph.can_split(2)
    assert unit_graph.can_split(4)
    # 1 -> 2 -> 5 alone
    unit_graph = _graph([(1, 2), (2, 5), (1, 3)])
    assert unit_graph.can_split(2)


def test_change_children_within_the_graph():
    unit_graph = _graph([(1, 2), (1, 3), (2, 4), (3, 4)])
    # 4 keeps its other parent, 3, when 2 lets it go; 3 becomes a child of 2
    unit_graph.change_children(2, [3])
    assert sorted(unit_graph.get_children_ids(2)) == [3]
    assert unit_graph.get_parent_ids(4) == [3]


def test_change_children_refuses_leaving_a_unit_without_parents():
    unit_graph = _graph([(1, 2), (2, 4)])
    with pytest.raises(IllegalOperationError):
        unit_graph.change_children(2, [])


def test_change_children_refuses_a_unit_from_another_graph():
    unit_graph = _graph([(1, 2)])
    with pytest.raises(ValueError):
        unit_graph.change_children(2, [99])


def test_change_parents_refuses_parents_outside_the_graph_and_none():
    unit_graph = _graph([(1, 2), (1, 3)])
    with pytest.raises(ValueError):
        unit_graph.change_parents(3, [99])
    with pytest.raises(IllegalOperationError):
        unit_graph.change_parents(3, [])
    unit_graph.change_parents(3, [2])
    assert unit_graph.get_parent_ids(3) == [2]


def test_same_position_compares_times_as_entered_and_coordinates_as_strings():
    a = Position(location_id=1, layout_id=2, coordinates=[1, 'A'], start=datetime64('2021-05'))
    assert same_position(a, Position(location_id=1, layout_id=2, coordinates=['1', 'A'], start=datetime64('2021-05')))
    assert not same_position(a, Position(location_id=1, layout_id=2, coordinates=['1', 'A'], start=datetime64('2021-05-01')))
    assert same_position(Position(location_id=1, coordinates=None), Position(location_id=1, coordinates=[]))
    assert not same_position(a, Position(location_id=1, layout_id=2, coordinates=['1', 'A'], start=datetime64('2021-05'), end=datetime64('2022')))


def test_unit_ids_by_subject():
    unit_graph = _graph([(1, 2), (1, 3)])
    assert list(unit_graph.yield_unit_ids_by_subject(12)) == [2]


from breedgraph.domain.model.unit_graphs import UnitDerivation
from breedgraph.domain.model.germplasm import GermplasmSourceType


def test_unit_derivation_takes_its_source_type_by_value_and_dumps_it_so():
    derivation = UnitDerivation(unit_id=7, source_type='TISSUE', description='Microcutting')
    assert derivation.source_type is GermplasmSourceType.TISSUE
    assert UnitDerivation(unit_id=7).source_type is GermplasmSourceType.UNKNOWN
    unit = UnitInput(subject=1, derived_from=[derivation])
    assert unit.model_dump()['derived_from'] == [{'unit_id': 7, 'source_type': 'TISSUE', 'description': 'Microcutting'}]


def test_hidden_unit_shows_no_derivation():
    unit = UnitStored(id=1, name="Plantlet", subject=1, derived_from=[UnitDerivation(unit_id=7)])
    controller = Controller(controls={
        1: Control(team_id=1, release=ReadRelease.PRIVATE, user_id=1, time=datetime64('now'))
    })
    assert unit.redacted(controller=controller, user_id=2, read_teams=set()).derived_from == []
    assert unit.redacted(controller=controller, user_id=1, read_teams={1}).derived_from == unit.derived_from


def test_a_unit_is_derived_only_from_units_outside_its_context():
    # 1 -> 2 -> 4, 1 -> 3
    unit_graph = _graph([(1, 2), (1, 3), (2, 4)])
    for refused in ([2], [1], [4], [2, 99]):
        with pytest.raises(IllegalOperationError):
            unit_graph.check_derived_from(2, refused)
    # a unit beside it in its unit graph, or one in another, is outside its context
    unit_graph.check_derived_from(2, [3, 99])

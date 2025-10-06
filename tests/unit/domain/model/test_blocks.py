import pytest

from src.breedgraph.domain.model.blocks import (
    Position,
    UnitInput,
    UnitStored,
    Block
)
from src.breedgraph.domain.model.controls import Controller, Control, ReadRelease
from tests.conftest import lorem_text_generator


def get_unit_input(lorem_text_generator):
    return UnitInput(
        subject=1,
        name=lorem_text_generator.new_text(5),
        description=lorem_text_generator.new_text(10),
        positions=[Position(location=1, start='2001', end='2004'), Position(location=1, layout=2, coordinates=[1,1], start='2001', end='2004')]
    )

@pytest.fixture
def unit_stored(lorem_text_generator) -> UnitStored:
    return UnitStored(
        **get_unit_input(lorem_text_generator).model_dump(),
        id=1
    )

def test_graph_redaction(unit_stored):
    ug = Block(nodes=[unit_stored])
    assert ug.root.id == unit_stored.id
    assert ug.root.name == unit_stored.name

    private_controllers = {
        'Unit': {
            ug.root.id: Controller(controls={1:Control(team_id=1, release=ReadRelease.PRIVATE)}),
        }
    }
    ug_red = ug.redacted(controllers=private_controllers, user_id=1, read_teams=None)
    assert ug_red.root.name == unit_stored.redacted_str

def test_insert_root(lorem_text_generator, unit_stored):
    ug = Block(nodes=[unit_stored])
    new_input = get_unit_input(lorem_text_generator)
    ug.add_unit(new_input)
    assert new_input.name == ug.root.name
    assert ug.get_sinks(ug.get_root_id())

def test_add_unit(lorem_text_generator, unit_stored):
    ug = Block(nodes=[unit_stored])
    existing_root_name = ug.root.name
    new_input = get_unit_input(lorem_text_generator)
    ug.add_unit(new_input, [ug.root.id])
    assert existing_root_name == ug.root.name
    new_child_id = list(ug.get_sinks(ug.root.id).keys())[0]
    assert ug.get_entry(new_child_id).name == new_input.name
    assert ug.get_entry(new_input.name)

def test_merge_blocks(lorem_text_generator, unit_stored):
    ug = Block(nodes=[unit_stored])
    new_input = get_unit_input(lorem_text_generator)
    new_unit_graph = Block(nodes=[new_input])
    ug.merge_block(new_unit_graph, [ug.get_root_id()])
    assert ug.get_sinks(ug.get_root_id())

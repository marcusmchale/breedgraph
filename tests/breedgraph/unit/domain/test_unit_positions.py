"""
Planning moves and changes of positions (domain.services.unit_positions): what each does to the positions units have
"""
import pytest
from numpy import datetime64

from breedgraph.custom_exceptions import IllegalOperationError, NoResultFoundError
from breedgraph.domain.model.unit_graphs import Position, CHILD_NAME_TEMPLATE, child_name
from breedgraph.domain.services.unit_positions import (
    StoredPosition, UnitPositions, plan_move, plan_change, plan_add, plan_remove, named, place_at
)

LAB, STORE, FIELD = 1, 2, 3


def at(location_id, start=None, end=None, **values) -> Position:
    return Position(
        location_id=location_id,
        start=None if start is None else datetime64(start),
        end=None if end is None else datetime64(end),
        **values
    )


def unit(unit_id: int, *positions: Position, root=False, name=None) -> UnitPositions:
    return UnitPositions(
        unit_id=unit_id, name=name or f"Sample {unit_id}", root=root,
        positions=[StoredPosition(key=f"{unit_id}:{i}", position=p) for i, p in enumerate(positions)]
    )


def test_a_move_ends_where_each_unit_is_and_adds_the_position():
    at_lab = unit(1, at(LAB, '2025-03-25'))
    with_its_parent = unit(2)
    writes = plan_move([at_lab, with_its_parent], at(STORE, '2025-05-02'))
    assert writes.changed == [('1:0', at(LAB, '2025-03-25', '2025-05-02'))]
    assert writes.created == [(1, at(STORE, '2025-05-02')), (2, at(STORE, '2025-05-02'))]
    assert writes.deleted == []


def test_a_move_leaves_positions_ended_before_it_and_cuts_those_ending_after():
    used_up = unit(1, at(LAB, '2025-03-25', '2025-04-15'))
    planned = unit(2, at(LAB, '2025-03-25', '2025-12'))
    ending_then = unit(3, at(LAB, '2025-03-25', '2025-05'))
    writes = plan_move([used_up, planned, ending_then], at(STORE, '2025-05-02'))
    # the planned end is cut to the move; one ending in the month the move is in keeps its end as entered
    assert writes.changed == [('2:0', at(LAB, '2025-03-25', '2025-05-02'))]
    assert [unit_id for unit_id, _ in writes.created] == [1, 2, 3]


def test_a_move_is_refused_for_a_unit_with_a_position_from_then_or_later():
    moved_on = unit(1, at(LAB, '2025-03-25'), at(STORE, '2025-05-02'), name='Sample A2')
    arrived_then = unit(2, at(LAB, '2025-05'), name='Sample A3')
    with pytest.raises(IllegalOperationError, match='Sample A2 and Sample A3 have positions from 2025-05-01 or later'):
        plan_move([moved_on, arrived_then, unit(3)], at(FIELD, '2025-05-01'))


def test_a_move_needs_a_start():
    with pytest.raises(ValueError, match='needs a start'):
        plan_move([unit(1)], at(STORE))


def test_a_change_finds_one_position_of_each_unit_as_entered():
    arrival = {'location_id': LAB, 'start': datetime64('2025-03')}
    units = [unit(1, at(LAB, '2025-03'), at(FIELD, '2024')), unit(2, at(LAB, '2025-03'))]
    writes = plan_change(units, arrival, {'end': datetime64('2025-04-15')})
    assert writes.changed == [('1:0', at(LAB, '2025-03', '2025-04-15')), ('2:0', at(LAB, '2025-03', '2025-04-15'))]
    # the same instant at another precision is another position
    with pytest.raises(NoResultFoundError, match='Sample 1 and Sample 2'):
        plan_change(units, {'location_id': LAB, 'start': datetime64('2025-03-01')}, {'end': datetime64('2025-04-15')})


def test_a_change_corrects_the_place_or_times_and_keeps_the_rest():
    units = [unit(1, at(LAB, '2025-03-25', layout_id=7, coordinates=['1', '2']))]
    moved = plan_change(units, {'location_id': LAB}, {'location_id': STORE, 'layout_id': None, 'coordinates': None})
    assert moved.changed == [('1:0', at(STORE, '2025-03-25'))]
    undated = plan_change(units, {'location_id': LAB}, {'start': None})
    assert undated.changed == [('1:0', at(LAB, layout_id=7, coordinates=['1', '2']))]


def test_a_change_is_refused_where_it_is_unclear_or_would_repeat_a_position():
    two_at_the_lab = unit(1, at(LAB, '2024-06', '2024-07'), at(LAB, '2025-03-25'))
    with pytest.raises(ValueError, match='Several positions match'):
        plan_change([two_at_the_lab], {'location_id': LAB}, {'end': datetime64('2025-04')})
    with pytest.raises(ValueError, match='same position twice'):
        plan_change([two_at_the_lab], {'location_id': LAB, 'start': datetime64('2025-03-25')}, {
            'start': datetime64('2024-06'), 'end': datetime64('2024-07')
        })
    with pytest.raises(ValueError, match='Start cannot be after end'):
        plan_change([two_at_the_lab], {'location_id': LAB, 'start': datetime64('2025-03-25')}, {'end': datetime64('2025-01')})
    with pytest.raises(ValueError, match='require location_id'):
        plan_change([two_at_the_lab], {'location_id': LAB, 'start': datetime64('2025-03-25')}, {'location_id': None})
    with pytest.raises(ValueError, match='Positions have no unit_id'):
        plan_change([two_at_the_lab], {'unit_id': 1}, {'end': datetime64('2025-04')})
    with pytest.raises(ValueError, match='Give what changes'):
        plan_change([two_at_the_lab], {'location_id': LAB}, {})


def test_adding_refuses_a_position_the_unit_has_and_removing_keeps_a_roots_last():
    field = unit(1, at(FIELD, '2024', coordinates=[1]), root=True)
    with pytest.raises(ValueError, match='already has this position'):
        plan_add(field, at(FIELD, '2024', coordinates=['1']))
    assert plan_add(field, at(FIELD, '2025')).created == [(1, at(FIELD, '2025'))]
    with pytest.raises(IllegalOperationError, match='at least one position'):
        plan_remove(field, at(FIELD, '2024', coordinates=['1']))
    with pytest.raises(ValueError, match='was not found'):
        plan_remove(unit(2, at(LAB, '2025-03-25')), at(LAB, '2025-03'))
    assert plan_remove(unit(2, at(LAB, '2025-03-25')), at(LAB, '2025-03-25')).deleted == ['2:0']


def test_refusals_name_a_few_units_and_count_the_rest():
    assert named([unit(1)]) == 'Sample 1'
    assert named([unit(1), unit(2, name='Tree')]) == 'Sample 1 and Tree'
    assert named([unit(i) for i in range(1, 9)]) == 'Sample 1, Sample 2, Sample 3, Sample 4, Sample 5 and 3 more'


# A field with a tree at a grid position in it, a sample of the tree sent to the lab, and a sample pooled from the tree
# and a tree that visited the lab: (parents, positions) by unit id
FIELD_UNIT, TREE, SAMPLE, VISITOR, POOLED, HIDDEN_UNIT, BELOW_HIDDEN = 1, 2, 3, 4, 5, 6, 7
GRAPH = {
    FIELD_UNIT: ([], [at(FIELD)]),
    TREE: ([FIELD_UNIT], [at(FIELD, '2024', layout_id=10, coordinates=['3', '5'])]),
    SAMPLE: ([TREE], [at(LAB, '2025-03-25')]),
    VISITOR: ([FIELD_UNIT], [at(LAB, '2024-06', '2024-07'), at(FIELD, '2024-07')]),
    POOLED: ([TREE, VISITOR], []),
    HIDDEN_UNIT: ([FIELD_UNIT], [at(STORE, '2025-01')]),
    BELOW_HIDDEN: ([HIDDEN_UNIT], []),
}


def placed(unit_id: int, time: str, hidden=()) -> Position | None:
    return place_at(
        unit_id,
        datetime64(time),
        positions_of=lambda u: GRAPH[u][1],
        parents_of=lambda u: GRAPH[u][0],
        hidden=lambda u: u in hidden
    )


def test_a_unit_is_placed_by_its_own_position_then_or_the_units_above_it():
    # its own position, with its layout and coordinates: not its times
    assert placed(TREE, '2025-05-03') == Position(location_id=FIELD, layout_id=10, coordinates=['3', '5'])
    # before the tree's position starts, it is where its field is
    assert placed(TREE, '2023-05-03') == Position(location_id=FIELD)
    # a sample at the lab from its arrival, and with its tree before it
    assert placed(SAMPLE, '2025-04-01') == Position(location_id=LAB)
    assert placed(SAMPLE, '2025-03-01') == Position(location_id=FIELD, layout_id=10, coordinates=['3', '5'])
    # a visit: at the lab during it, back in the field after it, the later-starting position once a move starts it
    assert placed(VISITOR, '2024-06-15') == Position(location_id=LAB)
    assert placed(VISITOR, '2024-07') == Position(location_id=FIELD)


def test_a_place_cant_be_told_where_lineages_differ_or_a_hidden_unit_stops_the_walk():
    # pooled from the tree in the field and a tree visiting the lab: placed only when they agree
    assert placed(POOLED, '2024-06-15') is None
    assert placed(POOLED, '2025-05-03') is None  # the field, but at different grid positions and layouts
    # a hidden unit with positions stops the walk, whether or not they hold then; without positions it is passed
    assert placed(BELOW_HIDDEN, '2025-05-03') == Position(location_id=STORE)
    assert placed(BELOW_HIDDEN, '2025-05-03', hidden={HIDDEN_UNIT}) is None
    assert placed(BELOW_HIDDEN, '2024-05-03', hidden={HIDDEN_UNIT}) is None
    assert placed(TREE, '2025-05-03', hidden={HIDDEN_UNIT}) is not None


def test_children_are_named_from_the_template():
    assert child_name(CHILD_NAME_TEMPLATE, 'Tree 1', 'Leaf', 1) == 'Tree 1 - Leaf 1'
    assert child_name('{parent}/{n}', 'T12', 'Leaf', 3) == 'T12/3'
    # each placeholder is filled in once, so braces in a parent's name, and other braces, are kept
    assert child_name('{parent} {n} {x}', 'Tree {n}', 'Leaf', 2) == 'Tree {n} 2 {x}'

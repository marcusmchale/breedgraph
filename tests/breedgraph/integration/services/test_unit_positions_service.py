"""
Positions written outside the unit graph (application.unit_positions), on the arrivals scenario's spare units
(tests/breedgraph/scenarios/arrival_scenario.py): an edit of a unit committed after a move it never saw keeps the move,
as the unit graph repository no longer writes positions; two moves of the same unit follow one another, the second
waiting for the first's lock and reading the positions it left; and an arrival selects the units the user can read.
"""
import asyncio

import pytest
from numpy import datetime64

from breedgraph.domain.model.unit_graphs import Position
from breedgraph.service_layer.application.unit_positions import ArrivalSelection
from tests.breedgraph.scenarios.arrival_scenario import EXPECTED_ARRIVALS, LAB, STORE, FIELD


async def positions_of(uow_factory, user_id: int, unit_id: int) -> list:
    async with uow_factory.get_uow(user_id=user_id) as uow:
        unit = (await uow.repositories.unit_graphs.get(unit_id=unit_id)).get_unit(unit_id)
    return unit, [(p.location_id, str(p.start), None if p.end is None else str(p.end)) for p in unit.positions]


@pytest.mark.asyncio(loop_scope="session")
async def test_a_unit_edit_keeps_a_move_it_did_not_see(uow_factory, read_policy, arrivals):
    writer, sample = read_policy['writer'], arrivals.units['Arrival Move Sample 1']
    async with uow_factory.get_uow(user_id=writer) as editing:
        unit_graph = await editing.repositories.unit_graphs.get(unit_id=sample)
        unit_graph.get_unit(sample).description = "Described while it moved"
        async with uow_factory.get_uow(user_id=writer) as moving:
            await moving.positions.move_units(
                [sample], Position(location_id=arrivals.ids[STORE], start=datetime64('2025-07-01'))
            )
            await moving.commit()
        # its positions as loaded are stale: the lab only
        await editing.commit()
    unit, positions = await positions_of(uow_factory, writer, sample)
    assert unit.description == "Described while it moved"
    assert positions == [(read_policy[LAB], '2025-06-10', '2025-07-01'), (arrivals.ids[STORE], '2025-07-01', None)]


@pytest.mark.asyncio(loop_scope="session")
async def test_moves_of_the_same_unit_follow_one_another(uow_factory, read_policy, arrivals):
    writer, sample = read_policy['writer'], arrivals.units['Arrival Move Sample 2']
    moved, release = asyncio.Event(), asyncio.Event()

    async def move(location_id: int, start: str, hold: bool):
        async with uow_factory.get_uow(user_id=writer) as uow:
            await uow.positions.move_units([sample], Position(location_id=location_id, start=datetime64(start)))
            if hold:
                moved.set()
                await release.wait()
            await uow.commit()

    first = asyncio.create_task(move(arrivals.ids[STORE], '2025-07-01', hold=True))
    await moved.wait()
    second = asyncio.create_task(move(read_policy[FIELD], '2025-08-01', hold=False))
    await asyncio.sleep(1)
    assert not second.done(), "the second move waits for the sample's write lock"
    release.set()
    await asyncio.gather(first, second)
    _, positions = await positions_of(uow_factory, writer, sample)
    # read after the first committed: its store position ended by the second, the lab's left as the first ended it
    assert positions == [
        (read_policy[LAB], '2025-06-10', '2025-07-01'),
        (arrivals.ids[STORE], '2025-07-01', '2025-08-01'),
        (read_policy[FIELD], '2025-08-01', None)
    ]


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', ['writer', 'outsider'])
async def test_an_arrival_selects_the_units_the_user_can_read(uow_factory, read_policy, arrivals, viewer):
    async with uow_factory.get_uow(user_id=read_policy[viewer]) as uow:
        unit_ids = await uow.positions.selected_unit_ids(
            None, ArrivalSelection(location_id=read_policy[LAB], start=datetime64('2025-03-25'))
        )
    names = {unit_id: name for name, unit_id in arrivals.units.items()}
    assert sorted(names[unit_id] for unit_id in unit_ids) == sorted(dict(EXPECTED_ARRIVALS[LAB][viewer])['2025-03-25'])

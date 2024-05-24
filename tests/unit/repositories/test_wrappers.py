import pytest

from pydantic import BaseModel
from src.breedgraph.adapters.repositories.trackable_wrappers import Tracked
from typing import List, Set, Dict

class SimpleModel(BaseModel):
    id: int = 0
    name: str = 'Simple Model'
    things: List = list()

    def __hash__(self):
        return hash(self.id)

class ComplexModel(BaseModel):
    str_value: str = 'Test Model'
    int_value: int = 1
    list_int: List[int] = [1, 2, 3]
    list_model: List[SimpleModel] = [SimpleModel()]
    set_int: Set[int] = {1, 2, 3}
    set_model: Set[SimpleModel] = {SimpleModel()}
    dict_int_str: Dict[int, str] = {1: 'a'}
    dict_int_model: Dict[int, SimpleModel] = {1: SimpleModel()}

@pytest.mark.asyncio
async def test_attribute_change():
    tracked = Tracked(ComplexModel())
    assert not tracked.changed

    tracked.str_value = 'Changed Name'
    assert "str_value" in tracked.changed

    tracked.int_value = 2
    assert 'int_value' in tracked.changed

    tracked.reset_tracking()
    assert not tracked.changed

@pytest.mark.asyncio
async def test_list_change():
    tracked = Tracked(ComplexModel())
    assert not tracked.changed
    assert not tracked.list_int.changed

    tracked.list_int[0] = -1
    assert 'list_int' in tracked.changed
    assert 0 in tracked.list_int.changed

    tracked.reset_tracking()
    assert not tracked.list_int.changed

@pytest.mark.asyncio
async def test_list_append():
    tracked = Tracked(ComplexModel())
    assert not tracked.changed
    assert not tracked.list_int.added

    tracked.list_int.append(4)
    assert 'list_int' in tracked.changed
    assert 3 in tracked.list_int.added

    tracked.reset_tracking()
    assert not tracked.list_int.changed
    assert not tracked.list_int.added

@pytest.mark.asyncio
async def test_list_remove():
    tracked = Tracked(ComplexModel())
    assert not tracked.changed
    assert not tracked.list_int.removed
    assert not tracked.list_int.added

    tracked.list_int.append(4)
    assert 'list_int' in tracked.changed
    assert 3 in tracked.list_int.added

    tracked.list_int.remove(2)
    assert 'list_int' in tracked.changed
    assert not tracked.list_int.changed
    assert 2 in tracked.list_int.removed
    assert 2 in tracked.list_int.added

    tracked.reset_tracking()
    assert not tracked.list_int.changed
    assert not tracked.list_int.added
    assert not tracked.list_int.removed

@pytest.mark.asyncio
async def test_tracked_list_insert():
    tracked = Tracked(ComplexModel())
    assert not tracked.changed
    assert not tracked.list_int.removed
    assert not tracked.list_int.added

    tracked.list_int.append(4)
    assert 'list_int' in tracked.changed
    assert 3 in tracked.list_int.added

    tracked.list_int.insert(2, 2)
    assert 'list_int' in tracked.changed
    assert not tracked.list_int.changed
    assert 2 in tracked.list_int.added
    assert 4 in tracked.list_int.added

    tracked.reset_tracking()
    assert not tracked.list_int.changed
    assert not tracked.list_int.added
    assert not tracked.list_int.removed


@pytest.mark.asyncio
async def test_tracked_list_model_change():
    tracked = Tracked(ComplexModel())
    assert not tracked.changed
    assert not tracked.list_int.changed

    tracked.list_model[0].name = "Changed"
    assert 'list_model' in tracked.changed
    assert 0 in tracked.list_model.changed

    tracked.reset_tracking()
    assert not tracked.changed
    assert not tracked.list_model.changed



@pytest.mark.asyncio
async def test_tracked_list_model_things_change():
    tracked = Tracked(ComplexModel())
    assert not tracked.changed
    assert not tracked.list_int.changed

    tracked.list_model[0].things.append("New")

    assert 'list_model' in tracked.changed
    assert 0 in tracked.list_model.changed
    assert 'things' in tracked.list_model[0].changed
    assert 0 in tracked.list_model[0].things.added

    tracked.reset_tracking()
    assert not tracked.changed
    assert not tracked.list_model.changed
    assert not tracked.list_model[0].changed
    assert not tracked.list_model[0].things.added


@pytest.mark.asyncio
async def test_tracked_set_add():
    tracked = Tracked(ComplexModel())
    assert not tracked.changed
    assert not tracked.set_int.changed

    tracked.set_int.add(-1)
    assert 'set_int' in tracked.changed
    assert hash(-1) in tracked.set_int.added

    tracked.reset_tracking()
    assert not tracked.set_int.changed

@pytest.mark.asyncio
async def test_tracked_set_discard():
    tracked = Tracked(ComplexModel())
    assert not tracked.changed
    assert not tracked.set_int.changed

    tracked.set_int.discard(1)
    assert 'set_int' in tracked.changed
    assert hash(1) in tracked.set_int.removed

    tracked.reset_tracking()
    assert not tracked.set_int.changed

@pytest.mark.asyncio
async def test_tracked_set_changed():
    tracked = Tracked(ComplexModel())
    assert not tracked.changed
    assert not tracked.set_int.changed

    for item in tracked.set_model:
        item.name = "new name"
        assert 'name' in item.changed
        assert hash(item) in tracked.set_model.changed
    assert 'set_model' in tracked.changed

    tracked.reset_tracking()
    assert not tracked.set_model.changed

@pytest.mark.asyncio
async def test_tracked_dict_change():
    tracked = Tracked(ComplexModel())
    assert not tracked.changed
    assert not tracked.dict_int_str.changed

    tracked.dict_int_str[1] = 'b'
    assert 'dict_int_str' in tracked.changed
    assert 1 in tracked.dict_int_str.changed

    tracked.reset_tracking()
    assert not tracked.changed
    assert not tracked.dict_int_str.changed

@pytest.mark.asyncio
async def test_tracked_dict_change_model():
    tracked = Tracked(ComplexModel())
    assert not tracked.changed
    assert not tracked.dict_int_str.changed

    tracked.dict_int_model[1].name = "New Name"
    assert 'dict_int_model' in tracked.changed
    assert 1 in tracked.dict_int_model.changed
    assert 'name' in tracked.dict_int_model[1].changed

    tracked.reset_tracking()
    assert not tracked.changed
    assert not tracked.dict_int_model.changed
    assert not tracked.dict_int_model[1].changed
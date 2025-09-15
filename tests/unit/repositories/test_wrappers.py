import pytest

from dataclasses import dataclass, field
from src.breedgraph.service_layer.tracking.wrappers import tracked
from typing import List, Set, Dict

@dataclass
class SimpleModel:
    id: int = 0
    name: str = 'Simple Model'
    things: List = field(default_factory=list)

    def __hash__(self):
        return hash(self.id)

@dataclass
class ComplexModel:
    str_value: str = 'Test Model'
    int_value: int = 1
    list_int: List[int] = field(default_factory = lambda: [1, 2, 3])
    list_model: List[SimpleModel] = field(default_factory = lambda: [SimpleModel()])
    set_int: Set[int] = field(default_factory = lambda: {1, 2, 3})
    set_model: Set[SimpleModel] = field(default_factory = lambda: {SimpleModel()})
    dict_int_str: Dict[int, str] = field(default_factory = lambda: {1: 'a'})
    dict_int_model: Dict[int, SimpleModel] = field(default_factory= lambda: {1: SimpleModel()})


@pytest.mark.asyncio
async def test_attribute_change():
    tracked_model = tracked(ComplexModel())
    assert not tracked_model.changed

    tracked_model.str_value = 'Changed Name'
    assert "str_value" in tracked_model.changed

    tracked_model.int_value = 2
    assert 'int_value' in tracked_model.changed

    tracked_model.reset_tracking()
    assert not tracked_model.changed

@pytest.mark.asyncio
async def test_list_change():
    tracked_model = tracked(ComplexModel())
    assert not tracked_model.changed
    assert not tracked_model.list_int.changed

    tracked_model.list_int[0] = -1
    assert 'list_int' in tracked_model.changed
    assert 0 in tracked_model.list_int.changed

    tracked_model.reset_tracking()
    assert not tracked_model.list_int.changed

@pytest.mark.asyncio
async def test_list_append():
    tracked_model = tracked(ComplexModel())
    assert not tracked_model.changed
    assert not tracked_model.list_int.added

    tracked_model.list_int.append(4)
    assert 'list_int' in tracked_model.changed
    assert 3 in tracked_model.list_int.added

    tracked_model.reset_tracking()
    assert not tracked_model.list_int.changed
    assert not tracked_model.list_int.added

@pytest.mark.asyncio
async def test_list_remove():
    tracked_model = tracked(ComplexModel())
    assert not tracked_model.changed
    assert not tracked_model.list_int.removed
    assert not tracked_model.list_int.added

    tracked_model.list_int.append(4)
    assert 'list_int' in tracked_model.changed
    assert 3 in tracked_model.list_int.added

    tracked_model.list_int.remove(2)
    assert 'list_int' in tracked_model.changed
    assert not tracked_model.list_int.changed
    assert 2 in tracked_model.list_int.removed
    assert 2 in tracked_model.list_int.added

    tracked_model.reset_tracking()
    assert not tracked_model.list_int.changed
    assert not tracked_model.list_int.added
    assert not tracked_model.list_int.removed

@pytest.mark.asyncio
async def test_tracked_list_insert():
    tracked_model= tracked(ComplexModel())
    assert not tracked_model.changed
    assert not tracked_model.list_int.removed
    assert not tracked_model.list_int.added

    tracked_model.list_int.append(4)
    assert 'list_int' in tracked_model.changed
    assert 3 in tracked_model.list_int.added

    tracked_model.list_int.insert(2, 2)
    assert 'list_int' in tracked_model.changed
    assert not tracked_model.list_int.changed
    assert 2 in tracked_model.list_int.added
    assert 4 in tracked_model.list_int.added

    tracked_model.reset_tracking()
    assert not tracked_model.list_int.changed
    assert not tracked_model.list_int.added
    assert not tracked_model.list_int.removed


@pytest.mark.asyncio
async def test_tracked_list_model_change():
    tracked_model= tracked(ComplexModel())
    assert not tracked_model.changed
    assert not tracked_model.list_int.changed

    tracked_model.list_model[0].name = "Changed"
    assert 'list_model' in tracked_model.changed
    assert 0 in tracked_model.list_model.changed

    tracked_model.reset_tracking()
    assert not tracked_model.changed
    assert not tracked_model.list_model.changed



@pytest.mark.asyncio
async def test_tracked_list_model_things_change():
    tracked_model= tracked(ComplexModel())
    assert not tracked_model.changed
    assert not tracked_model.list_int.changed

    tracked_model.list_model[0].things.append("New")

    assert 'list_model' in tracked_model.changed
    assert 0 in tracked_model.list_model.changed
    assert 'things' in tracked_model.list_model[0].changed
    assert 0 in tracked_model.list_model[0].things.added

    tracked_model.reset_tracking()
    assert not tracked_model.changed
    assert not tracked_model.list_model.changed
    assert not tracked_model.list_model[0].changed
    assert not tracked_model.list_model[0].things.added


@pytest.mark.asyncio
async def test_tracked_set_add():
    tracked_model= tracked(ComplexModel())
    assert not tracked_model.changed
    assert not tracked_model.set_int.changed

    tracked_model.set_int.add(-1)
    assert 'set_int' in tracked_model.changed
    assert hash(-1) in tracked_model.set_int.added

    tracked_model.reset_tracking()
    assert not tracked_model.set_int.changed

@pytest.mark.asyncio
async def test_tracked_set_discard():
    tracked_model= tracked(ComplexModel())
    assert not tracked_model.changed
    assert not tracked_model.set_int.changed

    tracked_model.set_int.discard(1)
    assert 'set_int' in tracked_model.changed
    assert hash(1) in tracked_model.set_int.removed

    tracked_model.reset_tracking()
    assert not tracked_model.set_int.changed

@pytest.mark.asyncio
async def test_tracked_set_changed():
    tracked_model= tracked(ComplexModel())
    assert not tracked_model.changed
    assert not tracked_model.set_int.changed

    for item in tracked_model.set_model:
        item.name = "new name"
        assert 'name' in item.changed
        assert hash(item) in tracked_model.set_model.changed
    assert 'set_model' in tracked_model.changed

    tracked_model.reset_tracking()
    assert not tracked_model.set_model.changed

@pytest.mark.asyncio
async def test_tracked_dict_change():
    tracked_model= tracked(ComplexModel())
    assert not tracked_model.changed
    assert not tracked_model.dict_int_str.changed

    tracked_model.dict_int_str[1] = 'b'
    assert 'dict_int_str' in tracked_model.changed
    assert 1 in tracked_model.dict_int_str.changed

    tracked_model.reset_tracking()
    assert not tracked_model.changed
    assert not tracked_model.dict_int_str.changed

@pytest.mark.asyncio
async def test_tracked_dict_change_model():
    tracked_model= tracked(ComplexModel())
    assert not tracked_model.changed
    assert not tracked_model.dict_int_str.changed

    tracked_model.dict_int_model[1].name = "New Name"
    assert 'dict_int_model' in tracked_model.changed
    assert 1 in tracked_model.dict_int_model.changed
    assert 'name' in tracked_model.dict_int_model[1].changed

    tracked_model.reset_tracking()
    assert not tracked_model.changed
    assert not tracked_model.dict_int_model.changed
    assert not tracked_model.dict_int_model[1].changed
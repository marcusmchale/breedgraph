import pytest

from dataclasses import dataclass, field
from breedgraph.service_layer.tracking.wrappers import tracked
from typing import List, Set, Dict
from datetime import datetime, date, timezone

@dataclass
class SimpleModel:
    id: int = 0
    name: str = 'Simple Model'
    things: List = field(default_factory=list)

    def __hash__(self):
        return hash(self.id)

    def rename(self, name: str):
        self.name = name

@dataclass
class ComplexModel:
    str_value: str = 'Test Model'
    int_value: int = 1
    list_int: List[int] = field(default_factory = lambda: [1, 2, 3])
    list_model: List[SimpleModel] = field(default_factory = lambda: [SimpleModel()])
    dict_int_str: Dict[int, str] = field(default_factory = lambda: {1: 'a'})
    dict_int_model: Dict[int, SimpleModel] = field(default_factory= lambda: {1: SimpleModel()})

    def set_int_value(self, value: int):
        self.int_value = value

    def replace_list_int(self, values: List[int]):
        self.list_int = values

    @property
    def doubled(self) -> int:
        return self.int_value * 2


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


@pytest.mark.asyncio
async def test_method_attribute_change():
    tracked_model = tracked(ComplexModel())
    tracked_model.set_int_value(5)
    assert 'int_value' in tracked_model.changed
    assert tracked_model.int_value == 5
    assert tracked_model.__wrapped__.int_value == 5

@pytest.mark.asyncio
async def test_method_unchanged_value_is_not_a_change():
    tracked_model = tracked(ComplexModel())
    tracked_model.set_int_value(tracked_model.int_value)
    assert not tracked_model.changed

@pytest.mark.asyncio
async def test_method_replaced_list_is_tracked():
    tracked_model = tracked(ComplexModel())
    tracked_model.replace_list_int([7, 8])
    assert 'list_int' in tracked_model.changed

    tracked_model.reset_tracking()
    tracked_model.list_int.append(9)
    assert 'list_int' in tracked_model.changed
    assert tracked_model.list_int == [7, 8, 9]

@pytest.mark.asyncio
async def test_method_on_nested_model_change():
    tracked_model = tracked(ComplexModel())
    tracked_model.list_model[0].rename('Renamed')
    assert 'list_model' in tracked_model.changed
    assert tracked_model.list_model[0].name == 'Renamed'

@pytest.mark.asyncio
async def test_properties_through_proxy():
    tracked_model = tracked(ComplexModel())
    assert tracked_model.doubled == 2
    assert not tracked_model.changed


@dataclass
class TimedModel:
    time: datetime | None = None
    day: date | None = None

    def set_time(self, value: datetime):
        self.time = value


@pytest.mark.asyncio
async def test_datetime_assignment():
    tracked_model = tracked(TimedModel(time=datetime(2020, 1, 1, tzinfo=timezone.utc)))
    tracked_model.set_time(datetime(2021, 1, 1, tzinfo=timezone.utc))
    tracked_model.day = date(2021, 1, 1)
    assert {'time', 'day'} <= tracked_model.changed
    assert tracked_model.time == datetime(2021, 1, 1, tzinfo=timezone.utc)
    assert tracked_model.day == date(2021, 1, 1)

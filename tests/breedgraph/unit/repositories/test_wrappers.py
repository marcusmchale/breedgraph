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


""" Callbacks: one per owner, finding a list item's index when it fires, and detached when a value is removed """
def changed_names(tracked_list) -> list[str]:
    models = []
    tracked_list.collect_changed_models(models)
    return [model.name for model in models]


@pytest.mark.parametrize('before', ['insert', 'delete', 'slice'])
def test_list_item_change_after_shifting_its_index(before):
    tracked_model = tracked(ComplexModel(list_model=[SimpleModel(id=i, name=n) for i, n in enumerate('abc')]))
    item = tracked_model.list_model[2]
    if before == 'insert':
        tracked_model.list_model.insert(0, SimpleModel(id=9, name='new'))
    elif before == 'delete':
        del tracked_model.list_model[0]
    else:
        tracked_model.list_model[0:1] = [SimpleModel(id=8, name='x'), SimpleModel(id=9, name='y')]
    tracked_model.reset_tracking()

    item.rename('changed')
    assert changed_names(tracked_model.list_model) == ['changed']
    assert 'list_model' in tracked_model.changed


def test_removed_values_no_longer_notify_their_owner():
    tracked_model = tracked(ComplexModel())
    from_list, from_dict, from_attribute = tracked_model.list_model[0], tracked_model.dict_int_model[1], tracked_model.list_int
    tracked_model.list_model.remove(from_list)
    tracked_model.dict_int_model[1] = SimpleModel(id=2)
    tracked_model.list_int = [4, 5]
    tracked_model.reset_tracking()

    from_list.rename('gone')
    from_dict.rename('gone')
    from_attribute.append(6)
    assert not tracked_model.changed
    assert not tracked_model.list_model.changed and not tracked_model.dict_int_model.changed


def test_a_value_held_twice_notifies_each_owner():
    tracked_model = tracked(ComplexModel())
    shared = tracked_model.list_model[0]
    tracked_model.dict_int_model[2] = shared
    tracked_model.reset_tracking()

    shared.rename('shared')
    assert tracked_model.list_model.changed == {0}
    assert tracked_model.dict_int_model.changed == {2}
    assert {'list_model', 'dict_int_model'} <= tracked_model.changed


def test_tracking_a_value_again_for_the_same_owner_replaces_its_callback():
    tracked_list = tracked([SimpleModel()])
    item = tracked_list[0]
    for _ in range(5):
        tracked_list.silent_append(item)
        tracked_list.silent_remove(item)
    tracked_list[0] = item
    assert len(item._self_on_changed) == 1


def test_a_discarded_list_releases_its_items():
    tracked_model = tracked(ComplexModel(list_model=[SimpleModel(id=i) for i in range(3)]))
    for _ in range(5):
        # a new list of the same items, as when an attribute is rebuilt from its own value
        tracked_model.list_model = list(tracked_model.list_model)
    assert all(len(item._self_on_changed) == 1 for item in tracked_model.list_model)
    # the new list, equal to the one it replaced, is tracked too
    tracked_model.reset_tracking()
    tracked_model.list_model.append(SimpleModel(id=3))
    assert tracked_model.list_model.added == {3} and 'list_model' in tracked_model.changed


def test_an_object_moved_to_another_owner_keeps_tracking_its_values():
    tracked_model = tracked(ComplexModel(list_model=[SimpleModel(id=1)]))
    item = tracked_model.list_model[0]
    tracked_model.list_model.remove(item)
    tracked_model.dict_int_model[5] = item
    tracked_model.reset_tracking()

    item.things.append('thing')
    assert tracked_model.dict_int_model.changed == {5}


def test_a_list_given_back_to_its_owner_attaches_its_items_again():
    tracked_model = tracked(ComplexModel())
    list_model = tracked_model.list_model
    tracked_model.list_model = []
    tracked_model.list_model = list_model
    tracked_model.reset_tracking()

    list_model[0].rename('again')
    assert tracked_model.list_model.changed == {0}
    assert 'list_model' in tracked_model.changed


@dataclass
class StartedModel:
    start: object = None


def test_a_change_of_time_precision_alone_is_a_change():
    """numpy counts 2021-05 and 2021-05-01 as equal, but a time is stored with its precision"""
    from numpy import datetime64
    tracked_model = tracked(StartedModel(start=datetime64('2021-05')))
    tracked_model.start = datetime64('2021-05')
    assert not tracked_model.changed

    tracked_model.start = datetime64('2021-05-01')
    assert 'start' in tracked_model.changed

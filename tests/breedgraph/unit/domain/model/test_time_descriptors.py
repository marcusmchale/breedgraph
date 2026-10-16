import pytest
from numpy import datetime_data, datetime64
from pydantic import BaseModel
from neo4j.time import DateTime as Neo4jDateTime
from datetime import datetime


from breedgraph.domain.model.time_descriptors import PyDT64

class TimeBase(BaseModel):
    time: PyDT64

def test_as_model_attr():
    time_str = '2001'
    test_class = TimeBase(time=time_str)
    dump = test_class.model_dump()
    time_dict = dump.get('time')
    assert time_dict.get('str') == time_str
    assert time_dict.get('unit') == 'Y'
    assert time_dict.get('step') == 1


@pytest.mark.parametrize('time, expected', [
    ('2021', '2022'),
    ('2021-12', '2022-01'),
    ('2020-02-29', '2020-03-01'),
    ('2021-05-03T23', '2021-05-04T00'),
    ('2021-05-03T10:59', '2021-05-03T11:00'),
    ('2021-05-03T10:30:59', '2021-05-03T10:31:00'),
])
def test_upper_is_the_end_of_the_period(time, expected):
    from breedgraph.domain.model.time_descriptors import upper
    end = upper(datetime64(time))
    assert end == datetime64(expected)
    assert datetime_data(end) == datetime_data(datetime64(time))


def test_upper_takes_the_step():
    from breedgraph.domain.model.time_descriptors import upper
    assert upper(datetime64('2021-05-03T10:30', ('m', 15))) == datetime64('2021-05-03T10:45')


@pytest.mark.parametrize('time', ['2021', '2021-05', '2021-05-03', '2021-05-03T10', '2021-05-03T10:30', '2021-05-03T10:30:15'])
def test_local_times_keep_their_precision_through_neo4j(time):
    from breedgraph.domain.model.time_descriptors import parse_local_datetime, npdt64_to_local, deserialize_time, same_time
    entered = parse_local_datetime(time)
    stored = npdt64_to_local(entered)
    assert stored.tzinfo is None
    assert same_time(deserialize_time(stored, *datetime_data(entered)), entered)


@pytest.mark.parametrize('time', ['2021-05-03T10:30Z', '2021-05-03T10:30+02:00', '2021-05-03T10:30-0300', '2021-05-03 10+01'])
def test_times_with_an_offset_are_refused(time):
    from breedgraph.domain.model.time_descriptors import parse_local_datetime, TimeZoneGivenError
    with pytest.raises(TimeZoneGivenError):
        parse_local_datetime(time)
    with pytest.raises(ValueError):
        TimeBase(time=time)


def test_timezone_aware_datetimes_are_refused():
    from datetime import timezone
    with pytest.raises(ValueError):
        TimeBase(time=datetime(2021, 5, 3, 10, 30, tzinfo=timezone.utc))


def test_same_time_compares_precision():
    from breedgraph.domain.model.time_descriptors import same_time
    assert datetime64('2021-05') == datetime64('2021-05-01')
    assert not same_time(datetime64('2021-05'), datetime64('2021-05-01'))
    assert same_time(datetime64('2021-05'), datetime64('2021-05'))
    assert same_time(None, None) and not same_time(None, datetime64('2021'))


@pytest.mark.parametrize('start, end, other_start, other_end, overlap', [
    # an end includes its whole period
    ('2021-05-01', '2021-05-03', '2021-05-03T18:00', None, True),
    ('2021-05-01', '2021-05-03', '2021-05-04', None, False),
    ('2021', '2021', '2021-06', '2021-06', True),
    (None, '2020', '2021', None, False),
    (None, None, '2021', '2021', True),
])
def test_intervals_overlap_over_periods(start, end, other_start, other_end, overlap):
    from breedgraph.domain.model.analysis import intervals_overlap
    as_time = lambda time: datetime64(time) if time is not None else None
    assert intervals_overlap(as_time(start), as_time(end), as_time(other_start), as_time(other_end)) == overlap


def test_the_graphql_datetime_scalar_refuses_offsets():
    from breedgraph.entrypoints.fastapi.graphql.resolvers import parse_datetime
    assert str(parse_datetime('2021-05-03T10:30')) == '2021-05-03T10:30'
    with pytest.raises(ValueError):
        parse_datetime('2021-05-03T10:30+02:00')

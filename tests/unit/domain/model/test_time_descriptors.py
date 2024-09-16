import pytest
from numpy import datetime_data, datetime64
from pydantic import BaseModel
from neo4j.time import DateTime as Neo4jDateTime
from datetime import datetime


from src.breedgraph.domain.model.time_descriptors import PyDT64

class TimeBase(BaseModel):
    time: PyDT64

def test_time_from_text():
    time = PyDT64("2025")
    assert datetime_data(time)[0] == 'Y'

def test_time_from_dt64():
    time = datetime64("2023")
    assert datetime_data(time)[0] == 'Y'

def test_time_from_neo4j():
    time = Neo4jDateTime(year=23, month=1, day=1)
    dt = PyDT64(time)
    assert datetime_data(dt)[0] == 'D'

def test_time_from_native():
    time = datetime(year=2023, month=1, day=1)
    dt = PyDT64(time)
    assert datetime_data(dt)[0] == 'us'

def test_as_model_attr():
    time_str = '2001'
    test_class = TimeBase(time=time_str)
    dump = test_class.model_dump()
    time_dict = dump.get('time')
    assert time_dict.get('str') == time_str
    assert time_dict.get('unit') == 'Y'
    assert time_dict.get('step') == 1

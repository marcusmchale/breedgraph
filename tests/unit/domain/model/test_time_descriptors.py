import pytest
from numpy import datetime_data, datetime64
from pydantic import BaseModel
from neo4j.time import DateTime as Neo4jDateTime
from datetime import datetime


from src.breedgraph.domain.model.time_descriptors import PyDT64

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

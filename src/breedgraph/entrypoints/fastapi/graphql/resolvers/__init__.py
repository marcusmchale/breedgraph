from . import mutations
from . import queries
from ariadne import ScalarType

from .mutations import graphql_mutation
from .queries import graphql_query
from numpy import datetime64
from datetime import datetime

team = queries.organisations.team
user = queries.organisations.user
account = queries.accounts.account
affiliations = queries.organisations.affiliations
affiliation = queries.organisations.affiliation
ontology_entry = queries.ontologies.ontology_entry
location = queries.regions.location
layout = queries.arrangements.layout
unit = queries.blocks.unit
dataset = queries.datasets.dataset
record = queries.datasets.record
program = queries.programs.program
trial = queries.programs.trial
study = queries.programs.study
controller = queries.controls.controller
control = queries.controls.control
write_stamp = queries.controls.write_stamp
user_access = queries.organisations.user_access

datetime_scalar = ScalarType("DateTime")

@datetime_scalar.value_parser
def parse_datetime(value):
    return datetime64(value)

@datetime_scalar.serializer
def serialize_datetime(value):
    """Serialize datetime objects to ISO format strings"""
    if isinstance(value, datetime):
        return value.isoformat()
    elif isinstance(value, datetime64):
        return str(value)
    return value
from . import mutations
from . import queries
from ariadne import ScalarType

from .mutations import graphql_mutation
from .queries import graphql_query
from numpy import datetime64

team = queries.organisations.team
user = queries.organisations.user
account = queries.accounts.account
affiliations = queries.organisations.affiliations
affiliation = queries.organisations.affiliation
ontology_entry = queries.ontologies.ontology_entry
location = queries.regions.location
layout = queries.arrangements.layout
unit = queries.blocks.unit

datetime_scalar = ScalarType("DateTime")

@datetime_scalar.value_parser
def parse_datetime(value):
    return datetime64(value)
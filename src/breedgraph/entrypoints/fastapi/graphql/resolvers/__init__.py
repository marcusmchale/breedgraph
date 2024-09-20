from . import mutations
from . import queries

from .mutations import graphql_mutation
from .queries import graphql_query

team = queries.organisations.team
user = queries.organisations.user
account = queries.accounts.account

affiliations = queries.organisations.affiliations
affiliation = queries.organisations.affiliation
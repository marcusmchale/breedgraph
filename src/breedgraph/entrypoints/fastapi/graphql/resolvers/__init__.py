from . import mutations
from . import queries

from .mutations import graphql_mutation
from .queries import graphql_query

team = queries.organisations.team
account = queries.accounts.account
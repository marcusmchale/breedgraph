from . import graphql_query

from neo4j_graphql_py import neo4j_graphql
from dbtools.entrypoints.flask_app import bus


@graphql_query.field("allowed_email")
def allowed_email(*_, email: str):
	with bus.uow as uow:
		return uow.emails.exists(email)


@graphql_query.field("get_teams")
def get_teams(obj, info, **kwargs):
	return neo4j_graphql(obj, info.context, info, **kwargs)

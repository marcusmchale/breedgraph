from flask import jsonify, request

from dbtools.entrypoints.flask_app import app, bus

from ariadne import (
	graphql_sync,  # todo consider asgi implementation of the dbtools
	make_executable_schema,
	load_schema_from_path,
	snake_case_fallback_resolvers
)

from ariadne.constants import PLAYGROUND_HTML

from dbtools.adapters.graphql import graphql_schema


@app.route('/graphql', methods=['GET'])
def playground():
	return PLAYGROUND_HTML, 200


@app.route('/graphql', methods=['POST'])
def graphql_server():
	data = request.get_json()
	success, result = graphql_sync(
		graphql_schema,
		data,
		context_value={'driver': bus.uow.driver, 'request': request},  # driver is used by neo4j_graphql_py
		debug=True,
		logger="logger"
	)
	status_code = 200 if success else 400
	return jsonify(result), status_code

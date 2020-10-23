from flask import Flask
from dbtools import bootstrap
from dbtools.entrypoints.flask_app.decorators import neo4j_required, redis_required
from flask_cors import CORS
import logging


__all__ = ['app', 'bus']


def create_app():
	app_instance = Flask(__name__)
	# allow cross origin requests
	CORS(app_instance) #, resources={r"/graphql": {"origins": "localhost:8080"}})

	app_instance.config.from_object('dbtools.config')

	formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
	logger = logging.getLogger()
	logger.setLevel(logging.DEBUG)
	fh = logging.FileHandler(app_instance.config['BREEDGRAPH_LOG'])
	fh.setFormatter(formatter)
	logger.addHandler(fh)
	logger.info("started")

	return app_instance


app = create_app()
bus = bootstrap.bootstrap(app=app)

# currently only using the app in bootstrap for flask_mail consider breaking this up by using another package.

import dbtools.entrypoints.flask_app.views

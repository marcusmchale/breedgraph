#!venv/bin/python
from dbtools.entrypoints.flask_app import app

if __name__ == '__main__':
	app.run(debug=True)

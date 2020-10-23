from flask import render_template, request
from dbtools.entrypoints.flask_app import app


@app.route('/index', methods=['GET'])
def index():
	return render_template('index.html', title='Home')


# Other than the index, static views are mostly to allow a simple link with data to be included in an email
@app.route('/confirm_user', methods=['GET'])
def confirm_account():
	return render_template("confirm_user.html", token=request.args.get('token'))

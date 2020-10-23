from functools import wraps
from flask import session, flash, redirect, url_for
from neo4j.exceptions import ServiceUnavailable
from redis.exceptions import ConnectionError
import logging


def neo4j_required(func):
	@wraps(func)
	def decorated_function(*args, **kwargs):
		try:
			return func(*args, **kwargs)
		except ServiceUnavailable:
			logging.error('Neo4j connection error')
			flash("Database unavailable")
			return redirect(url_for('index'))

	return decorated_function()


def redis_required(func):
	@wraps(func)
	def decorated_function(*args, **kwargs):
		try:
			return func(*args, **kwargs)
		except ConnectionError:
			logging.error('Redis connection error')
			flash("Login temporarily unavailable")
			return redirect(url_for('index'))

	return decorated_function()


def login_required(func):
	@wraps(func)
	def decorated_function(*args, **kwargs):
		if 'username' in session:
			return func(*args, **kwargs)
		else:
			flash("Please log in")
			return redirect(url_for('login'))

	return decorated_function()


def admin_required(func):
	@wraps(func)
	def decorated_function(*args, **kwargs):
		admin_access = ['partner_admin', 'global_admin']
		if 'access' in session and any([i in session['access'] for i in admin_access]):
			return func(*args, **kwargs)
		else:
			flash("The requested page is only available to administrators")
			return redirect(url_for('index'))

	return decorated_function()


def global_admin_required(func):
	@wraps(func)
	def decorated_function(*args, **kwargs):
		if 'access' in session and 'global_admin' in session['access']:
			return func(*args, **kwargs)
		else:
			flash("The requested page is only available to global administrators")
			return redirect(url_for('index'))

	return decorated_function()

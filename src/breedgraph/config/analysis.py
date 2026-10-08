import os

# Auth token for the analysis worker
ANALYSIS_WORKER_AUTH_TOKEN = os.environ.get('ANALYSIS_WORKER_AUTH_TOKEN')
# seconds a leased analysis job may run before it is re-queued
ANALYSIS_JOB_LEASE_SECONDS = int(os.environ.get('ANALYSIS_JOB_LEASE_SECONDS', 60 * 60))

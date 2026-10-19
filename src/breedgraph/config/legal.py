import os

# Append-only log of erased Persons (IDs and times only), replayed after restoring a database backup.
# Keep it outside the database and copy it off the server with the database dumps.
PERSON_ERASURE_LOG_PATH = os.environ.get('PERSON_ERASURE_LOG_PATH', 'instance/person_erasure_log.jsonl')

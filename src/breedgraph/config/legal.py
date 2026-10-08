import os

# The data processing terms accepted when an organisation declares its legal entity.
# The terms document is hosted elsewhere; only its version is recorded with each declaration.
# Declaring a legal entity is refused while no version is configured.
DATA_PROCESSING_TERMS_VERSION = os.environ.get('DATA_PROCESSING_TERMS_VERSION') or None
DATA_PROCESSING_TERMS_URL = os.environ.get('DATA_PROCESSING_TERMS_URL') or None

# Append-only log of erased Persons (IDs and times only), replayed after restoring a database backup.
# Keep it outside the database and copy it off the server with the database dumps.
PERSON_ERASURE_LOG_PATH = os.environ.get('PERSON_ERASURE_LOG_PATH', 'instance/person_erasure_log.jsonl')

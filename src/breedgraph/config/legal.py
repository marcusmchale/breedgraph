import os
from importlib.resources import files

# Append-only log of erased Persons (IDs and times only), replayed after restoring a database backup.
# Keep it outside the database and copy it off the server with the database dumps.
PERSON_ERASURE_LOG_PATH = os.environ.get('PERSON_ERASURE_LOG_PATH', 'instance/person_erasure_log.jsonl')

# The published Terms of Use, which everyone accepts before using BreedGraph (docs/licences.md §4): packaged with the
# API, as markdown, unless a deployment publishes its own. Their draft for review is docs/legal/terms-of-use.md.
TERMS_OF_USE_PATH = os.environ.get('TERMS_OF_USE_PATH') or str(files('breedgraph') / 'legal' / 'terms_of_use.md')

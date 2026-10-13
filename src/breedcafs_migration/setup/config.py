import os
from pathlib import Path

BREEDCAFS_NEO4J_PASSWORD = os.getenv('BREEDCAFS_NEO4J_PASSWORD')
BREEDCAFS_NEO4J_USERNAME = os.getenv('BREEDCAFS_NEO4J_USERNAME', 'neo4j')
BREEDCAFS_DB_NAME = os.getenv('BREEDCAFS_DB_NAME', 'graph.db')
BREEDCAFS_DB_HOST = os.getenv('BREEDCAFS_DB_HOST', 'localhost')
BREEDCAFS_DB_PORT = os.getenv('BREEDCAFS_DB_PORT', '7689')

BREEDCAFS_USER_NAME = os.getenv('BREEDCAFS_USER_NAME', 'BreedCAFS Migration')
BREEDCAFS_TEAM_NAME = os.getenv('BREEDCAFS_TEAM_NAME', 'BreedCAFS Migration')

# The BreedGraph user that runs the migration: an admin, through a heritable affiliation, of the parent team
BREEDCAFS_ADMIN_USER_ID = os.getenv('BREEDCAFS_ADMIN_USER_ID')
# The team the migration team is created under, in an organisation with a declared legal entity (University of Galway)
BREEDCAFS_PARENT_TEAM_ID = os.getenv('BREEDCAFS_PARENT_TEAM_ID')

# The extracted and curated CSV files, and the mappings written by each phase. Not in git.
BREEDCAFS_DATA_DIR = Path(os.getenv('BREEDCAFS_DATA_DIR', Path(__file__).parents[2] / 'data' / 'breedcafs_migration'))

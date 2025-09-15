import pathlib

queries = dict()
for folder in pathlib.Path('src/breedgraph/adapters/neo4j/cypher').iterdir():
    if folder.is_dir():
        queries[folder.name] = dict()
        for cypher_path in folder.glob('*.cypher'):
            queries[folder.name][cypher_path.stem] = pathlib.Path( cypher_path).resolve().read_text()

from src.breedgraph.adapters.neo4j.cypher.query_builders import ontology, controls

__all__ = ['queries', 'ontology', 'controls']


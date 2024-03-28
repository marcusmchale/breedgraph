import pathlib

queries = dict()

for cypher_path in pathlib.Path('src/breedgraph/adapters/neo4j/cypher').glob('*.cypher'):
    queries[cypher_path.stem] = pathlib.Path(cypher_path).read_text()

__all__ = ['queries']

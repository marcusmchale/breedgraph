import pathlib

queries = dict()
for folder in pathlib.Path('src/breedgraph/adapters/neo4j/cypher').iterdir():
    if folder.is_dir():
        for cypher_path in folder.glob('*.cypher'):
            queries[cypher_path.stem] = pathlib.Path( cypher_path).resolve().read_text()

__all__ = ['queries']


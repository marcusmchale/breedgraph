import pathlib
from importlib.resources import files

queries = dict()

cypher_root = files("breedgraph.adapters.neo4j.cypher")

for folder in cypher_root.iterdir():
    if folder.is_dir():
        queries[folder.name] = dict()
        for cypher_path in folder.iterdir():
            if cypher_path.name.endswith(".cypher"):
                queries[folder.name][pathlib.Path(cypher_path.name).stem] = cypher_path.read_text()


from breedgraph.adapters.neo4j.cypher.query_builders import ontology, controls

__all__ = ['queries', 'ontology', 'controls']


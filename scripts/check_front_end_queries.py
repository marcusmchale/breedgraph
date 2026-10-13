#!/usr/bin/env python3
"""
Validate every GraphQL operation in the front end against the current BreedGraph schema.

    python scripts/check_front_end_queries.py ../breedview/src

Each operation is checked with the fragments it uses, wherever they are defined.
Variables are not checked, so input fields the code builds at runtime (e.g. removed inputs) are not caught.
Exits with 1 if any operation has errors.
"""
import sys
from pathlib import Path

from graphql import parse, validate, DocumentNode, FragmentDefinitionNode, OperationDefinitionNode, visit, Visitor
from graphql.language import FragmentSpreadNode

from breedgraph.entrypoints.fastapi.graphql.schema import create_graphql_schema

root = Path(sys.argv[1])
schema = create_graphql_schema()

files = [p for p in root.rglob('*.graphql') if p.name != 'schema.graphql']
fragments, operations = {}, []
for path in files:
    try:
        document = parse(path.read_text())
    except Exception as e:
        print(f"PARSE {path.relative_to(root)}: {e}")
        continue
    for definition in document.definitions:
        if isinstance(definition, FragmentDefinitionNode):
            fragments[definition.name.value] = (path, definition)
        elif isinstance(definition, OperationDefinitionNode):
            operations.append((path, definition))


def spreads(node) -> set[str]:
    names = set()

    class Collect(Visitor):
        def enter_fragment_spread(self, spread: FragmentSpreadNode, *_):
            names.add(spread.name.value)
    visit(node, Collect())
    return names


def needed(node) -> list:
    seen, todo = {}, list(spreads(node))
    while todo:
        name = todo.pop()
        if name in seen or name not in fragments:
            continue
        seen[name] = fragments[name][1]
        todo += spreads(seen[name])
    return list(seen.values())


failures = 0
for path, operation in sorted(operations, key=lambda o: str(o[0])):
    errors = validate(schema, DocumentNode(definitions=[operation, *needed(operation)]))
    if errors:
        failures += 1
        name = operation.name.value if operation.name else '(anonymous)'
        print(f"\n{path.relative_to(root)} :: {name}")
        for error in errors:
            print(f"  - {error.message}")

print(f"\n{len(operations)} operations in {len(files)} files, {failures} with errors")
sys.exit(1 if failures else 0)

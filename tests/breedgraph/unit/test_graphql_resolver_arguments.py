"""Every query and mutation resolver accepts the arguments its schema field declares, under their snake_case names.

A mismatch only fails when the operation is called (e.g. `programsDeleteGrouping(id:)` reaching a resolver that took
`grouping_id`), so check them all against the executable schema. Needs no database.
"""
import inspect
import re

import pytest

from breedgraph.entrypoints.fastapi.graphql.schema import create_graphql_schema

schema = create_graphql_schema()


def snake(name: str) -> str:
    return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()


fields = [
    (type_name, name, field)
    for type_name in ('Query', 'Mutation')
    for name, field in schema.type_map[type_name].fields.items()
    if field.resolve is not None
]


@pytest.mark.parametrize('type_name, name, field', fields, ids=[f'{t}.{n}' for t, n, _ in fields])
def test_resolver_takes_the_field_arguments(type_name, name, field):
    # the resolver itself, under its decorators; its first two parameters are the parent object and info
    parameters = list(inspect.signature(inspect.unwrap(field.resolve)).parameters.values())[2:]
    if any(p.kind == p.VAR_KEYWORD for p in parameters):
        return
    names = {p.name for p in parameters}
    arguments = {snake(a) for a in field.args}
    required = {p.name for p in parameters if p.default is p.empty and p.kind != p.VAR_POSITIONAL}
    assert arguments <= names, f"{type_name}.{name} declares {sorted(arguments - names)}, which the resolver doesn't take"
    assert required <= arguments, f"{type_name}.{name}'s resolver requires {sorted(required - arguments)}, which the field doesn't declare"

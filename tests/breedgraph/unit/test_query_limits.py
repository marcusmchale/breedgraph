"""
The API answers queries up to its limits (config/queries.py) and refuses larger ones before running them: too deep, too
many fields, too many lists nested, or introspection nesting more lists than the standard introspection query. Checked
against the executable schema, as the endpoint validates. Needs no database.
"""
import time

from graphql import parse, validate, get_introspection_query, specified_rules

from breedgraph.entrypoints.fastapi.graphql.schema import create_graphql_schema
from breedgraph.entrypoints.fastapi.graphql.query_limits import (
    QueryLimits, QUERY_TOO_LARGE, MAX_QUERY_DEPTH, MAX_QUERY_FIELDS, MAX_QUERY_LISTS
)

schema = create_graphql_schema()


def refusals(query: str, rules=(QueryLimits,)) -> list[str]:
    errors = validate(schema, parse(query), rules=list(rules))
    assert all(error.extensions.get('code') == QUERY_TOO_LARGE for error in errors), errors
    return [error.message for error in errors]


def nested(field: str, levels: int, leaf: str = 'id') -> str:
    return f'{field} {{ ' * levels + leaf + ' }' * levels


def locations(selection: str) -> str:
    """locationsLocations' result is a list of locations, each with a parent and a list of children"""
    return f'{{ locationsLocations(ids: ["1"]) {{ result {{ {selection} }} }} }}'


def test_the_standard_introspection_query_is_answered():
    assert refusals(get_introspection_query(descriptions=True)) == []


def test_introspection_nesting_more_lists_than_the_standard_query_is_refused():
    # types, their fields, and the fields of those fields' types, twice over: a fourth list, over every type
    deeper = '{ __schema { types { fields { type { fields { type { fields { name } } } } } } } }'
    assert refusals(deeper) == ["The query's introspection nests more than 3 lists, as the standard introspection query does"]
    assert refusals('{ __schema { types { fields { args { name } } } } }') == []


def test_lists_nest_up_to_the_limit():
    # result is the first list, each children another
    assert refusals(locations(nested('children', MAX_QUERY_LISTS - 1))) == []
    assert refusals(locations(nested('children', MAX_QUERY_LISTS))) == [
        f"The query nests more than {MAX_QUERY_LISTS} lists, the most the API answers"
    ]


def test_fields_nest_up_to_the_limit():
    # the root field and result are the first two levels, each parent one more
    assert refusals(locations(nested('parent', MAX_QUERY_DEPTH - 3))) == []
    assert refusals(locations(nested('parent', MAX_QUERY_DEPTH - 2))) == [
        f"The query nests fields more than {MAX_QUERY_DEPTH} deep, the most the API answers"
    ]


def test_aliases_count_as_the_fields_they_repeat():
    aliased = lambda n: '{ ' + ' '.join(f'a{i}: __typename' for i in range(n)) + ' }'
    assert refusals(aliased(MAX_QUERY_FIELDS)) == []
    assert refusals(aliased(MAX_QUERY_FIELDS + 1)) == [
        f"The query asks for more than {MAX_QUERY_FIELDS} fields, the most the API answers"
    ]


def test_fragments_count_each_time_they_are_spread_and_cost_no_work_past_the_limit():
    # each fragment spreads the next twice: 2^40 fields, as written in a few lines
    fragments = '\n'.join(
        f'fragment F{i} on Location {{ ...F{i + 1} ...F{i + 1} }}' for i in range(40)
    ) + '\nfragment F40 on Location { id }'
    started = time.monotonic()
    assert refusals(locations('...F0') + '\n' + fragments) == [
        f"The query asks for more than {MAX_QUERY_FIELDS} fields, the most the API answers"
    ]
    assert time.monotonic() - started < 1


def test_a_fragment_cycle_is_left_to_the_standard_rules():
    cycle = locations('...A') + '\nfragment A on Location { children { ...A } }'
    assert refusals(cycle) == []
    assert any('within itself' in error.message for error in validate(schema, parse(cycle), specified_rules))

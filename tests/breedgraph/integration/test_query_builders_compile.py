"""
Every query the query builders compose compiles: each variant is planned with EXPLAIN, which neither reads nor writes
data, so syntax and scoping errors in the composed text show here rather than in the first request that reaches them.

Needs a running Neo4j, with credentials in the environment or in instance/private.breedgraph.env. The autouse
fixture under tests/breedgraph flushes the database, so to check against a database you want to keep, run this
module alone with: python -m pytest --noconftest -p no:cacheprovider tests/breedgraph/integration/test_query_builders_compile.py
"""
import os
import re
from itertools import combinations
from pathlib import Path

import pytest
from neo4j import GraphDatabase

from breedgraph.domain.model.controls import ControlledModelLabel
from breedgraph.adapters.neo4j.cypher.query_builders import (
    layout_trees, unit_graphs, unit_positions, controls, datasets, germplasm, people, programs, references, location_trees
)

ENV_FILE = Path(__file__).parents[3] / 'instance' / 'private.breedgraph.env'


def _load_env():
    if 'NEO4J_USERNAME' in os.environ or not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _summary_field_sets():
    """Every single field, every field, none, and the fields the front end asks for together"""
    fields = sorted(datasets.SUMMARY_FIELDS)
    sets = [frozenset(), frozenset(fields)] + [frozenset(combo) for combo in combinations(fields, 1)]
    sets += [frozenset({'record_count', 'start', 'end'}), frozenset(datasets.UNIT_FIELDS)]
    return sets


QUERIES = {
    'layout_trees.read_layouts': layout_trees.read_layouts(),
    'layout_trees.read_layout_trees': layout_trees.read_layout_trees(),
    'unit_graphs.read_units': unit_graphs.read_units(),
    'unit_graphs.read_unit_graph_roots': unit_graphs.read_unit_graph_roots(),
    'unit_graphs.read_unit_names': unit_graphs.read_unit_names(),
    'unit_graphs.read_descendants_by_subject': unit_graphs.read_descendants_by_subject(),
    'unit_graphs.read_unit_ancestors': unit_graphs.read_unit_ancestors(),
    **{f'unit_graphs.read_unit_arrivals(related={related})': unit_graphs.read_unit_arrivals(related) for related in (False, True)},
    **{f'unit_graphs.read_arrival_units(related={related})': unit_graphs.read_arrival_units(related) for related in (False, True)},
    **{f'unit_graphs.read_arrival_unit_ids(related={related})': unit_graphs.read_arrival_unit_ids(related) for related in (False, True)},
    'unit_graphs.read_arrival_units_by_subject': unit_graphs.read_arrival_units_by_subject(),
    'unit_graphs.read_inherited_germplasm': unit_graphs.read_inherited_germplasm(),
    'unit_positions.read_positions_locked': unit_positions.read_positions_locked(),
    'unit_positions.create_positions': unit_positions.create_positions(),
    'unit_positions.change_positions': unit_positions.change_positions(),
    'unit_positions.delete_positions': unit_positions.delete_positions(),
    'location_trees.read_locations': location_trees.read_locations(),
    'location_trees.read_location_trees': location_trees.read_location_trees(),
    'location_trees.read_locations_by_type': location_trees.read_locations_by_type(),
    'location_trees.read_descendants_by_type': location_trees.read_descendants_by_type(),
    'location_trees.search_locations': location_trees.search_locations(),
    'programs.read_programs': programs.read_programs(),
    **{f'programs.read_program({by})': programs.read_program(by) for by in ('program', 'trial', 'study')},
    **{f'programs.read_trial({by})': programs.read_trial(by) for by in ('trial', 'study')},
    'programs.read_study': programs.read_study(),
    'germplasm.read_entries': germplasm.read_entries(),
    'germplasm.read_all_entries': germplasm.read_all_entries(),
    'germplasm.read_crops': germplasm.read_crops(),
    'germplasm.read_descendant_ids': germplasm.read_descendant_ids(),
    'people.read_people': people.read_people(),
    'people.search_people': people.search_people(),
    'people.read_people_by_user': people.read_people_by_user(),
    'references.read_references': references.read_references(),
    'references.search_references': references.search_references(),
    'references.read_file_reference': references.read_file_reference(),
    'datasets.read_datasets': datasets.read_datasets(),
    'datasets.read_records': datasets.read_records(),
    'datasets.read_records(exact units)': datasets.read_records(include_below=False),
    'datasets.count_records': datasets.count_records(),
    'datasets.read_unit_ids': datasets.read_unit_ids(),
    'datasets.read_unit_level': datasets.read_unit_level(),
    'datasets.read_units_by_subject': datasets.read_units_by_subject(),
    'datasets.read_places': datasets.read_places(),
    **{f'datasets.dataset_summaries({sorted(fields)})': datasets.dataset_summaries(fields) for fields in _summary_field_sets()},
    **{f'datasets.dataset_unit_summaries({sorted(fields)})': datasets.dataset_unit_summaries(fields) for fields in _summary_field_sets()},
    **{
        f'controls.{builder.__name__}({label.name})': builder(label)
        for label in ControlledModelLabel
        for builder in (
            controls.set_controls, controls.add_controls, controls.end_controls, controls.record_writes,
            controls.get_controllers, controls.read_controllers, controls.read_controlled_entities, controls.scope_entity_ids
        )
    },
    'controls.read_controlled_counts': controls.read_controlled_counts(),
    'controls.read_controlled_unit_roots': controls.read_controlled_unit_roots(),
    'controls.read_controlled_unit_children': controls.read_controlled_unit_children(),
    'controls.scope_entity_ids(UNIT, below_units)': controls.scope_entity_ids(ControlledModelLabel.UNIT, below_units=True),
}


@pytest.fixture(scope='module')
def session():
    _load_env()
    if 'NEO4J_USERNAME' not in os.environ:
        pytest.skip('no Neo4j credentials')
    from breedgraph.config import get_bolt_url, get_graphdb_auth, DATABASE_NAME
    driver = GraphDatabase.driver(get_bolt_url(), auth=get_graphdb_auth())
    with driver.session(database=DATABASE_NAME) as session:
        yield session
    driver.close()


@pytest.mark.parametrize('name', list(QUERIES))
def test_query_compiles(session, name):
    query = QUERIES[name]
    parameters = {parameter: None for parameter in set(re.findall(r'\$(\w+)', query))}
    session.run('EXPLAIN ' + query, **parameters).consume()

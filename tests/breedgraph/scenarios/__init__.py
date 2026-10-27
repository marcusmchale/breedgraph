"""
The scenario builders, imported when first named (PEP 562), so that importing a module of this package alone, such as
authorisation_manager or demo.story, which scripts/set_demo_accounts.py runs on the demonstration site, doesn't import
the builders and the test utilities they use, whose faker is a test dependency only.
"""
from importlib import import_module

_BUILDERS = {
    'AccountBuilder': 'account_builder',
    'OntologyBuilder': 'ontology_builder',
    'LocationTreeBuilder': 'location_tree_builder',
    'ProgramBuilder': 'program_builder',
    'UnitGraphBuilder': 'unit_graph_builder',
    'PersonBuilder': 'person_builder',
    'TeamTreeBuilder': 'team_tree_builder',
    'ReferenceBuilder': 'reference_builder',
    'LayoutTreeBuilder': 'layout_tree_builder',
    'DatasetBuilder': 'dataset_builder',
}

__all__ = list(_BUILDERS)


def __getattr__(name):
    if name in _BUILDERS:
        builder = getattr(import_module(f'.{_BUILDERS[name]}', __name__), name)
        globals()[name] = builder
        return builder
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(set(globals()) | set(_BUILDERS))

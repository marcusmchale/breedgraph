"""
The demonstration database's manifest: what the guide, its recordings and the hosted demo need to find their way in a
build, by the story's keys and names (ids change when the story does, and recordings must not depend on them). It
holds the accounts' passwords, so it is private: written readable by its owner only, and never committed.

- accounts, teams and every entity by key, with its id, label, name (added from the database), controls, and who can
  read it (VIEWERS); Persons also say how each viewer sees them;
- the ontology's entries by kind and key, and its versions;
- the layouts, groupings and units, the stored files, and the files the guide uploads (uploads);
- for each chain of the guide's workflows, what it starts from, what it enters and what must not exist yet (chains);
  and for the other workflows, what they work on (workflows).
"""
from pathlib import Path
from typing import Dict

from .builder import DemoScenario, VIEWERS, coordinates
from .layout import plots, selection_plant_name
from .story import (
    ACCOUNTS, DATASETS, GERMPLASM, GRAIN_ARRIVED, GUIDE, HILL_FIELD, MAIL_DOMAIN, PARTNER_LICENCE, PEOPLE, PLACES,
    PLANNED_2026, STORY_VERSION, TEAMS, TYPO, Person
)
from . import values


def _accounts(scenario: DemoScenario, passwords: Dict[str, str]) -> dict:
    people = {person.account: key for key, person in PEOPLE.items() if person.account}
    return {
        key: {
            'user_id': scenario[key],
            'username': key,
            'fullname': account.fullname,
            'email': account.email,
            'password': passwords[key],
            'job': account.job,
            'ontology_role': account.ontology_role.name,
            'person': people.get(key),
            'write_team': account.write_team,
            'affiliations': {team: sorted(access.name for access in accesses)
                             for team, accesses in (account.affiliations or {}).items()},
        }
        for key, account in ACCOUNTS.items() if not account.deleted
    }


def _entities(scenario: DemoScenario) -> dict:
    entities = {}
    for key, label in scenario.labels.items():
        team, release = scenario.controls[key]
        entity = {
            'id': scenario[key],
            'label': label.value,
            'team': team,
            'release': release.name,
            'readable_by': [viewer for viewer in VIEWERS if scenario.readable(viewer, key)],
        }
        if isinstance(PEOPLE.get(key), Person):
            entity['person_views'] = {viewer: scenario.person_view(viewer, key) for viewer in VIEWERS}
            entity['erased'] = PEOPLE[key].erased
        entities[key] = entity
    return entities


def _this_season(scenario: DemoScenario) -> dict:
    planned = values.planned_2026()
    plot_name, concept = TYPO
    typed = dict(planned[concept])[plot_name]
    return {
        'actors': {'set_up': 'bridget', 'record': 'theo', 'check': 'theo', 'analyse': 'bridget'},
        'programme': 'programme',
        'trial': GUIDE['trial_2026'],
        'study': GUIDE['study_2026'],
        'location': 'long_meadow',
        'area': scenario.units["Long Meadow 2026 trial area"],
        'plots': [
            {
                'name': plot.name, 'unit_id': scenario.units[plot.name], 'block': plot.block, 'row': plot.row,
                'column': plot.column, 'germplasm': plot.entry, 'nitrogen': plot.nitrogen,
            }
            for plot in plots('lm26')
        ],
        'observations': {
            key: {
                'concept_id': scenario.ontology['variables' if key != 'nitrogen_rate' else 'factors'][key],
                'start': PLANNED_2026[key],
                'values': [[name, value] for name, value in planned[key]],
                # as pasted from a spreadsheet's column, in plot order
                'paste': '\n'.join(value for _, value in planned[key]),
            }
            for key in planned
        },
        'typo': {'plot': plot_name, 'concept': concept, 'typed': typed, 'correct': values.correct_2026(concept, plot_name)},
        'absent': {'trials': [GUIDE['trial_2026']['name']], 'studies': [GUIDE['study_2026']['name']]},
    }


def demo_manifest(
        scenario: DemoScenario,
        passwords: Dict[str, str],
        files_dir: Path,
        uploads_dir: Path,
        built_at: str,
        breedgraph_commit: str | None
) -> dict:
    s = scenario
    partner_licence_name, partner_licence_file = PARTNER_LICENCE
    return {
        'kind': 'demo',
        'description': (
            "The BreedGraph demonstration database: fictional winter wheat trials in Ireland "
            "(scripts/build_demo_database.py, docs/demo-database.md)"
        ),
        'story_version': STORY_VERSION,
        'built_at': built_at,
        'breedgraph_commit': breedgraph_commit,
        'accounts': _accounts(s, passwords),
        'deleted_accounts': {key: {'user_id': s[key]} for key, account in ACCOUNTS.items() if account.deleted},
        'teams': {key: {'id': s[key], 'name': team.name, 'parent': team.parent} for key, team in TEAMS.items()},
        'viewers': list(VIEWERS),
        'entities': _entities(s),
        'ontology': {
            'versions': [{'version': version, 'comment': comment} for version, comment in s.commits],
            'entries': s.ontology,
        },
        'layouts': s.layouts,
        'groupings': s.groupings,
        'units': dict(sorted(s.units.items())),
        'records': s.records,
        'files': {
            key: {
                'reference_id': s[key], 'file_id': file_id, 'filename': filename, 'path': str(files_dir / file_id)
            }
            for key, (file_id, _, filename) in s.files.items()
        },
        'uploads': {
            'partner_licence': {
                'description': partner_licence_name, 'path': str(uploads_dir / partner_licence_file)
            },
            'nir_block_2': [
                {'sample': f"{plot.name} grain", 'path': str(uploads_dir / values.nir_filename(plot))}
                for plot in values.nir_plots(block=2)
            ],
        },
        'chains': {
            'joining': {
                'inviter': 'bridget',
                'invitee': {**GUIDE['invitee'], 'email': f"nina.newcomer@{MAIL_DOMAIN}"},
                'offer': {
                    'team': GUIDE['invitation_offer']['team'],
                    'accesses': [access.name for access in GUIDE['invitation_offer']['accesses']],
                    'person': GUIDE['invitation_offer']['person'],
                },
                'request': {
                    'team': GUIDE['affiliation_request']['team'],
                    'access': GUIDE['affiliation_request']['access'].name,
                    'approver': GUIDE['affiliation_request']['approver'],
                    'heritable': GUIDE['affiliation_request']['heritable'],
                },
                'absent': {'accounts': [GUIDE['invitee']['username']]},
            },
            'this_season': _this_season(s),
            'next_season': {
                'ontology': {**GUIDE['flag_leaf'], 'scale_id': s.ontology['scales'][GUIDE['flag_leaf']['scale']]},
                'field': {
                    'name': HILL_FIELD.name, 'parent': HILL_FIELD.parent, 'code': HILL_FIELD.code,
                    'description': HILL_FIELD.description, 'boundary': coordinates(HILL_FIELD),
                },
                'layout': GUIDE['hill_field_layout'],
                'area': GUIDE['hill_field_area'],
                'cross': {'name': "EPB 26-X01", 'maternal': 'epb_25_s03', 'paternal': 'epb_21_022'},
                'absent': {'locations': [HILL_FIELD.name], 'germplasm': ["EPB 26-X01"]},
            },
        },
        'workflows': {
            'visitor_tour': {
                'programme': 'programme', 'trial': 'trial_2024', 'study': 'study_2024', 'licence': 'open_licence',
                'location': 'long_meadow', 'private_location': 'seed_field', 'germplasm': 'epb_19_031',
            },
            'sharing': {
                'study': 'study_2025', 'trial': 'trial_2025', 'field_plan': 'plan_2025',
                'datasets': [key for key, plan in DATASETS.items() if plan.study == 'study_2025'],
                'sharer': 'bridget', 'releaser': 'dara', 'partner': 'petra', 'licence_upload': 'partner_licence',
            },
            'people': {
                'new_person': GUIDE['new_person'], 'claim': {'person': 'person_petra', 'claimant': 'petra', 'approver': 'bridget'},
                'restricted_to_partner': 'person_fergus', 'contact': 'person_bridget',
            },
            'lab': {
                'arrival': {'location': 'laboratory', 'start': GRAIN_ARRIVED, 'units': len(plots('nf25'))},
                'freezer': 'freezer', 'rack': 'freezer_rack', 'glasshouse': 'glasshouse', 'benches': 'benches',
                'selection': {'plant': selection_plant_name(), 'germplasm': 'epb_25_s03'},
            },
            'bulk_control': {
                'team': GUIDE['transfer']['team'], 'germplasm': list(GUIDE['transfer']['germplasm']),
                'to': GUIDE['transfer']['to'], 'offerer': 'bridget', 'accepter': 'petra',
            },
            'ontology': {'role_request': 'theo', 'deprecate': GUIDE['deprecate'], 'editor': 'dara'},
            'data_files': {'study': 'study_lab_2025', 'concept': 'nir_spectrum', 'uploads': 'nir_block_2', 'writer': 'lena'},
        },
        'germplasm_names': {key: variety.name for key, variety in GERMPLASM.items()},
        'place_names': {key: place.name for key, place in PLACES.items()},
    }


def uploads(uploads_dir: Path) -> Dict[str, bytes]:
    """The files the guide uploads, by path: the partner licence and the spectra of block 2"""
    _, licence_file = PARTNER_LICENCE
    files = {uploads_dir / licence_file: values.partner_licence_pdf()}
    files.update({uploads_dir / values.nir_filename(plot): content for plot, content in values.nir_uploads()})
    return files

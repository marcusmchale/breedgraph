"""
The demonstration database's story (tests/breedgraph/scenarios/demo/), without a database: its names are English and
unique where the model needs them to be, every key it refers to exists, its releases are ones the API allows, its
trials are laid out as randomised complete blocks, its places sit inside their sites, and its values give the guide's
analyses something to find, with the one typo the guide corrects. Runs with --noconftest.
"""
import math
import re
from datetime import date
from pathlib import Path

import numpy as np
import pytest

from breedgraph.domain.model.controls import ReadRelease

from tests.breedgraph.scenarios.demo import story, values
from tests.breedgraph.scenarios.demo.builder import coordinates, ORIGINS, SITE_METRES_PER_DEGREE
from tests.breedgraph.scenarios.demo.layout import plots, selection_plot, selection_plant_name
from tests.breedgraph.scenarios.demo.story import (
    ACCOUNTS, CONDITIONS, CONTROL_METHODS, DATASETS, DESIGNS, FACTORS, GERMPLASM, GUIDE, HILL_FIELD, LAB_LAYOUTS,
    LAYOUT_TYPES, LOCATION_TYPES, OBSERVATION_METHODS, PEOPLE, PLACES, PLANS, PROGRAMMES, RECORD_GROUP_TYPES,
    REFERENCES, SCALES, SITE_BOXES, STUDIES, SUBJECTS, TEAMS, TRAITS, TRIALS, TYPO, VARIABLES
)

DEMO_PACKAGE = Path(story.__file__).parent

# Plain printable ASCII: the guide is in English, and the PDFs the build makes take ASCII only
ENGLISH = re.compile(r"^[A-Za-z0-9 ,.;:'()%/&+?!-]+$")


def all_names():
    yield from (team.name for team in TEAMS.values())
    yield from (account.fullname for account in ACCOUNTS.values())
    yield from (person.name for person in PEOPLE.values())
    yield from (place.name for place in [*PLACES.values(), HILL_FIELD])
    yield from (variety.name for variety in GERMPLASM.values())
    for entries in (LOCATION_TYPES, LAYOUT_TYPES, DESIGNS, RECORD_GROUP_TYPES, SUBJECTS, OBSERVATION_METHODS, SCALES,
                    TRAITS, VARIABLES, CONDITIONS, CONTROL_METHODS, FACTORS):
        yield from (entry[0] for entry in entries.values())
    yield from (category for scale in SCALES.values() for category, _ in scale[4])
    for programmes in (PROGRAMMES, TRIALS, STUDIES):
        yield from (programme.name for programme in programmes.values())
    yield from (reference[1] for reference in REFERENCES.values())
    yield from (plot.name for plan in PLANS for plot in plots(plan))


def test_names_are_plain_english():
    for name in all_names():
        assert ENGLISH.match(name), name


def test_addresses_are_reserved_for_examples():
    for account in ACCOUNTS.values():
        assert account.email.endswith('@example.org'), account.email


def test_names_are_unique_where_the_model_needs_them():
    germplasm_names = [name.casefold() for variety in GERMPLASM.values() for name in (variety.name, *variety.synonyms)]
    assert len(germplasm_names) == len(set(germplasm_names))
    for entries in (LOCATION_TYPES, LAYOUT_TYPES, DESIGNS, RECORD_GROUP_TYPES, SUBJECTS, OBSERVATION_METHODS, SCALES,
                    TRAITS, VARIABLES, CONDITIONS, CONTROL_METHODS, FACTORS):
        names = [entry[0].casefold() for entry in entries.values()]
        assert len(names) == len(set(names)), names
    categories = [category.casefold() for scale in SCALES.values() for category, _ in scale[4]]
    assert len(categories) == len(set(categories))
    for programmes in (PROGRAMMES, TRIALS, STUDIES):
        assert len({p.name for p in programmes.values()}) == len(programmes)
    assert len({account.fullname for account in ACCOUNTS.values()}) == len(ACCOUNTS)
    unit_names = [plot.name for plan in PLANS for plot in plots(plan)]
    assert len(unit_names) == len(set(unit_names))


def test_keys_resolve():
    for key, account in ACCOUNTS.items():
        assert set(account.affiliations) <= set(TEAMS), key
        assert account.write_team in account.affiliations and story.WRITE in account.affiliations[account.write_team]
    for key, person in PEOPLE.items():
        assert person.team in TEAMS and set(person.teams) <= set(TEAMS), key
        assert person.account in (None, *ACCOUNTS) and person.claimant in (None, *ACCOUNTS), key
    for key, place in PLACES.items():
        assert place.parent in (None, *PLACES), key
        assert place.type in (None, *LOCATION_TYPES), key
    for key, variety in GERMPLASM.items():
        assert {source for source, _ in variety.sources} <= set(GERMPLASM), key
        assert set(variety.control_methods) <= set(CONTROL_METHODS), key
        assert variety.origin in (None, *PLACES), key
    for key, plan in PLANS.items():
        assert plan.field in PLACES and set(plan.entries) <= set(GERMPLASM), key
    for key, trial in TRIALS.items():
        assert trial.programme in PROGRAMMES, key
    for key, study in STUDIES.items():
        assert study.trial in TRIALS and study.design in (None, *DESIGNS), key
        assert study.licence in (None, *REFERENCES) and set(study.references) <= set(REFERENCES), key
        assert {grouping.type for grouping in study.groupings} <= set(RECORD_GROUP_TYPES), key
    for key, plan in DATASETS.items():
        assert plan.study in STUDIES and plan.concept in {**VARIABLES, **FACTORS} and plan.writer in ACCOUNTS, key
        assert {person for person, _ in plan.contributions} <= set(PEOPLE), key
    for programme in [*PROGRAMMES.values(), *TRIALS.values()]:
        assert {person for person, _ in programme.contributions} <= set(PEOPLE)
    for name, type_key, location, _, team, _ in LAB_LAYOUTS.values():
        assert type_key in LAYOUT_TYPES and location in PLACES and team in TEAMS, name
    for key, (_, trait, method, scale, _) in VARIABLES.items():
        assert trait in TRAITS and method in OBSERVATION_METHODS and scale in SCALES, key
    for key, (_, condition, method, scale, _) in FACTORS.items():
        assert condition in CONDITIONS and method in CONTROL_METHODS and scale in SCALES, key
    assert set(GUIDE['transfer']['germplasm']) <= set(GERMPLASM)


def test_releases_are_ones_the_api_allows():
    # Persons are released at most to registered users; the country is public
    assert all(person.release <= ReadRelease.REGISTERED for person in PEOPLE.values())
    assert PLACES['ireland'].release == ReadRelease.PUBLIC
    # a contact is linked to an account and released to registered users (the programs handler's _verify_contacts)
    for programme in [*PROGRAMMES.values(), *TRIALS.values()]:
        for contact in programme.contacts:
            assert PEOPLE[contact].account is not None and PEOPLE[contact].release == ReadRelease.REGISTERED
    # a study's licence is released at least as widely as the study and its datasets
    for key, study in STUDIES.items():
        if study.licence:
            licence_release = REFERENCES[study.licence][3]
            assert licence_release >= study.release
            assert all(plan.release <= licence_release for plan in DATASETS.values() if plan.study == key)


def test_each_block_holds_each_treatment_once():
    for key, plan in PLANS.items():
        laid_out = plots(key)
        assert len(laid_out) == plan.blocks * len(plan.treatments)
        for block in range(1, plan.blocks + 1):
            treatments = sorted((p.entry, p.nitrogen or 0) for p in laid_out if p.block == block)
            assert treatments == sorted((entry, rate or 0) for entry, rate in plan.treatments), (key, block)
        # the order differs between blocks, as a randomisation would
        orders = [[(p.entry, p.nitrogen) for p in laid_out if p.block == block] for block in range(1, plan.blocks + 1)]
        assert len({tuple(order) for order in orders}) == plan.blocks, key
        assert all(1 <= p.row <= plan.rows and 1 <= p.column <= plan.columns for p in laid_out)


def test_the_selection_is_on_its_parent_line():
    plot = selection_plot()
    assert (plot.trial, plot.entry, plot.nitrogen, plot.block) == story.SELECTION
    assert selection_plant_name() == f"{plot.name} plant 1"


@pytest.mark.parametrize('place', [*PLACES.values(), HILL_FIELD], ids=lambda place: place.name)
def test_places_are_inside_their_sites(place):
    (west, south), (east, north) = SITE_BOXES[place.site]
    for offset_east, offset_north in place.shape:
        assert west <= offset_east <= east and south <= offset_north <= north, place.name
    latitude, longitude = ORIGINS[place.site]
    for point in coordinates(place):
        assert abs(point['latitude'] - latitude) * SITE_METRES_PER_DEGREE < 1000
        metres_east = (point['longitude'] - longitude) * SITE_METRES_PER_DEGREE * math.cos(math.radians(latitude))
        assert abs(metres_east) < 1000


def test_values_are_plausible():
    for key, plan in DATASETS.items():
        if plan.units != 'plots':
            continue
        trial = {'study_2024': 'lm24', 'study_2025': 'nf25'}[plan.study]
        for plot_name, value in values.plot_values(trial, plan.concept):
            if plan.concept == 'height':
                assert 60 <= int(value) <= 110, (plot_name, value)
            elif plan.concept == 'yield':
                assert 6 <= float(value) <= 13, (plot_name, value)
            elif plan.concept == 'septoria':
                assert value in {name for name, _ in story.SEPTORIA_CATEGORIES}
            elif plan.concept == 'heading':
                heading = date.fromisoformat(value)
                assert date(heading.year, 5, 20) <= heading <= date(heading.year, 6, 30), (plot_name, value)
    for plot in plots('nf25'):
        assert all(35 <= float(weight) <= 55 for weight in values.grain_weights(plot))
        assert 9 <= float(values.protein(plot)) <= 15
    assert values.nir_spectrum(plots('nf25')[0]).startswith(b"wavelength_nm,reflectance\n")


def test_one_typo_in_the_planned_values_and_it_stands_out():
    planned = values.planned_2026()
    plot_name, concept = TYPO
    for key, entered in planned.items():
        correct = values.plot_values('lm26', key)
        differences = [(name, value, right) for (name, value), (_, right) in zip(entered, correct) if value != right]
        assert differences == ([(plot_name, values.typed(values.correct_2026(key, plot_name)),
                                 values.correct_2026(key, plot_name))] if key == concept else [])
    heights = np.array([float(value) for _, value in planned[concept]])
    typo = [name for name, _ in planned[concept]].index(plot_name)
    others = np.delete(heights, typo)
    assert abs(heights[typo] - others.mean()) / others.std() > 10
    assert all(abs(others - others.mean()) / others.std() < 4)


def f_statistic(y, terms, tested):
    """The F statistic of one term in a linear model of the others (block, entry, nitrogen as factors), by least squares"""
    def design(names):
        columns = [np.ones(len(y))]
        for name in names:
            levels = sorted(set(terms[name]))
            columns += [np.array([value == level for value in terms[name]], dtype=float) for level in levels[1:]]
        return np.column_stack(columns)

    def sse(names):
        x = design(names)
        residual = y - x @ np.linalg.lstsq(x, y, rcond=None)[0]
        return residual @ residual, x.shape[1]

    full_sse, full_parameters = sse(list(terms))
    reduced_sse, reduced_parameters = sse([name for name in terms if name != tested])
    return ((reduced_sse - full_sse) / (full_parameters - reduced_parameters)) / (full_sse / (len(y) - full_parameters))


@pytest.mark.parametrize('trial, concept, value', [
    ('lm26', 'height', lambda p: float(values.height(p))),
    ('nf25', 'yield', lambda p: float(values.grain_yield(p))),
    ('nf25', 'height', lambda p: float(values.height(p))),
])
def test_entries_and_nitrogen_rates_differ(trial, concept, value):
    """
    What the guide's ANOVA finds: both entry and nitrogen rate, beyond chance. With these degrees of freedom (5 or 7 for
    entries, 1 for nitrogen, and 27 to 38 for the error), F over 4 and over 12 are both below p = 0.005.
    """
    laid_out = plots(trial)
    y = np.array([value(p) for p in laid_out])
    terms = {
        'block': [p.block for p in laid_out],
        'entry': [p.entry for p in laid_out],
        'nitrogen': [p.nitrogen for p in laid_out],
    }
    assert f_statistic(y, terms, 'nitrogen') > 12, concept
    assert f_statistic(y, terms, 'entry') > 4, concept


def test_nothing_comes_from_real_data():
    for source in DEMO_PACKAGE.glob('*.py'):
        text = source.read_text()
        assert 'breedcafs' not in text.casefold(), source.name
        assert 'src/data' not in text, source.name

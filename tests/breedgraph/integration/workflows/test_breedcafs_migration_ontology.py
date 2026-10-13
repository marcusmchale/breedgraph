import csv
import shutil

import pytest
import pytest_asyncio

from breedgraph.domain.model.accounts import OntologyRole
from breedgraph.domain.model.ontology import OntologyEntryLabel, OntologyRelationshipLabel, ScaleType

from breedcafs_migration import ontology
from breedcafs_migration.ontology import prepare_breedcafs_ontology
from breedcafs_migration.setup.config import BREEDCAFS_DATA_DIR

from tests.breedgraph.scenarios.account_builder import AccountBuilder

CURATED_COLUMNS = [
    'type', 'name', 'description', 'format', 'Factor', 'Condition', 'ControlMethod', 'ControlMethodType',
    'ControlMethodDescription', 'Variable', 'Trait', 'Trait Description', 'ObservationMethod', 'ObservationMethodType',
    'ObservationMethodDescription', 'Scale', 'Scale Description', 'ScaleType', 'categories', 'terms', 'subjects',
    'Apparatus'
]

# As exported: values wrapped in extra quotes, terms with typographic quotes
CURATED_ROWS = [
    {
        'type': '"Trait"', 'name': '"Total Boron"', 'description': '"Total boron content (µg/g)"', 'format': '"numeric"',
        'Variable': 'Boron (µg/g)', 'Trait': 'Boron', 'Trait Description': 'Concentration of Boron',
        'ObservationMethod': 'Mineral Analysis', 'ObservationMethodType': 'MEASUREMENT', 'Scale': 'µg/g',
        'ScaleType': 'NUMERICAL', 'categories': 'null', 'terms': '[“Elements”]', 'subjects': '["Sample"]'
    },
    {
        'type': '"Trait"', 'name': '"Tree rust symptoms"', 'format': '"categorical"',
        'Variable': 'Rust Defoliation Classes', 'Trait': 'Rust Symptoms', 'ObservationMethod': 'Proportion of defoliation',
        'ObservationMethodType': 'ESTIMATION', 'Scale': 'Defoliation Scale', 'ScaleType': '',
        'categories': '"0 / 1 / 2"', 'terms': '["Phenotype"]', 'subjects': '["Tree"]'
    },
    {
        'type': '"Property"', 'name': '"Set planting date"', 'format': '"date"', 'Factor': 'Planting Date',
        'Condition': 'Planting Time-point', 'ControlMethod': 'Schedule', 'ControlMethodType': 'MANAGEMENT',
        'Scale': 'Datetime', 'ScaleType': 'Date', 'categories': 'null', 'terms': '[“Plant Management”]', 'subjects': '["Tree"]'
    },
    # One input measured with two instruments
    *[
        {
            'type': '"Trait"', 'name': '"Fᵥ / Fₘ"', 'format': '"numeric"', 'Variable': f'Fv/Fm ({apparatus})',
            'Trait': 'Fv/Fm', 'ObservationMethod': apparatus, 'ObservationMethodType': 'MEASUREMENT', 'Scale': 'Ratio',
            'ScaleType': 'NUMERICAL', 'categories': 'null', 'terms': '[“Photosynthesis”]', 'subjects': '["Sample"]',
            'Apparatus': apparatus
        }
        for apparatus in ('PocketPEA', 'MiniPAM')
    ],
    # Incomplete curation
    {
        'type': '"Trait"', 'name': '"Fₒ"', 'format': '"numeric"', 'Trait': 'Fo', 'Scale': 'Arbitrary',
        'ScaleType': 'NUMERICAL', 'categories': 'null', 'terms': '[“Photosynthesis”]', 'subjects': '["Sample"]'
    },
]

INPUT_SUBJECTS = [
    {'input': 'Total Boron', 'subject': 'Leaves', 'record_count': 10},
    {'input': 'Total Boron', 'subject': 'Green Beans', 'record_count': 5},
    {'input': 'Tree rust symptoms', 'subject': 'Tree', 'record_count': 20},
    {'input': 'Set planting date', 'subject': 'Tree', 'record_count': 30},
]


def write_csv(path, columns, rows):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=columns, restval='')
        writer.writeheader()
        writer.writerows(rows)


@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def editor_id(isolated_state, uow_factory) -> int:
    return await AccountBuilder(uow_factory=uow_factory).account(ontology_role=OntologyRole.EDITOR)


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    write_csv(tmp_path / 'input_details_curated.csv', CURATED_COLUMNS, CURATED_ROWS)
    write_csv(tmp_path / 'input_subjects.csv', ['input', 'subject', 'record_count'], INPUT_SUBJECTS)
    monkeypatch.setattr(ontology, 'BREEDCAFS_DATA_DIR', tmp_path)
    return tmp_path


@pytest.mark.asyncio(loop_scope="session")
async def test_prepare_ontology(uow_factory, editor_id, data_dir):
    ids = await prepare_breedcafs_ontology(uow_factory, user_id=editor_id)

    assert set(ids.subjects) == {s[0] for s in ontology.SUBJECTS}
    assert set(ids.location_types) == {"Country", "Region", "Farm", "Field", "Research Center"}
    assert set(ids.layout_types) == {"Row and Tree"}
    assert set(ids.record_group_types) == {"Replicate"}
    assert set(ids.inputs) == {
        ("Total Boron", ""), ("Tree rust symptoms", ""), ("Set planting date", ""),
        ("Fᵥ / Fₘ", "PocketPEA"), ("Fᵥ / Fₘ", "MiniPAM")
    }
    assert ids.inputs[("Set planting date", "")][0] is OntologyEntryLabel.FACTOR
    assert ids.inputs[("Fᵥ / Fₘ", "PocketPEA")] != ids.inputs[("Fᵥ / Fₘ", "MiniPAM")]

    assert set(ids.design_factors) == {"Shade Treatment", "Shade Level Treatment", "Stratum"}

    async with uow_factory.get_uow(user_id=editor_id) as uow:
        variable = await uow.ontology.get_entry(entry_id=ids.inputs[("Total Boron", "")][1], label=OntologyEntryLabel.VARIABLE)
        assert variable.name == "Boron (µg/g)"
        assert variable.description == "Total boron content (µg/g)"
        assert variable.synonyms == ["Total Boron"]

        async def targets(source_id: int, label: OntologyRelationshipLabel) -> set[int]:
            return {r.target_id async for r in uow.ontology.get_relationships(source_ids=[source_id], labels=[label])}

        trait = await uow.ontology.get_entry(name="Boron", label=OntologyEntryLabel.TRAIT)
        assert await targets(trait.id, OntologyRelationshipLabel.DESCRIBES_SUBJECT) == {
            ids.subjects["Leaves"], ids.subjects["Green Beans"]
        }
        elements = await uow.ontology.get_entry(name="Elements", label=OntologyEntryLabel.TERM)
        assert await targets(variable.id, OntologyRelationshipLabel.HAS_TERM) == {elements.id}

        rust_scale = await uow.ontology.get_entry(name="Defoliation Scale", label=OntologyEntryLabel.SCALE)
        assert rust_scale.scale_type is ScaleType.ORDINAL
        assert len(await targets(rust_scale.id, OntologyRelationshipLabel.HAS_CATEGORY)) == 3

        shade_level = await uow.ontology.get_entry(entry_id=ids.design_factors["Shade Level Treatment"], label=OntologyEntryLabel.FACTOR)
        shade_scale_id = next(iter(await targets(shade_level.id, OntologyRelationshipLabel.USES_SCALE)))
        assert len(await targets(shade_scale_id, OntologyRelationshipLabel.HAS_CATEGORY)) == 6
        shade_condition_id = next(iter(await targets(shade_level.id, OntologyRelationshipLabel.DESCRIBES_CONDITION)))
        assert await targets(shade_condition_id, OntologyRelationshipLabel.DESCRIBES_SUBJECT) == {ids.subjects["Tree"]}
        stratum = ids.design_factors["Stratum"]
        stratum_scale_id = next(iter(await targets(stratum, OntologyRelationshipLabel.USES_SCALE)))
        stratum_scale = await uow.ontology.get_entry(entry_id=stratum_scale_id, label=OntologyEntryLabel.SCALE)
        assert stratum_scale.scale_type is ScaleType.ORDINAL
        stratum_condition_id = next(iter(await targets(stratum, OntologyRelationshipLabel.DESCRIBES_CONDITION)))
        assert await targets(stratum_condition_id, OntologyRelationshipLabel.DESCRIBES_SUBJECT) == {ids.subjects["Branch"]}

        shade_treatment_id = ids.design_factors["Shade Treatment"]
        for label in (OntologyRelationshipLabel.DESCRIBES_CONDITION, OntologyRelationshipLabel.USES_CONTROL_METHOD):
            assert await targets(shade_level.id, label) == await targets(shade_treatment_id, label)
        date_scale = await uow.ontology.get_entry(name="Datetime", label=OntologyEntryLabel.SCALE)
        assert date_scale.scale_type is ScaleType.DATE

        assert await uow.ontology.get_entry(name="Fo", label=OntologyEntryLabel.TRAIT) is None
        assert await uow.ontology.get_entry(name="Fv/Fm", label=OntologyEntryLabel.TRAIT) is not None

    with open(data_dir / 'ontology_ids.csv') as f:
        assert {(row['input'], row['apparatus']) for row in csv.DictReader(f)} == set(ids.inputs)

    # Running again finds everything already created
    again = await prepare_breedcafs_ontology(uow_factory, user_id=editor_id)
    assert again.created == 0
    assert again.inputs == ids.inputs


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.skipif(
    not (BREEDCAFS_DATA_DIR / 'input_details_curated.csv').exists(),
    reason="The curated BreedCAFS inputs are not in the data directory"
)
async def test_prepare_ontology_from_curated_inputs(uow_factory, editor_id, tmp_path, monkeypatch):
    for name in ('input_details_curated.csv', 'input_subjects.csv'):
        shutil.copy(BREEDCAFS_DATA_DIR / name, tmp_path / name)
    monkeypatch.setattr(ontology, 'BREEDCAFS_DATA_DIR', tmp_path)

    ids = await prepare_breedcafs_ontology(uow_factory, user_id=editor_id)
    with open(tmp_path / 'input_details_curated.csv', encoding='utf-8-sig') as f:
        assert len(ids.inputs) == sum(1 for _ in csv.DictReader(f))

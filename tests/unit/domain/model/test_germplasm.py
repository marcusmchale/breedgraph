import pytest
import pytest_asyncio

from src.breedgraph.domain.model.accounts import AccountStored, UserStored
from src.breedgraph.domain.model.organisations import TeamStored, Access, Authorisation, Affiliation
from src.breedgraph.domain.model.ontology import (
    Version, VersionStored,
    Ontology, GermplasmMethod
)
from src.breedgraph.domain.model.germplasm import (
    GermplasmEntryInput, GermplasmEntryStored,
    Germplasm, GermplasmSourceType,
    Reproduction,
    SourceDetails
)
from src.breedgraph.domain.model.controls import Control, Controller, ReadRelease

from src.breedgraph.custom_exceptions import IllegalOperationError

@pytest_asyncio.fixture
def germplasm_method(lorem_text_generator) -> GermplasmMethod:
    return GermplasmMethod(name=lorem_text_generator.new_text(10))

@pytest_asyncio.fixture
def ontology(
        lorem_text_generator,
        germplasm_method
) -> Ontology:
    version = Version(major=0, minor=0, patch=0, comment="Test")
    version_stored = VersionStored(**dict(version), id=1)
    ontology = Ontology(version=version_stored)
    ontology.add_germplasm_method(germplasm_method)
    return ontology

@pytest_asyncio.fixture
def first_germplasm(lorem_text_generator):
    return Germplasm()

@pytest_asyncio.fixture
def account():
    yield AccountStored(
        user=UserStored(id=1, name='Tester', fullname='TESTER', email='asdf@mail.com', password_hash="AAAA")
    )

@pytest_asyncio.fixture
def first_team(account):
    yield TeamStored(
        id=1,
        name="Team 1",
        affiliations= {
            Access.READ: {account.user.id: Affiliation(authorisation=Authorisation.AUTHORISED, heritable=True)}
        }
    )

@pytest_asyncio.fixture
def first_entry(lorem_text_generator, first_team):
    return GermplasmEntryInput(
        name=lorem_text_generator.new_text(10),
        synonyms=[lorem_text_generator.new_text(5)],
        controller=Controller(controls={first_team.id:Control(release=ReadRelease.PRIVATE)})
    )

def new_entry(lorem_text_generator, first_team):
    return GermplasmEntryInput(
        name=lorem_text_generator.new_text(10),
        synonyms=[lorem_text_generator.new_text(5)],
        controller=Controller(controls={first_team.id:Control(release=ReadRelease.PRIVATE)})
    )

@pytest_asyncio.fixture
def seed_source_details(lorem_text_generator) -> SourceDetails:
    return SourceDetails(label=GermplasmSourceType.SEED)

@pytest.mark.asyncio
async def test_germplasm_add_and_get_entry(lorem_text_generator, first_germplasm, first_entry):
    entry_id = first_germplasm.add_entry(first_entry, sources=[])
    assert first_germplasm.size == 1
    assert first_germplasm.get_entry(entry_id) == first_entry
    assert first_germplasm.get_entry(first_entry.name) == first_entry
    assert first_germplasm.get_entry(first_entry.synonyms[0]) == first_entry

@pytest.mark.asyncio
async def test_germplasm_multiple_roots_fails(lorem_text_generator, first_germplasm, first_entry):
    first_germplasm.add_entry(first_entry, sources=[])
    with pytest.raises(ValueError):
        first_germplasm.add_entry(first_entry, sources=[])

@pytest.mark.asyncio
async def test_build_and_read(
        lorem_text_generator,
        first_team,
        first_germplasm,
        first_entry,
        seed_source_details
):
    first_entry_id = first_germplasm.add_entry(first_entry, sources=[])
    second_entry = new_entry(lorem_text_generator, first_team)
    second_entry_id = first_germplasm.add_entry(
        second_entry,
        sources=[(first_entry_id, seed_source_details)]
    )
    redacted_for_read_team = first_germplasm.redacted({first_team.id})
    assert redacted_for_read_team.size == 2
    redacted_for_other_team = first_germplasm.redacted({2})
    assert redacted_for_other_team.size == 1
    assert redacted_for_other_team.root.name == Germplasm._redacted_str
    redacted_for_public = first_germplasm.redacted()
    assert redacted_for_public.size == 1
    assert redacted_for_public.root.name == Germplasm._redacted_str

    second_entry.set_release(ReadRelease.REGISTERED, first_team.id)
    redacted_for_other_team_after_release_to_registered = first_germplasm.redacted({2})
    assert redacted_for_other_team_after_release_to_registered.size == 2
    redacted_for_public_after_release_to_registered = first_germplasm.redacted()
    assert redacted_for_public_after_release_to_registered.size == 1

    second_entry.set_release(ReadRelease.PUBLIC, first_team.id)
    redacted_for_public_after_release_to_public = first_germplasm.redacted()
    assert redacted_for_public_after_release_to_public.size == 2


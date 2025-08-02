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
    Germplasm, GermplasmSourceType
)
from src.breedgraph.domain.model.controls import Control, Controller, ReadRelease
from src.breedgraph.domain.model.time_descriptors import PyDT64

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
    ontology.add_entry(germplasm_method)
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
def first_entry(lorem_text_generator):
    return GermplasmEntryInput(
        name=lorem_text_generator.new_text(10),
        synonyms=[lorem_text_generator.new_text(5)]
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
def first_entry_stored(lorem_text_generator, first_entry, first_team):
    return GermplasmEntryStored(
        **first_entry.model_dump(),
        id=1
    )

@pytest.mark.asyncio
async def test_germplasm_add_and_get_entry(lorem_text_generator, first_germplasm, first_entry):
    entry_id = first_germplasm.add_entry(first_entry)
    assert first_germplasm.size == 1
    assert first_germplasm.get_entry(entry_id) == first_entry
    assert first_germplasm.get_entry(first_entry.name) == first_entry
    assert first_germplasm.get_entry(first_entry.synonyms[0]) == first_entry


@pytest_asyncio.fixture
def second_entry_stored(lorem_text_generator, first_entry, first_team):
    return GermplasmEntryStored(
        name=lorem_text_generator.new_text(10),
        synonyms=[lorem_text_generator.new_text(5)],
        id=2,
        time="2024"
    )

@pytest.mark.asyncio
async def test_build_and_read(
        lorem_text_generator,
        account,
        first_team,
        first_germplasm,
        first_entry_stored, second_entry_stored
):
    first_entry_id = first_germplasm.add_entry(first_entry_stored)
    second_entry_id = first_germplasm.add_entry(
        second_entry_stored,
        sources={first_entry_id: {'type': GermplasmSourceType.SEED}}
    )
    private_controllers = {
        'Germplasm': {
            first_entry_id: Controller(controls={first_team.id: Control(release=ReadRelease.PRIVATE)}),
            second_entry_id: Controller(controls={first_team.id: Control(release=ReadRelease.PRIVATE)})
        }
    }
    redacted_for_read_team = first_germplasm.redacted(
        controllers=private_controllers,
        user_id=account.user.id,
        read_teams={first_team.id}
    )
    assert redacted_for_read_team.size == 2
    assert first_entry_id in redacted_for_read_team.get_sources(second_entry_id)
    assert second_entry_id in redacted_for_read_team.get_sinks(first_entry_id)

    redacted_for_registered = first_germplasm.redacted(
        controllers=private_controllers,
        user_id=account.user.id,
        read_teams=None
    )
    assert redacted_for_registered.size == 1
    assert redacted_for_registered.root.name == Germplasm._redacted_str

    redacted_for_public = first_germplasm.redacted(
        controllers=private_controllers,
        user_id=None,
        read_teams=None
    )
    assert redacted_for_public.size == 1
    assert redacted_for_public.root.name == Germplasm._redacted_str

    registered_controllers = {
        'Germplasm': {
            first_entry_id: Controller(controls={first_team.id: Control(release=ReadRelease.REGISTERED)}),
            second_entry_id: Controller(controls={first_team.id: Control(release=ReadRelease.REGISTERED)}),
        }
    }
    redacted_for_registered_after_release_to_registered = first_germplasm.redacted(
        controllers=registered_controllers,
        user_id=account.user.id,
        read_teams=None
    )
    assert redacted_for_registered_after_release_to_registered.size == 2

    redacted_for_public_after_release_to_registered = first_germplasm.redacted(
        controllers=registered_controllers,
        user_id=None,
        read_teams=None
    )
    assert redacted_for_public_after_release_to_registered.size == 1

    public_controllers = {
        'Germplasm': {
            first_entry_id: Controller(controls={first_team.id: Control(release=ReadRelease.PUBLIC)}),
            second_entry_id: Controller(controls={first_team.id: Control(release=ReadRelease.PUBLIC)}),
        }
    }

    redacted_for_public_after_release_to_public = first_germplasm.redacted(
        controllers=public_controllers,
        user_id=None,
        read_teams=None
    )
    assert redacted_for_public_after_release_to_public.size == 2


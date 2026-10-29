"""
Every deployment starts with the standard licences, CC BY 4.0 and CC0 1.0, as fixed legal references, and the
ontology's first version under CC BY 4.0, which later versions keep unless they name another (docs/licences.md §6).
The test setup seeds them as scripts/setup_initial_data.py does (service_layer/application/initial_data.py).
"""
import hashlib
from importlib.resources import files

import pytest

from breedgraph.custom_exceptions import IllegalOperationError
from breedgraph.domain.model.accounts import OntologyRole
from breedgraph.domain.model.controls import ControlledModelLabel, ReadRelease
from breedgraph.domain.model.ontology import VersionChange
from breedgraph.domain.model.references import TextFormat
from breedgraph.service_layer.application.licence_seed import seed_licences, STANDARD_LICENCES, CC_BY, CC0

from tests.breedgraph.scenarios.account_builder import AccountBuilder
from tests.breedgraph.scenarios.reference_builder import ReferenceBuilder


async def seeded_ids(uow_factory) -> dict[str, int]:
    async with uow_factory.get_uow() as uow:
        return {licence.seed_key: await uow.repositories.references.get_seeded_id(licence.seed_key) for licence in STANDARD_LICENCES}


async def latest_commit(views_factory):
    async with views_factory.get_views() as views:
        return max(await views.ontology.get_commits(), key=lambda commit: commit.version.packed_version)


@pytest.mark.asyncio(loop_scope="session")
async def test_the_standard_licences_are_fixed_and_read_by_everyone(uow_factory, views_factory):
    ids = await seeded_ids(uow_factory)
    assert set(ids) == {CC_BY, CC0} and None not in ids.values()
    async with views_factory.get_views() as views:
        references = await views.references.get_references(list(ids.values()))
        controllers = await views.controls.get_controllers(ControlledModelLabel.REFERENCE, list(ids.values()))
    by_id = {reference.id: reference for reference in references}
    for licence in STANDARD_LICENCES:
        reference = by_id[ids[licence.seed_key]]
        data = (files('breedgraph') / 'legal' / 'licences' / licence.filename).read_bytes()
        assert reference.description == licence.description
        assert reference.text == data.decode('utf-8')
        assert reference.text_format is TextFormat.PLAIN
        # the hash of the text is the file's, as the text is the file unchanged
        assert reference.content_hash == hashlib.sha256(data).hexdigest()
        assert controllers[reference.id].fixed and controllers[reference.id].release is ReadRelease.PUBLIC


@pytest.mark.asyncio(loop_scope="session")
async def test_seeding_again_creates_nothing(uow_factory):
    ids = await seeded_ids(uow_factory)
    async with uow_factory.get_uow() as uow:
        assert await seed_licences(uow.repositories.references) == ids
        result = await uow.tx.run("MATCH (reference:Reference) WHERE reference.seed_key IS NOT NULL RETURN count(reference) AS seeded")
        assert (await result.single())['seeded'] == len(STANDARD_LICENCES)


@pytest.mark.asyncio(loop_scope="session")
async def test_versions_keep_the_ontologys_licence_until_another_is_named(uow_factory, views_factory):
    ids = await seeded_ids(uow_factory)
    # the first version, from seeding, is under CC BY 4.0
    assert (await latest_commit(views_factory)).licence == ids[CC_BY]

    admin = await AccountBuilder(uow_factory).account_with_affiliations(ontology_role=OntologyRole.ADMIN)
    async with uow_factory.get_uow(user_id=admin['user_id']) as uow:
        commit = await uow.ontology.commit_version(version_change=VersionChange.PATCH, comment="No licence named")
        await uow.commit()
    assert commit.licence == ids[CC_BY]
    assert (await latest_commit(views_factory)).licence == ids[CC_BY]

    # another public licence can be named, and is kept in turn
    async with uow_factory.get_uow(
            user_id=admin['user_id'], write_team=admin['team_id'], release=ReadRelease.PUBLIC
    ) as uow:
        own_licence = await uow.repositories.references.create(ReferenceBuilder.legal_reference_input())
        await uow.commit()
    async with uow_factory.get_uow(user_id=admin['user_id']) as uow:
        await uow.ontology.commit_version(version_change=VersionChange.PATCH, licence_reference=own_licence.id)
        await uow.commit()
    async with uow_factory.get_uow(user_id=admin['user_id']) as uow:
        await uow.ontology.commit_version(version_change=VersionChange.PATCH)
        await uow.commit()
    assert (await latest_commit(views_factory)).licence == own_licence.id


@pytest.mark.asyncio(loop_scope="session")
async def test_a_private_licence_cant_be_the_ontologys(uow_factory):
    admin = await AccountBuilder(uow_factory).account_with_affiliations(ontology_role=OntologyRole.ADMIN)
    async with uow_factory.get_uow(user_id=admin['user_id'], write_team=admin['team_id']) as uow:
        private_licence = await uow.repositories.references.create(ReferenceBuilder.legal_reference_input())
        await uow.commit()
    async with uow_factory.get_uow(user_id=admin['user_id']) as uow:
        with pytest.raises(IllegalOperationError, match="public references only"):
            await uow.ontology.commit_version(version_change=VersionChange.PATCH, licence_reference=private_licence.id)


@pytest.mark.asyncio(loop_scope="session")
async def test_an_ontology_without_a_licence_takes_cc_by_at_its_next_version(uow_factory, views_factory):
    """A database set up before the licences were seeded gets them from scripts/seed_licences.py, and no version licence"""
    ids = await seeded_ids(uow_factory)
    async with uow_factory.get_uow() as uow:
        await uow.tx.run("MATCH (:OntologyCommit)-[uses:USES_LICENCE]->() DELETE uses")
        await uow.commit()
    assert (await latest_commit(views_factory)).licence is None

    admin = await AccountBuilder(uow_factory).account_with_affiliations(ontology_role=OntologyRole.ADMIN)
    async with uow_factory.get_uow(user_id=admin['user_id']) as uow:
        await uow.ontology.commit_version(version_change=VersionChange.PATCH)
        await uow.commit()
    assert (await latest_commit(views_factory)).licence == ids[CC_BY]

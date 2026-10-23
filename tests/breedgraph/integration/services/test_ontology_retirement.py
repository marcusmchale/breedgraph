"""
Deprecating entries takes their relationships with them, the commit removes both, and restoring brings them back
(domain.services.ontology_lifecycles)
"""
import pytest
import pytest_asyncio

from breedgraph.custom_exceptions import IllegalOperationError, IdentityExistsError
from breedgraph.domain.model.accounts import OntologyRole
from breedgraph.domain.model.ontology import (
    OntologyEntryLabel, OntologyRelationshipLabel, LifecyclePhase, VersionChange, ScaleType, ObservationMethodType,
    SubjectInput, TraitInput, ObservationMethodInput, ScaleInput, ScaleCategory, VariableInput, TermInput,
    LocationTypeInput
)

from tests.breedgraph.scenarios.account_builder import AccountBuilder


@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def editor_id(isolated_state, uow_factory) -> int:
    return await AccountBuilder(uow_factory=uow_factory).account(ontology_role=OntologyRole.EDITOR)


@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def entries(uow_factory, editor_id) -> dict[str, int]:
    """A variable with its trait, method and an ordinal scale, a term, and a location type with a child"""
    async with uow_factory.get_uow(user_id=editor_id) as uow:
        ontology = uow.ontology
        subject = await ontology.create_subject(SubjectInput(name="Retiring Tree"))
        trait = await ontology.create_trait(TraitInput(name="Retiring Vigour"), subjects=[subject.id])
        method = await ontology.create_entry(
            ObservationMethodInput(name="Retiring Look", observation_type=ObservationMethodType.ESTIMATION)
        )
        scale = await ontology.create_scale(ScaleInput(
            name="Retiring Classes", scale_type=ScaleType.ORDINAL,
            categories=[ScaleCategory("Retiring Low"), ScaleCategory("Retiring High")]
        ))
        variable = await ontology.create_variable(
            VariableInput(name="Retiring Vigour Class"), trait_id=trait.id, observation_method_id=method.id, scale_id=scale.id
        )
        term = await ontology.create_entry(TermInput(name="Retiring Term"))
        await ontology.link_to_term(source_id=variable.id, source_label=OntologyEntryLabel.VARIABLE, term_id=term.id)
        region = await ontology.create_entry(LocationTypeInput(name="Retiring Region"))
        farm = await ontology.create_entry(LocationTypeInput(name="Retiring Farm"), parents=[region.id])
        await ontology.commit_version(version_change=VersionChange.MINOR)
        await uow.commit()
    return {
        'subject': subject.id, 'trait': trait.id, 'method': method.id,
        'scale': scale.id, 'variable': variable.id, 'term': term.id, 'region': region.id, 'farm': farm.id
    }


async def relationships_of(uow, entry_id: int, phases=None) -> set[tuple[int, OntologyRelationshipLabel, int]]:
    return {
        (r.source_id, r.label, r.target_id)
        async for r in uow.ontology.get_relationships(entry_ids=[entry_id], phases=phases)
    }


@pytest.mark.asyncio(loop_scope="session")
async def test_an_entry_a_current_entry_is_defined_by_is_kept(uow_factory, editor_id, entries):
    async with uow_factory.get_uow(user_id=editor_id) as uow:
        with pytest.raises(IllegalOperationError, match="UsesScale"):
            await uow.ontology.deprecate_entries([entries['scale']])
        with pytest.raises(IllegalOperationError, match="DescribesSubject"):
            await uow.ontology.deprecate_entries([entries['subject']])


@pytest.mark.asyncio(loop_scope="session")
async def test_cancelling_brings_the_relationships_back(uow_factory, editor_id, entries):
    term_link = (entries['variable'], OntologyRelationshipLabel.HAS_TERM, entries['term'])
    async with uow_factory.get_uow(user_id=editor_id) as uow:
        await uow.ontology.deprecate_entries([entries['term']])
        await uow.commit()
    async with uow_factory.get_uow(user_id=editor_id) as uow:
        assert term_link in await relationships_of(uow, entries['term'], phases=[LifecyclePhase.DEPRECATED])
        # a relationship deprecated with an entry comes back with it, not on its own
        relationship = [r async for r in uow.ontology.get_relationships(entry_ids=[entries['term']])][0]
        with pytest.raises(IllegalOperationError, match="cancel their deprecation instead"):
            await uow.ontology.cancel_deprecate_relationships([relationship.id])
        # nor can anything be linked to it while it is deprecated
        with pytest.raises(IllegalOperationError, match="are deprecated"):
            await uow.ontology.link_to_term(
                source_id=entries['trait'], source_label=OntologyEntryLabel.TRAIT, term_id=entries['term']
            )
    async with uow_factory.get_uow(user_id=editor_id) as uow:
        await uow.ontology.cancel_deprecate_entries([entries['term']])
        await uow.commit()
    async with uow_factory.get_uow(user_id=editor_id) as uow:
        assert term_link in await relationships_of(uow, entries['term'], phases=[LifecyclePhase.ACTIVE])


@pytest.mark.asyncio(loop_scope="session")
async def test_the_commit_removes_the_relationships_with_their_entries(uow_factory, editor_id, entries):
    retired = [entries[name] for name in ('variable', 'trait', 'method', 'scale', 'subject', 'term', 'region')]
    async with uow_factory.get_uow(user_id=editor_id) as uow:
        await uow.ontology.deprecate_entries(retired)
        await uow.ontology.commit_version(version_change=VersionChange.MAJOR)
        await uow.commit()
    async with uow_factory.get_uow(user_id=editor_id) as uow:
        # the kept entries no longer have relationships to the removed ones
        assert await relationships_of(uow, entries['farm']) == set()
        # the removed variable's relationships were removed with it, marked with what they were deprecated with
        removed = [r async for r in uow.ontology.get_relationships(entry_ids=[entries['variable']], phases=[LifecyclePhase.REMOVED])]
        assert {(r.label, r.target_id) for r in removed} == {
            (OntologyRelationshipLabel.DESCRIBES_TRAIT, entries['trait']),
            (OntologyRelationshipLabel.USES_OBSERVATION_METHOD, entries['method']),
            (OntologyRelationshipLabel.USES_SCALE, entries['scale']),
            (OntologyRelationshipLabel.HAS_TERM, entries['term']),
        }
        lifecycles = await uow.ontology.persistence.get_relationship_lifecycles([r.id for r in removed])
        assert {r.target_id: lifecycles[r.id].deprecated_with for r in removed}[entries['scale']] == sorted(
            [entries['variable'], entries['scale']]
        )
        assert await uow.ontology.get_entry(entry_id=entries['farm']) is not None
        assert await uow.ontology.get_entry(entry_id=entries['region']) is None


@pytest.mark.asyncio(loop_scope="session")
async def test_restoring_brings_entries_back_with_their_relationships(uow_factory, editor_id, entries):
    async with uow_factory.get_uow(user_id=editor_id) as uow:
        with pytest.raises(IllegalOperationError, match="restore them with it"):
            await uow.ontology.restore_entries([entries['variable']])
        with pytest.raises(IllegalOperationError, match="is not removed"):
            await uow.ontology.restore_entries([entries['farm']])
        # a new location type takes the removed region's name
        await uow.ontology.create_entry(LocationTypeInput(name="Retiring Region"))
        await uow.commit()
    async with uow_factory.get_uow(user_id=editor_id) as uow:
        with pytest.raises(IdentityExistsError, match="Retiring Region"):
            await uow.ontology.restore_entries([entries['region']])

    async with uow_factory.get_uow(user_id=editor_id) as uow:
        await uow.ontology.restore_entries([entries[name] for name in ('variable', 'trait', 'method', 'scale', 'subject')])
        await uow.commit()
    async with uow_factory.get_uow(user_id=editor_id) as uow:
        # drafts until the next commit: data citing the variable reads it with what was restored with it,
        # but nothing new links to it
        scale = await uow.ontology.get_concept_scale(entries['variable'])
        assert scale.id == entries['scale'] and [c.name for c in scale.categories] == ["Retiring Low", "Retiring High"]
        with pytest.raises(IllegalOperationError, match="Not yet in a committed version"):
            await uow.ontology.require_entries([entries['variable']])
    async with uow_factory.get_uow(user_id=editor_id) as uow:
        await uow.ontology.commit_version(version_change=VersionChange.MINOR)
        await uow.commit()
    async with uow_factory.get_uow(user_id=editor_id) as uow:
        assert await uow.ontology.get_entry(entry_id=entries['variable']) is not None, "the same entry, by its id"
        # back with what defines it, but not its term, which stays removed
        assert await relationships_of(uow, entries['variable']) == {
            (entries['variable'], OntologyRelationshipLabel.DESCRIBES_TRAIT, entries['trait']),
            (entries['variable'], OntologyRelationshipLabel.USES_OBSERVATION_METHOD, entries['method']),
            (entries['variable'], OntologyRelationshipLabel.USES_SCALE, entries['scale']),
        }
        scale = await uow.ontology.get_entry(entry_id=entries['scale'])
        assert [c.name for c in scale.categories] == ["Retiring Low", "Retiring High"], "with its categories, in order"

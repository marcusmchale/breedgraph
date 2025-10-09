from src.breedgraph.domain import commands
from src.breedgraph.domain.model.ontology import *

from src.breedgraph.service_layer.infrastructure import AbstractUnitOfWork
from src.breedgraph.service_layer.application import OntologyApplicationService

from ..registry import handlers

import logging

from typing import List

ontology_mapper = ontology_mapper  # just re-declaring here for clarity as this is imported with import all above

logger = logging.getLogger(__name__)


@handlers.command_handler()
async def commit_ontology(cmd: commands.ontologies.CommitOntologyVersion, uow: AbstractUnitOfWork):
    async with uow.get_uow(user_id=cmd.agent_id) as uow_holder:
        ontology_service = uow_holder.ontology
        await ontology_service.commit_version(
            version_change = cmd.version_change,
            comment = cmd.comment,
            licence_reference = cmd.licence,
            copyright_reference = cmd.copyright
        )
        await uow_holder.commit()

@handlers.command_handler()
async def activate_ontology_entries(cmd: commands.ontologies.ActivateOntologyEntries, uow: AbstractUnitOfWork):
    async with uow.get_uow(user_id=cmd.agent_id) as uow_holder:
        ontology_service = uow_holder.ontology
        await ontology_service.activate_entries(
            entry_ids = cmd.entry_ids
        )
        await uow_holder.commit()

@handlers.command_handler()
async def deprecate_ontology_entries(cmd: commands.ontologies.DeprecateOntologyEntries, uow: AbstractUnitOfWork):
    async with uow.get_uow(user_id=cmd.agent_id) as uow_holder:
        ontology_service = uow_holder.ontology
        await ontology_service.deprecate_entries(
            entry_ids = cmd.entry_ids
        )
        await uow_holder.commit()

@handlers.command_handler()
async def remove_ontology_entries(cmd: commands.ontologies.RemoveOntologyEntries, uow: AbstractUnitOfWork):
    async with uow.get_uow(user_id=cmd.agent_id) as uow_holder:
        ontology_service = uow_holder.ontology
        await ontology_service.remove_entries(
            entry_ids = cmd.entry_ids
        )
        await uow_holder.commit()

@handlers.command_handler()
async def activate_ontology_relationships(cmd: commands.ontologies.ActivateOntologyRelationships, uow: AbstractUnitOfWork):
    async with uow.get_uow(user_id=cmd.agent_id) as uow_holder:
        ontology_service = uow_holder.ontology
        await ontology_service.activate_relationships(
            entry_ids = cmd.entry_ids
        )
        await uow_holder.commit()

@handlers.command_handler()
async def deprecate_ontology_relationships(cmd: commands.ontologies.DeprecateOntologyRelationships, uow: AbstractUnitOfWork):
    async with uow.get_uow(user_id=cmd.agent_id) as uow_holder:
        ontology_service = uow_holder.ontology
        await ontology_service.deprecate_relationships(
            entry_ids = cmd.entry_ids
        )
        await uow_holder.commit()

@handlers.command_handler()
async def remove_ontology_relationships(cmd: commands.ontologies.RemoveOntologyRelationships, uow: AbstractUnitOfWork):
    async with uow.get_uow(user_id=cmd.agent_id) as uow_holder:
        ontology_service = uow_holder.ontology
        await ontology_service.remove_relationships(
            entry_ids = cmd.entry_ids
        )
        await uow_holder.commit()

@handlers.command_handler()
async def create_term(cmd: commands.ontologies.CreateTerm, uow: AbstractUnitOfWork):
    async with uow.get_uow(user_id=cmd.agent_id) as uow_holder:
        ontology_service = uow_holder.ontology
        entry = TermInput(
            name=cmd.name,
            description=cmd.description,
            abbreviation=cmd.abbreviation,
            synonyms=cmd.synonyms or [],
            authors=cmd.author_ids or [],
            references=cmd.reference_ids or []
        )
        entry = await ontology_service.create_entry(entry, cmd.parent_ids, cmd.child_ids)
        to_link = [
            "subject_ids",
            "scale_ids",
            "category_ids",
            "observation_method_ids",
            "trait_ids",
            "variable_ids",
            "control_method_ids",
            "condition_ids",
            "factor_ids",
            "event_ids",
            "location_type_ids",
            "layout_type_ids",
            "design_ids",
            "role_ids",
            "title_ids"
        ]
        for attr in to_link:
            id_list = getattr(cmd, attr) or []
            label = ontology_mapper.get_other_label_from_attribute(attr)
            for id_ in id_list or []:
                await ontology_service.link_to_term(
                    source_id=id_,
                    source_label=label,
                    term_id=entry.id
                )
        await uow_holder.commit()


@handlers.command_handler()
async def create_subject(cmd: commands.ontologies.CreateSubject, uow: AbstractUnitOfWork):
    async with uow.get_uow(user_id=cmd.agent_id) as uow_holder:
        ontology_service = uow_holder.ontology
        entry = SubjectInput(
            name=cmd.name,
            description=cmd.description,
            abbreviation=cmd.abbreviation,
            synonyms=cmd.synonyms or [],
            authors=cmd.author_ids or [],
            references=cmd.reference_ids or []
        )
        entry = await ontology_service.create_subject(entry, cmd.parent_ids, cmd.child_ids, traits=cmd.trait_ids, conditions=cmd.condition_ids)
        for term_id in cmd.term_ids or []:
            await ontology_service.link_to_term(source_id=entry.id, source_label=entry.label, term_id=term_id)
        await uow_holder.commit()

@handlers.command_handler()
async def create_trait(cmd: commands.ontologies.CreateTrait, uow: AbstractUnitOfWork):
    async with uow.get_uow(user_id=cmd.agent_id) as uow_holder:
        ontology_service = uow_holder.ontology
        entry = TraitInput(
            name=cmd.name,
            description=cmd.description,
            abbreviation=cmd.abbreviation,
            synonyms=cmd.synonyms or [],
            authors=cmd.author_ids or [],
            references=cmd.reference_ids or []
        )
        entry = await ontology_service.create_trait(entry, cmd.parent_ids, cmd.child_ids, subjects=cmd.subject_ids)
        for term_id in cmd.term_ids or []:
            await ontology_service.link_to_term(source_id=entry.id, source_label=entry.label, term_id=term_id)
        await uow_holder.commit()


@handlers.command_handler()
async def create_condition(cmd: commands.ontologies.CreateCondition, uow: AbstractUnitOfWork):
    async with uow.get_uow(user_id=cmd.agent_id) as uow_holder:
        ontology_service = uow_holder.ontology
        entry = ConditionInput(
            name=cmd.name,
            description=cmd.description,
            abbreviation=cmd.abbreviation,
            synonyms=cmd.synonyms or [],
            authors=cmd.author_ids or [],
            references=cmd.reference_ids or []
        )
        entry = await ontology_service.create_condition(entry, cmd.parent_ids, cmd.child_ids, subjects=cmd.subject_ids)
        for term_id in cmd.term_ids or []:
            await ontology_service.link_to_term(source_id=entry.id, source_label=entry.label, term_id=term_id)
        await uow_holder.commit()


@handlers.command_handler()
async def create_scale(cmd: commands.ontologies.CreateScale, uow: AbstractUnitOfWork):
    async with uow.get_uow(user_id=cmd.agent_id) as uow_holder:
        ontology_service = uow_holder.ontology
        entry = ScaleInput(
            name=cmd.name,
            description=cmd.description,
            abbreviation=cmd.abbreviation,
            synonyms=cmd.synonyms or [],
            authors=cmd.author_ids or [],
            references=cmd.reference_ids or [],
            scale_type=cmd.scale_type
        )
        entry = await ontology_service.create_entry(entry, cmd.parent_ids, cmd.child_ids)
        for term_id in cmd.term_ids or []:
            await ontology_service.link_to_term(source_id=entry.id, source_label=entry.label, term_id=term_id)
        await uow_holder.commit()

@handlers.command_handler()
async def create_scale_category(cmd: commands.ontologies.CreateScaleCategory, uow: AbstractUnitOfWork):
    async with uow.get_uow(user_id=cmd.agent_id) as uow_holder:
        ontology_service = uow_holder.ontology
        entry = ScaleCategoryInput(
            name=cmd.name,
            description=cmd.description,
            abbreviation=cmd.abbreviation,
            synonyms=cmd.synonyms or [],
            authors=cmd.author_ids or [],
            references=cmd.reference_ids or []
        )
        entry = await ontology_service.create_entry(entry, cmd.parent_ids, cmd.child_ids)
        for term_id in cmd.term_ids or []:
            await ontology_service.link_to_term(source_id=entry.id, source_label=entry.label, term_id=term_id)
        await uow_holder.commit()


@handlers.command_handler()
async def create_observation_method(cmd: commands.ontologies.CreateObservationMethod, uow: AbstractUnitOfWork):
    async with uow.get_uow(user_id=cmd.agent_id) as uow_holder:
        ontology_service = uow_holder.ontology
        entry = ObservationMethodInput(
            name=cmd.name,
            description=cmd.description,
            abbreviation=cmd.abbreviation,
            synonyms=cmd.synonyms or [],
            authors=cmd.author_ids or [],
            references=cmd.reference_ids or [],
            observation_type=cmd.observation_type
        )
        entry = await ontology_service.create_entry(entry, cmd.parent_ids, cmd.child_ids)
        for term_id in cmd.term_ids or []:
            await ontology_service.link_to_term(source_id=entry.id, source_label=entry.label, term_id=term_id)
        await uow_holder.commit()


@handlers.command_handler()
async def create_variable(cmd: commands.ontologies.CreateVariable, uow: AbstractUnitOfWork):
    async with uow.get_uow(user_id=cmd.agent_id) as uow_holder:
        ontology_service = uow_holder.ontology
        entry_input = VariableInput(
            name=cmd.name,
            description=cmd.description,
            abbreviation=cmd.abbreviation,
            synonyms=cmd.synonyms or [],
            authors=cmd.author_ids or [],
            references=cmd.reference_ids or []
        )
        entry = await ontology_service.create_variable(
            entry_input,
            trait_id = cmd.trait_id,
            observation_method_id = cmd.observation_method_id,
            scale_id = cmd.scale_id,
            parents = cmd.parent_ids,
            children =cmd.child_ids
        )
        for term_id in cmd.term_ids or []:
            await ontology_service.link_to_term(source_id=entry.id, source_label=entry.label, term_id=term_id)
        await uow_holder.commit()


@handlers.command_handler()
async def create_control_method(cmd: commands.ontologies.CreateControlMethod, uow: AbstractUnitOfWork):
    async with uow.get_uow(user_id=cmd.agent_id) as uow_holder:
        ontology_service = uow_holder.ontology
        entry_input = ControlMethodInput(
            name=cmd.name,
            description=cmd.description,
            abbreviation=cmd.abbreviation,
            synonyms=cmd.synonyms or [],
            authors=cmd.author_ids or [],
            references=cmd.reference_ids or []
        )
        entry = await ontology_service.create_entry(entry_input, cmd.parent_ids, cmd.child_ids)
        for term_id in cmd.term_ids or []:
            await ontology_service.link_to_term(source_id=entry.id, source_label=entry.label, term_id=term_id)
        await uow_holder.commit()


@handlers.command_handler()
async def create_factor(cmd: commands.ontologies.CreateFactor, uow: AbstractUnitOfWork):
    async with uow.get_uow(user_id=cmd.agent_id) as uow_holder:
        ontology_service = uow_holder.ontology
        entry_input = FactorInput(
            name=cmd.name,
            description=cmd.description,
            abbreviation=cmd.abbreviation,
            synonyms=cmd.synonyms or [],
            authors=cmd.author_ids or [],
            references = cmd.reference_ids or []
        )

        entry = await ontology_service.create_factor(
            entry_input,
            condition_id = cmd.condition_id,
            control_method_id = cmd.control_method_id,
            scale_id = cmd.scale_id,
            parents = cmd.parent_ids,
            children = cmd.child_ids
        )
        for term_id in cmd.term_ids or []:
            await ontology_service.link_to_term(source_id=entry.id, source_label=entry.label, term_id=term_id)
        await uow_holder.commit()


@handlers.command_handler()
async def create_event_type(cmd: commands.ontologies.CreateEventType, uow: AbstractUnitOfWork):
    async with uow.get_uow(user_id=cmd.agent_id) as uow_holder:
        ontology_service = uow_holder.ontology
        entry_input = EventTypeInput(  # Using EventTypeInput
            name=cmd.name,
            description=cmd.description,
            abbreviation=cmd.abbreviation,
            synonyms=cmd.synonyms or [],
            authors=cmd.author_ids or [],
            references=cmd.reference_ids or []
        )
        entry = await ontology_service.create_event_type(
            entry_input,
            parents = cmd.parent_ids,
            children = cmd.child_ids,
            variables = cmd.variables,
            factors = cmd.factors
        )
        for term_id in cmd.term_ids or []:
            await ontology_service.link_to_term(source_id=entry.id, source_label=entry.label, term_id=term_id)
        await uow_holder.commit()

@handlers.command_handler()
async def create_location_type(cmd: commands.ontologies.CreateLocationType, uow: AbstractUnitOfWork):
    async with uow.get_uow(user_id=cmd.agent_id) as uow_holder:
        ontology_service = uow_holder.ontology
        entry_input = LocationTypeInput(
            name=cmd.name,
            description=cmd.description,
            abbreviation=cmd.abbreviation,
            synonyms=cmd.synonyms or [],
            authors=cmd.author_ids or [],
            references=cmd.reference_ids or []
        )
        entry = await ontology_service.create_entry(entry_input, cmd.parent_ids, cmd.child_ids)
        for term_id in cmd.term_ids or []:
            await ontology_service.link_to_term(source_id=entry.id, source_label=entry.label, term_id=term_id)
        await uow_holder.commit()


@handlers.command_handler()
async def create_design(cmd: commands.ontologies.CreateDesign, uow: AbstractUnitOfWork):
    async with uow.get_uow(user_id=cmd.agent_id) as uow_holder:
        ontology_service = uow_holder.ontology
        entry_input = DesignInput(
            name=cmd.name,
            description=cmd.description,
            abbreviation=cmd.abbreviation,
            synonyms=cmd.synonyms or [],
            authors=cmd.author_ids or [],
            references=cmd.reference_ids or []
        )
        entry = await ontology_service.create_entry(entry_input, cmd.parent_ids, cmd.child_ids)
        for term_id in cmd.term_ids or []:
            await ontology_service.link_to_term(source_id=entry.id, source_label=entry.label, term_id=term_id)
        await uow_holder.commit()


@handlers.command_handler()
async def create_layout_type(cmd: commands.ontologies.CreateLayoutType, uow: AbstractUnitOfWork):
    async with uow.get_uow(user_id=cmd.agent_id) as uow_holder:
        ontology_service = uow_holder.ontology
        entry_input = LayoutTypeInput(
            name=cmd.name,
            description=cmd.description,
            abbreviation=cmd.abbreviation,
            synonyms=cmd.synonyms or [],
            axes=cmd.axes or [],
            authors=cmd.author_ids or [],
            references=cmd.reference_ids or []
        )
        entry = await ontology_service.create_entry(entry_input, cmd.parent_ids, cmd.child_ids)
        for term_id in cmd.term_ids or []:
            await ontology_service.link_to_term(source_id=entry.id, source_label=entry.label, term_id=term_id)
        await uow_holder.commit()

def prepare_attr_relationship_updates(
        entry_id: int,
        entry_label: OntologyEntryLabel,
        attr: str,
        value: List[int]|int,
        existing_relationships,
        relationships_to_draft: List[OntologyRelationshipBase],
        relationships_to_deprecate: List[int],
        relationships_to_update: List[OntologyRelationshipBase]
):
    # first establish the specified source and target labels and ids and the relationship label for the given attribute
    if attr in ['parent_ids', 'child_ids']:
        source_label = entry_label
        target_label = entry_label
        relationship_label = OntologyRelationshipLabel.PARENT_OF
        if attr == 'parent_ids':
            source_ids = [entry_id]
            if not isinstance(value, list):
                raise ValueError('parent_ids must be a list')
            target_ids = value
        else:
            if not isinstance(value, list):
                raise ValueError('child_ids must be a list')
            source_ids = value
            target_ids = [entry_id]
    else:
        other_label = ontology_mapper.get_other_label_from_attribute(attr)
        relationship_label = ontology_mapper.get_relationship_label(entry_label, other_label)
        valid_sources, valid_targets = ontology_mapper.relationship_to_valid_source_and_target().get(relationship_label)
        if entry_label in valid_sources and other_label in valid_targets:
            source_label = entry_label
            source_ids = [entry_id]
            target_label = other_label
            target_ids = value if isinstance(value, list) else [value]
        elif other_label in valid_sources and entry_label in valid_targets:
            source_label = other_label
            source_ids = value if isinstance(value, list) else [value]
            target_label = entry_label
            target_ids = [entry_id]
        else:
            raise ValueError(f'Relationship between {entry_label} and {other_label} is not valid.')

    for relationship in existing_relationships:
        if all([
            relationship.source_id in source_ids,
            relationship.target_id in target_ids,
            relationship.label == relationship_label
        ]):
            continue
        else:
            relationships_to_deprecate.append(relationship.id)

    submitted_relationships = []
    i = 0
    for source_id in source_ids:
        for target_id in target_ids:
            i += 1
            submitted_relationships.append(
                OntologyRelationshipBase.relationship_from_label(
                    source_id=source_id,
                    target_id=target_id,
                    source_label=source_label,
                    target_label=target_label,
                    label=relationship_label,
                    rank=i
                )
            )

    for submitted in submitted_relationships:
        # check if already exists
        exists = False
        for existing in existing_relationships:
            if all([
                submitted.source_id == existing.source_id,
                submitted.target_id == existing.target_id,
                submitted.label == existing.label
            ]):
                exists = True
                if submitted.label == OntologyRelationshipLabel.HAS_CATEGORY:
                    if not submitted.rank == existing.rank:
                        relationships_to_update.append(submitted)
        if not exists:
            relationships_to_draft.append(submitted)

async def update_relationships(
        ontology_service: OntologyApplicationService,
        command: commands.Command,
        entry: OntologyEntryStored
):
    relationship_setters = [
        'parent_ids',
        'child_ids',
        'subject_ids',
        'trait_ids',
        'trait_id',
        'variable_ids',
        'condition_ids',
        'condition_id',
        'scale_ids',
        'scale_id',
        'category_ids',
        'observation_method_ids',
        'observation_method_id',
        'control_method_ids',
        'control_method_id',
        'factor_ids',
        'event_ids',
        'location_type_ids',
        'layout_type_ids',
        'design_ids',
        'role_ids',
        'title_ids',
    ]
    relationships = None
    relationships_to_draft: List[OntologyRelationshipBase] = []
    relationships_to_deprecate: List[int] = []
    relationships_to_update: List[OntologyRelationshipBase] = []
    for attr in relationship_setters:
        if hasattr(command, attr):
            new_attr_value = getattr(command, attr)
            if new_attr_value is not None:

                if relationships is None:
                    relationships = [rel async for rel in ontology_service.get_relationships(entry_ids=[command.id])]

                prepare_attr_relationship_updates(
                    entry_id=entry.id,
                    entry_label=entry.label,
                    attr=attr,
                    value=new_attr_value,
                    existing_relationships=relationships,
                    relationships_to_draft=relationships_to_draft,
                    relationships_to_deprecate=relationships_to_deprecate,
                    relationships_to_update=relationships_to_update
                )

    for relationship in relationships_to_draft:
        await ontology_service.create_relationship(relationship)
    if relationships_to_deprecate:
        await ontology_service.deprecate_relationships(relationships_to_deprecate)
    for relationship in relationships_to_update:
        await ontology_service.update_relationship(relationship)

def update_attributes(entry: OntologyEntryStored, cmd: commands.Command):
    if cmd.name:
        entry.name = cmd.name
    if cmd.abbreviation:
        entry.abbreviation = cmd.abbreviation
    if cmd.synonyms:
        entry.synonyms = cmd.synonyms
    if cmd.description:
        entry.description = cmd.description
    if cmd.author_ids:
        entry.authors = cmd.author_ids
    if cmd.reference_ids:
        entry.references = cmd.reference_ids

async def update_by_command(cmd: commands.Command, uow: AbstractUnitOfWork):
    async with uow.get_uow(user_id=cmd.agent_id) as uow_holder:
        ontology_service = uow_holder.ontology
        entry = await ontology_service.get_entry(cmd.id)
        update_attributes(entry, cmd)
        await ontology_service.update_entry(entry)
        await update_relationships(ontology_service, cmd, entry)
        await uow_holder.commit()

"""Update handlers"""
@handlers.command_handler()
async def update_term(cmd: commands.ontologies.UpdateTerm, uow: AbstractUnitOfWork):
    await update_by_command(cmd, uow)

@handlers.command_handler()
async def update_subject(cmd: commands.ontologies.UpdateSubject, uow: AbstractUnitOfWork):
    await update_by_command(cmd, uow)

@handlers.command_handler()
async def update_trait(cmd: commands.ontologies.UpdateTrait, uow: AbstractUnitOfWork):
    await update_by_command(cmd, uow)

@handlers.command_handler()
async def update_condition(cmd: commands.ontologies.UpdateCondition, uow: AbstractUnitOfWork):
    await update_by_command(cmd, uow)

@handlers.command_handler()
async def update_scale(cmd: commands.ontologies.UpdateScale, uow: AbstractUnitOfWork):
    await update_by_command(cmd, uow)

@handlers.command_handler()
async def update_category(cmd: commands.ontologies.UpdateCategory, uow: AbstractUnitOfWork):
    await update_by_command(cmd, uow)

@handlers.command_handler()
async def update_observation_method(cmd: commands.ontologies.UpdateObservationMethod, uow: AbstractUnitOfWork):
    await update_by_command(cmd, uow)


@handlers.command_handler()
async def update_variable(cmd: commands.ontologies.UpdateVariable, uow: AbstractUnitOfWork):
    await update_by_command(cmd, uow)

@handlers.command_handler()
async def update_control_method(cmd: commands.ontologies.UpdateControlMethod, uow: AbstractUnitOfWork):
    await update_by_command(cmd, uow)

@handlers.command_handler()
async def update_factor(cmd: commands.ontologies.UpdateFactor, uow: AbstractUnitOfWork):
    await update_by_command(cmd, uow)

@handlers.command_handler()
async def update_event_type(cmd: commands.ontologies.UpdateEventType, uow: AbstractUnitOfWork):
    await update_by_command(cmd, uow)

@handlers.command_handler()
async def update_location_type(cmd: commands.ontologies.UpdateLocationType, uow: AbstractUnitOfWork):
    await update_by_command(cmd, uow)

@handlers.command_handler()
async def update_design(cmd: commands.ontologies.UpdateDesign, uow: AbstractUnitOfWork):
    await update_by_command(cmd, uow)

@handlers.command_handler()
async def update_layout_type(cmd: commands.ontologies.UpdateLayoutType, uow: AbstractUnitOfWork):
    await update_by_command(cmd, uow)

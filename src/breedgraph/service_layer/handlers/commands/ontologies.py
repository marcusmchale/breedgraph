from src.breedgraph.domain import commands
from src.breedgraph.domain.model.ontology import *

from src.breedgraph.service_layer.infrastructure import AbstractUnitOfWork

from ..registry import handlers

import logging

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
            cmd.subject_ids,
            cmd.scale_ids,
            cmd.category_ids,
            cmd.observation_method_ids,
            cmd.trait_ids,
            cmd.variable_ids,
            cmd.control_method_ids,
            cmd.condition_ids,
            cmd.factor_ids,
            cmd.event_ids,
            cmd.location_type_ids,
            cmd.layout_type_ids,
            cmd.design_ids,
            cmd.role_ids,
            cmd.title_ids,
        ]
        for id_list in to_link:
            for id_ in id_list or []:
                await ontology_service.link_to_term(source_id=id_, term_id=entry.id)
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
        entry = await ontology_service.create_entry(entry, cmd.parent_ids, cmd.child_ids)
        for term_id in cmd.term_ids or []:
            await ontology_service.link_to_term(source_id=entry.id, term_id=term_id)
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
            await ontology_service.link_to_term(source_id=entry.id, term_id=term_id)
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
            await ontology_service.link_to_term(source_id=entry.id, term_id=term_id)
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
            await ontology_service.link_to_term(source_id=entry.id, term_id=term_id)
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
            await ontology_service.link_to_term(source_id=entry.id, term_id=term_id)
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
            await ontology_service.link_to_term(source_id=entry.id, term_id=term_id)
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
            await ontology_service.link_to_term(source_id=entry.id, term_id=term_id)
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
            await ontology_service.link_to_term(source_id=entry.id, term_id=term_id)
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
            references = cmd.references or []
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
            await ontology_service.link_to_term(source_id=entry.id, term_id=term_id)
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
            await ontology_service.link_to_term(source_id=entry.id, term_id=term_id)
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
            await ontology_service.link_to_term(source_id=entry.id, term_id=term_id)
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
            await ontology_service.link_to_term(source_id=entry.id, term_id=term_id)
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
            await ontology_service.link_to_term(source_id=entry.id, term_id=term_id)
        await uow_holder.commit()
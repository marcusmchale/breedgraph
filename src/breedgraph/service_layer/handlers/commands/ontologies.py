import tests.integration.conftest
from src.breedgraph.domain import commands
from src.breedgraph.domain.model.ontology import *

from src.breedgraph.service_layer.infrastructure import AbstractUnitOfWork

from ..registry import handlers

import logging

logger = logging.getLogger(__name__)

@handlers.command_handler
async def commit_ontology(cmd: commands.ontologies.CommitOntology, uow: AbstractUnitOfWork):
    async with uow.get_uow() as uow_holder:
        ontology_service = uow_holder.ontology
        version_change = VersionChange(cmd.version_change)
        ontology_service.commit_version(
            version_change = version_change,
            comment = cmd.comment,
            licence_reference = cmd.licence,
            copyright_reference = cmd.copyright
        )
        await uow_holder.commit()

@handlers.command_handler
async def create_term(cmd: commands.ontologies.CreateTerm, uow: AbstractUnitOfWork):
    async with uow.get_uow(user_id=cmd.user) as uow_holder:
        ontology_service = uow_holder.ontology
        entry = TermInput(
            name=cmd.name,
            description=cmd.description,
            abbreviation=cmd.abbreviation,
            synonyms=cmd.synonyms or [],
            authors=cmd.authors or [],
            references=cmd.references or []
        )
        await ontology_service.create_entry(entry, cmd.parents, cmd.children)
        await uow_holder.commit()


@handlers.command_handler()
async def create_subject(cmd: commands.ontologies.CreateSubject, uow: AbstractUnitOfWork):
    async with uow.get_uow(user_id=cmd.user) as uow_holder:
        ontology_service = uow_holder.ontology
        entry = SubjectInput(
            name=cmd.name,
            description=cmd.description,
            abbreviation=cmd.abbreviation,
            synonyms=cmd.synonyms or [],
            authors=cmd.authors or [],
            references=cmd.references or []
        )
        await ontology_service.create_entry(entry, cmd.parents, cmd.children)
        await uow_holder.commit()

@handlers.command_handler()
async def create_trait(cmd: commands.ontologies.CreateTrait, uow: AbstractUnitOfWork):
    async with uow.get_uow(user_id=cmd.user) as uow_holder:
        ontology_service = uow_holder.ontology
        entry = TraitInput(
            name=cmd.name,
            description=cmd.description,
            abbreviation=cmd.abbreviation,
            synonyms=cmd.synonyms or [],
            authors=cmd.authors or [],
            references=cmd.references or []
        )
        await ontology_service.create_trait(entry, cmd.parents, cmd.children, subjects=cmd.subjects)
        await uow_holder.commit()


@handlers.command_handler()
async def create_condition(cmd: commands.ontologies.CreateCondition, uow: AbstractUnitOfWork):
    async with uow.get_uow(user_id=cmd.user) as uow_holder:
        ontology_service = uow_holder.ontology
        entry = ConditionInput(
            name=cmd.name,
            description=cmd.description,
            abbreviation=cmd.abbreviation,
            synonyms=cmd.synonyms or [],
            authors=cmd.authors or [],
            references=cmd.references or []
        )
        await ontology_service.create_condition(entry, cmd.parents, cmd.children, subjects=cmd.subjects)
        await uow_holder.commit()


@handlers.command_handler()
async def create_scale(cmd: commands.ontologies.CreateScale, uow: AbstractUnitOfWork):
    async with uow.get_uow(user_id=cmd.user) as uow_holder:
        ontology_service = uow_holder.ontology
        entry = ScaleInput(
            name=cmd.name,
            description=cmd.description,
            abbreviation=cmd.abbreviation,
            synonyms=cmd.synonyms or [],
            authors=cmd.authors or [],
            references=cmd.references or [],
            scale_type=cmd.scale_type
        )
        await ontology_service.create_entry(entry, cmd.parents, cmd.children)
        await uow_holder.commit()

@handlers.command_handler()
async def create_scale_category(cmd: commands.ontologies.CreateScaleCategory, uow: AbstractUnitOfWork):
    async with uow.get_uow(user_id=cmd.user) as uow_holder:
        ontology_service = uow_holder.ontology
        entry = ScaleCategoryInput(
            name=cmd.name,
            description=cmd.description,
            abbreviation=cmd.abbreviation,
            synonyms=cmd.synonyms or [],
            authors=cmd.authors or [],
            references=cmd.references or []
        )

        await ontology_service.create_entry(entry, cmd.parents, cmd.children)
        await uow_holder.commit()


@handlers.command_handler()
async def create_observation_method(cmd: commands.ontologies.CreateObservationMethod, uow: AbstractUnitOfWork):
    async with uow.get_uow(user_id=cmd.user) as uow_holder:
        ontology_service = uow_holder.ontology
        entry = ObservationMethodInput(
            name=cmd.name,
            description=cmd.description,
            abbreviation=cmd.abbreviation,
            synonyms=cmd.synonyms or [],
            authors=cmd.authors or [],
            references=cmd.references or [],
            observation_type=cmd.observation_type
        )
        await ontology_service.create_entry(entry, cmd.parents, cmd.children)
        await uow_holder.commit()


@handlers.command_handler()
async def create_variable(cmd: commands.ontologies.CreateVariable, uow: AbstractUnitOfWork):
    async with uow.get_uow(user_id=cmd.user) as uow_holder:
        ontology_service = uow_holder.ontology
        entry = VariableInput(
            name=cmd.name,
            description=cmd.description,
            abbreviation=cmd.abbreviation,
            synonyms=cmd.synonyms or [],
            authors=cmd.authors or [],
            references=cmd.references or []
        )
        await ontology_service.create_variable(
            entry,
            trait_id = cmd.trait_id,
            observation_method_id = cmd.observation_method_id,
            scale_id = cmd.scale_id,
            parents = cmd.parents,
            children =cmd.children
        )
        await uow_holder.commit()


@handlers.command_handler()
async def create_control_method(cmd: commands.ontologies.CreateControlMethod, uow: AbstractUnitOfWork):
    async with uow.get_uow(user_id=cmd.user) as uow_holder:
        ontology_service = uow_holder.ontology
        entry = ControlMethodInput(
            name=cmd.name,
            description=cmd.description,
            abbreviation=cmd.abbreviation,
            synonyms=cmd.synonyms or [],
            authors=cmd.authors or [],
            references=cmd.references or []
        )
        await ontology_service.create_entry(entry, cmd.parents, cmd.children)
        await uow_holder.commit()


@handlers.command_handler()
async def create_factor(cmd: commands.ontologies.CreateFactor, uow: AbstractUnitOfWork):
    async with uow.get_uow(user_id=cmd.user) as uow_holder:
        ontology_service = uow_holder.ontology
        entry = FactorInput(
            name=cmd.name,
            description=cmd.description,
            abbreviation=cmd.abbreviation,
            synonyms=cmd.synonyms or [],
            authors=cmd.authors or [],
            references = cmd.references or []
        )

        await ontology_service.create_factor(
            entry,
            condition_id = cmd.condition_id,
            control_method_id = cmd.control_method_id,
            scale_id = cmd.scale_id,
            parents = cmd.parents,
            children = cmd.children
        )
        await uow_holder.commit()


@handlers.command_handler()
async def create_event_type(cmd: commands.ontologies.CreateEventType, uow: AbstractUnitOfWork):
    async with uow.get_uow(user_id=cmd.user) as uow_holder:
        ontology_service = uow_holder.ontology
        entry = EventTypeInput(  # Using EventTypeInput
            name=cmd.name,
            description=cmd.description,
            abbreviation=cmd.abbreviation,
            synonyms=cmd.synonyms or [],
            authors=cmd.authors or [],
            references=cmd.references or []
        )
        await ontology_service.create_event_type(
            entry,
            parents = cmd.parents,
            children = cmd.children,
            variables = cmd.variables,
            factors = cmd.factors
        )
        await uow_holder.commit()


@handlers.command_handler()
async def create_germplasm_method(cmd: commands.ontologies.CreateGermplasmMethod, uow: AbstractUnitOfWork):
    async with uow.get_uow(user_id=cmd.user) as uow_holder:
        ontology_service = uow_holder.ontology
        entry = GermplasmMethodInput(
            name=cmd.name,
            description=cmd.description,
            abbreviation=cmd.abbreviation,
            synonyms=cmd.synonyms or [],
            authors=cmd.authors or [],
            references=cmd.references or []
        )
        await ontology_service.create_entry(entry, cmd.parents, cmd.children)
        await uow_holder.commit()


@handlers.command_handler()
async def create_location_type(cmd: commands.ontologies.CreateLocationType, uow: AbstractUnitOfWork):
    async with uow.get_uow(user_id=cmd.user) as uow_holder:
        ontology_service = uow_holder.ontology
        entry = LocationTypeInput(
            name=cmd.name,
            description=cmd.description,
            abbreviation=cmd.abbreviation,
            synonyms=cmd.synonyms or [],
            authors=cmd.authors or [],
            references=cmd.references or []
        )
        await ontology_service.create_entry(entry, cmd.parents, cmd.children)
        await uow_holder.commit()


@handlers.command_handler()
async def create_design(cmd: commands.ontologies.CreateDesign, uow: AbstractUnitOfWork):
    async with uow.get_uow(user_id=cmd.user) as uow_holder:
        ontology_service = uow_holder.ontology
        entry = DesignInput(
            name=cmd.name,
            description=cmd.description,
            abbreviation=cmd.abbreviation,
            synonyms=cmd.synonyms or [],
            authors=cmd.authors or [],
            references=cmd.references or []
        )
        await ontology_service.create_entry(entry, cmd.parents, cmd.children)
        await uow_holder.commit()


@handlers.command_handler()
async def create_layout_type(cmd: commands.ontologies.CreateLayoutType, uow: AbstractUnitOfWork):
    async with uow.get_uow(user_id=cmd.user) as uow_holder:
        ontology_service = uow_holder.ontology
        entry = LayoutTypeInput(
            name=cmd.name,
            description=cmd.description,
            abbreviation=cmd.abbreviation,
            synonyms=cmd.synonyms or [],
            authors=cmd.authors or [],
            references=cmd.references or []
        )
        await ontology_service.create_entry(entry, cmd.parents, cmd.children)
        await uow_holder.commit()
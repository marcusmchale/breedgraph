from src.breedgraph.service_layer import unit_of_work
from src.breedgraph.domain import commands
from src.breedgraph.domain.model.ontology import (
    Term,
    Subject,
    LocationType,
    LayoutType,
    Design,
    Role,
    Title,
    GermplasmMethod,
    ObservationMethod,
    ObservationMethodType,
    Scale,
    ScaleType,
    ScaleCategory,
    Trait,
    Variable,
    Condition,
    Parameter,
    Exposure,
    EventType
)

import logging

logger = logging.getLogger(__name__)

async def add_term(
        cmd: commands.ontologies.AddTerm,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow.get_repositories() as uow:
        ontology = await uow.ontologies.get()
        term = Term(
            name = cmd.name,
            description=cmd.description,
            abbreviation=cmd.abbreviation,
            synonyms = cmd.synonyms if cmd.authors is not None else list(),
            authors = cmd.authors if cmd.authors is not None else list(),
            references = cmd.references if cmd.references is not None else list()
        )
        ontology.add_term(term, parents=cmd.parents, children=cmd.children)
        await uow.commit()

async def add_subject(
        cmd: commands.ontologies.AddSubject,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow.get_repositories() as uow:
        ontology = await uow.ontologies.get()
        subject = Subject(
            name = cmd.name,
            description=cmd.description,
            abbreviation=cmd.abbreviation,
            synonyms = cmd.synonyms if cmd.authors is not None else list(),
            authors = cmd.authors if cmd.authors is not None else list(),
            references = cmd.references if cmd.references is not None else list()
        )
        ontology.add_subject(subject, parents=cmd.parents, children=cmd.children)
        await uow.commit()

async def add_location_type(
        cmd: commands.ontologies.AddLocationType,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow.get_repositories() as uow:
        ontology = await uow.ontologies.get()
        location_type = LocationType(
            name = cmd.name,
            description=cmd.description,
            abbreviation=cmd.abbreviation,
            synonyms = cmd.synonyms if cmd.authors is not None else list(),
            authors = cmd.authors if cmd.authors is not None else list(),
            references = cmd.references if cmd.references is not None else list()
        )
        ontology.add_location_type(location_type, parents=cmd.parents, children=cmd.children)
        await uow.commit()

async def add_layout_type(
        cmd: commands.ontologies.AddLayoutType,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow.get_repositories() as uow:
        ontology = await uow.ontologies.get()
        layout_type = LayoutType(
            name = cmd.name,
            description=cmd.description,
            abbreviation=cmd.abbreviation,
            synonyms = cmd.synonyms if cmd.authors is not None else list(),
            authors = cmd.authors if cmd.authors is not None else list(),
            references = cmd.references if cmd.references is not None else list()
        )
        ontology.add_layout_type(layout_type, parents=cmd.parents, children=cmd.children)
        await uow.commit()

async def add_design_type(
        cmd: commands.ontologies.AddDesignType,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow.get_repositories() as uow:
        ontology = await uow.ontologies.get()
        design = Design(
            name = cmd.name,
            description=cmd.description,
            abbreviation=cmd.abbreviation,
            synonyms = cmd.synonyms if cmd.authors is not None else list(),
            authors = cmd.authors if cmd.authors is not None else list(),
            references = cmd.references if cmd.references is not None else list()
        )
        ontology.add_design(design, parents=cmd.parents, children=cmd.children)
        await uow.commit()

async def add_role(
        cmd: commands.ontologies.AddRole,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow.get_repositories() as uow:
        ontology = await uow.ontologies.get()
        role = Role(
            name = cmd.name,
            description=cmd.description,
            abbreviation=cmd.abbreviation,
            synonyms = cmd.synonyms if cmd.authors is not None else list(),
            authors = cmd.authors if cmd.authors is not None else list(),
            references = cmd.references if cmd.references is not None else list()
        )
        ontology.add_role(role, parents=cmd.parents, children=cmd.children)
        await uow.commit()

async def add_title(
        cmd: commands.ontologies.AddTitle,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow.get_repositories() as uow:
        ontology = await uow.ontologies.get()
        title = Title(
            name = cmd.name,
            description=cmd.description,
            abbreviation=cmd.abbreviation,
            synonyms = cmd.synonyms if cmd.authors is not None else list(),
            authors = cmd.authors if cmd.authors is not None else list(),
            references = cmd.references if cmd.references is not None else list()
        )
        ontology.add_title(title, parents=cmd.parents, children=cmd.children)
        await uow.commit()

async def add_germplasm_method(
        cmd: commands.ontologies.AddGermplasmMethod,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow.get_repositories() as uow:
        ontology = await uow.ontologies.get()
        germplasm_method = GermplasmMethod(
            name = cmd.name,
            description=cmd.description,
            abbreviation=cmd.abbreviation,
            synonyms = cmd.synonyms if cmd.authors is not None else list(),
            authors = cmd.authors if cmd.authors is not None else list(),
            references = cmd.references if cmd.references is not None else list()
        )
        ontology.add_germplasm_method(germplasm_method, parents=cmd.parents, children=cmd.children)
        await uow.commit()

async def add_observation_method(
        cmd: commands.ontologies.AddObservationMethod,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow.get_repositories() as uow:
        ontology = await uow.ontologies.get()
        observation_method = ObservationMethod(
            type = ObservationMethodType[cmd.method_type],
            name = cmd.name,
            description=cmd.description,
            abbreviation=cmd.abbreviation,
            synonyms = cmd.synonyms if cmd.authors is not None else list(),
            authors = cmd.authors if cmd.authors is not None else list(),
            references = cmd.references if cmd.references is not None else list()
        )
        ontology.add_observation_method(observation_method, parents=cmd.parents, children=cmd.children)
        await uow.commit()

async def add_scale(
        cmd: commands.ontologies.AddScale,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow.get_repositories() as uow:
        ontology = await uow.ontologies.get()
        scale = Scale(
            type = ScaleType[cmd.scale_type],
            name = cmd.name,
            description=cmd.description,
            abbreviation=cmd.abbreviation,
            synonyms = cmd.synonyms if cmd.authors is not None else list(),
            authors = cmd.authors if cmd.authors is not None else list(),
            references = cmd.references if cmd.references is not None else list()
        )
        ontology.add_scale(scale, parents=cmd.parents, children=cmd.children)
        await uow.commit()


async def add_category(
        cmd: commands.ontologies.AddCategory,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow.get_repositories() as uow:
        ontology = await uow.ontologies.get()
        category = ScaleCategory(
            name = cmd.name,
            description=cmd.description,
            abbreviation=cmd.abbreviation,
            synonyms = cmd.synonyms if cmd.authors is not None else list(),
            authors = cmd.authors if cmd.authors is not None else list(),
            references = cmd.references if cmd.references is not None else list()
        )
        ontology.add_category(category, scale=cmd.scale, rank=cmd.rank, parents=cmd.parents, children=cmd.children)
        await uow.commit()

async def add_trait(
        cmd: commands.ontologies.AddTrait,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow.get_repositories() as uow:
        ontology = await uow.ontologies.get()
        trait = Trait(
            name = cmd.name,
            description=cmd.description,
            abbreviation=cmd.abbreviation,
            synonyms = cmd.synonyms if cmd.authors is not None else list(),
            authors = cmd.authors if cmd.authors is not None else list(),
            references = cmd.references if cmd.references is not None else list()
        )
        ontology.add_trait(trait, subjects=cmd.subjects, parents=cmd.parents, children=cmd.children)
        await uow.commit()

async def add_variable(
        cmd: commands.ontologies.AddVariable,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow.get_repositories() as uow:
        ontology = await uow.ontologies.get()
        variable = Variable(
            name = cmd.name,
            description=cmd.description,
            abbreviation=cmd.abbreviation,
            synonyms = cmd.synonyms if cmd.authors is not None else list(),
            authors = cmd.authors if cmd.authors is not None else list(),
            references = cmd.references if cmd.references is not None else list()
        )
        ontology.add_variable(variable, trait=cmd.trait, method=cmd.method, scale=cmd.scale, parents=cmd.parents, children=cmd.children)
        await uow.commit()

async def add_condition(
        cmd: commands.ontologies.AddCondition,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow.get_repositories() as uow:
        ontology = await uow.ontologies.get()
        condition = Condition(
            name = cmd.name,
            description=cmd.description,
            abbreviation=cmd.abbreviation,
            synonyms = cmd.synonyms if cmd.authors is not None else list(),
            authors = cmd.authors if cmd.authors is not None else list(),
            references = cmd.references if cmd.references is not None else list()
        )
        ontology.add_condition(condition, parents=cmd.parents, children=cmd.children)
        await uow.commit()

async def add_parameter(
        cmd: commands.ontologies.AddParameter,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow.get_repositories() as uow:
        ontology = await uow.ontologies.get()
        parameter = Parameter(
            name = cmd.name,
            description=cmd.description,
            abbreviation=cmd.abbreviation,
            synonyms = cmd.synonyms if cmd.authors is not None else list(),
            authors = cmd.authors if cmd.authors is not None else list(),
            references = cmd.references if cmd.references is not None else list()
        )
        ontology.add_parameter(parameter, condition=cmd.condition, method=cmd.method, scale=cmd.scale, parents=cmd.parents, children=cmd.children)
        await uow.commit()

async def add_exposure(
        cmd: commands.ontologies.AddExposure,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow.get_repositories() as uow:
        ontology = await uow.ontologies.get()
        exposure = Exposure(
            name = cmd.name,
            description=cmd.description,
            abbreviation=cmd.abbreviation,
            synonyms = cmd.synonyms if cmd.authors is not None else list(),
            authors = cmd.authors if cmd.authors is not None else list(),
            references = cmd.references if cmd.references is not None else list()
        )
        ontology.add_exposure(exposure, parents=cmd.parents, children=cmd.children)
        await uow.commit()

async def add_event(
        cmd: commands.ontologies.AddEvent,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow.get_repositories() as uow:
        ontology = await uow.ontologies.get()
        event = EventType(
            name = cmd.name,
            description=cmd.description,
            abbreviation=cmd.abbreviation,
            synonyms = cmd.synonyms if cmd.authors is not None else list(),
            authors = cmd.authors if cmd.authors is not None else list(),
            references = cmd.references if cmd.references is not None else list()
        )
        ontology.add_event(event, exposure=cmd.exposure, method=cmd.method, scale=cmd.scale, parents=cmd.parents, children=cmd.children)
        await uow.commit()

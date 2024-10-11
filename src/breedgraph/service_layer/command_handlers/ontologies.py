from src.breedgraph.service_layer import unit_of_work
from src.breedgraph.domain import commands
from src.breedgraph.domain.model.ontology import OntologyEntry, Scale, ScaleType, ObservationMethod, ObservationMethodType, LayoutType
import logging

logger = logging.getLogger(__name__)

async def add_ontology_entry(
        cmd: commands.ontologies.AddOntologyEntry,
        uow: unit_of_work.AbstractUnitOfWork
):
    kwargs = cmd.model_dump()
    label = kwargs.pop('label')
    ontology_entry_classes_map = {i.label: i for i in OntologyEntry.__subclasses__()}
    entry_class = ontology_entry_classes_map.get(label, None)
    if entry_class is None:
        raise ValueError("Label is not recognised as a subclass of OntologyEntry")

    synonyms = [] if kwargs.get('synonyms') is None else kwargs['synonyms']
    authors = [] if kwargs.get('authors') is None else kwargs['authors']
    references = [] if kwargs.get('references') is None else kwargs['references']


    if entry_class == Scale:
        entry = entry_class(
            name=kwargs.pop('name'),
            description=kwargs.pop('description'),
            abbreviation=kwargs.pop('abbreviation'),
            synonyms=synonyms,
            authors=authors,
            references=references,
            scale_type=kwargs.pop('scale_type')
        )
    elif entry_class == ObservationMethod:
        entry = entry_class(
            name=kwargs.pop('name'),
            description=kwargs.pop('description'),
            abbreviation=kwargs.pop('abbreviation'),
            synonyms=synonyms,
            authors=authors,
            references=references,
            observation_type=kwargs.pop('observation_type')
        )
    elif entry_class == LayoutType:
        entry = entry_class(
            name=kwargs.pop('name'),
            description=kwargs.pop('description'),
            abbreviation=kwargs.pop('abbreviation'),
            synonyms=synonyms,
            authors=authors,
            references=references,
            axes=kwargs.pop('axes')
        )
    else:
        entry = entry_class(
            name=kwargs.pop('name'),
            description=kwargs.pop('description'),
            abbreviation=kwargs.pop('abbreviation'),
            synonyms=synonyms,
            authors=authors,
            references=references
        )
    async with uow.get_repositories() as uow:
        ontology = await uow.ontologies.get()
        ontology.add_entry(entry, **kwargs)
        await uow.commit()

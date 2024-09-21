from src.breedgraph.service_layer import unit_of_work
from src.breedgraph.domain import commands
from src.breedgraph.domain.model.ontology import OntologyEntry
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

    entry = entry_class(
        name=kwargs.pop('name'),
        description=kwargs.pop('description'),
        abbreviation=kwargs.pop('abbreviation'),
        synonyms=kwargs.pop('synonyms', []),
        authors=kwargs.pop('authors', []),
        references=kwargs.pop('references', [])
    )
    async with uow.get_repositories() as uow:
        ontology = await uow.ontologies.get()
        ontology.add_entry(entry, **kwargs)
        await uow.commit()

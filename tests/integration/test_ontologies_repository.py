import pytest

from src.breedgraph.domain.model.ontologies import (
    Ontology,
    Version,
    Term,
    Subject,
    Trait,
    Method, MethodType,
    Scale, ScaleType, Category, Scale,
    Variable
)

from src.breedgraph.adapters.repositories.ontologies import Neo4jOntologyRepository

from src.breedgraph.custom_exceptions import NoResultFoundError
from typing import List

@pytest.mark.asyncio(scope="session")
async def test_create_and_get_ontology(neo4j_tx, lorem_text_generator):
    ontology = Ontology(version=Version(major=0, minor=0, patch=0, comment="Test"))
    repo = Neo4jOntologyRepository(neo4j_tx)
    stored_ontology = await repo.create(ontology)
    assert stored_ontology.root.id
    retrieved_ontology = await repo.get(version_id=stored_ontology.version.id)
    assert retrieved_ontology.version == ontology.version

@pytest.mark.asyncio(scope="session")
async def test_create_term(neo4j_tx, lorem_text_generator):
    repo = Neo4jOntologyRepository(neo4j_tx)
    ontology = await repo.get(version_id=1)
    new_term = Term(name=lorem_text_generator.new_text())
    ontology.add_entry(new_term)
    await repo.update_seen()
    ontology = await repo.get(version_id=1)
    assert next(ontology.get_by_class(Term))
    assert next(ontology.get_by_name(new_term.name)).id > 0

@pytest.mark.asyncio(scope="session")
async def test_add_synonym_to_term(neo4j_tx, lorem_text_generator):
    repo = Neo4jOntologyRepository(neo4j_tx)
    ontology = await repo.get(version_id=1)
    term = ontology.entries[1]
    synonym = lorem_text_generator.new_text()
    term.synonyms.append(synonym)
    await repo.update_seen()
    ontology = await repo.get(version_id=1)
    assert len(ontology.entries) == 1
    assert synonym in next(ontology.get_by_name(term.name)).synonyms

@pytest.mark.asyncio(scope="session")
async def test_rename_term_causes_fork(neo4j_tx, lorem_text_generator):
    repo = Neo4jOntologyRepository(neo4j_tx)
    ontology = await repo.get(version_id=1)
    term = ontology.entries[1]
    term.name = lorem_text_generator.new_text()
    await repo.update_seen()
    ontology = await repo.get(version_id=1)
    assert next(ontology.get_by_name(term.name))
    assert len(list(ontology.get_by_class(Term))) == 2

@pytest.mark.asyncio(scope="session")
async def test_create_subject(neo4j_tx, lorem_text_generator):
    repo = Neo4jOntologyRepository(neo4j_tx)
    ontology = await repo.get(version_id=1)
    term_id = next(ontology.get_by_class(Term)).id
    new_subject = Subject(name=lorem_text_generator.new_text(), parents=[term_id])
    ontology.add_entry(new_subject)
    await repo.update_seen()
    ontology = await repo.get(version_id=1)
    assert next(ontology.get_by_class(Subject))
    assert term_id in next(ontology.get_by_name(new_subject.name)).parents

@pytest.mark.asyncio(scope="session")
async def test_create_trait(neo4j_tx, lorem_text_generator):
    repo = Neo4jOntologyRepository(neo4j_tx)
    ontology = await repo.get(version_id=1)
    subject_id = ontology.entries[3].id
    new_trait = Trait(name=lorem_text_generator.new_text(), subjects=[subject_id])
    ontology.add_entry(new_trait)
    await repo.update_seen()
    ontology = await repo.get(version_id=1)
    assert next(ontology.get_by_class(Trait))
    assert subject_id in next(ontology.get_by_name(new_trait.name)).subjects

@pytest.mark.asyncio(scope="session")
async def test_create_method(neo4j_tx, lorem_text_generator):
    repo = Neo4jOntologyRepository(neo4j_tx)
    ontology = await repo.get(version_id=1)
    method_type = MethodType("MEASUREMENT")
    new_method = Method(name=lorem_text_generator.new_text(), type=method_type)
    ontology.add_entry(new_method)
    await repo.update_seen()
    ontology = await repo.get(version_id=1)
    assert next(ontology.get_by_class(Method))
    assert next(ontology.get_by_name(new_method.name)).type == method_type

@pytest.mark.asyncio(scope="session")
async def test_create_scale(neo4j_tx, lorem_text_generator):
    repo = Neo4jOntologyRepository(neo4j_tx)
    ontology = await repo.get(version_id=1)
    scale_type = ScaleType("NUMERICAL")
    new_scale = Scale(name=lorem_text_generator.new_text(), type=scale_type)
    ontology.add_entry(new_scale)
    await repo.update_seen()
    ontology = await repo.get(version_id=1)
    assert next(ontology.get_by_class(Scale))
    assert next(ontology.get_by_name(new_scale.name)).type == scale_type

@pytest.mark.asyncio(scope="session")
async def test_create_categorical_scale(neo4j_tx, lorem_text_generator):
    repo = Neo4jOntologyRepository(neo4j_tx)
    ontology = await repo.get(version_id=1)
    for i in range(3):
        ontology.add_entry(Category(name=lorem_text_generator.new_text()))
    await repo.update_seen()
    ontology = await repo.get(version_id=1)
    scale_type = ScaleType("NOMINAL")
    categories = [c.id for c in ontology.get_by_class(Category)]
    assert len(categories) == 3
    new_scale = Scale(name=lorem_text_generator.new_text(), type=scale_type, categories=categories)
    ontology.add_entry(new_scale)
    await repo.update_seen()
    ontology = await repo.get(version_id=1)
    assert len(list(ontology.get_by_class(Scale))) == 2
    stored_scale = next(ontology.get_by_name(new_scale.name))
    assert stored_scale.categories == categories

@pytest.mark.asyncio(scope="session")
async def test_add_category_to_scale(neo4j_tx, lorem_text_generator):
    repo = Neo4jOntologyRepository(neo4j_tx)
    ontology = await repo.get(version_id=1)
    new_category_name = lorem_text_generator.new_text()
    ontology.add_entry(Category(name=new_category_name))
    await repo.update_seen()

    ontology = await repo.get(version_id=1)
    scale = [s for s in ontology.get_by_class(Scale) if s.categories][0]
    categories = list(ontology.get_by_class(Category))
    assert len(categories) == 4
    new_category_id = [c.id for c in categories if c.id not in scale.categories][0]
    scale.categories.append(new_category_id)
    await repo.update_seen()

    ontology = await repo.get(version_id=1)
    assert len(list(ontology.get_by_class(Scale))) == 2
    assert len(scale.categories) == 4
    assert new_category_id in scale.categories

@pytest.mark.asyncio(scope="session")
async def test_create_variable(neo4j_tx, lorem_text_generator):
    repo = Neo4jOntologyRepository(neo4j_tx)
    ontology = await repo.get(version_id=1)
    trait_id = next(ontology.get_by_class(Trait)).id
    method_id = next(ontology.get_by_class(Method)).id
    scale_id = next(ontology.get_by_class(Scale)).id
    new_var = Variable(
        name=lorem_text_generator.new_text(),
        trait=trait_id,
        method=method_id,
        scale=scale_id
    )
    ontology.add_entry(new_var)
    await repo.update_seen()
    ontology = await repo.get(version_id=1)
    assert next(ontology.get_by_class(Variable))
    var = next(ontology.get_by_name(new_var.name))
    assert var.trait == trait_id
    assert var.method == method_id
    assert var.scale == scale_id

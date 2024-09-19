import pytest

from src.breedgraph.domain.model.ontology import (
    Ontology, OntologyEntry,
    Version,
    Term,
    Subject,
    Trait,
    ObservationMethod, ObservationMethodType,
    ScaleType, ScaleCategory, Scale,
    Variable,
    Condition, Parameter,
    Exposure, EventType
)


@pytest.mark.asyncio(scope="session")
async def test_get(ontologies_repo, ontology):
    latest = await ontologies_repo.get()
    by_version = await ontologies_repo.get(version_id=ontology.version.id)
    assert latest.version == by_version.version == ontology.version


@pytest.mark.asyncio(scope="session")
async def test_add_term(ontologies_repo, ontology, lorem_text_generator):
    version_copy = ontology.version.model_copy()
    new_term = Term(name=lorem_text_generator.new_text())
    ontology.add_term(new_term)
    await ontologies_repo.update_seen()
    # ensure the version has forked
    assert ontology.version > version_copy

    assert ontologies_repo.get(version_id=version_copy.id)
    assert ontology.get_entry(entry=new_term.name, label=Term.label)
    entry_id, entry = ontology.get_entry(new_term.name)
    # ensure the entry has a stored ID
    assert entry_id > 0

@pytest.mark.asyncio(scope="session")
async def test_add_synonym_to_term_causes_patch_fork(ontologies_repo, ontology, lorem_text_generator):
    version_copy = ontology.version.model_copy()

    term_id, term = ontology.get_entry(label=Term.label)
    synonym = lorem_text_generator.new_text()
    term.synonyms.append(synonym)
    await ontologies_repo.update_seen()
    # ensure version has only applied a patch fork to reflect this immaterial change
    assert ontology.version.as_tuple()[0:1] == version_copy.as_tuple()[0:1]
    assert ontology.version.as_tuple()[2] > version_copy.as_tuple()[2]
    assert len(ontology.entries) == len(ontology.entries)
    assert next(ontology.get_entries(synonym))

@pytest.mark.asyncio(scope="session")
async def test_rename_term_causes_minor_fork(ontologies_repo, ontology, lorem_text_generator):
    version_copy = ontology.version.model_copy()
    size = ontology.size
    old_term_id, term = next(ontology.get_entries(label=Term.label))
    old_name = term.name
    term.name = lorem_text_generator.new_text()
    await ontologies_repo.update_seen()
    assert ontology.version.major == version_copy.major
    assert ontology.version.minor > version_copy.minor
    assert ontology.version.patch == 0
    assert ontology.version.id == version_copy.id + 1
    # ensure the old named term is not found
    assert next(ontology.get_entries(old_name), None) is None
    # ensure the new entry has a new ID
    term_id, term = next(ontology.get_entries(term.name))
    assert term_id != old_term_id
    # ensure that the ontology hasn't grown
    assert ontology.size == size

@pytest.mark.asyncio(scope="session")
async def test_create_subject(ontologies_repo, ontology, lorem_text_generator):
    term_id, _ = next(ontology.get_entries(label=Term.label))
    new_subject = Subject(name=lorem_text_generator.new_text())
    ontology.add_subject(new_subject, parents=[term_id])
    await ontologies_repo.update_seen()
    assert next(ontology.get_entries(label=Subject.label))
    subject_id, subject = next(ontology.get_entries(new_subject.name))
    assert subject_id > 0
    assert subject.name == new_subject.name
    assert term_id in ontology.get_ancestors(subject_id)

@pytest.mark.asyncio(scope="session")
async def test_create_trait(ontologies_repo, ontology, lorem_text_generator):
    subject_id, subject = ontology.get_entry(label=Subject.label)
    new_trait = Trait(name=lorem_text_generator.new_text())
    with pytest.raises(ValueError):
        ontology.add_trait(new_trait, subjects=[])

    ontology.add_trait(new_trait, subjects=[subject.id])
    await ontologies_repo.update_seen()

    trait_id, trait = ontology.get_entry(entry=new_trait.name, label=Trait.label)
    assert ontology.get_entries(new_trait.name)
    assert trait_id > 0
    assert trait.name == new_trait.name
    subject_ids, trait_subjects = ontology.get_trait_subjects(trait_id)
    assert subject_id in subject_ids
    assert subject in trait_subjects


@pytest.mark.asyncio(scope="session")
async def test_create_method(ontologies_repo, ontology, lorem_text_generator):
    method_type = ObservationMethodType.MEASUREMENT
    new_method = ObservationMethod(name=lorem_text_generator.new_text(), type=method_type)
    ontology.add_observation_method(new_method)
    await ontologies_repo.update_seen()
    method_id, method = ontology.get_entry(entry=new_method.name, label=ObservationMethod.label)
    assert next(ontology.get_entries(new_method.name))
    assert method_id > 0
    assert method.name == new_method.name
    assert method.type == method_type

@pytest.mark.asyncio(scope="session")
async def test_create_scale(ontologies_repo, ontology, lorem_text_generator):
    scale_type = ScaleType.NUMERICAL
    new_scale = Scale(name=lorem_text_generator.new_text(), type=scale_type)
    ontology.add_scale(new_scale)
    await ontologies_repo.update_seen()
    scale_id, scale = ontology.get_entry(entry=new_scale.name, label=Scale.label)
    assert next(ontology.get_entries(new_scale.name))
    assert scale_id > 0
    assert scale.name == new_scale.name
    assert scale.type == scale_type

@pytest.mark.asyncio(scope="session")
async def test_create_nominal_categorical_scale(ontologies_repo, ontology, lorem_text_generator):
    scale_type = ScaleType.NOMINAL
    n_stored_scale = len(list(ontology.get_entries(label=Scale.label)))
    for i in range(3):
        ontology.add_category(ScaleCategory(name=lorem_text_generator.new_text()))
    await ontologies_repo.update_seen()
    category_tuples = [c for c in ontology.get_entries(label=ScaleCategory.label)]
    category_ids = [c[0] for c in category_tuples]
    categories = [c[1] for c in category_tuples]
    assert len(category_ids) == 3
    new_scale = Scale(name=lorem_text_generator.new_text(), type=scale_type)
    ontology.add_scale(new_scale, categories=category_ids)

    await ontologies_repo.update_seen()
    assert len(list(ontology.get_entries(label=Scale.label))) == n_stored_scale + 1
    scale_id, stored_scale = next(ontology.get_entries(new_scale.name))
    category_ids_retrieved, categories_retrieved, ranks = ontology.get_scale_categories(stored_scale.id)
    assert category_ids == category_ids_retrieved
    assert categories == categories_retrieved
    assert ranks is None
    # add another category
    new_category_name = lorem_text_generator.new_text()
    ontology.add_category(ScaleCategory(name=new_category_name), scale=scale_id)
    await ontologies_repo.update_seen()
    category_ids, categories, ranks = ontology.get_scale_categories(scale_id)
    new_category_id, new_category = ontology.get_entry(new_category_name)
    assert len(categories) == 4
    assert [c for c in categories if c.name == new_category_name]
    assert new_category in categories

@pytest.mark.asyncio(scope="session")
async def test_create_and_expand_ordinal_categorical_scale(ontologies_repo, ontology, lorem_text_generator):
    scale_type = ScaleType.ORDINAL
    n_stored_scale = len(list(ontology.get_entries(label=Scale.label)))
    categories = [ScaleCategory(name=lorem_text_generator.new_text()) for i in range(3)]
    for c in categories:
        ontology.add_category(c)
    await ontologies_repo.update_seen()
    category_tuples = [ontology.get_entry(c.name, label=ScaleCategory.label) for c in categories]
    category_ids = [c[0] for c in category_tuples]
    new_scale = Scale(name=lorem_text_generator.new_text(), type=scale_type)
    extra_category = ScaleCategory(name=lorem_text_generator.new_text())
    categories = category_ids + [extra_category]
    ontology.add_scale(new_scale, categories=list(reversed(categories)))

    await ontologies_repo.update_seen()
    assert len(list(ontology.get_entries(label=Scale.label))) == n_stored_scale + 1
    scale_id, stored_scale = next(ontology.get_entries(new_scale.name))
    category_ids_retrieved, categories_retrieved, ranks = ontology.get_scale_categories(stored_scale.id)
    assert category_ids_retrieved[1:] == list(reversed(category_ids))
    assert categories_retrieved[0].name == extra_category.name
    assert ranks == list(range(4))
    # add another category
    new_category_name = lorem_text_generator.new_text()
    ontology.add_category(ScaleCategory(name=new_category_name), scale=scale_id, rank=1)

    await ontologies_repo.update_seen()
    category_ids, categories, ranks = ontology.get_scale_categories(scale_id)
    assert ontology.get_entry(new_category_name)
    assert categories[1].name == new_category_name

@pytest.mark.asyncio(scope="session")
async def test_create_variable(ontologies_repo, ontology, lorem_text_generator):
    trait_id, _ = ontology.get_entry(label=Trait.label)
    method_id, _ = ontology.get_entry(label=ObservationMethod.label)
    scale_id, _ = ontology.get_entry(label=Scale.label)
    new_var = Variable(name=lorem_text_generator.new_text())
    with pytest.raises(TypeError):
        ontology.add_variable(new_var)
    ontology.add_variable(new_var, trait=trait_id, method=method_id, scale=scale_id)
    await ontologies_repo.update_seen()
    variable_id, variable = ontology.get_entry(label=Variable.label)
    assert ontology.get_entry(new_var.name)
    assert variable_id > 0
    assert {trait_id, method_id, scale_id} == ontology.get_descendants(variable_id)

@pytest.mark.asyncio(scope="session")
async def test_create_parameter(ontologies_repo, ontology, lorem_text_generator):

    condition = Condition(name=lorem_text_generator.new_text(10))
    condition_id = ontology.add_condition(condition)
    method_id, _ = ontology.get_entry(label=ObservationMethod.label)
    scale_id, _ = ontology.get_entry(label=Scale.label)
    new_parameter = Parameter(name=lorem_text_generator.new_text())
    with pytest.raises(TypeError):
        ontology.add_parameter(Parameter)
    ontology.add_parameter(new_parameter, condition=condition_id, method=method_id, scale=scale_id)
    await ontologies_repo.update_seen()
    condition_id, _ = ontology.get_entry(condition.name, label=Condition.label)
    parameter_id, parameter = ontology.get_entry(new_parameter.name, label=Parameter.label)
    assert parameter_id > 0
    assert {condition_id, method_id, scale_id} == ontology.get_descendants(parameter_id)

@pytest.mark.asyncio(scope="session")
async def test_create_event(ontologies_repo, ontology, lorem_text_generator):
    exposure = Exposure(name=lorem_text_generator.new_text(10))
    exposure_id = ontology.add_exposure(exposure)
    method_id, _ = ontology.get_entry(label=ObservationMethod.label)
    scale_id, _ = ontology.get_entry(label=Scale.label)
    new_event = EventType(name=lorem_text_generator.new_text())
    ontology.add_event(new_event, exposure=exposure_id, method=method_id, scale=scale_id)
    await ontologies_repo.update_seen()
    exposure_id, _ = ontology.get_entry(exposure.name, label=Exposure.label)
    event_id, event = ontology.get_entry(new_event.name, label=EventType.label)
    assert event_id > 0
    assert {exposure_id, method_id, scale_id} == ontology.get_descendants(event_id)

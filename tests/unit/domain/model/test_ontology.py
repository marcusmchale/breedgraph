import pytest
import pytest_asyncio

from src.breedgraph.domain.model.ontology import (
    Version, VersionStored,
    Ontology,
    OntologyRelationshipLabel,
    Term,
    Scale, ScaleType, ScaleCategory,
    ObservationMethod, ObservationMethodType,
    Subject,
    Trait, Variable,
    Condition, Parameter,
    ControlMethod,
    Exposure, EventType,
    LocationType, LayoutType, Design, Role, Title, AxisType,
    GermplasmMethod
)
from src.breedgraph.custom_exceptions import IllegalOperationError

@pytest_asyncio.fixture
def first_version_stored() -> VersionStored:
    version = Version(major=0, minor=0, patch=0, comment="Test")
    return VersionStored(**dict(version), id=1)

@pytest_asyncio.fixture
def first_ontology(lorem_text_generator, first_version_stored) -> Ontology:
    return Ontology(version=first_version_stored)

@pytest.mark.asyncio
async def test_add_and_get(first_ontology, lorem_text_generator):
    name = lorem_text_generator.new_text(10)
    alt_name = lorem_text_generator.new_text(20)
    term = Term(name=name, synonyms=[alt_name])
    temp_id = first_ontology.add_entry(term)
    assert first_ontology.size == 1
    assert first_ontology.get_entry(temp_id)[1].name == name
    assert first_ontology.get_entry(name)[1].name == name
    assert first_ontology.get_entry(alt_name)[1].name == name
    assert first_ontology.get_entry(name, label=term.label)[1].name == name
    assert first_ontology.get_entry(alt_name, label=term.label)[1].name == name
    assert first_ontology.get_entry(temp_id, label=term.label)[1].name == name
    assert first_ontology.get_entry(lorem_text_generator.new_text(5)) is None

@pytest.mark.asyncio
async def test_add_prevents_duplicate_names(first_ontology, lorem_text_generator):
    name = lorem_text_generator.new_text(10)
    alt_name = lorem_text_generator.new_text(20)
    term = Term(name=name, synonyms=[alt_name])
    first_ontology.add_entry(term)
    with pytest.raises(ValueError):
        new_term1 = Term(name=term.name)
        first_ontology.add_entry(new_term1)
    with pytest.raises(ValueError):
        new_term2 = Term(name=lorem_text_generator.new_text(10), synonyms=term.synonyms)
        first_ontology.add_entry(new_term2)

@pytest.mark.asyncio
async def test_add_prevents_cycles(first_ontology, lorem_text_generator):
    first_id = first_ontology.add_entry(Term(name=lorem_text_generator.new_text(10)))
    second_id = first_ontology.add_entry(
        Term(name=lorem_text_generator.new_text(5)),
        parents=[first_id]
    )
    with pytest.raises(IllegalOperationError):
        first_ontology.add_entry(
            Term(name=lorem_text_generator.new_text(5)),
            parents=[second_id],
            children=[first_id]
        )

@pytest.mark.asyncio
async def test_add_relationship_prevents_loops(first_ontology, lorem_text_generator):
    first_id = first_ontology.add_entry(Term(name=lorem_text_generator.new_text(10)))
    with pytest.raises(IllegalOperationError):
        first_ontology.add_relationship(first_id, first_id, label=OntologyRelationshipLabel.RELATES_TO)

@pytest.mark.asyncio
async def test_add_term_with_parents(first_ontology, lorem_text_generator):
    first_id = first_ontology.add_entry(Term(name=lorem_text_generator.new_text(10)))
    second_id = first_ontology.add_entry(
        Term(name=lorem_text_generator.new_text(5)),
        parents=[first_id]
    )
    assert first_ontology.size == 2
    assert second_id in first_ontology.get_descendants(first_id)

@pytest.mark.asyncio
async def test_add_term_with_children(first_ontology, lorem_text_generator):
    first_id = first_ontology.add_entry(Term(name=lorem_text_generator.new_text(10)))
    second_id = first_ontology.add_entry(
        Term(name=lorem_text_generator.new_text(5)),
        children=[first_id]
    )
    assert first_ontology.size == 2
    assert second_id in first_ontology.get_ancestors(first_id)

@pytest.mark.asyncio
async def test_add_nominal_scale(first_ontology, lorem_text_generator):
    scale = Scale(
        name=lorem_text_generator.new_text(10),
        scale_type=ScaleType.NOMINAL
    )
    category_ids = [first_ontology.add_entry(ScaleCategory(name=lorem_text_generator.new_text())) for _ in range(5)]
    scale_id = first_ontology.add_entry(scale, categories=category_ids)
    assert category_ids == first_ontology.get_category_ids(scale_id)

    new_category = ScaleCategory(name=lorem_text_generator.new_text(10))
    first_ontology.add_entry(new_category, scale=scale_id)

    assert len(category_ids) + 1 == len(first_ontology.get_category_ids(scale_id))

@pytest.mark.asyncio
async def test_add_ordinal_scale(first_ontology, lorem_text_generator):
    scale = Scale(
        name=lorem_text_generator.new_text(10),
        scale_type=ScaleType.ORDINAL
    )
    category_ids = [first_ontology.add_entry(ScaleCategory(name=lorem_text_generator.new_text())) for _ in range(5)]
    scale_id = first_ontology.add_entry(scale, categories=category_ids)
    assert category_ids == first_ontology.get_category_ids(scale_id)

    new_category = ScaleCategory(name=lorem_text_generator.new_text(10))
    new_id = first_ontology.add_entry(new_category, scale=scale_id)

    latest_categories = first_ontology.get_category_ids(scale_id)
    assert len(category_ids) + 1 == len(latest_categories)
    assert new_id == latest_categories[-1]

@pytest.mark.asyncio
async def test_add_trait_requires_subject(first_ontology, lorem_text_generator):
    subject = Subject(name=lorem_text_generator.new_text(10))
    subject_id = first_ontology.add_entry(subject)
    trait = Trait(name=lorem_text_generator.new_text(10), synonyms=[lorem_text_generator.new_text(5)])
    trait_id = first_ontology.add_entry(trait, subjects=[subject_id])
    subject_indices, subjects = first_ontology.get_subjects(trait_id)
    assert len(subjects) == 1
    assert subject_id in subject_indices
    assert subject in subjects
    trait_indices, traits = first_ontology.get_traits(subject_id)
    assert len(trait_indices) == 1
    assert trait_id in trait_indices
    assert trait in traits
    with pytest.raises(ValueError):
        new_trait1 = Trait(name=lorem_text_generator.new_text(10))
        first_ontology.add_entry(new_trait1, subjects=[])

@pytest.mark.asyncio
async def test_add_variable(first_ontology, lorem_text_generator):
    variable = Variable(name = lorem_text_generator.new_text(10))
    subject = Subject(name=lorem_text_generator.new_text(10))
    subject_id = first_ontology.add_entry(subject)
    trait = Trait(name=lorem_text_generator.new_text(10), synonyms=[lorem_text_generator.new_text(5)])
    trait_id = first_ontology.add_entry(trait, subjects=[subject_id])
    method_type = ObservationMethodType.MEASUREMENT
    method = ObservationMethod(name=lorem_text_generator.new_text(10), observation_type=method_type)
    method_id = first_ontology.add_entry(method)
    scale = Scale(name=lorem_text_generator.new_text(10), scale_type=ScaleType.NUMERICAL)
    scale_id = first_ontology.add_entry(scale)
    first_ontology.add_entry(variable, trait=trait_id, method=method_id, scale=scale_id)
    with pytest.raises(ValueError):
        new_variable = Variable(name=lorem_text_generator.new_text(10))
        first_ontology.add_entry(new_variable, trait=method_id, method=method_id, scale=scale_id)
    with pytest.raises(ValueError):
        new_variable = Variable(name=lorem_text_generator.new_text(10))
        first_ontology.add_entry(new_variable, trait=trait_id, method=trait_id, scale=scale_id)
    with pytest.raises(ValueError):
        new_variable = Variable(name=lorem_text_generator.new_text(10))
        first_ontology.add_entry(new_variable, trait=trait_id, method=method_id, scale=method_id)

@pytest.mark.asyncio
async def test_add_parameter(first_ontology, lorem_text_generator):
    parameter = Parameter(name = lorem_text_generator.new_text(10))
    subject = Subject(name=lorem_text_generator.new_text(10))
    subject_id = first_ontology.add_entry(subject)
    condition = Condition(name=lorem_text_generator.new_text(10), synonyms=[lorem_text_generator.new_text(5)])
    condition_id = first_ontology.add_entry(condition, subjects=[subject_id])
    method = ControlMethod(name=lorem_text_generator.new_text(10))
    method_id = first_ontology.add_entry(method)
    scale = Scale(name=lorem_text_generator.new_text(10), scale_type=ScaleType.ORDINAL)
    scale_id = first_ontology.add_entry(scale)
    first_ontology.add_entry(parameter, condition=condition_id, method=method_id, scale=scale_id)
    with pytest.raises(ValueError):
        new_parameter = Parameter(name=lorem_text_generator.new_text(10))
        first_ontology.add_entry(new_parameter, condition=method_id, method=method_id, scale=scale_id)

@pytest.mark.asyncio
async def test_add_event(first_ontology, lorem_text_generator):
    event = EventType(name = lorem_text_generator.new_text(10))
    subject = Subject(name=lorem_text_generator.new_text(10))
    subject_id = first_ontology.add_entry(subject)
    exposure = Exposure(name=lorem_text_generator.new_text(10), synonyms=[lorem_text_generator.new_text(5)])
    exposure_id = first_ontology.add_entry(exposure, subjects=[subject_id])
    method_type = ObservationMethodType.DESCRIPTION
    method = ObservationMethod(name=lorem_text_generator.new_text(10), observation_type=method_type)
    method_id = first_ontology.add_entry(method)
    scale = Scale(name=lorem_text_generator.new_text(10), scale_type=ScaleType.ORDINAL)
    scale_id = first_ontology.add_entry(scale)
    first_ontology.add_entry(event, exposure=exposure_id, method=method_id, scale=scale_id)
    with pytest.raises(ValueError):
        new_event = EventType(name=lorem_text_generator.new_text(10))
        first_ontology.add_entry(new_event, exposure=method_id, method=method_id, scale=scale_id)

@pytest.mark.asyncio
async def test_add_location(first_ontology, lorem_text_generator):
    location = LocationType(name=lorem_text_generator.new_text(10))
    first_ontology.add_entry(location)
    assert first_ontology.get_entry(label=location.label)

@pytest.mark.asyncio
async def test_add_layout(first_ontology, lorem_text_generator):
    layout = LayoutType(name=lorem_text_generator.new_text(10), axes=[AxisType.NOMINAL])
    first_ontology.add_entry(layout)
    assert first_ontology.get_entry(label=layout.label)

@pytest.mark.asyncio
async def test_add_design(first_ontology, lorem_text_generator):
    design = Design(name=lorem_text_generator.new_text(10))
    first_ontology.add_entry(design)
    assert first_ontology.get_entry(label=design.label)

@pytest.mark.asyncio
async def test_add_role(first_ontology, lorem_text_generator):
    role = Role(name=lorem_text_generator.new_text(10))
    first_ontology.add_entry(role)
    assert first_ontology.get_entry(label=role.label)

@pytest.mark.asyncio
async def test_add_title(first_ontology, lorem_text_generator):
    title = Title(name=lorem_text_generator.new_text(10))
    first_ontology.add_entry(title)
    assert first_ontology.get_entry(label=title.label)

@pytest.mark.asyncio
async def test_add_germplasm_method(first_ontology, lorem_text_generator):
    method = GermplasmMethod(name=lorem_text_generator.new_text(10))
    first_ontology.add_entry(method)
    assert first_ontology.get_entry(label=method.label)
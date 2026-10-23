"""Values of nominal and ordinal scales are the names of the scale's categories (domain.services.value_parsers)"""
import pytest

from breedgraph.domain.model.ontology import ScaleStored, ScaleType, ScaleCategory
from breedgraph.domain.services.value_parsers import ValueParser

SEVERITY = ScaleStored(id=1, name="Severity", scale_type=ScaleType.ORDINAL, categories=[
    ScaleCategory("1", "No symptoms"), ScaleCategory("2", "A few lesions"), ScaleCategory("Dead")
])


def test_a_value_is_stored_as_the_category_name():
    assert ValueParser().parse("2", SEVERITY) == "2"
    assert ValueParser().parse(" dead ", SEVERITY) == "Dead", "matched ignoring case and spaces"


def test_a_value_that_is_no_category_name_is_refused():
    with pytest.raises(ValueError, match="doesn't match a category name"):
        ValueParser().parse("3", SEVERITY)
    # a description is not a name
    with pytest.raises(ValueError, match="doesn't match a category name"):
        ValueParser().parse("No symptoms", SEVERITY)


def test_a_value_is_text():
    with pytest.raises(ValueError, match="Only text values"):
        ValueParser().parse(1, SEVERITY)

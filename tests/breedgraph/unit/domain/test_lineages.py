"""What comes down a unit graph: the nearest units on each lineage (domain.services.lineages)"""
from breedgraph.domain.services.lineages import nearest_on_each_lineage, lineage_value

# field 1 > plot 2 > trees 3 and 4 > sample 5 pooled from both; tree 6 in plot 2 > sample 7
PARENTS = {5: [3, 4], 3: [2], 4: [2], 2: [1], 7: [6], 6: [2]}


def parents_of(unit_id):
    return PARENTS.get(unit_id, [])


def test_each_path_stops_at_its_first():
    assert nearest_on_each_lineage(5, parents_of, lambda u: u in (3, 4, 1)) == [3, 4]
    # the field is above both lineages, and found once
    assert nearest_on_each_lineage(5, parents_of, lambda u: u == 1) == [1]
    assert nearest_on_each_lineage(5, parents_of, lambda u: False) == []
    assert nearest_on_each_lineage(1, parents_of, lambda u: True) == []


def test_a_value_comes_down_when_the_lineages_agree():
    germplasm = {3: 'crop_a', 4: 'crop_b', 6: 'crop_a'}
    assert lineage_value(7, parents_of, germplasm.get) == ('crop_a', 6)
    assert lineage_value(5, parents_of, germplasm.get) == (None, None), 'pooled from two varieties'
    assert lineage_value(5, parents_of, {3: 'crop_a', 4: 'crop_a'}.get) == ('crop_a', 3), 'agreeing, the lower id'
    assert lineage_value(3, parents_of, germplasm.get) == ('crop_a', 3), 'its own'
    assert lineage_value(2, parents_of, germplasm.get) == (None, None), 'nothing above'

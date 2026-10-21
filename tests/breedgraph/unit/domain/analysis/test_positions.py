"""Position grouping (domain.services.analysis_places): where the units of records were"""
from numpy import datetime64

from breedgraph.domain.model.analysis import AnalysisWarningCode
from breedgraph.domain.model.analysis_context import UnitContext, LocationContext, LayoutContext, ConceptContext
from breedgraph.domain.model.ontology import ScaleType
from breedgraph.domain.model.unit_graphs import Position
from breedgraph.domain.services.analysis_preparation import prepare_observations

from .factories import record, dataset, context, descriptive, concept_term, domain_term

# location types and subjects
COUNTRY, FIELD, LAB = 1, 2, 3
FIELD_UNIT, TREE, SAMPLE = 50, 51, 52

# two countries, each with fields and a lab; a hidden root with a readable field below it
FIELD_A1, FIELD_A2, LAB_A, FIELD_B1, LAB_B, HIDDEN_ROOT, FIELD_C = 2, 3, 4, 11, 12, 20, 21
LOCATIONS = {location.location_id: location for location in [
    LocationContext(1, COUNTRY),
    LocationContext(FIELD_A1, FIELD, parent_id=1),
    LocationContext(FIELD_A2, FIELD, parent_id=1),
    LocationContext(LAB_A, LAB, parent_id=1),
    LocationContext(10, COUNTRY),
    LocationContext(FIELD_B1, FIELD, parent_id=10),
    LocationContext(LAB_B, LAB, parent_id=10),
    LocationContext(HIDDEN_ROOT, readable=False),
    LocationContext(FIELD_C, FIELD, parent_id=HIDDEN_ROOT),
]}
# Row and Tree layouts in fields A1 and B1; field A2 laid out in blocks, each with its own rows; a freezer in lab A;
# a hidden layout with a readable one below it
LAYOUTS = {layout.layout_id: layout for layout in [
    LayoutContext(100, ['Row', 'Tree']),
    LayoutContext(101, ['Row', 'Tree']),
    LayoutContext(110, ['Block']),
    LayoutContext(111, ['Row', 'Tree'], parent_id=110, position=['1']),
    LayoutContext(112, ['Row', 'Tree'], parent_id=110, position=['2']),
    LayoutContext(120, ['Box', 'Slot']),
    LayoutContext(130, readable=False),
    LayoutContext(131, ['Row'], parent_id=130, position=['1']),
]}

SAMPLED = datetime64('2025-05-01')


def unit(unit_id, subject, positions=(), parents=(), **options):
    return UnitContext(
        unit_id, subject_id=subject, positions=list(positions), parent_ids=list(parents),
        place_parent_ids=list(options.pop('place_parents', parents)), **options
    )

UNITS = [
    unit(1000, FIELD_UNIT, [Position(FIELD_A1)]),
    unit(1001, TREE, [Position(FIELD_A1, 100, ['1', '1'])], [1000]),
    unit(1002, TREE, [Position(FIELD_A1, 100, ['2', '1'])], [1000]),
    unit(1003, SAMPLE, [Position(LAB_A, start=SAMPLED)], [1001]),
    # analysed in a lab abroad
    unit(1004, SAMPLE, [Position(LAB_B, start=SAMPLED)], [1001]),
    # pooled from trees in two rows
    unit(1005, SAMPLE, [Position(LAB_A, start=SAMPLED)], [1001, 1002]),
    unit(1007, FIELD_UNIT, [Position(FIELD_B1)]),
    unit(1006, TREE, [Position(FIELD_B1, 101, ['1', '1'])], [1007]),
    unit(1009, FIELD_UNIT, [Position(FIELD_A2)]),
    unit(1008, TREE, [Position(FIELD_A2, 111, ['3', '1'])], [1009]),
    unit(1010, TREE, [Position(FIELD_A2, 112, ['3', '2'])], [1009]),
    unit(1011, TREE, [Position(FIELD_A1, 100, ['10', '1'])], [1000]),
    # in the lab's freezer
    unit(1012, SAMPLE, [Position(LAB_A, 120, ['B1', '5'], start=SAMPLED)], [1001]),
]

def axis(name):
    return domain_term('LAYOUT_AXIS', layout_axis=name)

def analyse(records, grouping, terms=(domain_term('LOCATION'),), units=(), aggregation=None, **options):
    """Records of concept 10 on the units of UNITS and those given, with position grouping"""
    term = concept_term(10, aggregation=aggregation) if aggregation else concept_term(10)
    ctx = context(
        descriptive([term, *terms], grouping={'position': grouping}),
        [dataset(1, 1, 10, records)],
        units={u.unit_id: u for u in [*UNITS, *units]},
        locations=LOCATIONS,
        layouts=LAYOUTS,
        **options
    )
    warnings = []
    return prepare_observations(ctx, warnings), warnings

def groups(frame):
    return {record_id: o.group for o in frame.observations for record_id in o.record_ids}

def locations(frame):
    return {record_id: group['location_id'] for record_id, group in groups(frame).items()}

def axes(frame, record_id):
    return [(a['axis'], a['layout_id'], a['value']) for a in groups(frame)[record_id]['layout_axes']]

def unassigned(warnings):
    return [w.record_ids for w in warnings if w.code == AnalysisWarningCode.UNASSIGNED_POSITION]


""" Locations """
def test_the_location_is_the_nearest_of_a_type():
    records = [record(1, 1001, '1'), record(2, 1000, '2'), record(3, 1006, '3')]
    frame, warnings = analyse(records, {'location_type_ids': [FIELD]})
    assert locations(frame) == {1: FIELD_A1, 2: FIELD_A1, 3: FIELD_B1}
    assert sorted(frame.data['location'].unique()) == [str(FIELD_B1), str(FIELD_A1)]
    assert unassigned(warnings) == []
    frame, _ = analyse(records, {'location_type_ids': [COUNTRY]})
    assert locations(frame) == {1: 1, 2: 1, 3: 10}
    # of two types, the nearer
    frame, _ = analyse(records, {'location_type_ids': [COUNTRY, FIELD]})
    assert locations(frame) == {1: FIELD_A1, 2: FIELD_A1, 3: FIELD_B1}

def test_a_sample_is_placed_by_its_tree_unless_its_lab_counts():
    records = [record(1, 1003, '1'), record(2, 1001, '2')]
    frame, _ = analyse(records, {'location_type_ids': [FIELD]})
    assert locations(frame) == {1: FIELD_A1, 2: FIELD_A1}
    frame, warnings = analyse(records, {'location_type_ids': [LAB]})
    assert locations(frame) == {1: LAB_A}
    assert unassigned(warnings) == [[2]]

def test_subjects_place_the_units_below_them():
    records = [record(1, 1004, '1'), record(2, 1001, '2'), record(3, 1000, '3')]
    # a sample analysed abroad is in its lab's country
    frame, _ = analyse(records, {'location_type_ids': [COUNTRY]})
    assert locations(frame) == {1: 10, 2: 1, 3: 1}
    # placed by its tree; the tree itself and the field unit above the trees are placed as before
    frame, _ = analyse(records, {'location_type_ids': [COUNTRY], 'subject_ids': [TREE]})
    assert locations(frame) == {1: 1, 2: 1, 3: 1}

def test_lineages_must_agree():
    records = [record(1, 1005, '1'), record(2, 1001, '2')]
    # the pooled sample's trees are in one field
    frame, _ = analyse(records, {'location_type_ids': [FIELD]})
    assert locations(frame) == {1: FIELD_A1, 2: FIELD_A1}
    # but in two rows
    frame, warnings = analyse(records, {'location_type_ids': [FIELD], 'axes': ['Row']}, [axis('Row')])
    assert 1 not in groups(frame)
    assert unassigned(warnings) == [[1]]
    # by subject, each lineage starts from its tree
    frame, warnings = analyse(records, {'location_type_ids': [FIELD], 'subject_ids': [TREE], 'axes': ['Row']}, [axis('Row')])
    assert unassigned(warnings) == [[1]]


""" Layouts and axes """
def test_axis_values_are_nested_in_their_layout():
    records = [record(1, 1001, '1'), record(2, 1002, '2'), record(3, 1006, '3'), record(4, 1011, '4')]
    frame, _ = analyse(records, {'location_type_ids': [FIELD], 'axes': ['Row']}, [axis('Row')])
    column = frame.columns[1]
    assert column.name == 'layout_axis:Row'
    # row 1 of field B1 is not row 1 of field A1; rows in numeric order
    assert column.levels == ['100|1', '100|2', '100|10', '101|1']
    assert axes(frame, 3) == [('Row', 101, '1')]
    assert groups(frame)[3]['location_id'] == FIELD_B1

def test_an_axis_of_a_layout_above():
    records = [record(1, 1008, '1'), record(2, 1010, '2')]
    frame, _ = analyse(records, {'location_type_ids': [FIELD], 'axes': ['Block', 'Row']}, [axis('Block'), axis('Row')])
    assert axes(frame, 1) == [('Block', 110, '1'), ('Row', 111, '3')]
    assert list(frame.data['layout_axis:Block']) == ['110|1', '110|2']
    # rows are numbered per block
    assert list(frame.data['layout_axis:Row']) == ['111|3', '112|3']

def test_positions_without_the_axes_do_not_count():
    records = [record(1, 1000, '1'), record(2, 1012, '2'), record(3, 1001, '3')]
    # the field unit has no row; the sample in the freezer takes its tree's
    frame, warnings = analyse(records, {'location_type_ids': [FIELD], 'axes': ['Row']}, [axis('Row')])
    assert unassigned(warnings) == [[1]]
    assert axes(frame, 2) == [('Row', 100, '1')]
    # in the lab, the box is the sample's own
    frame, warnings = analyse(records, {'location_type_ids': [LAB], 'axes': ['Box']}, [axis('Box')])
    assert axes(frame, 2) == [('Box', 120, 'B1')]
    assert unassigned(warnings) == [[1, 3]]


""" Time """
MOVED = unit(1020, TREE, [
    Position(FIELD_A1, end=datetime64('2024-03-01')), Position(FIELD_B1, start=datetime64('2024-03-01'))
])

def test_the_record_time_chooses_between_positions():
    records = [
        record(1, 1020, '1', start='2023-06-01'), record(2, 1020, '2', start='2024-06-01'),
        record(3, 1020, '3', start='2024-03-01'), record(4, 1020, '4')
    ]
    frame, warnings = analyse(records, {'location_type_ids': [FIELD]}, units=[MOVED], aggregation='MEAN')
    # on the day of the move, the later-starting position
    assert locations(frame) == {1: FIELD_A1, 2: FIELD_B1, 3: FIELD_B1}
    # without a time the positions differ
    assert unassigned(warnings) == [[4]]
    # a set time stands in for every record's
    frame, warnings = analyse(
        records, {'location_type_ids': [FIELD], 'time': '2023-01-01'}, units=[MOVED], aggregation='MEAN'
    )
    assert locations(frame) == {1: FIELD_A1, 2: FIELD_A1, 3: FIELD_A1, 4: FIELD_A1}

def test_positions_that_dont_count_are_not_chosen():
    # a plant that visited the lab
    visitor = unit(1022, TREE, [
        Position(FIELD_A1, end=datetime64('2024-03-01')),
        Position(LAB_A, start=datetime64('2024-03-01'), end=datetime64('2024-06-01')),
        Position(FIELD_A1, start=datetime64('2024-06-01')),
    ])
    records = [record(1, 1022, '1', start='2024-04-01'), record(2, 1022, '2', start='2023-06-01')]
    # while it was in the lab, its positions in field A1 before and after agree
    frame, _ = analyse(records, {'location_type_ids': [FIELD]}, units=[visitor], aggregation='MEAN')
    assert locations(frame) == {1: FIELD_A1, 2: FIELD_A1}
    # its only position in a lab places it there at any time
    frame, _ = analyse(records, {'location_type_ids': [LAB]}, units=[visitor], aggregation='MEAN')
    assert locations(frame) == {1: LAB_A, 2: LAB_A}

def test_positions_agreeing_place_a_record_when_none_holds():
    # moved to row 2 and back to row 1, then away for a while
    plant = unit(1021, TREE, [
        Position(FIELD_A1, 100, ['1', '1'], end=datetime64('2024-03-01')),
        Position(FIELD_A1, 100, ['2', '1'], start=datetime64('2024-03-01'), end=datetime64('2024-06-01')),
        Position(FIELD_A1, 100, ['1', '1'], start=datetime64('2024-09-01')),
    ])
    records = [record(1, 1021, '1', start='2024-07-15'), record(2, 1021, '2', start='2024-04-01')]
    frame, warnings = analyse(records, {'location_type_ids': [FIELD], 'axes': ['Row']}, [axis('Row')], units=[plant])
    assert unassigned(warnings) == [[1]]
    assert axes(frame, 2) == [('Row', 100, '2')]
    # all in one field
    frame, warnings = analyse(records, {'location_type_ids': [FIELD]}, units=[plant], aggregation='MEAN')
    assert locations(frame) == {1: FIELD_A1, 2: FIELD_A1}

def test_an_only_position_places_at_any_time():
    # a tree removed before its stored sample was analysed
    tree = unit(1030, TREE, [Position(FIELD_A1, 100, ['5', '1'], end=datetime64('2023-01-01'))], [1000])
    sample = unit(1031, SAMPLE, [Position(LAB_A, start=datetime64('2022-12-01'))], [1030])
    records = [record(1, 1031, '1', start='2025-06-01')]
    frame, _ = analyse(records, {'location_type_ids': [FIELD], 'axes': ['Row']}, [axis('Row')], units=[tree, sample])
    assert locations(frame) == {1: FIELD_A1}
    assert axes(frame, 1) == [('Row', 100, '5')]


""" What the user cannot see """
def test_what_the_user_cannot_see_stops_a_placement():
    hidden = [
        # a placeholder of a hidden unit with records is never placed, though its parent is
        UnitContext(1040, parent_ids=[1001], place_parent_ids=[1001], readable=False),
        # a readable sample below a hidden unit with positions
        unit(1041, SAMPLE, [Position(LAB_A, start=SAMPLED)], [1000], place_parents=[9999]),
        # positions at a location missing from the tree the user sees, and at a hidden root
        unit(1042, TREE, [Position(99)], [1000]),
        unit(1043, TREE, [Position(HIDDEN_ROOT)], [1000]),
        # a field below a hidden root is seen
        unit(1044, TREE, [Position(FIELD_C)]),
    ]
    records = [record(i, unit_id, str(i)) for i, unit_id in enumerate([1040, 1041, 1042, 1043, 1044, 1001], 1)]
    frame, warnings = analyse(records, {'location_type_ids': [FIELD]}, units=hidden, hidden_positioned={9999})
    assert unassigned(warnings) == [[1, 2, 3, 4]]
    assert locations(frame) == {5: FIELD_C, 6: FIELD_A1}
    # the hidden root's type is not seen, so the field below it has no country; the sample's own position is in a
    # country, so the hidden unit above it doesn't matter
    frame, warnings = analyse(records, {'location_type_ids': [COUNTRY]}, units=hidden, hidden_positioned={9999})
    assert unassigned(warnings) == [[1, 3, 4, 5]]
    assert locations(frame) == {2: 1, 6: 1}

def test_hidden_layouts():
    in_hidden = unit(1050, TREE, [Position(FIELD_A1, 130, ['x'])], [1000])
    below_hidden = unit(1051, TREE, [Position(FIELD_A1, 131, ['4'])], [1000])
    records = [record(1, 1050, '1'), record(2, 1051, '2')]
    frame, warnings = analyse(records, {'location_type_ids': [FIELD], 'axes': ['Row']}, [axis('Row')], units=[in_hidden, below_hidden])
    assert unassigned(warnings) == [[1]]
    assert axes(frame, 2) == [('Row', 131, '4')]
    # an axis above a hidden layout is not known; a tree in a layout without blocks has none
    frame, warnings = analyse(
        [*records, record(3, 1001, '3'), record(4, 1008, '4')], {'location_type_ids': [FIELD], 'axes': ['Block']},
        [axis('Block')], units=[in_hidden, below_hidden]
    )
    assert unassigned(warnings) == [[1, 2, 3]]
    assert axes(frame, 4) == [('Block', 110, '1')]
    # without axes the layout doesn't matter
    frame, warnings = analyse(records, {'location_type_ids': [FIELD]}, units=[in_hidden, below_hidden])
    assert locations(frame) == {1: FIELD_A1, 2: FIELD_A1}


""" Factors """
def test_factor_records_describe_observations_wherever_they_are():
    concepts = {
        10: ConceptContext(10, ScaleType.NUMERICAL),
        20: ConceptContext(20, ScaleType.NOMINAL, categories=['Shade', 'Sun'], factor=True),
    }
    ctx = context(
        descriptive(
            [concept_term(10), concept_term(20), domain_term('LOCATION'), axis('Row')],
            grouping={'position': {'location_type_ids': [FIELD], 'axes': ['Row']}}, dataset_ids=[1, 2]
        ),
        [
            dataset(1, 1, 10, [record(1, 1001, '1'), record(2, 1002, '2')]),
            # on the field unit, which has no row
            dataset(2, 1, 20, [record(3, 1000, 'Shade')]),
        ],
        units={u.unit_id: u for u in UNITS}, concepts=concepts, locations=LOCATIONS, layouts=LAYOUTS
    )
    warnings = []
    frame = prepare_observations(ctx, warnings)
    assert list(frame.data['concept:20']) == ['Shade', 'Shade']
    assert unassigned(warnings) == []

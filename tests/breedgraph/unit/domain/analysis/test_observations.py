import json
import math

import pytest
from numpy import datetime64

from breedgraph.domain.model.analysis import AnalysisFailed, AnalysisErrorCode, AnalysisWarningCode
from breedgraph.domain.model.analysis_context import UnitContext, ConceptContext
from breedgraph.domain.model.unit_graphs import Position
from breedgraph.domain.model.ontology import ScaleType, RecordGroupExtent
from breedgraph.domain.model.programs import RecordGroupingStored, GroupingScope, DatasetScope
from breedgraph.domain.services.analysis_job import build_job_payload
from breedgraph.domain.services.analysis_preparation import prepare_observations

from .factories import record, dataset, study, context, descriptive, concept_term, domain_term


def prepare(ctx):
    warnings = []
    frame = prepare_observations(ctx, warnings)
    return frame, warnings

def codes(warnings):
    return [w.code for w in warnings]

def values(frame, concept_id):
    return list(frame.data[f'concept:{concept_id}'])


""" Observation identity and aggregation """
def test_observation_per_unit():
    ctx = context(
        descriptive([concept_term(10), concept_term(11)], dataset_ids=[1, 2]),
        [
            dataset(1, 1, 10, [record(1, 100, '1'), record(2, 101, '2')]),
            dataset(2, 1, 11, [record(3, 100, '3,5')]),
        ]
    )
    frame, warnings = prepare(ctx)
    assert values(frame, 10) == [1.0, 2.0]
    assert values(frame, 11)[0] == 3.5 and math.isnan(values(frame, 11)[1])
    assert [o.record_ids for o in frame.observations] == [[1, 3], [2]]
    assert [o.group['unit_id'] for o in frame.observations] == [100, 101]
    assert codes(warnings) == [AnalysisWarningCode.MISSING_VALUES]

def test_duplicate_observation_is_an_error():
    ctx = context(descriptive([concept_term(10)]), [dataset(1, 1, 10, [record(1, 100, '1'), record(2, 100, '2')])])
    with pytest.raises(AnalysisFailed) as e:
        prepare(ctx)
    error = e.value.errors[0]
    assert error.code == AnalysisErrorCode.DUPLICATE_OBSERVATION
    assert error.record_ids == [1, 2]
    assert error.path == ['descriptiveStatistics', 'terms', '0', 'aggregation']

def test_messages_name_concepts_and_datasets():
    """By their names, with the dataset's ID, as breedview lists datasets; by their IDs where the names are unknown"""
    height = ConceptContext(10, ScaleType.NUMERICAL, name='Height')
    duplicated = context(
        descriptive([concept_term(10)]), [dataset(1, 1, 10, [record(1, 100, '1'), record(2, 100, '2')])],
        concepts={10: height}
    )
    with pytest.raises(AnalysisFailed) as e:
        prepare(duplicated)
    assert e.value.errors[0].message.startswith("Concept 'Height' has more than one value for some observations")

    missing = context(
        descriptive([concept_term(10), concept_term(11)], dataset_ids=[1, 2]),
        [dataset(1, 1, 10, [record(1, 100, '1'), record(2, 101, '2')]), dataset(2, 1, 11, [record(3, 100, '3')])],
        concepts={10: height, 11: ConceptContext(11, ScaleType.NUMERICAL)}
    )
    _, warnings = prepare(missing)
    assert [w.message for w in warnings] == ['1 of 2 observations have no value for concept 11']

    excluded = context(
        descriptive([concept_term(10)], dataset_ids=[1, 2], exclusions=[{'record_ids': [2]}]),
        [dataset(1, 1, 10, [record(1, 100, '1')]), dataset(2, 1, 10, [record(2, 101, '2')])],
        concepts={10: height}, concept_names={10: 'Height'}
    )
    _, warnings = prepare(excluded)
    fully = [w.message for w in warnings if w.code == AnalysisWarningCode.DATASET_FULLY_EXCLUDED]
    assert fully == ["All records of dataset 'Height' (#2) were excluded"]

@pytest.mark.parametrize('aggregation, expected', [
    ('MEAN', 2.0), ('MEDIAN', 2.0), ('SUM', 6.0), ('MIN', 1.0), ('MAX', 3.0), ('COUNT', 3.0)
])
def test_aggregation(aggregation, expected):
    ctx = context(
        descriptive([concept_term(10, aggregation=aggregation)]),
        [dataset(1, 1, 10, [record(i, 100, str(i)) for i in (1, 2, 3)])]
    )
    frame, _ = prepare(ctx)
    assert values(frame, 10) == [expected]

# a continuous term for descriptive statistics to describe, beside the term a test is about
DESCRIBED = dataset(9, 1, 90, [record(90, 100, '1'), record(91, 101, '2')])

def test_ordinal_aggregation_and_levels():
    concepts = {
        10: ConceptContext(10, ScaleType.ORDINAL, categories=['low', 'mid', 'high']),
        90: ConceptContext(90, ScaleType.NUMERICAL)
    }
    ctx = context(
        descriptive([concept_term(10, aggregation='MAX'), concept_term(90)], dataset_ids=[1, 9]),
        [dataset(1, 1, 10, [record(1, 100, 'mid'), record(2, 100, 'low'), record(3, 101, 'high')]), DESCRIBED],
        concepts=concepts
    )
    frame, _ = prepare(ctx)
    assert values(frame, 10) == ['mid', 'high']
    assert frame.columns[0].levels == ['low', 'mid', 'high']

def test_numbers_as_levels_are_written_as_recorded_in_numeric_order():
    """A nitrogen rate of 120 is the level 120, not 120.0, so a level order typed as recorded matches it"""
    records = [record(1, 100, '120'), record(2, 101, '200'), record(3, 102, '50'), record(4, 103, '62,5')]
    described = dataset(9, 1, 90, [record(90 + i, 100 + i, str(i)) for i in range(4)])
    terms = [concept_term(10, representation='CATEGORICAL'), concept_term(90)]
    frame, _ = prepare(context(descriptive(terms, dataset_ids=[1, 9]), [dataset(1, 1, 10, records), described]))
    assert values(frame, 10) == ['120', '200', '50', '62.5']
    assert frame.columns[0].levels == ['50', '62.5', '120', '200']

    terms[0] = concept_term(10, representation='ORDINAL', level_order=['200', '120', '62.5', '50'])
    frame, warnings = prepare(context(descriptive(terms, dataset_ids=[1, 9]), [dataset(1, 1, 10, records), described]))
    assert values(frame, 10) == ['120', '200', '50', '62.5']
    assert frame.columns[0].levels == ['200', '120', '62.5', '50']
    assert codes(warnings) == []

def test_descriptive_statistics_need_a_continuous_or_ordinal_concept_term():
    """A nominal score, or a number taken as categorical, only groups the others: alone, it leaves nothing to describe"""
    for concept, term in [
        (ConceptContext(10, ScaleType.NOMINAL, categories=['a', 'b']), concept_term(10)),
        (ConceptContext(10, ScaleType.NUMERICAL), concept_term(10, representation='CATEGORICAL')),
    ]:
        ctx = context(descriptive([term]), [dataset(1, 1, 10, [record(1, 100, 'a')])], concepts={10: concept})
        with pytest.raises(AnalysisFailed) as e:
            prepare(ctx)
        assert e.value.errors[0].code == AnalysisErrorCode.INCOMPATIBLE_SCALE
        assert e.value.errors[0].path == ['descriptiveStatistics', 'terms']
    # an ordinal score is summarised
    ordinal = ConceptContext(10, ScaleType.ORDINAL, categories=['1', '2', '3'])
    frame, _ = prepare(context(descriptive([concept_term(10)]), [dataset(1, 1, 10, [record(1, 100, '2')])], concepts={10: ordinal}))
    assert frame.columns[0].kind.value == 'ORDINAL'

def test_incompatible_scale():
    concepts = {10: ConceptContext(10, ScaleType.NOMINAL, categories=['a'])}
    ctx = context(
        descriptive([concept_term(10, representation='CONTINUOUS')]),
        [dataset(1, 1, 10, [record(1, 100, 'a')])], concepts=concepts
    )
    with pytest.raises(AnalysisFailed) as e:
        prepare(ctx)
    assert e.value.errors[0].code == AnalysisErrorCode.INCOMPATIBLE_SCALE

def test_transformations():
    ctx = context(
        descriptive([concept_term(10, transformations=['LOG', 'CENTER'])]),
        [dataset(1, 1, 10, [record(1, 100, '1'), record(2, 101, str(math.e ** 2))])]
    )
    frame, _ = prepare(ctx)
    assert values(frame, 10) == pytest.approx([-1.0, 1.0])

def test_invalid_transformation():
    ctx = context(
        descriptive([concept_term(10, transformations=['LOG'])]),
        [dataset(1, 1, 10, [record(1, 100, '0'), record(2, 101, '1')])]
    )
    with pytest.raises(AnalysisFailed) as e:
        prepare(ctx)
    assert e.value.errors[0].code == AnalysisErrorCode.INVALID_TRANSFORMATION
    assert e.value.errors[0].record_ids == [1]

def test_binned_concept():
    binned = concept_term(10, binning={'boundaries': ['10'], 'labels': ['low', 'high'], 'boundary': 'LEFT'})
    ctx = context(
        descriptive([binned, concept_term(90)], dataset_ids=[1, 9]),
        [dataset(1, 1, 10, [record(1, 100, '10'), record(2, 101, '11')]), DESCRIBED]
    )
    frame, _ = prepare(ctx)
    assert values(frame, 10) == ['low', 'high']
    assert frame.columns[0].kind.value == 'ORDINAL'


""" Dimensions """
TIME = {'assignment': 'START', 'binning': {'boundaries': ['2021-01-01'], 'labels': ['2020', '2021'], 'boundary': 'RIGHT'}}

def test_time_dimension_and_unassigned_warning():
    ctx = context(
        descriptive([concept_term(10), domain_term('TIME')], grouping={'time': TIME}),
        [dataset(1, 1, 10, [
            record(1, 100, '1', start='2020-06-01'),
            record(2, 100, '2', start='2021-01-01'),
            record(3, 100, '3'),
        ])]
    )
    frame, warnings = prepare(ctx)
    assert list(frame.data['time']) == ['2020', '2021']
    assert frame.observations[1].exclusion['start'].startswith('2021-01-01')
    assert frame.observations[1].exclusion['end'] is None
    unassigned = [w for w in warnings if w.code == AnalysisWarningCode.UNASSIGNED_TIME]
    assert unassigned[0].record_ids == [3]
    assert unassigned[0].path == ['descriptiveStatistics', 'grouping', 'time']

def time_bins(assignment, boundary_time, records, boundary='RIGHT'):
    """The time bin, before or after the boundary, of each record (one per unit) in record order"""
    spec = {'assignment': assignment, 'binning': {'boundaries': [boundary_time], 'labels': ['before', 'after'], 'boundary': boundary}}
    ctx = context(descriptive([concept_term(10), domain_term('TIME')], grouping={'time': spec}), [dataset(1, 1, 10, records)])
    frame, _ = prepare(ctx)
    return list(frame.data['time'])

def test_end_assignment_is_the_end_of_the_period_of_the_end():
    # an end of 2020-12-31 runs through that day, and an end of 2020 through the year
    assert time_bins('END', '2020-12-31T12:00', [
        record(1, 100, '1', start='2020-12-01', end='2020-12-31'),
        record(2, 101, '2', start='2020-03-01', end='2020'),
        record(3, 102, '3', start='2020-12-01', end='2020-12-30'),
    ]) == ['after', 'after', 'before']

@pytest.mark.parametrize('boundary', ['LEFT', 'RIGHT'])
def test_end_of_a_period_falls_before_a_boundary_at_the_next_period(boundary):
    assert time_bins('END', '2021-01-01', [record(1, 100, '1', start='2020-03-01', end='2020')], boundary) == ['before']

def test_midpoint_assignment_is_the_middle_of_the_period():
    # 2020-01-01 to the end of 2020-01-02 has its middle at the start of 2020-01-02, a record of 2020 in July
    assert time_bins('MIDPOINT', '2020-01-01T18:00', [record(1, 100, '1', start='2020-01-01', end='2020-01-02')]) == ['after']
    assert time_bins('MIDPOINT', '2020-07-01', [record(1, 100, '1', start='2020')]) == ['after']
    assert time_bins('MIDPOINT', '2020-07-03', [record(1, 100, '1', start='2020')]) == ['before']

def test_a_record_with_one_time_stands_for_its_period():
    # with only an end, START is the start of the end's period; with only a start, END is the end of the start's
    assert time_bins('START', '2020-05-03T12:00', [record(1, 100, '1', end='2020-05-03')]) == ['before']
    assert time_bins('END', '2020-05-03T12:00', [record(1, 100, '1', start='2020-05-03')]) == ['after']

def test_unit_grouping_uses_parent_unit():
    units = {
        100: UnitContext(100, ancestor_ids=[1], parent_ids=[1]),
        101: UnitContext(101, ancestor_ids=[1], parent_ids=[1]),
        102: UnitContext(102),
    }
    ctx = context(
        descriptive([concept_term(10, aggregation='MEAN')], grouping={'unit': {'unit_ids': [1]}}),
        [dataset(1, 1, 10, [record(1, 100, '1'), record(2, 101, '3'), record(3, 102, '5')])],
        units=units
    )
    frame, warnings = prepare(ctx)
    assert values(frame, 10) == [2.0]
    assert frame.observations[0].unit_ids == [100, 101]
    assert frame.observations[0].exclusion['unit_ids'] == [100, 101]
    assert [w.record_ids for w in warnings if w.code == AnalysisWarningCode.UNASSIGNED_UNIT] == [[3]]

def test_germplasm_dimension_assigns_closest_selected():
    units = {100: UnitContext(100, germplasm_id=3), 101: UnitContext(101, germplasm_id=2), 102: UnitContext(102, germplasm_id=9)}
    ctx = context(
        descriptive([concept_term(10), domain_term('GERMPLASM')], grouping={'germplasm': {'germplasm_ids': [1, 2]}}),
        [dataset(1, 1, 10, [record(1, 100, '1'), record(2, 101, '1'), record(3, 102, '1')])],
        units=units,
        germplasm_descendants={1: {2, 3}, 2: {3}}
    )
    frame, warnings = prepare(ctx)
    assert [o.group['germplasm_id'] for o in frame.observations] == [2, 2]
    assert [w.record_ids for w in warnings if w.code == AnalysisWarningCode.UNASSIGNED_GERMPLASM] == [[3]]

def test_germplasm_dimension_with_none_selected_takes_each_units_own():
    units = {100: UnitContext(100, germplasm_id=3), 101: UnitContext(101, germplasm_id=2), 102: UnitContext(102)}
    ctx = context(
        descriptive([concept_term(10), domain_term('GERMPLASM')], grouping={'germplasm': {'germplasm_ids': []}}),
        [dataset(1, 1, 10, [record(1, 100, '1'), record(2, 101, '1'), record(3, 102, '1')])],
        units=units
    )
    frame, warnings = prepare(ctx)
    assert [o.group['germplasm_id'] for o in frame.observations] == [3, 2]
    unassigned, = [w for w in warnings if w.code == AnalysisWarningCode.UNASSIGNED_GERMPLASM]
    assert unassigned.record_ids == [3]
    assert unassigned.message == "1 records could not be assigned to a germplasm and were excluded"

def test_study_only_with_study_term():
    datasets = [dataset(1, 1, 10, [record(1, 100, '1')]), dataset(2, 2, 10, [record(2, 100, '2')])]
    with pytest.raises(AnalysisFailed):
        prepare(context(descriptive([concept_term(10)], dataset_ids=[1, 2]), datasets))
    frame, _ = prepare(context(descriptive([concept_term(10), domain_term('STUDY')], dataset_ids=[1, 2]), datasets))
    assert [o.group['study_id'] for o in frame.observations] == [1, 2]


""" Record group dimensions """
def grouping(grouping_id, scope=GroupingScope.STUDY_WIDE, dataset_scopes=(), extent=RecordGroupExtent.SHARED):
    return RecordGroupingStored(
        id=grouping_id, name=f'g{grouping_id}', type=1, scope=scope, extent=extent, dataset_scopes=list(dataset_scopes)
    )

def test_record_groups_nested_and_shared():
    studies = {1: study(1, [grouping(7)]), 2: study(2, [grouping(8, GroupingScope.DATASET_SCOPED)])}
    datasets = [
        dataset(1, 1, 10, [record(1, 100, '1', groups={7: 'A'}), record(2, 100, '2', groups={7: 'B'})]),
        dataset(2, 2, 10, [record(3, 102, '3', groups={8: 'A'}), record(4, 101, '4')]),
    ]
    dimension = {'name': 'batch', 'grouping_ids': [7, 8], 'levels': [
        {'label': 'shared', 'members': [{'grouping_id': 7, 'code': 'B'}, {'grouping_id': 8, 'code': 'A', 'dataset_id': 2}]}
    ]}
    ctx = context(
        descriptive(
            [concept_term(10), domain_term('RECORD_GROUP', record_group_dimension='batch')],
            grouping={'record_groups': [dimension]}, dataset_ids=[1, 2]
        ),
        datasets, studies=studies
    )
    frame, warnings = prepare(ctx)
    # nested by default, the shared level pools codes across studies
    assert list(frame.data['record_group:batch']) == ['7|*|A', 'shared', 'shared']
    assert [o.record_ids for o in frame.observations] == [[1], [2], [3]]
    assert frame.observations[1].exclusion['record_groups'] == [{'grouping_id': 7, 'code': 'B', 'dataset_id': None}]
    assert frame.observations[2].exclusion['record_groups'] == [{'grouping_id': 8, 'code': 'A', 'dataset_id': 2}]
    assert frame.observations[1].group['record_groups'][0]['shared'] is True
    assert [w.record_ids for w in warnings if w.code == AnalysisWarningCode.UNASSIGNED_RECORD_GROUP] == [[4]]

def test_record_group_grouping_not_found():
    ctx = context(
        descriptive([concept_term(10)], grouping={'record_groups': [{'name': 'batch', 'grouping_ids': [7]}]}),
        [dataset(1, 1, 10, [record(1, 100, '1')])]
    )
    with pytest.raises(AnalysisFailed) as e:
        prepare(ctx)
    assert e.value.errors[0].code == AnalysisErrorCode.GROUPING_NOT_FOUND
    assert e.value.errors[0].path == ['descriptiveStatistics', 'grouping', 'recordGroups', '0', 'groupingIds', '0']


""" Codes of WITHIN_GRAPH groupings, nested in the root of the unit's graph """
# Trees 100 and 101 in the graph of field 1, tree 102 in the graph of field 2, whose root the user can't read
FIELDS = {
    100: UnitContext(100, ancestor_ids=[1], parent_ids=[1], root_id=1),
    101: UnitContext(101, ancestor_ids=[1], parent_ids=[1], root_id=1),
    102: UnitContext(102, ancestor_ids=[], root_id=2),
}

def blocks(levels=()):
    studies = {1: study(1, [grouping(7, extent=RecordGroupExtent.WITHIN_GRAPH)])}
    datasets = [dataset(1, 1, 10, [
        record(1, 100, '1', groups={7: 'Block 1'}), record(2, 101, '2', groups={7: 'Block 1'}),
        record(3, 102, '3', groups={7: 'Block 1'}),
    ])]
    return context(
        descriptive(
            [concept_term(10), domain_term('RECORD_GROUP', record_group_dimension='block')],
            grouping={'record_groups': [{'name': 'block', 'grouping_ids': [7], 'levels': list(levels)}]}
        ),
        datasets, units=FIELDS, studies=studies
    )

def test_within_graph_codes_are_nested_in_the_graph_root():
    frame, _ = prepare(blocks())
    # the same code is one level within a graph, and another in another graph; it can be a term
    assert list(frame.data['record_group:block']) == ['7|*|1|Block 1', '7|*|1|Block 1', '7|*|2|Block 1']
    assert [o.group['record_groups'][0]['unit_id'] for o in frame.observations] == [1, 1, 2]
    assert frame.observations[0].group['record_groups'][0]['shared'] is False

def test_within_graph_code_combined_across_graphs_by_a_level():
    frame, warnings = prepare(blocks(levels=[{'label': 'first', 'members': [{'grouping_id': 7, 'code': 'Block 1'}]}]))
    assert list(frame.data['record_group:block']) == ['first', 'first', 'first']
    assert AnalysisWarningCode.RECORD_GROUP_LEVEL_UNMATCHED not in codes(warnings)


""" Units of a subject as levels, in studies without a grouping of the dimension """
FIELD, PLOT, TREE, SAMPLE = 30, 31, 32, 33
# Field 1 with plots 2 and 3: trees 100 and 101 in plot 2, tree 102 in plot 3.
# Sample 200 is from tree 100, sample 201 from trees 100 and 102, of separate plots.
PLOTS = {
    1: UnitContext(1, subject_id=FIELD),
    2: UnitContext(2, subject_id=PLOT, ancestor_ids=[1], parent_ids=[1]),
    3: UnitContext(3, subject_id=PLOT, ancestor_ids=[1], parent_ids=[1]),
    100: UnitContext(100, subject_id=TREE, ancestor_ids=[2, 1], parent_ids=[2]),
    101: UnitContext(101, subject_id=TREE, ancestor_ids=[2, 1], parent_ids=[2]),
    102: UnitContext(102, subject_id=TREE, ancestor_ids=[3, 1], parent_ids=[3]),
    200: UnitContext(200, subject_id=SAMPLE, ancestor_ids=[100, 2, 1], parent_ids=[100]),
    201: UnitContext(201, subject_id=SAMPLE, ancestor_ids=[100, 102, 2, 3, 1], parent_ids=[100, 102]),
}
PLOT_TERM = domain_term('RECORD_GROUP', record_group_dimension='plot')

def test_nearest_unit_of_a_subject_is_the_level():
    ctx = context(
        descriptive([concept_term(10), PLOT_TERM], grouping={'record_groups': [{'name': 'plot', 'subject_ids': [PLOT]}]}),
        [dataset(1, 1, 10, [
            record(1, 100, '1'), record(2, 101, '2'), record(3, 102, '3'), record(4, 200, '4'), record(5, 2, '5'),
            record(6, 201, '6'), record(7, 1, '7')
        ])],
        units=PLOTS
    )
    frame, warnings = prepare(ctx)
    # a tree's plot, a sample's tree's plot, and a plot itself
    assert list(frame.data['record_group:plot']) == ['unit|2', 'unit|2', 'unit|3', 'unit|2', 'unit|2']
    assert frame.observations[2].group['record_groups'] == [{
        'dimension': 'plot', 'level': 'unit|3', 'shared': False,
        'grouping_id': None, 'scope_dataset_ids': None, 'code': None, 'unit_id': 3
    }]
    assert frame.observations[2].exclusion['record_groups'] is None
    # a sample of trees in two plots, and the field above the plots, have no plot
    assert [w.record_ids for w in warnings if w.code == AnalysisWarningCode.UNASSIGNED_RECORD_GROUP] == [[6, 7]]

def test_each_study_has_one_source_of_levels():
    studies = {1: study(1, [grouping(7)]), 2: study(2)}
    ctx = context(
        descriptive(
            [concept_term(10), PLOT_TERM],
            grouping={'record_groups': [{'name': 'plot', 'grouping_ids': [7], 'subject_ids': [PLOT]}]},
            dataset_ids=[1, 2]
        ),
        [
            dataset(1, 1, 10, [record(1, 100, '1', groups={7: 'Plot 1'}), record(2, 101, '2')]),
            dataset(2, 2, 10, [record(3, 102, '3')]),
        ],
        units=PLOTS, studies=studies
    )
    frame, warnings = prepare(ctx)
    # a record of a study with a grouping has its code or nothing, never its unit's plot
    assert list(frame.data['record_group:plot']) == ['7|*|Plot 1', 'unit|3']
    assert [w.record_ids for w in warnings if w.code == AnalysisWarningCode.UNASSIGNED_RECORD_GROUP] == [[2]]

def test_unit_levels_split_units_rolled_up_above_them():
    ctx = context(
        descriptive(
            [concept_term(10, aggregation='MEAN'), PLOT_TERM],
            grouping={'unit': {'unit_ids': [1]}, 'record_groups': [{'name': 'plot', 'subject_ids': [PLOT]}]}
        ),
        [dataset(1, 1, 10, [record(1, 100, '1'), record(2, 101, '3'), record(3, 102, '5')])],
        units=PLOTS
    )
    frame, _ = prepare(ctx)
    # levels come from the base unit, as codes on its records do
    assert [o.group['unit_id'] for o in frame.observations] == [1, 1]
    assert list(frame.data['record_group:plot']) == ['unit|2', 'unit|3']
    assert values(frame, 10) == [2.0, 5.0]

def test_factor_above_the_unit_levels_applies_across_them():
    concepts = {
        10: ConceptContext(10, ScaleType.NUMERICAL),
        20: ConceptContext(20, ScaleType.NOMINAL, categories=['Shade', 'Sun'], factor=True),
    }
    ctx = context(
        descriptive(
            [concept_term(10), concept_term(20), PLOT_TERM],
            grouping={'record_groups': [{'name': 'plot', 'subject_ids': [PLOT]}]}, dataset_ids=[1, 2]
        ),
        [
            dataset(1, 1, 10, [record(1, 100, '1'), record(2, 102, '2')]),
            dataset(2, 1, 20, [record(3, 2, 'Shade'), record(4, 1, 'Sun')]),
        ],
        units=PLOTS, concepts=concepts
    )
    frame, warnings = prepare(ctx)
    # plot 2's factor applies within it; the field's, with no plot, applies to plot 3
    assert list(frame.data['concept:20']) == ['Shade', 'Sun']
    assert AnalysisWarningCode.UNASSIGNED_RECORD_GROUP not in codes(warnings)



""" Replicates: codes of WITHIN_UNIT groupings """
WITHIN_UNIT = RecordGroupExtent.WITHIN_UNIT
TREES = {100: UnitContext(100, ancestor_ids=[1], parent_ids=[1]), 101: UnitContext(101, ancestor_ids=[1], parent_ids=[1])}

def replicates(scope=GroupingScope.STUDY_WIDE, dataset_scopes=(), extent=WITHIN_UNIT):
    """Study 1 with replicate grouping 7: tree 100 has 2 replicates, tree 101 has 4"""
    studies = {1: study(1, [grouping(7, scope, dataset_scopes, extent)])}
    records = [
        record(1, 100, '1', groups={7: '1'}), record(2, 100, '3', groups={7: '2'}),
        record(3, 101, '10', groups={7: '1'}), record(4, 101, '10', groups={7: '2'}),
        record(5, 101, '10', groups={7: '3'}), record(6, 101, '10', groups={7: '4'}),
    ]
    return studies, [dataset(1, 1, 10, records)]

def test_replicates_are_duplicates_without_replicate_aggregation():
    studies, datasets = replicates()
    ctx = context(descriptive([concept_term(10)]), datasets, studies=studies)
    with pytest.raises(AnalysisFailed) as e:
        prepare(ctx)
    error = e.value.errors[0]
    assert error.code == AnalysisErrorCode.DUPLICATE_OBSERVATION
    assert error.path == ['descriptiveStatistics', 'terms', '0', 'replicateAggregation']
    assert 'WITHIN_UNIT' in error.message

def test_replicate_aggregation_combines_each_reading_first():
    studies, datasets = replicates()
    ctx = context(
        descriptive([concept_term(10, replicate_aggregation={'aggregation': 'MEAN'}, aggregation='MEAN')], grouping={'unit': {'unit_ids': [1]}}),
        datasets, units=TREES, studies=studies
    )
    frame, warnings = prepare(ctx)
    # mean of the tree means (2 and 10), not of the 6 records
    assert values(frame, 10) == [6.0]
    assert AnalysisWarningCode.REPLICATES_POOLED not in codes(warnings)

def test_replicate_aggregation_alone_gives_one_value_per_unit():
    studies, datasets = replicates()
    ctx = context(
        descriptive([concept_term(10, replicate_aggregation={'aggregation': 'MAX'})]),
        datasets, studies=studies
    )
    frame, _ = prepare(ctx)
    assert values(frame, 10) == [3.0, 10.0]

def test_pooled_replicates_warn():
    studies, datasets = replicates()
    ctx = context(
        descriptive([concept_term(10, aggregation='MEAN')], grouping={'unit': {'unit_ids': [1]}}),
        datasets, units=TREES, studies=studies
    )
    frame, warnings = prepare(ctx)
    assert values(frame, 10) == [44 / 6]
    pooled = [w for w in warnings if w.code == AnalysisWarningCode.REPLICATES_POOLED]
    assert pooled[0].path == ['descriptiveStatistics', 'terms', '0', 'replicateAggregation']

def test_shared_grouping_codes_are_not_replicates():
    studies, datasets = replicates(extent=RecordGroupExtent.SHARED)
    ctx = context(
        descriptive([concept_term(10, replicate_aggregation={'aggregation': 'MEAN'})]),
        datasets, studies=studies
    )
    with pytest.raises(AnalysisFailed) as e:
        prepare(ctx)
    # without WITHIN_UNIT codes each record is its own reading
    assert e.value.errors[0].path == ['descriptiveStatistics', 'terms', '0', 'aggregation']

def test_replicates_of_different_times_and_scopes_are_different_readings():
    studies = {1: study(1, [grouping(7, GroupingScope.DATASET_SCOPED, extent=WITHIN_UNIT)])}
    datasets = [
        dataset(1, 1, 10, [
            record(1, 100, '1', start='2020-01-01', groups={7: '1'}), record(2, 100, '3', start='2020-01-01', groups={7: '2'}),
            record(3, 100, '5', start='2020-02-01', groups={7: '1'}),
        ]),
        dataset(2, 1, 10, [record(4, 100, '9', start='2020-01-01', groups={7: '1'})]),
    ]
    ctx = context(
        descriptive([concept_term(10, replicate_aggregation={'aggregation': 'MEAN'}, aggregation='MEAN')], dataset_ids=[1, 2]),
        datasets, studies=studies
    )
    frame, _ = prepare(ctx)
    # readings: 2 (dataset 1, January), 5 (dataset 1, February), 9 (dataset 2, its own scope)
    assert values(frame, 10) == [pytest.approx(16 / 3)]

def test_replicate_window_anchored_on_first_record():
    studies = {1: study(1, [grouping(7, extent=WITHIN_UNIT)])}
    times = ['2020-01-01T10:00', '2020-01-01T10:03', '2020-01-01T10:06', '2020-01-01T10:08', '2020-01-02T09:00']
    datasets = [dataset(1, 1, 10, [
        record(i, 100, str(v), start=t, groups={7: str(i)}) for i, (t, v) in enumerate(zip(times, (1, 3, 10, 20, 100)), start=1)
    ] + [record(9, 100, '7', groups={7: '9'})])]

    def mean_of_readings(window):
        ctx = context(
            descriptive([concept_term(10, replicate_aggregation={'aggregation': 'MEAN', 'window': window}, aggregation='MEAN')]),
            datasets, studies=studies
        )
        return values(prepare(ctx)[0], 10)[0]

    # 5 minutes: 10:00-10:03 (2), 10:06-10:08 (15, not chained to the first), the next day (100), no time (7)
    assert mean_of_readings('PT5M') == pytest.approx((2 + 15 + 100 + 7) / 4)
    # a day from 10:00 takes in 09:00 the next day (26.8), no time (7)
    assert mean_of_readings('P1D') == pytest.approx((26.8 + 7) / 2)
    # no window: every time is a reading
    assert mean_of_readings(None) == pytest.approx(141 / 6)

def test_replicate_window_means():
    studies = {1: study(1, [grouping(7, extent=WITHIN_UNIT)])}
    datasets = [dataset(1, 1, 10, [
        record(1, 100, '1', start='2020-01-01T10:00', groups={7: '1'}),
        record(2, 100, '3', start='2020-01-01T10:04', groups={7: '2'}),
        record(3, 100, '20', start='2020-01-01T11:00', groups={7: '1'}),
    ])]
    ctx = context(
        descriptive([concept_term(10, replicate_aggregation={'aggregation': 'MEAN', 'window': 'PT5M'}, aggregation='MEAN')]),
        datasets, studies=studies
    )
    # readings 2 and 20
    assert values(prepare(ctx)[0], 10) == [11.0]

def test_replicate_dimension_nests_codes_in_the_base_unit():
    studies, datasets = replicates()
    ctx = context(
        descriptive(
            [concept_term(10)],
            grouping={'unit': {'unit_ids': [1]}, 'record_groups': [{'name': 'replicate', 'grouping_ids': [7]}]}
        ),
        datasets, units=TREES, studies=studies
    )
    frame, _ = prepare(ctx)
    # each replicate of each tree stays an observation of the parent unit
    assert len(frame.observations) == 6
    assert [o.group['unit_id'] for o in frame.observations] == [1] * 6
    assert frame.observations[0].group['record_groups'][0]['level'] == '7|*|100|1'
    assert frame.observations[0].group['record_groups'][0]['unit_id'] == 100

def test_replicate_dimension_cannot_be_a_term():
    studies, datasets = replicates()
    ctx = context(
        descriptive(
            [concept_term(10), domain_term('RECORD_GROUP', record_group_dimension='replicate')],
            grouping={'record_groups': [{'name': 'replicate', 'grouping_ids': [7]}]}
        ),
        datasets, studies=studies
    )
    with pytest.raises(AnalysisFailed) as e:
        prepare(ctx)
    assert e.value.errors[0].code == AnalysisErrorCode.CONFIG_INVALID
    assert e.value.errors[0].path == ['descriptiveStatistics', 'terms', '1', 'reference']

def test_replicate_dimension_not_in_anova():
    studies, datasets = replicates()
    analysis = {
        'analysis_type': 'ANOVA',
        'dataset_ids': [1],
        'anova': {
            'terms': [concept_term(10), domain_term('UNIT')],
            'response': {'type': 'CONCEPT', 'concept_id': 10},
            'grouping': {'record_groups': [{'name': 'replicate', 'grouping_ids': [7]}]}
        }
    }
    ctx = context(analysis, datasets, studies=studies)
    with pytest.raises(AnalysisFailed) as e:
        prepare(ctx)
    assert e.value.errors[0].code == AnalysisErrorCode.CONFIG_INVALID
    assert e.value.errors[0].path == ['anova', 'grouping', 'recordGroups', '0']

def test_replicate_codes_cannot_be_shared_levels():
    studies, datasets = replicates()
    dimension = {'name': 'replicate', 'grouping_ids': [7], 'levels': [
        {'label': 'first', 'members': [{'grouping_id': 7, 'code': '1'}]}
    ]}
    ctx = context(
        descriptive([concept_term(10)], grouping={'record_groups': [dimension]}),
        datasets, studies=studies
    )
    with pytest.raises(AnalysisFailed) as e:
        prepare(ctx)
    assert e.value.errors[0].code == AnalysisErrorCode.CONFIG_INVALID
    assert e.value.errors[0].path == ['descriptiveStatistics', 'grouping', 'recordGroups', '0', 'levels', '0', 'members', '0']



""" Factors describe the observations of variables """
FACTOR_CONCEPTS = {
    10: ConceptContext(10, ScaleType.NUMERICAL),
    20: ConceptContext(20, ScaleType.NOMINAL, categories=['Lower', 'Upper', 'Shade', 'Sun'], factor=True),
}

def factor_values(frame):
    return list(frame.data['concept:20'])

def test_undated_factor_applies_to_every_time_bin():
    ctx = context(
        descriptive([concept_term(10), concept_term(20), domain_term('TIME')], grouping={'time': TIME}, dataset_ids=[1, 2]),
        [
            dataset(1, 1, 10, [record(1, 100, '1', start='2020-06-01'), record(2, 100, '2', start='2021-06-01')]),
            dataset(2, 1, 20, [record(3, 100, 'Upper')]),
        ],
        concepts=FACTOR_CONCEPTS
    )
    frame, warnings = prepare(ctx)
    assert list(frame.data['time']) == ['2020', '2021']
    assert factor_values(frame) == ['Upper', 'Upper']
    assert AnalysisWarningCode.UNASSIGNED_TIME not in codes(warnings)
    # the factor record contributes to both observations
    assert [o.record_ids for o in frame.observations] == [[1, 3], [2, 3]]

def test_dated_factor_applies_to_its_time_bin():
    ctx = context(
        descriptive([concept_term(10), concept_term(20)], grouping={'time': TIME}, dataset_ids=[1, 2]),
        [
            dataset(1, 1, 10, [record(1, 100, '1', start='2020-06-01'), record(2, 100, '2', start='2021-06-01')]),
            dataset(2, 1, 20, [record(3, 100, 'Shade', start='2021-02-01')]),
        ],
        concepts=FACTOR_CONCEPTS
    )
    frame, _ = prepare(ctx)
    assert factor_values(frame)[0] is None and factor_values(frame)[1] == 'Shade'

def test_factor_of_the_closest_unit_applies():
    units = {
        1: UnitContext(1),  # a block
        100: UnitContext(100, ancestor_ids=[1], parent_ids=[1]),
        101: UnitContext(101, ancestor_ids=[1], parent_ids=[1]),
    }
    ctx = context(
        descriptive([concept_term(10), concept_term(20)], dataset_ids=[1, 2]),
        [
            dataset(1, 1, 10, [record(1, 100, '1'), record(2, 101, '2')]),
            dataset(2, 1, 20, [record(3, 1, 'Shade'), record(4, 101, 'Sun')]),
        ],
        units=units, concepts=FACTOR_CONCEPTS
    )
    frame, warnings = prepare(ctx)
    # tree 100 takes its block's treatment; tree 101 has its own
    assert factor_values(frame) == ['Shade', 'Sun']
    # the block's record does not widen the exclusion rule of the tree's observation to the block
    assert frame.observations[0].exclusion['unit_ids'] == [100]
    assert AnalysisWarningCode.DATASET_FULLY_EXCLUDED not in codes(warnings)

def test_factor_records_on_separate_lineages_must_agree():
    """
    A sample pooled from trees of two plots takes their plots' factor only when the plots' records agree (PLOTS: sample
    201 is from tree 100 in plot 2 and tree 102 in plot 3); a sample of one tree takes its plot's
    """
    def light(plot_2, plot_3):
        return context(
            descriptive([concept_term(10), concept_term(20)], dataset_ids=[1, 2]),
            [
                dataset(1, 1, 10, [record(1, 200, '1'), record(2, 201, '2')]),
                dataset(2, 1, 20, [record(3, 2, plot_2), record(4, 3, plot_3)]),
            ],
            units=PLOTS, concepts=FACTOR_CONCEPTS
        )
    frame, warnings = prepare(light('Shade', 'Sun'))
    assert factor_values(frame) == ['Shade', None]
    (warning,) = [w for w in warnings if w.code == AnalysisWarningCode.FACTOR_LINEAGES_DIFFER]
    assert warning.record_ids == [3, 4]

    frame, warnings = prepare(light('Shade', 'Shade'))
    assert factor_values(frame) == ['Shade', 'Shade']
    assert AnalysisWarningCode.FACTOR_LINEAGES_DIFFER not in codes(warnings)


def test_a_nearer_factor_record_on_a_lineage_hides_one_further_up():
    """The field's record is above plot 2's on the same lineage, so only the plot's describes the tree"""
    ctx = context(
        descriptive([concept_term(10), concept_term(20)], dataset_ids=[1, 2]),
        [
            dataset(1, 1, 10, [record(1, 100, '1'), record(2, 102, '2')]),
            dataset(2, 1, 20, [record(3, 1, 'Sun'), record(4, 2, 'Shade')]),
        ],
        units=PLOTS, concepts=FACTOR_CONCEPTS
    )
    frame, warnings = prepare(ctx)
    assert factor_values(frame) == ['Shade', 'Sun']
    assert AnalysisWarningCode.FACTOR_LINEAGES_DIFFER not in codes(warnings)


def test_factors_alone_are_the_observations():
    ctx = context(
        descriptive([concept_term(21)], dataset_ids=[2]),
        [dataset(2, 1, 21, [record(3, 100, '120'), record(4, 101, '200')])],
        concepts={21: ConceptContext(21, ScaleType.NUMERICAL, factor=True)}
    )
    frame, _ = prepare(ctx)
    assert values(frame, 21) == [120.0, 200.0]

def test_factor_without_a_code_applies_to_every_replicate():
    studies = {1: study(1, [grouping(7, extent=WITHIN_UNIT)])}
    ctx = context(
        descriptive(
            [concept_term(10), concept_term(20)], dataset_ids=[1, 2],
            grouping={'record_groups': [{'name': 'replicate', 'grouping_ids': [7]}]}
        ),
        [
            dataset(1, 1, 10, [record(1, 100, '1', groups={7: '1'}), record(2, 100, '2', groups={7: '2'})]),
            dataset(2, 1, 20, [record(3, 100, 'Upper')]),
        ],
        studies=studies, concepts=FACTOR_CONCEPTS
    )
    frame, warnings = prepare(ctx)
    assert factor_values(frame) == ['Upper', 'Upper']
    assert AnalysisWarningCode.UNASSIGNED_RECORD_GROUP not in codes(warnings)

def test_factor_describing_no_observation_leaves_its_dataset_unused():
    ctx = context(
        descriptive([concept_term(10), concept_term(20)], dataset_ids=[1, 2]),
        [dataset(1, 1, 10, [record(1, 100, '1')]), dataset(2, 1, 20, [record(3, 999, 'Upper')])],
        concepts=FACTOR_CONCEPTS
    )
    frame, warnings = prepare(ctx)
    assert factor_values(frame) == [None]
    assert [w.path for w in warnings if w.code == AnalysisWarningCode.DATASET_FULLY_EXCLUDED] == [['datasetIds', '1']]


""" Exclusions """
def exclusion_context(exclusions, units=None, studies=None):
    return context(
        descriptive([concept_term(10)], exclusions=exclusions),
        [dataset(1, 1, 10, [
            record(1, 100, '1', start='2020-01-01', end='2020-02-01', groups={7: 'A'}),
            record(2, 101, '2', start='2021-01-01'),
            record(3, 102, '3'),
        ])],
        units=units,
        studies=studies
    )

def included(ctx):
    frame, warnings = prepare(ctx)
    return [r for o in frame.observations for r in o.record_ids], warnings

def test_exclusion_rules_any_rule_all_criteria():
    ids, warnings = included(exclusion_context([
        {'unit_ids': [100, 101], 'start': '2020-06-01'},  # record 2 only: record 1 ends before start
        {'record_ids': [3]},
    ]))
    assert ids == [1]
    excluded = [w for w in warnings if w.code == AnalysisWarningCode.EXCLUDED_BY_CONFIG]
    assert [(w.path, w.message) for w in excluded] == [
        (['exclusions', '0'], 'Exclusion rule 1 matched 1 records'),
        (['exclusions', '1'], 'Exclusion rule 2 matched 1 records'),
    ]

def test_time_bounded_rule_never_matches_record_without_time():
    ids, _ = included(exclusion_context([{'end': '2030-01-01'}]))
    assert ids == [3]

def test_exclusion_by_germplasm_and_record_group():
    units = {100: UnitContext(100, germplasm_id=5), 101: UnitContext(101, germplasm_id=6), 102: UnitContext(102)}
    studies = {1: study(1, [grouping(7)])}
    ids, _ = included(exclusion_context(
        [{'germplasm_ids': [6]}, {'record_groups': [{'grouping_id': 7, 'code': 'A'}]}], units=units, studies=studies
    ))
    assert ids == [3]

def test_position_exclusion_uses_position_history():
    units = {
        100: UnitContext(100, positions=[Position(location_id=1, layout_id=2, coordinates=['1', 'a'], end=datetime64('2019-01-01'))]),
        101: UnitContext(101, positions=[Position(location_id=1, layout_id=2, coordinates=['1', 'b'])]),
        102: UnitContext(102, positions=[Position(location_id=1, layout_id=3, coordinates=['1'])]),
    }
    # axis 0 matches all units in layout 2; unit 100 left the position before the rule starts
    ids, _ = included(exclusion_context([{
        'positions': [{'location_id': 1, 'layout_id': 2, 'axes': [{'index': 0, 'value': '1'}]}],
        'start': '2020-01-01'
    }], units=units))
    assert ids == [1, 3]

def test_dataset_fully_excluded():
    frame_ctx = context(
        descriptive([concept_term(10)], dataset_ids=[1, 2], exclusions=[{'study_ids': [2]}]),
        [dataset(1, 1, 10, [record(1, 100, '1')]), dataset(2, 2, 10, [record(2, 101, '2')])]
    )
    _, warnings = prepare(frame_ctx)
    fully = [w for w in warnings if w.code == AnalysisWarningCode.DATASET_FULLY_EXCLUDED]
    assert [w.path for w in fully] == [['datasetIds', '1']]

def test_insufficient_data():
    with pytest.raises(AnalysisFailed) as e:
        prepare(exclusion_context([{'record_ids': [1, 2, 3]}]))
    assert e.value.errors[0].code == AnalysisErrorCode.INSUFFICIENT_DATA


""" Payload """
def test_job_payload_names_terms_by_title():
    ctx = context(
        descriptive([concept_term(10), domain_term('GERMPLASM')], grouping={'germplasm': {'germplasm_ids': []}}),
        [dataset(1, 1, 10, [record(1, 100, '1'), record(2, 101, '2')])],
        units={100: UnitContext(unit_id=100, germplasm_id=7), 101: UnitContext(unit_id=101, germplasm_id=8)},
        concepts={10: ConceptContext(10, ScaleType.NUMERICAL, name='Height')}
    )
    frame, _ = prepare(ctx)
    payload = build_job_payload('abc', ctx.request, frame)
    assert [(c['name'], c['title']) for c in payload['columns']] == [('concept:10', 'Height'), ('germplasm', 'Germplasm')]

def test_job_payload_is_json_with_nulls():
    ctx = context(
        descriptive([concept_term(10), concept_term(11)], dataset_ids=[1, 2]),
        [dataset(1, 1, 10, [record(1, 100, '1'), record(2, 101, '2')]), dataset(2, 1, 11, [record(3, 100, '3')])]
    )
    frame, _ = prepare(ctx)
    payload = build_job_payload('abc', ctx.request, frame)
    encoded = json.dumps(payload, allow_nan=False)
    assert json.loads(encoded) == payload
    assert payload['analysis_type'] == 'DESCRIPTIVE_STATISTICS'
    assert payload['rows'] == [[1.0, 3.0], [2.0, None]]
    assert [c['name'] for c in payload['columns']] == ['concept:10', 'concept:11']
    assert payload['config']['terms'][0]['reference'] == {
        'type': 'CONCEPT', 'concept_id': 10, 'record_group_dimension': None, 'layout_axis': None
    }
    assert payload['observations'][0]['exclusion'] == {'unit_ids': [100], 'start': None, 'end': None, 'record_groups': None}


def test_representation_resolved_from_scale_must_suit_analysis():
    concepts = {10: ConceptContext(10, ScaleType.NOMINAL, categories=['a', 'b'])}
    analysis = {'analysis_type': 'OUTLIER_DETECTION', 'dataset_ids': [1], 'outlier_detection': {
        'terms': [concept_term(10)], 'method': 'IQR'
    }}
    ctx = context(analysis, [dataset(1, 1, 10, [record(1, 100, 'a')])], concepts=concepts)
    with pytest.raises(AnalysisFailed) as e:
        prepare(ctx)
    assert e.value.errors[0].code == AnalysisErrorCode.INCOMPATIBLE_SCALE
    assert e.value.errors[0].path == ['outlierDetection', 'terms', '0', 'representation']

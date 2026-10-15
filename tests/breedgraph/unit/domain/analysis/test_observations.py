import json
import math

import pytest
from numpy import datetime64

from breedgraph.domain.model.analysis import AnalysisFailed, AnalysisErrorCode, AnalysisWarningCode
from breedgraph.domain.model.analysis_context import UnitContext, ConceptContext
from breedgraph.domain.model.blocks import Position
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

def test_ordinal_aggregation_and_levels():
    concepts = {10: ConceptContext(10, ScaleType.ORDINAL, categories=['low', 'mid', 'high'])}
    ctx = context(
        descriptive([concept_term(10, aggregation='MAX')]),
        [dataset(1, 1, 10, [record(1, 100, 'mid'), record(2, 100, 'low'), record(3, 101, 'high')])],
        concepts=concepts
    )
    frame, _ = prepare(ctx)
    assert values(frame, 10) == ['mid', 'high']
    assert frame.columns[0].levels == ['low', 'mid', 'high']

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
    ctx = context(
        descriptive([concept_term(10, binning={'boundaries': ['10'], 'labels': ['low', 'high'], 'boundary': 'LEFT'})]),
        [dataset(1, 1, 10, [record(1, 100, '10'), record(2, 101, '11')])]
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

def test_unit_grouping_uses_parent_unit():
    units = {
        100: UnitContext(100, ancestor_ids=[1]),
        101: UnitContext(101, ancestor_ids=[1]),
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

def test_position_dimension_by_axes():
    units = {
        100: UnitContext(100, positions=[Position(location_id=1, layout_id=2, coordinates=['1', 'a'])]),
        101: UnitContext(101, positions=[Position(location_id=1, layout_id=2, coordinates=['1', 'b'])]),
        102: UnitContext(102, positions=[Position(location_id=5)]),
    }
    ctx = context(
        descriptive(
            [concept_term(10), domain_term('POSITION')],
            grouping={'position': {'location_id': 1, 'layout_id': 2, 'axis_indexes': [0]}}
        ),
        [dataset(1, 1, 10, [record(1, 100, '1'), record(2, 101, '2'), record(3, 102, '3')])],
        units=units
    )
    frame, warnings = prepare(ctx)
    # same row on axis 0, distinct observation units
    assert frame.data['position'].nunique() == 1
    assert frame.observations[0].group['position'] == {'location_id': 1, 'layout_id': 2, 'coordinates': ['1', None]}
    assert AnalysisWarningCode.UNASSIGNED_POSITION in codes(warnings)

def test_study_only_with_study_term():
    datasets = [dataset(1, 1, 10, [record(1, 100, '1')]), dataset(2, 2, 10, [record(2, 100, '2')])]
    with pytest.raises(AnalysisFailed):
        prepare(context(descriptive([concept_term(10)], dataset_ids=[1, 2]), datasets))
    frame, _ = prepare(context(descriptive([concept_term(10), domain_term('STUDY')], dataset_ids=[1, 2]), datasets))
    assert [o.group['study_id'] for o in frame.observations] == [1, 2]


""" Record group dimensions """
def grouping(grouping_id, scope=GroupingScope.STUDY_WIDE, dataset_scopes=(), type_id=None):
    return RecordGroupingStored(
        id=grouping_id, name=f'g{grouping_id}', type=type_id, scope=scope, dataset_scopes=list(dataset_scopes)
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



""" Replicates: codes of WITHIN_UNIT groupings """
REPLICATE_TYPE = 50
EXTENTS = {REPLICATE_TYPE: RecordGroupExtent.WITHIN_UNIT}
TREES = {100: UnitContext(100, ancestor_ids=[1]), 101: UnitContext(101, ancestor_ids=[1])}

def replicates(scope=GroupingScope.STUDY_WIDE, dataset_scopes=()):
    """Study 1 with replicate grouping 7: tree 100 has 2 replicates, tree 101 has 4"""
    studies = {1: study(1, [grouping(7, scope, dataset_scopes, type_id=REPLICATE_TYPE)])}
    records = [
        record(1, 100, '1', groups={7: '1'}), record(2, 100, '3', groups={7: '2'}),
        record(3, 101, '10', groups={7: '1'}), record(4, 101, '10', groups={7: '2'}),
        record(5, 101, '10', groups={7: '3'}), record(6, 101, '10', groups={7: '4'}),
    ]
    return studies, [dataset(1, 1, 10, records)]

def test_replicates_are_duplicates_without_replicate_aggregation():
    studies, datasets = replicates()
    ctx = context(descriptive([concept_term(10)]), datasets, studies=studies, record_group_extents=EXTENTS)
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
        datasets, units=TREES, studies=studies, record_group_extents=EXTENTS
    )
    frame, warnings = prepare(ctx)
    # mean of the tree means (2 and 10), not of the 6 records
    assert values(frame, 10) == [6.0]
    assert AnalysisWarningCode.REPLICATES_POOLED not in codes(warnings)

def test_replicate_aggregation_alone_gives_one_value_per_unit():
    studies, datasets = replicates()
    ctx = context(
        descriptive([concept_term(10, replicate_aggregation={'aggregation': 'MAX'})]),
        datasets, studies=studies, record_group_extents=EXTENTS
    )
    frame, _ = prepare(ctx)
    assert values(frame, 10) == [3.0, 10.0]

def test_pooled_replicates_warn():
    studies, datasets = replicates()
    ctx = context(
        descriptive([concept_term(10, aggregation='MEAN')], grouping={'unit': {'unit_ids': [1]}}),
        datasets, units=TREES, studies=studies, record_group_extents=EXTENTS
    )
    frame, warnings = prepare(ctx)
    assert values(frame, 10) == [44 / 6]
    pooled = [w for w in warnings if w.code == AnalysisWarningCode.REPLICATES_POOLED]
    assert pooled[0].path == ['descriptiveStatistics', 'terms', '0', 'replicateAggregation']

def test_shared_grouping_codes_are_not_replicates():
    studies, datasets = replicates()
    ctx = context(
        descriptive([concept_term(10, replicate_aggregation={'aggregation': 'MEAN'})]),
        datasets, studies=studies, record_group_extents={REPLICATE_TYPE: RecordGroupExtent.SHARED}
    )
    with pytest.raises(AnalysisFailed) as e:
        prepare(ctx)
    # without WITHIN_UNIT codes each record is its own reading
    assert e.value.errors[0].path == ['descriptiveStatistics', 'terms', '0', 'aggregation']

def test_replicates_of_different_times_and_scopes_are_different_readings():
    studies = {1: study(1, [grouping(7, GroupingScope.DATASET_SCOPED, type_id=REPLICATE_TYPE)])}
    datasets = [
        dataset(1, 1, 10, [
            record(1, 100, '1', start='2020-01-01', groups={7: '1'}), record(2, 100, '3', start='2020-01-01', groups={7: '2'}),
            record(3, 100, '5', start='2020-02-01', groups={7: '1'}),
        ]),
        dataset(2, 1, 10, [record(4, 100, '9', start='2020-01-01', groups={7: '1'})]),
    ]
    ctx = context(
        descriptive([concept_term(10, replicate_aggregation={'aggregation': 'MEAN'}, aggregation='MEAN')], dataset_ids=[1, 2]),
        datasets, studies=studies, record_group_extents=EXTENTS
    )
    frame, _ = prepare(ctx)
    # readings: 2 (dataset 1, January), 5 (dataset 1, February), 9 (dataset 2, its own scope)
    assert values(frame, 10) == [pytest.approx(16 / 3)]

def test_replicate_window_anchored_on_first_record():
    studies = {1: study(1, [grouping(7, type_id=REPLICATE_TYPE)])}
    times = ['2020-01-01T10:00', '2020-01-01T10:03', '2020-01-01T10:06', '2020-01-01T10:08', '2020-01-02T09:00']
    datasets = [dataset(1, 1, 10, [
        record(i, 100, str(v), start=t, groups={7: str(i)}) for i, (t, v) in enumerate(zip(times, (1, 3, 10, 20, 100)), start=1)
    ] + [record(9, 100, '7', groups={7: '9'})])]

    def mean_of_readings(window):
        ctx = context(
            descriptive([concept_term(10, replicate_aggregation={'aggregation': 'MEAN', 'window': window}, aggregation='MEAN')]),
            datasets, studies=studies, record_group_extents=EXTENTS
        )
        return values(prepare(ctx)[0], 10)[0]

    # 5 minutes: 10:00-10:03 (2), 10:06-10:08 (15, not chained to the first), the next day (100), no time (7)
    assert mean_of_readings('PT5M') == pytest.approx((2 + 15 + 100 + 7) / 4)
    # a day from 10:00 takes in 09:00 the next day (26.8), no time (7)
    assert mean_of_readings('P1D') == pytest.approx((26.8 + 7) / 2)
    # no window: every time is a reading
    assert mean_of_readings(None) == pytest.approx(141 / 6)

def test_replicate_window_means():
    studies = {1: study(1, [grouping(7, type_id=REPLICATE_TYPE)])}
    datasets = [dataset(1, 1, 10, [
        record(1, 100, '1', start='2020-01-01T10:00', groups={7: '1'}),
        record(2, 100, '3', start='2020-01-01T10:04', groups={7: '2'}),
        record(3, 100, '20', start='2020-01-01T11:00', groups={7: '1'}),
    ])]
    ctx = context(
        descriptive([concept_term(10, replicate_aggregation={'aggregation': 'MEAN', 'window': 'PT5M'}, aggregation='MEAN')]),
        datasets, studies=studies, record_group_extents=EXTENTS
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
        datasets, units=TREES, studies=studies, record_group_extents=EXTENTS
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
        datasets, studies=studies, record_group_extents=EXTENTS
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
    ctx = context(analysis, datasets, studies=studies, record_group_extents=EXTENTS)
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
        datasets, studies=studies, record_group_extents=EXTENTS
    )
    with pytest.raises(AnalysisFailed) as e:
        prepare(ctx)
    assert e.value.errors[0].code == AnalysisErrorCode.CONFIG_INVALID
    assert e.value.errors[0].path == ['descriptiveStatistics', 'grouping', 'recordGroups', '0', 'levels', '0', 'members', '0']


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
        (['exclusions', '0'], 'Exclusion rule 0 matched 1 records'),
        (['exclusions', '1'], 'Exclusion rule 1 matched 1 records'),
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
    assert payload['config']['terms'][0]['reference'] == {'type': 'CONCEPT', 'concept_id': 10, 'record_group_dimension': None}
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

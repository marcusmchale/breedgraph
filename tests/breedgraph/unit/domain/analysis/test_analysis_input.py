import pytest
from pydantic import ValidationError

from breedgraph.domain.importers.analysis import AnalysisInputImport, validation_messages
from breedgraph.domain.model.analysis import (
    AnalysisType, AnovaSpec, AnalysisTermType, AnalysisErrorCode, SumOfSquaresType, EstimatedMeansContrast,
    AnalysisConfigInvalid
)
from breedgraph.domain.services.analysis_validation import validate_request

from .factories import concept_term, domain_term


def anova(**spec):
    return {
        'analysis_type': 'ANOVA',
        'dataset_ids': ['1', '2'],
        'anova': {
            'terms': [
                concept_term('10'),
                concept_term('11', representation='CATEGORICAL'),
                domain_term('GERMPLASM')
            ],
            'response': {'type': 'CONCEPT', 'concept_id': '10'},
            'grouping': {'germplasm': {'germplasm_ids': ['5']}},
            **spec
        }
    }

def messages(analysis: dict):
    try:
        request = AnalysisInputImport(**analysis).to_domain()
    except ValidationError as e:
        return {(tuple(m.path or []), m.message) for m in validation_messages(e)}
    return {(tuple(m.path or []), m.message) for m in validate_request(request)}

def paths(analysis: dict):
    return {path for path, _ in messages(analysis)}


def test_valid_anova_to_domain():
    request = AnalysisInputImport(**anova(estimated_means=[{'terms': [{'type': 'GERMPLASM'}]}])).to_domain()
    assert request.analysis_type == AnalysisType.ANOVA
    assert request.dataset_ids == [1, 2]
    spec = request.spec
    assert isinstance(spec, AnovaSpec)
    assert spec.response.concept_id == 10
    assert spec.sum_of_squares == SumOfSquaresType.TYPE_III
    assert spec.estimated_means[0].contrast == EstimatedMeansContrast.PAIRWISE
    assert [t.reference.type for t in spec.model_terms] == [AnalysisTermType.CONCEPT, AnalysisTermType.GERMPLASM]
    assert validate_request(request) == []

def test_spec_must_match_type():
    analysis = anova()
    analysis['mds'] = {'terms': [concept_term(1)], 'distance': 'EUCLIDEAN'}
    assert paths(analysis) == {()}

def test_structural_errors_have_paths():
    analysis = anova()
    analysis['exclusions'] = [{}, {'start': '2020-01-02', 'end': '2020-01-01'}, {'positions': [{'location_id': 1, 'axes': [{'index': 0, 'value': 'a'}]}]}]
    analysis['anova']['terms'][0]['reference'] = {'type': 'CONCEPT'}
    analysis['anova']['grouping']['record_groups'] = [{'name': 'b', 'grouping_ids': [1], 'levels': [
        {'label': 'x|y', 'members': [{'grouping_id': 1, 'code': 'a'}]}
    ]}]
    assert paths(analysis) == {
        ('exclusions', '0'),
        ('exclusions', '1'),
        ('exclusions', '2', 'positions', '0'),
        ('anova', 'terms', '0', 'reference'),
        ('anova', 'grouping', 'recordGroups', '0', 'levels', '0'),
    }

def test_unknown_fields_rejected():
    analysis = anova()
    analysis['anova']['tukey'] = {'terms': []}
    assert paths(analysis) == {('anova', 'tukey')}

@pytest.mark.parametrize('change, expected', [
    # response must be a continuous concept term without effect
    (lambda a: a['anova'].update(response={'type': 'CONCEPT', 'concept_id': 99}), ('anova', 'response')),
    (lambda a: a['anova']['terms'][0].update(representation='CATEGORICAL'), ('anova', 'response')),
    (lambda a: a['anova']['terms'][0].update(effect='FIXED'), ('anova', 'response')),
    # domain terms require their dimension
    (lambda a: a['anova'].update(grouping={}), ('anova', 'terms', '2', 'reference', 'type')),
    (lambda a: a['anova']['terms'].append(domain_term('RECORD_GROUP', record_group_dimension='batch')),
     ('anova', 'terms', '3', 'reference', 'recordGroupDimension')),
    # random slopes
    (lambda a: a['anova']['terms'][2].update(random_slope_terms=[{'type': 'CONCEPT', 'concept_id': 11}]),
     ('anova', 'terms', '2', 'randomSlopeTerms')),
    # interactions and estimated means reference model terms
    (lambda a: a['anova'].update(interactions=[{'terms': [{'type': 'CONCEPT', 'concept_id': 10}, {'type': 'GERMPLASM'}]}]),
     ('anova', 'interactions', '0', 'terms', '0')),
    (lambda a: a['anova'].update(estimated_means=[{'terms': [{'type': 'GERMPLASM'}], 'contrast': 'TRT_VS_CTRL'}]),
     ('anova', 'estimatedMeans', '0', 'control')),
    (lambda a: a['anova'].update(estimated_means=[{'terms': [{'type': 'GERMPLASM'}], 'control': 'x'}]),
     ('anova', 'estimatedMeans', '0', 'control')),
    # random terms are categorical and not part of interactions
    (lambda a: a['anova']['terms'][1].update(effect='RANDOM', representation='CONTINUOUS'),
     ('anova', 'terms', '1', 'representation')),
    (lambda a: (a['anova']['terms'][2].update(effect='RANDOM'), a['anova'].update(
        interactions=[{'terms': [{'type': 'CONCEPT', 'concept_id': 11}, {'type': 'GERMPLASM'}]}])),
     ('anova', 'interactions', '0')),
    # duplicates
    (lambda a: a.update(dataset_ids=[1, 1]), ('datasetIds',)),
    (lambda a: a['anova']['terms'].append(domain_term('GERMPLASM')), ('anova', 'terms', '3', 'reference')),
])
def test_semantic_errors(change, expected):
    analysis = anova()
    change(analysis)
    assert expected in paths(analysis)

def test_record_group_dimensions():
    analysis = anova()
    analysis['anova']['grouping']['record_groups'] = [
        {'name': 'Batch', 'grouping_ids': [1, 2]},
        {'name': 'batch', 'grouping_ids': [2]},
    ]
    assert paths(analysis) == {
        ('anova', 'grouping', 'recordGroups', '1', 'name'),
        ('anova', 'grouping', 'recordGroups', '1', 'groupingIds', '0'),
    }

def test_domain_term_options():
    analysis = anova()
    analysis['anova']['terms'][2].update(transformations=['LOG'], aggregation='MEAN')
    assert paths(analysis) == {
        ('anova', 'terms', '2', 'transformations'),
        ('anova', 'terms', '2', 'aggregation'),
    }


@pytest.mark.asyncio
async def test_request_analysis_rejects_invalid_input_before_storing():
    from asyncio import Queue
    from breedgraph.domain.commands.analysis import RequestAnalysis
    from breedgraph.service_layer.handlers.commands.analysis import request_analysis

    class StateStore:
        stored = None
        async def store_analysis(self, agent_id, analysis):
            self.stored = analysis
            return 'id'

    state_store, queue = StateStore(), Queue()
    analysis = anova()
    analysis['anova'].update(response={'type': 'TIME'})
    with pytest.raises(AnalysisConfigInvalid) as e:
        await request_analysis(RequestAnalysis(agent_id=1, analysis=analysis), state_store=state_store, event_queue=queue)
    assert {tuple(m.path) for m in e.value.errors} >= {('anova', 'response')}
    assert all(m.code == AnalysisErrorCode.CONFIG_INVALID for m in e.value.errors)
    assert state_store.stored is None and queue.empty()

    analysis_id = await request_analysis(RequestAnalysis(agent_id=1, analysis=anova()), state_store=state_store, event_queue=queue)
    assert analysis_id == 'id'
    assert state_store.stored == anova()  # stored as an exact mirror of the input
    assert queue.qsize() == 1


def test_mds_validation():
    analysis = {
        'analysis_type': 'MDS', 'dataset_ids': [1],
        'mds': {
            'terms': [concept_term(1), concept_term(2, representation='CATEGORICAL')],
            'distance': 'EUCLIDEAN',
            'clustering': {'method': 'HIERARCHICAL'}
        }
    }
    assert paths(analysis) == {('mds', 'terms', '1', 'representation'), ('mds', 'clustering', 'clusters')}

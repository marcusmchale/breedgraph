"""Builders for job payloads, in the format of breedgraph.domain.services.analysis_job."""
from analysis_worker.domain.model.job import AnalysisJob


def concept(concept_id: int) -> dict:
    return {'type': 'CONCEPT', 'concept_id': concept_id, 'record_group_dimension': None}

def domain(term_type: str, dimension: str | None = None) -> dict:
    return {'type': term_type, 'concept_id': None, 'record_group_dimension': dimension}

def name(reference: dict) -> str:
    if reference['type'] == 'CONCEPT':
        return f"concept:{reference['concept_id']}"
    if reference['type'] == 'RECORD_GROUP':
        return f"record_group:{reference['record_group_dimension']}"
    return reference['type'].lower()

def column(reference: dict, kind: str = 'CONTINUOUS', levels: list[str] | None = None) -> dict:
    return {'name': name(reference), 'term': reference, 'kind': kind, 'levels': levels}

def term(reference: dict, effect: str | None = None, slopes: list[dict] | None = None) -> dict:
    return {
        'reference': reference, 'representation': None, 'binning': None, 'level_order': None,
        'transformations': [], 'aggregation': 'NONE', 'effect': effect, 'random_slope_terms': slopes or []
    }

def job(analysis_type: str, config: dict, columns: list[dict], rows: list[list]) -> AnalysisJob:
    observations = [
        {
            'group': {'time': None, 'germplasm_id': None, 'unit_id': i, 'position': None, 'study_id': None,
                      'record_groups': []},
            'record_ids': [i],
            'unit_ids': [i],
            'exclusion': {'unit_ids': [i], 'start': None, 'end': None, 'record_groups': None}
        }
        for i in range(len(rows))
    ]
    config = {'terms': [term(c['term']) for c in columns], 'grouping': {}} | config
    return AnalysisJob(analysis_id='a', lease='l', lease_seconds=60, payload={
        'version': 1, 'analysis_id': 'a', 'analysis_type': analysis_type, 'config': config,
        'columns': columns, 'rows': rows, 'observations': observations
    })

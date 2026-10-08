"""Builders for analysis contexts from plain values, standing in for repository aggregates."""
from types import SimpleNamespace

from numpy import datetime64

from breedgraph.domain.importers.analysis import AnalysisInputImport
from breedgraph.domain.model.analysis_context import AnalysisContext, ConceptContext, UnitContext
from breedgraph.domain.model.datasets import RecordGroup
from breedgraph.domain.model.ontology import ScaleType


def record(record_id, unit, value, start=None, end=None, groups=None):
    return SimpleNamespace(
        id=record_id,
        unit=unit,
        value=value,
        start=datetime64(start) if start else None,
        end=datetime64(end) if end else None,
        groups=[RecordGroup(id=g, code=c) for g, c in (groups or {}).items()]
    )

def dataset(dataset_id, study, concept, records):
    return SimpleNamespace(id=dataset_id, study=study, concept=concept, records=records)

def study(study_id, groupings=()):
    return SimpleNamespace(id=study_id, groupings=list(groupings))

def request(analysis: dict):
    return AnalysisInputImport(**analysis).to_domain()

def descriptive(terms, grouping=None, dataset_ids=(1,), exclusions=None, **spec):
    analysis = {
        'analysis_type': 'DESCRIPTIVE_STATISTICS',
        'dataset_ids': list(dataset_ids),
        'descriptive_statistics': {'terms': terms, 'grouping': grouping or {}, **spec}
    }
    if exclusions is not None:
        analysis['exclusions'] = exclusions
    return analysis

def concept_term(concept_id, **options):
    return {'reference': {'type': 'CONCEPT', 'concept_id': concept_id}, **options}

def domain_term(term_type, **reference):
    return {'reference': {'type': term_type, **reference}}

def context(
        analysis: dict,
        datasets,
        units=None,
        concepts=None,
        studies=None,
        germplasm_descendants=None
) -> AnalysisContext:
    datasets = {d.id: d for d in datasets}
    concepts = concepts or {
        d.concept: ConceptContext(concept_id=d.concept, scale_type=ScaleType.NUMERICAL) for d in datasets.values()
    }
    if units is None:
        units = {
            r.unit: UnitContext(unit_id=r.unit) for d in datasets.values() for r in d.records if r.unit is not None
        }
    if studies is None:
        studies = {d.study: study(d.study) for d in datasets.values()}
    return AnalysisContext(
        request=request(analysis),
        datasets=datasets,
        concepts=concepts,
        units=units,
        studies=studies,
        germplasm_descendants=germplasm_descendants or {}
    )

from types import SimpleNamespace

from numpy import datetime64

from breedgraph.domain.model.ontology import OntologyEntryLabel
from breedcafs_migration.datasets import RecordPlan
from breedcafs_migration.ontology import OntologyIds
from breedcafs_migration.validate import replicate_summary


def test_replicate_summary():
    ontology = OntologyIds()
    ontology.inputs[('A', 'CIRAS3')] = (OntologyEntryLabel.VARIABLE, 1)
    ontology.inputs[('Tree height', '')] = (OntologyEntryLabel.VARIABLE, 2)
    t1, t2 = datetime64('2020-01-01T10:00'), datetime64('2020-01-01T10:05')
    plan = SimpleNamespace(datasets={
        ('Study', 1, '100', '7'): [
            RecordPlan('1_T1', '5', t1, t1, '1'), RecordPlan('1_T1', '6', t1, t1, '2'),   # one reading, 2 replicates
            RecordPlan('1_T1', '7', t2, t2, '3'),                                         # minutes later: its own
            RecordPlan('1_T2', '8', t1, t1, '4'),
        ],
        ('Study', 2, '100', '7'): [RecordPlan('1_T1', '12', t1, t1, '0'), RecordPlan('1_T2', '13', t1, t1, None)],
    })
    section = replicate_summary(plan, ontology)
    assert section.rows == [
        ['A (CIRAS3)', 4, 4, 1, 2, '1–4'],
        ['Tree height', 2, 0, 0, 0, ''],   # code 0 is not migrated
    ]

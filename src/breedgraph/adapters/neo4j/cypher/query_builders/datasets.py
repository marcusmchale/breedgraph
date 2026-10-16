from typing import AbstractSet

from breedgraph.domain.model.controls import ControlledModelLabel
from breedgraph.adapters.neo4j.cypher.query_builders.access import visible as _visible, readable as _readable_as

# Datasets as the user may see them (see docs/read-access.md). A readable dataset is returned in full, all its records
# included; a hidden one only as a placeholder when asked for by id, and not at all from a search. A record's unit is a
# reference to another aggregate, so the units of a readable dataset's records are all shown, hidden ones as
# placeholders (the units view does that), but hidden units above them are not: in the tree of a dataset's units a
# recorded unit hangs from its nearest readable ancestor, and a hidden unit stands alone, holding nothing below it.

DATASET = ControlledModelLabel.DATASET
UNIT = ControlledModelLabel.UNIT
EDGE = 'INCLUDES_UNIT'

# A record is in the window when its own period (start to end, either standing in for a missing other) overlaps it
IN_WINDOW = """($start IS NULL OR coalesce(record.end, record.start) >= $start)
  AND ($end IS NULL OR coalesce(record.start, record.end) <= $end)"""


def _readable(unit: str) -> str:
    return _readable_as(unit, UNIT)

# The summary fields read from the datasets' units rather than from their records alone
UNIT_FIELDS = frozenset({'unit_count', 'subject_ids', 'unit_root_ids', 'location_ids'})
SUMMARY_FIELDS = UNIT_FIELDS | {'record_count', 'start', 'end'}


def _check_fields(fields: AbstractSet[str]):
    unknown = set(fields) - SUMMARY_FIELDS
    if unknown:
        raise ValueError(f"Unknown dataset summary fields: {sorted(unknown)}")


def dataset_summaries(fields: AbstractSet[str] = SUMMARY_FIELDS):
    """
    The summaries of a study's readable datasets with the fields that don't need their units: the record count is
    the dataset's relationship degree, and the time range reads its records unless the unit summaries
    (dataset_unit_summaries) read it on the way.
    """
    _check_fields(fields)
    returns = ['id: dataset.id', 'concept_id: concept.id']
    parts = []
    if 'record_count' in fields:
        returns.append('record_count: COUNT { (dataset)-[:INCLUDES_RECORD]->(:Record) }')
    if fields & {'start', 'end'} and not fields & UNIT_FIELDS:
        parts.append("""
            CALL (dataset) {
              MATCH (dataset)-[:INCLUDES_RECORD]->(record:Record)
              RETURN
                min(coalesce(record.start, record.end)) AS start,
                max(coalesce(record.end, record.start)) AS end
            }
        """)
        returns.extend(['start: start', 'end: end'])

    return f"""
        MATCH (study: Study {{id: $study_id}})
                <-[:FOR_STUDY]-(dataset: Dataset)
                -[:FOR_CONCEPT]->(concept: Variable | Factor)
        {_visible('dataset', ControlledModelLabel.DATASET, 'dataset_visible')}
        WITH concept, dataset WHERE dataset_visible
        {''.join(parts)}
        RETURN {{ {', '.join(returns)} }} AS dataset_summary
        ORDER BY dataset.id
    """


def dataset_unit_summaries(fields: AbstractSet[str] = SUMMARY_FIELDS):
    """
    What the units of the datasets with ids $dataset_ids add to their summaries, for the given fields, one row per
    dataset with records. Datasets of a study share most of their units, so each unit's subjects and unit graph are read
    once, then credited to every dataset it has records in. A unit's locations are those of its positions that
    overlap the time span of its records in the dataset, or all of them when either is untimed. The time range of
    each dataset comes from the same pass.
    """
    _check_fields(fields)
    # Hidden units count, as the records for them are readable, but their subjects, unit graphs and locations are not shown
    locations = 'location_ids' in fields
    timed = bool(fields & {'start', 'end'})
    spans = timed or locations

    # one row per dataset and unit
    use = ['dataset_id: dataset_id']
    query = ["""
        UNWIND $dataset_ids AS dataset_id
        MATCH (dataset:Dataset {id: dataset_id})-[:INCLUDES_RECORD]->(record:Record)-[:FOR_UNIT]->(unit:Unit)
    """]
    if spans:
        query.append("""
        WITH unit, dataset_id,
          min(coalesce(record.start, record.end)) AS first, max(coalesce(record.end, record.start)) AS last
        """)
        use.extend(['first: first', 'last: last'])
    else:
        query.append("WITH DISTINCT unit, dataset_id")
    if locations:
        query.append("""
        CALL (unit, first, last) {
          OPTIONAL MATCH (unit)-[:IN_POSITION]->(position:Position)-[:AT_LOCATION]->(location:Location)
          WHERE (position.start IS NULL OR last IS NULL OR position.start <= last)
          AND (position.end IS NULL OR first IS NULL OR position.end >= first)
          RETURN collect(DISTINCT location.id) AS location_ids
        }
        """)
        use.append('location_ids: location_ids')

    # one row per unit, with what it was in each dataset
    query.append(f"WITH unit, collect({{ {', '.join(use)} }}) AS uses")
    if fields & {'subject_ids', 'unit_root_ids', 'location_ids'}:
        query.append(f"WITH unit, uses {_visible('unit', UNIT, 'unit_readable')}")
    if 'subject_ids' in fields:
        query.append("""
        CALL (unit, unit_readable) {
          OPTIONAL MATCH (unit)-[:OF_SUBJECT]->(subject:Subject) WHERE unit_readable
          RETURN collect(DISTINCT subject.id) AS subject_ids
        }
        """)
    if 'unit_root_ids' in fields:
        # a readable unit's unit graph root, a placeholder if hidden, as the unit graphs view keeps it
        query.append("""
        CALL (unit, unit_readable) {
          OPTIONAL MATCH (root:Unit)-[:INCLUDES_UNIT*0..]->(unit) WHERE unit_readable AND NOT (:Unit)-[:INCLUDES_UNIT]->(root)
          RETURN collect(DISTINCT root.id) AS unit_root_ids
        }
        """)

    # one row per dataset
    query.append("UNWIND uses AS use")
    aggregates = ['use.dataset_id AS dataset_id', 'count(unit) AS unit_count']
    returns = ['id: dataset_id']
    if 'unit_count' in fields:
        returns.append('unit_count: unit_count')
    if timed:
        aggregates.extend(['min(use.first) AS start', 'max(use.last) AS end'])
        returns.extend(['start: start', 'end: end'])
    for name, values in [
        ('subject_ids', 'subject_ids'),
        ('unit_root_ids', 'unit_root_ids'),
        ('location_ids', 'CASE WHEN unit_readable THEN use.location_ids ELSE [] END')
    ]:
        if name in fields:
            aggregates.append(f'collect({values}) AS {name}_lists')
            returns.append(f'{name}: apoc.coll.toSet(apoc.coll.flatten({name}_lists))')
    query.append(f"WITH {', '.join(aggregates)}")
    query.append(f"RETURN {{ {', '.join(returns)} }} AS unit_summary")
    return '\n'.join(query)


def read_datasets():
    """
    Dataset headers by id ($dataset_ids), study ($study_ids) and/or concept ($concept_ids), null parameters matching
    everything, with their record counts; records are read separately (read_records). A dataset the user cannot read
    is a placeholder when asked for by id alone, and is otherwise left out: a search does not show what it found hidden
    """
    return f"""
        MATCH (dataset:Dataset)
        WHERE ($dataset_ids IS NULL OR dataset.id IN $dataset_ids)
          AND ($study_ids IS NULL OR EXISTS {{ (dataset)-[:FOR_STUDY]->(study:Study) WHERE study.id IN $study_ids }})
          AND ($concept_ids IS NULL OR EXISTS {{ (dataset)-[:FOR_CONCEPT]->(concept:Variable|Factor) WHERE concept.id IN $concept_ids }})
        {_visible('dataset', DATASET, 'dataset_visible')}
        WITH dataset, dataset_visible
        WHERE dataset_visible OR ($dataset_ids IS NOT NULL AND $study_ids IS NULL AND $concept_ids IS NULL)
        RETURN CASE WHEN dataset_visible THEN dataset {{
          id: dataset.id,
          study: [(dataset)-[:FOR_STUDY]->(study:Study) | study.id][0],
          concept: [(dataset)-[:FOR_CONCEPT]->(concept:Variable|Factor) | concept.id][0],
          contributors: [(dataset)<-[:CONTRIBUTED_TO]-(contributor:Person) | contributor.id],
          references: [(dataset)<-[:REFERENCE_FOR]-(reference:Reference) | reference.id],
          record_count: COUNT {{ (dataset)-[:INCLUDES_RECORD]->(:Record) }}
        }} ELSE dataset {{
          id: dataset.id, study: null, concept: null, contributors: [], references: [], record_count: 0
        }} END AS dataset
        ORDER BY dataset.id
    """


def _selected_units() -> str:
    """
    A call collecting, as selected_units, the ids of the units $unit_ids select: each unit and, when the user can read
    it, every unit below it. A hidden unit selects only itself, as it holds nothing in the tree of a dataset's units
    """
    return f"""
        CALL () {{
          UNWIND coalesce($unit_ids, []) AS selected_id
          MATCH (selected:Unit {{id: selected_id}})
          WITH selected, {_readable('selected')} AS expands
          MATCH (selected)-[:{EDGE}*0..]->(descendant:Unit)
          WHERE expands OR descendant = selected
          RETURN collect(DISTINCT descendant.id) AS selected_units
        }}
    """


def _dataset_records() -> str:
    """The records of the readable dataset $dataset_id, narrowed to the units $unit_ids select and the time window"""
    return f"""
        MATCH (dataset:Dataset {{id: $dataset_id}})
        {_selected_units()}
        MATCH (dataset)-[:INCLUDES_RECORD]->(record:Record)-[:FOR_UNIT]->(unit:Unit)
        WHERE ($unit_ids IS NULL OR unit.id IN selected_units)
          AND {IN_WINDOW}
    """


def _utc_text(time: str) -> str:
    """A stored time as its UTC wall-clock time in ISO text, without an offset, as numpy parses it; null stays null"""
    return f"CASE WHEN {time} IS NULL THEN null ELSE toString(localdatetime(datetime({{datetime: {time}, timezone: 'UTC'}}))) END"


def read_records():
    """A page of a readable dataset's records in submission order, narrowed as _dataset_records"""
    return f"""
        {_dataset_records()}
        WITH record, unit
        ORDER BY record.submitted, record.id
        SKIP $offset
        LIMIT $limit
        RETURN record {{
          .id, .value, .start_unit, .start_step, .end_unit, .end_step,
          // times as text: hydrating the driver's DateTimes is the slowest part of reading many records
          start: {_utc_text('record.start')},
          end: {_utc_text('record.end')},
          submitted: toString(record.submitted),
          unit: unit.id,
          references: [(record)<-[:REFERENCE_FOR]-(reference:Reference) | reference.id],
          groups: [
            (record)-[:IN_GROUP]->(group:RecordGroup)<-[:HAS_GROUP]-(grouping:RecordGrouping) |
            {{ id: grouping.id, code: group.code }}
          ]
        }} AS record
    """


def count_records():
    """The number of a readable dataset's records, narrowed as _dataset_records, so a client can page through them"""
    return f"""
        {_dataset_records()}
        RETURN count(record) AS record_count
    """


def read_unit_ids():
    """
    The ids of the units a readable dataset has records for, in id order, narrowed as _dataset_records, so a client
    can page through records by unit and keep every unit's records together
    """
    return f"""
        {_dataset_records()}
        WITH DISTINCT unit.id AS unit_id
        ORDER BY unit_id
        RETURN collect(unit_id) AS unit_ids
    """


def _has_records(unit: str) -> str:
    """A predicate for whether the readable datasets $dataset_ids have records for unit in the time window"""
    return f"""EXISTS {{
          MATCH ({unit})<-[:FOR_UNIT]-(record:Record)<-[:INCLUDES_RECORD]-(dataset:Dataset)
          WHERE dataset.id IN $dataset_ids AND {IN_WINDOW}
        }}"""


def read_unit_level():
    """
    One level of the tree of the units the readable datasets $dataset_ids have records for in the time window: the
    children of the units $parent_ids, or with no parents the roots. The tree holds every recorded unit and the
    readable units above them; each hangs from its nearest readable ancestor, hidden ones between being skipped, and
    is a root when it has none. A hidden recorded unit holds nothing below it. Each node comes with how many recorded
    units it holds, itself included, how many records those have, and whether any of them is below it.
    """
    return f"""
        CALL () {{
          WITH 1 AS _
          WHERE $parent_ids IS NULL
          UNWIND $dataset_ids AS dataset_id
          MATCH (:Dataset {{id: dataset_id}})-[:INCLUDES_RECORD]->(record:Record)-[:FOR_UNIT]->(unit:Unit)
          WHERE {IN_WINDOW}
          WITH DISTINCT unit
          MATCH (top:Unit)-[:{EDGE}*0..]->(unit)
          WITH DISTINCT top
          WHERE ({_readable('top')} OR {_has_records('top')})
            AND NOT EXISTS {{ MATCH (ancestor:Unit)-[:{EDGE}]->+(top) WHERE {_readable('ancestor')} }}
          RETURN top AS child
          UNION
          WITH 1 AS _
          WHERE $parent_ids IS NOT NULL
          UNWIND $parent_ids AS parent_id
          MATCH (parent:Unit {{id: parent_id}})
          WHERE {_readable('parent')}
          MATCH (parent) (()-[:{EDGE}]->(hidden:Unit WHERE NOT {_readable('hidden')})){{0,}} ()-[:{EDGE}]->(child:Unit)
          WITH DISTINCT child
          WHERE {_readable('child')} OR {_has_records('child')}
          RETURN child
        }}
        WITH DISTINCT child, {_readable('child')} AS child_readable
        CALL (child, child_readable) {{
          MATCH (child)-[:{EDGE}*0..]->(unit:Unit)<-[:FOR_UNIT]-(record:Record)<-[:INCLUDES_RECORD]-(dataset:Dataset)
          WHERE (child_readable OR unit = child) AND dataset.id IN $dataset_ids AND {IN_WINDOW}
          RETURN
            count(DISTINCT unit) AS unit_count,
            count(DISTINCT record) AS record_count,
            max(CASE WHEN unit = child THEN 0 ELSE 1 END) AS below
        }}
        WITH child, child_readable, unit_count, record_count, below WHERE unit_count > 0
        RETURN child.id AS id, unit_count, record_count, below = 1 AS has_children
        ORDER BY CASE WHEN child_readable THEN child.name END, child.id
    """


def read_units_by_subject():
    """
    The units the readable datasets $dataset_ids have records for in the time window, narrowed to those $unit_ids
    select (see _selected_units), grouped by subject as id and name: for selecting all the recorded units of a subject
    at once. Hidden units are one group without a subject, as placeholders
    """
    return f"""
        CALL () {{
          WITH 1 AS _
          WHERE $unit_ids IS NULL
          UNWIND $dataset_ids AS dataset_id
          MATCH (:Dataset {{id: dataset_id}})-[:INCLUDES_RECORD]->(record:Record)-[:FOR_UNIT]->(unit:Unit)
          WHERE {IN_WINDOW}
          RETURN DISTINCT unit
          UNION
          WITH 1 AS _
          WHERE $unit_ids IS NOT NULL
          {_selected_units()}
          UNWIND selected_units AS selected_id
          MATCH (unit:Unit {{id: selected_id}})
          WHERE {_has_records('unit')}
          RETURN DISTINCT unit
        }}
        WITH unit, {_readable('unit')} AS unit_readable
        OPTIONAL MATCH (unit)-[:OF_SUBJECT]->(subject:Subject) WHERE unit_readable
        WITH subject.id AS subject, unit, unit_readable
        ORDER BY unit.name, unit.id
        RETURN subject, collect(CASE WHEN unit_readable THEN {{id: unit.id, name: unit.name}} ELSE {{id: unit.id, name: 'REDACTED'}} END) AS units
    """

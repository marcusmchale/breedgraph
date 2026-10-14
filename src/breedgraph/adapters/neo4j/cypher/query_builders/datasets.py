from typing import AbstractSet

# The summary fields read from the datasets' units rather than from their records alone
UNIT_FIELDS = frozenset({'unit_count', 'subject_ids', 'block_ids', 'location_ids'})
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
                -[:FOR_CONCEPT]->(concept: Variable | Factor),
              (dataset)<-[:CONTROLS]-(control: Control)
                <-[:CONTROLS]-(:TeamDatasets)
                <-[:CONTROLS]-(team: Team)

        WITH concept, dataset, team, control
        ORDER BY dataset.id, team.id, control.sequence DESC

        WITH concept, dataset, team, collect(control)[0] as control
        WHERE NOT coalesce(control.ended, false)
        WITH concept, dataset, collect(team.id) as team_ids, collect(control.release) as releases

        WITH concept, dataset, team_ids, min(releases) as effective_release
        WHERE any(team_id in team_ids WHERE team_id in $read_teams)
        OR effective_release >= $minimum_release

        WITH concept, dataset
        {''.join(parts)}
        RETURN {{ {', '.join(returns)} }} AS dataset_summary
        ORDER BY dataset.id
    """


def dataset_unit_summaries(fields: AbstractSet[str] = SUMMARY_FIELDS):
    """
    What the units of the datasets with ids $dataset_ids add to their summaries, for the given fields, one row per
    dataset with records. Datasets of a study share most of their units, so each unit's subjects and block are read
    once, then credited to every dataset it has records in. A unit's locations are those of its positions that
    overlap the time span of its records in the dataset, or all of them when either is untimed. The time range of
    each dataset comes from the same pass.
    """
    _check_fields(fields)
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
    if 'subject_ids' in fields:
        query.append("""
        CALL (unit) {
          OPTIONAL MATCH (unit)-[:OF_SUBJECT]->(subject:Subject)
          RETURN collect(DISTINCT subject.id) AS subject_ids
        }
        """)
    if 'block_ids' in fields:
        query.append("""
        CALL (unit) {
          OPTIONAL MATCH (root:Unit)-[:INCLUDES_UNIT*]->(unit) WHERE NOT (:Unit)-[:INCLUDES_UNIT]->(root)
          RETURN collect(DISTINCT coalesce(root, unit).id) AS block_ids
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
    for name, values in [('subject_ids', 'subject_ids'), ('block_ids', 'block_ids'), ('location_ids', 'use.location_ids')]:
        if name in fields:
            aggregates.append(f'collect({values}) AS {name}_lists')
            returns.append(f'{name}: apoc.coll.toSet(apoc.coll.flatten({name}_lists))')
    query.append(f"WITH {', '.join(aggregates)}")
    query.append(f"RETURN {{ {', '.join(returns)} }} AS unit_summary")
    return '\n'.join(query)

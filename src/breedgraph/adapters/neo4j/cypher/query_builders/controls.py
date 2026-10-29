from breedgraph.domain.model.controls import ControlledModelLabel
from breedgraph.adapters.neo4j.cypher.query_builders.access import (
    visible as _visible, readable as _readable, least_release as _least_release
)

def set_controls(label: ControlledModelLabel):
    return f"""
        MATCH (entity:{label.label})
        WHERE entity.id IN $entity_ids

        OPTIONAL MATCH (existing_team:Team)-[:CONTROLS]->(existing_tp:Team{label.plural})
            -[:CONTROLS]->(existing_control:Control)-[:CONTROLS]->(entity)

        WITH entity, existing_team, existing_control
        ORDER BY entity.id, existing_team.id, existing_control.sequence DESC

        WITH entity, existing_team, collect(existing_control)[0] AS latest_control

        WITH entity,
             collect(
                CASE WHEN NOT coalesce(latest_control.ended, false) THEN existing_team.id END
             ) AS existing_control_team_ids

        WITH entity,
             CASE
                 WHEN size(existing_control_team_ids) = 0
                 THEN $team_ids
                 ELSE [team_id IN $team_ids
                       WHERE team_id IN existing_control_team_ids]
             END AS control_team_ids

        UNWIND control_team_ids AS team_id

        MATCH (control_team:Team)
        WHERE control_team.id = team_id

        MERGE (control_team)-[:CONTROLS]->(tp:Team{label.plural})
        ON CREATE SET tp.sequence = 0
        ON MATCH SET tp.sequence = tp.sequence + 1

        CREATE (tp)-[:CONTROLS]->(control:Control {{
            user: $user_id,
            release: $release,
            time: datetime.transaction(),
            sequence: tp.sequence
        }})-[:CONTROLS]->(entity)
    """


def add_controls(label: ControlledModelLabel):
    return f"""
        MATCH (entity:{label.label})
        WHERE entity.id IN $entity_ids

        UNWIND $team_ids AS team_id

        MATCH (control_team:Team {{id: team_id}})

        MERGE (control_team)-[:CONTROLS]->(tp:Team{label.plural})
        ON CREATE SET tp.sequence = 0
        ON MATCH SET tp.sequence = tp.sequence + 1

        CREATE (tp)-[:CONTROLS]->(control:Control {{
            user: $user_id,
            release: $release,
            time: datetime.transaction(),
            sequence: tp.sequence
        }})-[:CONTROLS]->(entity)
    """

def end_controls(label: ControlledModelLabel):
    """
    Ending a control appends a Control marked as ended, so control history is kept.
    A team controls an entity while its latest Control for that entity is not ended.
    """
    return f"""
        MATCH (entity:{label.label})
        WHERE entity.id IN $entity_ids

        UNWIND $team_ids AS team_id

        MATCH (control_team:Team {{id: team_id}})-[:CONTROLS]->(tp:Team{label.plural})
            -[:CONTROLS]->(control:Control)-[:CONTROLS]->(entity)

        WITH entity, tp, control
        ORDER BY entity.id, control.sequence DESC

        WITH entity, tp, collect(control)[0] AS latest_control
        WHERE NOT coalesce(latest_control.ended, false)

        SET tp.sequence = tp.sequence + 1

        CREATE (tp)-[:CONTROLS]->(ended_control:Control {{
            user: $user_id,
            release: latest_control.release,
            time: datetime.transaction(),
            sequence: tp.sequence,
            ended: true
        }})-[:CONTROLS]->(entity)
    """

def record_writes(label:ControlledModelLabel):
    return f"""
        MATCH (user:User {{id: $user_id}})
        MERGE (user)-[:CONTRIBUTED]->(uc:User{label.plural})
        WITH user, uc
        MATCH (entity: {label.label}) WHERE entity.id in $entity_ids
        MERGE (uc)-[contributed:CONTRIBUTED {{time: datetime.transaction()}}]->(entity)
    """

def get_controllers(label:ControlledModelLabel):
    """
    The controllers of the entities with ids $entity_ids, each with its current controls: none for an entity without
    any, which is fixed (Controller.fixed), or new in this transaction and not yet given its first controls
    """
    return f"""
        MATCH (entity: {label.label} ) WHERE entity.id in $entity_ids
        CALL (entity) {{
            OPTIONAL MATCH (entity)<-[:CONTROLS]-(control:Control)<-[:CONTROLS]-(:Team{label.plural})<-[:CONTROLS]-(team:Team)
            WITH team, control
            ORDER BY team.id, control.sequence DESC
            WITH team, collect(control)[0] AS control
            WHERE team IS NOT NULL AND NOT coalesce(control.ended, false)
            RETURN collect({{team: team.id, release: control.release, time: control.time, user: control.user}}) AS controls
        }}
        RETURN
            entity.id as entity_id,
            controls,
            [(entity)<-[write:CONTRIBUTED]-(:User{label.plural})<-[:CONTRIBUTED]-(user:User|DeletedUser) |
            {{user:user.id, time: write.time}}] as writes
   """


def licence_release_violations() -> str:
    """
    The studies among $study_ids, those of the datasets $dataset_ids, and those licensed by, or whose datasets or their
    records cite, the references $reference_ids, whose licence is released less widely than the study, one of its
    datasets, or a file reference those datasets or their records cite (docs/read-access.md, rule 10). Each comes with
    its licence, the licence's release, the widest release among the study and its datasets, and the widest among the
    files they cite (null for none) with, when the licence is released less widely than that, one such file. Releases
    are as visible() compares them. A study without a licence is never one of them, nor is the ontology.
    """
    return f"""
        CALL () {{
          MATCH (study:Study) WHERE study.id IN $study_ids
          RETURN study
          UNION
          MATCH (dataset:Dataset)-[:FOR_STUDY]->(study:Study) WHERE dataset.id IN $dataset_ids
          RETURN study
          UNION
          MATCH (study:Study)-[:USES_LICENCE]->(licence:Reference) WHERE licence.id IN $reference_ids
          RETURN study
          UNION
          MATCH (cited:Reference)-[:REFERENCE_FOR]->(:Dataset)-[:FOR_STUDY]->(study:Study) WHERE cited.id IN $reference_ids
          RETURN study
          UNION
          MATCH (cited:Reference)-[:REFERENCE_FOR]->(:Record)<-[:INCLUDES_RECORD]-(:Dataset)-[:FOR_STUDY]->(study:Study)
          WHERE cited.id IN $reference_ids
          RETURN study
        }}
        MATCH (study)-[:USES_LICENCE]->(licence:Reference)
        {_least_release('licence', ControlledModelLabel.REFERENCE, 'licence_release')}
        {_least_release('study', ControlledModelLabel.STUDY, 'study_release')}
        CALL (study) {{
          MATCH (dataset:Dataset)-[:FOR_STUDY]->(study)
          {_least_release('dataset', ControlledModelLabel.DATASET, 'dataset_release')}
          RETURN max(dataset_release) AS datasets_release
        }}
        // the files its data cites, found from the file references, which are few, rather than from its records
        CALL (study) {{
          MATCH (file:Reference) WHERE file.file_id IS NOT NULL AND (
            EXISTS {{ MATCH (file)-[:REFERENCE_FOR]->(:Dataset)-[:FOR_STUDY]->(study) }}
            OR EXISTS {{ MATCH (file)-[:REFERENCE_FOR]->(:Record)<-[:INCLUDES_RECORD]-(:Dataset)-[:FOR_STUDY]->(study) }}
          )
          {_least_release('file', ControlledModelLabel.REFERENCE, 'file_release')}
          WITH file, file_release
          ORDER BY file_release DESC, file.id
          RETURN collect(file_release)[0] AS cited_release, collect(file.id)[0] AS widest_cited
        }}
        WITH study, licence, licence_release, cited_release, widest_cited,
          CASE WHEN datasets_release > study_release THEN datasets_release ELSE study_release END AS data_release
        WHERE licence_release < data_release OR licence_release < cited_release
        RETURN study.id AS study_id, licence.id AS licence_id, licence_release, data_release, cited_release,
          CASE WHEN licence_release < cited_release THEN widest_cited END AS cited_reference_id
        ORDER BY licence_id, study_id
    """


def read_controllers(label: ControlledModelLabel):
    """
    The controllers of the entities with ids $entity_ids as the user may see them (see docs/read-access.md): the
    current controls of each, and the writes to it only when the user can read the entity. For an entity they cannot
    read, the controller is a placeholder with its controls alone, without when they were set, so they see whom to
    ask for access, but not the history of data hidden from them. An entity without current controls has none.
    """
    return f"""
        MATCH (entity: {label.label}) WHERE entity.id IN $entity_ids
        {_visible('entity', label, 'entity_readable')}
        CALL (entity, entity_readable) {{
            OPTIONAL MATCH (entity)<-[:CONTROLS]-(control:Control)<-[:CONTROLS]-(:Team{label.plural})<-[:CONTROLS]-(team:Team)
            WITH team, control
            ORDER BY team.id, control.sequence DESC
            WITH team, collect(control)[0] AS control
            WHERE team IS NOT NULL AND NOT coalesce(control.ended, false)
            RETURN collect({{
                team: team.id,
                release: control.release,
                time: CASE WHEN entity_readable THEN control.time END,
                user: CASE WHEN entity_readable THEN control.user END
            }}) AS controls
        }}
        RETURN
            entity.id AS entity_id,
            controls,
            CASE WHEN entity_readable THEN [
                (entity)<-[write:CONTRIBUTED]-(:User{label.plural})<-[:CONTRIBUTED]-(user:User|DeletedUser) |
                {{user: user.id, time: write.time}}
            ] ELSE [] END AS writes
    """


# What a team controls, for its admins acting on many entities at once. A team controls an entity while its latest
# Control of it (the highest sequence under the team's Team<Plural> node) is not ended; that control's release is the
# entity's release as the team set it. Names follow the read check: an entity the user cannot read is named REDACTED.

UNIT = ControlledModelLabel.UNIT
UNIT_EDGE = 'INCLUDES_UNIT'


def _current_controls(label: ControlledModelLabel) -> str:
    """Rows of each entity of label that team (in scope) currently controls, with the team's latest control of it"""
    return f"""
        MATCH (team)-[:CONTROLS]->(:Team{label.plural})-[:CONTROLS]->(any_control:Control)-[:CONTROLS]->(entity:{label.label})
        WITH team, entity, any_control ORDER BY any_control.sequence DESC
        WITH team, entity, collect(any_control)[0] AS control
        WHERE NOT coalesce(control.ended, false)
    """


def _other_teams(entity: str, label: ControlledModelLabel, team_id: str) -> str:
    """A call collecting the ids of the teams other than team_id that currently control entity, as other_team_ids"""
    return f"""
        CALL ({entity}) {{
          OPTIONAL MATCH ({entity})<-[:CONTROLS]-(other_control:Control)<-[:CONTROLS]-(:Team{label.plural})<-[:CONTROLS]-(other:Team)
          WHERE other.id <> {team_id}
          WITH other, other_control ORDER BY other.id, other_control.sequence DESC
          WITH other, collect(other_control)[0] AS other_control
          WHERE other IS NOT NULL AND NOT coalesce(other_control.ended, false)
          RETURN collect(other.id) AS other_team_ids
        }}
    """


def read_controlled_counts() -> str:
    """For each team $team_ids and label, how many entities the team currently controls, by release"""
    return '\nUNION ALL\n'.join(f"""
        MATCH (team:Team) WHERE team.id IN $team_ids
        {_current_controls(label)}
        RETURN team.id AS team_id, '{label.name}' AS label, control.release AS release, count(entity) AS count
    """ for label in ControlledModelLabel)


def _name(label: ControlledModelLabel, entity: str = 'entity') -> str:
    if label == ControlledModelLabel.DATASET:
        return f"[({entity})-[:FOR_CONCEPT]->(concept) | concept.name][0]"
    if label == ControlledModelLabel.REFERENCE:
        return f"coalesce({entity}.filename, {entity}.description, {entity}.url)"
    return f"{entity}.name"


# What holds an entity of each label, named for context: the pattern, with the holder as holder, and its label
_HOLDERS = {
    ControlledModelLabel.DATASET: ("(entity)-[:FOR_STUDY]->(holder:Study)", ControlledModelLabel.STUDY),
    ControlledModelLabel.STUDY: ("(holder:Trial)-[:HAS_STUDY]->(entity)", ControlledModelLabel.TRIAL),
    ControlledModelLabel.TRIAL: ("(holder:Program)-[:HAS_TRIAL]->(entity)", ControlledModelLabel.PROGRAM),
    ControlledModelLabel.LOCATION: ("(holder:Location)-[:INCLUDES_LOCATION]->(entity)", ControlledModelLabel.LOCATION),
    ControlledModelLabel.LAYOUT: ("(entity)-[:AT_LOCATION]->(holder:Location)", ControlledModelLabel.LOCATION),
}


def _context(label: ControlledModelLabel) -> str:
    """The name of what holds entity, REDACTED when the user cannot read it, or null"""
    if label not in _HOLDERS:
        return "null"
    pattern, holder_label = _HOLDERS[label]
    return f"""head(COLLECT {{
            MATCH {pattern}
            RETURN CASE WHEN {_readable('holder', holder_label)} THEN holder.name ELSE 'REDACTED' END
          }})"""


def read_controlled_entities(label: ControlledModelLabel) -> str:
    """
    The entities of label that team $team_id currently controls, at release $release when given, ordered by id, as
    a page from $offset of $limit, with how many there are in all: each with its name, the team's release, the other
    teams controlling it and what holds it. No row when the team controls none.
    """
    return f"""
        MATCH (team:Team {{id: $team_id}})
        {_current_controls(label)}
        WITH team, entity, control WHERE $release IS NULL OR control.release = $release
        WITH team, entity, control ORDER BY entity.id
        WITH team, collect({{entity: entity, release: control.release}}) AS controlled
        CALL (team, controlled) {{
          UNWIND controlled[$offset..$offset + $limit] AS item
          WITH team, item.entity AS entity, item.release AS release
          {_other_teams('entity', label, '$team_id')}
          WITH entity, release, other_team_ids ORDER BY entity.id
          RETURN collect({{
            id: entity.id,
            name: CASE WHEN {_readable('entity', label)} THEN {_name(label)} ELSE 'REDACTED' END,
            release: release,
            other_team_ids: other_team_ids,
            context: {_context(label)}
          }}) AS items
        }}
        RETURN size(controlled) AS total, items
    """


def read_entity_names(label: ControlledModelLabel) -> str:
    """The entities of label with ids $ids, each named as read_controlled_entities names it: REDACTED for one the user cannot read"""
    return f"""
        MATCH (entity:{label.label}) WHERE entity.id IN $ids
        RETURN entity.id AS id, CASE WHEN {_readable('entity', label)} THEN {_name(label)} ELSE 'REDACTED' END AS name
    """


def _team_controls(unit: str) -> str:
    """Whether team $team_id currently controls unit, with EXISTS subqueries only, for quantified path patterns"""
    return f"""EXISTS {{
          MATCH ({unit})<-[:CONTROLS]-(team_control:Control)<-[:CONTROLS]-(team_units:TeamUnits)<-[:CONTROLS]-(:Team {{id: $team_id}})
          WHERE NOT coalesce(team_control.ended, false)
            AND NOT EXISTS {{ MATCH ({unit})<-[:CONTROLS]-(newer:Control)<-[:CONTROLS]-(team_units) WHERE newer.sequence > team_control.sequence }}
        }}"""


def _shown(unit: str) -> str:
    """A unit in the tree of what a team controls: one the user can read, or that the team controls"""
    return f"({_readable(unit, UNIT)} OR {_team_controls(unit)})"


def _unit_summary(unit: str) -> str:
    """unit as id, name, subject and germplasm, for naming it in the tree; REDACTED when the user cannot read it"""
    return f"""CASE WHEN {_readable(unit, UNIT)} THEN {{
            id: {unit}.id,
            name: {unit}.name,
            subject: [({unit})-[:OF_SUBJECT]->(subject:Subject) | subject.id][0],
            germplasm: [({unit})-[:OF_GERMPLASM]->(germplasm:Germplasm) | germplasm.id][0]
          }} ELSE {{ id: {unit}.id, name: 'REDACTED' }} END"""


def _unit_controls(unit: str) -> str:
    """A call setting release, the team's release of unit (null where it doesn't control it), and other_team_ids"""
    return f"""
        CALL ({unit}) {{
          OPTIONAL MATCH ({unit})<-[:CONTROLS]-(any_control:Control)<-[:CONTROLS]-(:TeamUnits)<-[:CONTROLS]-(controller:Team)
          WITH controller, any_control ORDER BY controller.id, any_control.sequence DESC
          WITH controller, collect(any_control)[0] AS latest
          WHERE controller IS NOT NULL AND NOT coalesce(latest.ended, false)
          WITH collect({{team: controller.id, release: latest.release}}) AS controls
          RETURN
            [control IN controls WHERE control.team = $team_id | control.release][0] AS release,
            [control IN controls WHERE control.team <> $team_id | control.team] AS other_team_ids
        }}
    """


def read_controlled_unit_roots() -> str:
    """
    The roots of the unit graphs holding units team $team_id controls, each with how many of them are in its graph.
    A root is kept even when hidden, as a placeholder holding them (docs/read-access.md, rule 4).
    """
    return f"""
        MATCH (team:Team {{id: $team_id}})
        {_current_controls(UNIT)}
        MATCH (root:Unit)-[:{UNIT_EDGE}*0..]->(entity) WHERE NOT (:Unit)-[:{UNIT_EDGE}]->(root)
        WITH root, count(DISTINCT entity) AS count
        {_unit_controls('root')}
        RETURN {_unit_summary('root')} AS unit, null AS parent_id, count, release, other_team_ids
        ORDER BY root.id
    """


def read_controlled_unit_children() -> str:
    """
    For each unit $parent_ids that the tree shows (one the user can read, that team $team_id controls, or a root), the
    nearest units below it that the tree shows, through others, that are or hold units the team controls, each with
    how many of those it holds, itself included
    """
    return f"""
        UNWIND $parent_ids AS parent_id
        MATCH (parent:Unit {{id: parent_id}})
        WHERE {_shown('parent')} OR NOT (:Unit)-[:{UNIT_EDGE}]->(parent)
        CALL (parent) {{
          MATCH (parent) (()-[:{UNIT_EDGE}]->(between:Unit WHERE NOT {_shown('between')})){{0,}} ()-[:{UNIT_EDGE}]->(child:Unit)
          WHERE {_shown('child')}
          RETURN DISTINCT child
        }}
        CALL (child) {{
          MATCH (child)-[:{UNIT_EDGE}*0..]->(below:Unit)
          WHERE {_team_controls('below')}
          RETURN count(DISTINCT below) AS count
        }}
        WITH parent, child, count WHERE count > 0
        {_unit_controls('child')}
        RETURN {_unit_summary('child')} AS unit, parent.id AS parent_id, count, release, other_team_ids
        ORDER BY parent.id, child.id
    """


def scope_entity_ids(label: ControlledModelLabel, below_units: bool = False) -> str:
    """
    The ids of the entities of label that team $team_id currently controls, at release $release when given; with
    below_units, only the units $below_unit_ids and those below them. For acting on everything in a scope at once.
    """
    if below_units:
        match = f"""
        MATCH (top:Unit) WHERE top.id IN $below_unit_ids
        MATCH (top)-[:{UNIT_EDGE}*0..]->(entity:Unit)
        WITH DISTINCT entity
        MATCH (team:Team {{id: $team_id}})-[:CONTROLS]->(:TeamUnits)-[:CONTROLS]->(any_control:Control)-[:CONTROLS]->(entity)
        WITH team, entity, any_control ORDER BY any_control.sequence DESC
        WITH team, entity, collect(any_control)[0] AS control
        WHERE NOT coalesce(control.ended, false)
        """
    else:
        match = f"""
        MATCH (team:Team {{id: $team_id}})
        {_current_controls(label)}
        """
    return f"""
        {match}
        WITH entity, control WHERE $release IS NULL OR control.release = $release
        RETURN collect(entity.id) AS entity_ids
    """

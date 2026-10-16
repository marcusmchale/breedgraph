from breedgraph.domain.model.controls import ControlledModelLabel
from breedgraph.adapters.neo4j.cypher.query_builders.access import visible as _visible

# Programs, trials and studies as the user may see them. A node the user can read is returned in full. A node the
# user cannot read is returned only as a placeholder, its id and a REDACTED name: when it was asked for directly, or
# when it holds members the user can read, which then stay reachable below it. Otherwise it is left out.


def _study(study: str = 'study') -> str:
    return f"""{study} {{
          .*,
          reference_ids: [(reference:Reference)-[:REFERENCE_FOR]->({study})|reference.id],
          design_id: [({study})-[:USES_DESIGN]->(design:Design)|design.id][0],
          licence_id: [({study})-[:USES_LICENCE]->(licence:Reference)|licence.id][0],
          groupings: [({study})-[:USES_GROUPING]->(grouping: RecordGrouping)-[:OF_TYPE]->(type:RecordGroupType) | {{
              id: grouping.id,
              type: type.id,
              name: grouping.name,
              scope: grouping.scope,
              extent: grouping.extent,
              scopes: [
                (grouping)-[:HAS_SCOPE]->(scope:GroupingScope) | {{
                  dataset_ids: [(scope)<-[:IN_SCOPE]-(dataset:Dataset) | dataset.id]
                }}
              ]
          }}]
        }}"""


def _placeholder(entity: str, **fields: str) -> str:
    """entity as its id and a REDACTED name, with the given fields as Cypher expressions"""
    extra = ''.join(f", {field}: {value}" for field, value in fields.items())
    return f"{entity} {{ .id, name: 'REDACTED'{extra} }}"


def _studies(trial: str = 'trial') -> str:
    """A call collecting the studies of trial the user can read, as studies"""
    return f"""
        CALL ({trial}) {{
          OPTIONAL MATCH ({trial})-[:HAS_STUDY]->(study: Study)
          {_visible('study', ControlledModelLabel.STUDY, 'study_visible')}
          WITH study WHERE study_visible
          RETURN collect({_study()}) AS studies
        }}
    """


def _trial(trial: str = 'trial', visible: str = 'trial_visible') -> str:
    return f"""CASE WHEN {visible} THEN {trial} {{
          .*,
          contact_ids: [({trial})-[:HAS_CONTACT]->(contact:Person)|contact.id],
          reference_ids: [(reference:Reference)-[:REFERENCE_FOR]->({trial})|reference.id],
          studies: studies
        }} ELSE {_placeholder(trial, contact_ids='[]', reference_ids='[]', studies='studies')} END"""


def _trials(program: str = 'program') -> str:
    """A call collecting the trials of program the user can read, or that hold studies they can read, as trials"""
    return f"""
        CALL ({program}) {{
          OPTIONAL MATCH ({program})-[:HAS_TRIAL]->(trial: Trial)
          {_visible('trial', ControlledModelLabel.TRIAL, 'trial_visible')}
          {_studies('trial')}
          WITH trial, trial_visible, studies WHERE trial IS NOT NULL AND (trial_visible OR size(studies) > 0)
          RETURN collect({_trial()}) AS trials
        }}
    """


def _program(program: str = 'program', visible: str = 'program_visible') -> str:
    return f"""CASE WHEN {visible} THEN {program} {{
          .*,
          contact_ids: [({program})-[:HAS_CONTACT]->(contact:Person)|contact.id],
          reference_ids: [(reference:Reference)-[:REFERENCE_FOR]->({program})|reference.id],
          trials: trials
        }} ELSE {_placeholder(program, contact_ids='[]', reference_ids='[]', trials='trials')} END"""


def read_programs():
    """Every program the user can read, or that holds trials or studies they can read"""
    return f"""
        MATCH (program: Program)
        {_visible('program', ControlledModelLabel.PROGRAM, 'program_visible')}
        {_trials()}
        WITH program, program_visible, trials WHERE program_visible OR size(trials) > 0
        RETURN {_program()} AS program
        ORDER BY program.id
    """


def read_program(by: str = 'program'):
    """A program asked for by its id ($program_id), or by a trial's ($trial_id) or a study's ($study_id)"""
    match = {
        'program': "MATCH (program: Program {id: $program_id})",
        'trial': "MATCH (: Trial {id: $trial_id})<-[:HAS_TRIAL]-(program: Program)",
        'study': "MATCH (: Study {id: $study_id})<-[:HAS_STUDY]-(:Trial)<-[:HAS_TRIAL]-(program: Program)",
    }[by]
    return f"""
        {match}
        {_visible('program', ControlledModelLabel.PROGRAM, 'program_visible')}
        {_trials()}
        RETURN {_program()} AS program
    """


def read_trial(by: str = 'trial'):
    """A trial asked for by its id ($trial_id) or a study's ($study_id)"""
    match = {
        'trial': "MATCH (trial: Trial {id: $trial_id})",
        'study': "MATCH (: Study {id: $study_id})<-[:HAS_STUDY]-(trial: Trial)",
    }[by]
    return f"""
        {match}
        {_visible('trial', ControlledModelLabel.TRIAL, 'trial_visible')}
        {_studies('trial')}
        RETURN {_trial()} AS trial
    """


def read_study():
    """A study asked for by its id ($study_id)"""
    return f"""
        MATCH (study: Study {{id: $study_id}})
        {_visible('study', ControlledModelLabel.STUDY, 'study_visible')}
        RETURN CASE WHEN study_visible THEN {_study()} ELSE {_placeholder('study', reference_ids='[]', groupings='[]')} END AS study
    """

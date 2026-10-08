from breedgraph.domain.model.controls import ControlledModelLabel

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
    return f"""
        MATCH (entity: {label.label} ) WHERE entity.id in $entity_ids
        WITH entity
        
        MATCH (entity)<-[:CONTROLS]-(control:Control)
            <-[:CONTROLS]-(:Team{label.plural})
            <-[:CONTROLS]-(team:Team)
        
        WITH entity, team, control
        ORDER BY entity.id, team.id, control.sequence DESC
        
        WITH entity, team, collect(control)[0] as control
        WHERE NOT coalesce(control.ended, false)
        
        RETURN
            entity.id as entity_id,
            collect({{team: team.id, release: control.release, time: control.time, user: control.user}}) as controls,
            [(entity)<-[write:CONTRIBUTED]-(:User{label.plural})<-[:CONTRIBUTED]-(user:User) |
            {{user:user.id, time: write.time}}] as writes
   """

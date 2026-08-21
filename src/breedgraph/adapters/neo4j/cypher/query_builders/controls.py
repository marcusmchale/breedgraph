from breedgraph.domain.model.controls import ControlledModelLabel

def set_controls(label: ControlledModelLabel):
    return f"""
        MATCH (entity:{label.label})
        WHERE entity.id IN $entity_ids

        OPTIONAL MATCH (existing_team:Team)-[:CONTROLS]->(existing_tp:Team{label.plural})
            -[:CONTROLS]->(:Control)-[:CONTROLS]->(entity)

        WITH entity,
             collect(DISTINCT existing_team.id) AS existing_control_team_ids

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


def remove_controls(label:ControlledModelLabel):
    return f"""
        MATCH (: {label.label})
        <-[:CONTROLS]-(control:Control)<-[:CONTROLS]-(:Team{label.plural})
        <-[:CONTROLS]-(control_team:Team)
        WHERE control_team.id in $team_ids AND entity.id in $entity_ids
        DETACH DELETE control
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
        
        RETURN
            entity.id as entity_id,
            collect({{team: team.id, release: control.release, time: control.time, user: control.user}}) as controls,
            [(entity)<-[write:CONTRIBUTED]-(:User{label.plural})<-[:CONTRIBUTED]-(user:User) |
            {{user:user.id, time: write.time}}] as writes
   """

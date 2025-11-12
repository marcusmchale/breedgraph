from src.breedgraph.domain.model.controls import ControlledModel, ControlledModelLabel

def set_controls(label:ControlledModelLabel):
    return f"""
        MATCH (control_team:Team) WHERE control_team.id in $team_ids
        MERGE (control_team)-[:CONTROLS]->(tp:Team{label.plural})
        WITH tp
        MATCH (entity: {label.label}) WHERE entity.id in $entity_ids
        MERGE (tp)-[controls: CONTROLS]->(entity)
        ON CREATE SET 
            controls.users = [$user_id], 
            controls.releases = [$release], 
            controls.times = [datetime.transaction()]
        ON MATCH SET
            controls.users = controls.users + $user_id,
            controls.releases = controls.releases + $release,
            controls.times = controls.times + datetime.transaction() 
    """

def remove_controls(label:ControlledModelLabel):
    return f"""
        MATCH (: {label.label})
        <-[controls:CONTROLS]-(:Team{label.plural})
        <-[:CONTROLS]-(control_team:Team)
        WHERE control_team.id in $team_ids AND entity.id in $entity_ids
        DELETE controls
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
        RETURN
            entity.id as entity_id,
            [(entity)<-[controls:CONTROLS]-(:Team{label.plural})<-[:CONTROLS]-(team:Team) |
            {{team: team.id, releases: controls.releases, times: controls.times, users: controls.users}}] as controls,
            [(entity)<-[write:CONTRIBUTED]-(:User{label.plural})<-[:CONTRIBUTED]-(user:User) |
            {{user:user.id, time: write.time}}] as writes
   """

from src.breedgraph.domain.model.controls import ControlledModel

def record_write(label:str, plural:str, ):
    return f"""
        MATCH (entity: {label} {{id: $entity_id}})
        MATCH (user:User {{id: $user_id}})
        MERGE (user)-[:CONTRIBUTED]->(uc:User{plural})
        MERGE (uc)-[contributed:CONTRIBUTED {{time: datetime.transaction()}}]->(entity)
        return user.id as user, contributed.time as time
    """

def create_control(label:str, plural:str):
    return f"""
        MATCH (entity: {label} {{id: $entity_id}})
        MATCH (control_team:Team {{id: $team_id}})
        MERGE (control_team)-[:CONTROLS]->(tp:Team{plural})
        MERGE (tp)-[control:CONTROLS]->(entity)
        ON CREATE SET control.release = $release, control.time = datetime.transaction()
        RETURN control
    """

def get_controller(label:str, plural:str):
    return f"""
        MATCH (entity: {label} {{id: $entity_id}})
        RETURN
            [(entity)<-[controls:CONTROLS]-(:Team{plural})<-[:CONTROLS]-(team:Team) |
            {{team: team.id, release: controls.release, time: controls.time}}] as controls,
            [(entry)<-[write:CONTRIBUTED]-(:User{plural})<-[:CONTRIBUTED]-(user:User) |
            {{user:user.id, time: write.time}}] as writes
   """




def set_control(label:str, plural:str):
    if not (label, plural) in  [(i.label, i.plural) for i in ControlledModel.__subclasses__()]:
        raise ValueError("Only controlled entity labels can be used")

    query = f"""
        MATCH (entity: {label} {{id: $entity_id}})
        MATCH (team:Team {{id:$team_id}})
        MERGE (team)-[:CONTROLS]->(tp:Team{plural})
        MERGE (tp)-[controls:CONTROLS]->(entity)
        ON CREATE SET controls.time = datetime.transaction()
        SET controls.release = $release
    """
    return query


def remove_control(label:str, plural:str):
    if not (label, plural) in  [(i.label, i.plural) for i in ControlledModel.__subclasses__()]:
        raise ValueError("Only controlled entity labels can be used")

    query = f"""
        MATCH (: {label} {{id: $entity_id}})
        <-[controls:CONTROLS]-(:Team{plural})
        <-[:CONTROLS]-(:Team {{id:$team_id}})
        DELETE controls
    """
    return query
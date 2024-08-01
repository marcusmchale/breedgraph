from src.breedgraph.domain.model.controls import ControlledModel

def create_control(label:str, plural:str):
    if not (label, plural) in  [(i.label, i.plural) for i in ControlledModel.__subclasses__()]:
        raise ValueError("Only controlled entity labels can be used")

    query = f"""
        MATCH (entity: {label} {{id: $entity_id}})
        MATCH (control_team:Team {{id: $team_id}})
        MERGE (control_team)-[:CONTROLS]->(tp:Team{plural})
        MERGE (tp)-[controls:CONTROLS]->(entity)
        ON CREATE SET controls.release = $release, controls.time = datetime.transaction()
    """
    return query

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
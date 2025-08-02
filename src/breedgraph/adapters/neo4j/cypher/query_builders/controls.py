from src.breedgraph.domain.model.controls import ControlledModel
from typing import Dict

_plurals_cache: Dict[str, str] = {}

def get_plurals() -> Dict[str, str]:
    """Get plurals dictionary, ensuring all ControlledModel subclasses are loaded"""
    global _plurals_cache

    if not _plurals_cache:
        # Import all model modules to ensure subclasses are loaded
        try:
            from src.breedgraph.domain.model import (
                programs, arrangements, germplasm, people,
                references, regions, blocks, datasets
            )
        except ImportError:
            pass  # Some modules might not exist or have import issues

        # Now get all subclasses
        def get_all_subclasses(cls):
            all_subclasses = set()
            for subclass in cls.__subclasses__():
                all_subclasses.add(subclass)
                all_subclasses.update(get_all_subclasses(subclass))
            return all_subclasses

        all_controlled_models = get_all_subclasses(ControlledModel)
        _plurals_cache = {
            m.label: m.plural for m in all_controlled_models
            if hasattr(m, 'label') and hasattr(m, 'plural')
        }

    return _plurals_cache

def set_controls(label:str):
    plurals = get_plurals()
    return f"""
        MATCH (control_team:Team) WHERE control_team.id in $team_ids
        MERGE (control_team)-[:CONTROLS]->(tp:Team{plurals[label]})
        WITH tp
        MATCH (entity: {label}) WHERE entity.id in $entity_ids
        MERGE (tp)-[controls:CONTROLS]->(entity)
        SET controls.release = $release
        SET controls.time = datetime.transaction()
    """

def remove_controls(label:str):
    plurals = get_plurals()
    return f"""
        MATCH (: {label})
        <-[controls:CONTROLS]-(:Team{plurals[label]})
        <-[:CONTROLS]-(control_team:Team)
        WHERE control_team.id in $team_ids AND entity.id in $entity_ids
        DELETE controls
    """

def record_writes(label:str):
    plurals = get_plurals()
    return f"""
        MATCH (user:User {{id: $user_id}})
        MERGE (user)-[:CONTRIBUTED]->(uc:User{plurals[label]})
        WITH user, uc
        MATCH (entity: {label}) WHERE entity.id in $entity_ids
        MERGE (uc)-[contributed:CONTRIBUTED {{time: datetime.transaction()}}]->(entity)
    """

def get_controllers(label:str):
    plurals = get_plurals()
    return f"""
        MATCH (entity: {label} ) WHERE entity.id in $entity_ids
        RETURN
            entity.id as entity_id,
            [(entity)<-[controls:CONTROLS]-(:Team{plurals[label]})<-[:CONTROLS]-(team:Team) |
            {{team: team.id, release: controls.release, time: controls.time}}] as controls,
            [(entry)<-[write:CONTRIBUTED]-(:User{plurals[label]})<-[:CONTRIBUTED]-(user:User) |
            {{user:user.id, time: write.time}}] as writes
   """

from src.breedgraph.domain.model.base import EnumLabel

def delete_relationship(source_label:EnumLabel, sink_label:EnumLabel, relationship_label: str):
    """
    Deletes a relationship between two nodes in the graph.
    Provide source and sink ID as parameters
    """
    return f"""
        MATCH (:{source_label.label} {{id: $source_id}})
            -[rel:{relationship_label}]->
            (:{sink_label.label} {{id: $sink_id}})
        DELETE rel 
    """
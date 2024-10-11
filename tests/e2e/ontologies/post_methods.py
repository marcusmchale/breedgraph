from src.breedgraph.config import GQL_API_PATH
from src.breedgraph.domain.model.ontology import ObservationMethodType, ScaleType
from typing import List

async def post_to_add_entry(
        client,
        token: str,
        label: str,
        name: str,
        description: str|None = None,
        abbreviation: str|None = None,
        synonyms: List[str]|None = None,
        authors: List[int]|None = None,
        references: List[int]|None = None,
        parents: List[int]|None = None,
        subjects: List[int]|None = None,
        observation_type: ObservationMethodType|None = None,
        scale_type: ScaleType|None = None,
        trait: int|None=None,
        method: int|None=None,
        scale: int|None=None,
        axes: int|None=None
):
    json={
        "query": (
            " mutation ( $entry: OntologyEntryInput ) { "
            "  ontology_add_entry( "
            "   entry: $entry  "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "entry" : {
                "label": label,
                "name": name,
                "description": description,
                "abbreviation": abbreviation,
                "synonyms": synonyms,
                "authors": authors,
                "references": references,
                "parents": parents,
                "subjects": subjects,
                "observation_type": observation_type,
                "scale_type": scale_type,
                "trait": trait,
                "method": method,
                "scale": scale,
                "axes": axes
            }
        }
    }
    return await client.post(f"{GQL_API_PATH}/", json=json, headers={"token":token})

async def post_to_get_entries(
        client,
        token: str,
        name: str|None = None,
        label: str|None = None,
):
    json={
        "query": (
            " query ( "
            "  $name: String"
            "  $label: OntologyLabel"
            " ) { "
            "  ontology_entries( "
            "    name: $name "
            "    label: $label "
            "  ) { "
            "    status, "
            "    result { "
            "       id, "
            "       name,"
            "       label, "
            "       parents { id, name }, "
            "       children { id, name } "
            "       scale_type "
            "       observation_type "
            "       subjects { id, name } "
            "       categories { id, name } "
            "       trait { id, name } "
            "       condition { id, name } "
            "       exposure { id, name } "
            "       method { id, name, label } "
            "       scale { id, name, scale_type } "
            "       rank "
            "       axes "
            "       "
            "   }, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "name": name,
            "label": label
        }
    }
    return await client.post(f"{GQL_API_PATH}/", json=json, headers={"token":token})
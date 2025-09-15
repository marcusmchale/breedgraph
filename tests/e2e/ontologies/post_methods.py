from src.breedgraph.config import GQL_API_PATH
from src.breedgraph.domain.model.ontology import ObservationMethodType, ScaleType
from typing import List
from tests.e2e.utils import with_auth

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
        axes: List[str]|None=None
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
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response

async def post_to_get_entries(
        client,
        token: str,
        names: List[str] | None = None,
        labels: List[str] |None = None,
):
    json={
        "query": (
            " query ( "
            "  $names: [String]"
            "  $labels: [OntologyLabel]"
            " ) { "
            "  ontology_entries( "
            "    names: $names "
            "    labels: $labels "
            "  ) { "
            "    status, "
            "    result { "
            "       id, "
            "       name,"
            "       parents { id, name }, "
            "       children { id, name } "
            "       ... on RelatedToTerms { terms { id, name } }"
            "       ... on Subject { traits { id, name } , conditions { id, name } } "
            "       ... on Trait { subjects { id, name }, variables { id, name } } "
            "       ... on Condition { subjects { id, name } , parameters { id, name } } "
            "       ... on Scale { scaleType, categories  { id, name } , variables { id, name } , parameters { id, name } }"
            "       ... on Category { scales  { id, name } }"
            "       ... on ObservationMethod { observationMethodType, variables  { id, name } } " 
            "       ... on Variable { trait { id, name } , observationMethod { id, name }, scale  { id, name } } "
            "       ... on ControlMethod { controlMethodType, parameters { id, name } } "
            "       ... on Parameter { condition { id, name }, controlMethod { id, name }, scale { id, name } } "
            "       ... on Event { variables { id, name }, parameters { id, name } } "
            "       ... on LayoutType { axes } "
            "   }, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "names": names,
            "labels": labels
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response
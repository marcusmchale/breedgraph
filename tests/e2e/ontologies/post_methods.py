from src.breedgraph.config import GQL_API_PATH
from typing import List

async def post_to_add_term(
        client,
        token: str,
        name: str,
        description: str|None = None,
        abbreviation: str|None = None,
        synonyms: List[str]|None = None,
        authors: List[int]|None = None,
        references: List[int]|None = None,
        parents: List[int]|None = None
):
    json={
        "query": (
            " mutation ( $entry: OntologyEntryInput ) { "
            "  add_term( "
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
                "name": name,
                "description": description,
                "abbreviation": abbreviation,
                "synonyms": synonyms,
                "authors": authors,
                "references": references,
                "parents": parents
            }
        }
    }
    return await client.post(f"{GQL_API_PATH}/", json=json, headers={"token":token})


#async def post_to_add_term(
#        client,
#        token: str,
#        name: str,
#        description: str|None = None,
#        abbreviation: str|None = None,
#        synonyms: List[str]|None = None,
#        authors: List[int]|None = None,
#        references: List[int]|None = None,
#        parents: List[int]|None = None
#):
#    json={
#        "query": (
#            " mutation ( "
#            "  $name: String!"
#            "  $description: String,"
#            "  $abbreviation: String "
#            "  $synonyms: [String],"
#            "  $authors: [Int],"
#            "  $references: [Int],"
#            "  $parents: [Int]"
#            " ) { "
#            "  add_term( "
#            "    name: $name "
#            "    description: $description, "
#            "    abbreviation: $abbreviation "
#            "    synonyms: $synonyms, "
#            "    authors: $authors, "
#            "    references: $references "
#            "    parents: $parents "
#            "  ) { "
#            "    status, "
#            "    result, "
#            "    errors { name, message } "
#            "  } "
#            " } "
#        ),
#        "variables": {
#            "name": name,
#            "description": description,
#            "abbreviation": abbreviation,
#            "synonyms": synonyms,
#            "authors": authors,
#            "references": references,
#            "parents": parents
#        }
#    }
#    return await client.post(f"{GQL_API_PATH}/", json=json, headers={"token":token})
"""
The roles of CRediT (Contributor Roles Taxonomy, ANSI/NISO Z39.104-2022), seeded as locked Role entries (docs/contributions.md §3).

CRediT is published by NISO under CC BY 4.0. Each seeded Role keeps the definition unchanged,
and its source gives the role's URL and the attribution.
"""
import csv
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

CREDIT_ROLES_PATH = Path(__file__).parents[3] / 'data' / 'credit_roles.csv'

CREDIT_ATTRIBUTION = (
    "National Information Standards Organization (2022). ANSI/NISO Z39.104-2022, CRediT, Contributor Roles Taxonomy. "
    "NISO. https://credit.niso.org/. "
    "Definition licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/)."
)

@dataclass(frozen=True)
class CreditRole:
    name: str
    external_id: str  # the role's identifier in its URL, e.g. data-curation
    url: str
    definition: str

@lru_cache(maxsize=1)
def credit_roles() -> tuple[CreditRole, ...]:
    """The CRediT roles, in CRediT order"""
    with open(CREDIT_ROLES_PATH, encoding='utf-8', newline='') as roles_csv:
        return tuple(CreditRole(**row) for row in csv.DictReader(roles_csv))

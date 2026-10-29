"""
The standard licences every deployment starts with, created by scripts/setup_initial_data.py as the system user:
CC BY 4.0, under which the ontology is published, and CC0 1.0, for studies to choose too (docs/licences.md §6).

Each is a legal reference without controls, so it is fixed: everyone can read it and cite it, and no one can change it
(docs/read-access.md, rule 11). Its text is Creative Commons' legal code, packaged unchanged in breedgraph/legal/licences.
Each is keyed, so seeding again creates only what is missing.
"""
from dataclasses import dataclass
from importlib.resources import files

from breedgraph.domain.model.references import LegalReferenceInput, TextFormat, text_hash

import logging
logger = logging.getLogger(__name__)

# the seed keys of the standard licences
CC_BY = 'cc-by-4.0'
CC0 = 'cc0-1.0'


@dataclass(frozen=True)
class StandardLicence:
    seed_key: str
    description: str
    # in breedgraph/legal/licences
    filename: str

    @property
    def text(self) -> str:
        return (files('breedgraph') / 'legal' / 'licences' / self.filename).read_text(encoding='utf-8')

    def reference_input(self) -> LegalReferenceInput:
        text = self.text
        return LegalReferenceInput(
            description=self.description,
            text=text,
            text_format=TextFormat.PLAIN,
            content_hash=text_hash(text)
        )


STANDARD_LICENCES = (
    StandardLicence(CC_BY, 'Creative Commons Attribution 4.0 International (CC BY 4.0)', 'cc-by-4.0.txt'),
    StandardLicence(CC0, 'Creative Commons CC0 1.0 Universal (CC0 1.0), a public domain dedication', 'cc0-1.0.txt'),
)


async def seed_licences(references) -> dict[str, int]:
    """
    Create the standard licences that are missing, through the references repository, as the system user.
    Returns the id of each by its seed key.
    """
    ids = {}
    for licence in STANDARD_LICENCES:
        ids[licence.seed_key] = await references.get_seeded_id(licence.seed_key)
        if ids[licence.seed_key] is None:
            logger.info(f"Creating the standard licence {licence.description}")
            ids[licence.seed_key] = (await references.seed(licence.reference_input(), licence.seed_key)).id
    return ids

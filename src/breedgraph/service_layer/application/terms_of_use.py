"""
The published legal texts, read once at start-up with their hashes: the Terms of Use, which everyone accepts before using
BreedGraph (docs/licences.md §4), an acceptance naming its hash, so a change to the text asks everyone again; and the
privacy notice, whose hash an account records with the consent given when registering.
"""
import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LegalText:
    # markdown
    text: str
    # the SHA-256 of the published file
    content_hash: str


def load_legal_text(path: str) -> LegalText:
    data = Path(path).read_bytes()
    return LegalText(text=data.decode('utf-8'), content_hash=hashlib.sha256(data).hexdigest())

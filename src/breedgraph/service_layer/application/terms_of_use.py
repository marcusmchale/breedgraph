"""
The Terms of Use, which everyone accepts before using BreedGraph (docs/licences.md §4): the published text, read once
at start-up, and its hash, which an acceptance names, so a change to the text asks everyone again.
"""
import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TermsOfUse:
    # markdown
    text: str
    # the SHA-256 of the published file
    content_hash: str


def load_terms_of_use(path: str) -> TermsOfUse:
    data = Path(path).read_bytes()
    return TermsOfUse(text=data.decode('utf-8'), content_hash=hashlib.sha256(data).hexdigest())

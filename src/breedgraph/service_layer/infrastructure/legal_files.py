"""
Legal references given as files, such as licences: a .txt, .md or .pdf file, whose text is read when it is uploaded,
so it can be shown and agreed to without the file, which is kept for download. The file's SHA-256 is its content hash,
which an acceptance names (docs/licences.md).
"""
import hashlib
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from breedgraph.config import LEGAL_FILE_SIZE_LIMIT, LEGAL_FILE_PAGE_LIMIT
from breedgraph.domain.model.references import TextFormat

# by extension: the content type the file is stored and served with, whatever the client said, and how its text is written
LEGAL_FILE_FORMATS: dict[str, tuple[str, TextFormat]] = {
    '.txt': ('text/plain; charset=utf-8', TextFormat.PLAIN),
    '.md': ('text/markdown; charset=utf-8', TextFormat.MARKDOWN),
    '.pdf': ('application/pdf', TextFormat.PLAIN),
}


class LegalFileInvalid(ValueError):
    """What is wrong with a legal file, for the person uploading it"""


@dataclass(frozen=True)
class LegalText:
    text: str
    text_format: TextFormat
    content_type: str
    content_hash: str


def read_legal_file(filename: str, data: bytes) -> LegalText:
    """
    The text of a legal file, checked: one of the formats above by its extension and its content, within the size and
    page limits, with text to show. Anything wrong raises LegalFileInvalid.
    """
    extension = Path(filename or '').suffix.lower()
    if extension not in LEGAL_FILE_FORMATS:
        raise LegalFileInvalid("A legal reference's file must be a .txt, .md or .pdf file")
    if len(data) > LEGAL_FILE_SIZE_LIMIT:
        raise LegalFileInvalid(f"A legal reference's file can be at most {LEGAL_FILE_SIZE_LIMIT / 1e6:g} MB")
    content_type, text_format = LEGAL_FILE_FORMATS[extension]
    text = _pdf_text(filename, data) if extension == '.pdf' else _plain_text(filename, data)
    text = text.replace('\r\n', '\n').replace('\r', '\n').strip()
    if not text:
        raise LegalFileInvalid(f"{filename} has no text")
    return LegalText(
        text=text,
        text_format=text_format,
        content_type=content_type,
        content_hash=hashlib.sha256(data).hexdigest()
    )


def _plain_text(filename: str, data: bytes) -> str:
    if b'\x00' in data:
        raise LegalFileInvalid(f"{filename} is not a text file")
    try:
        # a byte order mark, which some editors write, is not part of the text
        return data.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise LegalFileInvalid(f"{filename} is not UTF-8 text: save it as UTF-8 and upload it again")


def _pdf_text(filename: str, data: bytes) -> str:
    """The text of each page, in order, a blank line between pages. Scans have none: their text must be given as text."""
    from pypdf import PdfReader

    if not data.startswith(b'%PDF-'):
        raise LegalFileInvalid(f"{filename} is not a PDF file")
    try:
        reader = PdfReader(BytesIO(data))
        # a PDF encrypted with an empty password is only protected from changes, and its text can be read
        locked = reader.is_encrypted and not reader.decrypt('')
        page_count = 0 if locked else len(reader.pages)
        pages = [] if locked or page_count > LEGAL_FILE_PAGE_LIMIT else [
            (page.extract_text() or '').strip() for page in reader.pages
        ]
    except Exception as e:
        raise LegalFileInvalid(f"{filename} could not be read as a PDF ({type(e).__name__})")
    if locked:
        raise LegalFileInvalid(f"{filename} is protected by a password, so its text can't be read")
    if page_count > LEGAL_FILE_PAGE_LIMIT:
        raise LegalFileInvalid(f"A legal reference's PDF can have at most {LEGAL_FILE_PAGE_LIMIT} pages")
    text = '\n\n'.join(page for page in pages if page)
    if not text:
        raise LegalFileInvalid(
            f"{filename} has no text to read, as a scanned document has none: give the text as a .txt or .md file"
        )
    return text

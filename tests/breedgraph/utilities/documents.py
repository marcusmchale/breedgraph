"""Small documents for tests of reading legal files, made here so the tests need no fixture files"""
from io import BytesIO


def _pdf_string(text: str) -> str:
    return text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')


def pdf_with_text(*pages: str) -> bytes:
    """
    A PDF with a page for each text given, its lines shown in Helvetica, so a PDF reader finds that text; an empty
    text makes a page with nothing on it, as a scan has no text. ASCII only.
    """
    pages = pages or ('',)
    page_count = len(pages)
    # 1 catalog, 2 page tree, 3 font, then a page and its contents for each page
    kids = ' '.join(f'{4 + 2 * i} 0 R' for i in range(page_count))
    objects = [
        b'<< /Type /Catalog /Pages 2 0 R >>',
        f'<< /Type /Pages /Kids [{kids}] /Count {page_count} >>'.encode(),
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
    ]
    for i, text in enumerate(pages):
        lines = ' T* '.join(f'({_pdf_string(line)}) Tj' for line in text.split('\n')) if text else ''
        stream = f'BT /F1 12 Tf 14 TL 72 720 Td {lines} ET'.encode() if lines else b''
        objects.append(
            f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {5 + 2 * i} 0 R '
            f'/Resources << /Font << /F1 3 0 R >> >> >>'.encode()
        )
        objects.append(f'<< /Length {len(stream)} >>\nstream\n'.encode() + stream + b'\nendstream')

    document = bytearray(b'%PDF-1.4\n')
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(document))
        document += f'{number} 0 obj\n'.encode() + body + b'\nendobj\n'
    xref = len(document)
    document += f'xref\n0 {len(objects) + 1}\n0000000000 65535 f \n'.encode()
    for offset in offsets:
        document += f'{offset:010d} 00000 n \n'.encode()
    document += f'trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()
    return bytes(document)


def encrypted_pdf(pdf: bytes, user_password: str) -> bytes:
    """pdf encrypted with RC4, which pypdf handles without a cryptography library; an empty user password opens it"""
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter(clone_from=PdfReader(BytesIO(pdf)))
    writer.encrypt(user_password=user_password, owner_password='owner', algorithm='RC4-128')
    output = BytesIO()
    writer.write(output)
    return output.getvalue()

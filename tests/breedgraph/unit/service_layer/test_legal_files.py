"""
Reading legal files (service_layer/infrastructure/legal_files.py). Fixture-free, so it can run without the database:
python -m pytest --noconftest -p no:cacheprovider tests/breedgraph/unit/service_layer/test_legal_files.py
"""
import hashlib

import pytest

from breedgraph.domain.model.references import TextFormat
from breedgraph.service_layer.infrastructure import legal_files
from breedgraph.service_layer.infrastructure.legal_files import LegalFileInvalid, read_legal_file

from tests.breedgraph.utilities.documents import pdf_with_text, encrypted_pdf


def test_markdown_is_read_as_markdown():
    data = '# Licence\r\n\r\nUse it **freely**, with credit.\r\n'.encode()
    legal = read_legal_file('Licence.MD', data)
    assert legal.text == '# Licence\n\nUse it **freely**, with credit.'
    assert legal.text_format == TextFormat.MARKDOWN
    assert legal.content_type == 'text/markdown; charset=utf-8'
    assert legal.content_hash == hashlib.sha256(data).hexdigest()


def test_text_is_read_as_written_without_a_byte_order_mark():
    data = '﻿Licence: use with credit, café included.\n'.encode('utf-8')
    legal = read_legal_file('licence.txt', data)
    assert legal.text == 'Licence: use with credit, café included.'
    assert legal.text_format == TextFormat.PLAIN
    assert legal.content_type == 'text/plain; charset=utf-8'


def test_a_pdf_is_read_page_by_page():
    data = pdf_with_text('Licence (version 1)\nUse with credit', 'Page two')
    legal = read_legal_file('licence.pdf', data)
    assert 'Licence (version 1)' in legal.text and 'Use with credit' in legal.text
    assert legal.text.index('Use with credit') < legal.text.index('Page two')
    assert '\n\nPage two' in legal.text
    assert legal.text_format == TextFormat.PLAIN
    assert legal.content_type == 'application/pdf'
    assert legal.content_hash == hashlib.sha256(data).hexdigest()


def test_a_pdf_encrypted_without_a_password_to_open_it_is_read():
    legal = read_legal_file('licence.pdf', encrypted_pdf(pdf_with_text('Use with credit'), user_password=''))
    assert 'Use with credit' in legal.text


@pytest.mark.parametrize('filename, data, message', [
    ('licence.docx', b'PK\x03\x04', r'\.txt, \.md or \.pdf'),
    ('licence', b'Use with credit', r'\.txt, \.md or \.pdf'),
    ('licence.pdf', b'Use with credit', 'is not a PDF file'),
    ('licence.txt', b'Use\x00with credit', 'is not a text file'),
    ('licence.md', 'Licence café'.encode('latin-1'), 'is not UTF-8 text'),
    ('licence.txt', b'  \r\n\t', 'has no text'),
    ('licence.pdf', pdf_with_text(''), 'no text to read'),
    ('licence.pdf', encrypted_pdf(pdf_with_text('Use with credit'), user_password='secret'), 'protected by a password'),
    ('licence.pdf', b'%PDF-1.4\nnot really a PDF', 'could not be read as a PDF'),
])
def test_wrong_files_are_refused_saying_why(filename, data, message):
    with pytest.raises(LegalFileInvalid, match=message):
        read_legal_file(filename, data)


def test_the_size_and_page_limits_are_kept(monkeypatch):
    monkeypatch.setattr(legal_files, 'LEGAL_FILE_SIZE_LIMIT', 10)
    with pytest.raises(LegalFileInvalid, match='at most'):
        read_legal_file('licence.txt', b'Use with credit')

    monkeypatch.setattr(legal_files, 'LEGAL_FILE_SIZE_LIMIT', 5_000_000)
    monkeypatch.setattr(legal_files, 'LEGAL_FILE_PAGE_LIMIT', 1)
    with pytest.raises(LegalFileInvalid, match='at most 1 pages'):
        read_legal_file('licence.pdf', pdf_with_text('One', 'Two'))

import pytest

from breedcafs_migration.datasets import replicate_code


@pytest.mark.parametrize('value, code', [
    (None, None), ('', None), ('0', None), (' 0 ', None),   # no code, or BreedCAFS's code for a reading not replicated
    ('1', '1'), (' 12', '12'), ('10', '10'),
])
def test_replicate_code(value, code):
    assert replicate_code(value) == code

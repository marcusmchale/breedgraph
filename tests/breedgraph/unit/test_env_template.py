"""
instance/breedgraph.env, which a deployment's environment is written from, names every variable the API reads, set or
commented out, so that none is missed when the site is set up (docs/deployment.md). Runs with --noconftest.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
READS = re.compile(r"""(?:environ\.get\(|environ\[|getenv\()\s*['"]([A-Z][A-Z0-9_]+)['"]""")


def read_by(package: str = 'breedgraph') -> set[str]:
    return {name for path in (ROOT / 'src' / package).rglob('*.py') for name in READS.findall(path.read_text())}


def named_in(template: str = 'breedgraph.env') -> set[str]:
    return set(re.findall(r'^#?([A-Z][A-Z0-9_]+)=', (ROOT / 'instance' / template).read_text(), re.MULTILINE))


def test_the_template_names_every_variable_the_api_reads():
    missing = read_by() - named_in()
    assert not missing, f'instance/breedgraph.env leaves out {sorted(missing)}'


def test_the_map_workers_template_names_every_variable_it_reads():
    missing = read_by('map_worker') - named_in('map_worker.env')
    assert not missing, f'instance/map_worker.env leaves out {sorted(missing)}'


def test_the_password_policy_reads_its_settings_as_numbers(monkeypatch):
    from breedgraph.config import get_password_policy
    for name, value in (('PASSWORD_MIN_LENGTH', '10'), ('PASSWORD_MIN_UPPERCASE', '1'),
                        ('PASSWORD_MIN_NUMBERS', '1'), ('PASSWORD_MIN_SPECIAL', '1')):
        monkeypatch.setenv(name, value)
    policy = get_password_policy()
    assert policy.test('Short-1') and not policy.test('Long-enough-1')

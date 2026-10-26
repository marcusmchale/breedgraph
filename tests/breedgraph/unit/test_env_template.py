"""
instance/breedgraph.env, which a deployment's environment is written from, names every variable the API reads, set or
commented out, so that none is missed when the site is set up (docs/deployment.md). Runs with --noconftest.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
READS = re.compile(r"""(?:environ\.get\(|environ\[|getenv\()\s*['"]([A-Z][A-Z0-9_]+)['"]""")


def read_by_the_api() -> set[str]:
    return {name for path in (ROOT / 'src' / 'breedgraph').rglob('*.py') for name in READS.findall(path.read_text())}


def named_in_the_template() -> set[str]:
    template = (ROOT / 'instance' / 'breedgraph.env').read_text()
    return set(re.findall(r'^#?([A-Z][A-Z0-9_]+)=', template, re.MULTILINE))


def test_the_template_names_every_variable_the_api_reads():
    missing = read_by_the_api() - named_in_the_template()
    assert not missing, f'instance/breedgraph.env leaves out {sorted(missing)}'

"""
scripts/reset_demo.sh runs scripts on the demonstration site, whose venv has the deployed extras only, without the test
dependencies: set_demo_accounts.py imports the demo story and the authorisation manager from tests.breedgraph.scenarios,
whose builders need faker, and failed there with "No module named 'faker'" until the package imported its builders
only when named.
"""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
# What scripts/reset_demo.sh runs with the site's venv
RESET_SCRIPTS = ['load_state_store.py', 'set_demo_accounts.py']


@pytest.mark.parametrize('name', RESET_SCRIPTS)
def test_reset_scripts_import_without_faker(name):
    # In a process of its own, with faker refused, the script's imports and module-level code run, but not its main
    code = (
        "import runpy, sys\n"
        "sys.modules['faker'] = None\n"
        f"runpy.run_path({str(ROOT / 'scripts' / name)!r}, run_name='imported')\n"
    )
    result = subprocess.run([sys.executable, '-c', code], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr[-2000:]


def test_scenario_builders_are_imported_when_named():
    from tests.breedgraph.scenarios import AccountBuilder, DatasetBuilder
    from tests.breedgraph.scenarios.account_builder import AccountBuilder as defined
    assert AccountBuilder is defined
    assert DatasetBuilder.__name__ == 'DatasetBuilder'
    with pytest.raises(ImportError):
        from tests.breedgraph.scenarios import NoSuchBuilder  # noqa: F401

"""
The application logs to its files (breedgraph.config.logging), so the scripts an operator runs on the server report
to the terminal too, through log_to_console: without it, setup_initial_data.py ran silently in a deployment, and said
how it went only in the log file.
"""
import ast
import logging
from pathlib import Path

import pytest

from breedgraph.config.logging import log_to_console

SCRIPTS = Path(__file__).parents[3] / 'scripts'
# Run on the server by an operator, or by a unit, saying what they did through logging
OPERATOR_SCRIPTS = [
    'setup_initial_data.py', 'apply_schema.py', 'apply_erasures.py', 'erase_person.py', 'load_state_store.py',
    'set_demo_accounts.py', 'map_tiles.py', 'seed_licences.py'
]


def test_log_to_console_reports_to_the_terminal(capsys):
    root = logging.getLogger()
    before = set(root.handlers)
    logger = logging.getLogger('scripts.example')
    logger.setLevel(logging.INFO)
    try:
        log_to_console()
        logger.info("Read models refreshed")
        logger.debug("Build neo4j driver")
    finally:
        for handler in set(root.handlers) - before:
            root.removeHandler(handler)
        logger.setLevel(logging.NOTSET)
    reported = capsys.readouterr().err
    assert "Read models refreshed" in reported
    assert "Build neo4j driver" not in reported


@pytest.mark.parametrize('name', OPERATOR_SCRIPTS)
def test_operator_scripts_report_to_the_terminal(name):
    tree = ast.parse((SCRIPTS / name).read_text())
    main_blocks = [node for node in tree.body if isinstance(node, ast.If) and '__main__' in ast.unparse(node.test)]
    assert main_blocks, f"{name} has no __main__ block"
    called = {ast.unparse(node.func) for block in main_blocks for node in ast.walk(block) if isinstance(node, ast.Call)}
    assert 'log_to_console' in called, f"{name} logs only to the application's log files"

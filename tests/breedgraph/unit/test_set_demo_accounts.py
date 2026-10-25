"""
The hosted demonstration site's accounts file, as scripts/set_demo_accounts.py checks it before touching the database:
a password for each story account the build keeps, and each reviewer complete, not named like a story account, with
affiliations to story teams only. Runs with --noconftest.
"""
import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / 'scripts' / 'set_demo_accounts.py'
spec = importlib.util.spec_from_file_location('set_demo_accounts', SCRIPT)
set_demo_accounts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(set_demo_accounts)

PASSWORDS = {key: f"{key}-password" for key in set_demo_accounts.ACCOUNTS}
REVIEWER = {
    'username': 'dpo-reviewer-1', 'fullname': 'DPO reviewer 1', 'email': 'dpo-reviewer-1@example.org',
    'password': 'reviewer-password', 'teams': {'institute': ['READ']}
}


def accounts_file(tmp_path, contents: dict) -> Path:
    path = tmp_path / 'demo_accounts.json'
    path.write_text(json.dumps(contents))
    return path


def test_the_build_deletes_no_account_the_file_must_name():
    # rita's account is deleted at the end of the build: no password is asked for it
    assert 'rita' not in set_demo_accounts.ACCOUNTS
    assert {'dara', 'bridget', 'theo', 'lena', 'petra'} <= set(set_demo_accounts.ACCOUNTS)


def test_a_complete_file_is_read(tmp_path):
    given = set_demo_accounts.read_accounts(accounts_file(tmp_path, {'accounts': PASSWORDS, 'reviewers': [REVIEWER]}))
    assert given['reviewers'][0]['username'] == 'dpo-reviewer-1'


@pytest.mark.parametrize('contents, refusal', [
    ({'accounts': {**PASSWORDS, 'dara': ''}}, 'no password for dara'),
    ({'accounts': PASSWORDS, 'reviewers': [{**REVIEWER, 'password': ''}]}, 'a reviewer has no password'),
    ({'accounts': PASSWORDS, 'reviewers': [{**REVIEWER, 'username': 'theo'}]}, "has a story account's name"),
    ({'accounts': PASSWORDS, 'reviewers': [{**REVIEWER, 'teams': {'nowhere': ['READ']}}]}, 'names no story team nowhere'),
])
def test_an_incomplete_file_is_refused(tmp_path, contents, refusal):
    with pytest.raises(SystemExit, match=refusal):
        set_demo_accounts.read_accounts(accounts_file(tmp_path, contents))


def test_a_reviewer_is_affiliated_by_the_owner_of_the_teams_tree():
    # the Institute's child teams are administered by the owner of its tree
    assert set_demo_accounts.team_owner('field') == set_demo_accounts.team_owner('institute')

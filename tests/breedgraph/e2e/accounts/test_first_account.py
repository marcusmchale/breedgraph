"""
scripts/create_first_account.py makes the site's first account on the server, as registering needs an invitation: it
is verified, signs in, is the first ontology admin, and records the account holder's consent to the privacy notice.
Once a verified account exists it refuses.
"""
import importlib.util
from pathlib import Path

import bcrypt
import pytest

from breedgraph import config
from breedgraph.domain.model.accounts import OntologyRole
from breedgraph.service_layer.application.terms_of_use import load_legal_text

from tests.breedgraph.e2e.accounts.post_methods import post_to_login
from tests.breedgraph.e2e.utils import get_verified_payload, assert_payload_success

SCRIPT = Path(__file__).resolve().parents[4] / 'scripts' / 'create_first_account.py'
spec = importlib.util.spec_from_file_location('create_first_account', SCRIPT)
script = importlib.util.module_from_spec(spec)
spec.loader.exec_module(script)

PASSWORD = 'First-Passw0rd!'


async def first_account(uow_factory, name='first.admin', email='first.admin@example.org') -> int:
    notice_hash = load_legal_text(config.PRIVACY_NOTICE_PATH).content_hash
    password_hash = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode()
    return await script.create_first_account(uow_factory, name, email, password_hash, notice_hash, 'First Admin')


@pytest.mark.asyncio(loop_scope="session")
async def test_the_first_account_is_a_verified_ontology_admin_who_signs_in(client, uow_factory, isolated_state):
    user_id = await first_account(uow_factory)
    async with uow_factory.get_uow() as uow:
        account = await uow.repositories.accounts.get(user_id=user_id)
    assert account.user.email_verified
    assert account.user.ontology_role == OntologyRole.ADMIN
    assert account.user.fullname == 'First Admin'
    assert account.user.privacy_consented_at is not None
    assert account.user.privacy_notice_hash == load_legal_text(config.PRIVACY_NOTICE_PATH).content_hash
    assert_payload_success(get_verified_payload(await post_to_login(client, 'first.admin', PASSWORD), "accountsLogin"))


@pytest.mark.asyncio(loop_scope="session")
async def test_it_refuses_once_a_verified_account_exists(uow_factory, isolated_state):
    with pytest.raises(script.Refused, match="has an account already"):
        await first_account(uow_factory, name='second.admin', email='second.admin@example.org')

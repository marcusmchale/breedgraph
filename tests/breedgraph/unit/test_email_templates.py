"""
The emails telling admins that something awaits them (service_layer/infrastructure/notifications/email_templates.py)
say what and where, not who asked or offered. Runs with --noconftest.
"""
from types import SimpleNamespace

from breedgraph.config import get_vue_url
from breedgraph.domain.model import Access
from breedgraph.service_layer.infrastructure.notifications.email_templates import (
    PersonClaimRequestedMessage, AffiliationRequestedMessage, ControlTransferOfferedMessage, names
)

TEAM = SimpleNamespace(name='Plant Lab')


def content(email) -> str:
    return email.message.get_content()


def test_names_are_listed_as_in_a_sentence():
    assert (names(['A']), names(['A', 'B']), names(['A', 'B', 'C'])) == ('A', 'A and B', 'A, B and C')


def test_a_request_to_link_a_person_record_names_its_teams_and_where_to_review_it():
    text = content(PersonClaimRequestedMessage(teams=['Plant Lab', 'Soil Lab']))
    assert 'Someone asked to link their account to a Person record controlled by Plant Lab and Soil Lab.' in text
    assert f'{get_vue_url()}people' in text


def test_an_affiliation_request_names_the_access_and_team():
    assert 'An account requested read access to Plant Lab and the teams below it.' in content(
        AffiliationRequestedMessage(team=TEAM, access=Access.READ, heritable=True)
    )
    assert 'An account with write access to Plant Lab requested it for the teams below it too.' in content(
        AffiliationRequestedMessage(team=TEAM, access=Access.WRITE, held=True)
    )


def test_a_control_transfer_offer_names_what_is_offered_and_to_which_team():
    assert 'Control of 1 entry was offered to Plant Lab.' in content(ControlTransferOfferedMessage(team=TEAM, entity_count=1))

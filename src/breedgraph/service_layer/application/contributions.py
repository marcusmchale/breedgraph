from typing import Iterable

from breedgraph.domain.model.contributions import Contribution
from breedgraph.domain.model.controls import ControlledModelLabel
from breedgraph.domain.model.ontology import OntologyEntryLabel


async def verify_contributions(uow, contributions: Iterable[Contribution], stored: Iterable[Contribution] = ()) -> None:
    """
    You can only credit a Person you can read, so only Persons added are checked: a dataset can still be edited
    while it credits Persons the editor cannot read. Each role added to a Person must be a Role entry of the current
    ontology; roles already credited are kept, even once removed.
    """
    contributions = list(contributions)
    stored = list(stored)
    stored_persons = {contribution.person for contribution in stored}
    await uow.controls.require_read(
        ControlledModelLabel.PERSON,
        [contribution.person for contribution in contributions if contribution.person not in stored_persons]
    )
    stored_roles = {(contribution.person, role_id) for contribution in stored for role_id in contribution.roles}
    role_ids = {
        role_id for contribution in contributions for role_id in contribution.roles
        if (contribution.person, role_id) not in stored_roles
    }
    if role_ids:
        await uow.ontology.require_entries(list(role_ids), label=OntologyEntryLabel.ROLE)

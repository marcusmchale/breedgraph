from typing import Dict, Type, List, Callable

from src.breedgraph.domain import events

from . import accounts

#EVENT_HANDLERS = {
#    events.accounts.EmailAdded: [accounts.email_user_allowed],
#    events.accounts.AccountCreated: [accounts.send_user_verify_url],
#    events.accounts.EmailVerified: [accounts.email_verified],
#    events.accounts.AffiliationRequested: [accounts.process_affiliation_request],
#    events.accounts.AffiliationApproved: [accounts.notify_user_approved],
#    events.accounts.PasswordChangeRequested: [accounts.password_change_requested],
#    events.accounts.EmailChangeRequested: [accounts.email_change_requested]
#}  # type: Dict[Type[events.base.Event], List[Callable]]

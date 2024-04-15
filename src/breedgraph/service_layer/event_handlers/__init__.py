from typing import Dict, Type, List, Callable

from src.breedgraph.domain import events

from . import accounts

EVENT_HANDLERS = {
    events.accounts.EmailAdded: [accounts.email_user_allowed],
    events.accounts.EmailRemoved: [],
    events.accounts.AccountAdded: [accounts.send_user_verify_url],
    events.accounts.EmailVerified: [accounts.email_verified],
    events.accounts.ReadRequested: [accounts.email_admins_read_request]
    #events.accounts.AdminGranted: [accounts.send_admin_notification]
}  # type: Dict[Type[events.base.Event], List[Callable]]

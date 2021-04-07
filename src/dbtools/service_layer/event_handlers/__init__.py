from typing import Dict, Type, List, Callable

from src.dbtools.domain import events

from . import accounts

EVENT_HANDLERS = {
    events.accounts.EmailAdded: [accounts.email_user_allowed],
    events.accounts.AccountAdded: [accounts.send_user_confirm_url],
    events.accounts.AffiliationConfirmed: [accounts.send_confirmed_notification],
    events.accounts.AdminGranted: [accounts.send_admin_notification]
}  # type: Dict[Type[events.base.Event], List[Callable]]

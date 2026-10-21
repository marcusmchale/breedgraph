"""
What the request's user has accepted, the Terms of Use and study licences (docs/licences.md §4): read from their
cookie once per request, and written back as the cookie when they accept more
"""
from breedgraph.service_layer.application.acceptance_tokens import Acceptances


def request_acceptances(context) -> Acceptances:
    if context.get('acceptances') is None:
        context['acceptances'] = context['acceptance_tokens'].read(context['request'].cookies, context.get('user_id'))
    return context['acceptances']


def save_acceptances(context, acceptances: Acceptances) -> None:
    """Queue the identity's cookie with these acceptances, in place of any queued before in this request"""
    cookie = context['acceptance_tokens'].cookie(acceptances)
    context['cookies_to_set'] = [c for c in context['cookies_to_set'] if c.get('key') != cookie['key']] + [cookie]
    if acceptances.user_id == context.get('user_id'):
        context['acceptances'] = acceptances


def terms_accepted(context) -> bool:
    return request_acceptances(context).accepts_terms(context['terms_of_use'].content_hash)

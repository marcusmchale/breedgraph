import os

from .routing import get_vue_url

# An ORCID Public API client, for users to link their verified ORCID iD to their Person record.
# Register the application at <ORCID_BASE_URL>/developer-tools, with ORCID_REDIRECT_URI as a redirect URI.
# Use https://sandbox.orcid.org for testing and https://orcid.org in production. Sign-in needs no client secret.
ORCID_CLIENT_ID = os.environ.get('ORCID_CLIENT_ID') or None
ORCID_BASE_URL = os.environ.get('ORCID_BASE_URL', 'https://sandbox.orcid.org')
# The keys ORCID signs id_tokens with, as published at <ORCID_BASE_URL>/oauth/jwks. Those of orcid.org and the sandbox
# are packaged (scripts/orcid_jwks.py), so set this only to take a key ORCID changed before a release carries it.
ORCID_JWKS_PATH = os.environ.get('ORCID_JWKS_PATH') or None
# A front-end page that completes the link with the id_token and state ORCID adds to its fragment
ORCID_REDIRECT_URI = os.environ.get('ORCID_REDIRECT_URI', f'{get_vue_url()}orcid')
ORCID_STATE_EXPIRES_SECONDS = int(os.environ.get('ORCID_STATE_EXPIRES_SECONDS', 600))

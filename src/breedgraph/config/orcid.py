import os

from .routing import PROTOCOL, HOST_ADDRESS

# ORCID Public API credentials, for users to link their verified ORCID iD to their Person record.
# Register the application at <ORCID_BASE_URL>/developer-tools, with ORCID_REDIRECT_URI as a redirect URI.
# Use https://sandbox.orcid.org for testing and https://orcid.org in production.
ORCID_CLIENT_ID = os.environ.get('ORCID_CLIENT_ID') or None
ORCID_CLIENT_SECRET = os.environ.get('ORCID_CLIENT_SECRET') or None
ORCID_BASE_URL = os.environ.get('ORCID_BASE_URL', 'https://sandbox.orcid.org')
# A front-end page that completes the link with the code and state ORCID adds to it
ORCID_REDIRECT_URI = os.environ.get('ORCID_REDIRECT_URI', f'{PROTOCOL}://{HOST_ADDRESS}/orcid')
ORCID_STATE_EXPIRES_SECONDS = int(os.environ.get('ORCID_STATE_EXPIRES_SECONDS', 600))

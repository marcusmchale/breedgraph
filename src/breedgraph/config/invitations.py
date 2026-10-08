import os

INVITATION_EXPIRY_DAYS = int(os.environ.get('INVITATION_EXPIRY_DAYS', 30))
INVITATION_SALT = os.environ.get('INVITATION_SALT', 'invitation_salt')

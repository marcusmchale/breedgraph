import os

# The emails a user's actions send each hour to addresses they give: invitations sent or resent, and the verification
# of a new email address. Counted in Redis per user, as messages to contacts are (MESSAGE_RATE_LIMIT_PER_HOUR).
EMAIL_RATE_LIMIT_PER_HOUR = int(os.environ.get('EMAIL_RATE_LIMIT_PER_HOUR', 20))
# The password resets asked for each hour for one address, which anyone can ask for: counted for the address given,
# registered or not, so that the limit says nothing of who is registered
PASSWORD_RESET_RATE_LIMIT_PER_HOUR = int(os.environ.get('PASSWORD_RESET_RATE_LIMIT_PER_HOUR', 3))

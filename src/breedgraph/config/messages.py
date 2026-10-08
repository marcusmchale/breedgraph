import os

# Messages to contacts, sent through BreedGraph without revealing the recipient's email address
MESSAGE_RATE_LIMIT_PER_HOUR = int(os.environ.get('MESSAGE_RATE_LIMIT_PER_HOUR', 10))
MESSAGE_MAX_LENGTH = int(os.environ.get('MESSAGE_MAX_LENGTH', 5000))
MESSAGE_SUBJECT_MAX_LENGTH = int(os.environ.get('MESSAGE_SUBJECT_MAX_LENGTH', 200))

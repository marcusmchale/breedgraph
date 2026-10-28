import os

FILE_STORAGE_PATH = os.environ.get('FILE_STORAGE_PATH')
FILE_DOWNLOAD_SALT = os.environ.get('FILE_DOWNLOAD_SALT', 'file_download_salt')
FILE_DOWNLOAD_EXPIRES = int(os.environ.get('FILE_DOWNLOAD_EXPIRES', 1440))  # minutes
# the most uploaded files saved at once: an upload asked for while they are all taken is refused, to try again later
MAX_CONCURRENT_UPLOADS = int(os.environ.get('MAX_CONCURRENT_UPLOADS', 5))

# Legal references given as files (.txt, .md or .pdf), whose text is read on upload: the largest file, in bytes, and the
# most pages of a PDF
LEGAL_FILE_SIZE_LIMIT = int(os.environ.get('LEGAL_FILE_SIZE_LIMIT', 5000000))
LEGAL_FILE_PAGE_LIMIT = int(os.environ.get('LEGAL_FILE_PAGE_LIMIT', 200))

# bytes for file size above which local copies of the file will be removed after local storage duration
LOCAL_SIZE_LIMIT = int(os.environ.get('LOCAL_SIZE_LIMIT', 10000000))
# days to temporarily keep a file larger than archival file size on the web server
LOCAL_STORAGE_DURATION = int(os.environ.get('LOCAL_STORAGE_DURATION', 28))

# how many times to attempt to archive a file before failing
ARCHIVE_ATTEMPT_LIMIT = int(os.environ.get('ARCHIVE_ATTEMPT_LIMIT', 5))
# how many times to attempt to retrieve an archived a file before failing
RETRIEVE_ATTEMPT_LIMIT = int(os.environ.get('RETRIEVE_ATTEMPT_LIMIT', 5))

# Auth token for the archive server
ARCHIVE_AUTH_TOKEN = os.environ.get('ARCHIVE_AUTH_TOKEN')

# Files are encrypted with age when sent to the archive server, as database backups are (docs/backups.md, Encryption key):
# to this public key ("age1..."), and decrypted with the key file when they come back, which may hold old keys too.
# Without a public key they are sent unencrypted, which only development allows.
ENCRYPTION_RECIPIENT = os.environ.get('ENCRYPTION_RECIPIENT') or None
ENCRYPTION_IDENTITY_PATH = os.environ.get('ENCRYPTION_IDENTITY_PATH') or None

# File retention policy
# For the file retention policy trigger (use a cron job to run scripts/trigger_retention.sh)
RETENTION_AUTH_TOKEN = os.environ.get('RETENTION_AUTH_TOKEN')
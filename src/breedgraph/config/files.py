import os

FILE_STORAGE_PATH = os.environ.get('FILE_STORAGE_PATH')
FILE_DOWNLOAD_SALT = os.environ.get('FILE_DOWNLOAD_SALT', 'file_download_salt')
FILE_DOWNLOAD_EXPIRES = int(os.environ.get('FILE_DOWNLOAD_EXPIRES', 1440))  # minutes
MAX_CONCURRENT_UPLOADS = int(os.environ.get('MAX_CONCURRENT_UPLOADS', 5))

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

# File retention policy
# For the file retention policy trigger (use a cron job to run trigger_file_retention.py)
RETENTION_AUTH_TOKEN = os.environ.get('RETENTION_AUTH_TOKEN')
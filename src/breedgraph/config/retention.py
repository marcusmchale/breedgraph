import os

SUBMISSION_RETENTION_DAYS = int(os.environ.get('SUBMISSION_RETENTION_DAYS', 7))
ANALYSIS_RETENTION_DAYS = int(os.environ.get('ANALYSIS_RETENTION_DAYS', 7))
# days a file reference must be found unused (nothing cites it) by the retention job, and not written, before the
# job removes it with its file
UNUSED_REFERENCE_RETENTION_DAYS = int(os.environ.get('UNUSED_REFERENCE_RETENTION_DAYS', 7))


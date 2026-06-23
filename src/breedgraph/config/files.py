import os

FILE_STORAGE_PATH = os.environ.get('FILE_STORAGE_PATH')
FILE_DOWNLOAD_SALT = os.environ.get('FILE_DOWNLOAD_SALT', 'file_download_salt')
FILE_DOWNLOAD_EXPIRES = int(os.environ.get('FILE_DOWNLOAD_EXPIRES', 1440))  # minutes
MAX_CONCURRENT_UPLOADS = int(os.environ.get('MAX_CONCURRENT_UPLOADS', 5))
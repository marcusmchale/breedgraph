from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from pathlib import Path
from itsdangerous import URLSafeTimedSerializer, SignatureExpired

from src.breedgraph.config import (
    FILE_STORAGE_PATH,
    SECRET_KEY,
    FILE_DOWNLOAD_SALT,
    FILE_DOWNLOAD_EXPIRES
)

import logging
logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/download")
async def download_file(token: str):
    ts = URLSafeTimedSerializer(SECRET_KEY)
    try:
        file_details = ts.loads(token, salt=FILE_DOWNLOAD_SALT, max_age=FILE_DOWNLOAD_EXPIRES * 60)
        uuid = file_details.get('uuid')
        if not uuid:
            raise HTTPException(status_code=401, detail="Invalid download token")
        file_path = Path(FILE_STORAGE_PATH, uuid)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        filename = file_details.get('filename')
        content_type = file_details.get('contentType')
        return FileResponse(
            file_path,
            media_type=content_type,
            filename=filename
        )

    except SignatureExpired as e:
        logger.debug(f"Attempt to use expired token, signed: {e.date_signed}")
        raise HTTPException(status_code=401, detail="Download token has expired")


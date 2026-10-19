"""
Encryption with age (https://age-encryption.org), through its command line, as the backup scripts use it.
Anything encrypted this way can be read by hand with `age --decrypt --identity <key file> <file>`.
"""
import asyncio
from pathlib import Path
from typing import AsyncIterator

import aiofiles

CHUNK_SIZE = 1024 * 1024  # 1 MiB


class AgeError(Exception):
    pass


async def encrypted_chunks(path: Path, recipient: str) -> AsyncIterator[bytes]:
    """Yield the file at path encrypted to the public key recipient, raising AgeError if age fails"""
    process = await asyncio.create_subprocess_exec(
        'age', '--encrypt', '--recipient', recipient, str(path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    try:
        while chunk := await process.stdout.read(CHUNK_SIZE):
            yield chunk
        error = await process.stderr.read()
        if await process.wait() != 0:
            raise AgeError(f"age could not encrypt {path.name}: {error.decode().strip()}")
    finally:
        # the reader stopped early, e.g. when a download was interrupted
        if process.returncode is None:
            process.kill()
            await process.wait()


async def decrypt_file(source: Path, destination: Path, identity_path: str | Path) -> None:
    """Decrypt source to destination with the keys in identity_path, raising AgeError if age fails"""
    process = await asyncio.create_subprocess_exec(
        'age', '--decrypt', '--identity', str(identity_path), '--output', str(destination), str(source),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE
    )
    _, error = await process.communicate()
    if process.returncode != 0:
        raise AgeError(f"age could not decrypt {source.name}: {error.decode().strip()}")


async def file_chunks(path: Path) -> AsyncIterator[bytes]:
    """Yield the file at path unencrypted, for development without a key"""
    async with aiofiles.open(path, 'rb') as f:
        while chunk := await f.read(CHUNK_SIZE):
            yield chunk

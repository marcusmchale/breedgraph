import json
import redis.asyncio as redis

from src.breedgraph.service_layer.infrastructure.state_store import AbstractStateStore
from src.breedgraph.service_layer.infrastructure.unit_of_work import AbstractUnitOfWork

from src.breedgraph.config import get_redis_host_and_port

from src.breedgraph.adapters.redis.load_data import RedisLoader

from src.breedgraph.domain.model.regions import LocationInput, LocationStored
from src.breedgraph.domain.model.errors import ItemError
from src.breedgraph.domain.model.submissions import SubmissionStatus, SubmissionKeys

import logging
logger = logging.getLogger(__name__)

from typing import AsyncGenerator, List, Self


class RedisStateStore(AbstractStateStore):
    def __init__(self, connection: redis.Redis):
        self.connection = connection

    @classmethod
    async def create(
            cls,
            uow: AbstractUnitOfWork,
            connection: redis.Redis|None = None,
            db: int = 0
    ) -> Self:
        if connection is None:
            logger.debug(f"Create new redis connection for db = {db}")
            host, port = get_redis_host_and_port()
            connection = await redis.Redis(host=host, port=port, db=db)
            logger.debug(f"Ping redis successful: {await connection.ping()}")
        if not await connection.exists("country"):
            loader = RedisLoader(connection, uow)
            await loader.load_read_model()

        return cls(connection)

    async def get_country(self, code: str) -> LocationInput|LocationStored|None:
        return await self.connection.hget('country', code)

    async def get_countries(self) -> AsyncGenerator[LocationInput|LocationStored, None]:
        countries_bytes = await self.connection.hgetall("country")
        for code, country in countries_bytes.items():
            country_json = json.loads(country)
            if country_json.get('id'):
                yield LocationStored(**country_json)
            else:
                yield LocationInput(**country_json)

    async def _set_agent(self, agent_id: int, key: str):
        await self.connection.hset(
            name=key,
            key=SubmissionKeys.AGENT.value,
            value=str(agent_id)
        )

    async def _verify_agent(self, agent_id, key: str):
        agent = await self.connection.hget(key, key="agent")
        agent = int(agent.decode('utf-8'))
        if not agent_id == agent:
            raise ValueError(f"Requesting user does not match stored agent for this key: {key}")

    async def _set_expiry(self, key: str, duration_seconds: int):
        await self.connection.expire(name=key, time=duration_seconds)

    async def _get_ttl(self, key):
        return await self.connection.ttl(key)

    async def _store_user_submission(self, agent_id: int, submission_id: str):
        await self.connection.sadd(
            f"user:{agent_id}:submissions",
            submission_id
        )

    async def _store_user_file(self, agent_id: int, file_id: str):
        await self.connection.sadd(
            f"user:{agent_id}:files",
            file_id
        )

    async def _set_submission_data(self, submission_id: str, submission: dict):
        await self.connection.hset(
            name=submission_id,
            key=SubmissionKeys.DATA.value,
            value=json.dumps(submission, default=str) # the default str makes datetime64 objects strings
        )

    async def _set_filename(self, file_id: str, filename: str):
        await self.connection.hset(
            name=file_id,
            key='filename',
            value=filename
        )

    async def set_file_progress(self, file_id: str, progress: int):
        await self.connection.hset(
            name=file_id,
            key='progress',
            value=str(progress)
        )

    async def set_file_status(self, file_id: str, status: SubmissionStatus):
        await self.connection.hset(
            name=file_id,
            key='status',
            value=status.value
        )

    async def set_submission_dataset_id(self, submission_id:str, dataset_id: int):
        await self.connection.hset(
            name=submission_id,
            key=SubmissionKeys.DATASET_ID.value,
            value=str(dataset_id)
        )

    async def _remove_submission_data(self, submission_id: str):
        await self.connection.hdel(submission_id, SubmissionKeys.DATA.value)

    async def _set_submission_status(self, submission_id: str, status: SubmissionStatus):
        await self.connection.hset(
            name=submission_id,
            key=SubmissionKeys.STATUS.value,
            value=status.value
        )


    async def _set_submission_errors(self, submission_id: str, errors: List[str]):
        await self.connection.hset(
            name=submission_id,
            key=SubmissionKeys.ERRORS.value,
            value=json.dumps(errors)
        )

    async def _set_submission_item_errors(self, submission_id: str, item_errors: List[ItemError]):
        serialized_item_errors = [e.model_dump() for e in item_errors]
        await self.connection.hset(
            name=submission_id,
            key=SubmissionKeys.ITEM_ERRORS.value,
            value=json.dumps(serialized_item_errors)
        )

    async def _get_user_submissions(self, agent_id: int) -> List[str]:
        user_submissions_key = f"user:{agent_id}:submissions"
        submission_ids = await self.connection.smembers(user_submissions_key)
        return list(submission_ids)

    async def _submission_exists(self, submission_id: str) -> bool:
        return await self.connection.exists(submission_id)

    async def _remove_user_submission(self, user_id, submission_id):
        user_submissions_key = f"user:{user_id}:submissions"
        await self.connection.srem(user_submissions_key, submission_id)

    async def _get_submission_data(self, submission_id: str):
        dataset_json = await self.connection.hget(submission_id, key=SubmissionKeys.DATA.value)
        return json.loads(dataset_json)

    async def _get_submission_dataset_id(self, submission_id):
        dataset_id = await self.connection.hget(submission_id, key=SubmissionKeys.DATASET_ID.value)
        if dataset_id is None:
            return None
        else:
            return int(dataset_id.decode('utf-8'))

    async def _get_submission_status(self, submission_id: str):
        status = await self.connection.hget(submission_id, key=SubmissionKeys.STATUS.value)
        return SubmissionStatus(status.decode('utf-8'))

    async def _get_submission_errors(self, submission_id):
        errors = await self.connection.hget(submission_id, key=SubmissionKeys.ERRORS.value)
        return json.loads(errors) if errors else []

    async def _get_submission_item_errors(self, submission_id):
        errors = await self.connection.hget(submission_id, key=SubmissionKeys.ITEM_ERRORS.value)
        item_errors = json.loads(errors) if errors else []
        return [ItemError(**e) for e in item_errors]

    async def _get_file_progress(self, file_id: str):
        progress = await self.connection.hget(file_id, key='progress')
        return int(progress.decode('utf-8')) if progress else 0

    async def _get_file_status(self, file_id: str):
        status = await self.connection.hget(
            name=file_id,
            key='status'
        )
        return SubmissionStatus(status.decode('utf-8'))

    async def set_file_reference_id(self, file_id: str, reference_id: int):
        await self.connection.hset(
            name=file_id,
            key=SubmissionKeys.FILE_ID.value,
            value=str(reference_id)
        )

    async def get_file_reference_id(self, file_id: str) -> int | None:
        reference_id = await self.connection.hget(
            name=file_id,
            key=SubmissionKeys.FILE_ID.value
        )
        return int(reference_id.decode('utf-8')) if reference_id else None

    """ Brute force protection state """

    async def _increment_failed_logins(self, attempts_key: str) -> int:
        attempts = await self.connection.incr(attempts_key)
        return attempts

    async def _set_locked_out(self, lockout_key: str, duration_seconds: int):
        await self.connection.setex(lockout_key, duration_seconds, 'locked')

    async def _clear_failed_logins(self, attempts_key: str):
        await self.connection.delete(attempts_key)


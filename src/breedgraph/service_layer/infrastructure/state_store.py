from abc import ABC, abstractmethod
from typing import Self, List, AsyncGenerator
from src.breedgraph.domain.model.submissions import SubmissionStatus, SubmissionKeys
from uuid import uuid4
from src.breedgraph.config import SUBMISSION_RETENTION_DAYS
from src.breedgraph.domain.model.regions import LocationInput, LocationStored
from src.breedgraph.domain.model.errors import ItemError


class AbstractStateStore(ABC):

    @classmethod
    @abstractmethod
    async def create(cls, *args, **kwargs) -> Self:
        ...

    """" Read model """
    # todo consider moving read model behaviour to another class
    # state store and read_model have been blurred here by the use of redis
    # consider using another redis db
    @abstractmethod
    async def get_country(self, code: str) -> LocationInput|LocationStored|None:
        ...

    @abstractmethod
    def get_countries(self) -> AsyncGenerator[LocationInput | LocationStored, None]:
        ...

    """ Agent Control (for dataset submission and file management) """
    @abstractmethod
    async def _set_agent(self, agent_id: int, key: str):
        ...

    @abstractmethod
    async def verify_agent(self, agent_id: int, key: str):
        ...

    """ Dataset Submission"""

    async def store_submission(self, agent_id: int, submission: dict) -> str:
        submission_id = uuid4().hex
        await self._set_agent(agent_id, submission_id)
        await self._store_user_submission(agent_id, submission_id)
        await self._set_agent(agent_id, submission_id)
        await self._set_submission_data(submission_id, submission)
        await self.set_submission_status(submission_id, SubmissionStatus.PENDING)
        return submission_id

    async def get_user_submissions(self, agent_id: int) -> List[str]:
        """ Return a list of submission ID """
        submission_ids = await self._get_user_submissions(agent_id)
        valid_submissions = []
        for submission_id in submission_ids:
            if await self._submission_exists(submission_id):
                valid_submissions.append(submission_id)
            else:
                # clean up expired submission
                await self._remove_user_submission(agent_id, submission_id)
        return valid_submissions

    async def get_submission_data(self, agent_id: int, submission_id: str):
        await self.verify_agent(agent_id, submission_id)
        return await self._get_submission_data(submission_id)

    async def get_submission_dataset_id(self, agent_id: int, submission_id: str) -> int | None:
        await self.verify_agent(agent_id, submission_id)
        return await self._get_submission_dataset_id(submission_id)

    async def add_submission_errors(self, submission_id, errors: List[str]):
        stored_errors = await self._get_submission_errors(submission_id)
        if stored_errors:
            errors = stored_errors + errors
        await self._set_submission_errors(submission_id, errors)

    async def get_submission_errors(self, agent_id: int, submission_id: str):
        await self.verify_agent(agent_id, submission_id)
        return await self._get_submission_errors(submission_id)

    async def add_submission_item_errors(self, submission_id: str, item_errors: List[ItemError]):
        stored_item_errors = await self._get_submission_item_errors(submission_id)
        if stored_item_errors:
            item_errors = stored_item_errors + item_errors
        await self._set_submission_item_errors(submission_id, item_errors)

    async def get_submission_item_errors(self, agent_id: int, submission_id: str):
        await self.verify_agent(agent_id, submission_id)
        return await self._get_submission_item_errors(submission_id)

    async def set_submission_status(self, submission_id: str, status: SubmissionStatus):
        await self._set_submission_status(submission_id, status)
        if status == SubmissionStatus.COMPLETED:
            # remove data if successful, no need to keep it in redis,
            # it can be accessed via the dataset_id from the db
            await self._remove_submission_data(submission_id)
            # reset expiry from when complete
            await self._set_expiry(submission_id, duration_seconds=60 * 60 * 24 * SUBMISSION_RETENTION_DAYS)

    async def get_submission_status(self, agent_id: int, submission_id: str) -> SubmissionStatus:
        await self.verify_agent(agent_id, submission_id)
        return await self._get_submission_status(submission_id)

    @abstractmethod
    async def _set_expiry(self, key: str, duration_seconds: int):
        ...

    @abstractmethod
    async def _get_ttl(self, key: str) -> int | None:
        """Return time to expiry in seconds"""
        ...

    @abstractmethod
    async def _store_user_submission(self, agent_id: int, submission_id: str):
        """ Store a submission ID for the given user """
        ...

    @abstractmethod
    async def _get_user_submissions(self, agent_id: int) -> List[str]:
        ...

    @abstractmethod
    async def _submission_exists(self, submission_id) -> bool:
        ...

    @abstractmethod
    async def _remove_user_submission(self, user_id, submission_id):
        ...

    @abstractmethod
    async def _set_submission_data(self, submission_id: str, submission: dict):
        """ Set submission data for the given submission ID """
        ...

    @abstractmethod
    async def _get_submission_data(self, submission_id: str) -> str:
        """ Get submission data for the given submission ID """
        ...

    @abstractmethod
    async def set_submission_dataset_id(self, submission_id, dataset_id: int):
        ...

    @abstractmethod
    async def _get_submission_dataset_id(self, submission_id: str) -> int | None:
        """ Get submission dataset ID for the given submission ID """
        ...

    @abstractmethod
    async def _set_submission_errors(self, submission_id: str, errors: List[str]):
        ...

    @abstractmethod
    async def _get_submission_errors(self, submission_id: str) -> List[str]:
        ...

    @abstractmethod
    async def _get_submission_item_errors(self, submission_id: str):
        ...

    @abstractmethod
    async def _set_submission_item_errors(self, submission_id: str, item_errors: List[ItemError]):
        ...

    @abstractmethod
    async def _remove_submission_data(self, submission_id: str):
        ...

    @abstractmethod
    async def _set_submission_status(self, submission_id: str, status: SubmissionStatus):
        ...

    @abstractmethod
    async def _get_submission_status(self, submission_id: str):
        ...

    """ File management state """
    async def store_file(self, agent_id: int, filename: str, reference_id: int | None = None) -> str:
        file_id = uuid4().hex
        await self._set_agent(agent_id, file_id)
        await self._store_user_file(agent_id, file_id)
        if reference_id is not None:
            await self.set_file_reference_id(file_id, reference_id)
        await self._set_filename(file_id, filename)
        await self.set_file_progress(file_id, 0)
        await self.set_file_status(file_id, SubmissionStatus.PENDING)
        return file_id

    async def get_file_status(self, agent_id: int, file_id: str) -> SubmissionStatus:
        await self.verify_agent(agent_id, file_id)
        return await self._get_file_status(file_id)

    async def get_file_progress(self, agent_id: int, file_id: str):
        await self.verify_agent(agent_id, file_id)
        return await self._get_file_progress(file_id)

    async def get_file_errors(self, agent_id: int, file_id: str):
        await self.verify_agent(agent_id, file_id)
        return await self._get_file_errors(file_id)

    async def get_user_file_ids(self, agent_id: int) -> List[str]:
        """ Return a list of submission ID """
        file_ids = await self._get_user_files(agent_id)
        valid_files = []
        for file_id in file_ids:
            if await self._file_exists(file_id):
                status = await self._get_file_status(file_id)
                if status == SubmissionStatus.COMPLETED:
                    valid_files.append(file_id)
            else:
                # clean up expired submissions
                await self._remove_user_file(agent_id, file_id)
        return valid_files

    async def get_user_file_reference_ids(self, user_id: int) -> List[str]:
        """ Return a list of reference ID """
        file_ids = await self.get_user_file_ids(user_id)
        reference_ids = []
        for file_id in file_ids:
            reference_id = await self.get_file_reference_id(file_id)
            reference_ids.append(reference_id)
        return reference_ids

    @abstractmethod
    async def _store_user_file(self, agent_id: int, file_id: str):
        ...

    @abstractmethod
    async def _set_filename(self, file_id: str, filename: str):
        ...

    @abstractmethod
    async def set_file_status(self, file_id: str, status: SubmissionStatus):
        ...

    @abstractmethod
    async def _get_file_status(self, file_id: str) -> SubmissionStatus:
        ...

    @abstractmethod
    async def set_file_progress(self, file_id: str, progress: int):
        ...

    @abstractmethod
    async def _get_file_progress(self, file_id: str):
        ...

    @abstractmethod
    async def set_file_errors(self, file_id: str, errors: List[str]):
        ...

    @abstractmethod
    async def _get_file_errors(self, file_id: str):
        ...

    @abstractmethod
    async def set_file_reference_id(self, file_id: str, reference_id: int):
        ...

    @abstractmethod
    async def get_file_reference_id(self, file_id: str) -> int | None:
        """ Get reference ID for the given file ID """
        ...

    @abstractmethod
    async def _get_user_files(self, agent_id) -> List[str]:
        ...

    @abstractmethod
    async def _file_exists(self, file_id) -> bool:
        ...

    @abstractmethod
    async def _remove_user_file(self, agent_id, file_id) -> None:
        ...

    """
    Brute force protection state
    
    Identifier can be either user_id or IP address
    """

    async def record_failed_login(self, identifier: str, duration_seconds: int) -> int:
        attempts_key = f"login_attempts:{identifier}"
        attempts = await self._increment_failed_logins(attempts_key)
        await self._set_expiry(attempts_key, duration_seconds)
        return attempts

    @abstractmethod
    async def _increment_failed_logins(self, identifier: str) -> int:
        ...

    @abstractmethod
    async def _clear_failed_logins(self, identifier: str):
        ...

    async def set_locked_out(self, identifier: str, duration_seconds: int):
        lockout_key = f"login_lockout:{identifier}"
        await self._set_locked_out(lockout_key, duration_seconds)

    @abstractmethod
    async def _set_locked_out(self, lockout_key: str, duration_seconds: int):
        ...

    async def record_successful_login(self, identifier: str):
        attempts_key = f"login_attempts:{identifier}"
        await self._clear_failed_logins(attempts_key)

    async def get_lockout_ttl(self, identifier: str) -> int | None:
        lockout_key = f"login_lockout:{identifier}"
        return await self._get_ttl(lockout_key)

from abc import ABC, abstractmethod

from analysis_worker.domain.model.job import AnalysisJob, Message


class AbstractAnalysisAPIClient(ABC):
    """Abstract base class for Analysis API client implementations"""

    @abstractmethod
    async def lease_job(self) -> AnalysisJob | None:
        """Lease the next queued job from the web server, None if no job is queued"""
        ...

    @abstractmethod
    async def post_result(self, job: AnalysisJob, result: dict, warnings: list[Message]) -> bool:
        """Report the result of a job. Returns False if the lease is no longer held."""
        ...

    @abstractmethod
    async def post_failure(self, job: AnalysisJob, errors: list[Message], warnings: list[Message]) -> bool:
        """Report the failure of a job. Returns False if the lease is no longer held."""
        ...

    @abstractmethod
    async def close(self):
        ...

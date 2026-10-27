"""The API's access log leaves out the workers' polls, made every few seconds (config/logging.py). Runs with --noconftest."""
import logging

import pytest

from breedgraph.config.logging import IgnoreAccessPaths


def access(path: str) -> logging.LogRecord:
    """A record as uvicorn's access logger makes it: client, method, path, HTTP version, status"""
    return logging.LogRecord(
        'uvicorn.access', logging.INFO, __file__, 0, '%s - "%s %s HTTP/%s" %d',
        ('127.0.0.1:5000', 'GET', path, '1.1', 204), None
    )


@pytest.mark.parametrize('path', [
    '/archive/archival_pending', '/archive/retrieval_pending', '/archive/deletion_pending',
    '/analysis_jobs/next', '/map_jobs/next/quick', '/map_jobs/next/extract'
])
def test_the_workers_polls_are_left_out(path):
    assert not IgnoreAccessPaths().filter(access(path))


@pytest.mark.parametrize('path', ['/graphql', '/analysis_jobs/abc/result', '/map_jobs/extract/IRL/file'])
def test_everything_else_is_logged(path):
    assert IgnoreAccessPaths().filter(access(path))

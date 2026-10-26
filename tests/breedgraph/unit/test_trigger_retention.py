"""
scripts/trigger_retention.py, run from cron on the web server: it posts to the API where it listens on that machine
(API_URL), with the retention token, using only what the API's own install has (httpx, not requests). Runs with
--noconftest.
"""
import importlib.util
from pathlib import Path

import httpx

from breedgraph import config

SCRIPT = Path(__file__).resolve().parents[3] / 'scripts' / 'trigger_retention.py'


def load(monkeypatch, api_url: str | None):
    if api_url is None:
        monkeypatch.delenv('API_URL', raising=False)
    else:
        monkeypatch.setenv('API_URL', api_url)
    spec = importlib.util.spec_from_file_location('trigger_retention', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_it_posts_to_the_api_on_this_machine_with_the_token(monkeypatch):
    calls = []

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return httpx.Response(200, json={'status': 'ok'}, request=httpx.Request('POST', url))

    monkeypatch.setattr(httpx, 'post', post)
    assert load(monkeypatch, None).main() == 0
    assert load(monkeypatch, 'http://127.0.0.1:8001/').main() == 0
    assert [url for url, _ in calls] == ['http://127.0.0.1:8000/retention/run', 'http://127.0.0.1:8001/retention/run']
    assert calls[0][1]['headers'] == {'Authorization': f'Bearer {config.RETENTION_AUTH_TOKEN}'}
    assert calls[0][1]['params'] == {'reason': 'scheduled'}


def test_a_refusal_fails_the_run(monkeypatch):
    def post(url, **kwargs):
        return httpx.Response(401, request=httpx.Request('POST', url))

    monkeypatch.setattr(httpx, 'post', post)
    assert load(monkeypatch, None).main() == 1

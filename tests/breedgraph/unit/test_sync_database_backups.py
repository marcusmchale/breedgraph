"""
scripts/sync_database_backups.sh, run from cron on the archive server: it copies the dumps and the erasure log from
the web server with rsync alone, so that the web server can restrict the key it accepts to reading with rsync from one
directory (rrsync -ro). Here ssh is a stand-in that runs rrsync on this machine, as that key's forced command would.
Runs with --noconftest.
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / 'scripts' / 'sync_database_backups.sh'
RRSYNC = shutil.which('rrsync')

pytestmark = pytest.mark.skipif(shutil.which('rsync') is None or RRSYNC is None, reason='needs rsync and rrsync')


@pytest.fixture
def servers(tmp_path):
    web = tmp_path / 'web'
    (web / 'neo4j_dumps').mkdir(parents=True)
    (web / 'erasure').mkdir()
    copy = tmp_path / 'copy'
    ssh = tmp_path / 'ssh'
    # ssh's own options and the host go, and the command the client asked for is handed to the forced command of the
    # key on the web server: rsync alone, reading only, within the web directory
    ssh.write_text(
        '#!/bin/sh\n'
        'while [ "$1" != rsync ]; do shift; done\n'
        f'SSH_ORIGINAL_COMMAND="$*" exec {RRSYNC} -ro {web}\n'
    )
    ssh.chmod(0o755)
    return web, copy, ssh


def sync(servers, dumps='/neo4j_dumps', log='/erasure/person_erasure_log.jsonl'):
    web, copy, ssh = servers
    env = {
        'PATH': os.environ['PATH'],
        'BACKUP_SYNC_ENV': str(copy.parent / 'no_settings_file'),
        'RSYNC_RSH': str(ssh),
        'BACKUP_SOURCE': 'breedgraph@web',
        'NEO4J_ARCHIVE_PATH': dumps,
        'PERSON_ERASURE_LOG_PATH': log,
        'BACKUP_DESTINATION_PATH': str(copy),
    }
    return subprocess.run(['bash', str(SCRIPT)], env=env, capture_output=True, text=True)


def test_it_copies_the_finished_dumps_and_the_log(servers):
    web, copy, _ = servers
    (web / 'neo4j_dumps' / 'neo4j-20261027-021500.dump.age').write_bytes(b'age-encryption.org/v1 one')
    (web / 'neo4j_dumps' / 'neo4j-20261028-021500.dump.age.partial').write_bytes(b'still being written')
    (web / 'erasure' / 'person_erasure_log.jsonl').write_text('{"person": 1}\n')

    result = sync(servers)

    assert result.returncode == 0, result.stderr
    assert sorted(path.name for path in copy.iterdir()) == ['neo4j-20261027-021500.dump.age', 'person_erasure_log.jsonl']
    assert (copy / 'person_erasure_log.jsonl').read_text() == '{"person": 1}\n'


def test_the_copy_of_the_log_only_grows(servers):
    web, copy, _ = servers
    log = web / 'erasure' / 'person_erasure_log.jsonl'
    log.write_text('{"person": 1}\n')
    assert sync(servers).returncode == 0

    log.write_text('{"person": 1}\n{"person": 2}\n')
    assert sync(servers).returncode == 0
    assert (copy / 'person_erasure_log.jsonl').read_text() == '{"person": 1}\n{"person": 2}\n'

    log.write_text('{"person": 1}\n')
    assert sync(servers).returncode == 0
    log.unlink()
    assert sync(servers).returncode == 0
    assert (copy / 'person_erasure_log.jsonl').read_text() == '{"person": 1}\n{"person": 2}\n'


def test_before_the_first_erasure_there_is_no_log_to_copy(servers):
    _, copy, _ = servers

    result = sync(servers)

    assert result.returncode == 0, result.stderr
    assert 'No erasure log on the web server yet' in result.stdout
    assert not (copy / 'person_erasure_log.jsonl').exists()


def test_the_key_reads_nothing_outside_its_directory(servers):
    result = sync(servers, dumps='/../outside')

    assert result.returncode != 0
    assert 'do not use ..' in result.stderr

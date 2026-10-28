# Encryption, backups, restores and retention

## Encryption key

Database backups and archived files are encrypted with [age](https://age-encryption.org) before they leave the web
server, so the archive server holds only copies it cannot read. The web server keeps the private key, as it decrypts
archived files when users ask for them back, and restores need it too. On the web server, install age and make the key
as the user that runs BreedGraph (here `breedgraph`):

    sudo apt install age
    sudo -u breedgraph age-keygen -o /opt/breedgraph/encryption_key.txt
    sudo -u breedgraph age-keygen -y /opt/breedgraph/encryption_key.txt

`age-keygen` makes the key file readable only by its owner. The last command prints the public key, `age1…`.
Set both in `breedgraph.env`, and restart the API:

    ENCRYPTION_RECIPIENT="age1…"
    ENCRYPTION_IDENTITY_PATH="/opt/breedgraph/encryption_key.txt"

Run `scripts/backup.sh` and `scripts/restore.sh` as that user too. The archive server needs neither age nor the key:
never copy the private key there. In development (`ENVIRONMENT=development`) both settings may be left empty, and
backups and archived files are then not encrypted. Elsewhere `backup.sh` refuses to run without a public key, and the
API refuses to send files to the archive server or take them back.

**Keep copies of the private key**, the `AGE-SECRET-KEY-1…` line in the key file, somewhere safe away from the web
server and the archive server, including a printed copy in a sealed envelope on campus. Without the key no backup or
archived file can be read, so losing the web server without a copy loses them all.

**Check each copy** once it is made, by decrypting a backup with it on a machine with age installed, then deleting the
copied key file:

    age --decrypt --identity copy_of_key.txt <database>-<date>.dump.age > /dev/null && echo "the key works"

**Changing the key.** Make a new key with `age-keygen -o new_key.txt`, add it to the end of the key file
(`cat new_key.txt >> encryption_key.txt`, then delete `new_key.txt`), set `ENCRYPTION_RECIPIENT` to its public key,
restart the API, and replace the copies. age tries every key in the key file, so backups and archived files made with
the old key can still be read. Keep an old key for as long as anything made with it exists: backups are kept for 90
days, but archived files can be kept indefinitely.

## Backups, restores and retention

Neo4j is dumped on the web server, encrypted, and the dumps and the erasure log are copied to an archive server.
The erasure log records erased Persons and deleted accounts outside the database, so a restore can apply them
again ([person.md](person.md) §5). Redis is not backed up: it holds read models, which are rebuilt from
Neo4j, and work in progress (dataset submissions, analysis jobs and their results for `ANALYSIS_RETENTION_DAYS`,
upload progress), which is lost if Redis is.

**Back up** on the web server with `scripts/backup.sh`. It stops Neo4j (the API is unavailable meanwhile),
dumps `DATABASE_NAME` to `NEO4J_ARCHIVE_PATH` as `<database>-<date>.dump.age`, encrypted to `ENCRYPTION_RECIPIENT`
as it is written, and starts Neo4j again. No unencrypted dump is written, and a dump is named `.partial` until complete.
In development without a key it writes an unencrypted `<database>-<date>.dump`, as before.
It uses `sudo` to stop Neo4j and dump as the neo4j user, and writes the encrypted dump as the user running it, who
needs write access to `NEO4J_ARCHIVE_PATH`. Allow that user those commands, and no more, in
`/etc/sudoers.d/breedgraph-backup` (mode 0440, checked first with `sudo visudo -cf <file>`), for `DATABASE_NAME` neo4j:

    breedgraph ALL=(root) NOPASSWD: /usr/sbin/service neo4j stop, /usr/sbin/service neo4j start
    breedgraph ALL=(neo4j) NOPASSWD: /usr/bin/neo4j-admin database dump neo4j --to-stdout

It reads its settings from the environment, which cron doesn't load. For example, nightly, in `/etc/cron.d/breedgraph`,
whose lines name the user they run as, logging to `LOG_BASE`:

    15 2 * * * breedgraph cd /path/to/breedgraph && set -a && . ./breedgraph.env && set +a && scripts/backup.sh >> /var/log/breedgraph/backup.log 2>&1

Only root can change `/etc/cron.d`, whereas the user's own crontab (`crontab -u breedgraph`, the same lines without the
user) is the API's account's to change, and is refused where `/etc/cron.allow` leaves the user out.

Dumps accumulate on the web server; remove old ones there as space requires, once the archive server has them.

**Copy** the dumps and the erasure log to the archive server with `scripts/sync_database_backups.sh`, run from cron
*on the archive server*, at least as often as dumps are made: an erasure is at risk until the log is copied.
Its settings are in `/etc/breedgraph/backup_sync.env` (example: `instance/backup_sync.env`), and it needs ssh key
access to the web server, but never the encryption key. New dumps are copied as they appear, and the log with
`rsync --append-verify`, as it is only ever appended to. `BACKUP_RETENTION_DAYS` removes old dumps there: set it to
90, the period the privacy notice states. The erasure log is never removed, and is not encrypted: it holds only
record and account numbers, and must stay appendable.

The script runs nothing on the web server but rsync, so the key there can be restricted to reading with rsync, from
the archive server's address, by a user of its own that can read the dumps and the erasure log and nothing else
beside them, such as the file store. In that user's `~/.ssh/authorized_keys` on the web server:

    restrict,from="<archive server's address>",command="/usr/bin/rrsync -ro /data/breedgraph" ssh-ed25519 AAAA... backup copy

`rrsync` comes with rsync, and the user needs a login shell to run it. The paths in `backup_sync.env` are then given
from that directory: `NEO4J_ARCHIVE_PATH="/neo4j_dumps"` and `PERSON_ERASURE_LOG_PATH="/erasure/person_erasure_log.jsonl"`.

    0 * * * * /path/to/breedgraph/scripts/sync_database_backups.sh >> /var/log/breedgraph_backup_sync.log 2>&1

**Restore** on the web server, with the environment loaded, by the dump's file name in `NEO4J_ARCHIVE_PATH`
(copy it back from the archive server first if needed). Stop the API first, so that nothing uses the database before
the erasure log is applied and the read models are rebuilt, and start it again at the end:

    sudo systemctl stop breedgraph
    cd /path/to/breedgraph
    set -a; . ./breedgraph.env; set +a
    scripts/restore.sh <database>-20261015-021500.dump.age

An encrypted dump needs the key file `ENCRYPTION_IDENTITY_PATH`, so run it as the key's owner, or, if the web server
was lost, with `ENCRYPTION_IDENTITY_PATH` set to a copy of the key. It decrypts the whole dump first, so a wrong key or
a damaged dump stops it before anything is changed. An unencrypted `.dump`, such as a test database, loads as it is.
It asks for confirmation, stops Neo4j, loads the dump over `DATABASE_NAME`, starts Neo4j, and replays the erasure log
(`scripts/apply_erasures.py`), so Persons erased and accounts deleted since the dump stay that way. Each entry is
applied to its own record only, and the id counters are advanced past the logged ids, so no erased id is given out
again. If the log isn't on the web server, restore it from the archive server and run `scripts/apply_erasures.py <log>`
before the database is used. Then rebuild the read models in Redis from the restored database, and start the API:

    scripts/load_state_store.py
    sudo systemctl start breedgraph

Uploaded files are not in the dump: they stay in `FILE_STORAGE_PATH`, or in archive storage (the archive worker).
The API encrypts files as it sends them to the archive worker and decrypts them when they come back, with the same
key, so the archive server holds only encrypted copies, while `FILE_STORAGE_PATH` holds files as uploaded. Once a file
is archived, the retention job removes the web server's copy after `LOCAL_STORAGE_DURATION` days, so the archive server
then holds its only copy. The API checks the archive server stored exactly what it sent before marking a file archived.

**Erasure on request.** The University is the data controller, so people without an account linked to their Person
record ask us to erase it. Confirm who is asking, then, with the environment loaded:

    scripts/erase_person.py <person id>

It erases the Person and appends it to the erasure log, as erasures in BreedGraph are, so a restore applies it again.

**Logs** are kept for the periods the privacy notice states: access logs 30 days, the others 90. The application writes
them to `LOG_BASE` without rotating, as several processes write them, so rotate them with logrotate, e.g. in
`/etc/logrotate.d/breedgraph`:

    /var/log/breedgraph/access.log {
        su breedgraph breedgraph
        daily
        rotate 30
        copytruncate
        compress
        delaycompress
        missingok
        notifempty
    }
    /var/log/breedgraph/breedgraph.log /var/log/breedgraph/graphql.log /var/log/breedgraph/neo4j.log /var/log/breedgraph/redis.log /var/log/breedgraph/backup.log /var/log/breedgraph/retention.log {
        su breedgraph breedgraph
        daily
        rotate 90
        copytruncate
        compress
        delaycompress
        missingok
        notifempty
    }

and keep nginx's access logs no longer than 30 days (`rotate` in `/etc/logrotate.d/nginx`).

**Retention** of files and expired invitations runs through the API, with `scripts/trigger_retention.sh` from cron
on the web server. It loads the environment file it is given, and calls the API where it listens on that machine
(`API_URL`), not through nginx. Each run notes the file references nothing cites (as a licence, a
copyright or a reference of anything), and removes those it has found unused, and that were not written, for
`UNUSED_REFERENCE_RETENTION_DAYS` (default 7), with their files, here and from the archive. A reference cited again
before then is kept. Then it removes the local copies of archived files, as above. Run it e.g. daily, from the
checkout of the release ([deployment.md](deployment.md)):

    30 3 * * * breedgraph BREEDGRAPH_PYTHON=/opt/breedgraph/.venv/bin/python /opt/breedgraph/checkout/scripts/trigger_retention.sh /opt/breedgraph/breedgraph.env >> /var/log/breedgraph/retention.log 2>&1

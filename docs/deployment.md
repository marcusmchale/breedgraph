# Deploying BreedGraph and BreedView

The steps in order, from building the release to checking the running site. The details of each are where they are
kept: [maps.md](maps.md), [backups.md](backups.md), the README (Setup), [BreedView's
README](https://github.com/marcusmchale/breedview) (Branding), `instance/` (the units and environment templates), and
`instance/demo/README.md` for the demonstration site. What each release needs besides the usual upgrade is in
[upgrading.md](upgrading.md), and how a release is made in [releasing.md](releasing.md).

## What runs where

**The web server**, which serves the site, at `<site>` below (e.g. `breedgraph.example.org`):
- nginx: the site, its certificate, BreedView's build in `/var/www/breedview` and its branding in
  `/etc/breedview/branding`; the API's public routes; the map tiles; and the routes the workers poll, for the worker
  server's address alone (below).
- The API: uvicorn on `127.0.0.1:8000` (`instance/breedgraph.service`), as the `breedgraph` user, from
  `/opt/breedgraph/.venv`, with its environment in `/opt/breedgraph/breedgraph.env`.
- Neo4j, running Cypher 25, and Redis.
- A checkout of the release in `/opt/breedgraph/checkout`, for the scripts, which aren't in the wheel.
- cron: the database backups and the retention run.
- The demonstration site, if it is hosted: `instance/demo/README.md`.

**The worker server**, for archive, analysis and maps:
- The archive worker (`instance/archive_worker.service`) in `/opt/archive_worker`, as `archiveworker`, keeping the
  archived files in its `ARCHIVE_DESTINATION`.
- The analysis worker (`instance/analysis_worker.service`) in `/opt/analysis_worker`, as `analysisworker`, with R.
- The map worker (`instance/map_worker.service`) in `/opt/map_worker`, as `mapworker`, with `pmtiles`: it fetches the
  map tiles and outlines the API needs from the internet, so that the web server needs no access to it (maps.md), and keeps
  what it cuts in its `MAP_CACHE_PATH`. If the demonstration site is hosted, its own map worker runs beside it
  (`instance/demo/map-worker-demo.service`), sharing the cache.
- cron: copying the database backups and the erasure log from the web server (`scripts/sync_database_backups.sh`).

The worker server reaches the web server, and never the other way. The workers poll the API at the site's address
(`API_URL`, `https://<site>`) with the tokens they share with the API, and nginx passes `/archive/`, `/analysis_jobs/`
and `/map_jobs/` to the API for the worker server's address alone (nginx, below); the backup copy reads the web
server's dumps with rsync over ssh (§3). So the worker server needs HTTPS and ssh to the web server, and the web
server nothing of it; where the two are, and what lies between them, doesn't matter otherwise. The retention run, on
the web server, calls the API on `127.0.0.1:8000` directly.

Tested with Python 3.12, Neo4j 2026.05 (Cypher 25), Redis 7, and R 4.3 (Ubuntu 24.04's) with lme4, lmerTest,
emmeans, car and pbkrtest; the worker server also with Ubuntu 22.04 and its R 4.1 and packages (§3). breedgraph and BreedView are deployed at the same version ([releasing.md](releasing.md)).

## 1. Build, on the development machine

- **breedgraph:** `scripts/build_wheelhouses.sh --check v<version>` (Installing from the wheelhouses, below), which
  leaves the wheel and the three wheelhouses in `dist/`.
- **BreedView, production:** its build reads `.env.production`, which git ignores:

      VITE_API_HOST=https://<site>
      VITE_GRAPHQL_PATH=/graphql

  The guide's videos are in `public/guide-media`, which git ignores too; from a fresh checkout, take them from the
  release that has them before building:

      gh release download v0.1.0 --repo marcusmchale/breedview --pattern guide-media.zip
      unzip guide-media.zip -d public

  then `npm run build`, which writes `dist/`.
- **BreedView, the demonstration site:** `.env.demo.local` and `npm run build:demo`, which writes `dist-demo/`
  (`instance/demo/README.md`, BreedView).

## 2. The web server, the first time

1. **Packages.** Python 3.12 with venv, nginx, age, rsync, Neo4j and Redis (README, Setup). rsync is for the worker
   server's copy of the backups, which runs rsync over ssh and needs it at both ends, and for the demonstration site's
   reset. `pmtiles` is the map worker's, on the worker server (§3). For Neo4j, also:
   - Cypher 25, which the API's queries are written in, and which it refuses to start without: a database runs the
     language it was created with, so set `db.query.default_language=CYPHER_25` in `/etc/neo4j/neo4j.conf` before
     Neo4j first starts, for the database it creates then. `scripts/setup_initial_data.py` sets it too (step 6), as
     does, for an existing database, `ALTER DATABASE neo4j SET DEFAULT LANGUAGE CYPHER 25` in `cypher-shell -d system`
     as Neo4j's admin. BreedGraph needs no plugin (APOC).
   - Its memory: `neo4j-admin server memory-recommendation` gives settings for the machine. Leave room for the
     demonstration site, which its slice holds to 6 GB (`instance/demo/README.md`, Limits).
2. **The user and directories.** A `breedgraph` system user, owning `/opt/breedgraph` and the directories its
   environment names: the logs (`LOG_BASE`, e.g. `/var/log/breedgraph`), the uploaded files (`FILE_STORAGE_PATH`), the
   database dumps (`NEO4J_ARCHIVE_PATH`), the erasure log's (`PERSON_ERASURE_LOG_PATH`), and the map tiles and
   outlines (`MAP_TILES_PATH`, `MAP_BOUNDARIES_PATH`).
3. **The code.** The `server` wheelhouse into `/opt/breedgraph/.venv` (Installing from the wheelhouses, below), and a
   checkout
   of the release's tag in `/opt/breedgraph/checkout`, or its `git archive` where the server can't reach GitHub (same
   section).
4. **The environment.** `/opt/breedgraph/breedgraph.env`, from `instance/breedgraph.env`, which names every variable
   the API reads, owned by `breedgraph` with mode 0600:
   - `ENVIRONMENT="production"`, `PROTOCOL="https"`, `HOST_ADDRESS="<site>"`,
     `HOST_PORT=443`, `VUE_PORT=443`, `SITE_PATH=''`, `COOKIE_PREFIX=''`, `SITE_NAME`.
   - Paths absolute, as the API runs from `/opt/breedgraph` and the scripts from the checkout.
   - New random values for `SECRET_KEY`, every `*_SALT` (`ACCEPTANCE_SALT` among them: the API refuses to start
     without it) and the four tokens: `ARCHIVE_AUTH_TOKEN`, `ANALYSIS_WORKER_AUTH_TOKEN` and `MAP_WORKER_AUTH_TOKEN`,
     which the workers' env files repeat, and `RETENTION_AUTH_TOKEN`. For example
     `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`.
   - `MAP_WORKER=1`, so that the map worker fetches the maps, and `MAP_PMTILES_COMMAND=""`: the web server needs
     neither pmtiles nor internet access for them.
   - Neo4j's password (`NEO4J_USERNAME`, `NEO4J_PASSWORD`), the mail server (`MAIL_*`), and the encryption key's
     (`ENCRYPTION_RECIPIENT`, `ENCRYPTION_IDENTITY_PATH`; backups.md, Encryption key).
   - `TERMS_OF_USE_PATH` and `PRIVACY_NOTICE_PATH`, unless the packaged texts are served, and `ORCID_*` to let users
     link an ORCID iD.
   - `TMPDIR`, a directory owned by `breedgraph` on the large disk, beside `FILE_STORAGE_PATH`: uploads are held there
     while they are received, in `/tmp` otherwise (nginx, below).
   - `COUNTRY_CODES_PATH`, the countries offered when adding a location: a file in neither the repository nor the
     wheel, the UN's M49 overview as CSV, which the template's comment describes. Without it, only the countries
     already added are offered, and none at all until the read models are filled (step 6).
5. **The unit.** `instance/breedgraph.service` to `/etc/systemd/system/`, then `sudo systemctl daemon-reload` and
   `sudo systemctl enable --now breedgraph`.
6. **The first data.** From the checkout, with the venv and the environment: `python scripts/setup_initial_data.py`,
   which refuses a database that isn't empty, and makes the schema, a system account and the ontology's first entries
   (Installing from the wheelhouses, below). Then make the site's first account, the first ontology admin, which invites
   the others:
   `python scripts/create_first_account.py --name <username> --email <address> --fullname "<full name>"` asks for its
   password and its holder's consent to the privacy notice, and prints its id. Registering in BreedView always needs
   an invitation, so nobody can register before you.
   - **Germplasm.** Create the team that will control it (Access control, Teams), and give yourself write access to
     it: Set Affiliation on the team, and Write, approved at once as you are its admin; creating a team gives admin
     access, not write. Then, from the checkout, with the user's and the team's ids:
     `python scripts/import_germplasm.py -e germplasm.json -r relationships.json -u <user id> -t <team id>`, whose
     header gives the files' format. It writes everything or nothing, and refuses a second run. The team shows its id
     under Access control, and the first account's is the one `create_first_account.py` printed.
   - **The read models.** Last, `python scripts/load_state_store.py`, which fills Redis with the countries and the
     ontology that the API reads from there: until it runs, adding a location offers no countries. Run it again after
     any script that writes to the database.
7. **Maps.** Once the map worker runs (§3), from the checkout with the venv and the environment:
   `python scripts/map_tiles.py` cuts the world file through it (about 560 MB, maps.md), and
   `python scripts/map_tiles.py --regions` fetches the detailed maps of the countries and located locations already
   in the database, which no one asked the worker for. The API fetches the rest as countries are added.
8. **BreedView.** `dist/` copied to `/var/www/breedview`; the branding to `/etc/breedview/branding` (BreedView's
   README, Branding).
9. **nginx**, below.
10. **cron and logrotate**: the backup and the retention run (backups.md), as
    `breedgraph`, in `/etc/cron.d/breedgraph`, which only root can change, logging to `LOG_BASE`:

        15 2 * * * breedgraph cd /opt/breedgraph/checkout && set -a && . /opt/breedgraph/breedgraph.env && set +a && scripts/backup.sh >> /var/log/breedgraph/backup.log 2>&1
        30 3 * * * breedgraph BREEDGRAPH_PYTHON=/opt/breedgraph/.venv/bin/python /opt/breedgraph/checkout/scripts/trigger_retention.sh /opt/breedgraph/breedgraph.env >> /var/log/breedgraph/retention.log 2>&1

    The backup needs the sudo rule [backups.md](backups.md) gives, `/etc/sudoers.d/breedgraph-backup`; then the log rotation it
    gives. Run each once as `breedgraph`: the backup ends with its dump's name, and the API is still running after it.
11. **The BreedCAFS data**, once: `src/breedcafs_migration/RUNBOOK.md`.

## 3. The worker server, the first time

1. **Packages.** Python 3.12 with venv, rsync (for the backups' copy); R with its headers and a compiler, and R's
   packages, as root:

       sudo apt install r-base r-base-dev build-essential
       sudo Rscript -e 'install.packages(c("lme4", "lmerTest", "emmeans", "car", "pbkrtest"), repos = "https://cloud.r-project.org")'

   Where CRAN can't be reached, take them from Ubuntu instead, which served as well on Ubuntu 24.04 (R 4.3):

       sudo apt install r-base r-base-dev build-essential r-cran-lme4 r-cran-lmertest r-cran-emmeans r-cran-car r-cran-pbkrtest

   On Ubuntu 22.04, take them from Ubuntu even where CRAN can be reached: its R is 4.1, too old for CRAN's current
   releases, while Ubuntu's own packages pass the analysis worker's tests (Checks). Either way, check that R loads them:

       Rscript -e 'for (p in c("lme4", "lmerTest", "emmeans", "car", "pbkrtest")) library(p, character.only = TRUE)'

   Ubuntu 22.04's Python is 3.10: install 3.12 where the units can reach it, outside `/home`, which their
   `ProtectHome=yes` hides, e.g. `sudo env UV_PYTHON_INSTALL_DIR=/opt/python uv python install 3.12`, and make the venvs
   with `/opt/python/cpython-3.12-linux-x86_64-gnu/bin/python3.12`, which follows uv's upgrades of 3.12.

   For the map worker, `pmtiles` in `/usr/local/bin` (maps.md): it needs internet access, to Protomaps' builds
   (`build.protomaps.com`, `build-metadata.protomaps.dev`) and geoBoundaries (`www.geoboundaries.org` and the GitHub
   files it links to).
2. **Users and directories.** `archiveworker` owning `/opt/archive_worker`, `/var/log/archive_worker` and the
   archive's `ARCHIVE_DESTINATION`, on the large disk; `analysisworker` owning `/opt/analysis_worker` and
   `/var/log/analysis_worker`; `mapworker` owning `/opt/map_worker`, `/var/log/map_worker` and `/srv/map_worker`, on
   the large disk. That holds the worker's `MAP_WORK_PATH` (`/srv/map_worker/work`), with room for the largest file the
   API fetches (`MAP_REGION_MAX_GB`, 2), and its `MAP_CACHE_PATH` (`/srv/map_worker/cache`), which keeps every region
   cut, for either site, until it is deleted by hand (maps.md). The two must be on the same filesystem.
3. **The code.** The `worker` wheelhouse into `/opt/archive_worker/.venv` and `/opt/map_worker/.venv`, and the
   `analysis_worker` wheelhouse into `/opt/analysis_worker/.venv`, which compiles rpy2 against R as it installs. Where
   `/tmp` is mounted `noexec`, that fails with `TypeError: 'NoneType' object is not callable`: install with `TMPDIR`
   set to a directory where programs may run (Installing from the wheelhouses, below).
4. **The environments.** `/opt/archive_worker/archive_worker.env`, `/opt/analysis_worker/analysis_worker.env` and
   `/opt/map_worker/map_worker.env`, from `instance/`, mode 0600: `API_URL` the site's address (`https://<site>`),
   the token the API's environment has for each, `LOG_BASE` in
   `/var/log/...`, for the archive worker its `ARCHIVE_DESTINATION` and for the map worker its `MAP_WORK_PATH` and
   `MAP_CACHE_PATH`.
5. **The units.** `instance/archive_worker.service`, `instance/analysis_worker.service` and
   `instance/map_worker.service` to `/etc/systemd/system/`, with the archive's `ARCHIVE_DESTINATION` in the archive
   worker's `ReadWritePaths` and `/srv/map_worker` in the map worker's, then `daemon-reload` and `enable --now` each.
   For the demonstration site, also its map worker: `instance/demo/README.md`, Setting it up.
6. **The backup copy.** `/etc/breedgraph/backup_sync.env` (from `instance/backup_sync.env`), an ssh key the web server
   accepts, and cron (backups.md). It never needs the encryption key. On the web server,
   the key belongs to a user of its own, which may only read the dumps and the erasure log, and only with rsync
   (`rrsync -ro`, backups.md).

## nginx on the web server

Set nginx's `client_max_body_size` to the largest file users may upload, e.g. `100M`. It is the upload size limit:
the API sets none of its own, but for legal references given as files (`LEGAL_FILE_SIZE_LIMIT`). nginx refuses a larger
request with 413 before it reaches the API, and breedview says the file is larger than the server accepts. breedview
and the API are served from one origin, so the browser lets breedview read the 413; were they served from separate
origins, nginx's error page would need the CORS headers too (`add_header ... always`), or breedview would see only a
failed request.

A large upload is written to disk twice on its way in unless told otherwise: nginx keeps the whole request in a
temporary file before passing it on, and the API keeps each file in one while it is received, in the system's
temporary directory (`/tmp`). Where the root disk is small beside the upload limit, pass the API's requests on as they
arrive, with `proxy_request_buffering off;` and `proxy_http_version 1.1;` in its location, and set `TMPDIR` in the
API's environment to a directory on the large disk (§2, the environment).

The site's server block, with the certificate lines it has, and the demonstration site's snippet if it is hosted:

    server {
        listen 443 ssl;
        server_name <site>;
        # ... ssl_certificate and ssl_certificate_key, as now

        # the upload limit, which BreedView reports (above)
        client_max_body_size 100M;

        root /var/www/breedview;
        # BreedView's routes, such as /guide/joining, load its index.html, so that deep links survive a reload
        location / {
            try_files $uri $uri/ /index.html;
        }
        # BreedView's page, which names the build's files: browsers check it on every load, so that a new release is
        # used at once rather than a copy cached by guesswork, while the files it names, renamed with each build, are
        # kept a year. Without it, a browser that knew the old release may keep loading it for days after an upgrade.
        location = /index.html {
            add_header Cache-Control "no-cache";
        }
        location ^~ /assets/ {
            add_header Cache-Control "public, max-age=31536000, immutable";
        }

        # the API's public routes: everything else it serves is for the workers and the retention run
        location ~ ^/(graphql|csrf|download|verify|reset)$ {
            proxy_pass http://127.0.0.1:8000;
            proxy_http_version 1.1;
            # uploads go to the API as they arrive, not first to a temporary file on the root disk (above)
            proxy_request_buffering off;
            proxy_set_header Host $host;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # map tiles (maps.md, Serving the tiles), with the paths of MAP_TILES_PATH
        location = /tiles/tiles.json {
            alias /opt/breedgraph/map_tiles/tiles.json;
            add_header Cache-Control "no-cache";
        }
        location ^~ /tiles/ {
            alias /opt/breedgraph/map_tiles/;
            add_header Cache-Control "public, max-age=86400";
        }

        # the deployment's branding (BreedView's README, Branding)
        location ^~ /branding/ {
            alias /etc/breedview/branding/;
            add_header Cache-Control "no-cache";
        }

        # the guide's videos, answered in ranges, and its captions, which browsers play only as text/vtt
        location ^~ /guide-media/ {
            add_header Cache-Control "public, max-age=3600";
            location ~ \.vtt$ {
                types { }
                default_type text/vtt;
            }
        }

        include snippets/breedgraph-demo.conf;
    }

And, in the same server block, the routes the workers poll, for the worker server's address alone: the tokens
authenticate the workers, and the address keeps everyone else from trying. Archived files come back to the API whole
when users ask for them, and analysis results and map files (to 2 GB) can be large, so they set no body limit, and pass
bodies both ways as they arrive rather than through temporary files on the root disk:

    location ~ ^/(archive|analysis_jobs|map_jobs)/ {
        allow <worker server's address>;
        deny all;
        proxy_pass http://127.0.0.1:8000;
        # HTTP/1.1, without which nginx buffers a chunked upload whatever proxy_request_buffering says
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        client_max_body_size 0;
        proxy_request_buffering off;
        proxy_buffering off;
        proxy_read_timeout 300s;
        # the workers poll every few seconds, which the API's own log leaves out too; refusals still go to the error log
        access_log off;
    }

The demonstration site's snippet has the same for its map worker, at `/demo/map_jobs/`. Then `sudo nginx -t` and
`sudo systemctl reload nginx`.

nginx allows by the address a request comes from. Where the site's name resolves, from the worker server, to something
in front of the web server, such as a proxy or a load balancer, the workers' requests come from that instead: give the
worker server the web server's own address for the name (in its `/etc/hosts`), so that it connects directly, the
certificate still checked as for any visitor. From the worker server,
`curl -s -o /dev/null -w '%{http_code}\n' https://<site>/map_jobs/next/quick` then gives 401, the API refusing a request
without the token; from anywhere else, 403.

## Upgrading to a new release

1. Build it (§1).
2. **The web server:** the new `server` wheelhouse into `/opt/breedgraph/.venv`, as installed with `--upgrade`, the
   checkout moved to the new tag (or replaced by its archive), the release's new settings added to `breedgraph.env`
   ([upgrading.md](upgrading.md) lists them), and `sudo systemctl restart breedgraph`; then BreedView's new `dist/` in place of
   `/var/www/breedview`.
3. **The worker server:** the wheelhouses with `--upgrade` into the three venvs, and the three units restarted (with
   `map-worker-demo` if the demonstration site is hosted, as it runs from the map worker's venv).
4. **The demonstration site:** `instance/demo/README.md`, Upgrades.
5. What the release needs besides, in its section of [upgrading.md](upgrading.md).
6. The checks below.

## Checks

- The site loads with its branding, and signing in and out works.
- An upload shows as archived within a minute or so (the worker server reaches the API), and is downloaded again.
- An analysis runs: an ANOVA (R) and descriptive statistics. Before the site holds data to analyse, run the analysis
  worker's tests against its venv instead, from the release's checkout, with pytest installed beside the venv rather
  than in it; they need neither the API nor the database, and pass with none skipped:

      mkdir ~/awtest
      tar xzf breedgraph-<version>-checkout.tar.gz -C ~/awtest
      /opt/analysis_worker/.venv/bin/python -m pip install --target ~/awtest/pylib pytest pytest-asyncio
      cd ~/awtest/checkout
      PYTHONPATH=$HOME/awtest/pylib ANALYSIS_WORKER_AUTH_TOKEN=test LOG_BASE=$HOME/awtest/logs /opt/analysis_worker/.venv/bin/python -m pytest -p no:cacheprovider -q -rs tests/analysis_worker
- The map shows its tiles, and a place search answers. Adding a country fetches its map through the map worker: its
  log (`/var/log/map_worker/map.log`) shows the outlines, size and extract jobs, and the country's layer is in
  `/tiles/tiles.json` once it is done (or it is divided, if larger than `MAP_REGION_MAX_GB`). Remove that country and
  add it again: the log says the region is sent from the cache, and `/srv/map_worker/cache` holds it.
- An invitation's email arrives, and its link opens the registration page.
- A guide chapter's video plays, with its captions.
- `trigger_retention.sh /opt/breedgraph/breedgraph.env` prints the API's response.
- `scripts/backup.sh` writes an encrypted dump, and the worker server's copy picks it up.

## Installing from the wheelhouses

Each service installs from a wheelhouse, a folder of the wheels it needs, without reaching PyPI: the API from the
`server` extra's, the archive and map workers from `worker`'s and the analysis worker from `analysis_worker`'s. Build
them from the release's tag, on a machine with the development environment:

    cd path/to/breedgraph
    scripts/build_wheelhouses.sh --check v<version>

They land in `dist/` as `wheelhouse_<extra>_<version>`, beside the wheel and the source distribution, built for
CPython 3.12 on x86_64 with glibc 2.34 or later; the script's header says what `--check` needs. rpy2 has no wheels, so
the analysis worker's machine builds it as it installs, with R's headers and a compiler
(`sudo apt install r-base-dev build-essential`), beside R and the packages `instance/analysis_worker.service` names.

Copy each wheelhouse to its machine, somewhere the user that runs the service can read it:

    scp -r dist/wheelhouse_server_<version> user@server:~/

then, on the server and as that user, install it into the venv its unit runs:

    cd /opt/breedgraph
    python3 -m venv .venv
    .venv/bin/python -m pip install --no-index --find-links /path/to/wheelhouse_server_<version>/ 'breedgraph[server]'

and likewise `breedgraph[worker]` into `/opt/archive_worker/.venv` and `/opt/map_worker/.venv`, and
`breedgraph[analysis_worker]` into `/opt/analysis_worker/.venv`. To upgrade, install the new wheelhouse into the same
venv with `--upgrade`, then restart the service.

On a server whose `/tmp` is mounted `noexec` (`findmnt -no OPTIONS /tmp`), building rpy2 fails: pip installs cffi,
whose compiled module can't be loaded from `/tmp`, and rpy2's build, giving up on it quietly, ends with
`TypeError: 'NoneType' object is not callable` in cffi's `setuptools_ext.py`. Give pip a temporary directory where
programs may run, owned by the installing user, and remove it afterwards:

    sudo install -d -o analysisworker -g analysisworker -m 700 /opt/analysis_worker/pip-tmp
    sudo -u analysisworker env TMPDIR=/opt/analysis_worker/pip-tmp /opt/analysis_worker/.venv/bin/python -m pip install --no-index --find-links /path/to/wheelhouse_analysis_worker_<version>/ 'breedgraph[analysis_worker]'
    sudo rm -rf /opt/analysis_worker/pip-tmp

The scripts aren't in the wheel, nor in the source distribution: run them from a checkout of the release's tag, with
the venv, whose breedgraph they import, and the environment. A server that can't reach GitHub is sent the tag as an
archive, unpacked where the checkout goes (`tar xzf ... -C /opt/breedgraph` gives `/opt/breedgraph/checkout`):

    git archive --format=tar.gz --prefix=checkout/ -o dist/breedgraph-<version>-checkout.tar.gz v<version>

and then:

    . /opt/breedgraph/.venv/bin/activate
    set -a
    . /opt/breedgraph/breedgraph.env
    set +a
    python scripts/setup_initial_data.py
    python scripts/load_state_store.py

`load_state_store.py` fills the read models in Redis that the API reads the countries and the ontology from: until it
runs, adding a location offers no countries. Run it again after any script that writes to the database, such as
`scripts/import_germplasm.py`.

## BreedView and its branding

BreedView, the front end, is built and deployed from its own repository, and so is a deployment's branding, its
colours, logo, fonts and footer links: breedview README.md, Branding. nginx serves both from the API's origin (nginx,
above). The API's emails name the site by `SITE_NAME`, and its Terms of Use and privacy notice are files of their own
(`TERMS_OF_USE_PATH`, `PRIVACY_NOTICE_PATH`): branding doesn't change them.

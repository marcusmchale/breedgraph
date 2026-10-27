# Deploying BreedGraph and BreedView

The steps in order, from building the release to checking the running site. The details of each are where they are
kept: this README (Setup, deploy), [BreedView's README](https://github.com/marcusmchale/breedview) (Branding),
`instance/` (the units and environment templates), and `instance/demo/README.md` for the demonstration site.

## What runs where

**The web server**, `breedgraph.universityofgalway.ie`:
- nginx: the site, its certificate, BreedView's build in `/var/www/breedview` and its branding in
  `/etc/breedview/branding`; the API's public routes; the map tiles; and, on the internal network, the routes the
  workers poll (below).
- The API: uvicorn on `127.0.0.1:8000` (`instance/breedgraph.service`), as the `breedgraph` user, from
  `/opt/breedgraph/.venv`, with its environment in `/opt/breedgraph/breedgraph.env`.
- Neo4j, with the APOC core plugin, and Redis.
- A checkout of the release in `/opt/breedgraph/checkout`, for the scripts, which aren't in the wheel.
- cron: the database backups and the retention run.
- The demonstration site, if it is hosted: `instance/demo/README.md`.

**The worker server**, for archive and analysis, on the internal network:
- The archive worker (`instance/archive_worker.service`) in `/opt/archive_worker`, as `archiveworker`, keeping the
  archived files in its `ARCHIVE_DESTINATION`.
- The analysis worker (`instance/analysis_worker.service`) in `/opt/analysis_worker`, as `analysisworker`, with R.
- cron: copying the database backups and the erasure log from the web server (`scripts/sync_database_backups.sh`).

Both workers poll the API at their `API_URL`, an address of the web server on the internal network, with the tokens
they share with the API. nginx there passes `/archive/` and `/analysis_jobs/` to the API, for the worker server alone.
The retention run, on the web server, calls the API on `127.0.0.1:8000` directly.

Tested with Python 3.12, Neo4j 2026.05 and its APOC core, Redis 7, and R 4.3 (Ubuntu 24.04's) with lme4, lmerTest,
emmeans, car and pbkrtest. breedgraph and BreedView are deployed at the same version (README, Releases).

## 1. Build, on the development machine

- **breedgraph:** `scripts/build_wheelhouses.sh --check v<version>` (README, Build the wheelhouses), which leaves the
  wheel and the three wheelhouses in `dist/`.
- **BreedView, production:** its build reads `.env.production`, which git ignores:

      VITE_API_HOST=https://breedgraph.universityofgalway.ie
      VITE_GRAPHQL_PATH=/graphql

  The guide's videos are in `public/guide-media`, which git ignores too; from a fresh checkout, take them from the
  release that has them before building:

      gh release download v0.1.0 --repo marcusmchale/breedview --pattern guide-media.zip
      unzip guide-media.zip -d public

  then `npm run build`, which writes `dist/`.
- **BreedView, the demonstration site:** `.env.demo.local` and `npm run build:demo`, which writes `dist-demo/`
  (`instance/demo/README.md`, BreedView).

## 2. The web server, the first time

1. **Packages.** Python 3.12 with venv, nginx, age, Neo4j and Redis (README, Setup), and `pmtiles` (README, Maps).
   For Neo4j, also:
   - The APOC core plugin, which the API's queries use (`apoc.coll.*`): copy `apoc-<version>-core.jar` from
     `/var/lib/neo4j/labs/` to `/var/lib/neo4j/plugins/`, and allow it in `/etc/neo4j/neo4j.conf`:
     `dbms.security.procedures.allowlist=apoc.coll.*`.
   - Its memory: `neo4j-admin server memory-recommendation` gives settings for the machine. Leave room for the
     demonstration site, which its slice holds to 6 GB (`instance/demo/README.md`, Limits).
2. **The user and directories.** A `breedgraph` system user, owning `/opt/breedgraph` and the directories its
   environment names: the logs (`LOG_BASE`, e.g. `/var/log/breedgraph`), the uploaded files (`FILE_STORAGE_PATH`), the
   database dumps (`NEO4J_ARCHIVE_PATH`), the erasure log's (`PERSON_ERASURE_LOG_PATH`), and the map tiles and
   outlines (`MAP_TILES_PATH`, `MAP_BOUNDARIES_PATH`).
3. **The code.** The `server` wheelhouse into `/opt/breedgraph/.venv` (README, Build the wheelhouses), and a checkout
   of the release's tag in `/opt/breedgraph/checkout`.
4. **The environment.** `/opt/breedgraph/breedgraph.env`, from `instance/breedgraph.env`, which names every variable
   the API reads, owned by `breedgraph` with mode 0600:
   - `ENVIRONMENT="production"`, `PROTOCOL="https"`, `HOST_ADDRESS="breedgraph.universityofgalway.ie"`,
     `HOST_PORT=443`, `VUE_PORT=443`, `SITE_PATH=''`, `COOKIE_PREFIX=''`, `SITE_NAME`.
   - Paths absolute, as the API runs from `/opt/breedgraph` and the scripts from the checkout.
   - New random values for `SECRET_KEY`, every `*_SALT` (`ACCEPTANCE_SALT` among them: the API refuses to start
     without it) and the three tokens: `ARCHIVE_AUTH_TOKEN` and `ANALYSIS_WORKER_AUTH_TOKEN`, which the workers' env
     files repeat, and `RETENTION_AUTH_TOKEN`. For example `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`.
   - Neo4j's password (`NEO4J_USERNAME`, `NEO4J_PASSWORD`), the mail server (`MAIL_*`), and the encryption key's
     (`ENCRYPTION_RECIPIENT`, `ENCRYPTION_IDENTITY_PATH`; README, Encryption key).
   - `TERMS_OF_USE_PATH` and `PRIVACY_NOTICE_PATH`, unless the packaged texts are served, and `ORCID_*` to let users
     link an ORCID iD.
   - `TMPDIR`, a directory owned by `breedgraph` on the large disk, beside `FILE_STORAGE_PATH`: uploads are held there
     while they are received, in `/tmp` otherwise (README, Nginx).
   - `COUNTRY_CODES_PATH`, the countries offered when adding a location: a file in neither the repository nor the
     wheel, the UN's M49 overview as CSV, which the template's comment describes. Without it, only the countries
     already added are offered.
5. **The unit.** `instance/breedgraph.service` to `/etc/systemd/system/`, then `sudo systemctl daemon-reload` and
   `sudo systemctl enable --now breedgraph`.
6. **The first data.** From the checkout, with the venv and the environment: `python scripts/setup_initial_data.py`,
   which refuses a database that isn't empty, and makes the schema, a system account and the ontology's first entries
   (README, deploy). Then make the site's first account, the first ontology admin, which invites the others:
   `python scripts/create_first_account.py --name <username> --email <address> --fullname "<full name>"` asks for its
   password and its holder's consent to the privacy notice, and prints its id. Registering in BreedView always needs
   an invitation, so nobody can register before you.
   - **Germplasm.** Create the team that will control it (Access control, Teams), and give yourself write access to
     it: Set Affiliation on the team, and Write, approved at once as you are its admin; creating a team gives admin
     access, not write. Then, from the checkout, with the user's and the team's ids:
     `python scripts/import_germplasm.py -e germplasm.json -r relationships.json -u <user id> -t <team id>`, whose
     header gives the files' format. It writes everything or nothing, and refuses a second run. The team shows its id
     under Access control, and the first account's is the one `create_first_account.py` printed.
7. **Maps.** `scripts/map_tiles.py` cuts the world file (README, Maps).
8. **BreedView.** `dist/` copied to `/var/www/breedview`; the branding to `/etc/breedview/branding` (BreedView's
   README, Branding).
9. **nginx**, below.
10. **cron and logrotate**: the backup and the retention run (README, Backups, restores and retention), as
    `breedgraph`, in `/etc/cron.d/breedgraph`, which only root can change, logging to `LOG_BASE`:

        15 2 * * * breedgraph cd /opt/breedgraph/checkout && set -a && . /opt/breedgraph/breedgraph.env && set +a && scripts/backup.sh >> /var/log/breedgraph/backup.log 2>&1
        30 3 * * * breedgraph BREEDGRAPH_PYTHON=/opt/breedgraph/.venv/bin/python /opt/breedgraph/checkout/scripts/trigger_retention.sh /opt/breedgraph/breedgraph.env >> /var/log/breedgraph/retention.log 2>&1

    The backup needs the sudo rule the README gives, `/etc/sudoers.d/breedgraph-backup`; then the log rotation it
    gives. Run each once as `breedgraph`: the backup ends with its dump's name, and the API is still running after it.
11. **The BreedCAFS data**, once: README, Migrating the BreedCAFS data.

## 3. The worker server, the first time

1. **Packages.** Python 3.12 with venv; R with its headers and a compiler, and R's packages, as root:

       sudo apt install r-base r-base-dev build-essential
       sudo Rscript -e 'install.packages(c("lme4", "lmerTest", "emmeans", "car", "pbkrtest"), repos = "https://cloud.r-project.org")'

2. **Users and directories.** `archiveworker` owning `/opt/archive_worker`, `/var/log/archive_worker` and the
   archive's `ARCHIVE_DESTINATION`, on the large disk; `analysisworker` owning `/opt/analysis_worker` and
   `/var/log/analysis_worker`.
3. **The code.** The `worker` wheelhouse into `/opt/archive_worker/.venv`, and the `analysis_worker` wheelhouse into
   `/opt/analysis_worker/.venv`, which compiles rpy2 against R as it installs.
4. **The environments.** `/opt/archive_worker/archive_worker.env` and `/opt/analysis_worker/analysis_worker.env`, from
   `instance/`, mode 0600: `API_URL` the web server's internal address (`http://<internal address>:8080`, below), the
   token the API's environment has for each, `LOG_BASE` in `/var/log/...`, and for the archive worker its
   `ARCHIVE_DESTINATION`.
5. **The units.** `instance/archive_worker.service` and `instance/analysis_worker.service` to `/etc/systemd/system/`,
   then `daemon-reload` and `enable --now` each.
6. **The backup copy.** `/etc/breedgraph/backup_sync.env` (from `instance/backup_sync.env`), an ssh key the web server
   accepts, and cron (README, Backups, restores and retention). It never needs the encryption key.

## nginx on the web server

The site's server block, with the certificate lines it has, and the demonstration site's snippet if it is hosted:

    server {
        listen 443 ssl;
        server_name breedgraph.universityofgalway.ie;
        # ... ssl_certificate and ssl_certificate_key, as now

        # the upload limit, which BreedView reports (README, Nginx)
        client_max_body_size 100M;

        root /var/www/breedview;
        # BreedView's routes, such as /guide/joining, load its index.html, so that deep links survive a reload
        location / {
            try_files $uri $uri/ /index.html;
        }

        # the API's public routes: everything else it serves is for the workers and the retention run
        location ~ ^/(graphql|csrf|download|verify|reset)$ {
            proxy_pass http://127.0.0.1:8000;
            proxy_http_version 1.1;
            # uploads go to the API as they arrive, not first to a temporary file on the root disk (README, Nginx)
            proxy_request_buffering off;
            proxy_set_header Host $host;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # map tiles (README, Nginx), with the paths of MAP_TILES_PATH
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

And a server on the web server's internal address, for the worker server alone. Archived files come back to the API
whole when users ask for them, and analysis results can be large, so it sets no body limit:

    server {
        listen <web server's internal address>:8080;
        allow <worker server's internal address>;
        deny all;
        client_max_body_size 0;
        proxy_request_buffering off;
        proxy_read_timeout 300s;

        location ~ ^/(archive|analysis_jobs)/ {
            proxy_pass http://127.0.0.1:8000;
            proxy_set_header Host $host;
        }
        location / {
            return 404;
        }
    }

then `sudo nginx -t` and `sudo systemctl reload nginx`. If a firewall runs on the web server, open that port to the
worker server only.

## Upgrading to a new release

1. Build it (§1).
2. **The web server:** the new `server` wheelhouse into `/opt/breedgraph/.venv`, as installed with `--upgrade`, the
   checkout moved to the new tag, the release's new settings added to `breedgraph.env` (its notes list them), and
   `sudo systemctl restart breedgraph`; then BreedView's new `dist/` in place of `/var/www/breedview`.
3. **The worker server:** both wheelhouses with `--upgrade`, and both units restarted.
4. **The demonstration site:** `instance/demo/README.md`, Upgrades.
5. The checks below.

## Checks

- The site loads with its branding, and signing in and out works.
- An upload shows as archived within a minute or so (the worker server reaches the API), and is downloaded again.
- An analysis runs: an ANOVA (R) and descriptive statistics.
- The map shows its tiles, and a place search answers.
- An invitation's email arrives, and its link opens the registration page.
- A guide chapter's video plays, with its captions.
- `trigger_retention.sh /opt/breedgraph/breedgraph.env` prints the API's response.
- `scripts/backup.sh` writes an encrypted dump, and the worker server's copy picks it up.

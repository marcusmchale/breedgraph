# The hosted demonstration site

A second BreedGraph beside production, on the same server, for the user guide's readers and for the DPO's and the legal
office's review: the demonstration database (docs/demo-database.md), reset every night, with BreedView's demonstration
build, whose banner says the site is fictional. It has its own Neo4j, Redis, API, analysis and archive workers, files,
encryption key and logs, so nothing in it touches production, and one systemd target starts, stops and restarts them
together.

The files here are templates: copy each to the place its first line names, fill in what is in angle brackets, and keep
the private ones (mode 0600).

| File | Goes to | What it is |
|---|---|---|
| `breedgraph-demo.env` | `/opt/breedgraph-demo/breedgraph-demo.env` (private, owned by `breedgraph-demo`) | the API's and the reset's environment |
| `analysis-worker-demo.env`, `archive-worker-demo.env` | `/opt/breedgraph-demo/` (private, owned by root) | the workers' environments, which hold none of the API's secrets |
| `neo4j.conf` | `/opt/breedgraph-demo/neo4j/conf/neo4j.conf` | the second Neo4j: its own directories and ports, authentication on |
| `redis-demo.conf` | `/etc/redis/redis-demo.conf` | the second Redis, on 6380 |
| `breedgraph-demo.target` | `/etc/systemd/system/` | the site's services together |
| `neo4j-demo.service`, `redis-demo.service`, `breedgraph-demo.service`, `analysis-worker-demo.service`, `archive-worker-demo.service` | `/etc/systemd/system/` | the services, each part of the target |
| `breedgraph-demo-reset.service`, `breedgraph-demo-reset.timer` | `/etc/systemd/system/` | the nightly reset (`scripts/reset_demo.sh`) |
| `nginx-breedgraph-demo.conf` | `/etc/nginx/sites-available/breedgraph-demo` | the site: BreedView's build, the API, the tiles |
| `legal-preamble.md` | read from here by the reset | what the site's Terms and privacy notice say first |
| `demo_accounts.example.json` | `/opt/breedgraph-demo/private/demo_accounts.json` (private, owned by `breedgraph-demo`) | the site's passwords and reviewer accounts (`scripts/set_demo_accounts.py`) |

## The host name

`demo.breedgraph.universityofgalway.ie`, a subdomain of production's, on the same address: nginx tells the two sites
apart by name, as the browser sends it (and, for HTTPS, as SNI).

- **DNS.** The name needs a record of its own, an `A` record for the server's address or a `CNAME` to
  `breedgraph.universityofgalway.ie`, from whoever keeps the university's DNS, unless a wildcard already covers it.
- **HTTPS, not HTTP.** Every cookie the API sets (login, CSRF, the Terms' acceptance) is `Secure`, so over plain HTTP a
  browser keeps none of them and nothing past the first page works. A certificate for the name is free from Let's
  Encrypt (below), or the university's certificate service can issue one.
- **Cookies.** The API sets every cookie for its own host only, so neither site is sent the other's. Before 2026-10-26
  the CSRF cookie named `domain=HOST_ADDRESS`, which browsers also send to subdomains: deploy production with that
  change, at least an hour (`CSRF_EXPIRES`) before the site opens, so that no browser still holds the old one.

## Setting it up (the server work)

1. **Accounts and directories.** A `breedgraph-demo` system user (Neo4j, Redis, the API, the archive worker and the
   reset run as it), and `analysisworker` if production's isn't on this machine. `/opt/breedgraph-demo` owned by
   `breedgraph-demo`, holding:
   - `checkout/`: a clone of breedgraph at production's version, with a `.venv` holding
     `pip install -e '.[api,worker,analysis_worker]'` (or production's wheelhouse);
   - `neo4j/` (`conf`, `data`, `logs`, `run`, `import`), `dump/`, `files/`, `archive/`, `legal/`, `map_tiles/`;
   - `logs/`, with `logs/analysis-worker/` owned by `analysisworker`;
   - `private/` (0700).
2. **Neo4j.** The installed package, run a second time (Community runs one database an instance): `neo4j.conf` here,
   ports 7688 and 7475 on 127.0.0.1. Copy `server-logs.xml` and `user-logs.xml` from `/etc/neo4j` beside it, then set
   its password as `breedgraph-demo`: `NEO4J_CONF=/opt/breedgraph-demo/neo4j/conf neo4j-admin dbms set-initial-password
   <password>`, and put it in the env file. Its memory (1 GB heap at most and a 256 MB page cache, ample for a dump
   under 1 MB) comes on top of production's: check the server has room for both.
3. **Redis.** `redis-demo.conf`: port 6380 on 127.0.0.1, nothing saved, as each reset empties it.
4. **The environments.** `breedgraph-demo.env`, with its own `SECRET_KEY`, salts and worker tokens (none shared with
   production), and real SMTP. The workers' env files take the same two tokens. The site's own encryption key, for the
   archive worker's copies: `sudo -u breedgraph-demo age-keygen -o /opt/breedgraph-demo/private/encryption_key.txt`,
   and its public key (`age-keygen -y` on the file) as `ENCRYPTION_RECIPIENT`.
5. **The dump.** Copy the build's `demo_database.dump` to `/opt/breedgraph-demo/dump/neo4j.dump` and its
   `demo_database_files/` to `/opt/breedgraph-demo/dump/files/`. The build's manifest holds its generated passwords:
   the site's own go in the accounts file instead.
6. **Map tiles.** The world file and Ireland's region into `/opt/breedgraph-demo/map_tiles`, cut on a machine with
   `pmtiles` (`scripts/map_tiles.py`), as `MAP_PMTILES_COMMAND` is empty here: the site fetches no regions itself.
7. **BreedView.** `npm run build:demo` with `.env.demo.local` giving
   `VITE_API_HOST=https://demo.breedgraph.universityofgalway.ie`, and the `dist/` copied to `/var/www/breedgraph-demo`.
   The guide's media go in its `guide-media/` (from `public/guide-media`).
8. **The certificate.** Once the DNS record answers: `sudo certbot certonly --nginx -d
   demo.breedgraph.universityofgalway.ie`. certbot's timer renews it, as it does production's.
9. **nginx.** `nginx-breedgraph-demo.conf` into `sites-available`, linked from `sites-enabled`, then `sudo nginx -t`
   and `sudo systemctl reload nginx`. Production's server block stays as it is. The configuration sends
   `X-Robots-Tag: noindex`, so that search engines leave the site out.
10. **The units and the first load.** Copy the units, `sudo systemctl daemon-reload`, then
    `sudo /opt/breedgraph-demo/checkout/scripts/reset_demo.sh`, which loads the dump and starts the target, as each
    night. Then `sudo systemctl enable breedgraph-demo.target breedgraph-demo-reset.timer`, so that the site starts at
    boot and resets each night.

## Running it

The target holds Neo4j, Redis, the API and the two workers, and starts them in order:

    sudo systemctl restart breedgraph-demo.target       # or stop, or start
    systemctl list-dependencies breedgraph-demo.target  # each service's state
    journalctl -u 'neo4j-demo' -u 'breedgraph-demo' -u '*-worker-demo' --since today

The API's and the workers' logs are in `/opt/breedgraph-demo/logs`, Neo4j's in `/opt/breedgraph-demo/neo4j/logs`.
Production's services are not part of the target, so none of this stops them.

**Upgrades.** Update the site with production: pull the same version into `checkout/`, update its `.venv`, rebuild
BreedView's demonstration build, and restart the target. When the release changes the demonstration database
(`scripts/build_demo_database.py`) or its dump, copy the new dump into `dump/` and run the reset. An upgrade of the
Neo4j package upgrades both instances: run the reset afterwards, to check the dump still loads.

## Each night

`scripts/reset_demo.sh`, run by `breedgraph-demo-reset.service`:

1. Refuses to run outside the demonstration site: its env file must say `BREEDGRAPH_DEMO=1`, and name neither
   production's Neo4j port nor its Redis port.
2. Stops the target: the API, the workers, Neo4j and Redis.
3. Loads the dump with `neo4j-admin database load --overwrite-destination=true`, which replaces the store and its
   transaction logs, so what was entered is really gone.
4. Starts Neo4j and Redis, empties Redis, copies the dump's files over the file store, deleting the rest, and empties
   the archive worker's store. The dump's files wait to be archived, so the worker archives them again.
5. Empties the site's erasure log, without replaying it: the people erased there were the site's, and are gone with it.
6. Rotates `SECRET_KEY`, so that no login cookie from before the reset signs in, as a restore reissues account ids.
7. Writes the site's legal texts (`legal-preamble.md` and the drafts in `docs/legal/`), loads the state store, sets the
   accounts (`scripts/set_demo_accounts.py`), and starts the target.

## Accounts

The story's accounts (dara, bridget, theo, lena and petra) get the site's passwords, and reviewers get accounts of their
own (`dpo-reviewer-1`, ...), both from the accounts file, after each reset. DPO staff who want to try registering are
invited from the app, as anyone joins BreedGraph, and those accounts go at the next reset, as the preamble says.

## Checks

- `https://demo.breedgraph.universityofgalway.ie` shows the banner on every page, and production's site is unchanged.
- Signed in to production in the same browser, the demonstration site signs in and saves as it should (its cookies and
  production's stay apart).
- Deep links (`/guide/joining`) survive a reload: nginx falls back to `index.html`.
- `/guide-media/*.vtt` is served as `text/vtt`, and the videos answer range requests (206).
- An upload shows as archived within a minute, and an analysis runs.
- After a reset the story's state is the manifest's, and a login cookie from before it no longer signs in.

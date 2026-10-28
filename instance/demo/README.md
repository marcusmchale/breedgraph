# The hosted demonstration site

A second BreedGraph beside production, on the same server, at https://breedgraph.universityofgalway.ie/demo/, for the
user guide's readers and for the DPO's and the legal office's review: the demonstration database (docs/demo-database.md), reset every night, with BreedView's demonstration
build, whose banner says the site is fictional. It has its own Neo4j, Redis, API, analysis and archive workers, files,
encryption key and logs, so nothing in it touches production, and one systemd target starts, stops and restarts them
together. Its map worker runs on the worker server, beside production's, since the web server can't reach the
internet. The two share the worker's cache, but the site's map files are its own.

The files here are templates: copy each to the place its first line names, fill in what is in angle brackets, and keep
the private ones (mode 0600).

| File | Goes to | What it is |
|---|---|---|
| `breedgraph-demo.env` | `/opt/breedgraph-demo/breedgraph-demo.env` (private, owned by `breedgraph-demo`) | the API's and the reset's environment |
| `analysis-worker-demo.env`, `archive-worker-demo.env` | `/opt/breedgraph-demo/` (private, owned by root) | the workers' environments, which hold none of the API's secrets |
| `neo4j.conf` | `/opt/breedgraph-demo/neo4j/conf/neo4j.conf` | the second Neo4j: its own directories and ports, authentication on |
| `redis-demo.conf` | `/opt/breedgraph-demo/redis-demo.conf` | the second Redis, on 6380 |
| `breedgraph-demo.target` | `/etc/systemd/system/` | the site's services together |
| `breedgraph-demo.slice` | `/etc/systemd/system/` | the site's share of the machine's memory, which its units run in |
| `neo4j-demo.service`, `redis-demo.service`, `breedgraph-demo.service`, `analysis-worker-demo.service`, `archive-worker-demo.service` | `/etc/systemd/system/` | the services, each part of the target |
| `breedgraph-demo-reset.service`, `breedgraph-demo-reset.timer` | `/etc/systemd/system/` | the nightly reset (`scripts/reset_demo.sh`) |
| `map-worker-demo.env`, `map-worker-demo.service` | on the worker server: `/opt/map_worker/` (private, as production's `map_worker.env`) and `/etc/systemd/system/` | the site's map worker, beside production's |
| `nginx-breedgraph-demo.conf` | `/etc/nginx/snippets/breedgraph-demo.conf`, included in production's server block | the site at `/demo/`: BreedView's build, the API, the tiles |
| `legal-preamble.md` | read from here by the reset | what the site's Terms and privacy notice say first |
| `demo_accounts.example.json` | `/opt/breedgraph-demo/private/demo_accounts.json` (private, owned by `breedgraph-demo`) | the site's passwords and reviewer accounts (`scripts/set_demo_accounts.py`) |

## The address

`https://breedgraph.universityofgalway.ie/demo/`: production's host, name and certificate, so neither a DNS record nor a
certificate of its own is needed. nginx sends `/demo/` to the site (`nginx-breedgraph-demo.conf`, included in
production's server block) and the rest to production, as before.

- **Paths.** BreedView's demonstration build is built for `/demo/` (`VITE_BASE_PATH`), and the API is sent its requests
  without `/demo`, which its `SITE_PATH` puts back at the start of every link it gives: emails, verify and reset links,
  downloads.
- **Cookies.** A browser sends a host's cookies to every path on it, so the site's are named `demo_...` (`COOKIE_PREFIX`)
  and set for `/demo/`: it never reads or overwrites production's, and production is never sent the site's. Production
  needs no change. Every cookie is `Secure`, so the site needs HTTPS, which production's gives it.
- **Branding.** The site has no `branding/` folder, so it keeps BreedView's own look, as the guide's videos show it,
  while production carries the University's (breedview README.md, Branding).
- **One origin.** The two sites share an origin, so a script running in the demonstration site could call production's
  API with a visitor's production sign-in. The site runs the same code as production, so this adds little to
  production's own exposure; keep it at production's version.
- **Limits.** Visitors share production's machine, so the site's use of it is bounded. nginx refuses uploads over
  10 MB (`client_max_body_size` in the snippet), below production's limit. The analysis worker runs one analysis at
  a time, however many visitors ask, which may reserve 1.5 GB, and the worker uses 2 GB at most (`LimitAS` and
  `MemoryMax` in `analysis-worker-demo.service`), so an analysis needing more fails, saying so. Neo4j and Redis have
  limits of their own (`neo4j.conf`, `redis-demo.conf`). Visitors may add countries, whose maps are fetched to
  production's disk: the site's regions together are held to `MAP_TILES_MAX_GB` (10), beyond which a fetch fails and
  the map says so, and each reset deletes them. The site's units all run in
  `breedgraph-demo.slice`, which holds the site to 6 GB without swap, so that whatever one of its processes does, it
  is one of the site's that the kernel ends, never one of production's.

## Setting it up (the server work)

1. **Accounts and directories.** A `breedgraph-demo` system user (Neo4j, Redis, the API, the archive worker and the
   reset run as it), and `analysisworker` if production's isn't on this machine, with R and its packages, as the
   worker server has them (docs/deployment.md, the worker server, step 1: from Ubuntu's `r-cran-*` packages where
   CRAN can't be reached). `/opt/breedgraph-demo` owned by `breedgraph-demo`, holding:
   - `checkout/`: a clone of breedgraph at production's version, with a `.venv` holding
     `pip install -e '.[api,worker,analysis_worker]'` (or the three wheelhouses,
     `breedgraph[server,worker,analysis_worker]` with a `--find-links` for each). The install compiles rpy2, which
     fails where `/tmp` is mounted `noexec` (`TypeError: 'NoneType' object is not callable`): run it with `TMPDIR` set
     to a directory where programs may run (breedgraph docs/deployment.md, Installing from the wheelhouses);
   - `neo4j/` (`conf`, `data`, `logs`, `run`, `import`, `tmp`), `redis/`, `dump/`, `files/`, `archive/`, `legal/`,
     `map_tiles/`, `map_boundaries/`;
   - `logs/`, with `logs/analysis-worker/` owned by `analysisworker`;
   - `private/` (0700);
   - `country_codes.csv`, a copy of production's (`COUNTRY_CODES_PATH`).

   The maps take room: the regions visitors fetch, to `MAP_TILES_MAX_GB` (10 GB), and the world and Ireland, which
   `dump/` keeps a copy of, about 2 GB. Where `/opt` is on the system disk, beside production's Neo4j, put
   `map_tiles/`, `map_boundaries/` and `dump/` on a data disk instead, owned by `breedgraph-demo` likewise, and name
   them in the env file (`MAP_TILES_PATH`, `MAP_BOUNDARIES_PATH`, `DEMO_DUMP_DIR`) and in the nginx snippet's two
   tile locations.
2. **Neo4j.** The installed package, run a second time (Community runs one database an instance): `neo4j.conf` here,
   ports 7688 and 7475 on 127.0.0.1. Copy `server-logs.xml` and `user-logs.xml` from `/etc/neo4j` beside it, then set
   its password as `breedgraph-demo`: `NEO4J_CONF=/opt/breedgraph-demo/neo4j/conf neo4j-admin dbms set-initial-password
   <password>`, and put it in the env file. Its memory (1 GB heap at most and a 256 MB page cache, ample for a dump
   under 1 MB) comes on top of production's: check the server has room for both.
3. **Redis.** `redis-demo.conf`: port 6380 on 127.0.0.1, nothing saved, as each reset empties it. It is kept in
   `/opt/breedgraph-demo`, not `/etc/redis`, which Ubuntu closes to all but the `redis` group: `breedgraph-demo`, which
   runs this Redis, couldn't read it there, and joining that group would let it read production's Redis files.
4. **The environments.** `breedgraph-demo.env`, with its own `SECRET_KEY`, salts and worker tokens (none shared with
   production), and real SMTP. The workers' env files take the same three tokens: the map worker's on the worker
   server (step 6). The site's own encryption key, for the
   archive worker's copies: `sudo -u breedgraph-demo age-keygen -o /opt/breedgraph-demo/private/encryption_key.txt`,
   and its public key (`age-keygen -y` on the file) as `ENCRYPTION_RECIPIENT`.
5. **The dump** (`DEMO_DUMP_DIR`). Copy the build's `demo_database.dump` to `/opt/breedgraph-demo/dump/neo4j.dump`
   and its `demo_database_files/` to `/opt/breedgraph-demo/dump/files/`. The build's manifest holds its generated passwords:
   the site's own go in the accounts file instead.
6. **Maps.** The site's regions are fetched by its own map worker, on the worker server, which reaches the site's API
   at the site's address, as production's workers do (step 8):
   - On the worker server, `map-worker-demo.env` to `/opt/map_worker/` (mode 0600, as production's), with the
     site's address and its `MAP_WORKER_AUTH_TOKEN`, and `map-worker-demo.service` to
     `/etc/systemd/system/`, then `sudo systemctl daemon-reload` and `sudo systemctl enable --now map-worker-demo`. It
     runs as `mapworker` from production's map worker's venv, with a work path of its own, `/srv/map_worker/work-demo`,
     and production's cache, `/srv/map_worker/cache` (docs/deployment.md, the worker server).
   - Once the site runs (step 9), fetch its maps through its worker, as `breedgraph-demo` from the checkout with the
     site's environment: `scripts/map_tiles.py` for the world file, then `scripts/map_tiles.py --regions` for Ireland.
     The worker sends the world from its cache when it keeps one of the same zoom and major version of the tiles
     (docs/maps.md), and otherwise cuts it once from Protomaps and keeps it. If the world's run warns that regions are
     of another zoom or version (an Ireland from an earlier world), run `--refresh` rather than `--regions`. The files
     are the site's own, so nothing production does to its maps changes them.
   - Keep them as the baseline each reset restores:

         rsync -a --delete /opt/breedgraph-demo/map_tiles/ /opt/breedgraph-demo/dump/map_tiles/
         rsync -a --delete /opt/breedgraph-demo/map_boundaries/ /opt/breedgraph-demo/dump/map_boundaries/

     The world (560 MB) and Ireland (450 MB) are then on the disk twice, about 2 GB in all. To move the site to a newer
     build, fetch the world with `--fresh` and the regions with `--refresh`, and keep them again.
7. **BreedView.** `npm run build:demo` with `.env.demo.local` giving `VITE_BASE_PATH=/demo/` and
   `VITE_API_HOST=https://breedgraph.universityofgalway.ie/demo`, and its `dist-demo/` copied to `/var/www/demo`. The guide's
   media go in its `guide-media/` (from `public/guide-media`).
8. **nginx.** `nginx-breedgraph-demo.conf` to `/etc/nginx/snippets/breedgraph-demo.conf`, and
   `include snippets/breedgraph-demo.conf;` in production's server block for port 443, with the worker server's
   address in its `/demo/map_jobs/` location, for the site's map worker. Then `sudo nginx -t` and
   `sudo systemctl reload nginx`. Everything is inside one `^~ /demo/` location, so production's own locations,
   regular expressions too, take nothing of the site's. It sends `X-Robots-Tag: noindex`, so that search engines leave
   the site out.
9. **The units and the first load.** Copy the units, `sudo systemctl daemon-reload`, then
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

The map worker is on the worker server, outside the target: `sudo systemctl restart map-worker-demo` there, and its log
is `/var/log/map_worker/map-demo.log`. While the site is stopped or resetting, nginx answers its polls with 502: it
logs a warning when they start going unanswered (one for each of its two lanes, quick and extract), and a line when the
site's API answers again, and goes on.

Restarting the target restarts Redis too, which saves nothing: the read models (the countries, the ontology) are gone
until the next reset. Restart the API and the workers alone (`sudo systemctl restart breedgraph-demo
archive-worker-demo analysis-worker-demo`), or run the reset, which fills them again.

**Upgrades.** Update the site with production: pull the same version into `checkout/`, update its `.venv`, rebuild
BreedView's demonstration build, restart `map-worker-demo` on the worker server once production's map worker's venv
is upgraded, and run the reset, which restarts everything on the new code and checks the dump
loads, the accounts are set and the read models filled as each night. When the release changes the demonstration
database (`scripts/build_demo_database.py`) or its dump, copy the new dump into `dump/` first. An upgrade of the Neo4j
package upgrades both instances: run the reset afterwards, to check the dump still loads.

## Each night

`scripts/reset_demo.sh`, run by `breedgraph-demo-reset.service`:

1. Refuses to run outside the demonstration site: its env file must say `BREEDGRAPH_DEMO=1`, and name neither
   production's Neo4j port nor its Redis port. It reads the dump's parts from `DEMO_DUMP_DIR` (`neo4j.dump`,
   `files/`, `map_tiles/`, `map_boundaries/`), and refuses, before stopping anything, a dump without its files, or an
   env file of an earlier release naming a part elsewhere (`DEMO_FILES_DIR`, `DEMO_MAP_TILES_DIR`,
   `DEMO_MAP_BOUNDARIES_DIR`): move it into `DEMO_DUMP_DIR` and remove the setting.
2. Stops the target: the API, the workers, Neo4j and Redis.
3. Loads the dump with `neo4j-admin database load --overwrite-destination=true`, which replaces the store and its
   transaction logs, so what was entered is really gone.
4. Starts Neo4j and Redis, empties Redis, copies the dump's files over the file store, deleting the rest, and empties
   the archive worker's store. The dump's files wait to be archived, so the worker archives them again. It copies the
   dump's maps (`dump/map_tiles/`, `dump/map_boundaries/`) over the site's in the same way, deleting the regions
   visitors fetched. Without them it warns and goes on. Emptying Redis cancels the map worker's jobs, which it stops at their next renewal; the regions
   it kept stay in its cache.
5. Empties the site's erasure log, without replaying it: the people erased there were the site's, and are gone with it.
6. Rotates `SECRET_KEY`, so that no login cookie from before the reset signs in, as a restore reissues account ids.
7. Writes the site's legal texts (`legal-preamble.md` and the drafts in `docs/legal/`), loads the state store, sets the
   accounts (`scripts/set_demo_accounts.py`), and starts the target.

## Accounts

The story's accounts (dara, bridget, theo, lena and petra) get the site's passwords, and reviewers get accounts of their
own (`dpo-reviewer-1`, ...), both from the accounts file, after each reset. DPO staff who want to try registering are
invited from the app, as anyone joins BreedGraph, and those accounts go at the next reset, as the preamble says.

## Checks

- `https://breedgraph.universityofgalway.ie/demo/` shows the banner on every page, and production's site is unchanged.
- Signed in to production in the same browser, the demonstration site signs in and saves as it should, and production
  is still signed in afterwards (their cookies stay apart).
- Deep links (`/demo/guide/joining`) survive a reload: nginx falls back to the site's `index.html`.
- `/demo/guide-media/*.vtt` is served as `text/vtt`, and the videos answer range requests (206).
- The links in a verification email start `https://breedgraph.universityofgalway.ie/demo/`.
- An upload shows as archived within a minute, and an analysis runs.
- From the worker server, the site's map routes answer: `curl -s -o /dev/null -w '%{http_code}\n'
  https://<site>/demo/map_jobs/next/quick` prints 401, the site's API refusing a request without the token. A 403 is
  nginx refusing the worker server's address, a 200 nginx without the `/demo/map_jobs/` location (BreedView's page),
  and a 502 the site's API not running. Then the map worker's log shows no warning about its polls.
- The map shows Ireland in detail, and `/demo/tiles/world.pmtiles` answers range requests (206). Adding a country
  fetches its map through the site's map worker (`/var/log/map_worker/map-demo.log` on the worker server), and after
  the next reset its layer is gone from `/demo/tiles/tiles.json`.
- After a reset the story's state is the manifest's, and a login cookie from before it no longer signs in.

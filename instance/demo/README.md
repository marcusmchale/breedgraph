# The hosted demonstration site

A second BreedGraph beside production, on the same server, at https://breedgraph.universityofgalway.ie/demo/, for the
user guide's readers and for the DPO's and the legal office's review: the demonstration database (docs/demo-database.md), reset every night, with BreedView's demonstration
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
7. **BreedView.** `npm run build:demo` with `.env.demo.local` giving `VITE_BASE_PATH=/demo/` and
   `VITE_API_HOST=https://breedgraph.universityofgalway.ie/demo`, and its `dist-demo/` copied to `/var/www/demo`. The guide's
   media go in its `guide-media/` (from `public/guide-media`).
8. **nginx.** `nginx-breedgraph-demo.conf` to `/etc/nginx/snippets/breedgraph-demo.conf`, and
   `include snippets/breedgraph-demo.conf;` in production's server block for port 443, then `sudo nginx -t` and
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

- `https://breedgraph.universityofgalway.ie/demo/` shows the banner on every page, and production's site is unchanged.
- Signed in to production in the same browser, the demonstration site signs in and saves as it should, and production
  is still signed in afterwards (their cookies stay apart).
- Deep links (`/demo/guide/joining`) survive a reload: nginx falls back to the site's `index.html`.
- `/demo/guide-media/*.vtt` is served as `text/vtt`, and the videos answer range requests (206).
- The links in a verification email start `https://breedgraph.universityofgalway.ie/demo/`.
- An upload shows as archived within a minute, and an analysis runs.
- After a reset the story's state is the manifest's, and a login cookie from before it no longer signs in.

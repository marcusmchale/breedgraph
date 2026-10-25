# The hosted demonstration site

A second BreedGraph beside production, for the user guide's readers and for the DPO's and the legal office's review:
the demonstration database (docs/demo-database.md), reset every night, with BreedView's demonstration build, whose
banner says the site is fictional. It has its own Neo4j, Redis, API, analysis worker, files and logs, so nothing in it
touches production.

The files here are templates: copy each to the place its first line names, fill in what is in angle brackets, and keep
the private ones (mode 0600, owned by `breedgraph-demo`).

| File | Goes to | What it is |
|---|---|---|
| `breedgraph-demo.env` | `/opt/breedgraph-demo/breedgraph-demo.env` (private) | the API's, the worker's and the reset's environment |
| `neo4j.conf` | `/opt/breedgraph-demo/neo4j/conf/neo4j.conf` | the second Neo4j: its own directories and ports, authentication on |
| `redis-demo.conf` | `/etc/redis/redis-demo.conf` | the second Redis, on 6380 |
| `neo4j-demo.service`, `redis-demo.service`, `breedgraph-demo.service`, `analysis-worker-demo.service` | `/etc/systemd/system/` | the services |
| `breedgraph-demo-reset.service`, `breedgraph-demo-reset.timer` | `/etc/systemd/system/` | the nightly reset (`scripts/reset_demo.sh`) |
| `nginx-breedgraph-demo.conf` | `/etc/nginx/sites-available/breedgraph-demo` | the site: BreedView's build, the API, the tiles |
| `legal-preamble.md` | read from here by the reset | what the site's Terms and privacy notice say first |
| `demo_accounts.example.json` | `/opt/breedgraph-demo/private/demo_accounts.json` (private) | the site's passwords and reviewer accounts (`scripts/set_demo_accounts.py`) |

## The host name

Use a sibling of production's host name, such as `breedgraph-demo.universityofgalway.ie`, never a subdomain of it:
the API sets its CSRF cookie with `domain=HOST_ADDRESS` (`src/breedgraph/entrypoints/fastapi/security.py`), so a
subdomain would be sent production's cookies.

## Setting it up (the server work)

1. **Accounts and directories.** A `breedgraph-demo` system user, and `/opt/breedgraph-demo` owned by it, holding
   `checkout/` (a clone of breedgraph, with its `.venv` as production's), `neo4j/` (`conf`, `data`, `logs`, `run`,
   `import`), `dump/`, `files/`, `logs/`, `legal/`, `private/` (0700) and `map_tiles/`. The analysis worker runs as
   `analysisworker`, as production's does, from its own checkout or production's.
2. **Neo4j.** The same version as the machine the dump was built on (Community runs one database an instance, so this
   is a second instance of the installed package): `neo4j.conf` here, then set its initial password as the
   `breedgraph-demo` user, `NEO4J_CONF=/opt/breedgraph-demo/neo4j/conf neo4j-admin dbms set-initial-password <password>`,
   and put it in the env file.
3. **Redis.** `redis-demo.conf` and its service: port 6380, bound to 127.0.0.1, no persistence (the dump is the backup).
4. **The environment.** `breedgraph-demo.env`, with its own `SECRET_KEY` and salts (none shared with production), real
   SMTP, and `HOST_ADDRESS` the site's name.
5. **The dump.** Copy the build's `demo_database.dump` to `/opt/breedgraph-demo/dump/neo4j.dump` and its
   `demo_database_files/` to `/opt/breedgraph-demo/dump/files/`. The build's manifest holds its generated passwords:
   the site's own go in the accounts file instead.
6. **Map tiles.** The world file and Ireland's region into `/opt/breedgraph-demo/map_tiles`, cut on a machine with
   `pmtiles` (`scripts/map_tiles.py`), as `MAP_PMTILES_COMMAND` is empty here: the site fetches no regions itself.
7. **BreedView.** `npm run build:demo` with `.env.demo.local` giving `VITE_API_HOST=https://<the site's name>`, and the
   `dist/` copied to `/var/www/breedgraph-demo`. The guide's media go in its `guide-media/` (from `public/guide-media`).
8. **nginx, DNS and TLS.** The site's configuration, a certificate, and `X-Robots-Tag: noindex` (in the configuration),
   so that search engines leave it out.
9. **The first load.** `sudo /opt/breedgraph-demo/checkout/scripts/reset_demo.sh` does what the nightly reset does, then
   enable the timer: `systemctl enable --now breedgraph-demo-reset.timer`.

## Each night

`scripts/reset_demo.sh`, run by `breedgraph-demo-reset.service`:

1. Refuses to run outside the demonstration site: its env file must say `BREEDGRAPH_DEMO=1`.
2. Stops the API, the worker and Neo4j.
3. Loads the dump with `neo4j-admin database load --overwrite-destination=true`, which replaces the store and its
   transaction logs, so what was entered is really gone.
4. Starts Neo4j, empties Redis, and copies the dump's files over the file store, deleting the rest.
5. Empties the site's erasure log, without replaying it: the people erased there were the site's, and are gone with it.
6. Rotates `SECRET_KEY`, so that no login cookie from before the reset signs in, as a restore reissues account ids.
7. Writes the site's legal texts (`legal-preamble.md` and the drafts in `docs/legal/`), loads the state store, sets the
   accounts (`scripts/set_demo_accounts.py`), and starts the API and the worker.

## Accounts

The story's accounts (dara, bridget, theo, lena and petra) get the site's passwords, and reviewers get accounts of their
own (`dpo-reviewer-1`, ...), both from the accounts file, after each reset. DPO staff who want to try registering are
invited from the app, as anyone joins BreedGraph, and those accounts go at the next reset, as the preamble says.

## Checks

- Deep links (`/guide/joining`) survive a reload: nginx falls back to `index.html`.
- `/guide-media/*.vtt` is served as `text/vtt`, and the videos answer range requests (206).
- The banner shows on every page.
- After a reset the story's state is the manifest's, and a login cookie from before it no longer signs in.

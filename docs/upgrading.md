# Upgrading

What each release needs when a deployment is upgraded to it, besides the steps every upgrade takes
([deployment.md](deployment.md), Upgrading to a new release): its new settings, anything to do once, in order, and the
checks after. A release that needs nothing more says so. Upgrade one release at a time, or follow each release's
section in turn. Releases before v0.1.6 list theirs in their notes on GitHub.

The release's notes on GitHub link here; corrections found while deploying a release are made here, not in its notes.

## Unreleased

**Standard licences.** Setting up now seeds two standard licences, CC BY 4.0 and CC0 1.0, as legal references
without controls, which everyone can read and no one can change, and gives the ontology's first version CC BY 4.0
([licences.md](licences.md) §6). A database set up before needs them once, after the schema step (a new constraint,
on the references' seed keys), on the web server, from the release's checkout with the venv and environment:

    python scripts/apply_schema.py
    python scripts/seed_licences.py

The second creates only what is missing, and says which references the licences are. The ontology's next version then
takes CC BY 4.0, unless an ontology admin names another. The demonstration site's database is rebuilt for the release,
with them.

**ORCID linking without outbound access.** ORCID sign-in now gives the browser an id_token that ORCID signed, which
the API checks with ORCID's public key, carried by the release, rather than exchanging a code with `orcid.org`. So the
web server needs no access to ORCID, and linking can be turned on wherever a client is registered
([deployment.md](deployment.md), ORCID linking). The client secret is no longer used: delete `ORCID_CLIENT_SECRET`
from the API's env file, and from the demonstration site's. The client ID, `ORCID_BASE_URL` and the registered
redirect URI are as before. Once production's client is registered on `orcid.org`, set `ORCID_CLIENT_ID`,
`ORCID_BASE_URL="https://orcid.org"` and `ORCID_REDIRECT_URI`, and restart the API. A sign-in begun before the upgrade
fails and is started again.

## v0.1.7

**Cypher 25.** The queries are now written in Cypher 25, with no APOC, and the API refuses to start on a database
running another language. A database runs the language it was created with, whatever `db.query.default_language`
says, so one created before that was set runs Cypher 5, as production's does. Before restarting the API, once, as
Neo4j's admin (it asks for the password):

    cypher-shell -u neo4j -d system "SHOW DATABASES YIELD name, defaultLanguage WHERE name = 'neo4j'"
    cypher-shell -u neo4j -d system "ALTER DATABASE neo4j SET DEFAULT LANGUAGE CYPHER 25"

The first shows the language before, the second sets it; nothing else in the database changes, and it can be set back
the same way. The same for the demonstration site's Neo4j, with `-a neo4j://127.0.0.1:7688` and its password, if its
first command shows anything but `CYPHER 25` (its `neo4j.conf` has set it since the site was made). With
`db.query.default_language=CYPHER_25` in `/etc/neo4j/neo4j.conf` too, a database made later runs it from the start.
The APOC plugin and its allowlist are no longer used: they can stay, or go at the next restart of Neo4j.

**Detailed maps.** The API no longer emails whoever added a country about its maps: BreedView's location map says
where they stand instead (`locationsMapStatus`, [maps.md](maps.md)). Nothing to set. Redis keeps who asked for the
regions requested before the upgrade, which nothing reads now; delete them once, on the web server:

    redis-cli --scan --pattern 'map:requestors:*' | xargs -r redis-cli del
    redis-cli --scan --pattern 'map:notified:*' | xargs -r redis-cli del

The demonstration site's Redis is emptied by each reset, so it needs neither.

**The demonstration site's dump.** Its reset reads the dump's parts from `DEMO_DUMP_DIR` alone: `neo4j.dump`, the
files in `files/` and the maps in `map_tiles/` and `map_boundaries/`. `DEMO_FILES_DIR`, `DEMO_MAP_TILES_DIR` and
`DEMO_MAP_BOUNDARIES_DIR` are gone, and the reset refuses an env file still naming one of them elsewhere, before it
stops anything. Before the site's upgrade:

1. Where they all name folders inside `DEMO_DUMP_DIR`, as in the template, remove the three lines from
   `/opt/breedgraph-demo/breedgraph-demo.env`:

       sudo sed -i '/^DEMO_\(FILES\|MAP_TILES\|MAP_BOUNDARIES\)_DIR=/d' /opt/breedgraph-demo/breedgraph-demo.env

2. Where the maps' copy was put on a data disk ([v0.1.6](#v016), step 4), move the rest of the dump beside it and point
   `DEMO_DUMP_DIR` there, then remove the three lines as above. For a copy in `/data/breedgraph-demo/dump`:

       sudo -u breedgraph-demo mv /opt/breedgraph-demo/dump/neo4j.dump /opt/breedgraph-demo/dump/files /data/breedgraph-demo/dump/
       sudo sed -i 's|^DEMO_DUMP_DIR=.*|DEMO_DUMP_DIR="/data/breedgraph-demo/dump"|' /opt/breedgraph-demo/breedgraph-demo.env

   A new demonstration database goes into that folder from then on.

The site's upgrade ends with its reset as usual, which checks the dump and its files are where it reads them.

**Place search from GeoNames, without Nominatim.** Place searches on the location map are answered by the API from
its own copy of GeoNames' places ([maps.md](maps.md), Place search), so no search leaves our server and no third
party receives what anyone searches for: until now they went to Nominatim, the OpenStreetMap Foundation's service in
the United Kingdom. They are open to visitors. The countries offered for a new location tree come from GeoNames' list,
packaged with BreedGraph, rather than from a file of each deployment's. Upgrade the map workers with the API: an
older worker fails the new kind of job.

1. In the API's env file, remove `NOMINATIM_URL`, `GEOCODING_RATE_LIMIT_PER_HOUR` and `COUNTRY_CODES_PATH` (the
   country codes file it named can be deleted), and add `GAZETTEER_PATH`, a folder the API's user owns, on a disk with
   room (`/data/breedgraph/gazetteer`, say), and `GEONAMES_URL`: the template's where the API fetches for itself, or
   empty with `MAP_WORKER=1`.
2. In each map worker's env file, `GEONAMES_URL` as in `instance/map_worker.env`. The worker server must reach
   `download.geonames.org`. The worker keeps the files in its cache, and sends them again until asked for them fresh.
3. Where `PRIVACY_NOTICE_PATH` names a copy of the privacy notice, copy the release's `src/breedgraph/legal/privacy_notice.md`
   over it: its "Maps and place search" section says searches are answered on our server. It has a new hash, which
   accounts registering from then on record with their consent.
4. After the restart, the API fetches the world's towns and the places of every country in the location trees by
   itself, in a few minutes: its log says "Loaded … towns" and "Loaded … places of IRL". Later,
   `scripts/map_tiles.py --gazetteer --fresh` downloads them anew rather than take what the map worker keeps.

The demonstration site: set `GAZETTEER_PATH` in its env file (beside its maps, `/data/breedgraph-demo/gazetteer`, say)
and `GEONAMES_URL=""`. Each reset deletes its places' database, and its API fetches the world's and Ireland's again as
it starts, from the cache of the map worker it shares with production.

**ORCID linking** is offered on the profile only where the API's ORCID client is configured (`ORCID_CLIENT_ID` and
`ORCID_CLIENT_SECRET`), and elsewhere the profile says it isn't available on the site, as on the demonstration site.
Where the credentials are set but the web server can't yet reach `orcid.org`, comment out `ORCID_CLIENT_ID` until it
can, or linking is offered and fails at its last step. (The next release needs no access to `orcid.org`: Unreleased,
above.)

**The map workers' logs** say once when the API stops answering, each hour while it doesn't, and when it answers again,
rather than at each poll: nothing to do.

**BreedView's mark.** BreedView has a favicon of its own and its mark before its name in the header, in the header's
text colour. A branding's `favicon` still replaces it (BreedView's README, Branding): remove it from the branding's
`branding.json` for BreedView's.

Nothing to do for the rest: the emails telling admins of a request or an offer say what awaits and where, no longer
who asked ([person.md](person.md)); the map's credit links OpenStreetMap's copyright page, `tiles.json` being written
anew as the API starts; and BreedView's builds carry `licenses.txt`, the licences of the code they bundle, which its
footer links to.

## v0.1.6

**The demonstration site's map worker, and a cache of maps on the worker server** (the release's notes). After the
usual upgrade, once:

1. **Worker server, the folders.** The work paths and the cache, on the large disk and on one filesystem:

       sudo mkdir -p /srv/map_worker/work /srv/map_worker/work-demo /srv/map_worker/cache
       sudo chown -R mapworker:mapworker /srv/map_worker
       stat -c %d /srv/map_worker/work /srv/map_worker/work-demo /srv/map_worker/cache

   The three numbers must be the same, or the worker refuses to start: it moves what it cuts into the cache. Where the
   large disk is mounted elsewhere, such as a ZFS pool at `/pool`, make the three there instead (e.g.
   `/pool/breedgraph/map_worker/...`, mode 700), use those paths below, and change the `ReadWritePaths` of
   `instance/map_worker.service` and `instance/demo/map-worker-demo.service` to their folder before installing them.
2. **Worker server, production's map worker.** In `/opt/map_worker/map_worker.env`,
   `MAP_WORK_PATH="/srv/map_worker/work"` and `MAP_CACHE_PATH="/srv/map_worker/cache"`. Install the release's
   `instance/map_worker.service`, whose `ReadWritePaths` holds `/srv/map_worker`, then
   `sudo systemctl daemon-reload` and `sudo systemctl restart map_worker`: the line starting the worker in
   `/var/log/map_worker/map.log` names the cache. Remove its old work folder, which it no longer uses.
3. **Web server, nginx.** Install the release's `instance/demo/nginx-breedgraph-demo.conf` as
   `/etc/nginx/snippets/breedgraph-demo.conf`, with its `/demo/map_jobs/` block uncommented and the worker server's
   address in it ([deployment.md](deployment.md), nginx; compare it with the installed one first: `diff`). Then
   `sudo nginx -t && sudo systemctl reload nginx`. From any other machine,
   `curl -s -o /dev/null -w '%{http_code}\n' https://<site>/demo/map_jobs/next/quick` gives 403.
4. **Web server, the demonstration site's env and maps.** A new token, made into a file only you can read, so that it
   is never printed, and the settings, in `/opt/breedgraph-demo/breedgraph-demo.env` (keeping
   `MAP_PMTILES_COMMAND=""`; check first with `sudo grep -oE '^(MAP|DEMO_MAP)[A-Z_]*'` that none is there already):

       (umask 077; printf 'MAP_WORKER_AUTH_TOKEN="%s"\n' "$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')" > ~/demo_map_token.env)

       MAP_WORKER=1
       MAP_WORKER_AUTH_TOKEN=...  (from the file: sudo tee -a <env file> < ~/demo_map_token.env)
       MAP_JOB_LEASE_SECONDS=300
       MAP_TILES_MAX_GB=10
       DEMO_MAP_TILES_DIR="/opt/breedgraph-demo/dump/map_tiles"
       DEMO_MAP_BOUNDARIES_DIR="/opt/breedgraph-demo/dump/map_boundaries"

   and `sudo -u breedgraph-demo mkdir -p /opt/breedgraph-demo/map_boundaries`. The site's maps take up to
   `MAP_TILES_MAX_GB` and its snapshot about 2 GB more: where `/opt` is on the system disk, beside production's Neo4j,
   put them on a data disk instead. Copy `map_tiles/` and `map_boundaries/` there with `rsync -a` as
   `breedgraph-demo`, point `MAP_TILES_PATH`, `MAP_BOUNDARIES_PATH` and the two `DEMO_MAP_*` settings at them (e.g.
   `/data/breedgraph-demo/map_tiles` and `/data/breedgraph-demo/dump/map_tiles`), and the nginx snippet's two tile
   `alias` lines too. Then upgrade the site as usual (`instance/demo/README.md`, Upgrades). Its reset says there are
   no maps in the snapshot yet, which is expected, and the site's log says "Detailed maps are fetched by the map
   worker".
5. **Worker server, the site's map worker.** Copy the token over (`scp -3 <web server>:demo_map_token.env <worker>:`,
   then `shred -u` it on the web server). `instance/demo/map-worker-demo.env` to `/opt/map_worker/` (mode 0600, owned
   by root, as `map_worker.env`), with `API_URL` the site's address followed by `/demo` (`https://<site>/demo`), its
   paths, and the token
   appended from the copied file (`sudo tee -a`), which is then shredded. Check the route from here:
   `curl -s -o /dev/null -w '%{http_code}\n' <API_URL>/map_jobs/next/quick` gives 401 (the site's API refusing a
   request without the token); 403 is nginx refusing this server's address, 404 or 200 nginx without the location, 502
   the site's API down. Then `instance/demo/map-worker-demo.service` to `/etc/systemd/system/`,
   `sudo systemctl daemon-reload && sudo systemctl enable --now map-worker-demo`, and its log,
   `/var/log/map_worker/map-demo.log`, shows it started with no warning after it.
6. **The site's maps.** Its world file was a link to production's, and Ireland copied by hand. Fetch its own through
   its worker, as `breedgraph-demo` from its checkout with its environment:

       sudo -u breedgraph-demo bash -c 'cd /opt/breedgraph-demo/checkout && set -a && . /opt/breedgraph-demo/breedgraph-demo.env && set +a && .venv/bin/python scripts/map_tiles.py'

   With an empty cache it is cut once from Protomaps (about 560 MB, under a minute on the University's servers) and
   kept. Then the same with `scripts/map_tiles.py --regions`, or `--refresh` if the world's run warned that regions are
   of another zoom or version. Check no link is left (`sudo find <MAP_TILES_PATH> -type l` prints nothing), and keep
   them as the baseline each reset restores:

       sudo -u breedgraph-demo rsync -a --delete <MAP_TILES_PATH>/ <DEMO_MAP_TILES_DIR>/
       sudo -u breedgraph-demo rsync -a --delete <MAP_BOUNDARIES_PATH>/ <DEMO_MAP_BOUNDARIES_DIR>/

   The world and Ireland are then on the disk twice, about 2 GB in all.
7. **The reset, once more:** `sudo /opt/breedgraph-demo/checkout/scripts/reset_demo.sh`, which now prints no "No maps"
   line. While it runs, the site's map worker logs that its polls get 502: expected, as the site's API is stopped.

**Analyses.** The analysis workers' fixes take effect once the worker server's analysis worker, and the demonstration
site's, run v0.1.6, as in the usual upgrade.

**Checks**

- The site's map shows Ireland in detail, and `/demo/tiles/world.pmtiles` answers range requests (206).
- On the site, adding a small country (the Isle of Man, 9 MB) fetches its map through the site's worker
  (`map-demo.log`). Removed and added again, it is sent from the cache, with no second extract. After the next reset
  its layer is gone from `/demo/tiles/tiles.json`.
- On production, a country removed and added again is sent from the cache (`map.log`), and the cache holds it.

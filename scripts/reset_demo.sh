#!/usr/bin/env bash
# Reset the hosted demonstration site to its dump (instance/demo/README.md, Each night): stop its services, load the
# dump over the store (its transaction logs too, so what was entered is gone), empty Redis, copy the dump's files over
# the file store and its maps over the site's, empty the archive worker's store and the site's erasure log, rotate
# SECRET_KEY so that no login cookie from before signs in, write the site's legal texts, load the state store, set the
# accounts (scripts/set_demo_accounts.py), and start the services.
#
#   sudo scripts/reset_demo.sh /opt/breedgraph-demo/breedgraph-demo.env
#
# The dump is DEMO_DUMP_DIR: neo4j.dump, the file store's files in files/, and the site's maps in map_tiles/ and
# map_boundaries/ (instance/demo/README.md, Setting it up).
#
# Run as root, by breedgraph-demo-reset.service each night: it stops and starts the site's services (its systemd target,
# instance/demo/breedgraph-demo.target), and runs the rest as breedgraph-demo. It refuses an env file that is not the demonstration site's (BREEDGRAPH_DEMO=1) or that points at
# production's Neo4j or Redis. With DRY_RUN=1 it prints what it would do, and runs nothing.
set -euo pipefail

ENV_FILE="${1:-/opt/breedgraph-demo/breedgraph-demo.env}"
refuse() { echo "Refused: $*" >&2; exit 1; }
[ -f "$ENV_FILE" ] || refuse "no env file $ENV_FILE"
set -a; . "$ENV_FILE"; set +a

# 1. Only the demonstration site
[ "${BREEDGRAPH_DEMO:-}" = 1 ] || refuse "$ENV_FILE does not say BREEDGRAPH_DEMO=1"
[ "${DB_PORT:-7687}" != 7687 ] || refuse "$ENV_FILE points at production's Neo4j (7687)"
[ "${REDIS_PORT:-6379}" != 6379 ] || refuse "$ENV_FILE points at production's Redis (6379)"
for name in DEMO_ROOT DEMO_DUMP_DIR DEMO_ACCOUNTS DEMO_CHECKOUT DEMO_ARCHIVE_DIR NEO4J_PACKAGE \
    FILE_STORAGE_PATH PERSON_ERASURE_LOG_PATH TERMS_OF_USE_PATH PRIVACY_NOTICE_PATH; do
  [ -n "${!name:-}" ] || refuse "$ENV_FILE sets no $name"
done
DEMO_DUMP_DIR="${DEMO_DUMP_DIR%/}"
DUMP_FILES="$DEMO_DUMP_DIR/files"
DUMP_MAP_TILES="$DEMO_DUMP_DIR/map_tiles"
DUMP_MAP_BOUNDARIES="$DEMO_DUMP_DIR/map_boundaries"
# Earlier releases named the dump's folders one by one: an env file naming one elsewhere is refused, before anything is
# stopped, rather than the reset leaving out what is there
declare -A DUMP_PARTS=([DEMO_FILES_DIR]="$DUMP_FILES" [DEMO_MAP_TILES_DIR]="$DUMP_MAP_TILES" \
  [DEMO_MAP_BOUNDARIES_DIR]="$DUMP_MAP_BOUNDARIES")
for name in "${!DUMP_PARTS[@]}"; do
  if [ -n "${!name:-}" ] && [ "${!name%/}" != "${DUMP_PARTS[$name]}" ]; then
    refuse "$ENV_FILE sets $name to ${!name}, but the reset reads ${DUMP_PARTS[$name]}: move it there and remove" \
      "the setting (instance/demo/README.md, Upgrades)"
  fi
done
[ -f "$DEMO_DUMP_DIR/neo4j.dump" ] || refuse "no dump at $DEMO_DUMP_DIR/neo4j.dump"
[ -d "$DUMP_FILES" ] || refuse "no files at $DUMP_FILES"
[ -f "$DEMO_ACCOUNTS" ] || refuse "no accounts file at $DEMO_ACCOUNTS"
DEMO_USER="${DEMO_USER:-breedgraph-demo}"
TARGET="${DEMO_TARGET:-breedgraph-demo.target}"

run() {
  if [ "${DRY_RUN:-}" = 1 ]; then echo "+ $*"; else "$@"; fi
}
# as the site's user, with its environment and from its checkout
as_demo() { run runuser -u "$DEMO_USER" -- env -C "$DEMO_CHECKOUT" "$@"; }
if [ "${DRY_RUN:-}" != 1 ] && [ "$(id -u)" != 0 ]; then refuse "run as root: it stops and starts the site's services"; fi

# 2. Stop the site: every service of its target
echo "Stopping $TARGET"
run systemctl stop "$TARGET"

# 3. The dump over the store
echo "Loading $DEMO_DUMP_DIR/neo4j.dump"
as_demo NEO4J_HOME="$DEMO_ROOT/neo4j" NEO4J_CONF="$DEMO_ROOT/neo4j/conf" \
  "$NEO4J_PACKAGE/bin/neo4j-admin" database load neo4j --from-path="$DEMO_DUMP_DIR" --overwrite-destination=true

# 4. Neo4j and Redis started, Redis emptied, the files copied, the archive worker's copies of them deleted (the dump's
# files wait to be archived, and are again), and the maps restored
run systemctl start neo4j-demo redis-demo
echo "Waiting for Neo4j on $DB_PORT"
as_demo .venv/bin/python - <<'EOF'
import os, time
from neo4j import GraphDatabase
for _ in range(90):
    try:
        with GraphDatabase.driver(f"neo4j://127.0.0.1:{os.environ['DB_PORT']}",
                                  auth=(os.environ['NEO4J_USERNAME'], os.environ['NEO4J_PASSWORD'])) as driver:
            driver.execute_query("RETURN 1", database_=os.environ.get('DATABASE_NAME') or 'neo4j')
        break
    except Exception:
        time.sleep(2)
else:
    raise SystemExit("Neo4j did not answer")
EOF
run redis-cli -h 127.0.0.1 -p "$REDIS_PORT" flushall
as_demo mkdir -p "$FILE_STORAGE_PATH"
as_demo rsync -a --delete "$DUMP_FILES"/ "$FILE_STORAGE_PATH"/
as_demo find "$DEMO_ARCHIVE_DIR" -mindepth 1 -delete
# The dump's maps (the site's world file, Ireland's region and tiles.json) over the site's, deleting the regions
# visitors fetched. Without them, or without the settings naming the site's, the reset goes on: the site works without
# detailed maps, and a reset that stopped would leave the day's visitors' data in place.
if [ -z "${MAP_TILES_PATH:-}" ] || [ -z "${MAP_BOUNDARIES_PATH:-}" ]; then
  echo "No maps restored: $ENV_FILE does not set MAP_TILES_PATH and MAP_BOUNDARIES_PATH"
elif [ -d "$DUMP_MAP_TILES" ] && [ -d "$DUMP_MAP_BOUNDARIES" ]; then
  as_demo rsync -a --delete "$DUMP_MAP_TILES"/ "$MAP_TILES_PATH"/
  as_demo rsync -a --delete "$DUMP_MAP_BOUNDARIES"/ "$MAP_BOUNDARIES_PATH"/
else
  echo "No maps in $DUMP_MAP_TILES and $DUMP_MAP_BOUNDARIES: the site's are left as they are"
fi
# The place search's database deleted, with the places of countries visitors added: as it starts, the API fetches the
# world's and those of the dump's countries again, through the site's map worker, from the cache that keeps them
# (docs/maps.md, Place search)
if [ -z "${GAZETTEER_PATH:-}" ]; then
  echo "No places reset: $ENV_FILE does not set GAZETTEER_PATH"
else
  as_demo find "$GAZETTEER_PATH" -maxdepth 1 -name 'gazetteer.sqlite*' -delete
fi

# 5. The site's erasure log emptied, not replayed: the people erased on the site went with its data
as_demo truncate -s 0 "$PERSON_ERASURE_LOG_PATH"

# 6. A new SECRET_KEY: a restore reissues account ids, so a cookie signed with the old key could sign in as another
echo "Rotating SECRET_KEY"
SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
# as the site's user, as sed -i writes a new file, which must stay its own
as_demo sed -i "s|^SECRET_KEY=.*|SECRET_KEY=\"$SECRET_KEY\"|" "$ENV_FILE"
export SECRET_KEY

# 7. The legal texts (the preamble, then the drafts under review), the state store, the accounts, and the site started
as_demo mkdir -p "$(dirname "$TERMS_OF_USE_PATH")" "$(dirname "$PRIVACY_NOTICE_PATH")"
as_demo sh -c "cat instance/demo/legal-preamble.md docs/legal/terms-of-use.md > '$TERMS_OF_USE_PATH'"
as_demo sh -c "cat instance/demo/legal-preamble.md docs/legal/privacy-notice.md > '$PRIVACY_NOTICE_PATH'"
as_demo .venv/bin/python scripts/load_state_store.py
as_demo .venv/bin/python scripts/set_demo_accounts.py --accounts "$DEMO_ACCOUNTS"
run systemctl start "$TARGET"
echo "The demonstration site is reset"

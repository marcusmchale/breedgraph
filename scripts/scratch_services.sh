#!/usr/bin/env bash
# Throwaway Neo4j and Redis, run as the user from the packaged Neo4j, with everything in a scratch directory: to build
# a database from a fresh store (the demonstration database, docs/demo-database.md, or the public test database) and
# dump it without sudo, and to load a dump for recordings or tests without touching the development database.
# A fresh store holds no transaction logs or deleted records from earlier writes, so its dumps can be shared.
#
# Usage: SCRATCH=<dir> scripts/scratch_services.sh <command>
#   init                        remove and recreate the scratch directory's stores, and write Neo4j's configuration
#   start | stop | status       the two services (Neo4j on SCRATCH_DB_PORT, default 7688; Redis on SCRATCH_REDIS_PORT,
#                               default 6380), bound to 127.0.0.1
#   env                         print the environment that points breedgraph at them, for eval after loading the
#                               instance environment: eval "$(scripts/scratch_services.sh env)"
#   build <dump> -- <command>   init, start, run the command with that environment, then stop and dump the database to
#                               <dump> (neo4j-admin's format)
#   load <dump> [<files dir>]   replace the database with a dump, empty Redis and load the state store, and copy the
#                               dump's files into the scratch file store
#
# The instance environment must be loaded for build and load (set -a; . instance/breedgraph.env;
# . instance/private.breedgraph.env; set +a): the command and scripts/load_state_store.py read it.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"
NEO4J_PACKAGE="${NEO4J_PACKAGE:-/usr/share/neo4j}"
NEO4J_PLUGINS="${NEO4J_PLUGINS:-/var/lib/neo4j/plugins}"
NEO4J_LOG_CONFIGS="${NEO4J_LOG_CONFIGS:-/etc/neo4j}"
DB_PORT_SCRATCH="${SCRATCH_DB_PORT:-7688}"
HTTP_PORT_SCRATCH="${SCRATCH_HTTP_PORT:-7475}"
REDIS_PORT_SCRATCH="${SCRATCH_REDIS_PORT:-6380}"

: "${SCRATCH:?Set SCRATCH to the scratch directory}"
SCRATCH="$(mkdir -p "$SCRATCH" && cd "$SCRATCH" && pwd)"
case "$SCRATCH" in
  /|"$HOME"|"$ROOT"|"$ROOT"/*) echo "Refusing SCRATCH=$SCRATCH: use a directory of its own" >&2; exit 1 ;;
esac
if [ "$DB_PORT_SCRATCH" = 7687 ] || [ "$REDIS_PORT_SCRATCH" = 6379 ]; then
  echo "Refusing the default ports (7687, 6379): they are the development services'" >&2; exit 1
fi

NEO4J_HOME_SCRATCH="$SCRATCH/neo4j"
NEO4J_CONF_SCRATCH="$SCRATCH/neo4j/conf"
NEO4J_PID="$SCRATCH/neo4j/run/console.pid"

neo4j_env() { NEO4J_HOME="$NEO4J_HOME_SCRATCH" NEO4J_CONF="$NEO4J_CONF_SCRATCH" "$@"; }
port_in_use() { ss -ltn "( sport = :$1 )" 2>/dev/null | grep -q LISTEN; }
# Neo4j's processes: the launcher started (its pid recorded, as it names no scratch path) and the server it starts,
# which names the scratch directory on its command line; never the development instance's
neo4j_processes() {
  local launcher
  launcher="$(cat "$NEO4J_PID" 2>/dev/null || true)"
  if [ -n "$launcher" ] && ps -o args= -p "$launcher" 2>/dev/null | grep -q 'neo4j'; then echo "$launcher"; fi
  pgrep -f -- "$NEO4J_HOME_SCRATCH/" || true
}
neo4j_running() { [ -n "$(neo4j_processes)" ]; }
redis_running() { redis-cli -p "$REDIS_PORT_SCRATCH" ping >/dev/null 2>&1; }

print_env() {
  cat <<EOF
export DB_HOST=127.0.0.1 DB_PORT=$DB_PORT_SCRATCH REDIS_HOST=127.0.0.1 REDIS_PORT=$REDIS_PORT_SCRATCH DATABASE_NAME=neo4j
export FILE_STORAGE_PATH="$SCRATCH/file_store" LOG_BASE="$SCRATCH/app_logs"
export PERSON_ERASURE_LOG_PATH="$SCRATCH/person_erasure_log.jsonl" MAP_PMTILES_COMMAND=
EOF
}

init() {
  if neo4j_running || redis_running; then echo "Stop the services first" >&2; exit 1; fi
  rm -rf "${SCRATCH:?}/neo4j" "${SCRATCH:?}/redis" "${SCRATCH:?}/file_store" "${SCRATCH:?}/app_logs" "${SCRATCH:?}/dump"
  rm -f "${SCRATCH:?}/person_erasure_log.jsonl"
  mkdir -p "$NEO4J_CONF_SCRATCH" "$SCRATCH"/neo4j/{data,logs,run,import,tmp} "$SCRATCH"/{redis,file_store,app_logs,dump}
  cp "$NEO4J_LOG_CONFIGS/server-logs.xml" "$NEO4J_LOG_CONFIGS/user-logs.xml" "$NEO4J_CONF_SCRATCH/"
  # as the development configuration (/etc/neo4j/neo4j.conf), with authentication off: it listens on 127.0.0.1 only
  cat > "$NEO4J_CONF_SCRATCH/neo4j.conf" <<EOF
db.query.default_language=CYPHER_25
server.directories.data=$SCRATCH/neo4j/data
server.directories.plugins=$NEO4J_PLUGINS
server.directories.logs=$SCRATCH/neo4j/logs
server.directories.lib=$NEO4J_PACKAGE/lib
server.directories.run=$SCRATCH/neo4j/run
server.directories.import=$SCRATCH/neo4j/import
server.logs.config=$NEO4J_CONF_SCRATCH/server-logs.xml
server.logs.user.config=$NEO4J_CONF_SCRATCH/user-logs.xml
server.default_listen_address=127.0.0.1
server.bolt.enabled=true
server.bolt.listen_address=127.0.0.1:$DB_PORT_SCRATCH
server.bolt.advertised_address=127.0.0.1:$DB_PORT_SCRATCH
server.http.enabled=true
server.http.listen_address=127.0.0.1:$HTTP_PORT_SCRATCH
server.https.enabled=false
dbms.security.auth_enabled=false
server.memory.heap.initial_size=1g
server.memory.heap.max_size=2g
server.memory.pagecache.size=1g
server.jvm.additional=-XX:+UseG1GC
server.jvm.additional=--add-opens=java.base/java.nio=ALL-UNNAMED
server.jvm.additional=--add-opens=java.base/java.io=ALL-UNNAMED
server.jvm.additional=--add-opens=java.base/sun.nio.ch=ALL-UNNAMED
server.jvm.additional=--add-opens=java.base/java.util.concurrent=ALL-UNNAMED
server.jvm.additional=--enable-native-access=ALL-UNNAMED
server.jvm.additional=-Djava.io.tmpdir=$SCRATCH/neo4j/tmp
EOF
  echo "Initialised $SCRATCH"
}

wait_for_neo4j() {
  for _ in $(seq 1 90); do
    if "$PYTHON" - "$DB_PORT_SCRATCH" <<'EOF' 2>/dev/null
import sys
from neo4j import GraphDatabase
with GraphDatabase.driver(f"neo4j://127.0.0.1:{sys.argv[1]}") as driver:
    driver.execute_query("RETURN 1", database_="neo4j")
EOF
    then return 0; fi
    neo4j_running || { echo "Neo4j stopped; see $SCRATCH/neo4j/logs/console.log" >&2; exit 1; }
    sleep 2
  done
  echo "Neo4j did not answer on $DB_PORT_SCRATCH" >&2; exit 1
}

start() {
  [ -f "$NEO4J_CONF_SCRATCH/neo4j.conf" ] || { echo "Run init first" >&2; exit 1; }
  if ! neo4j_running; then
    if port_in_use "$DB_PORT_SCRATCH"; then echo "Port $DB_PORT_SCRATCH is in use" >&2; exit 1; fi
    # exec, so the process started is Neo4j's own
    ( cd "$SCRATCH" && NEO4J_HOME="$NEO4J_HOME_SCRATCH" NEO4J_CONF="$NEO4J_CONF_SCRATCH" \
        exec nohup "$NEO4J_PACKAGE/bin/neo4j" console > "$SCRATCH/neo4j/logs/console.log" 2>&1 ) &
    echo $! > "$NEO4J_PID"
  fi
  if ! redis_running; then
    if port_in_use "$REDIS_PORT_SCRATCH"; then echo "Port $REDIS_PORT_SCRATCH is in use" >&2; exit 1; fi
    redis-server --port "$REDIS_PORT_SCRATCH" --bind 127.0.0.1 --save "" --appendonly no --dir "$SCRATCH/redis" \
      --daemonize yes --pidfile "$SCRATCH/redis/redis.pid" --logfile "$SCRATCH/redis/redis.log"
  fi
  wait_for_neo4j
  for _ in $(seq 1 30); do redis_running && break; sleep 1; done
  redis_running || { echo "Redis did not answer on $REDIS_PORT_SCRATCH" >&2; exit 1; }
  echo "Neo4j on 127.0.0.1:$DB_PORT_SCRATCH, Redis on 127.0.0.1:$REDIS_PORT_SCRATCH"
}

stop_neo4j() {
  local pids; pids="$(neo4j_processes)"
  if [ -n "$pids" ]; then
    # shellcheck disable=SC2086
    kill -TERM $pids 2>/dev/null || true
    # the store is in use until every one has exited, not just when the port closes
    for _ in $(seq 1 120); do neo4j_running || break; sleep 1; done
    if neo4j_running; then echo "Neo4j did not stop: $(neo4j_processes | tr '\n' ' ')" >&2; exit 1; fi
  fi
  rm -f "$NEO4J_PID"
}

stop() {
  stop_neo4j
  if redis_running; then redis-cli -p "$REDIS_PORT_SCRATCH" shutdown nosave >/dev/null 2>&1 || true; fi
  echo "Stopped"
}

status() {
  neo4j_running && echo "Neo4j running (pids $(neo4j_processes | tr '\n' ' ')) on $DB_PORT_SCRATCH" || echo "Neo4j stopped"
  redis_running && echo "Redis running on $REDIS_PORT_SCRATCH" || echo "Redis stopped"
}

build() {
  local dump="${1:?build needs the dump path}"; shift
  [ "${1:-}" = "--" ] || { echo "Usage: build <dump> -- <command>" >&2; exit 1; }
  shift
  [ $# -gt 0 ] || { echo "build needs a command after --" >&2; exit 1; }
  [ -e "$dump" ] && { echo "$dump exists: remove it or choose another path" >&2; exit 1; }
  init
  start
  ( eval "$(print_env)"; "$@" )
  stop_neo4j
  neo4j_env "$NEO4J_PACKAGE/bin/neo4j-admin" database dump neo4j --to-path="$SCRATCH/dump" --overwrite-destination=true
  mkdir -p "$(dirname "$dump")"
  mv "$SCRATCH/dump/neo4j.dump" "$dump"
  if redis_running; then redis-cli -p "$REDIS_PORT_SCRATCH" shutdown nosave >/dev/null 2>&1 || true; fi
  echo "Dumped to $dump"
}

load() {
  local dump="${1:?load needs the dump path}" files="${2:-}"
  [ -f "$dump" ] || { echo "No dump at $dump" >&2; exit 1; }
  [ -f "$NEO4J_CONF_SCRATCH/neo4j.conf" ] || init
  stop_neo4j
  rm -rf "${SCRATCH:?}/dump" && mkdir -p "$SCRATCH/dump"
  # neo4j-admin loads <path>/<database>.dump
  ln -s "$(cd "$(dirname "$dump")" && pwd)/$(basename "$dump")" "$SCRATCH/dump/neo4j.dump"
  neo4j_env "$NEO4J_PACKAGE/bin/neo4j-admin" database load neo4j --from-path="$SCRATCH/dump" --overwrite-destination=true
  start
  redis-cli -p "$REDIS_PORT_SCRATCH" flushall >/dev/null
  ( eval "$(print_env)"; cd "$ROOT"; "$PYTHON" scripts/load_state_store.py )
  if [ -n "$files" ]; then
    mkdir -p "$SCRATCH/file_store"
    rsync -a --delete "$files"/ "$SCRATCH/file_store"/
  fi
  : > "$SCRATCH/person_erasure_log.jsonl"
  echo "Loaded $dump"
}

command="${1:-}"; shift || true
case "$command" in
  init) init ;;
  start) start ;;
  stop) stop ;;
  status) status ;;
  env) print_env ;;
  build) build "$@" ;;
  load) load "$@" ;;
  *) sed -n '2,21p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 1 ;;
esac

#!/usr/bin/env bash
# Build breedgraph's wheel and the wheelhouses its services install from, offline: the API's (the server extra), the
# archive worker's (worker) and the analysis worker's (analysis_worker), in dist/ as wheelhouse_<extra>_<version>,
# beside the wheel and the source distribution (README.md, deploy).
#
# Usage: scripts/build_wheelhouses.sh [--check] [<ref>]     (<ref> defaults to HEAD)
#
# The wheel is built from <ref> as committed, so nothing uncommitted goes in. The wheels are for CPython 3.12 on x86_64
# with glibc 2.34 or later (the servers'; GLIBC_MINOR for another floor), whatever machine builds them. rpy2 3.5 has no
# wheels, so the analysis worker's wheelhouse holds its source and what building it needs, and the analysis worker's
# machine builds it as it installs, with R's headers and a C compiler.
#
# --check then installs each wheelhouse offline into a new venv, as a server does, and imports the API and the workers
# with <ref>'s instance/ templates for their environments. It needs python3.12 here (PYTHON312 for another), and for
# the analysis worker, which builds rpy2 and sources models.R, R with its packages (instance/analysis_worker.service).
set -euo pipefail
CHECK=false
if [ "${1:-}" = --check ]; then CHECK=true; shift; fi
REF=${1:-HEAD}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
PY=${PYTHON:-$ROOT/.venv/bin/python}
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

git -C "$ROOT" archive "$REF" | tar -x -C "$WORK/"
VERSION=$("$PY" -c 'import sys, tomllib; print(tomllib.load(open(sys.argv[1], "rb"))["project"]["version"])' \
  "$WORK/pyproject.toml")
mkdir -p "$ROOT/dist"
"$PY" -m build --outdir "$ROOT/dist" "$WORK" > "$WORK/build.log" 2>&1 || { cat "$WORK/build.log"; exit 1; }
WHEEL=$ROOT/dist/breedgraph-$VERSION-py3-none-any.whl

# pip takes each platform tag as given, so every manylinux tag up to the floor is listed
TARGET=(--only-binary=:all: --implementation cp --python-version 3.12)
for minor in $(seq "${GLIBC_MINOR:-34}" -1 5); do TARGET+=(--platform "manylinux_2_${minor}_x86_64"); done
TARGET+=(--platform manylinux2014_x86_64 --platform manylinux2010_x86_64 --platform manylinux1_x86_64)
DOWNLOAD=("$PY" -m pip download --quiet --disable-pip-version-check)
house () { echo "$ROOT/dist/wheelhouse_$1_$VERSION"; }

for extra in server worker; do
  rm -rf "$(house "$extra")"
  "${DOWNLOAD[@]}" "${TARGET[@]}" --dest "$(house "$extra")" "$WHEEL[$extra]"
done

# the analysis worker's extra as wheels but rpy2, then rpy2 3.5's requirements and build requirements, and its source
requirements () {
  unzip -p "$WHEEL" "breedgraph-$VERSION.dist-info/METADATA" \
    | sed -n 's/^Requires-Dist: \(.*\); extra == "analysis-worker"$/\1/p'
}
ANALYSIS=$(house analysis_worker)
rm -rf "$ANALYSIS"; mkdir -p "$ANALYSIS"; cp "$WHEEL" "$ANALYSIS/"
mapfile -t WHEELS < <(requirements | grep -v '^rpy2')
"${DOWNLOAD[@]}" "${TARGET[@]}" --dest "$ANALYSIS" "${WHEELS[@]}" "cffi>=1.15.1" jinja2 tzlocal "setuptools>=61" wheel
"${DOWNLOAD[@]}" --no-deps --no-binary=:all: --dest "$ANALYSIS" "$(requirements | grep '^rpy2')"

if $CHECK; then
  for extra in server worker analysis_worker; do
    "${PYTHON312:-python3.12}" -m venv "$WORK/venv_$extra"
    "$WORK/venv_$extra/bin/python" -m pip install --quiet --disable-pip-version-check --no-index \
      --find-links "$(house "$extra")" "breedgraph[$extra]"
  done
  check () {  # <extra> <env file> <code>
    ( set -a; . "$WORK/instance/$2"; LOG_BASE=$WORK; set +a
      cd "$WORK" && "$WORK/venv_$1/bin/python" -I -c "$3" )
  }
  check server breedgraph.env 'import breedgraph.main'
  check worker archive_worker.env 'import archive_worker.main'
  check analysis_worker analysis_worker.env \
    'import analysis_worker.main; from analysis_worker.adapters.r import models; models._r()'
  echo "Each wheelhouse installs offline, and the API and the workers import"
fi

ls -l "$ROOT/dist"/breedgraph-"$VERSION"*
for extra in server worker analysis_worker; do
  echo "$(house "$extra"): $(ls "$(house "$extra")" | wc -l) files, $(du -sh "$(house "$extra")" | cut -f1)"
done

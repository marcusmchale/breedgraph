# Releasing

breedgraph and [BreedView](https://github.com/marcusmchale/breedview) are released together under the same version: a
breedgraph release works with the BreedView release of the same number, and a release of one comes with a release of
the other, even one with no changes of its own. The version is in `pyproject.toml`, and in BreedView's `package.json`.

## Before

- Both repositories' `master` holds what is to be released, pushed, with nothing uncommitted.
- breedgraph's suites pass on throwaway services, never the development database, which they empty
  (`scripts/scratch_services.sh`; its header says how):

      SCRATCH=<scratch directory> scripts/scratch_services.sh init
      SCRATCH=<scratch directory> scripts/scratch_services.sh start
      set -a; . instance/breedgraph.env; . instance/private.breedgraph.env; set +a
      eval "$(SCRATCH=<scratch directory> scripts/scratch_services.sh env)"
      python -m pytest tests/breedgraph tests/analysis_worker tests/map_worker tests/breedcafs_migration --ignore-glob="*test_breedcafs_migration_*"

  Run `src/breedgraph/adapters/neo4j/cypher/infrastructure/create_indexes.cypher` on the new store first, or the
  reference searches fail. The tests skipped are those of one map mode only (`test_map_regions.py`) or of what isn't
  installed (R, rsync).
- BreedView's unit tests, lint and end-to-end tests pass, the latter against an API from `master` on the test database
  (breedview `tests/e2e/README.md`). A test that fails in a full run but passes alone is a flake to fix, not to ignore.
- [upgrading.md](upgrading.md): its Unreleased section becomes the release's (`## v<version>`), saying what the
  release needs besides the usual upgrade, or that it needs nothing.

## The version

In breedgraph, `version` in `pyproject.toml`; in BreedView, `npm version <version> --no-git-tag-version`, which sets
`package.json` and `package-lock.json`. Each is committed alone ("Version <version>, with …"), tagged `v<version>` on
that commit, and pushed with its tag:

    git tag v<version>
    git push origin master v<version>

## The builds

From the tag, on a machine with the development environment:

- breedgraph's wheel, source distribution and wheelhouses, checked by installing each offline and importing the API
  and the workers ([deployment.md](deployment.md), Build):

      scripts/build_wheelhouses.sh --check v<version>
      git archive --format=tar.gz --prefix=checkout/ -o dist/breedgraph-<version>-checkout.tar.gz v<version>

- BreedView's production and demonstration builds, `npm run build` and `npm run build:demo` (breedview README.md).

## The releases

breedgraph's, with the wheel and the source distribution attached:

    gh release create v<version> dist/breedgraph-<version>-py3-none-any.whl dist/breedgraph-<version>.tar.gz --title "BreedGraph v<version>" --notes-file <notes>

and BreedView's, with nothing attached (its guide's videos stay in the release that has `guide-media.zip`, which the
guide's site takes the newest of):

    gh release create v<version> --title "BreedView v<version>" --notes-file <notes>

Each one's notes start "Released with BreedGraph v<version>." (or BreedView), then say what changed, for its users and
for whoever deploys it, and end with where to read how to upgrade: [upgrading.md](upgrading.md), its section. BreedView's
release starts its guide's Pages workflow, which deploys from `master`.

Then deploy ([deployment.md](deployment.md), Upgrading to a new release).

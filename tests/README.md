# Test conventions

## Setup

Test dependencies live in `requirements-dev.txt` (pytest + pinned
pytest-xdist):

```
pip install -r requirements.txt -r requirements-dev.txt
```

pytest-xdist is optional for serial runs — plain `pytest` works without
it. Passing `-n` requires it AND `--dist=loadgroup` (a conftest guard
refuses `-n` without loadgroup, because the `real_corpus` group would
otherwise race — see Markers below).

## Running tests

### Fast subset (default local run)

```
python3 -m pytest
```

`pytest.ini` sets `addopts = -m "not slow"`.  Running plain `pytest` skips the
heavyweight integration tests and completes in under 30 seconds.

### Full suite locally

```
python3 -m pytest -m "" --override-ini="addopts="
```

Or with parallelism (respects `real_corpus` isolation groups):

```
python3 -m pytest -m "" --override-ini="addopts=" -n auto --dist=loadgroup
```

### Parallel fast subset

```
python3 -m pytest -n auto --dist=loadgroup
```

The `addopts` default filter (`-m "not slow"`) still applies, so only the
fast subset runs. `--dist=loadgroup` must be passed explicitly whenever
`-n` is used (it is not in `addopts` because xdist is a dev-only
dependency); the conftest guard turns a forgotten `--dist=loadgroup` into
a clear error instead of a flaky race.

## Markers

### `slow`

Applied to any test that individually takes more than ~2 seconds.  This covers:

- Tests that call `publish()` or `build_release()` (zip construction + validator
  passes over the full content corpus).
- Tests in `test_validate_content_hook.py` (subprocess calls to the full
  validator stack).
- Tests in `test_cli_phase4.py` (factory-copy construction + validator run).

Files currently marked `slow` at module level:

| File | Reason |
|------|--------|
| `test_publish_phase3.py` | zip builds + real corpus validators (~30s/test) |
| `test_publish_pr_mode_v4.py` | zip builds + real corpus validators |
| `test_third_party_routing.py` | zip builds + publish integration |
| `test_third_party_component_routing_phase5.py` | zip builds + publish integration |
| `test_cli_phase4.py` | factory copy + validators (~8s/test) |
| `test_release_builder_phase2.py` | zip construction (~5s/test) |
| `test_validate_content_hook.py` | subprocess validator calls |

### `real_corpus`

An `xdist_group` marker.  Tests that **read** the real `content/` corpus through
subprocess validators (`publish(factory_repo=REPO_ROOT)`) must not run
concurrently.

`xdist_group("real_corpus")` colocates all affected tests on a single xdist
worker where they execute sequentially, preventing races where concurrent
validator scans interfere with each other.

Files that carry both `slow` and `real_corpus`:

- `test_publish_phase3.py`
- `test_publish_pr_mode_v4.py`
- `test_third_party_routing.py`
- `test_third_party_component_routing_phase5.py`

`test_validate_content_hook.py` is marked `slow` but **NOT** `real_corpus`.
It is hermetic: it sets `VCFCF_CONTENT_ROOT` to a `tmp_path`-based copy of
the corpus for every test, so it never reads from or writes to the real
`content/` directories.  It is safe to run on any xdist worker in parallel
with other workers.

`test_cli_phase4.py` and `test_release_builder_phase2.py` are marked `slow`
but **not** `real_corpus` because they operate on private temp-directory copies
of the corpus and are safe to run in parallel with other workers.

## Parallel safety

All tests that do NOT carry `real_corpus` are designed to be fixture-isolated:

- Publish/release tests create temporary git repos via `tmp_path`.
- `test_cli_phase4.py` copies the entire corpus into a temp directory for each
  test class.
- `test_validate_content_hook.py` builds a `tmp_path` workspace and sets
  `VCFCF_CONTENT_ROOT` so the hook subprocess resolves all `content/…` paths
  against that temp tree — the real `content/` directories are never touched.
- No test mutates `content/`, `releases/`, or any shared repository state
  outside of the `real_corpus` group.

`tests/managementpacks/` and all the validator/loader unit tests are
stateless and safe for full parallelism with `-n auto`.

## CI

CI runs the full suite with parallelism:

```yaml
python3 -m pytest tests/ -v --tb=short -n auto --dist=loadgroup --override-ini="addopts=" -m ""
```

`--override-ini="addopts="` clears the local-default `not slow` filter.  
`-m ""` explicitly matches all tests regardless of marker.  
`-n auto` parallelises across available CPUs.  
`--dist=loadgroup` ensures `xdist_group("real_corpus")` tests are colocated on
one worker so the publish tests (which scan the real content/ corpus) never
execute concurrently.

# Framework review: release/publish audit-by-default (offline) + ${this} ref auditing

- **Branch/commit:** `fix/release-audit-default-and-this-refs` @ `6ae322d` + fold-in `abf9ed5` vs `origin/main`
- **Reviewer:** framework-reviewer, 2026-08-25
- **Area:** `src/vcfops_packaging/` (release_builder, publish, deps, audit, cli)
- **Verdict:** **APPROVE** (0 BLOCKING / 0 open WARNING / 3 NIT; W1 resolved by `abf9ed5`)

## Change under review

1. Release/publish builds now run the describe-cache dependency audit by
   default, offline (`skip_audit=False`, `live_describe=False` at all three
   `release_builder.py` sites). `publish.py` maps `AuditError` and
   `DescribeCacheError` to hard `PublishError`s naming the `--skip-audit`
   opt-out; new `publish --skip-audit` CLI flag; `skip_audit` bound via
   `functools.partial` to preserve the #125 seam contract.
2. `deps._refs_from_formula` now resolves `${this, metric=KEY}` against the
   SM's declared `resource_kinds` (one `MetricReference` per pair); a this-ref
   with no usable resource_kinds raises `AuditError` instead of being skipped.
3. 13 new tests, a `**kw` fix in `test_publish_seams.py`, doc update in
   `guide_install_verification.md`.

## Independent verification (all re-run by reviewer)

| Check | Result |
|---|---|
| Validate chain (7 packages per project-conventions skill) | all pass |
| Full test suite (`PYTHONPATH=src pytest tests/`) | 1098 passed, 4 skipped |
| New test file + seams file incl. `slow` marks | 20 passed |
| Corpus release rebuild, offline, scratchpad output | **13/13 PASS**, 10 zip-bearing, 0 unknown refs, 0 auto-adds, 0 WARNs; `storage-path-monitoring` now shows its previously invisible this-ref audited (1 ref, resolved defaultMonitored=true) |
| Zip content vs `dist/storage-path-monitoring.zip` | member lists identical, `install.ps1` identical; only `vcfops_manifest.json` `built_at` differs. Template version unchanged (`2026-08-24-2`), correct: no content drift, no bump needed |
| Offline default | test asserts zero `VCFOpsClient` constructions with creds in env; code-confirmed `make_cache(live=False)` never builds a client (`describe.py:427`) |
| Silent-downgrade probe (unenumerated failure: cache file chmod 000) | loud `DescribeCacheError` ("corrupt: Permission denied") -> `PublishError` naming `--skip-audit`. No path lets publish continue unaudited: missing cache file -> `AuditError` from `_check_cache_coverage`; corrupt/unreadable -> `DescribeCacheError`; anything else -> generic `PublishError`. All abort |
| Publish abort path | test asserts no commit lands and `.publish.lock` released; staging is a `tempfile.TemporaryDirectory` outside the dist repo (`publish.py:1294`), so dist tree stays clean on abort |
| Seam contract (#125) | injected stubs keep the 3-positional-arg shape; `TestDefaultsAreReal` and anti-drift pass; `functools.partial` binds `skip_audit` only on the real default |
| CLI | `publish --skip-audit` parses and threads to the builder (`cli.py:1406`); plain `publish -h` wording matches the build commands' warning wording, not misleading |
| Mutation check | restoring the pre-fix "skip every `${this}`" behavior fails 7 of the 13 new tests (author claimed 4; coverage is stronger than claimed) |
| Corpus-wide this-ref sweep | all 28 `content/supermetrics/*.yaml` (including the 3 multi-kind this-SMs: `vks_global_vcpu_pcore_ratio`, `vks_vmservice_vcpu`, `vks_cores`) extract and resolve clean against the committed describe cache |
| Wire-shape trace | staged bundles carry `resourceKinds` camelCase (`vcfops_supermetrics/handler.py:52`), matching `audit.py:analyze_staged_bundle`; loader normalizes authoring snake_case to camelCase, matching `deps.py`'s dual-key acceptance. `cmd_analyze`'s pair-discovery `continue` is safe: `analyze_staged_bundle` below re-raises loudly (verified `cli.py:418`) |

## Findings

### WARNING (RESOLVED by `abf9ed5`, re-verified 2026-08-25)

- **[src/vcfops_packaging/audit.py:143] semantics + message wording for
  partial-kind coverage.** Probe confirmed: an SM declaring two
  resource_kinds whose this-metric exists on only one hard-fails as
  "metric keys were not found ... usually means the metric key is
  misspelled". The strictness is defensible (a `${this}` key absent from an
  assigned kind means the SM is dead on that kind) and `--skip-audit` is the
  escape hatch, but a legitimate broad-assignment SM would be blocked with a
  misleading diagnosis. Corpus is clean today (verified, all 28 SMs). Fix:
  when an unknown this-ref key resolves on a sibling declared kind, say so
  ("present on VMWARE/VirtualMachine but not VMWARE/HostSystem; narrow
  resource_kinds or fix the key") instead of "misspelled". Follow-up issue,
  not a blocker.

  **Resolution re-check (`abf9ed5`):** message-only change confirmed; the
  diff touches only the `if unknown:` message-assembly block in
  `audit_bundle_dependencies`, raise semantics and all pass paths untouched.
  Original probe re-run: still a hard `AuditError`, now with
  "NOTE: this key DOES resolve on VMWARE/VirtualMachine but NOT on
  VMWARE/HostSystem. This is partial resource-kind coverage ... not a
  misspelled key", and the typo hint qualified "For keys with no NOTE
  above". New test `test_partial_kind_coverage_names_both_sides` pins both
  sides. Re-run by reviewer: new file 14/14 incl. slow; related files
  (audit/publish/deps/seams) 103 passed; full suite 1099 passed, 4 skipped.
  The sibling match is conservative (same metric key AND same source_desc),
  so a NOTE never fires on an unrelated resolver: correct.

### NIT

- **CLAUDE.md "After tooling changes" lists `release_builder.py`**, so the
  mechanical stale-zip rule fires. Byte-compare shows zip content is
  unchanged for passing content (only `built_at` differs), so a packager
  rebuild is a no-op and no `CURRENT_TEMPLATE_VERSION` bump is warranted
  (a bump would falsely mark distributed zips stale). The PR/handoff should
  carry this byte-identity evidence explicitly so the exemption is on the
  record.
- **[src/vcfops_packaging/cli.py:404]** in live mode, the `except AuditError:
  continue` in pair discovery also skips refreshing pairs from later
  non-this refs in the same SM formula. Harmless (the audit below fails
  loudly anyway) but costs one potential refresh.
- **[src/vcfops_packaging/publish.py:1252]** `publish(skip_audit=True)`
  combined with an injected `build_one_release` seam silently ignores
  `skip_audit` (the partial only wraps the real default). Test-seam-only
  surface, documented as the #125 contract; noting for the record.

## If shipped as-is

Publish gains a real offline audit gate: an unknown or this-bound-invisible
metric ref now aborts the publish loudly with a repair path and an explicit
opt-out, with zero change to shipped zip content for passing releases and no
network dependency introduced.

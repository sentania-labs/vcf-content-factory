# Framework Review — defect-gate tests, DEF-001 closed

- **Area:** `tests/test_defect_gate.py` (no `vcfops_*/` source changed)
- **Branch:** `fix/defect-gate-tests-def001-closed`
- **Change:** De-brittle the defect-gate suite after DEF-001 (synology
  credential-leak) was legitimately closed in `knowledge/context/defects.md`
  (shipped as `v1.0.0.19`, 2026-06-26). 10 real-corpus-coupled tests
  hardcoded "DEF-001 open / synology blocked"; they were inverted
  (synology now exit-0/clean) or retargeted to a genuinely-open blocker.
- **Verdict:** APPROVE
- **Findings:** 0 BLOCKING / 0 WARNING / 1 NIT

## Checks re-run (independently)

- `pytest tests/test_defect_gate.py -q` → **49 passed**.
- `pytest -q` (default `-m "not slow"`) → **435 passed, 4 skipped, 162
  deselected** (deselected = `slow` marker per `pytest.ini addopts`, not
  hidden defect tests).
- `pytest -m "" --override-ini="addopts=" tests/test_defect_gate.py` →
  **49 passed** (CI-equivalent marker set; no slow-only red).
- Live gate against the real registry:
  - `gate_pak("synology")` → `[]` (genuinely clean — DEF-001 + DEF-003
    both closed)
  - `gate_pak("unifi")` → `["DEF-002"]`
  - `gate_all()` → `["DEF-002", "DEF-004"]`
- Registry cross-check `knowledge/context/defects.md`: DEF-001 **closed**
  (Closing-evidence: synology build 19 `1.0.0.19`, 2026-06-26), DEF-002
  **open** (unifi), DEF-003 **closed** (synology), DEF-004 **open**
  (vcommunity-os). Test comments match the registry exactly.
- `closing_evidence` is a real `DefectEntry` dataclass field
  (`vcfops_packaging/defects.py:88`), required non-empty when
  `status == "closed"` — so the new `test_def001_fields` assertion checks
  a genuine schema invariant, not a tautology.

## Verification against the brief's bar

1. **Suite genuinely green** — yes, 0 failed in all three runs; the 162
   deselected are `slow`-marked, not silently dropped defect tests.

2. **Block coverage still real and present** — confirmed the gate's
   ability to BLOCK a genuinely-open-blocker pak survives, relocated (not
   deleted) from the now-closed synology to genuinely-open DEF-002/DEF-004:
   - `test_pak_unifi_exits_2` (CLI, DEF-002) — `tests/test_defect_gate.py:469`
   - `test_pak_vcommunity_os_exits_2` (CLI, DEF-004) — `:487`
   - `test_sdk_adapter_release_refused_for_unifi` (cmd_release exit-2,
     DEF-002) — `:607`
   - `test_raises_for_unifi_sdk_adapter` (`_gate_publish` raises
     `PublishError`, DEF-002) — `:710`
   - `test_all_exits_2_when_open_blockers` (CLI `--all`, DEF-002+DEF-004)
   - `test_all_exits_2_lists_def002_and_def004` (standalone `--all`)
   - `test_bare_copy_matches_in_package_run` retargeted synology→**unifi**,
     still asserts exit-2 + names DEF-002 + RULE-012 (curl-and-run proof
     intact) — `:965`
   - 9 surviving `rc == 2` / `pytest.raises(PublishError)` assertions in
     the file. The gate is still provably able to block.

3. **Synthetic-fixture / logic tests untouched** — the 6 changed test
   functions are *all* synology→closed inversions or unifi/open-set
   retargets. No inline test-registry fixture, malformed-entry test
   (`TestMalformedEntries`), `gate_item`, `gate_all_empty_registry`, or
   error-path test was altered. Gate *logic* coverage is unchanged.

4. **Inverted assertions are meaningful, not vacuous:**
   - `test_synology_is_clean_def001_closed` → `assert blockers == []` —
     meaningful: `gate_pak` demonstrably returns non-empty for unifi, and
     synology genuinely resolves to `[]` against the live registry.
   - `test_def001_fields` → asserts `status == "closed"` **and**
     `closing_evidence.strip()` non-empty — a real closed-entry schema
     invariant, not a no-op.
   - `test_synology_passes_def001_closed` → `_gate_publish(...)` must NOT
     raise; this exercises the pass path for a real pak, distinct from the
     raise path covered by `test_raises_for_unifi_sdk_adapter`.
   - The `gate_all` real-corpus floor was lowered `>= 3` → `>= 2`,
     matching the current open set {DEF-002, DEF-004}, and still asserts
     `DEF-001 not in ids` / `DEF-003 not in ids` (closed must never
     appear). Not loosened into vacuity.

5. **Real-corpus tests appropriately resilient** — retargeted to the
   current open set {DEF-002, DEF-004} with explicit "tracks the live
   corpus; update when a defect changes state" comments. They assert
   *which* ids are present/absent rather than a total count, so a new
   filing does not break CI — same anti-brittleness invariant as before,
   not a new brittleness.

## NIT

- [`tests/test_defect_gate.py:918`] Stale docstring cross-reference: the
  standalone `test_pak_synology_exits_0_def001_closed` docstring says "For
  exit-2 coverage see `test_pak_unifi_exits_2_names_def002`", but no test
  by that name exists. The actual exit-2 coverage is
  `test_pak_unifi_exits_2` (`:469`) and, in the standalone class,
  `test_all_exits_2_lists_def002_and_def004` / the unifi bare-copy run.
  → Fix the referenced name so a future reader following the pointer lands
  on a real test. Documentation only; no coverage gap.

## If shipped as-is

CI goes green again and the release gate keeps its teeth: an operator who
tries to `/publish` or tag a genuinely-blocked pak (unifi/DEF-002,
vcommunity-os/DEF-004) is still refused with the defect id named, while
synology — legitimately fixed in v1.0.0.19 — is correctly no longer
blocked. The only residual is a dead test-name reference in one docstring.

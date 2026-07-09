# synology SDK adapter — build 27 review

- **Adapter:** `content/sdk-adapters/synology`
- **Build reviewed:** 27 (`0.0.0.27`), adapter-repo commit `aa918d0` on `main`
- **Reviewer:** `sdk-adapter-reviewer`
- **Date:** 2026-07-06
- **Verdict: APPROVE** (0 BLOCKING / 0 WARNING / 2 NIT)
- **Scope:** docs-only build adopting the new `cross_mp_edges` adapter.yaml
  stanza. Diff = `adapter.yaml` (+22), `CHANGELOG.md` (+13),
  `docs/README.md` (+11/-1), `docs/inventory-tree.md` (+10/-1). **No Java,
  no `describe.xml`, no `template.json` touched** (git diff confirms).
  Primary exercise: first live use of docs-parity dimension (#11).

## Claims verified independently (re-run, not taken from author block)

| Claim | Result |
|---|---|
| `validate-sdk` passes | **confirmed** — `OK: content/sdk-adapters/synology is a valid Tier 2 SDK adapter project` (4 source files compile; 1 benign `-source 11` warning) |
| build reproduces `0.0.0.27` | **confirmed** — `Built: dist/vcfcf_sdk_synology_diskstation.0.0.0.27.pak` |
| docs are byte-reproducible | **confirmed** — `git status` clean after `build-sdk` regenerated `docs/README.md` + `inventory-tree.md`; committed == generated |
| `pak-compare` vs `0.0.0.26` = 0/0/0 | **confirmed** — "No structural divergences found. Score: 0 BLOCKING, 0 WARNING, 0 INFO" |
| `pak-compare` vs compliance reference = 0 BLOCKING | **confirmed** — 0 BLOCKING / 3 WARNING / 35 INFO; all WARN/INFO are inherent cross-adapter differences (different credential-field/identifier/traversal counts, distinct resource kinds, icons, profiles), none introduced by build 27 (describe.xml identical to build 26 per the 0/0/0 above) |
| stanza matches the stitch code | **confirmed** — see below |
| no Java/describe.xml diff beyond adapter.yaml/docs/CHANGELOG | **confirmed** — `git diff a312cac aa918d0` touches only those 4 files |

## Stanza-vs-code honesty (SynologyAdapter.emitDatastoreCrossLink, lines 982–1049; SynologyStitcher path helpers)

Every claim in the two stanza descriptions is backed by the actual code:

- **direction `parent_foreign`, Datastore is parent** — `rb.parentForeign(ds, lunKey)` / `rb.parentForeign(ds, exportKey)` (lines 1008, 1039). Correct: Datastore = parent, synology child. TRUE.
- **`foreign_adapter_kind: VMWARE`** — resolver loads VMWARE Datastores (`SynologyStitcher.loadDatastores`). TRUE.
- **iSCSI "matched by computed VMFS extent NAA path"** — `SynologyStitcher.lunDataStorePath(uuid)` builds `VMFS:|naa.6001405…|` (lines 149–158). TRUE.
- **"resolved against real inventory only (no phantom Datastore minted when no match exists)"** — `if (matches.isEmpty()) continue;` (lines 996, 1030); resolver returns empty list, never mints keys. TRUE (matches the class doc at SynologyStitcher:33 and SynologyAdapter:60).
- **"One path can back N datastores (one per vCenter view) — bound to every copy"** — `for (ResourceKey ds : matches) { rb.parentForeign(...) }` (lines 1007, 1037). TRUE.
- **NFS "matched by computed `<nas_ip>/<vol_path>/<share>` path per connected NAS interface"** — `nfsDataStorePath(ip, volPath, name)` iterated over `connectedNasIps(s.networkInterfaces)` from the per-cycle snapshot, no live call (lines 1015–1028). TRUE.
- **NFS "deduped so a single Datastore never gets the same export as a duplicate child"** — `Set<ResourceKey> linkedDs` guard `if (!linkedDs.add(ds)) continue;` (lines 1026, 1038). TRUE.

No dishonest coverage inflation, no phantom-Datastore claim, no MOID-based joins (path identity only). Dimension #5 (stitch identity / uniqueness-flag trap) is not touched by this build — no `ResourceKey` construction changed — and the underlying additive-scoping safety was live-proven under DEF-003 (closed).

Read-path safety (dimensions 1–4) is unchanged: no Java diff. The cross-link is `try/catch`-guarded (line 1048) so a stitch fault never costs the cycle its internal topology, and it is a no-op when `stitcher == null` — both unchanged from build 26.

## Docs-parity walk (dimension #11 — first exercise, the point of this build)

This build exists **specifically to close the same gap that bit unifi
v1.1.0.11 / synology previously** (cross-MP edge documented only in
`overview.md`, invisible on the landing README and inventory tree). It does:

- **Landing `docs/README.md`** — now carries a `## Cross-MP Relationships`
  section with a Parent/Child/Description table listing **both** edges,
  foreign endpoints italicized `*VMWARE Datastore* (foreign, VMWARE)`, owned
  endpoints in `code`, plus a Quick Reference line
  `Cross-MP relationships: 2 (see …)`. **Surfaced. PASS.**
- **`docs/inventory-tree.md`** — same section present with identical table.
  **Surfaced. PASS.**
- **`docs/overview.md`** — pre-existing `## Cross-Adapter Behavior` section
  (path identity never MOID, no phantom Datastore, ambient/optional,
  skipped-with-WARN when Suite API unavailable). Accurate against the code
  and **non-contradictory** with the new stanza. **PASS.**

The gap is closed on all three doc surfaces. This is exactly the outcome
dimension #11 was written to force.

## Registry check (context/defects.md) — mandatory

Read in full. **No open defect names `synology`.**

- DEF-001 (synology) — **closed** (build 19, secrets redaction). No re-assert owed.
- DEF-003 (synology) — **closed** (build 16 devel proof; this is the additive-scoping certification that underwrites the edge this build now documents). No re-assert owed.
- DEF-005 (synology) — **closed** (build 24, BC-mirror transport). No re-assert owed.
- DEF-006 (synology) — **closed** (build 26, ambient identity v3; residual is *evidentiary only* — capture the unquoted CP-side `file=instance` log line — not functional, not gating). No re-assert owed; unchanged by this docs-only build.
- DEF-004 (vcommunity-os), DEF-002 / DEF-007 (unifi) — do not affect synology.

No new registration candidate: the only findings are NITs (NITs do not enter the registry, per RULE-012 / defects.md graduation rule).

## NIT (non-blocking)

- **[docs/README.md:26, docs/inventory-tree.md:26]** dimension #11 — the NFS
  row's placeholder `<nas_ip>/<vol_path>/<share>` is emitted **un-backticked**
  inside a markdown table cell (generated verbatim from the `adapter.yaml`
  stanza description). GitHub's markdown sanitizer strips non-whitelisted
  `<…>` tokens, so on the *rendered* landing README an operator sees
  "matched by computed  //  path per connected NAS interface" — the three
  placeholder tokens vanish. The iSCSI row is unaffected (no angle brackets).
  `overview.md:63` already wraps the identical construct in backticks
  (`` `<nas_ip>/<volume_path>/<share>` ``), so the correct idiom is known.
  Smallest fix (author-owned, in `adapter.yaml` cross_mp_edges[1].description):
  wrap the path template in backticks. Cosmetic — the substantive facts
  (per-NAS-interface, deduped) and the code-truth survive.
- **[CHANGELOG.md / commit message]** minor attribution imprecision: the
  edge is described as "built by `SynologyStitcher`/`emitDatastoreCrossLink`",
  but `emitDatastoreCrossLink` lives in **`SynologyAdapter`** (lines 982–1049);
  `SynologyStitcher` supplies the resolver (`loadDatastores`, `matchByPath`,
  `lunDataStorePath`, `nfsDataStorePath`). Not operator-visible (CHANGELOG
  only), no action required.

## If shipped as-is

Operators browsing the synology pak repo will, for the first time, see the
two Datastore→Synology cross-MP edges documented on the landing README and
inventory tree (not just buried in overview.md) — the exact silent-omission
gap this build targets is closed. `describe.xml`/`template.json`/wire content
are byte-identical to build 26 (0/0/0), so there is zero runtime/collection
behavior change. The only blemish is one rendered-markdown placeholder that
loses its `<…>` tokens on GitHub — a cosmetic doc nit, not a correctness or
coverage issue.

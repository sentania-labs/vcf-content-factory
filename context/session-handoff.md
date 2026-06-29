# Session Handoff — 2026-06-14 (orchestration-review sprint + 9.1 bundle + curation/hygiene — ALL MERGED; vCommunity parked)

Transient working-state note so a fresh session can pick up cold. Point the
new session here. Not durable knowledge — delete once consumed.

The 2026-06-10 vCommunity handoff below is **still live** (install paused,
files uncommitted) — preserved verbatim, do not drop it when consuming this.

## HEADLINE

A long multi-day session. The vault orchestration review's whole P-list
plus a VCF 9.1 review bundle, a curation pass, and a doc-hygiene round are
**all merged to main** (`bd54f9e`). **No open PRs.** vCommunity is still
parked on a credential/log blocker only Scott can clear.

## What merged (#12–#23, all on main)

- **P2 defect registry + release gate** (#12, RULE-012) and its **pak-repo
  v\* gate** (#18 + propagation): `context/defects.md` registry,
  `vcfops_packaging/defects.py` (+ standalone `__main__`), `defect-gate`
  CLI, the gate wired into `release`/`publish` AND into every pak repo's
  `build-pak-on-tag.yml` (vendored `ci/defect_gate.py`, fetches only the
  live registry — Codex-P1 supply-chain fix). Design: `designs/defect-registry-v1.md`,
  `designs/defect-gate-pak-ci-v1.md`.
- **P4 framework-reviewer** (#17, RULE-013): read-only `vcfops_*/` regression
  gate, `.claude/agents/framework-reviewer.md`, + CI reminder
  `scripts/check_framework_review.sh`. Proven by reverting `00d3382`.
- **P6 curator** (#20): `.claude/agents/curator.md` + SessionStart staleness
  hook (`scripts/curation_staleness_check.sh`, marker `context/curation/.last-run`
  committed + `.sessions-since` gitignored). 8 rot classes. Design: `designs/curator-v1.md`.
- **P5 hygiene** (#19), **test-speed** (#16: default `pytest` ~13s, CI full
  parallel), **SDK build-from-source docs** (#15), **Fleet self-provider**
  (#14), **Ford-quote removal** (#13).
- **9.1 update bundle** (#22): `context/investigations/vcf-ops-9.1-adoption-review-2026-06-13.md`
  + prod 9.1 OpenAPI specs `docs/operations-api-9.1.json` (343 paths) /
  `docs/internal-api-9.1.json` (217), saved version-suffixed beside the
  9.0.x baselines. Prod confirmed 9.1.0.0 build 25435105.
- **Curation pass + mechanical fixes** (#21) and **doc-hygiene** (#23):
  fixed corrupt `docs/vsphere-data-api-openapi.json` (missing `}`, invalid
  since first commit), de-staled `tier2_architecture.md`, codified
  `lessons/no-volatile-status-in-reference-docs.md`.

## ⏸ RESUME POINT / what's next (nothing in-flight)

1. **Two NEW agent types are on main but not registered in the current
   session** (`curator`, `framework-reviewer`) — they register on the next
   fresh session start. Until then they run via prompt-adoption.
2. **9.1 follow-up spikes** (design-first, version-aware — none started),
   ranked: **(a) vIDB-auth-for-install** — Scott's flagged priority; the
   9.1 review did NOT confirm 9.1 adds programmatic VIDB (the 2026-04-23
   investigation found 9.0.2 blocks it → Local service account). Needs a
   focused investigation against the +93 new 9.1 paths. **(b) Findings/
   Diagnostics API** supplemental-enrichment spike. **(c) Prometheus-source
   MPB** new authoring lane. Cheapest first step: a **9.0→9.1 path diff** of
   the +93 added endpoints (both specs now in-repo) — also resolves the
   vIDB question.
3. **DEF-004 candidate**: compliance MOID fix built (build 51, pushed
   c126194) but devel still on build 50 — register per RULE-012 if
   unverified at next compliance review.
4. **Deferred curation-judgment tail** (low-stakes, next curation re-flags):
   the SUPERSEDED "compliance fix queued" claim lives in an *uncommitted*
   vCommunity lesson (`stitch-moid-not-unique-across-vcenters.md`); the
   pak-install lessons want DUPLICATION cross-links.

## Durable state / facts a fresh session must not re-derive

- **Defect registry is LIVE on main.** DEF-002 (unifi foreign-HostSystem
  edge, unproven on devel) and DEF-004 (vcommunity-os in-guest collection)
  are **open/blocking** → a unifi or vcommunity-os `v\*` tag is refused until
  they close. DEF-001 (synology secret-in-path) closed via synology 1.0.0.19
  (2026-06-26); DEF-003 (synology edge) closed via build-16 9.0.2 proof.
- **Two new governance conventions** (from this session): (1) the committed
  OpenAPI spec **supersedes PDF prose** where they conflict (9.1 review);
  (2) **no volatile status in reference docs** — versions/phase/counts live
  in transient surfaces (`lessons/no-volatile-status-in-reference-docs.md`).
- **9.1 public API is +93 paths / 0 removed vs 9.0.x** — purely additive;
  every endpoint the factory uses today still exists on 9.1. Core content
  schemas: no breaking property change; one deprecation
  (`symptom-definition.realtimeMonitoringEnabled`). `setRelationships`
  scoping + SSL-TOFU: **9.1 UNVERIFIED** (docs silent — lessons' residual
  flags stay correct). FIPS on-by-default-can't-disable is the 9.1 landmine.
- **VCF 9.1 PDF** at `docs/vmware-cloud-foundation-9-1.pdf` (178MB, 9279pp,
  gitignored); pdftotext extract recipe in the 9.1 review doc.

## Working-tree state (uncommitted, deliberately left)

`M context/managed_paks.md`, `M context/session-handoff.md` (this file),
plus the vCommunity-session artifacts: `designs/managementpacks/vcommunity{,-sdk}.md`,
`context/reviews/vcommunity-build-1.md`,
`context/investigations/vcommunity_{upgrade_path_experiment,validate_silent_failure_2026_06_13}.md`,
`lessons/{cross-runtime-pak-upgrade-split-brain,stitch-moid-not-unique-across-vcenters}.md`,
`.review-passed`. Left uncommitted per Scott until the vCommunity work lands
(their lesson INDEX rows were dropped from #21 to avoid dead links — Codex
catch). Local worktree `/home/scott/projects/vcf-content-factory-vcommunity`
(explore/vcommunity-mp) left intact.

## vCommunity (task #6) — BLOCKED ON SCOTT

Silent-collection bug: instance 5186 DATA_RECEIVING but 0 metrics, nothing
stitched, `vCommunityWorld Summary|status` never written. Diagnosis is in
`context/investigations/vcommunity_validate_silent_failure_2026_06_13.md`;
prime suspect is the SuiteApiStitcher channel failing every cycle (SSL
handshake per `lessons/suite-api-stitch-ssl-tofu-vs-java-http.md`, or the
build-2 vCenter-UUID scoping dropping all foreign resources). DECISIVE
EVIDENCE = the adapter container log on the devel appliance (needs SSH —
only Scott can fetch it): grep the ~cycle for SSLHandshakeException / auth /
UUID. Hold all fixes until Scott provides it. The original 2026-06-10
vCommunity install (paused at instance creation on a missing wld01 .env
credential) is the carried-over handoff below — still live.

---

# Carried over verbatim: Session Handoff — 2026-06-10 (vCommunity Tier 2 rewrite: designed, built, reviewed, half-installed)

*(2026-06-12 annotations in square brackets; otherwise untouched.)*

## HEADLINE

Full Tier 2 lifecycle for the **vCommunity rewrite** ran end-to-end today:
recon → design (approved, zero open) → repo instantiated → Java adapter
built (build 2) → reviewer **APPROVE 0 BLOCKING** → pak installed on devel.
**Install is paused at adapter-instance creation** — wld01 vCenter password
missing from `.env`. One env edit by the user unblocks the final smoke
tests. Bonus: compliance got a correctness fix (build 51, built+pushed,
NOT installed), and two new lessons were codified.

## ⏸ RESUME POINT (the one blocked step)

`content-installer` completed preflight/install/registration on devel but
stopped at instance creation per RULE-008. User must add to `.env`:

```
export VCFCF_VCOMMUNITY_VCENTER_WLD01_USER=administrator@wld01.domain
export VCFCF_VCOMMUNITY_VCENTER_WLD01_PASSWORD=<password>
```

Then re-brief `content-installer` for steps 4–6: create wld01 instance
(**Windows Monitoring = Disabled, Windows Guest Credential UNSET** — the
unset-second-credential acceptance is itself a smoke-test item; config-file
identifiers at defaults), verify DATA_RECEIVING, `vCommunity|` keys on live
Cluster/Host/VM, central SolutionConfig fetch, and the vim25 surfaces beyond
the compliance-proven set (guest-ops manager, QueryAssignedLicenses,
fetchSoftwarePackages/installDate, EvcManager).

## Decisions made today (user-confirmed, all recorded verbatim in designs/managementpacks/vcommunity.md)

1. **Full parity v1** incl. Windows guest-ops; **port ALL ~100 content
   artifacts** (incl. the generic "Report - VOA -" set — "as close to a
   pure rewrite as possible"), converted to **factory YAML as canonical
   source** (pipeline-strengthening is a co-equal goal).
2. Name **vcommunity**; keep the **`vCommunity|` key namespace** verbatim.
3. **True upgrade pak REJECTED** — proven non-viable on devel (silent
   split-brain; see lesson). Side-by-side `vcfcf_vcommunity` + migration
   runbook (in pak README). Prod migration = uninstall original first
   (user confirmed; both adapters write the same keys).
4. **Config = central** SolutionConfig store (the original's actual
   mechanism, adapter.py:261): pak ships six byte-identical default XMLs,
   six file-NAME identifiers (original keys verbatim), Suite API fetch per
   cycle + last-good cache. The earlier on-collector `custom_config_dir`
   design is dead.
5. **pak-compare B1 ACCEPTED** (two CredentialKinds vs compliance ref's
   one) — user explicitly acknowledged the multi-credential pattern
   (relevant to a future joint Enphase+FranklinWH MP). Once vcommunity is
   verified, it becomes the factory's 2-credential reference pak.
6. **Ship v1, close gaps in later builds, document them** — gap ledger is
   committed in the pak's README/CHANGELOG.

## State of the vcommunity pak (repo: sentania-labs/vcf-content-factory-sdk-vcommunity)

- Clone: `content/sdk-adapters/vcommunity/`; registered in
  `context/managed_paks.md`. Pushed to main (`a0f98fc`, `401babd`,
  `2267544`); **no v* tag** (release tagging = separate user decision).
  [2026-06-12: any future v* tag now also requires a passing
  `defect-gate --pak vcommunity` once PR #12 merges — currently clean.]
- Build 2 = `dist/vcfcf_sdk_vcommunity.1.0.0.2.pak`. validate-sdk green;
  pak-compare 1B/2W = the accepted B1 family only.
- Review: APPROVE, 0 BLOCKING — `context/reviews/vcommunity-build-1.md`.
  MOID-trap WARNING fixed in build 2 (vCenter-scoped stitching).
- Devel install state: pak INSTALLED (1.0.0.2,
  pakId `VCFContentFactoryvCommunity-1002`), `adapterKindType: GENERAL`
  (Docker requirement proven gone), both CredentialKinds probe-verified
  (windows kind field names: `winUser`/`winPass`), 10/10 identifiers
  registered. **Zero adapter instances yet** (see resume point).

## Task board

1. **Resume install steps 4–6** (blocked on .env; see resume point).
2. **Compliance build 51 install decision** — MOID cross-vCenter fix
   built, pushed (`c126194`), pak-compare 0/0/0 vs 50. Devel mgmt+wld01
   instances still run build 50. Live exposure: devel has two vCenters,
   so the unscoped bug is real there. Recommend installing 51 alongside
   the vcommunity instance verification pass. [2026-06-12: now also the
   DEF-004 graduation candidate — see today's queued rounds above.]
3. **Content port workstream** (not started, deliberately separate):
   ~57 SMs, 13 dashboards, ~22 reports + ~9 views, 2 symptoms + 3 alerts
   → factory YAML → rendered into pak content/. Known loader gaps are
   enumerated in the design (GAP #3/#4: report/view XML, SM UUID-ref
   rewriting, localization bundles) — expect TOOLSET GAP → `tooling`
   rounds. Keep `vCommunity|` paths verbatim.
4. **v1.1 ledger** (documented in pak README/CHANGELOG): real
   foreign-resource event push (`tooling` to add
   `SuiteApiStitcher.pushEvents` once an endpoint is proven — facade
   currently has only private `rawPost` to `/properties` + `/stats`);
   stable event-id keys (replaces positional Last Event keys).
   v2: per-VM guest-ops scoping, guest-ops concurrency.
5. **Windows guest-ops live test** — needs a Windows-enabled instance +
   Windows guest credential from the user. Not yet smoke-tested at all.

## Uncommitted factory-repo changes (commit when user asks)

`M context/managed_paks.md` (vcommunity entry), `M lessons/INDEX.md`,
new: `designs/managementpacks/vcommunity{,-sdk}.md`,
`context/investigations/vcommunity_upgrade_path_experiment.md`,
`context/reviews/vcommunity-build-1.md`,
`lessons/cross-runtime-pak-upgrade-split-brain.md`,
`lessons/stitch-moid-not-unique-across-vcenters.md`.
The pak repos (vcommunity, compliance) are committed and pushed.
[2026-06-12: still uncommitted, deliberately excluded from PR #12.]

## Key facts a fresh session must not re-derive

- **Cross-runtime upgrade is dead**: same-identity classic-over-containerized
  install is ACCEPTED but silently keeps the kind DOCKERIZED with the old
  describe; instance creation 500s. Lesson + investigation on file.
- **MOIDs are per-vCenter**: stitchers must pin owning vCenter UUID per
  cycle and filter by `VMEntityVCID` (lesson on file; vcommunity build 2
  and compliance build 51 carry the fix; the compliance *reference*
  previously enshrined the bug — copied patterns inherit it).
- `GET /api/credentials?adapterKindKey=` is a **leaky filter** — verify
  `adapterKindKey` on each returned record before trusting/deleting.
- `pushProperties` AND `pushStats` are proven on the Suite API stitcher;
  events are not (v1 degrades them to alertable properties).
- Original vCommunity MP identity: pak `iSDK_VCFOperationsvCommunity`
  v0.2.8, kind `VCFOperationsvCommunity`. NOT installed on devel; IS
  installed on **prod** (user statement) — prod migration runbook applies
  whenever that day comes. RULE-009: nothing touches prod.
- `sdk_project.py` enforces lowercase adapter kinds; platform accepts
  mixed-case (minor validator-note TOOLSET GAP, not blocking).

## Carried over from 2026-06-09 handoff (status not re-verified today)

Compliance reached build 50/51 and devel instances are healthy, so the v2
migration + raw-SOAP work evidently landed; treat these leftovers as
possibly stale, verify before acting: CI private-jar fetch wiring +
jar-free buildkit replacement (old `sdk-buildkit-v1` release exposed
Broadcom jars publicly — replace ASAP if not already), template-repo
update, prod compliance recovery status on 9.1, synology/unifi v2
migrations [2026-06-12: the synology/unifi v2 migrations DID land —
synology build 14→16 and unifi build 3, both reviewed APPROVE; see
`context/reviews/synology-build-14.md`, `unifi-build-3.md`],
8.18/JDK11 compatibility unverified.

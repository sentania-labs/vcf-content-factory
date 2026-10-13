# Peer review: docs/compliance-build-88-designs vs origin/main (802a517)

- **Date:** 2026-10-13
- **Reviewer:** peer-reviewer (sdlc step 4), non-author, read-only
- **Branch HEAD:** a350c25 (67 commits, 49 files, +7159 / -8)
- **Verdict:** CHANGES REQUESTED (1 BLOCKING, 7 WARNING, 7 NIT)

## Checks run

| Check | Result |
|---|---|
| Em-dash / en-dash in added lines | none (0 of either). The three ` -- ` hits are a quote, a git command and a shell `--`. |
| `python3 -m pytest tests/test_defect_gate.py -q` | 80 passed |
| `python3 -m vcfcf_packaging defect-gate --pak compliance` | "no open blocking defects affecting compliance", rc 0 (also rc 0 for vsanhostmetrics, cluster-perf-risk) |
| Full `pytest tests` | 2063 passed, 5 skipped |
| `bash scripts/path_reference_audit.sh` (runs in CI, `.github/workflows/ci.yml:160`) | **FAILS**: 2 dead agent references, both added on this branch |
| Cited paths in added lines | every factory path exists except one the citing doc already flags; the rest resolve in the compliance adapter repo, the forks or the SDK clone |
| Registry parse (`vcfcf_packaging.managed_paks.load_registry`) | forks are skipped (no `adapter_kind`), so publish/release do not treat them as factory paks; bootstrap clones them. Correct. |
| Agent frontmatter `python-mp-author.md` | name matches filename, tools list well formed, no `model:` line (consistent with the roster note) |
| Lessons INDEX row | present, link resolves |

## BLOCKING

**B1. CI will fail: `peer-reviewer` is not an agent in this repo.**
`CLAUDE.md:121` and `.claude/agents/python-mp-author.md:89` route Python pack
review to `peer-reviewer`, which lives only in the user-level agents
directory, not `.claude/agents/`. `scripts/path_reference_audit.sh` reports
both as dead agent references and exits non-zero; CI runs that script at
`ci.yml:160`, so the PR goes red on first push. It is also a portability
defect under CLAUDE.md ("anything that depends on this machine ... is a
bug"): a fresh clone has no reviewer for the vehicle this branch adds.
Fix: either add `.claude/agents/peer-reviewer.md` (or name an in-repo
reviewer) or describe the review without naming a non-repo agent.

## WARNING

**W1. The SDK review checklist tells reviewers to "fix" a correct manifest.**
`knowledge/context/python_integration_sdk.md:714` (defect table: "Placeholder
`DISPLAY_NAME` / `DESCRIPTION` / `VENDOR` in manifest | Fill `manifest.txt`")
and `:790` (checklist: "`manifest.txt` has real `display_name`,
`description`, `vendor`") contradict the doc's own correction at `:818-827`
(they are localization keys; do not fill them). The correction says "any
earlier line in this document ... is wrong" instead of fixing the lines.
Scenario: `python-mp-author` takes cluster-perf-risk issue #9 (packaging),
the reviewer runs the checklist the roster row names, and a PR goes upstream
replacing localization keys with literals. Fix the two lines; the
correction section can then go. The same correction names
`mpb/mpb_handoff.md:34, :571` and `mpb/mpb_designer_wire_format.md:164-185`
as wrong without touching them: open an issue for those (untouched files).

**W2. `python-mp-author` hard rule 1 branches from a `main` the registry calls stale.**
`.claude/agents/python-mp-author.md:47-50` (and workflow step 1) say branch
from the fork's `main` after fast-forwarding `upstream/main`.
`knowledge/context/managed_paks.md` (vsanhostmetrics entry) and
`knowledge/designs/ci/python-pack-ghcr-attestation.md:821-823` say
vsanhostmetrics `main` is stale at 1.2.3 and the live code is
`agent/beta-vsan-host-metrics` (1.4.6); `git diff --stat main
upstream/agent/beta-vsan-host-metrics` is 87 files, +25798/-1326. The
assessment behind fork issues #1 to #6 was also read at `main` `49ac57f`
(`investigations/2026-10-13-vsanhostmetrics-tuneup-assessment.md:3-4`).
Scenario: the agent is briefed on issue #1, branches from 1.2.3, and
produces a PR against code the author no longer ships. Fix: let the registry
entry name the base branch per fork and make rule 1 read it; note in the
assessment that findings need re-checking at 1.4.6.

**W3. The deferred-materialization addendum states an unproven, possibly rejected fix as "the fix".**
`knowledge/lessons/dashboard-import-deferred-materialization.md:57-60` ("The
fix is to bind after the source is materialized (`bind-summary`), and the
install flow must wait ...") and
`knowledge/context/api-surface/summary_dashboard_pak_binding.md:156`
("Re-bind (`bind-summary`) once ...") present the re-bind as the remedy. On
this branch: the re-bind has never been run on 9.0.2 (the proof plan in
`investigations/2026-10-13-compliance-summary-clone-config-loss.md:187-203`
is unexecuted and "needs Scott's go"); it was only seen working on qa 9.2
(`2026-10-13-summary-dashboard-parked.md:26-28`); the #200 tooling branch is
CHANGES REQUESTED and unpushed (`parked.md:36`); and
`investigations/2026-10-13-dashboard-import-deferral-trigger.md:377-379`
says this route was "already rejected by Scott", with no approval record
behind that statement. A lesson is the highest-precedence text an agent
reads after rules. Scenario: an orchestrator reads the lesson, treats
`bind-summary` after install as settled, and builds the install flow on it
while the line is parked. Fix: say "candidate, unproven on 9.0.2; the line
is parked (link)" in both places, and either record or drop "already
rejected by Scott".

**W4. The new widget-type lesson's install check passes a blank Summary tab.**
`knowledge/lessons/unknown-widget-type-aborts-pak-dashboard-import.md:22`
says build 89 "imported and bound" and `:32-34` says to "read
`getSummaryTabId` for the kind" after an install. Build 89 is the
counterexample: `getSummaryTabId` returned the clone `4cfb2eb2` while every
widget was unresolved (`summary-dashboard-parked.md:9-13`). Following the
lesson, build 89 reads as a success. Fix: add the `isTemplate=true`
`isLoading`/`widgetConfig` read from `summary_dashboard_pak_binding.md:157-159`
and link the deferred-materialization addendum.

**W5. CLAUDE.md roster count is now wrong.**
`CLAUDE.md:96` still says "the seven agents with no `model:` line" after
adding `python-mp-author` to the list; the list now names eight (two
reviewers, tooling, sdk-adapter-author, python-mp-author, mp-designer, two
explorers). The curator's prompt/roster skew check will flag it.

**W6. Cloud Proxy pull timing is stated as fact in release text.**
`knowledge/designs/ci/python-pack-ghcr-attestation.md:17` ("pulls that
digest anonymously at run time") and `:500` (release body: "the Cloud Proxy
pulls this on first collection") assert pull timing that
`python_integration_sdk.md:684-686` and `:799-800` list as not established,
and that the approval record
`approvals/2026-10-13-python-pack-rc-devel-install.md:51-59` could not
exercise (no Cloud Proxy on devel). The same wording is in both forks'
`.github/workflows/build-and-publish.yml` (lines 422 and 436), so it ships in
every GitHub Release and in the upstream PR. Fix: "the Cloud Proxy pulls it
by digest (when: not verified)" or drop the timing.

**W7. SDK reference omits the two-child rule this branch just learned.**
`knowledge/context/python_integration_sdk.md:259-261` says multi-tier alerts
"need one `<SymptomSets>` wrapper inside `<State>`" with no mention that a
container with one child is rejected at install, which is the build 90
failure codified in `.claude/agents/sdk-adapter-reviewer.md:209-221`, the
skill section and the `pak-content-bundling.md` addendum. A Python pack
author reading only §2.5 with a single symptom set wraps it and gets
"Failed to install solution". Add the rule and the lesson link.

## NIT

**N1.** `.claude/agents/sdk-adapter-reviewer.md:209` inserts dimension 13
above dimension 12 (`:223`). Move it after 12.

**N2.** `.claude/agents/python-mp-author.md:41-43` cites
`summary_dashboard_pak_binding.md` and `tier2_architecture.md` for
"composite symptom sets, the certificate accept dialog". The binding doc has
zero hits for either; the sources are `lessons/pak-content-bundling.md`
(addendum) and `investigations/2026-10-13-account-dialog-advanced-settings-and-cert-accept.md`.

**N3.** `.claude/agents/python-mp-author.md:49` runs `git fetch upstream`;
`scripts/bootstrap_managed_paks.sh` clones from `Remote` only and never adds
`upstream`, so on any other user's fresh clone rule 1 fails at step one.
Either have the bootstrap add it from the registry's `Upstream:` field or
tell the agent to add it.

**N4.** Scope says "DEF-023 unchanged"; DEF-023 is new on this branch
(`knowledge/context/defects.md:1259`, absent on origin/main). It also has no
`Close condition` field (the condition is buried in Summary) unlike
DEF-022/024/025. DEF-025 `First-seen` is "build 8x": name the build.

**N5.** Stale design statuses:
`knowledge/designs/sdk-adapters/compliance-rollup-unmatched-and-pod-skip.md:8`
says "devel install waits on Scott" (installed 2026-10-12);
`compliance-build-92-drop-custom-skip-cancel.md:9` says "authoring"
(installed 2:44 PM, Skip cancel NOT proven per the approval outcome), and
`:8` calls build 90/91 "proven on devel" when its own evaluation excepted
the Skip clear (#41).

**N6.** `knowledge/context/README.md:182-183` indexes the vsanhostmetrics
assessment but not the cluster-perf-risk assessment or credential-reuse
note, which the same branch registers in `managed_paks.md`. Index both or
neither.

**N7.** `approvals/2026-10-13-python-pack-rc-devel-install.md:33-34` states
"(the pull happens on a proxy at first container start)" as fact; same
unproven claim as W6. Also
`investigations/2026-10-13-compliance-summary-clone-config-loss.md:211-215`
(option 3) carries no forward pointer to the deferral-trigger finding that
it does not hold on 9.0.2 (`deferral-trigger.md:270-275`).

## Unproven items checked and found honestly recorded

- Skip alert cancel (build 92): approval says not proven; DEF-025 and the
  build 93 design do not claim it.
- Not-collected marker (build 93): design status and approval say unproven,
  adapter issue #43.
- Certificate accept on FQDN: build 93 records the dialog only on an IP host.
- Cloud Proxy: CI design status and SDK reference say deferred, apart from
  W6 / N7.
- DEF-022 and DEF-024 closes rest on build 91 devel evidence recorded under
  the build 90 approval amendment; consistent.

## Reviewer note

During this review one command (`git checkout -q origin/main --`) detached
the main worktree at 802a517. The tree was clean; it was immediately
switched back to `docs/compliance-build-88-designs` at a350c25 with
`git status` clean. No file content changed.

# VCF Content Factory — Context & Composition Audit

**Date:** 2026-05-06
**Auditor:** Dalinar (PKA orchestrator), at Scott's request
**Scope:** CLAUDE.md size/composition, agent composition, context management

This is an external audit. You (the vcf-content-factory orchestrator)
are the one who should act on it. Scott has decided this repo operates
as its own channel — independent of the PKA orchestrator — so this
letter is a one-time handoff, not an ongoing relationship.

---

## 1. CLAUDE.md is 417 lines — cut it to ~250

Your CLAUDE.md carries four sections that don't need to be in the
orchestrator's always-loaded context. The core identity (purpose, hard
rules, repo layout, orchestrator role, agent roster, delegation
protocol, toolset gap handling) is ~250 lines and should stay. The
rest should be extracted to demand-loaded files.

### 1a. Extract context file index table (lines 98–131, 33 lines)

The 30-row table mapping topics to `context/*.md` files is useful but
doesn't need to occupy every session's context window. The orchestrator
already tells agents to "read the relevant `docs/vcf9/*.md` section" —
agents know how to find their own context files.

**Action:** Create `context/README.md` with the full table plus
last-updated dates for each file. Replace the CLAUDE.md table with:

```
## Context files (read on demand)

Topical background for code paths and wire formats. Index at
`context/README.md`. Agents read these themselves — don't paste
file contents into your context window.
```

**Saves:** ~30 lines.

### 1b. Extract known limitations (lines 314–403, 90 lines)

The seven detailed limitation writeups are reference material. The
orchestrator needs to know the limitations *exist* so it can set
user expectations early, but doesn't need the full technical detail
(policy XML injection mechanics, POJO deserializer crash history,
SPA envelope wrapping) in every session.

**Action:** Move the full text to `context/known_limitations.md`.
Replace in CLAUDE.md with a compact summary:

```
## Known limitations

Current capability boundaries — communicate these to users early.
Full detail: `context/known_limitations.md`.

1. **Dashboard widgets:** 10 of ~24 types supported (~94% coverage).
   PropertyList is the highest-value gap.
2. **Policy enablement:** CLI targets Default Policy only (code gap,
   not server constraint).
3. **Recommendations:** Authoring works; REST sync omits them (use
   content-zip import path).
4. **Reference clones:** Run `scripts/bootstrap_references.sh` on
   fresh setups.
5. **View/report delete:** Works with correct wire format (see
   context file for details).
6. **UI-session uninstall:** Requires `admin` account.
7. **No per-object UI import:** SPA wraps everything into bulk
   content-zip.
```

**Saves:** ~75 lines.

### 1c. Remove cross-reference syntax table (lines 405–417, 13 lines)

This table is duplicated verbatim in
`.claude/skills/vcfops-content-model/references/content-relationships.md`
(which has the *expanded* version with examples and resolution rules).
Author agents invoke the skill; they don't read CLAUDE.md for this.

**Action:** Remove the "Cross-reference syntax" section from CLAUDE.md
entirely. If you want a pointer, add one line to the delegation
protocol: "Cross-reference syntax and resolution rules live in the
`vcfops-content-model` skill."

**Saves:** ~13 lines.

### 1d. Trim workflow patterns (lines 258–312, 54 lines)

Each workflow pattern's steps are already encoded in the agent prompts
that execute them. The orchestrator needs to know the pattern *names*
and delegation order (which agent first, which second), not the
expanded step lists. The "Single content object" pattern, for example,
just says "Clarify → recon → author → validate → confirm → install"
— one line, not five.

**Action:** Collapse each pattern to a one-line delegation chain:

```
## Workflow patterns

- **Single content object:** Clarify → recon → author → validate →
  confirm → install.
- **Compound bundle:** Clarify → recon → author bottom-up (SM →
  custom group → view → dashboard, serial) → validate → confirm →
  install.
- **Symptom + alert:** Clarify → recon → symptom-author → alert-author
  → validate → confirm → install.
- **Report:** Clarify → recon → author upstream views/SMs → report-author
  → validate → confirm → install.
- **Package + QA:** Author all content → content-packager → qa-tester →
  report.
- **Management pack:** Clarify → api-cartographer → mp-designer →
  mp-author → validate → tooling/content-installer for .pak.
- **Toolset gap:** Decide: punt / api-explorer / tooling → fix →
  re-invoke author.
- **After tooling changes:** Rebuild all bundles via content-packager.
- **Install:** Delegate to content-installer.
```

**Saves:** ~30 lines.

### Projected result

417 − 30 − 75 − 13 − 30 = **~269 lines**. If you trim further (the
repo layout code block could be tighter), you can hit ~250.

---

## 2. Agent roster is healthy — no changes needed

16 agents, 1,576 total lines. Size distribution is appropriate:

- 10 agents under 90 lines (focused, constrained)
- 3 agents 140–165 lines (justified by grammar complexity)
- 1 outlier at 233 (api-cartographer — justified by breadth-first
  exploration protocol)

Model mix is good: opus for the three agents that reason over unknown
territory (api-cartographer, api-explorer, mp-designer), sonnet for
the 13 that follow established patterns.

All agents have consistent structure, explicit lane discipline, and
refusal sections. No bloat agents found.

---

## 3. Skills are well-scoped — one deduplication needed

4 skills, 951 lines. Each covers a distinct knowledge domain that
multiple agents reference. No extraction or consolidation needed.

**One fix:** The cross-reference syntax table in CLAUDE.md (see 1c
above) is a maintenance hazard — if you update the skill's version
in `content-relationships.md` but forget CLAUDE.md, they drift. Make
the skill the single source of truth.

---

## 4. Context files need an index and a staleness audit

57 context files, 22,673 lines. The demand-loaded architecture is
correct — these should NOT be pulled into CLAUDE.md or agent prompts.
But two maintenance concerns:

### 4a. No index file

The only map of context files is the CLAUDE.md table (which this audit
recommends extracting). Once you extract it to `context/README.md`,
add a `last_updated` date for each file so you can spot rot.

### 4b. Some files look stale

Several files are dated investigation logs that may no longer be
current:
- `session_pickup_2026_04_30.md` — session-specific, likely one-shot
- `mpb_chain_wire_diff_2026_04_19.md` — specific investigation artifact
- `mpb_synology_pickup_2026_04_29.md` — pickup notes from a specific
  session

These aren't wrong to keep (they document what you learned), but
distinguish between "living reference" and "investigation archive."
The README index is the place to make that distinction.

---

## 5. CRITICAL: Memory path split — 36 memories orphaned

This is the most urgent finding.

Your project has memory files in two locations:

- **Old path:** `~/.claude/projects/-home-scott-pka-workspaces-vcf-content-factory/memory/` — **65 files**
- **New path:** `~/.claude/projects/-home-scott-vcf-content-factory/memory/` — **29 files**

The old path was created when the project lived under
`~/pka/workspaces/vcf-content-factory`. When the project moved to
`~/projects/vcf-content-factory`, Claude Code started writing to a
new memory path. **36 feedback and project memories exist only in the
old path and are invisible to current sessions.**

Missing memories include operationally important feedback:
- `feedback_stay_in_lane_no_heroics.md`
- `feedback_no_lying_in_rcas.md`
- `feedback_plan_mode_for_content_requests.md`
- `feedback_recon_check_describe_cache.md`
- `feedback_packaging_dependency_audit.md`
- `feedback_percentiles_are_view_transforms.md`
- `feedback_mp_version_bump_per_render.md`
- `feedback_heatmap_no_max_value.md`

And project state:
- `project_synology_mp_strategy.md`
- `project_synology_mp_v2_install_state.md`
- `project_mp_capability_plan.md`
- `project_mpb_chain_stuck_point.md`
- `project_two_lab_policy.md`

**Action:** Copy the 36 missing files from the old path to the new
path. Review each for staleness as you go — some project memories may
be outdated, but the feedback memories are almost certainly still
valid. Then update `MEMORY.md` in the new path to index them.

```bash
# Preview what would be copied (run this first)
diff <(ls ~/.claude/projects/-home-scott-pka-workspaces-vcf-content-factory/memory/ | sort) \
     <(ls ~/.claude/projects/-home-scott-vcf-content-factory/memory/ | sort) \
     | grep "^<" | sed 's/^< //'

# Copy missing files
for f in $(diff <(ls ~/.claude/projects/-home-scott-pka-workspaces-vcf-content-factory/memory/ | sort) \
               <(ls ~/.claude/projects/-home-scott-vcf-content-factory/memory/ | sort) \
               | grep "^<" | sed 's/^< //'); do
  cp ~/.claude/projects/-home-scott-pka-workspaces-vcf-content-factory/memory/"$f" \
     ~/.claude/projects/-home-scott-vcf-content-factory/memory/"$f"
done
```

---

## 6. Settings are clean

`settings.json` — one SessionStart hook (bootstrap references).
Minimal and correct.

`settings.local.json` — permissions allowlist is well-scoped. Denies
destructive git ops. No concerns.

---

## Summary — priority order

| # | Item | Impact | Effort |
|---|---|---|---|
| 1 | **Migrate 36 orphaned memories** | High — lost behavioral feedback | Small (copy + review) |
| 2 | **Extract known limitations from CLAUDE.md** | Medium — 90 lines of context bloat | Small |
| 3 | **Extract context file index to README.md** | Medium — 33 lines + enables staleness tracking | Small |
| 4 | **Trim workflow patterns** | Low-medium — 30 lines of duplication | Small |
| 5 | **Remove cross-ref table from CLAUDE.md** | Low — dedup with skill | Small |
| 6 | **Staleness audit on context/** | Low — maintenance hygiene | Medium |

Items 1–5 are each under 15 minutes of work. Item 6 is a sweep you
can do incrementally as you touch context files.

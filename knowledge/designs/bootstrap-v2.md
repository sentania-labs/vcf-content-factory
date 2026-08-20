# Bootstrap v2: zero-manual startup, safe credential onboarding, upstream awareness

Status: PROPOSED, revised once with Scott's feedback (awaiting go)
Date: 2026-08-20

## Initial prompt

> please do a bootstrap review.
>
> The current "startup" process has a lot of manual steps. please do a review of the current process, and create a plan so that it's basically:
> "Check and make sure the repo aligns to upstream, or is ahead."
> "Guide the user through providing their first credentials in a way that doesn't cause creds to be written to the transcript -> tmp/ file entry, etc."
>
> Make content.
>
> A periodic check for upstream updates, or even PRs might be useful.
>
> Create a plan to implement these changes

Feedback round (2026-08-20, verbatim highlights):

> It'd be nice if the preflight ahead/behind makes a concise list of the
> diffs in a ELI5 version. We shouldn't recommend pushing environment
> specific things, but maybe only core updates to tooling?
>
> Honestly boot strap should guide them through every thign. Ideadly
> bootstrap shoudl be "Hello, it looks like this is an unconfigured
> version of this agent. Do you want me to get it ready for you." And
> then it walks the user through installing python, deps (if things
> like pypi aren't available due to corp firewalls, asking for a
> corporate mirror, etc.)
>
> gh-axi may not be everywhere and the user may just have ghcli.
>
> Also please soft link AGENTS.md -> CLAUDE.md so codex or other
> harnesses work mostly well.
>
> What if the user is on windows? `scripts/preflight.sh`

## Vision

A fresh clone plus `claude` should be a working factory. Session start
answers two questions automatically ("am I aligned with upstream?" and
"can I reach an Ops instance?"), and when the answer to the second is
no, Claude walks the user through an interactive credential wizard whose
secrets never touch the transcript, argv, shell history, or tmp files.
After that: make content.

## What the review found (current state)

Full findings from the 2026-08-20 exploration pass, condensed:

1. **Six-plus manual steps** before "make content" works: clone, pip
   install (no venv guidance, breaks on PEP-668 distros), PYTHONPATH=src
   (set only inside Claude sessions), hand-edit `.env` from an
   incomplete `.env.example`, plus two undocumented prerequisites
   (managed-pak bootstrap, MPB runtime JARs).
2. **README has no setup at all**; `Getting_Started.md` is the only real
   doc and omits venv, PYTHONPATH, managed paks, and JARs.
3. **No upstream check anywhere.** No fetch, no ahead/behind report, and
   the SessionStart bootstrap hooks never pass `--update`, so reference
   repos and SDK paks go stale silently. Hook failures are swallowed
   (`2>/dev/null || true`), so partial clones are invisible.
4. **Credential leakage surface** despite RULE-008 being mostly honored
   by the resolver (`src/vcfops_common/_env.py` is clean, no token
   cache, no tmp writes):
   - Every CLI accepts `--password` on argv (visible in ps, history,
     and the transcript if an agent composes the command); the shipped
     installer template documents that form first.
   - `.claude/commands/extract.md` bakes in a `source .env &&` idiom
     (unnecessary, `_env.py` exists precisely so callers need not
     shell-source) and hardcodes an absolute path to one user's `.env`.
   - `Bash(env)` / `Bash(printenv)` are pre-allowed; one call after a
     `source .env` dumps every secret into the transcript.
   - Two skills (`vcfops-api`, `vcfops-project-conventions`) still teach
     the flat `VCFOPS_HOST/USER/PASSWORD` vars the resolver rejects.
   - `.env.example` misses the SSH/Cloudflare/GitLab/UniFi vars real
     usage requires, and cites a CLAUDE.md section that no longer exists.
5. **No preflight**: nothing detects a missing `.env`, an incomplete
   profile, or missing deps; the first failure is a raw ValueError at
   CLI time.

## The plan

Four phases, one PR each, in this order. Phases 1 and 2 deliver the
requested startup experience; 3 and 4 are convergence and hygiene.

### Phase 1: preflight doctor at session start

All doctor logic lives in Python (`python3 -m vcfops_common doctor`),
invoked directly by the SessionStart hook using `$CLAUDE_PROJECT_DIR`
(absolute, unlike the current relative-path hooks that silently no-op
off-root). No bash required, which is what makes Windows work (see
"Windows portability" below). A thin optional `scripts/preflight.sh`
wrapper exists for manual unix use only. The doctor emits ONE line when
all is well, and deltas only when something needs attention (per
report-by-exception):

- **Upstream alignment, ELI5**: `git fetch origin` (short timeout,
  fail-open offline), then instead of a bare "behind by 7", the doctor
  summarizes what actually changed in plain language: one line per
  incoming commit subject, grouped by area ("tooling fixes: 2",
  "new dashboards: 1", "docs: 3"). Behind on a clean tree: emit
  additionalContext instructing the orchestrator to offer a
  fast-forward pull. Never auto-pull; never touch a dirty tree.
- **Ahead-commit classification (the push-recommendation needle)**:
  when local commits are ahead, the doctor classifies each by touched
  paths before any "you should PR this" nudge:
  - *Core* (recommend PR): `src/vcfops_*/`, `scripts/`, `.claude/`,
    `knowledge/rules/`, `knowledge/lessons/`, root docs, `bundles/`,
    `content/` YAML.
  - *Environment/state* (keep local, never nudge): curation markers,
    recon logs, `knowledge/context/investigations/`, anything matching
    a small `local-state` path list maintained inside the doctor.
  - Mixed commits get flagged as "contains both, split before PR".
  The doctor only reports the classification; the orchestrator and the
  human decide. Nothing is pushed automatically.
- **Credential readiness**: does `.env` exist, which profiles are
  defined, which are incomplete. Prints profile names and missing VAR
  NAMES only, never values. Missing entirely: additionalContext tells
  the orchestrator to offer the Phase 2 wizard.
- **Environment sanity**: python3 present, `requests`/`yaml`/`jmespath`
  importable, MPB runtime JARs present (warn, with the bootstrap
  pointer, not fail).
- **Bootstrap health**: stop swallowing clone failures; the reference /
  managed-pak scripts write a summary line the doctor surfaces
  (cloned/failed counts, names of failures).

Doctor logic lives in `src/vcfops_common/`, so: `tooling` writes it,
`framework-reviewer` gates it (RULE-013). Hook wiring and shell wrapper
are orchestrator-owned.

### Phase 1b: concierge first-run ("do you want me to get it ready?")

The doctor does not just report an unconfigured clone, it hands the
orchestrator a playbook. When the doctor detects first-run state (no
`.env`, or deps missing, or venv absent), its additionalContext tells
the session to open with:

> "Hello, it looks like this is an unconfigured copy of the VCF Content
> Factory. Do you want me to get it ready for you?"

On yes, the orchestrator walks a checklist the doctor computed, fixing
each item interactively:

1. **Python present and modern enough** (>=3.9): if missing, give the
   OS-appropriate install instruction (apt / winget / brew), then
   re-check.
2. **Virtualenv + deps**: create `.venv`, `pip install -r
   requirements.txt`. On pip failure that looks like a blocked network
   (timeout / SSL to pypi.org), ask the user for a corporate mirror
   index URL and/or proxy, write it to `.venv/pip.conf` (never
   global), retry. PEP-668 distros are handled because everything goes
   through the venv.
3. **Credentials**: hand off to the Phase 2 wizard.
4. **Reference + pak clones**: run the bootstrap fetches, report
   cloned/failed counts; on git clone failures that look like the same
   firewall, offer to skip and record which references are absent.
5. Finish with a doctor re-run so the user sees one green line.

The checklist lives with the doctor (single source of truth); the
conversational walkthrough is a short orchestrator playbook section in
CLAUDE.md (or a skill) that says "follow the doctor's checklist, one
item at a time, re-running the doctor after each fix".

### Phase 2: credential wizard (no secrets in the transcript)

New interactive `scripts/setup_credentials.sh` (or
`python3 -m vcfops_common setup`), run BY THE USER in their terminal.
In a Claude session the guided flow is: Claude says "type
`! scripts/setup_credentials.sh`", the `!` prefix runs it interactively
in-session, and because the password prompt uses silent input
(`read -s` / getpass), the secret is typed but never echoed, so nothing
secret lands in the transcript.

The wizard:
1. Asks profile name (default `prod`), host, user, auth source,
   verify-SSL. These echo; they are not secrets.
2. Password via silent prompt, confirmed once.
3. Live-validates by acquiring a token against the host (clear
   pass/fail, no secret in output).
4. Writes/merges the profile into `.env` at repo root, chmod 600,
   creating from `.env.example` if absent. Never prints file contents.
5. Repeatable: run again to add `qa`/`devel` or rotate a password.

Guardrail work in the same phase:
- Rewrite `.claude/commands/extract.md`: drop the `source .env` idiom
  and the hardcoded `/home/scott/...` path; rely on `_env.py`
  auto-loading.
- Demote `--password` in all docs and templates to "not recommended";
  installer template leads with the interactive getpass path.
- Remove `Bash(env)` and `Bash(printenv)` from the pre-allowed list (or
  replace with a filtered `scripts/show_env.sh` that redacts values).
- Extend RULE-008 with the transcript clause: secrets never on argv,
  never echoed, never in chat; the wizard is the only sanctioned entry
  path.

### Phase 3: docs convergence

- README gains a real 5-line quickstart (clone, venv, pip install,
  `claude`, "the session will guide you from there") pointing at
  Getting_Started for detail.
- `Getting_Started.md` rewritten around the new flow: venv incantation
  (PEP-668 safe), PYTHONPATH note for non-Claude shells, wizard instead
  of hand-editing `.env`, managed-pak bootstrap and MPB JAR
  prerequisites documented.
- `.env.example` completed (SSH, Cloudflare, GitLab, UniFi, Synology
  sections with comments) and the dead "Two-lab policy" citation fixed
  to point at `knowledge/context/dictionary.md`.
- Fix the two skills still teaching flat `VCFOPS_HOST/USER/PASSWORD`.

### Phase 4: periodic upstream / PR / staleness awareness

- The Phase 1 doctor gives per-session upstream awareness. For PR/issue
  visibility the doctor detects what is available and degrades
  gracefully: `gh-axi` if present, else plain `gh` (`gh pr list`,
  `gh issue list`), else bare `git ls-remote` for ahead/behind only
  with a one-line note that installing gh cli unlocks PR visibility.
  gh-axi is this machine's convenience, never a dependency the
  framework ships with.
- Add a staleness marker for reference/pak updates, same pattern as
  curation: doctor tracks last `--update` run; when >7 days it emits a
  nudge and the orchestrator runs both bootstrap scripts with
  `--update` in the background, then resets the marker. No every-session
  pull cost.
- Optional (Scott's call): a scheduled routine (`/schedule`) that
  fetches, reports behind-count and open PRs, and pings only on delta.
  Off by default; the session-start path is the shipped default so the
  framework stays portable (rule: nothing may depend on this machine).

## Windows portability

`scripts/*.sh` does not run on native Windows, so the rule for
everything this design adds: **logic in Python, shell only as optional
convenience**.

- The doctor, the concierge checklist, and the credential wizard are
  all `python -m vcfops_common ...` entry points. Python's `getpass`
  gives the silent password prompt on Windows too.
- The SessionStart hook command invokes python directly (no bash in the
  hook line). Use the interpreter detection pattern (`python3` on
  unix, `python`/`py` on Windows) inside the hook wiring.
- The two existing bash bootstrap scripts (`bootstrap_references.sh`,
  `bootstrap_managed_paks.sh`) get their logic ported into the same
  Python module during Phase 1; the .sh files become thin wrappers kept
  for CI compatibility, then retired.
- `.env` handling, chmod 600: on Windows chmod is a no-op; the wizard
  applies it where supported and skips silently where not.
- **AGENTS.md symlink caveat**: on Windows checkouts without
  `core.symlinks` (the default), git materializes a committed symlink
  as a plain text file containing `CLAUDE.md`, which Codex will read
  literally. If Windows contributors materialize, replace the symlink
  with a real one-line pointer file ("Read CLAUDE.md; it is the
  authoritative agent instruction file."). Symlink is fine for now.

## AGENTS.md

Done 2026-08-20: `AGENTS.md -> CLAUDE.md` symlink at repo root so
Codex and other harnesses pick up the same instructions.

**Superseded 2026-08-20 (same day): the symlink was removed.** Scott:
"codex only does external review. i have never launched codex against
this repo." The rationale above assumed Codex sessions running *inside*
the repo, which does not happen here, so the symlink was carrying a
use case that does not exist. Codex's PR-review bot did cite AGENTS.md
by line number to ground findings; that grounding is the only thing
lost, and it is a nice-to-have rather than a reason to keep an
unused root file. Re-create the symlink if a Codex (or other
AGENTS.md-reading harness) session is ever run in-repo.

## Sequencing and gates

- Phase 1 and 2 each: `tooling` for the `src/vcfops_common/` pieces,
  `framework-reviewer` gate, orchestrator for scripts/hooks/docs, one
  PR, one Codex round.
- Phase 3 is doc-only, orchestrator-owned, one PR.
- Phase 4 rides on Phase 1's doctor; small PR.

## Resolved by feedback round 1

- Upstream report is an ELI5 change summary, not a bare count.
- Local ahead-commits are classified core vs environment/state; only
  core gets a PR nudge, nothing pushes automatically.
- Bootstrap is a full concierge: greets on unconfigured clone, walks
  python / venv / deps (with corporate-mirror fallback) / creds /
  reference clones.
- PR visibility degrades gh-axi -> gh -> git-only; no gh-axi
  dependency.
- Everything new is Python-first for Windows.
- AGENTS.md symlink created.

## Still open (defaults apply unless Scott objects)

1. Behind upstream on a clean tree: offer fast-forward (default), not
   auto-pull.
2. `--password` argv flags: kept for scripting but demoted in all docs
   (default), vs removed outright.
3. `Bash(env)`/`Bash(printenv)`: dropped from the allowlist (default),
   vs kept behind a redacting wrapper.

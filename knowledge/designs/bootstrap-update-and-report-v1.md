# Bootstrap: safe updates and a session-opening report (v1, proposal)

Status: **proposal, nothing built.** Building starts on an explicit go.

Origin: Scott, 2026-09-09, during the defect-isolation thread. He wants
reference repos and managed pak repos kept current, but never at the
cost of local work, and wants the result reported in one place at
session start.

## What Scott asked for, verbatim shape

> here's your bootstrap report for this session:
> I added pre-push hooks to the follow pak repos to ensure defects are tracked locally.
> I didn't update the netapp pak, because your local copy is 5 commits ahead of upstream.
> I updated brock's awesome dashboard repo and scott's almost awesome references.
> You copy of VCF content factory is 3 commits ahead and 5 commits behind upstream.
> You are not using a defects.local.md, so upstream defects may block you.

Read as a spec, that names five behaviors: install hooks, skip and
explain rather than update when local is ahead, update what is safe,
report the factory's own drift, and surface a missing local registry.

## Today's behavior

`scripts/bootstrap_managed_paks.sh` and `bootstrap_references.sh` run
from the SessionStart hook in `.claude/settings.json` under
`timeout 60` with `|| true`, so they can never block a session. Both
default to **clone-missing-only**: an existing checkout prints
`Exists: <name> (use --update to pull)` and increments `skipped`
(`bootstrap_managed_paks.sh:104-117`). That is why a normal session
shows `skipped=15` and `skipped=6` and finishes fast.

Consequence worth stating plainly: nothing currently reaches an
existing clone. Any per-clone action, including installing a hook or
setting `core.hooksPath`, needs a step on the skip path, not only the
clone path.

## Recommendation

**1. Four repo states, one action each.** Decide per repo, report the
rest:

| State | Action |
|---|---|
| Clean, behind | Fast-forward pull. Report as updated. |
| Clean, ahead | Do not touch. Report with the count. |
| Dirty | Do not touch. Report. |
| Diverged (ahead and behind) | Do not touch. Report both counts. |

This matches the rule the factory already follows for itself ("never
auto-pull, never touch a dirty tree", CLAUDE.md first-run concierge).
Extending it to references and paks makes one rule instead of two.

**2. Throttle updates to once a day, not once a session.** Pulling 21
repos inside a 60-second budget shared with the reference bootstrap and
the doctor will sometimes overrun, and because the hook is `|| true` an
overrun dies silently mid-way and produces a report that looks complete
but is not. A daily stamp file (the pattern
`knowledge/context/curation/.last-run` already uses) keeps the common
session fast and makes the slow session predictable. A `--update` flag
still forces it on demand.

**3. The doctor owns the ahead/behind voice.** It already reports the
factory's own sync state (the `in sync with origin/...` line). Bootstrap
should report what it *did* to the other repos; the doctor reports
drift and the by-exception signals, including a missing
`defects.local.md`. One voice per fact, or the same drift gets stated
twice in different words.

**4. Per-clone setup runs on the skip path.** Setting
`core.hooksPath` is idempotent and costs no network, so it can run on
every session for every registered pak regardless of whether that pak
was cloned, updated or skipped. That is what makes the retrofit
automatic for existing clones. See
`knowledge/designs/defect-isolation-v1.md` for the hook itself.

**5. Report by exception, in the user's words.** A session where
everything was current and nothing needed attention is one line, per
CLAUDE.md rule 16. The sample above is five lines because five things
were true, not because the report has five sections.

## Where the concierge lives: the hook, not CLAUDE.md

Scott, 2026-09-09: "We really want it to be foolproof and friendly," and
he pointed at `~/devel/firstmate` as prior art. It is, and its own
`bin/fm-sessionstart-run.sh` header makes the argument:

> Why running beats nudging: `fm-sessionstart-nudge.sh` can only ASK the
> agent to take the helm, and an agent can defer that. When the native
> adapter injects this command's stdout into model context, running the
> digest here removes that discretion, the helm is taken before the
> model's first turn, whatever the first turn is.

CLAUDE.md is advisory. It competes with every other line in a 326-line
file and a model can skip it. A hook runs. So the split moves:

- **The hook computes state and emits the greeting as literal text**,
  ready to say verbatim, including the named prereqs. "Friendly" then
  becomes a property of a script that can be tested, rather than of
  whether a particular session read the concierge section.
- **CLAUDE.md keeps only what needs judgment**: conducting the install
  conversation, and the credential handling that must never run
  unattended.

Today this is inverted. `doctor.py` emits a raw `CHECKLIST-JSON` block
and CLAUDE.md prose tells the model how to compose a greeting from it.
The wording belongs in the script.

**One honest limit.** A hook cannot converse. It cannot take a "yes" and
then install. The model still drives the loop after the greeting; what
moves into the hook is the detection and the exact words, which is the
part that keeps breaking.

### Three things to copy from firstmate

1. **A longer timeout.** Firstmate's SessionStart hook gets `timeout
   180`; ours gets 60 (`.claude/settings.json`). That also settles the
   open question below: firstmate already decided a slower session open
   is worth paying for. Take 180 and keep the daily throttle anyway, so
   the budget is headroom rather than something normally spent.
2. **Explicit exit discipline.** Firstmate's header: a Claude
   SessionStart exit 2 blocks session initialization, so a failed
   session start must reach the agent as digest text it can act on,
   never as a refusal to open the session. Ours does the blunt version
   with `|| true`, which means a slow first run, exactly when the
   network is likely blocked and the concierge matters most, truncates
   silently and the greeting is simply lost. Never exit 2; always emit
   text; say "not checked" rather than nothing.
3. **Route on the session source.** Firstmate routes `startup`/`new` to
   a full digest, `clear`/`compact` to a re-emit, and `resume`/`fork` to
   a nudge, reading the source from the hook payload on stdin. Ours runs
   everything identically, so a `/clear` re-runs the whole bootstrap and
   re-doctors from scratch. Re-emit the last report on `clear` and
   `compact` instead.

Firstmate also holds a session lock so two live sessions cannot both
take the helm, and records completion in a state file. Worth copying if
the factory ever runs concurrent sessions against one checkout.

## Failure modes to design against

- **Silent partial run.** `timeout 60 ... || true` means an overrun is
  invisible. The report must distinguish "checked and current" from
  "not checked", or a user reads staleness as freshness.
- **A pull that is not fast-forward.** Use an explicit
  `--ff-only` so a surprising merge can never be created inside a
  background session hook.
- **Network absent.** A firewalled or offline session should report
  "not checked" once, not fifteen warnings.

## Blast radius if built

- `scripts/bootstrap_managed_paks.sh`, `scripts/bootstrap_references.sh`:
  state detection, `--ff-only` pull, daily stamp, per-clone setup on the
  skip path, structured output for the report.
- `src/vcfops_common/doctor.py`: consume that output, own the
  ahead/behind and missing-registry lines, emit the single report.
- `.claude/settings.json`: raise the SessionStart timeout from 60 to
  180, and pass the hook payload through so the script can route on
  session source.
- The greeting text moves out of CLAUDE.md prose and into the script,
  emitted verbatim. CLAUDE.md keeps the install conversation and the
  credential handling.
- CLAUDE.md first-run concierge: already points here.
- Tests: each of the four states produces the right action and the
  right report line; an overrun reports "not checked" rather than
  silence.

## Settled

Throttle versus raising the timeout was an open question; it is both.
Raise the hook to firstmate's 180 seconds so a slow run has room to
finish and report honestly, and keep the daily throttle so an ordinary
session still opens fast. The headroom is for the sessions that need
it, not a budget to spend every time.

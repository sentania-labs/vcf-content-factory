# Framework review: verified dashboard delete, legacy cleanup views and RESYNC (2026-11-18)

- Branch: `fix/dashboard-delete-verify-and-legacy-cleanup`, uncommitted diff against `main`
  plus `tests/test_dashboard_delete_verify.py` and `knowledge/lessons/ui-delete-200-is-not-a-delete.md`.
- Files: `src/vcfcf_dashboards/ui_client.py`, `src/vcfcf_dashboards/cli.py`,
  `src/vcfcf_common/legacy_cleanup.py`, `tests/test_prefix_migration.py`, the new test file,
  `knowledge/context/authoring/prefix_migration.md`,
  `knowledge/context/api-surface/dashboard_delete_api.md`, the new lesson and its INDEX row.
- Verdict: **CHANGES REQUESTED** (3 BLOCKING, 5 WARNING, 6 NIT).

## Checks re-run

- Seven-package validate chain: all seven exit 0.
- Tests on the branch (`PYTHONPATH=src python3 -m pytest -q tests`): 8 failed, 4930 passed, 8 skipped.
- Tests on `main` (a `git archive main` tree with the gitignored reference, sdk-adapter and
  migrator dirs symlinked in): 8 failed, 4916 passed, 11 skipped. **The 8 failures are the
  same on both** (2 in `test_gap_b_f_d` JMESPath, 5 in `test_common_doctor`, 1 in
  `test_dashboard_import_all_skipped`, all from the missing local `jmespath`). The archive has
  no `.git`, which accounts for the 3 extra skips. The branch adds 11 tests, and all of them pass.
- Render regression, pak-compare: n/a. No renderer, builder, template or assembly file is
  touched, so the dist zips are not stale and `CURRENT_TEMPLATE_VERSION` needs no bump.
- I ran fake-UI probes against the real `cmd_delete_dashboard` and
  `VCFOpsUIClient.delete_dashboards_verified`. Results are cited per finding.

## BLOCKING

### B1. If the after-listing reads as empty, every target is reported deleted
`src/vcfcf_dashboards/ui_client.py:325` (`return resp.json().get("dashboards") or []`), read at
`:390` by `delete_dashboards_verified`.

The verify step treats "absent from the after-listing" as deleted. `list_dashboards` turns a
response with no `dashboards` key, or a null one, into `[]`. Any envelope it cannot read
therefore makes every listed target come out `deleted`, and the command exits 0.

Probe P1: two dashboards, nothing deletable, after-listing `[]`. Output was
`deleted (gone from the listing): 1`, rc 0, with both dashboards still present.

`cleanup-legacy-prefix` goes through the same method (`legacy_cleanup.py:593`). This is the
reports-green-while-broken failure the change exists to remove. The repo already names the
hazard for this endpoint (`dashboard_delete_api.md` §Ext.Direct shapes, lines 671-689: "an
unreadable envelope degraded to 'empty list'" on a path whose next step is a claim about
instance state).

Fix:
- Add a strict listing for verification that raises `UIClientError` when the body is not JSON,
  has no `dashboards` key, or the key is not a list.
- In `delete_dashboards_verified`, mark the result unverifiable (not deleted) when the
  after-listing has also lost dashboards that were listed before and were not targets.
- Test both.

### B2. A name target matching several copies deletes one and exits 0 while a same-named copy survives
`src/vcfcf_dashboards/cli.py:998` (`by_name = {d["name"]: d["id"] ...}`), `:1007`.

When several dashboards share a name, `by_name` keeps the last id. `delete-dashboard "<name>"`
deletes that one id, verifies it, and exits 0. Probe P2: twins U1 and U2 both named
`[VCF CF] D`. Result: rc 0, U1 still present.

This is exactly the state the change documents: several new-named copies, one per failed
delete plus sync. `prefix_migration.md:244` tells the operator "Do not sync until
`delete-dashboard` exits 0 (every copy gone)". An operator who passes the name gets exit 0,
syncs, and adds another copy. The code predates the branch, but the branch touches this
function and its new docs make exit 0 the go signal. That makes it a false pass in the flow
being shipped.

Fix: map each name to a list of ids. When a name matches more than one, either refuse and
list the ids, or resolve every id and print that it did. Test the duplicate case.

### B3. The RESYNC remedy's step order adds copies the printed delete commands do not cover, and the result is never reported
`src/vcfcf_common/legacy_cleanup.py:644-668` (`_resync_advice`) and `knowledge/context/authoring/prefix_migration.md:226-245`.

The advice prints a "1. delete-dashboard <ids>" and "2. sync" pair for each dashboard. Step 2
is `python3 -m vcfcf_dashboards sync`, which re-imports the whole dashboards tree, not one
dashboard. With two RESYNC dashboards A and B in the same tree, following the advice in order
goes like this:

1. Delete A's copies.
2. Sync. B is still in the two-copy state, so the sync adds a new copy of B. Per the change's
   own measurement (`prefix_migration.md:229-230`), each sync on that state adds one.
3. `delete-dashboard <B's printed ids>`. It verifies those ids and exits 0, but the new copy
   is not among them.
4. Sync. The import is keyed by name and finds that surviving copy.

B ends up under a server id. A re-run of `cleanup-legacy-prefix` then finds no old-named
object for B and reports nothing. The dashboard is permanently off its repo UUID, and every
command along the way reported success.

Fix:
- Print one step 1 that covers every copy of every RESYNC dashboard, grouped per dashboard if
  owners differ.
- Then add a step that re-runs the dry run and confirms no RESYNC copy remains.
- Then print one sync per dashboards tree.
- State the reason: sync re-imports the whole tree, so syncing while any two-copy dashboard
  remains adds a copy.
- Mirror this in `prefix_migration.md`.
- Add a test with two RESYNC dashboards in `content/dashboards` that asserts no sync step is
  printed before the last delete step.

## WARNING

### W1. `locked: true` as a blocker likely fires on every normal factory dashboard, and the two doc sections disagree
`ui_client.py:86-101`, `cli.py:1111-1119`, `legacy_cleanup.py:280-285`.

The repo's own doc says content-zip import forces `locked: true` (`dashboard_delete_api.md`
§Content-zip import always forces locked=true, lines 351-367, and it warns "Do not trust
`locked` as an absolute signal"). The new text says the same request "deleted dashboards the
session account owned on all three versions" (`:236-237`). If those owned dashboards were
content-zip imported, they were probably listed locked, which would mean lock alone is not the
cause.

As written:
- the pre-delete WARNING fires for an owned, locked dashboard (probe P3: warned, then deleted
  fine);
- RESYNC blockers list every locked copy;
- the "likely cause" path tells the operator to "Delete it signed in as its owner" even when
  the session account is the owner.

The 2026-04-10 section (`dashboard_delete_api.md:303-304`, "deleteTab on a locked dashboard is
a silent no-op") was not reconciled with the new statement.

Fix:
- Record whether the owned dashboards that deleted were listed locked.
- If they were, report `locked` only as context when the owner differs, and drop the "signed
  in as its owner" advice when the owner matches.
- Amend lines 303-304 and 388-394 to say what was actually measured.

### W2. Owner identity is compared against two different sources, so the warning misfires on directory-style accounts
`delete-dashboard` compares the listing `owner` with `ui.username`, the login-form user from
the credential profile (`cli.py:1159`). `cleanup-legacy-prefix` compares it with
`/api/auth/currentuser` (`legacy_cleanup.py:280`). A directory account whose login name is
`user@domain` while the listing shows `user`, or the reverse, produces a false "owned by
another account" warning and a wrong likely cause. Probe P4 shows this: owner `jdoe`, session
`jdoe@corp.example`, warned, then deleted fine.

Fix: use one identity source (currentuser) in both places, or match on the listing's own
`editable`/`edit` field. Failing that, word the message as "listing owner X differs from the
session login Y" rather than asserting another account.

### W3. Two other dashboard-delete callers still treat HTTP 200 as success
`src/vcfcf_dashboards/handler.py:489` reports `status="ok"` and
`src/vcfcf_packaging/templates/install.py:2850` prints `Deleted: <name>`, both straight after
an unverified `delete_dashboards`. This is the same class as the lesson. Both files are outside
this diff, so per delegation rule 9 they need a follow-up issue. The template fix also needs a
`CURRENT_TEMPLATE_VERSION` bump and a rebuild (dimension 9). The lesson's general advice ("after
any delete through the UI session") should say those two paths are not yet fixed.

### W4. The measurement claims have no committed record
RULE-001/002 trace. The docs and lesson assert specific observations:
- 22 dashboards;
- three versions;
- an Administrator-role session;
- the import being keyed by name for same-id, new-name;
- that deleting every copy and re-importing lands under the repo UUID.

The only source cited is "prefix migration 2026-11-17/18". No
`knowledge/context/investigations/` note exists for these dates.

Fix: add an investigation note with versions, roles (no hosts or account names), the request,
the response, before/after listings, and the re-import result. Cite it from both docs and the
lesson.

### W5. The new tests do not cover the failures above
The new tests are real. The fakes call the real `delete_dashboards_verified` and the real
`cmd_delete_dashboard`, so the 200-deleted-nothing failure (`test_a_200_that_deleted_nothing_exits_non_zero`),
the partial case, the unlisted case and dry-run all exercise production code. Missing:
- an empty or unreadable after-listing (B1);
- a duplicate-name target (B2);
- multi-RESYNC step ordering (B3);
- an owned-but-locked target (W1);
- a plan that mixes `delete` and `resync` under `--apply`, asserting the deletes run, the
  RESYNC copies are untouched, and exit is 1.

## NIT

- N1. `legacy_cleanup.py:374-378`: the "old-named object still carries the repo id" conflict
  branch is now unreachable, because the RESYNC check above it takes every such case that has
  twins. Remove it or comment why it stays.
- N2. `cli.py:997,1004`: `by_id` lookup is case-sensitive while verification is
  case-insensitive. A UUID in another case gets the UUID sent as `tabName`. Lowercase the map.
- N3. `cli.py` dry-run: a UUID target missing from the listing passes dry-run silently and then
  fails the real run as NOT VERIFIED. Flag it in dry-run.
- N4. Field-name drift. The new text says `edit: false` (`dashboard_delete_api.md:230`, lesson);
  the field list (`:376`) and the `list_dashboards` docstring say `editable`. Record which
  version carries which name.
- N5. `_is_true` is defined in both `ui_client.py:82` and `legacy_cleanup.py:242`. Import one.
- N6. Out of diff, orchestrator-owned: `.github/release-notes-buildkit.md:93-98` and the
  `vcfops-api` skill gotcha 8 do not yet mention the same-id, new-name two-copy state or that
  `cleanup-legacy-prefix` now leaves it to the operator.

## Proven safe

- RESYNC does not weaken any guard. `_resync_dashboard` only ever emits verdict `resync`; it
  fires only for dashboards, only when an old-named copy carries the repo id and no twin does,
  and it `continue`s before the delete branches. Every case it takes was `conflict` on `main`.
  Other kinds never reach it. `--apply` deletes only `by_verdict("delete")`, and the test
  confirms `inst.deleted == []`. Digests for these plans change (conflict to resync), so an old
  reviewed digest is refused, which is the safe direction.
- The changed assertion in `test_prefix_migration.py:592` is the intended reclassification,
  conflict to resync, not a dropped check.
- Views: `_view_id` prefers `viewDefinitionKey` and falls back to `id`. Views are still never
  deleted (IN_PLACE).
- Exit codes: no caller in `src/`, `scripts/`, `.claude/` or `.github/` depends on
  `delete-dashboard` exiting 0 or printing "done", or on `cleanup-legacy-prefix` output text.
  One historical investigation note quotes the old "done" text, which is fine. A UUID target
  that was never listed now exits 1 (it was 0), and that change is documented.
- `--dry-run` sends nothing (asserted).
- The docs name no hosts, instances or accounts beyond "the built-in admin account". The tests
  use the existing fictional `svc-factory` and `ops.example.invalid`.

## If shipped as-is

An operator following the printed two-copy remedy for more than one dashboard ends with
dashboards permanently off their repo UUIDs, with every step reporting success and the cleanup
tool then reporting nothing. Deleting by name, or getting an unreadable listing response, still
prints "deleted" and exits 0 while the dashboard remains.

# Defect registry

The declared registry of **known defects that must converge**. A review
verdict records findings; this file is where a finding that survives
acceptance stops being prose and becomes something a release mechanically
refuses over. Design of record: `designs/defect-registry-v1.md`. Gate
rule: `rules/release-gate-defects.md` (RULE-012).

## How it works

- **Graduation.** Any review finding of **WARNING or worse** that
  survives build acceptance unfixed MUST be registered here before the
  next build of that artifact is briefed. NITs do not enter the
  registry — they live in the review docs.
- **The gate consumes this file.** `python3 -m vcfops_packaging
  defect-gate` parses the entries; `release` and `publish` refuse, and a
  v* tag must not be pushed, while an **open blocking** defect affects
  the artifact (RULE-012). Refusals name defect ids.
- **The reviewer re-asserts.** `sdk-adapter-reviewer` reads this file
  every review and re-asserts each open defect affecting the pak under
  review; if a build resolves one, the verdict *proposes* closure with
  evidence. The reviewer never edits this file.
- **Only the orchestrator (or the user) writes here.** Agents propose;
  this file changes only via the orchestrator, in a diff.

## Schema

One `### DEF-NNN` section per entry. Ids are sequential and never
reused. Field lines are `- **Field:** value` (parsed by
`vcfops_packaging` — keep the shape exact, same convention as
`context/managed_paks.md`).

| Field | Values / meaning |
|---|---|
| `Title` | One line; refusal messages quote it. |
| `Severity` | `blocking` (gates releases of affected artifacts) or `tracked` (must converge, re-asserted every review, but ships). |
| `Status` | `open` or `closed`. **No `waived`.** A conscious decision to ship is a severity downgrade with a dated note — the diff is the audit trail. |
| `Affects` | Exactly one artifact scope per entry: a managed pak name from `context/managed_paks.md` (e.g. `synology`), a content item as `<type>/<slug>` (e.g. `dashboard/demand_driven_capacity_v2`), or `factory:<area>` for framework code. One issue on N artifacts = N entries, cross-linked via `Related:`. |
| `First-seen` | Build (or commit) + date where the defect first appeared. |
| `Source` | The review / lesson / investigation that found it, by path (+ finding label). |
| `Summary` | 2–4 lines: what it is, why it matters, smallest correct fix. Enough for a reviewer to re-assert without re-reading the source. |
| `Closing-evidence` | **Required when `Status: closed`** — concrete proof (fix commit/build, devel proof, lesson), not assertion. Omitted while open. A close without evidence is invalid. |
| `Related` | Optional cross-links to sibling entries / lessons. |

## Defects

### DEF-001

- **Title:** Synology: plaintext password and `_sid` reachable from the on-disk adapter log via exception paths
- **Severity:** blocking
- **Status:** open
- **Affects:** synology
- **First-seen:** build 14 (2026-06-10)
- **Source:** `context/reviews/synology-build-14.md` (WARNING-2)
- **Summary:** `SynologyApiClient.callRaw` throws `"HTTP <code> from <path>"`
  where the path carries `_sid=` on every call and `account=` /
  `passwd=<URL-encoded plaintext password>` on the login call; the
  framework logs exception messages to the on-disk adapter log and
  surfaces them on Test-connection, and v14's `componentLogger` swap
  newly lands the `_sid`-bearing logout WARN on disk
  (`rules/no-secrets-on-disk.md`). Smallest correct fix: redact
  `_sid` / `account` / `passwd` from every thrown message — build the
  message from `api`/`method`, never the full path. Hand-back issued at
  build 14; not yet executed.

### DEF-002

- **Title:** UniFi: full-set `setRelationships` onto foreign VMWARE HostSystem unproven on devel (LLDP stitch never exercised)
- **Severity:** blocking
- **Status:** open
- **Affects:** unifi
- **First-seen:** build 3 (2026-06-10)
- **Source:** `context/reviews/unifi-build-3.md` (WARNING-1)
- **Summary:** `emitLldpHostCrossLink` emits full-set
  `setRelationships(host, {switchPort})` onto a VMWARE-owned
  HostSystem — a semantic change from v1's additive `addParent`. The
  per-reporting-adapter scoping that makes this safe is proven on devel
  9.0.2 only via synology (see DEF-003); unifi's LLDP path has **never
  once run on a live instance** (golden baseline: no configured devel
  instance), and 9.1 is unverified. Closes when a unifi devel collect
  against an LLDP-reachable ESXi host shows the matched HostSystem
  retains its pre-existing VMWARE children AND gains the UniFiSwitchPort
  child. If children are clobbered, switch to a labeled generic edge
  (`setGenericRelationships`).
- **Related:** DEF-003, `lessons/setrelationships-foreign-adapter-scoped.md`

### DEF-003

- **Title:** Synology: full-set `setRelationships` onto foreign VMWARE Datastore — clobber risk
- **Severity:** blocking
- **Status:** closed
- **Affects:** synology
- **First-seen:** build 16 (2026-06-10)
- **Source:** `context/reviews/synology-build-16.md` (WARNING-1)
- **Summary:** Same idiom as DEF-002: full-set `setRelationships` emitted
  by the synology adapter onto a foreign VMWARE-owned Datastore, with
  the same static-unprovable clobber risk against the owning adapter's
  child edges.
- **Closing-evidence:** Devel 9.0.2 proof, synology build 16,
  2026-06-10: wld01 iSCSI Datastore retained its 22 VMWARE children and
  gained the LUN child — the platform scopes `setRelationships`
  per-reporting-adapter. Codified in
  `lessons/setrelationships-foreign-adapter-scoped.md`. Residual: 9.1
  unverified (re-open or re-prove at the first 9.1 target).
- **Related:** DEF-002

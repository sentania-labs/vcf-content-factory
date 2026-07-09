# Unreadable is NOT compliant

**Rule.** A value an adapter **failed to read** must never become a pass,
a sentinel score, or a healthy-looking datapoint. Absence of evidence is
not compliance — it is "unreadable," and it must surface as exactly that.

**The three contracts:**

1. **Skip, don't score.** A read that finds nothing → drop the control
   from the denominator, or surface an explicit unreadable/error signal.
   Never fold a failed read into a score as if it evaluated.
2. **Zero-divisor contract.** When *no* controls were evaluable against a
   resource: score = 100.0 **with `totalCount = 0`**, and every caller
   must refuse to fold a `totalCount==0` result into a per-resource or
   fleet average. `totalCount = 0` is how an operator distinguishes
   "perfect" from "nothing was actually evaluated."
3. **Broken source must look broken.** A snapshot refresh that fails
   (REST error, expired session, network down) must **throw out of
   `currentSnapshot()`** so the framework marks the resource ERROR/DOWN.
   Never catch inside and return a partial/empty snapshot — that makes a
   broken source look healthy. (Per-endpoint sub-failures within an
   otherwise-healthy snapshot may be caught locally, sub-resource
   skipped, with a WARN log.)

**Why it's a lesson.** This is the defining failure mode of scoring
adapters — the reason the compliance canonical schema exists and the #1
hunt item in every Tier 2 review. It is seductive because the failure is
*invisible*: a folded `score=100` from an unread control looks like
success on every dashboard while reporting fiction to the operator.

**Corollary hunt items** (reviewer dimension 1,
`.claude/agents/sdk-adapter-reviewer.md`): any path where a
failed/missing read becomes a `pass`/sentinel/folded 100; any widening of
the evaluable set without a real reader behind the new kind; any caller
averaging in a `totalCount==0` result.

**Authority / history:** skill § *Unreadable is NOT compliant*
(`.claude/skills/vcfops-sdk-adapter/SKILL.md`); enforced end-to-end in
`context/reviews/compliance-build-37.md`, `-41.md`, `-43.md`; the
snapshot-must-throw contract is `context/framework_v2_migration.md`
(SourceSnapshot section).

# Agent delegation and lane discipline rules

Operational rules governing how the orchestrator delegates work and how
agents stay in their lanes. Derived from corrections during live
sessions — each rule prevents a documented failure mode.

## 1. Always delegate content authoring

Never write content YAML (supermetrics/, views/, dashboards/,
customgroups/, symptoms/, alerts/, managementpacks/) directly. Always
delegate to the corresponding author agent, even for trivial test
content. Simple content is the best test case for the pipeline.

## 2. Never edit vcfops_*/ code inline

Always delegate to the tooling agent, even for small one-line fixes.
Inline edits erode the boundary that keeps the orchestrator from
accumulating implementation context it shouldn't hold.

## 3. Delegate builds to content-packager

Bundle builds go through content-packager, not inline
`python3 -m vcfops_packaging build`. Same discipline as content
authoring.

## 4. Delegate intent, not pre-designed structure

Send the raw user intent to the top-level author agent. The author
decides decomposition and comes back requesting upstream dependencies.
Don't pre-design the component structure.

## 5. Agents stay in lane — escalate, don't fix

When an agent hits a blocker outside its lane: (1) document with full
detail, (2) escalate to orchestrator, (3) offer a hypothesis — labeled
explicitly, (4) do NOT attempt the fix. The TOOLSET GAP format is the
canonical escalation shape.

## 6. No inline JSON/wire-format authoring

Never author MPB JSON, post-process rendered JSON, or hand-wire wire
format structures inline. Delegate to tooling for renderer fixes or
one-off post-processing.

## 7. Agent-scope boundaries in BOTH specs

When two agents have adjacent scopes, the boundary must be explicit in
both agent spec files. Write a "Relationship to `<sibling>`" section
in each.

## 8. Never lie in post-mortems

State the real chain of events, even when it exposes mistakes. "I
noticed X and didn't act on it" is a valid finding. Ambiguity is
sayable; deception is not.

## 9. Plan mode for all content creation

Enter plan mode unconditionally for any content-creation request.
Dashboard plans must include an ASCII mockup. Other content: formula
preview, threshold table, column list, or section outline. Save a
design artifact before delegating to authors.

## 10. No inline verification after tooling

Don't re-run checks the tooling agent already verified. Relay the
agent's report. Only run inline checks if the report is ambiguous or
the user specifically asks.

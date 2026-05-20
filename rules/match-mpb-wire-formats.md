---
id: RULE-023
decision_refs: []
---

# RULE-023: Match MPB wire formats exactly

When the factory builds the same content type as MPB (management packs,
dashboards, super metrics), the rendered output must be byte-equivalent
to what MPB produces. Do not abbreviate, optimize, or choose alternate
field representations — every divergence is a potential install failure
or runtime incompatibility.

**If violated:** Pak installs fail mysteriously. Adapters register but
don't collect. Content imports but doesn't behave correctly. The VCF Ops
runtime was built to consume MPB's output; factory output that diverges
may pass validation but fail at install or collection time.

**Validation:** Use `pak-compare` against a reference MPB-built pak for
the same domain before shipping. Zero BLOCKINGs is the install gate.

**Evidence:** Lessons learned from vSphere Storage Paths v2.0.0 install
campaign (2026-05-13), documented in
`context/lessons_pak_install_reliability.md` §1, §3, §4. Five failed
installs traced to factory choosing different conventions than MPB.

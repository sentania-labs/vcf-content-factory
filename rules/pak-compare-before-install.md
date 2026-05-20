---
id: RULE-026
decision_refs: []
---

# RULE-026: Use pak-compare before every install attempt

Before attempting to install a factory-built management pack `.pak` on
any VCF Ops instance, run `pak-compare` against the closest reference
MPB-built pak for the same domain. Zero BLOCKINGs is the install gate.

**If violated:** Structural issues (missing XML elements, wrong field
values, malformed JSON) escape to install time, causing cryptic runtime
errors that require appliance log analysis to diagnose. Each iteration
costs minutes to build, transfer, install, and debug.

**The cheap loop:** pak-compare runs in seconds and surfaces structural
divergence immediately. Fix issues at build time, not install time.

**Evidence:** vSphere Storage Paths v2.0.0 had 7 structural issues caught
by pak-compare after 5 failed install attempts. Every issue was fixable
in the renderer. Running pak-compare first would have caught all 7 before
the first install. Documented in
`context/lessons_pak_install_reliability.md` §7 and Process lessons.

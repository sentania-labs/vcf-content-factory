---
id: RULE-024
decision_refs: []
---

# RULE-024: When the wire format is unknown, emit nothing

When the factory encounters a content element whose correct runtime wire
format is unknown or unverified (no ground-truth reference pak, no MPB
output to compare against), omit the element entirely from the build
rather than emitting a best-guess format.

**If violated:** Pak builds succeed but installs fail with parse errors,
field validation errors, or silent runtime failures. The runtime
validator may accept malformed wire formats that the collection engine
rejects later.

**What to do instead:** Document the gap in `context/known_limitations.md`,
mark the feature deferred, and emit the content without that element. When
a ground-truth reference becomes available, implement the correct format.

**Evidence:** Events in pak-runtime format remain a TOOLSET GAP (all MPB
reference paks have `events: []`). The factory stripped events from pak
builds after runtime validation errors; the `--no-events` workaround for
design import should have been applied to pak builds from the start.
Documented in `context/lessons_pak_install_reliability.md` §5.

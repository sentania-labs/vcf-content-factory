---
id: RULE-006
---

# RULE-006: All authored content uses `[VCF CF]` prefix

Literal brackets, one space after. The prefix was `[VCF Content Factory]` until 2026-11-12 (owner: "Let's move to VCF CF prefix and retroactively fix stuff"); a name in the old spelling is now a load error that points at `python3 -m vcfcf_common migrate-prefix` (`knowledge/context/authoring/prefix_migration.md`). Dashboards additionally live under the `VCF Content Factory` folder. No alternate prefixes: `[AI Content]` is legacy and must not be reintroduced.

**Carve-out:** Management packs use the prose prefix `VCF Content Factory` without brackets in display names.

**Carve-out:** Content that ships inside something the factory did not name follows that thing's naming: a third-party project with `factory_native: false` in its `PROJECT.yaml`, and an SDK-adapter pak whose `adapter.yaml` declares `content_naming: unprefixed`. There `validate-sdk` and `build-sdk` enforce the absence of the prefix. A pak that declares nothing gets the default (`factory_prefixed`) with a warning on mismatch, not a failure (issue #229); the one exception is a name in the old `[VCF Content Factory]` spelling, which fails the build in every pak.

**If violated:** Content becomes indistinguishable from user-authored objects, breaking discovery, bulk operations, and the promise that factory content is clearly tagged.

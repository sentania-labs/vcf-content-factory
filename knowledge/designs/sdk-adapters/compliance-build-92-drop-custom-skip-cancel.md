# Compliance build 92: drop Custom, one place per decision, Skip clears its alert

- **Type:** managementpack (Tier 2 SDK adapter change), build 92
- **Slug:** compliance-build-92-drop-custom-skip-cancel
- **Adapter repo:** `content/sdk-adapters/compliance/`
- **Date:** 2026-10-13
- **Tracking:** adapter issue #41 (Skip alert does not clear; doc path corrections)
- **Builds on:** `compliance-overrides-file.md` (build 90/91, evaluated on devel 2026-10-13; Skip alert clear excepted, issue #41)
- **Status:** go from Scott 2026-10-13 ("GO."); build 92 installed on devel 2:44 PM (identity PASS, Skip pushes -1 every cycle, call rate unchanged; alert cancel NOT proven, alerts were already cancelled); PR #45

## Initial prompt (Scott, verbatim, 2026-10-13)

> so are we at a point that allowing a user to select the SCG is redundant?

> So we make it Auto + Custom, custom points to a MP xml file - similar to,
> but different then the override?

> I was thinking more: Auto + Overridefile / Custom + You define your
> benchmark file. Basically it reads the specificied file as the endall be
> all.

> maybe we just drop custom and rely purely on override - because of the
> complication of the alerts.

> GO.

## Vision

1. **Custom is gone.** The Compliance Profile setting offers Auto (by
   version) and the bundled SCG versions only. The `custom_profile_path`
   setting, the `Custom` branch in the loader and selector, the build 90
   deprecation WARN, and every doc mention of the custom CSV are removed.
   An existing instance stored as Custom logs one WARN naming the removal
   and runs as Auto. CANONICAL_SCHEMA.md stays as the contributor reference
   for the bundled profiles (linked from docs/building.md only).
2. **One place per decision.** The instance setting owns "Auto or which
   bundled version". The overrides file owns Skip, Override and the
   per-kind Profile pin. The instance-wide `<Profile version=.../>` element
   (no `kind`) is removed from the schema, the template and the docs; if
   present it is rejected and reported like any unknown entry
   ("instance-wide pin: use the Compliance Profile setting").
3. **Skip clears its alert.** While a Skip is in force the adapter pushes
   `VCF-CF Compliance|<control>|Compliant` = -1 (and the Actual text) on
   every cycle, not once, so the symptom sees its cancel cycles and the
   alert cancels. Devel evidence for the defect: issue #41 (one -1 sample
   at 11:54 AM, alert still ACTIVE at 12:36 PM). Removing the Skip resumes
   normal scoring on the next cycle.
4. **Docs match the UI.** Menu path is Infrastructure Operations >
   Configurations > Management Packs Configuration (devel 9.0.2; say
   "Administration > Configuration Files on older builds" if the adapter
   author can confirm that wording from reference docs, otherwise omit).
   The clone dialog defaults to `<template>.xml_Copy` under System
   Defined; saving under a new name ending in `.xml` lands it in User
   Defined; the instance setting takes the name without `.xml`.
   `docs/overrides.md` Step 1 says so. The adapter README known-issue
   entries that build 90/91 resolved are closed.

No new keys, no new alerts. `overrides_overridden` and `overrides_skipped`
semantics unchanged.

## Verification on devel (under a separate go)

Upgrade over 91; wld01 still points at `compliance_overrides_wld01`; the
shell-timeout alerts on both wld01 hosts cancel within three cycles of
the first build 92 collection; lockout override still in force; VM pin
still in force; the instance setting no longer offers Custom.

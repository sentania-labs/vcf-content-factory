# Pak Content Localization Bundles — Four Bundles Required, Keys Must Match

> **SCOPE NARROWED 2026-08-06 (DEF-018).** This lesson applies to
> **pak units that ship localization bundles** (the SDK-pak
> `content/reports/<dir>/` layout below). It is NOT an instruction to
> emit `localizationKey` in general. The inverse failure mode is just
> as fatal: a `localizationKey` attribute with **no** properties bundle
> in the same import unit hard-fails view import on VCF Ops 8.18
> (`ViewDefinitionDataServiceImpl.validate`; 9.1 silently tolerates
> it). Standalone content-import zips (`Views.zip` = bare `content.xml`)
> ship no bundles, so their `<Title>`/`<Description>` must carry **no**
> `localizationKey` at all — the renderer emits plain elements since
> DEF-018. Corpus invariant: emit `localizationKey` only when a
> `content.properties` bundle ships in the same import unit; never
> dangling. (14 of 934 vendor Title/Description elements carry the
> attribute; all 14 ship a co-located bundle, zero carry it without one.)

## The dead end

Builds 21 and 22 debugging why a VCF Ops solution pak with a clean
`content/dashboards/` and `content/reports/` tree silently failed to import
its dashboard and view, even after adding the four localization properties
files that Pass 30 identified as required structural pieces.

Build 21 added all four bundles and fixed empty content/ subdirs (Pass 30
candidates). The dashboard still did not import. The analytics log showed:

```
ERROR: Localization for key desc is absent
```

Build 22 traced this to a suffix mismatch: the view XML renderer emitted
`localizationKey="desc"` on `<Description>`, but the properties generator
wrote `view.<uuid>.description=...` (with the full word). The importer does
an exact-suffix lookup and aborts the entire content tree — killing dashboard
import for the whole pak — when any single key is absent.

## Symptom

Post-install inventory shows 0 dashboards, 0 views, despite the pak
containing populated `content/dashboards/<dir>/dashboard.json` and
`content/reports/<dir>/content.xml`.

In the analytics log during step 15 (APPLY_ADAPTER), grep for:

```
ERROR: Localization for key <suffix> is absent
```

The `<suffix>` value is what appears in the view XML as
`localizationKey="<suffix>"`. Compare against the properties file entries
under `view.<viewdef_uuid>.*` — the missing key is the mismatch.

A silent drop (no error, just nothing imported) means the bundle lookup
itself failed before reaching per-key validation. Check that the
`content/resources/resources.properties` file exists and is non-empty.

## Cause

Two separate issues that compound:

1. **Missing bundles**: the content importer requires populated properties
   files at all four levels (outer pak, content-wide, per-dashboard,
   per-view). Any missing bundle causes a silent drop of the corresponding
   content type.

2. **Suffix mismatch**: the view XML `localizationKey` attribute value must
   exactly match the suffix after `view.<uuid>.` in content.properties. The
   XML renderer and the properties generator are two separate code paths —
   they can drift independently.

## Fix

### The four-bundle contract (must be present and populated)

| Path | Purpose |
|---|---|
| `resources/resources.properties` | Outer pak solution metadata (`DISPLAY_NAME`, `DESCRIPTION`, `VENDOR`) |
| `content/resources/resources.properties` | Adapter-wide nameKey-to-display map (numeric keys from describe.xml) |
| `content/dashboards/<dir>/resources/resources.properties` | Per-dashboard folder label, dashboard name, widget titles |
| `content/reports/<dir>/resources/content.properties` | Per-view title, description, and column display names keyed as `view.<uuid>.<suffix>` |

Never emit empty properties files. The importer distinguishes absent from
empty — an empty file does not satisfy the bundle requirement.

### The localizationKey alignment rule

The view XML `<Description localizationKey="desc">` and the properties entry
`view.<uuid>.desc=...` must use the **same suffix**. Two conventions exist in
the corpus (`desc` vs. `description`); pick one and enforce it across both the
XML renderer and the properties generator.

VCF-CF convention: `desc` (matching VCFAutomation, our closest structural
reference). The `_attribute_to_localization_key()` function that sanitizes
column attribute keys runs identically in both `src/vcfops_dashboards/render.py`
and `src/vcfops_managementpacks/sdk_builder.py` — keep them in sync when modifying
either.

A build-time validator in `validate_sdk_project()` now catches mismatches
before the pak is built. Run `python3 -m vcfops_managementpacks validate`
after any change to the renderer or properties generator.

## Reference

- Spec/18 Pass 31: `knowledge/context/cleanroom-spec/spec/18-pak-content-bundle.md`
  (four-bundle contract, diagnostic fingerprint, build history)
- Generator code: `src/vcfops_managementpacks/sdk_builder.py` —
  `_generate_outer_resources_properties`, `_generate_content_resources_properties`,
  `_generate_dashboard_resources_properties`, `_generate_view_content_properties`,
  `_attribute_to_localization_key`
- XML renderer: `src/vcfops_dashboards/render.py` — since DEF-018 emits plain
  `<Title>`/`<Description>` (no `localizationKey`); the suffix-alignment rule
  above applies only if a bundle-shipping path re-introduces the attribute
- Confirmed working: v22 pak (`vcfcf_sdk_compliance.1.0.0.22.pak`) on devel,
  post-install inventory: 1 dashboard, 1 view, 1 alert, 2 symptoms, 3 recs

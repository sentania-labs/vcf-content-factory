# dist/ ↔ /publish parity (v1)

**Status:** design — implementing in the same workstream as the 2026-04-28 PowerShell fix
**Owner:** tooling agent
**Date:** 2026-04-28

## Goal

Make `python3 -m vcfops_packaging build` (the local `dist/` writer)
produce zips with the same **filenames and directory layout** that
`/publish` ships to `vcf-content-factory-bundles/`. So a QA tester
working out of `dist/` sees the exact artifact a customer would
download from the distribution repo.

## Current state (as of 2026-04-28)

| | `dist/` (local) | `vcf-content-factory-bundles/` (publish) |
|---|---|---|
| Filename | `[VCF Content Factory] <Display Name>.zip` | `<release-slug>.zip` |
| Layout | flat | per-type subdirs (`dashboards/`, `bundles/`, `reports/`, `ThirdPartyContent/<type>/`) |
| Driver | `vcfops_packaging.builder.build_package` (`output_dir="dist"`) | `vcfops_packaging.publish` via tempdir → routed copy |

Concrete example:
- `dist/[VCF Content Factory] Idps Planner.zip`
- `vcf-content-factory-bundles/ThirdPartyContent/dashboards/idps-planner.zip`

These are byte-equivalent contents wrapped under different names.
That's bad for filename-as-identity tooling and confuses QA.

## Proposed change

`python3 -m vcfops_packaging build <manifest>` should:

1. Use the **release-routing logic** from `publish.py` (`_classify_release`,
   per-type subdir mapping, `factory_native` flag) to decide the dest
   subdir under `dist/`.
2. Use the **release filename logic** from `release_builder.py` (slug-based
   `<content>-<type>.zip`) to decide the filename.
3. Drop the `[VCF Content Factory]` prefix from the filename — that prefix
   exists for *display name* identity inside Ops, not for filesystem
   identity. Filesystem identity is the slug.

After the change, the table above collapses to:

| | `dist/` | `vcf-content-factory-bundles/` |
|---|---|---|
| Filename | `<release-slug>.zip` | `<release-slug>.zip` |
| Layout | per-type subdirs | per-type subdirs |

Same routing function, same naming function, called once per build.

## Compatibility / breaking changes

- **Existing CI / scripts that read `dist/[VCF Content Factory] <Name>.zip`** —
  if any exist, they break. Audit before shipping. None known in-repo;
  if the user has external scripts pointing at `dist/`, they need to
  rev to the new layout.
- **Stale zips in `dist/` from old naming schemes** — leave alone or
  bulk-delete in the same change. Recommend bulk-delete: `dist/` is a
  build artifact, not a curated archive.
- **Bundles built outside the release lifecycle** (rare — `bundles/*.yaml`
  built directly without a `releases/<name>.yaml`) — these don't have
  a slug-with-type suffix. Need a fallback: use `<bundle-slug>.zip`
  with no type suffix, dropped at `dist/` root.

## Implementation sketch

1. Extract the routing + naming helpers from `publish.py` into
   shared functions (`vcfops_packaging.routing`).
2. `builder.build_package` (or a new `build_release_artifact` wrapper)
   calls those helpers when given a release path.
3. `cli.py`'s `build` command:
   - if arg is `releases/*.yaml` → use release-builder + routing
   - if arg is `bundles/*.yaml` → use legacy builder, slug-flat filename, no subdir
4. `dist/` cleanup helper: optional flag `--clean` to delete stale
   files under `dist/` that don't match a known release slug. Same
   semantics as publish's stale-zip sweep.

## Open questions for whoever picks this up

- Should `build` ALSO regenerate the dist-repo README between AUTO
  markers locally, mirroring publish's `readme_gen.py` pass? Argument
  for: complete parity. Argument against: README is a publish artifact,
  not a build artifact, and confuses the difference.
- Should `dist/` keep ANY top-level legacy-format zips for backwards
  compatibility, or fully migrate? Recommend full migrate — `dist/` is
  not a stable contract.

## Why now

QA tester workflow: someone validates a fix in `dist/`, then `/publish`
ships an "identical" artifact. Currently the validator can't grep,
diff, or hash by filename across the two surfaces. After this change,
they can.

Forcing function: 2026-04-28 PowerShell `Enable-BuiltinMetricsOnDefaultPolicy`
fix went into `dist/[VCF Content Factory] Idps Planner.zip`; the
external user (Ryan Pletka) will receive `ThirdPartyContent/dashboards/idps-planner.zip`
from the distribution repo. Same fix, two filenames. Confusing.

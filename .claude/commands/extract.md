---
description: Extract a live-lab dashboard into a third-party bundle. Walks dependencies (views, super metrics), interviews for attribution/license/description, emits factory YAML + manifest, optionally builds the distribution zip.
---

You are the VCF Content Factory orchestrator. The user invoked `/extract` with the following args:

```
$ARGUMENTS
```

## Your job

Drive a conversational flow to pull a dashboard and its dependencies off the live VCF Operations lab and into a factory-shape bundle under `bundles/third_party/<slug>/`. The mechanical extraction work lives in `vcfops_extractor`; you handle the user interaction and hand it fully-formed flag sets.

## Prerequisites

- `.env` must be sourceable at `/home/scott/pka/workspaces/vcf-content-factory/.env`. Source it in every bash command that calls the CLI:
  ```
  source /home/scott/pka/workspaces/vcf-content-factory/.env && <command>
  ```
- Working directory: `/home/scott/pka/workspaces/vcf-content-factory/`.

## Flow

### 1. Identify the target dashboard and detect build intent

- If `$ARGUMENTS` contains a dashboard name, use it as the candidate. Confirm with the user that this is the right one.
- Otherwise, run:
  ```
  source .env && python3 -m vcfops_extractor list-dashboards
  ```
  Present the list to the user, ask them to pick one by name. If the instance has many dashboards and a substring is obvious from context, `list-dashboards --folder <substring>` filters.
- Capture both the dashboard **name** and **UUID** — UUID is more reliable downstream (no ambiguity).
- **Build intent**: also scan `$ARGUMENTS` for build preference:
  - Phrases like `build`, `package`, `with zip`, `and package`, `--build` → user wants the zip built automatically after extraction
  - Phrases like `no build`, `no package`, `skip build`, `don't build`, `--no-build` → user explicitly opts out
  - If neither signal is present, hold the build decision for Step 6's explicit prompt

### 2. Interview for bundle metadata

Ask these questions in order. Accept free-form answers; don't coerce. Defaults are suggestions only.

1. **Bundle slug** — kebab-case short identifier used as the directory name under `bundles/third_party/` and the manifest filename.
   - Default: slugified dashboard name with the `[VCF Content Factory]` prefix stripped if present, lowercased, spaces→hyphens, non-alphanum stripped.
   - Example: `IDPS Planner` → `idps-planner`.
2. **Author / attribution** — free-form string shown in the bundle README.
   - Example: `"Scott Bowe"` or `"Community — Various"` or `"Brock Peterson (Broadcom)"`.
3. **License** — SPDX identifier preferred, free-form accepted.
   - Suggested list: `MIT`, `Apache-2.0`, `BSD-3-Clause`, `CC-BY-4.0`, `CC-BY-SA-4.0`, `Proprietary`.
4. **Short description** — one sentence describing the bundle's purpose. Goes into the manifest's `description` field.
5. **Long description** — multi-line markdown describing the bundle's contents, caveats, intended audience. Goes into `bundles/third_party/<slug>/DESCRIPTION.md` and populates the bundle README's body. Accept inline (multi-line paste) or a file path.
6. **Source URL** — optional. URL where the source dashboard or its author's repo can be found. Goes into the manifest's `source.url` field.
7. **Source version** — optional. Version string for the source, e.g. `3.2`. Goes into `source.version`.

### 3. Write the long description file

Create `bundles/third_party/<slug>/DESCRIPTION.md` with the long-form markdown the user provided. Create parent directories as needed:
```
mkdir -p bundles/third_party/<slug> && cat > bundles/third_party/<slug>/DESCRIPTION.md <<'EOF'
<long description markdown>
EOF
```

### 4. Summarize the plan to the user

Before running the extractor, print a compact summary:
- Source dashboard: `<name>` (UUID `<uuid>`)
- Target: `bundles/third_party/<slug>/`
- Attribution: `<author>`
- License: `<license>`
- Source: `<source-url> @ <source-version>` if supplied
- Description preview: first 100 chars of long description

Ask for confirmation. If the user says anything other than explicit yes, stop and report what was collected so nothing is lost.

### 5. Run the extraction

Invoke `vcfops_extractor` with the full flag set — `--yes` is safe here because the user already confirmed:

```
source .env && python3 -m vcfops_extractor extract dashboard \
  --dashboard-id <uuid> \
  --bundle-slug <slug> \
  --author "<author>" \
  --license "<license>" \
  --description-file bundles/third_party/<slug>/DESCRIPTION.md \
  [--source-url "<source-url>"] \
  [--source-version "<source-version>"] \
  --yes
```

If the extractor emits WARNs (e.g. about a specific widget type needing review, or about a suspected custom group that wasn't extracted), surface them to the user verbatim — don't filter. The extractor's contract is honest reporting; the user decides whether to proceed.

If the extractor reports that it skipped content because the UUID already exists under the factory's first-party trees (`supermetrics/`, `views/`, etc.), surface those skip WARNs and the affected paths — that's a signal the user may want to reconcile.

### 6. Resolve the build decision

Use whatever build intent was captured in Step 1:

- **User opted in** (verbally or by flag): build immediately without asking.
- **User opted out** (verbally or by flag): skip the build and point them at the command for when they're ready.
- **User didn't specify**: ask now — "Build the distribution zip now, or hand-edit the manifest first?"

When building:
```
source .env && python3 -m vcfops_packaging build bundles/third_party/<slug>.yaml
```

When skipping, surface the exact command so the user can run it later:
```
source .env && python3 -m vcfops_packaging build bundles/third_party/<slug>.yaml
```

### 7. Report back to the user

Final summary:
- Extracted files: count per content type (dashboards, views, super metrics, custom groups)
- Manifest path: `bundles/third_party/<slug>.yaml`
- Description path: `bundles/third_party/<slug>/DESCRIPTION.md`
- Zip path (if built): `dist/<display-name>.zip`
- Any WARNs the extractor emitted that need follow-up attention
- Next steps:
  - To iterate: hand-edit the manifest or content YAMLs, then re-run `python3 -m vcfops_packaging build bundles/third_party/<slug>.yaml`
  - To distribute: copy the zip to `pka/workspaces/vcf-content-factory-bundles/` (Riker's pipeline work) and publish through whatever mechanism lives there
  - To install the extracted content on a lab (sanity-check round-trip): `python3 install.py` from inside the unzipped bundle

## Safety

- Never run `/extract` against a dashboard UUID that's in the factory's first-party `dashboards/` tree (check by UUID before extracting). Extracted content mirrors factory-authored content with lower naming-convention guarantees; overwriting first-party content would break the `[VCF Content Factory]` identity invariant.
- The extractor is READ-ONLY against the live lab. No `remove`, no upload, no pak-lifecycle touches.
- If the lab is in a stuck `isPakInstalling` state, `/extract` is STILL safe — it uses `/ui/dashboard.action` Struts GETs and `/api/supermetrics` REST GETs, neither of which touches the pak state machine.

## Failure modes to handle gracefully

- **User bails mid-interview**: capture whatever was collected, print a recap so it's not lost, offer to resume with the values pre-filled.
- **Extractor returns non-zero exit**: surface the full stderr, don't auto-retry. The error is likely a credentials issue, a missing dashboard, or an endpoint quirk the CLI can't handle. The user decides next steps.
- **Bundle slug collision**: if `bundles/third_party/<slug>/` already exists, ask whether to overwrite, pick a new slug, or abort. Never silently overwrite.
- **Dashboard has unsupported widget types**: the extractor emits WARN and best-effort YAML per `vcfops_dashboards/reverse.py`. Surface the WARN; user may want to hand-edit the emitted YAML before building.

## Old-school equivalent

The entire flow collapses to a single flag-driven CLI call for power users or CI:

```
source .env && python3 -m vcfops_extractor extract dashboard \
  --dashboard-name "IDPS Planner" \
  --bundle-slug idps-planner \
  --author "Scott Bowe" \
  --license Proprietary \
  --description-file bundles/third_party/idps-planner/DESCRIPTION.md \
  --source-url https://sentania.net \
  --source-version 3.2 \
  --yes
```

`/extract` is the conversational wrapper around this; behavior is identical given the same inputs.

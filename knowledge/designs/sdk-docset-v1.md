# Design note — standard docset for SDK management packs (v1)

## Initial prompt

2026-06-10 session (verbatim):

> also an update for the MPs - part of the standard deliverable should
> be a rendered excalidraw diagram showing kinds + keys:
> https://techdocs.broadcom.com/us/en/vmware-cis/aria/aria-operations-for-integrations/9-1/management-pack-for-microsoft-sql-server-9-1/using-the-management-pack-microsoft-sql-server/inventory-tree-traversal-spec-microsoft-sql-server.html
>
> basically we should ship a docset that is similar to this MP:
> https://techdocs.broadcom.com/us/en/vmware-cis/aria/aria-operations-for-integrations/9-1/management-pack-for-microsoft-sql-server-9-1.html

## Vision

- Every SDK pak repo ships a `docs/` docset modeled on Broadcom's
  per-MP documentation structure (the MS SQL Server MP is the
  exemplar): overview / what's-in-the-pack, installing & configuring
  (prereqs, adapter config fields, permissions, ports), using the MP
  (inventory tree + traversal spec, resource kinds with their
  identifying keys), and the metrics/properties reference (the
  existing generated REFERENCE.md slots in here).
- **Centerpiece: an inventory-tree diagram showing kinds + keys**,
  shipped as Excalidraw source (`.excalidraw`) plus a **committed
  rendered SVG/PNG** so it displays on the GitHub repo page. The
  diagram is *generated deterministically* from `describe.xml`
  (ResourceKinds, identifiers with isUnique flags, TraversalSpecKind)
  — never hand-drawn — so it can't drift from the shipped pak.
- Generation policy mirrors the CHANGELOG lesson: **derived files
  regenerate every build** (diagram, kinds/keys tables, reference);
  **prose files generate once** as scaffolds and are hand-curated
  thereafter (overview, installing).
- Generator lives in the factory tooling (and flows into the
  sdk-buildkit so CI/template users get it); per-repo adoption is an
  author pass; template repo gets the docset scaffold.
- The bundles-repo README pointer rows (knowledge/designs/release-sdk-pointer-v1.md)
  gain nothing new — the repo-page link already lands users on the
  docset.
- Rendering constraint: GitHub does not render `.excalidraw` natively,
  so the SVG must be produced headlessly at generation time. If no
  acceptable headless renderer exists (node dep weight, portability),
  that is a TOOLSET GAP to surface with options — not a silent
  downgrade.

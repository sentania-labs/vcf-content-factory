# Reference docs and how to add more

## What we already have

| File | What it is |
|---|---|
| `reference/docs/operations-api.json` | VCF Ops Suite API OpenAPI spec (public, supported) |
| `reference/docs/internal-api.json` | `/internal/*` OpenAPI spec (unsupported, requires `X-Ops-API-use-unsupported: true`) |
| `reference/docs/operations-api-9.1.json`, `internal-api-9.1.json` | Same pair for 9.1 |
| `reference/docs/operations-api-8.18.json`, `internal-api-8.18.json` | Same pair for Aria Operations 8.18.7, verbatim as served by `devel_8_18` (springfox Swagger 2.0, `/suite-api/doc/v2/api-docs?group=Public%20APIs` and `?group=Internal%20APIs`, fetched 2026-10-28). Generated schemas use Java field names in places; trust the per-operation `x-examples` for JSON wire keys (see `api-surface/suite_api_batch_push.md`) |
| `knowledge/context/vrops-content-management.md` | Extracted from the Suite-API whitepaper |
| `reference/docs/vcf9/supermetrics.md` | VCF 9 docs p.4171–4180, the super metric DSL reference |
| `reference/docs/vcf9/metrics-properties.md` | VCF 9 docs p.4242–4507, valid metric key reference |
| `reference/docs/vcf9/dashboards.md` | VCF 9 docs p.3921–4053 |
| `reference/docs/vcf9/views-reports.md` | VCF 9 docs p.4137–4169 |
| `reference/docs/vcf9/policies.md` | VCF 9 docs p.3130–3155 |
| `reference/docs/vcf9/alerts-actions.md` | VCF 9 docs p.3157–3270 |
| `reference/docs/vcf9/suite-api.md` | VCF 9 docs p.7968–7986 |

Prefer the extracted markdown over the source PDFs — the markdown is
grep-friendly and readable directly with the `Read` tool. PDFs are
gitignored because the VCF 9 PDF alone is ~148 MB / 8,285 pages.

## When a new PDF lands

Review it, identify the sections relevant to VCF Operations content
authoring, and extract them to markdown under `reference/docs/`:

- Chapters of the main VCF 9 docs → `reference/docs/vcf9/<slug>.md`.
- Standalone whitepapers → `reference/docs/<slug>.md`.

Extraction recipe:

```python
import pypdf
r = pypdf.PdfReader("<path/to.pdf>")
with open("reference/docs/vcf9/<section>.md", "w") as f:
    f.write(f"# <section> (pages S-E)\n")
    for p in range(S - 1, E):   # S, E are 1-indexed inclusive
        f.write(f"\n\n---\n## page {p+1}\n\n{r.pages[p].extract_text() or ''}")
```

After extracting, commit the markdown. Do NOT commit the PDF —
`*.pdf` is gitignored.

## Anything under `reference/docs/` is authoritative

Treat every file under `reference/docs/` as valid reference material on par
with the PDF and the OpenAPI specs. It is there because someone
(usually the user) curated it.

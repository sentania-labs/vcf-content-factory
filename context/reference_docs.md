# Reference docs and how to add more

## What we already have

| File | What it is |
|---|---|
| `docs/operations-api.json` | VCF Ops Suite API OpenAPI spec (public, supported) |
| `docs/internal-api.json` | `/internal/*` OpenAPI spec (unsupported, requires `X-Ops-API-use-unsupported: true`) |
| `docs/vrops-content-management.md` | Extracted from the Suite-API whitepaper |
| `docs/vcf9/supermetrics.md` | VCF 9 docs p.4171–4180, the super metric DSL reference |
| `docs/vcf9/metrics-properties.md` | VCF 9 docs p.4242–4507, valid metric key reference |
| `docs/vcf9/dashboards.md` | VCF 9 docs p.3921–4053 |
| `docs/vcf9/views-reports.md` | VCF 9 docs p.4137–4169 |
| `docs/vcf9/policies.md` | VCF 9 docs p.3130–3155 |
| `docs/vcf9/alerts-actions.md` | VCF 9 docs p.3157–3270 |
| `docs/vcf9/suite-api.md` | VCF 9 docs p.7968–7986 |

Prefer the extracted markdown over the source PDFs — the markdown is
grep-friendly and readable directly with the `Read` tool. PDFs are
gitignored because the VCF 9 PDF alone is ~148 MB / 8,285 pages.

## When a new PDF lands

Review it, identify the sections relevant to VCF Operations content
authoring, and extract them to markdown under `docs/`:

- Chapters of the main VCF 9 docs → `docs/vcf9/<slug>.md`.
- Standalone whitepapers → `docs/<slug>.md`.

Extraction recipe:

```python
import pypdf
r = pypdf.PdfReader("<path/to.pdf>")
with open("docs/vcf9/<section>.md", "w") as f:
    f.write(f"# <section> (pages S-E)\n")
    for p in range(S - 1, E):   # S, E are 1-indexed inclusive
        f.write(f"\n\n---\n## page {p+1}\n\n{r.pages[p].extract_text() or ''}")
```

After extracting, commit the markdown. Do NOT commit the PDF —
`*.pdf` is gitignored.

## Anything under `docs/` is authoritative

Treat every file under `docs/` as valid reference material on par
with the PDF and the OpenAPI specs. It is there because someone
(usually the user) curated it.

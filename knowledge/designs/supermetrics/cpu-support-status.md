# Supermetric: CPU Support Status (KB318697)

## Initial prompt (verbatim)

> I'd like a dashboard that helps me identify CPU support in relation to
> vsphere. The official source of record is:
> https://knowledge.broadcom.com/external/article/318697/cpu-support-deprecation-and-discontinuat.html
>
> If i were to build this, I would probably create a number of Groups or
> a super metric that joined thigns together in "supported"/unsupport"
> and the display it.
>
> I'd like the dashboard to have a scoping tier, that then lists all
> hosts in the scope with: hostname, model, CPU model, deprecated,
> discontinued, discontinued 9.2, supported.

Clarifying turns (paraphrase-free excerpts):

> Personally if we can make it work with a super metric and get the
> string slicing right - that's the smallest/most compact approach

> I keep giving you evidence that you can do this with few super
> metrics, why do you insist on multiple ones without having a
> discussion

Final choice via question: **1 coded SM** ("supported" derived — not in
any bad list; unknown/new CPUs read as supported).

## Vision

- ONE supermetric on VMWARE HostSystem:
  `[VCF Content Factory] CPU Support Status (KB318697)`.
- Emits a tier code: 0=supported, 1=deprecated,
  2=discontinued starting from VCF 9.2, 3=discontinued. Most-severe
  tier wins (nested ternary, checked 3 → 2 → 1 → 0). **Codes are
  monotonic in severity** so a downstream max() roll-up never masks a
  currently-discontinued host behind a merely future-discontinued one.

> **Correction (2026-07-22, Codex review P1 on bundles PR):** the
> original code assignment had 3=discontinued-starting-from-9.2 and
> 2=discontinued, which is inverted — discontinued-now is strictly
> worse than discontinued-starting-9.2 (blocked on all 9.x releases
> vs. blocked only from 9.2 onward). This made the cluster-level
> max() roll-up (`cluster_cpu_support_worst_status_kb318697.yaml`)
> mask a currently-discontinued host behind a future-discontinued one
> whenever both existed in the same cluster. Fixed by swapping the
> emitted codes in `cpu_support_status_kb318697.yaml` (pattern
> literals unchanged, tier check order unchanged at 3→2→1→0): the
> tier table below reflects the corrected mapping.
- Each tier is one `count(${this, metric=cpu|cpuModel, where=($value
  contains '<p1>' || $value contains '<p2>' || …)})` term — the
  parenthesized `$value` where-dialect with single-quoted literals,
  attested by vendor blog "My Top 15 vRealize Operations Super Metrics"
  #9 (compound `||` with string ops) and #10 (ternary). This dialect is
  DISTINCT from the quoted-string dialect
  (`where="prop equals X && …"`) whose compound form silently fails
  (2026-04-09 finding in
  knowledge/context/authoring/supermetric_authoring.md).
- Probe gate before authoring the real SM: throwaway compound-`||`
  probe SM on devel must return correct 1/0 before the pattern set is
  built out. Fallback if the probe zeroes: boolify-then-chain
  (`count(...) ? 1 : 0` per single-condition term, summed).
- Pattern table: KB 318697 series rows → cpuModel substrings, each
  verified against recon-sampled live `cpu|cpuModel` strings; unmatched
  patterns are annotated, never silently shipped. See "Pattern table"
  section (appended during implementation).
- Probe outcome gets codified back into
  knowledge/context/authoring/supermetric_authoring.md (two-dialect
  distinction), correcting the overgeneralized "no && with string
  operators" claim.

## Pattern table (KB 318697, fetched 2026-07-22)

ESXi `cpu|cpuModel` string shapes the patterns target:
`Intel(R) Xeon(R) Gold 6130 CPU @ 2.10GHz`,
`Intel(R) Xeon(R) CPU E5-2680 v4 @ 2.40GHz`,
`AMD EPYC 7551 32-Core Processor`, `Intel(R) Atom(TM) CPU C3558 @ 2.20GHz`.

Tier check order in the formula: 3 → 2 → 1 → 0 (most severe wins; the
tiers below are disjoint by construction).

### Tier 3 — Discontinued (code 3, most severe)

| KB series | Code name | contains patterns |
|---|---|---|
| Xeon D-1500 | Broadwell-DE | `'D-15'` |
| E5-2600-V4 / E5-1600-V4 / E5-4600-V4 / E7-8800-4800-V4 | Broadwell-EP/EX | `' v4'` (all Xeon v4 are Broadwell; slight over-match on unlisted edge v4 SKUs is intended-spirit) |
| Xeon E3-1200-v6 | Kaby Lake-S | `' v6'` (v6 suffix exists only on E3-1200 v6) |
| Xeon W-2100 | Skylake-W | `'W-21'` |

### Tier 2 — Discontinued starting from 9.2

| KB series | Code name | contains patterns |
|---|---|---|
| Xeon E3-1200-V5 / E3-1500-V5 | Skylake-S | `' v5'` (v5 suffix exists only on these) |
| Platinum 8100, Gold 6100/5100, Silver 4100, Bronze 3100 | Skylake-SP | `'Platinum 81'`, `'Gold 61'`, `'Gold 51'`, `'Silver 41'`, `'Bronze 31'` |
| Xeon D-2100 | Skylake-D | `'D-21'` |

### Tier 1 — Deprecated

| KB series | Code name | contains patterns |
|---|---|---|
| AMD EPYC 7001 (Naples) | Zen | model enumeration: `'EPYC 7251'`, `'EPYC 7261'`, `'EPYC 7281'`, `'EPYC 7301'`, `'EPYC 7351'`, `'EPYC 7371'`, `'EPYC 7401'`, `'EPYC 7451'`, `'EPYC 7501'`, `'EPYC 7551'`, `'EPYC 7571'`, `'EPYC 7601'` |
| AMD EPYC 7002/7Fx2 (Rome) | Zen2 | `'EPYC 7232'`, `'EPYC 7252'`, `'EPYC 7262'`, `'EPYC 7272'`, `'EPYC 7282'`, `'EPYC 7302'`, `'EPYC 7352'`, `'EPYC 7402'`, `'EPYC 7452'`, `'EPYC 7502'`, `'EPYC 7532'`, `'EPYC 7542'`, `'EPYC 7552'`, `'EPYC 7642'`, `'EPYC 7662'`, `'EPYC 7702'`, `'EPYC 7742'`, `'EPYC 7F32'`, `'EPYC 7F52'`, `'EPYC 7F72'`, `'EPYC 7H12'` |
| Platinum 8200, Gold 6200/5200, Silver 4200, Bronze 3200 | Cascade Lake | `'Platinum 82'`, `'Gold 62'`, `'Gold 52'`, `'Silver 42'`, `'Bronze 32'` |
| Xeon E-2100, E-2200 (all core counts) | Coffee Lake (+Refresh) | `'E-21'`, `'E-22'` (E-2300 Rocket Lake not matched) |
| Atom C3000 | Denverton | `'Atom(TM) CPU C3'` |

Notes:
- AMD needs per-model enumeration because the generation digit is the
  LAST of four (7xx1 vs 7xx2 vs supported 7xx3) — a bare `'EPYC 7'`
  would wrongly sweep Milan/Genoa. 33 AMD literals total; formula-length
  tolerance is part of what the probe/author validates.
- Every pattern must be checked against recon's live string sample;
  patterns matching nothing in this environment stay in the formula but
  get annotated here (portability: the SM ships correct for other
  environments).
- **Recon caveat (2026-07-22, devel):** the lab fleet is homelab-class —
  9 hosts: `12th Gen Intel(R) Core(TM) i7-1260P` ×4,
  `AMD Ryzen 9 9955HX 16-Core Processor` ×4,
  `Intel(R) Celeron(R) J6412 @ 2.00GHz` ×1. NO KB-318697-listed CPU is
  present, so every KB pattern legitimately matches zero hosts here and
  all hosts will read 0 (supported). The probe validates the where-
  dialect MECHANISM with lab-real literals (`'i7-1260P'`); byte-exact
  pattern fidelity against production Xeon/EPYC strings could not be
  verified on this instance and the patterns rest on the canonical
  vendor string shapes documented above. Re-verify on a production
  fleet when available.

## Production-fleet validation and tier 4 (2026-07-23)

**Validation summary:** the SM (and its cluster-level max() roll-up)
was validated against a real 324-host production inventory covering
46 distinct `cpu|cpuModel` strings.

- Zero false positives across the 226 hosts that read 0/supported —
  every one of those CPU strings was independently confirmed to be
  outside all KB-318697 deprecated/discontinued families.
- All KB-318697 family matches (tiers 1-3) were confirmed correct
  against the fleet's actual strings — no pattern over-matched or
  under-matched a family it wasn't intended for.
- 40 of 324 hosts carried CPU models that predate KB 318697's scope
  entirely (the KB only covers CPUs transitioning within VCF 9.x):
  Haswell (Xeon E5 vN "v3"), Ivy Bridge ("v2"), and Sandy Bridge
  (bare "0" generation marker, e.g. `E5-2640 0 @ 2.50GHz`). Under the
  original 0-3 scheme these 40 hosts read 0/supported, which is wrong
  in spirit — they are not "supported," they are simply not
  addressed by this KB. This population motivated a new, most-severe
  tier 4 rather than silently continuing to read as tier 0.

**User decision:** tier 4 is distinct from tier 3
(discontinued-per-KB), not folded into it. Rationale: tier 3 hosts
are named in KB 318697 as actively being discontinued across VCF
9.x; tier 4 hosts are old enough that the KB doesn't discuss them at
all — a meaningfully different (and more severe) risk category for
an admin doing capacity/refresh planning. Tier 4 is checked *first*
in the chained ternary (most-severe-first ordering), so it wins over
any coincidental tier 1-3 substring match.

**New tier-4 patterns (validated against the 324-host fleet):**

| Generation | Example fleet string | Pattern | Rationale |
|---|---|---|---|
| Haswell (Xeon E5 v3) | `Intel(R) Xeon(R) CPU E5-2650 v3 @ 2.30GHz` | `' v3'` | No modern (post-9.0-relevant) Xeon carries a `vN` version suffix of "3"; disjoint from the existing `' v4'`/`' v5'`/`' v6'` tier-3/2 patterns by construction. |
| Ivy Bridge (Xeon E5 v2) | `Intel(R) Xeon(R) CPU E5-2420 v2 @ 1.90GHz` | `' v2 '` (leading AND trailing space) | The trailing space distinguishes the version suffix from incidental substring collisions (e.g. avoids matching inside longer tokens); confirmed present in the fleet's Ivy Bridge strings exactly as `... v2 @ ...`. |
| Sandy Bridge | `Intel(R) Xeon(R) CPU E5-2640 0 @ 2.50GHz` | `' 0 @'` | Sandy Bridge-era Xeons report a bare `0` generation marker (no `vN` suffix existed yet) immediately before the clock-speed `@`; ` 0 @` isolates that shape from unrelated zeros elsewhere in the string. |

All three patterns are disjoint from each other and from the
existing tier 1-3 pattern set (checked against the full 46-string
fleet vocabulary, not just the tier-4 subset).

**Latent risk — case sensitivity (not fixed, flagged for awareness):**
matching is case-sensitive (per the existing Dialect B where-clause
mechanism; unchanged by this update). The 324-host fleet contained
one CPU model string reported in ALL CAPS:
`INTEL(R) XEON(R) SILVER 4514Y`. This host is genuinely
supported (Sapphire Rapids, not in any tier 1-4 pattern set), so the
case mismatch is harmless *today* — it already reads 0, correctly,
just not via any pattern match. However, if a fleet ever reports a
deprecated/discontinued/unsupported CPU model in all-uppercase (some
BIOS/firmware versions are known to vary `cpu|cpuModel` casing), none
of the tier 1-4 patterns (`'Gold 61'`, `' v3'`, `'EPYC 7551'`, etc.)
would match against the uppercased string, and that host would
silently read 0/supported when it should read 1-4. This is a known
gap, not addressed by this change — case-insensitive matching is not
available in the current where-dialect (see
knowledge/context/authoring/supermetric_authoring.md for dialect
capabilities). Flagging for future revisit if an uppercase-reporting
fleet surfaces a deprecated/discontinued CPU in practice.

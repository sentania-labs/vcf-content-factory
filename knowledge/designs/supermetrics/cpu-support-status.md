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

## Tier-4 family-complete expansion (2026-07-23, Codex P1 on PR #66)

Codex flagged that tier 4 covered only the three production-sampled
generations — a Westmere `X5670` or AMD Opteron still read 0. Expanded
to family-complete coverage. Mechanism gate: the Dialect-B
`contains && !(contains)` combo was probed on devel first
(probe_where_and_negation, sm_467dfab5…): 9/9 hosts matched ground
truth (four i7-1260P → 1, five Ryzen/Celeron → 0); probe deleted from
instance and repo after the run.

Tier-4 structure: FOUR count() terms summed, ternaried, checked first:
1. Literals: ' v3', ' v2 ', 'Opteron', ' X55', ' X56', ' E55',
   ' E56', ' L55', ' L56' (Haswell/Ivy literals + Nehalem/Westmere-EP
   55xx/56xx families + all Opterons). ' 0 @' dropped (subsumed by 2).
2. `contains 'E5-' && !(contains ' v')` — bare Sandy Bridge E5
   (incl. the "E5-2640 0 @" form).
3. `contains 'E7-' && !(contains ' v')` — Westmere/Nehalem-EX E7.
4. `contains 'E3-' && !(contains ' v')` — bare Sandy Bridge E3.

Disjointness: the three bare-prefix terms exclude every vN-suffixed
part (v2/v3 → term 1; v4/v5/v6 → tiers 3/2, checked later); 'E3-'
cannot occur in tier-1's 'E-21'/'E-22' strings (dash follows E);
' E55'/' E56' (leading space) never match 'E5-…' modern strings.
Fleet re-simulation: 324 hosts → identical results to the pre-expansion
run (40×tier4, 98×tiers1-3, 186×0) + synthetic Westmere/Opteron/EX
strings now classify 4.

## Tier-4 universe rebuild (2026-07-23, ESX 6.7/7.0/8.0-derived — user direction)

User direction after three rounds of reactive pattern gaps (Codex P1s on
dist PRs): "reference any CPUs that were supported in ESX 7 and 8 — so
that our dashboard accurately reflects 9.0, 9.1, 9.2 and beyond
expectations." Tier 4 rebuilt construction-complete from the researched
support universe (full table: research artifact esx-cpu-support-universe.md,
summarized below; five count() terms, tiers 3/2/1/0 untouched).

# ESXi CPU-generation support universe (6.x → VCF 9.x)

Compiled 2026-07-23 from primary sources. Purpose: complete substring-classification
universe for a dashboard supermetric doing case-sensitive `contains` on the ESXi
`cpuModel` brand string.

## Sources (primary unless noted)

1. **Broadcom KB 318697** — "CPU Support Deprecation and Discontinuation In VCF Releases"
   (also reachable as `legacyId=82794`; the historic VMware KB 82794 now redirects here).
   https://knowledge.broadcom.com/external/article/318697/cpu-support-deprecation-and-discontinuat.html
   Authoritative for the VCF 9.x deprecated/discontinued tables. **Confirmed unchanged:**
   6 deprecated rows, 9 discontinued rows (3 of them "starting 9.2").
2. **Broadcom KB 428874** — "Deprecated CPU Systems / Servers in ESX 9.0 and implications
   for support". https://knowledge.broadcom.com/external/article/428874
   Confirms Cascade Lake deprecated-but-supported through 9.x, and that Skylake was
   originally discontinued at 9.0 then moved to "Deprecated Mode for VCF 9.1.x only"
   (i.e., discontinued starting 9.2 — matches KB 318697).
3. **vSphere 7.0 Release Notes** (Broadcom TechDocs).
   https://techdocs.broadcom.com/us/en/vmware-cis/vsphere/vsphere/7-0/release-notes/vsphere-esxi-vcenter-server-70-release-notes.html
   7.0 newly drops: Intel Family 6 Model 2C (Westmere-EP), Model 2F (Westmere-EX).
   7.0 deprecates (still runs, warned): Model 2A (Sandy Bridge DT/EN), 2D (Sandy
   Bridge-EP), 3A (Ivy Bridge DT/EN), AMD Family 15h Model 01 (Bulldozer).
4. **vSphere 6.7 Release Notes** (Broadcom TechDocs PDF).
   https://techdocs.broadcom.com/content/dam/broadcom/techdocs/us/en/pdf/vmware/vsphere/vsphere/vSphere-6-7-Release-Notes/vsphere-esxi-vcenter-server-67-release-notes.pdf
   Verbatim drop list vs 6.5: AMD Opteron 13xx/23xx/24xx/41xx/61xx/83xx/84xx;
   Intel Xeon 31xx/33xx/34xx(Clarkdale)/34xx(Lynnfield)/35xx/36xx/52xx/54xx/55xx/
   56xx/65xx/74xx/75xx; Core i7-620LE; Clarkdale i3/i5.
   Deprecated in 6.7 (dropped later): Xeon E3-1200 (SNB-DT), Xeon E7-2800/4800/8800 (WSM-EX).
5. **Historic VMware KB 82794 content** ("Updated Plan for CPU Support Discontinuation In
   Future Major vSphere Releases after 7.0") — archived copy at
   https://vdan.cz/vmware/esxi/updated-plan-for-cpu-support-discontinuation-in-future-major-vsphere-releases-after-7-0-82794/
   (secondary mirror of the KB): the 7.0-era warned list = Sandy Bridge (E3-11xx/12xx,
   E5-1400/1600/2400/2600/4600 v1), Ivy Bridge (v2 incl. E7 v2), Haswell (v3 incl. E7 v3),
   Broadwell-DT/H (E3-1200 v4), Avoton (Atom C2xxx), AMD Bulldozer 6200/4200/3200,
   Piledriver 6300/4300/3300, Steamroller/Kyoto — all of which ESXi 8.0 then blocked.
6. **vSphere 8.0 CPU floor** — 8.0 installer blocks SandyBridge-DT/EP/EN, IvyBridge
   (DT/EP/EN/EX), Haswell (DT/EP/EX), Broadwell-DT/H, Avoton, AMD Bulldozer/Piledriver/
   Steamroller/Kyoto (bypassable with `allowLegacyCPU=true`, unsupported; 8.0U2
   additionally hard-requires XSAVE). Broadwell-EP/EX/DE and later remain supported in
   8.x. Secondary corroboration: williamlam.com/2022/09/homelab-considerations-for-vsphere-8.html
   (reproduces the 8.0 installer list); Broadcom 8.0 Release Notes point to KB 82794/318697.

Note on the "KB 88325" the task brief mentions: no article with that ID surfaces any
more; its content ("CPU Support Deprecation In vSphere 8.x") was folded into what is
now KB 318697 / legacyId 82794.

---

## Master table

Tier legend: **0** supported 9.x · **1** KB 318697 deprecated in 9.x · **2** KB 318697
discontinued starting 9.2 · **3** KB 318697 discontinued at 9.0 · **4** died at/before
8.0 (or cannot install 9.0) and has NO KB 318697 row · **?** ambiguous (flagged below).

`cpuModel` shapes are the canonical Intel/AMD brand strings ESXi reports verbatim.
Watch the quirks: Core2/Nehalem/Westmere strings have **no family prefix letter before
"CPU"** is false — they have "CPU <model>"; Sandy Bridge E3 has **no hyphen** (`E31230`);
Sandy Bridge E5 has a **trailing " 0"**; Westmere-EX has a **space after the hyphen**
(`E7- 4870`); Ivy Bridge E3 uses **capital "V2"** while E5/E7 v2 use lowercase.

### Intel

| Generation (codename) | Model families | Last ESXi | cpuModel string shape (example) | Tier |
|---|---|---|---|---|
| Pentium 4-era Xeon MP (Paxville/Tulsa 71xx), Dempsey 50xx | 7020-7150N, 5030-5080 | 6.0/6.5 | `Intel(R) Xeon(TM) CPU 3.20GHz`, `Intel(R) Xeon(R) CPU 7140M @ 3.40GHz` | 4 |
| Core2 Woodcrest/Clovertown | 51xx / 53xx (E/X/L5335…) | 6.5 | `Intel(R) Xeon(R) CPU 5160 @ 3.00GHz`, `... CPU E5345 @ 2.33GHz`, `... CPU X5355 @ 2.66GHz` | 4 |
| Core2 Wolfdale/Harpertown | 52xx / 54xx (E5205, X5460, L5420) | 6.5 | `Intel(R) Xeon(R) CPU X5460 @ 3.16GHz`, `... CPU L5420 @ 2.50GHz` | 4 |
| Core2 Tigerton/Dunnington | 73xx / 74xx (E7330, X7460) | 6.5 | `Intel(R) Xeon(R) CPU E7330 @ 2.40GHz`, `... CPU X7460 @ 2.66GHz` | 4 |
| Core2 UP Xeon 3xxx | 30xx/32xx/31xx/33xx (X3220, X3360) | 6.5 | `Intel(R) Xeon(R) CPU X3360 @ 2.83GHz` | 4 |
| Nehalem-EP (Gainestown) | 55xx: X/E/L/W55xx | 6.5 (6.7 RN drop list) | `Intel(R) Xeon(R) CPU X5570 @ 2.93GHz`, `... CPU E5540 @ 2.53GHz`, `... CPU L5520 @ 2.26GHz` | 4 |
| Lynnfield / Clarkdale UP | 34xx: X/L34xx, i3/i5 Clarkdale, W35xx/36xx Bloomfield/Gulftown | 6.5 | `Intel(R) Xeon(R) CPU X3470 @ 2.93GHz`, `... CPU L3426 @ 1.87GHz`, `... CPU W3565 @ 3.20GHz` | 4 |
| Beckton (Nehalem-EX) | 65xx/75xx: X/E/L65xx-75xx | 6.5 | `Intel(R) Xeon(R) CPU X7560 @ 2.27GHz`, `... CPU E6540 @ 2.00GHz`, `... CPU L7555 @ 1.87GHz` | 4 |
| Westmere-EP (Gulftown) | 56xx: X/E/L56xx, W36xx | 6.5 (6.7 RN drop list; 7.0 RN also names Model 2C) | `Intel(R) Xeon(R) CPU X5680 @ 3.33GHz`, `... CPU E5645 @ 2.40GHz`, `... CPU L5640 @ 2.27GHz` | 4 |
| Westmere-EX | E7-2800/4800/8800 (v1) | 6.7 (deprecated in 6.7, dropped 7.0, Model 2F) | `Intel(R) Xeon(R) CPU E7- 4870 @ 2.40GHz` ← **space after hyphen** | 4 |
| Sandy Bridge E3 (SNB-DT) | E3-1200/1100 v1 | 7.0 | `Intel(R) Xeon(R) CPU E31230 @ 3.20GHz` ← **no hyphen** | 4 |
| Sandy Bridge-EP/EN | E5-1600/2400/2600/4600 v1 | 7.0 | `Intel(R) Xeon(R) CPU E5-2670 0 @ 2.60GHz` ← **trailing " 0"** | 4 |
| Ivy Bridge E3 | E3-1200 v2 | 7.0 | `Intel(R) Xeon(R) CPU E3-1230 V2 @ 3.30GHz` ← **capital V2** | 4 |
| Ivy Bridge-EP/EN/EX | E5 v2, E7-2800/4800/8800 v2 | 7.0 | `Intel(R) Xeon(R) CPU E5-2680 v2 @ 2.80GHz`, `... CPU E7-4880 v2 @ 2.50GHz` | 4 |
| Haswell (all: DT/EP/EX) | E3 v3, E5 v3, E7 v3 | 7.0 | `Intel(R) Xeon(R) CPU E5-2670 v3 @ 2.30GHz`, `... CPU E3-1231 v3 @ 3.40GHz` | 4 |
| Broadwell-DT/H | E3-1200 v4, i7-5700EQ | 7.0 | `Intel(R) Xeon(R) CPU E3-1265L v4 @ 2.30GHz` | 4 |
| Avoton (Atom) | C2300/2500/2700 | 7.0 | `Intel(R) Atom(TM) CPU C2750 @ 2.40GHz` | 4 |
| Broadwell-EP/EX | E5-1600/2600/4600 v4, E7-4800/8800 v4 | 8.x | `Intel(R) Xeon(R) CPU E5-2680 v4 @ 2.40GHz`, `... CPU E7-8880 v4 @ 2.20GHz` | 3 |
| Broadwell-DE | Xeon D-1500 | 8.x | `Intel(R) Xeon(R) CPU D-1541 @ 2.10GHz` | 3 |
| Skylake-S (E3 v5) | E3-1200/1500 v5 | 9.1 | `Intel(R) Xeon(R) CPU E3-1270 v5 @ 3.60GHz` | 2 |
| Kaby Lake-S (E3 v6) | E3-1200 v6 (E3-1500 v6 unlisted — see ambiguities) | 8.x | `Intel(R) Xeon(R) CPU E3-1270 v6 @ 3.80GHz` | 3 |
| Skylake-SP | Platinum 81xx, Gold 61xx/51xx, Silver 41xx, Bronze 31xx | 9.1 | `Intel(R) Xeon(R) Gold 6130 CPU @ 2.10GHz`, `... Platinum 8168 CPU @ 2.70GHz` | 2 |
| Skylake-D | Xeon D-2100 | 9.1 | `Intel(R) Xeon(R) D-2146NT CPU @ 2.30GHz` | 2 |
| Skylake-W | Xeon W-2100 | 8.x | `Intel(R) Xeon(R) W-2155 CPU @ 3.30GHz` | 3 |
| Coffee Lake (E-2100/2200) | Xeon E-2100, E-2200 (4/6/8-core) | 9.x deprecated | `Intel(R) Xeon(R) E-2278G CPU @ 3.40GHz` | 1 |
| Denverton (Atom) | C3000 | 9.x deprecated | `Intel(R) Atom(TM) CPU C3758 @ 2.20GHz` | 1 |
| Cascade Lake-SP/Refresh | Platinum 82xx, Gold 62xx/52xx, Silver 42xx, Bronze 32xx | 9.x deprecated | `Intel(R) Xeon(R) Gold 6230 CPU @ 2.10GHz` | 1 |
| Cascade Lake-W | W-2200/W-3200 | ? | `Intel(R) Xeon(R) W-2265 CPU @ 3.50GHz` | ? |
| Cascade Lake-AP | Platinum 9200 | ? | `Intel(R) Xeon(R) Platinum 9242 CPU @ 2.30GHz` | ? |
| Hewitt Lake | Xeon D-1600 | ? | `Intel(R) Xeon(R) D-1637 CPU @ 2.90GHz` | ? |
| Cooper Lake | Platinum 83xxH(L), Gold 63xxH/53xxH | 9.x | `Intel(R) Xeon(R) Gold 6328H CPU @ 2.80GHz` | 0 |
| Ice Lake-SP | Platinum 83xx, Gold 63xx/53xx, Silver 43xx | 9.x | `Intel(R) Xeon(R) Gold 6330 CPU @ 2.00GHz` | 0 |
| Ice Lake-D | D-1700/D-2700 (later D-1800/D-2800) | 9.x | `Intel(R) Xeon(R) D-2776NT CPU @ 2.10GHz` | 0 |
| Ice Lake-W | W-3300 | 9.x | `Intel(R) Xeon(R) W-3345 CPU @ 3.00GHz` | 0 |
| Rocket Lake E | Xeon E-2300 | 9.x | `Intel(R) Xeon(R) E-2378 CPU @ 2.60GHz` | 0 |
| Raptor Lake E | Xeon E-2400 | 9.x | `Intel(R) Xeon(R) E-2488` (new short form, no "CPU @ freq") | 0 |
| Sapphire Rapids | Platinum 84xx, Gold 64xx/54xx, Silver 44xx, Bronze 34xx, w-2400/w-3400 | 9.x | `Intel(R) Xeon(R) Platinum 8480+`, `Intel(R) Xeon(R) Gold 6430`, `Intel(R) Xeon(R) w9-3475X` | 0 |
| Xeon Max (SPR-HBM) | Max 94xx | 9.x | `Intel(R) Xeon(R) CPU Max 9480` | 0 |
| Emerald Rapids | Platinum 85xx, Gold 65xx/55xx | 9.x | `Intel(R) Xeon(R) Platinum 8592+`, `... Gold 6526Y` | 0 |
| Granite Rapids / Sierra Forest ("Xeon 6") | 6xxxP / 6xxxE | 9.x | `Intel(R) Xeon(R) 6767P`, `INTEL(R) XEON(R) 6740E` (case varies by BIOS!) | 0 |

### AMD

| Generation | Model families | Last ESXi | cpuModel string shape | Tier |
|---|---|---|---|---|
| Opteron K8 (SledgeHammer→Santa Rosa) | 1xx/2xx/8xx, 12xx/22xx/82xx | 5.5/6.0 | `AMD Opteron(tm) Processor 250`, `Dual-Core AMD Opteron(tm) Processor 2218` | 4 |
| Opteron K10 Barcelona/Shanghai/Istanbul | 13xx/23xx/83xx, 24xx/84xx | 6.5 | `Quad-Core AMD Opteron(tm) Processor 2356`, `Six-Core AMD Opteron(tm) Processor 2427` | 4 |
| Opteron Lisbon/Magny-Cours | 41xx/61xx | 6.5 | `AMD Opteron(tm) Processor 6174` | 4 |
| Opteron Bulldozer (Interlagos/Valencia/Zurich) | 62xx/42xx/32xx | 7.0 | `AMD Opteron(tm) Processor 6276` | 4 |
| Opteron Piledriver (Abu Dhabi/Seoul/Delhi) | 63xx/43xx/33xx, X2250/X1250 | 7.0 | `AMD Opteron(tm) Processor 6380` | 4 |
| Opteron Steamroller/Kyoto | X1100/X2100 | 7.0 | `AMD Opteron(tm) X2150 ...` | 4 |
| EPYC Naples (Zen, 7001) | 7251–7601, 7xx1P | 9.x deprecated | `AMD EPYC 7601 32-Core Processor`, `AMD EPYC 7551P 32-Core Processor` | 1 |
| EPYC Rome (Zen2, 7002/7Fx2/7H12) | 7232P–7742, 7F32/7F52/7F72, 7H12 | 9.x deprecated | `AMD EPYC 7742 64-Core Processor`, `AMD EPYC 7F52 16-Core Processor` | 1 |
| EPYC 3000 (Snowy Owl, Zen embedded) | 3101–3451 | ? | `AMD EPYC 3251 8-Core Processor` | ? |
| EPYC Milan (Zen3, 7003/7xF3) | 7313–7773X, 72F3–75F3 | 9.x | `AMD EPYC 7763 64-Core Processor` | 0 |
| EPYC Genoa/Bergamo/Genoa-X (Zen4, 9xx4) | 9124–9684X, 97x4 | 9.x | `AMD EPYC 9654 96-Core Processor` | 0 |
| EPYC Siena (Zen4c, 8xx4) / EPYC 4004 | 8024P–8534P, 4124P–4584PX | 9.x | `AMD EPYC 8534P 64-Core Processor` | 0 |
| EPYC Turin (Zen5, 9xx5) | 9015–9965 | 9.x | `AMD EPYC 9755 128-Core Processor` | 0 |

---

## Substring classification (case-sensitive `contains` on cpuModel)

Modern universe collision-checked against: `... Bronze/Silver/Gold/Platinum {3,4,5,6,8}xxx CPU @ ...`
and new short forms (`Platinum 8480+`, `Gold 6430`), `Xeon(R) 6xxxP/E` (Granite/Sierra),
`E-2xxx CPU @`, `D-1xxx/D-2xxx CPU @`, `W-2xxx/W-3xxx CPU @`, `w7-2495X`-style, `CPU Max 94xx`,
`AMD EPYC <sku> NN-Core Processor` (7xx1…9xx5, 7V12 cloud SKUs).

### Tier 4 pattern set (dead pre-9.0, no KB row)

| Substring(s) | Catches | Collision check vs modern |
|---|---|---|
| `Opteron` | Every pre-EPYC AMD server CPU, all generations | EPYC strings never contain "Opteron". SAFE. Single pattern covers all tier-4 AMD. |
| `Xeon(TM)` | Netburst-era Xeon MP/DP | Modern strings all use `Xeon(R)`. SAFE. |
| `CPU X` | X3xxx, X5xxx, X7xxx (Core2 UP, Harpertown, Nehalem/Westmere-EP, Beckton, Tigerton) | Only modern "CPU <letter>" is `CPU Max` (`CPU M`). SAFE. |
| `CPU L` | L3426, L5420, L5520, L5640, L7555 | Same argument. SAFE. |
| `CPU W` | W3565/W3690 Bloomfield/Gulftown workstation Xeons | Modern W-series is `W-2155 CPU @` (W before CPU). SAFE. |
| `CPU 5`, `CPU 7`, `CPU 3` | Digit-only families: 5160, 5060, 7140M, E7330-era boards that report bare numbers | Modern strings never have a digit right after `CPU ` (always `CPU @` or `CPU Max`). SAFE. |
| `CPU E5-` **minus** ` v4 ` — or positively: ` 0 @` | Sandy Bridge-EP (`E5-2670 0 @`) | ` 0 @` (space-zero-space-at) appears in no modern string (modern = `... CPU @ 2.10GHz` or no @). SAFE and uniquely Sandy-EP. |
| ` E31` | Sandy Bridge E3 (`CPU E31230 @`) | Modern E-series is ` E-2`; Ice Lake `Gold 6314U` contains ` 6314` not ` E31`. SAFE. |
| ` E55`, ` E56`, ` E53`, ` E54`, ` E52`, ` E65`, ` E75`, ` E72`, ` E73`, ` E74` (as `CPU E55` etc. for extra margin) | Nehalem-EP E55xx, Westmere-EP E56xx, Core2 E53xx/E54xx/E52xx, Beckton E65xx/E75xx, Tigerton/Dunnington E72xx/E73xx/E74xx | Modern E-series always has hyphen (`E-2288G`); v-series E5s have hyphen (`E5-2680`). No modern string contains `CPU E5<digit>`/`CPU E7<digit>` without hyphen. SAFE. |
| `CPU E7- ` (trailing space) | Westmere-EX (`E7- 4870`) | Broadwell `E7-8880 v4` has a digit after the hyphen, not a space. SAFE — and required, since these strings otherwise look like modern-ish E7s. |
| ` v2 ` **and** ` V2 ` | All Ivy Bridge (E5/E7 v2 lowercase; E3 V2 capital) | No modern string contains space-v2-space in either case (EPYC cloud SKU `7V12` has no spaces around V2). SAFE. |
| ` v3 ` | All Haswell (E3/E5/E7 v3) | No modern string contains ` v3 `. SAFE. |
| `CPU C2` | Avoton Atom C2xxx | Denverton (tier 1) is `CPU C37`/`C3` — `CPU C2` ≠ `CPU C3`. SAFE. |
| ` E3-12` + ` v4 ` (both required) | Broadwell-DT/H E3-1200 v4 — the one tier-4 family whose suffix (` v4 `) belongs to tier 3 | If the SM engine can't AND two contains, accept E3 v4 misclassifying into tier 3 (rare parts, one tier off) and document it. |

Practical minimal tier-4 set if you want few patterns and evaluate tiers in
most-specific-first order: `Opteron`, `Xeon(TM)`, `CPU X`, `CPU L`, `CPU W`,
`CPU 5`, `CPU 7`, `CPU 3`, `CPU E5`, `CPU E6`, `CPU E7- `, ` E31`, ` 0 @`,
` v2 `, ` V2 `, ` v3 `, `CPU C2` — where `CPU E5`/`CPU E6` (no hyphen enforcement
impossible with contains; `CPU E5` also matches `CPU E5-2680 v4`) **must be
evaluated AFTER the tier-3 ` v4 ` check**. If evaluation order is not available,
use the hyphen-free digit forms (`CPU E55` … `CPU E75`) listed above, which are
order-independent.

### Tier 3 (KB 318697 discontinued at 9.0)

| Substring | Catches | Collision notes |
|---|---|---|
| ` v4 ` | Broadwell E5/E7 v4 (also swallows E3 v4 = tier 4, see above) | No modern/other-tier string contains ` v4 `. |
| ` D-15` | Xeon D-1500 | Ice Lake-D is ` D-17`/` D-27`/` D-18`/` D-28`; Skylake-D ` D-21`. SAFE. |
| ` v6 ` | Kaby Lake E3 v6 | Unique. |
| ` W-21` | Skylake-W W-2100 | Cascade-W is ` W-22`/` W-32`; new workstation is lowercase ` w7-`/` w9-`. SAFE. |

### Tier 2 (discontinued starting 9.2)

| Substring | Catches | Collision notes |
|---|---|---|
| ` v5 ` | Skylake-S E3 v5 | Unique. |
| `Platinum 81`, `Gold 61`, `Gold 51`, `Silver 41`, `Bronze 31` | Skylake-SP | Cascade = x2xx (`Platinum 82`…), Ice = x3xx, Sapphire = x4xx, Emerald = x5xx. 4-char digit prefixes never overlap across Scalable gens. `Gold 61` vs Granite `Xeon(R) 67xxP`: Granite strings have no `Gold`. SAFE. |
| ` D-21` | Skylake-D D-2100 | Ice Lake-D ` D-27` etc. SAFE. |

### Tier 1 (deprecated in 9.x)

| Substring | Catches | Collision notes |
|---|---|---|
| `Platinum 82`, `Gold 62`, `Gold 52`, `Silver 42`, `Bronze 32` | Cascade Lake-SP/Refresh | Distinct from 81/61/51/41/31 (tier 2) and x3xx+ (tier 0). |
| ` E-21`, ` E-22` | Xeon E-2100/E-2200 | Rocket/Raptor E = ` E-23`/` E-24`. SAFE. |
| `CPU C3` | Atom C3000 Denverton | Avoton = `CPU C2`. SAFE. |
| `EPYC 7` + SKU whitelist (Naples): `EPYC 7251`, `7261`, `7281`, `7301`, `7351`, `7371`, `7401`, `7451`, `7501`, `7551`, `7601` | EPYC 7001 (P-variants contain the base SKU, e.g. `7551P` ⊃ `7551`) | 4-digit SKUs required: 3-digit prefixes collide with Rome (e.g. `725` hits 7251 Naples AND 7252 Rome). None of these 11 strings appear inside any Milan/Genoa/Turin SKU. |
| Rome whitelist: `EPYC 7232`, `7252`, `7262`, `7272`, `7282`, `7302`, `7352`, `7402`, `7452`, `7502`, `7532`, `7542`, `7552`, `7642`, `7662`, `7702`, `7742`, `7H12`, `7F32`, `7F52`, `7F72` | EPYC 7002/7Fx2/7H12 | Checked against Milan (7xx3, 7xF3), Genoa (9xx4), Turin (9xx5): no containment collisions. |

### Tier 0 = everything not matched above (residual bucket)
Includes Cooper/Ice/Sapphire/Emerald/Granite/Sierra Forest, Xeon Max, E-23xx/24xx,
D-17xx/27xx/18xx/28xx, W-33xx / w-24xx / w-34xx, EPYC 7003/8004/9004/9005/4004.
Recommend tier 0 be the fall-through default, with tiers evaluated 4 → 3 → 2 → 1
(most-dead first) or in any order if using the order-independent tier-4 set.

---

## Ambiguous families (in 8.x VCG, absent from KB 318697, not obviously current)

Flagged, not guessed — verify in the Broadcom Compatibility Guide before assigning:

1. **Xeon W-2200 / W-3200 (Cascade Lake-W)** — sibling W-2100 is discontinued 9.x, and
   Cascade-SP is deprecated 9.x, but KB 318697 has no W-22xx/W-32xx row.
2. **Xeon Platinum 9200 (Cascade Lake-AP)** — not listed with the Platinum 8200 row.
   Likely shares Cascade deprecation; unconfirmed.
3. **Xeon D-1600 (Hewitt Lake)** — Broadwell-derived like the discontinued D-1500 but
   absent from KB 318697.
4. **Xeon E3-1500 v6** — KB row names only "E3-1200-v6". Near-certainly same fate; the
   ` v6 ` substring covers both regardless.
5. **AMD EPYC 3000 (Snowy Owl, Zen 1)** — same core as deprecated Naples, no KB row.
6. **Cooper Lake (x3xxH)** — absent from KB 318697, treated here as tier 0 (supported);
   note its `Gold 63xxH` strings match the tier-0 residual, not `Gold 62` (SAFE).

Dashboard handling suggestion: W-22xx/W-32xx and EPYC 3xxx get explicit "verify"
patterns (` W-22`, ` W-32`, whitelist of EPYC 3101/3151/3201/3251/3255/3301/3351/3401/3451)
routed to an "ambiguous/verify" bucket rather than silently falling into tier 0.

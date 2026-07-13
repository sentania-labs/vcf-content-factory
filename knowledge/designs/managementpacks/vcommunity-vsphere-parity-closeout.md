# vcommunity-vsphere — parity closeout (license alert, VOA reports, missing views)

## Initial prompt (verbatim, 2026-07-09 session)

> Review the vcommunity vsphere pak for parity against the source python
> pak for the vsphere aspects

(after the parity review reported collector parity FULL, content parity
PARTIAL:)

> Let’s close those gaps, licenses, voa, missing views.  Please make
> sure the licensing alerts and reports and metrics reflect, 8 vs 9.0
> vs 9.2 realities of licensing

## Vision

Close the three real gap classes from
`knowledge/context/reviews/vcommunity-vsphere-parity-vs-source.md`:

1. **Licensing alert** — port `ESXi Host License Expiring`
   (symptom + alert on the already-collected
   `vCommunity|Licensing:*|Remaining Days` surface) — but **version-aware**.
   The user (VCF Ops SME) explicitly flags that licensing semantics
   changed across vSphere/VCF 8.x → 9.0 → 9.1 (user corrected "9.2"
   to "9.1" — the labs' actual version). Recon 2026-07-09 verified:
   9.1 subscription-term keys (`esx.vcf.entitlement.*`) carry real
   expiry dates and Remaining Days flows; 8.x perpetual keys are the
   blind case, and our collector already handles it correctly by
   emitting NO Remaining Days metric on null expiration (never a
   sentinel) — so "no expiry date" structurally cannot read as
   "expiring". Symptoms must be `instanced: true` against
   `vCommunity|Licensing:<name>|Remaining Days` — the source pak's
   hardcoded-license-name symptoms (an 8.x SKU string) match nothing
   in a 9.x estate and must not be copied. Threshold VALUES from the
   source are kept.

   **TOOLSET GAP (accepted, routed to tooling):** the view renderer
   lacks instanced-group columns (source's `isInstancedGroup` /
   `GROUP_vCommunity` attributes-selector — one row per license
   name). Until tooling ships it, the licensing view/report leg is
   blocked, and the already-shipped
   `views/ESXi Host License Information vCommunity.yaml` is broken
   (hardcodes `Licensing:Evaluation Mode`). User approved the tooling
   route 2026-07-09.
2. **VOA reports** — the 16 View-Oriented-Analysis reports the source
   pak ships (plus the input-dashboards template), absent entirely
   from our pak (`reports/` does not exist). Known Phase-2-last work
   from `vcommunity-parity-plan.md`, now due. Licensing-related report
   content honors the same version matrix.
3. **Missing views** — `nfnic VIB Vendor Distribution` + the 3 views
   whose super metrics already exist (`VM Network Top Talkers`,
   `VM Memory Allocation Trend`, `Distributed Port Groups`).

Out of scope: the LOW-ranked `Windows Services vCommunity` view
substitution (OPEN-B1 of the split design — guest-OS surface, revisit
with vcommunity-os), and anything allocated BY-DESIGN to the other two
split members.

Constraints carried from lessons: pak content subdirectory pattern +
SymptomSets ≥2 children (`knowledge/lessons/pak-content-bundling.md`),
four localization bundles + exact localizationKey matching
(`knowledge/lessons/pak-content-localization-bundles.md`) — note the
pak repo has an in-flight localization fix branch
(`fix/localization-raw-keys-build-2`) that this work must build on,
not fight.

## EXECUTED (2026-07-12)

Closeout complete and certified
(`knowledge/context/reviews/vcommunity-vsphere-parity-certification.md`:
PARITY CERTIFIED, 5/5 original gaps closed or deferred-by-design).
Delivered across pak builds 5-10 + factory PRs #46-#49 + sdk-buildkit
1.0.7/1.0.8: 4-tier instanced license alert (version-aware,
no-metric-no-fire), licensing view on instanced-group columns, 4 ported
views incl. Top Talkers (subject.filter), 11 CSV-export VOA reports
(subdir emission), DEF-008 + DEF-009 found/fixed/closed. Deferred by
design, recorded in REFERENCE.md + CHANGELOG: 5 PDF VOA reports +
34-dashboard input-dashboards template (future dashboard-author design);
Windows-surface views (vcommunity-os, OPEN-B1). New residual R1 (LOW):
4 additional nenic/nfnic VIB views in the source's 5-ViewDef container
file, optional future port.

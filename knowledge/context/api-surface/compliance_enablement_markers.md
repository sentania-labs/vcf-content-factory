# Compliance-enablement markers (per component, per instance)

Established 2026-07-23 by dual-instance recon (devel + prod; recon_log.md
dated entry). The reliable procedure for "is compliance enabled on this
component":

1. **`badge|compliance` VALUE is the discriminator, not key presence.**
   The key exists on every VMWARE resource regardless of enablement.
   `GET /api/resources/{id}/stats/latest?statKey=badge|compliance`:
   - `-1.0` → NO compliance alert enabled for this resource
   - `0–100` → at least one compliance-subtype alert enabled and
     evaluating (100 = fully compliant)
   (statkeys listing response field is `stat-key`, not `statKey`.)
2. **Compliance alert definitions are `subType=21`** on
   `/api/alertdefinitions` and `/api/alerts` (BuilderAlertSubType:
   18=AVAILABILITY 19=PERFORMANCE 20=CAPACITY 21=COMPLIANCE
   22=CONFIGURATION — internal-api-9.1.json).
3. **Never infer enablement from definition existence** — prod ships a
   Cluster-targeting SCG def yet cluster badge = -1.0 (not enabled).
4. **Never infer non-enablement from zero active alerts** — prod
   Host/VM show badge=100 with zero firing subType-21 alerts
   ("enabled + fully compliant" looks identical to "disabled" if you
   only count alerts).
5. **Factory compliance pak (`vcfcf_compliance`)**: check
   `GET /api/adapters?adapterKindKey=vcfcf_compliance` (presence +
   `lastCollected` freshness) first; the pushed
   `VCF-CF Compliance|*` keys (score / pass_count / fail_count /
   total_count / unreadable_count / profile_name / per-control
   subtrees) then confirm the ARIA_OPS push landed on the component.
   NOTE: REFERENCE.md documents only the adapter's internal world
   object — the pushed key namespace lives in ComplianceAdapter.java.
6. **Per-policy alert-enablement detail via REST is BLOCKED**:
   `GET /api/policies/{id}` returns HTTP 500 on BOTH devel and prod
   (FB-010, re-scoped 2026-07-23); `/api/policies/{id}/settings` has no
   alert-enablement type. The badge value (marker 1) is the practical
   per-resource substitute.

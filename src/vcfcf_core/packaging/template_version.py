"""Canonical source of truth for the distribution template version.

Format: YYYY-MM-DD-N, where N increments if multiple template versions
ship on the same day.  Both the install-script template emitter and the
staleness-check CLI read from this single constant.

Bump this value whenever any of the following change:
  - vcfcf_packaging/templates/install.py
  - vcfcf_packaging/templates/install.ps1
  - vcfcf_packaging/builder.py  (output structure changes)
  - vcfcf_packaging/discrete_builder.py  (output structure changes)
  - vcfcf_packaging/release_builder.py  (output structure changes)
  - vcfcf_dashboards/render.py  (dashboard or view wire format changes)
  - vcfcf_core/alerts/render.py  (AlertContent.xml wire format changes)

This list is the same one CLAUDE.md carries under "After tooling changes";
keep the two in step.

History (most recent first):
  2026-11-13-1  install.py / install.ps1: a content-import summary whose
                imported + skipped + failed is below total is an error (exit
                2), for every content type; before any import, an install
                whose dashboards carry a widget type above the instance's
                version (Section below 9.1.1) is refused, naming them
                (issue #199; on 8.18.7 and 9.0.2 one such dashboard loses
                every dashboard in the import while the task reports FINISHED)
  2026-11-12-1  content prefix moved to [VCF CF] (from [VCF Content Factory]);
                zips built before carry the legacy names, and re-running one
                reverts the rename (UUID-keyed objects rename back in place,
                name-keyed ones get legacy twins). Bumped so check-staleness
                reports them stale. No template or wire-format change
  2026-11-11-1  install.py / install.ps1: the advisory for a skipped dashboard
                or view import no longer asserts the existing object was not
                updated. It says the import sent force=true, so the
                create-only cause does not apply; a dashboard skip is the
                unmappable usermappings.json owner (the dashboard was never
                created; check view-bridge.log) or unexplained, and a view
                skip is unexplained; both say to report it with the envelope
  2026-11-07-1  install.py / install.ps1: custom groups install before views +
                dashboards (install order 1.5, was 4) so a View widget pinned
                to a helper custom group by name binds at import, and uninstall
                before super metrics (uninstall order 38, was 50) (issue #302)
  2026-10-28-2  alerts/render.py: AlertContent.xml writes a metric_dynamic
                symptom condition in content-import form (type="dtmetric",
                operator above/below/abnormal), not the REST DT_ABOVE on
                type="metric" that the UI import rejected, silently dropping
                the symptom and its alerts. The scripted install path (REST
                symptoms.json) was always correct
  2026-10-28-1  install.py / install.ps1: alert subType defaults to 19 when
                absent or null (was 3, outside the 18-22 enum); out-of-enum
                values skip the alert with a warning. install.ps1 now skips
                an alert on any conversion error instead of aborting the run
                (as install.py already did), and reads optional symptom-set
                threshold fields StrictMode-safely (issue #282)
  2026-10-26-1  install.ps1: post-import dashboard materialization check
                (MATERIALIZATION lines, -SkipMaterializationCheck,
                -MaterializationWait; issue #255)
  2026-10-24-1  install.py: post-import dashboard materialization check
                (MATERIALIZATION lines, --skip-materialization-check,
                --materialization-wait; issue #244). README footers name
                vcfcf_packaging, not the removed vcfops_packaging (#159)
  2026-09-25-1  install.py: an explicit --skip-ssl-verify / VCFOPS_VERIFY_SSL=false
                is no longer overridden by REQUESTS_CA_BUNDLE (issue #174)
  2026-08-29-1  render.py: multi-subject view columns unbound by default,
                bound only via column `subject:` (view wire format change)
  2026-08-24-2  install.ps1: uninstall residual-else sites warn and continue
"""

CURRENT_TEMPLATE_VERSION = "2026-11-13-1"

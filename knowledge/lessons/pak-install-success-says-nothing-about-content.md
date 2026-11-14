# A pak install that reports success says nothing about its content; and a deleted symptom id is burned

**Date:** 2026-11-14. **Cost:** a pak installed "verified" on 9.0.2 and 9.1.1
with 14 views and a report template missing, and on 9.0.2 two alerts with no
conditions; a wrong root cause shipped in a fix branch before a probe run
disproved it.

## The trap

The product's pak installer imports each content directory on its own and
carries on after a failure. One schema error in one file (here a localization
entry with an empty value, `view.<id>.<key>=`) drops every object in that
directory. The install task still finishes, the installer prints nothing, and
the only trace is in the appliance logs. Counting dashboards after install was
not enough: views, report templates, symptoms and alerts were never counted.

The second half looked like the same kind of defect and was not. On 9.0.2 the
symptom import failed with a duplicate-key error on
`SymptomRelationship-SymptomDefinition-<id>`. The pak did define every symptom
twice, so the duplicate was blamed, the layout was changed, and the docs said
so. A probe run with fresh ids showed a twice-defined symptom imports fine. The
real mechanism: deleting a symptom definition (pak uninstall, an upgrade that
drops it, a REST delete) leaves a tombstone; a daily cleaner purges tombstones
older than the retention setting (45 days on the lab instance) but leaves the
relationship row; after that, creating that id again fails forever on that
instance, every other symptom in the same alert file fails with it, and the
alert installs with empty symptom sets. The instance had history with those
ids from another pak months earlier.

## The rules

1. Gate the built pak's `content/` tree (no empty localization value, every
   referenced key present, one definition per content id) and count content by
   id after install, per type. Both exist now:
   `src/vcfcf_core/packaging/pak_content.py` and
   `src/vcfcf_managementpacks/post_install_content.py`.
2. Read presence from list endpoints. On 9.0.2 a deleted symptom still answers
   200 on a read by id.
3. Condition symptoms (`condition_self`) never appear on
   `/api/symptomdefinitions`; check them through the alert's symptom sets.
4. A symptom id that a released pak version drops, or that an uninstall
   removes, must not be reused on that instance after the retention window. A
   symptom that comes back gets a new id. A pak that reuses another pack's
   symptom ids inherits that pack's history on every instance it was ever
   removed from.
5. Before writing a cause into code comments, gate messages and docs, run the
   probe that separates the candidate causes. The fresh-id probe took an hour
   and overturned the explanation.

Evidence: `knowledge/context/investigations/2026-11-14-pak-content-silent-drops.md`,
`knowledge/context/investigations/2026-11-14-symptom-duplicate-key-on-902.md`.

# Content exports leave out three families of symptom and alert definitions (vcf-cf-migrator false "missing")

Date: 2026-11-11, about 15:50 to 16:20 CST. Instances: `devel_8_18`
(Aria Operations 8.18.7, build 25423534), `devel` (VCF Operations 9.0.2,
25431135), `devel_9_1` and `prod` (VCF Operations 9.1.1, 25795063). Read-only
REST plus one content export job per instance (`POST
/api/content/operations/export`, `{"scope":"ALL","contentTypes":
["ALERT_DEFINITIONS","SYMPTOM_DEFINITIONS","RECOMMENDATION_DEFINITIONS",
"NOTIFICATION_RULES"]}`). Inventory and export were taken within two minutes
of each other on each instance. Nothing was created or imported, so there is
nothing to clean up. Zips stayed in the session scratchpad.

Tool under study: `sentania-labs/vcf-cf-migrator` at `7dead31`
(`src/vcfcf_migrator/graph.py`, `_alert_refs`, `_rule_refs`). It refuses to
build a bundle that includes an alert whose `<SymptomSet ref>` or `<Symptom
ref>` names a symptom id absent from `symptomdefs.xml`, and its message says
"an export carries custom content only". On a customer's scope-`ALL` export it
reports 289 such alert-to-symptom edges and 3 notification-rule-to-alert
edges. Companion note for views and dashboards:
`2026-11-11-stock-content-ships-dangling-refs-migrator-false-missing.md`. The
ids below are product content ids. None is a name, owner or other
customer-identifying string.

Labels: **verified** means measured on these instances today. **Inferred**
means it follows from verified facts but was not measured directly.
**Unverified** means not known.

## Answer in one paragraph

Unlike views, a content export is **not** complete for symptom and alert
definitions. On all four instances it leaves out every definition whose
adapter kind is `ALL`, and every symptom whose condition is on a badge score
(`badge|health`, `badge|risk`, `badge|efficiency`) or on the capacity keys
`OnlineCapacityAnalytics|timeRemaining` and
`OnlineCapacityAnalytics|capacityRemainingPercentage`. Nothing else is left
out, and recommendations are exported complete (verified, zero exceptions in
about 8,300 symptoms, 5,300 alerts and 4,300 recommendations). The rule is
keyed on adapter kind and condition key, not on ownership: three
uuid-id symptoms on the `timeRemaining` key on `prod` are left out too. All
52 symptom ids behind the customer's 289 edges are of these families.
They exist on the 8.18.7 lab, and the customer's 289 edges are
**identical, edge for edge,** to the 289 the tool reports on the clean
8.18.7 lab export (verified). The 3 notification-rule edges name
`AlertDefinition-vCenter Operations Adapter-AdapterInstanceIsDownAlert`, an
`ALL` alert that is on every lab instance and in no export (verified).
Separately, the export carries alert-embedded conditions as symptoms (with a
`symptomDefType` attribute) that the REST symptom list does not show, and 9.x
stock alerts ship one dangling symptom reference that REST hides and the
export keeps. What content-zip import does with an alert whose symptom is
absent on the target is unverified (§Q3).

## Q1. Is the export complete for symptoms, alerts and recommendations?

### Counts (verified)

REST inventory: `GET /api/symptomdefinitions` and `GET /api/alertdefinitions`
paged at 1000 (the counts match `pageInfo.totalCount`);
`GET /api/recommendations`, which takes no `page`/`pageSize` and returns
everything with no `pageInfo` in one response. Export counts are the elements
in `symptomdefs.xml`, `alertdefs.xml` and `recommendationdefs.xml`, and agree
with `configuration.json` on every instance.

| Instance | Type | REST | Export | Both | REST only | Export only |
|---|---|---|---|---|---|---|
| 8.18.7 | symptom | 1739 | 1685 | 1628 | 111 | 57 |
| 8.18.7 | alert | 1074 | 1061 | 1061 | 13 | 0 |
| 8.18.7 | recommendation | 807 | 807 | 807 | 0 | 0 |
| 9.0.2 | symptom | 2024 | 2075 | 1968 | 56 | 107 |
| 9.0.2 | alert | 1305 | 1292 | 1292 | 13 | 0 |
| 9.0.2 | recommendation | 1116 | 1116 | 1116 | 0 | 0 |
| 9.1.1 `devel_9_1` | symptom | 2087 | 2237 | 2039 | 48 | 198 |
| 9.1.1 `devel_9_1` | alert | 1330 | 1319 | 1319 | 11 | 0 |
| 9.1.1 `devel_9_1` | recommendation | 1064 | 1064 | 1064 | 0 | 0 |
| 9.1.1 `prod` | symptom | 2457 | 2618 | 2405 | 52 | 213 |
| 9.1.1 `prod` | alert | 1658 | 1646 | 1646 | 12 | 0 |
| 9.1.1 `prod` | recommendation | 1317 | 1317 | 1317 | 0 | 0 |

Notification rules: `prod` 3 on REST, 3 exported; the others have none.

### On REST, not in the export: the exclusion rule (verified)

Every REST-only definition on all four instances is in exactly one of these
families, and no definition of these families is in any export:

| Family | Symptoms left out (8.18.7 / 9.0.2 / `devel_9_1` / `prod`) | Alerts left out |
|---|---|---|
| Adapter kind `ALL` (resource kind `All`): `vCenter Operations Adapter-*` health, risk, efficiency, workload, capacity and adapter-instance symptoms, `ComponentDriftCheck`, `ComponentConfigurationApply`, `vRoWorkflowNotification`, and the `VMWARE-vCenter Operations Adapter-*State*` set | 53 / 53 / 45 / 46 (all `ALL` symptoms on each instance) | 13 / 13 / 11 / 12 (all `ALL` alerts) |
| Condition key `badge|health`, `badge|risk` or `badge|efficiency` on a real adapter kind. On 8.18.7 these are the 54 `SymptomDefinition-CASAdapter-*State*` symptoms (VMWARE VM, host, cluster; AWS EC2; Azure VM; GCP CE; CAS Project) | 54 / 0 / 0 / 0 | n/a |
| Condition key `OnlineCapacityAnalytics|timeRemaining` or `OnlineCapacityAnalytics|capacityRemainingPercentage` | 4 / 3 / 3 / 6 | n/a |

Notes:

- Adapter kind and condition key are the only attributes that separate the
  two sets. No field in the REST JSON does (compared field by field on 8.18.7).
  The `badge|*` keys are in the resource kind's stat-key catalogue
  (`/api/adapterkinds/{ak}/resourcekinds/{rk}/statkeys`), so "the key is not
  a declared stat key" is not the rule. `OnlineCapacityAnalytics|cpu|demand|timeRemaining`,
  `...|mem|demand|timeRemaining` and `...|diskspace|demand|timeRemaining`
  symptoms **are** exported (8.18.7 and the customer export carry them).
- The `timeRemaining` family includes the stock `SymptomDefinition-VMWARE-VMTimeRemaining{Critical,Immediate,Warning}`
  (all four instances) and, on `prod`, three bare-uuid symptoms
  (`SymptomDefinition-27141143-...`, `-699cb1d1-...`, `-8c8b692b-...`,
  "Cluster Compute Resource Time Remaining is ..."). A bare uuid is the id
  shape the UI and `POST /api/symptomdefinitions` produce, and they are in no
  factory content, so they are probably user-created (inferred). So the
  exclusion also drops custom symptoms of these families (verified for these
  three; their authorship is inferred).
- Why the exporter skips them is unverified. A plausible reading is that
  they are evaluated against analytics-computed scores or wildcard kinds that
  the content XML writer does not model, but no log or bytecode was read.
- Ids of the never-exported set are stable across versions where both have
  them: the 9 `vCenter Operations Adapter-*State*` symptoms and
  `AdapterInstanceIsDownAlert` have the same id on 8.18.7, 9.0.2 and 9.1.1
  (verified). The union over the four instances is 117 symptom ids (55
  `CASAdapter-`, 44 `vCenter Operations Adapter-`, 12 `VMWARE-`, 3 bare uuid,
  3 others) and 16 alert ids.

### In the export, not on REST: alert-embedded conditions (verified)

Every export-only symptom carries `symptomDefType="condition_self"` or
`"condition_population"` (57 / 107 / 198 / 213), and no symptom on REST
carries that attribute. These are the conditions written inline in an alert
definition. REST shows them only inside the alert, as
`states[].base-symptom-set.alertConditions[].id = "Condition-<x>"`, while the
export writes `<SymptomDefinition id="SymptomDefinition-<x>"
symptomDefType="...">` and the alert's `<SymptomSet ref>` points at that id.
`GET /api/symptomdefinitions/SymptomDefinition-<x>` returns 404 for them.
Mapping `Condition-<x>` to `SymptomDefinition-<x>` matched 206 of 213 on
`prod`; the other 7 (6 on 9.0.2, 7 on `devel_9_1`, 1 on 8.18.7) are
referenced by no alert, so the export also carries orphaned inline
conditions. The customer export has 96 (76 self, 20 population). The tool
already sees them as symptoms, so they produce no false "missing" edge.

### A dangling stock reference that REST hides (verified)

On 9.0.2 and 9.1.1 the four stock alerts
`AlertDefinition-VcfAdapter-VCFCompliance-NSXManagementClusterViolatingVCFCompliance4dot{2,3,4,5}`
name `SymptomDefinition-NSXTAdapter-ComplianceVIPNotSet`.
That symptom is 404 on both 9.x versions, which ship
`...ComplianceVIPv4NotSet` and `...ComplianceVIPv6NotSet` instead; it exists on
8.18.7. REST shows the slot as an empty set (`"symptomDefinitionIds": []`
between two populated sets); the export keeps `<SymptomSet ref="SymptomDefinition-NSXTAdapter-ComplianceVIPNotSet"/>`.
So the instance stores the reference, the product install accepted it, and a
REST read of the alert cannot reveal it.

## Q2. The customer's 289 alert-to-symptom edges and 3 rule-to-alert edges

Regenerated with `vcfcf_migrator tree <zip> --json` from the pinned venv: 289
`alert -> symptom` edges, 52 distinct symptom ids, 34 source alerts.

**The edge set is identical to the clean 8.18.7 lab export's 289 edges**
(same source alert, same symptom id, every one; verified). It shares 18 edges
with 9.0.2 and none with 9.1.1.

| Class | Symptom ids | Edges | Label |
|---|---|---|---|
| (a) exists on a lab instance as product or pak content, left out of every export by the Q1 rule | 52 | 289 | verified on the lab; that they exist on the customer's instance is inferred from the identical edge set |
| (b) of a pak the lab does not have | 0 | 0 | verified |
| (c) customer-authored, absent everywhere | 0 | 0 | verified |

Class (a) by family and by the symptom's adapter kind:

| Id family | Rule family | Adapter kind | Ids | Lab instances that have them |
|---|---|---|---|---|
| `SymptomDefinition-CASAdapter-*State*` | `badge|*` key | MicrosoftAzureAdapter | 9 | 8.18.7 |
| same | same | AmazonAWSAdapter | 9 | 8.18.7 |
| same | same | GoogleCloudPlatformAdapter | 9 | 8.18.7 |
| same | same | VMWARE | 9 | 8.18.7 |
| same | same | CASAdapter (Project) | 6 | 8.18.7 |
| `SymptomDefinition-CASAdapter-CapacityRemaining` | `capacityRemainingPercentage` key | CASAdapter (CloudZone) | 1 | 8.18.7 |
| `SymptomDefinition-vCenter Operations Adapter-{Health,Risk,Efficiency}State{Red,Orange,Yellow}` | adapter kind `ALL` | ALL | 9 | all four |

The 34 source alerts are themselves stock pak alerts, all present in the
8.18.7 lab export: 28 `AlertDefinition-CASAdapter-*` (the Aria Automation 8.x
`CASAdapter` content) and 6 `AlertDefinition-Container-*`
(Application/Tier Health, Risk, Efficiency). None has a bare-uuid id. The
`CASAdapter` adapter kind is installed on 8.18.7 and absent on both 9.1.1
instances (`GET /api/adapterkinds`), so on a 9.x target the 28 `CASAdapter`
alerts and their 43 symptoms would not be supplied by any pak (inferred; not
tested whether the 8.x pak installs on 9.x). The 6 Container alerts and the 9
`ALL` symptoms are on 9.0.2.

Notification-rule edges: all 3 rules name
`AlertDefinition-vCenter Operations Adapter-AdapterInstanceIsDownAlert`
("Adapter instance Object is down", adapter kind `ALL`). It is on REST on all
four lab instances and in no export. Class (a), 3 of 3 (verified on the lab;
inferred for the customer's instance).

## Q3. What does import do with an alert whose symptom is not, or is, on the target?

Known (verified, but not by content-zip import):

- **Pak and product install accept an alert whose symptom does not exist.**
  The 9.x stock alerts in §Q1 carry `ComplianceVIPNotSet`, which does not
  exist on 9.x. The alert is installed, REST shows an
  empty symptom set in that slot, and the export writes the ref back out.
- `recon_log.md` (2026-06-23, devel) records a vCommunity alert installed by
  pak with its symptom 404 and the alert reported active. That recon did not
  establish which import path put it there.
- Vendor paks reference symptoms by id in `<SymptomSet ref>`, and the ids of
  product symptoms are stable across 8.18.7 to 9.1.1
  (`alertdef_symptomset_import.md`; §Q1). So an alert whose symptom the
  target's pak supplies refers to the right object by id (inferred).

Not known (unverified): what `POST /api/content/operations/import` does with
an `alertdefs.xml` alert whose referenced symptom is neither in the zip's
`symptomdefs.xml` nor on the target. Possible outcomes are that the alert is
imported with an empty set (as the product install does), that the alert is
skipped or failed in the `ALERT_DEFINITIONS` envelope, or that it is
imported with the ref kept. Also not known: whether it resolves a symptom
supplied by the target's pak (an `ALL` or `badge|*` symptom) the same way as
one supplied in the zip. No existing note covers content-zip import of alerts.
The factory installs alerts by REST (`src/vcfcf_alerts/client.py`), not by
content zip.

Smallest experiment (not run): on `devel` (9.0.2), one content zip holding
only the marker, `configuration.json` and an `alertdefs.xml` with two
factory-named alerts. A1 names `SymptomDefinition-EXP-DoesNotExist`. A2 names
`SymptomDefinition-vCenter Operations Adapter-HealthStateRed`, which is on
every target and never exported. Import with `force=true`. Read the
`ALERT_DEFINITIONS` imported/skipped/failed counts in the envelope, the
analytics log around `importAlertDefinitions`, `GET
/api/alertdefinitions/{id}` for both, and an `ALERT_DEFINITIONS` export.
Clean up with `DELETE /api/alertdefinitions/{id}` and check against a
pre-snapshot. Repeat on 8.18.7 if 9.0.2 drops A1.

## Q4. False-positive baseline (migrator `tree --json`, clean lab exports)

| Export | `alert -> symptom` missing edges (distinct ids, source alerts) | Cause | Other missing edges in that zip |
|---|---|---|---|
| 8.18.7 | 289 (52, 34) | all Q1-rule: 43 `CASAdapter-*` badge/capacity symptoms, 9 `ALL` badge symptoms | 1 symptom-to-super-metric (SMs not in this zip) |
| 9.0.2 | 22 (10, 10) | 18 Q1-rule (`Container-*` alerts to the 9 `ALL` badge symptoms), 4 dangling stock `ComplianceVIPNotSet` | 1 symptom-to-super-metric |
| 9.1.1 `devel_9_1` | 4 (1, 4) | 4 dangling stock `ComplianceVIPNotSet` | 1 symptom-to-super-metric |
| 9.1.1 `prod` | 4 (1, 4) | same | 1 symptom-to-super-metric; 3 rule-to-outbound-setting (outbound settings not in this zip) |

Every one is blocking in the tool. No edge in this table comes from
customer-authored content. The 4 on 9.1.1 agree with the "4 symptom refs" in
the companion note's §Q5.

## Q5. A rule the tool can apply offline, and what a live check adds

From the zip alone, the missing symptom is absent, so its condition key
cannot be read. What is available is the referenced id, the referencing
alert, and the knowledge in §Q1. Proposed rule, in order:

1. **Known never-exported id** (verified list): the referenced symptom or
   alert id is in the union set from §Q1 (117 symptoms, 16 alerts), or
   matches `SymptomDefinition-vCenter Operations Adapter-*`,
   `SymptomDefinition-VMWARE-vCenter Operations Adapter-*`,
   `AlertDefinition-vCenter Operations Adapter-*` (the `ALL` family), or
   `SymptomDefinition-CASAdapter-*` absent from the zip. Classify as
   "supplied by the product or a pak, never exported". Warn, do not block.
   The list is version-specific and should ship as data with the version it
   was measured on.
2. **Stock source alert**: the referencing alert's id is keyed
   (`AlertDefinition-<Kind>-<Name>`, not `AlertDefinition-<uuid>`) and it
   matches the pak naming of its adapter kind. Its symptoms come from the
   same pak as the alert. Default the alert out of bundles, as for
   pak-supplied dashboards, and treat its missing symptoms as inert. This
   also covers the dangling `ComplianceVIPNotSet`, which is already broken on
   the source. Keyed versus bare-uuid id is a heuristic, not a proof of
   authorship: `devel_9_1` has 28 bare-uuid alerts, all product content
   (APPOSUCP 15, VMSP 8, SupervisorAdapter 4, VMWARE 1), and vCommunity pak
   alerts use bare uuids too (verified ids; the authorship reading is
   inferred).
3. **Truly missing** (block, or warn loudly): a custom-looking alert
   (bare-uuid id) naming a missing symptom not covered by 1. The export
   cannot carry it if it is a custom symptom on a `badge|*`, `timeRemaining`
   or `capacityRemainingPercentage` key, or of adapter kind `ALL` (the §Q1
   `prod` case). The message is "the export does not carry this symptom
   type; read it from the source", not "export it as well". Re-exporting
   cannot fix it.

What a live check adds:

- **On the source:** `GET /api/symptomdefinitions/{id}` (public, supported)
  returns the left-out definitions with their condition, so the tool can
  confirm the family (adapter kind `ALL`, condition key) and, for a custom
  one, read it to re-create on the target. Whether a re-created badge or
  `timeRemaining` symptom can go through content-zip import, or only through
  `POST /api/symptomdefinitions`, is unverified.
- **On the target:** `GET /api/symptomdefinitions/{id}` and `GET
  /api/alertdefinitions/{id}` are authoritative per id for everything except
  alert-embedded conditions. They returned 200 for every `ALL`, `badge|*`
  and `timeRemaining` definition and 404 for a symptom that really is absent
  (`ComplianceVIPNotSet` on 9.x). The paged lists `?page=&pageSize=` are
  complete too: their `totalCount` matched and their union with the export
  covered every id. Unlike `getDashboardList` for dashboards, an id absent
  from the target's symptom or alert list is absent. The exception is
  alert-embedded conditions (`symptomDefType`). They are not on the symptom
  endpoints (404 by id) and appear as `alertConditions[].id =
  "Condition-<x>"` inside the alert. They travel with their alert in the
  zip, so the tool should never look them up on their own.
- REST is not a substitute for the export when reading the source's alerts.
  It hides dangling refs as empty sets (§Q1), and the export is the only read
  of what the alert actually stores.

## Method and artefacts

- Inventory and export: one Python script per profile using
  `vcfcf_common.client.VCFOpsClient` (`_request`) from the factory tree,
  running in the session scratchpad. The first run of the recommendations
  read looped on the unpaged endpoint and was de-duplicated by id (1317
  distinct on `prod`); the other three were re-read unpaged.
- Export took 10 s (`prod`) to about 2.5 min (`devel_9_1`) per instance for
  these four types.
- Comparison scripts parse the zips with `xml.etree` under `python3 -I`. The
  customer zip was only read as data (unzip of the four XML/JSON members to
  their own directory; the migrator walk run from an empty working
  directory).
- The `prod` `notificationrules.json` carries a webhook URL (a secret). The
  zip stays in the scratchpad and is not quoted here.

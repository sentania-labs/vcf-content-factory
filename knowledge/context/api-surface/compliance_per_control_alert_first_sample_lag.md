# Per-control compliance alerts: "not firing" was a two-cycle lag on new pushed keys

Investigated 2026-09-23, DEVEL (VCF Ops, compliance pak build 67), read-only
(GET only; nothing created, imported, enabled, or edited). All times
America/Chicago.

## Answer

Nothing is broken. The 144 per-control alerts do fire. The ops-recon snapshot
at 12:47 PM was taken in the ten-minute window before they could:

1. The profile-free key `VCF-CF Compliance|<control_id>|Compliant` is new in
   the v3 builds. Its **first** sample on DEVEL landed at about 11:46 AM, and
   a symptom on a brand-new pushed metric key does **not** trigger on the
   key's first sample.
2. The adapter pushes hourly (`monitoringInterval="60"`), so the **second**
   sample arrived at 12:47 PM, and the per-control symptoms went active at
   12:47:25 PM.
3. Alerts then followed on the next analytics pass, 12:49:20 to 12:52:41 PM.

At 12:53 PM DEVEL had **336 active per-control alerts on 96 objects across 26
distinct definitions**. On vcf-lab-wld02-esx01 all six controls with
Compliant = 0 had an active alert starting at 12:52:08 PM.

No change to describe.xml, the generator, or policy is needed.

## Evidence by question

### 1. Condition key vs pushed stat key: identical

Installed definition, `GET /api/symptomdefinitions/SymptomDefinition-vcfcf_compliance-vcfcf_compliance_ctl_esx_lockdown_mode_noncompliant`:

```json
"condition": {
  "type": "CONDITION_HT",
  "key": "VCF-CF Compliance|esx.lockdown-mode|Compliant",
  "operator": "EQ", "value": "0.0", "valueType": "NUMERIC",
  "instanced": false, "thresholdType": "STATIC"
}
```

`GET /api/resources/{esx01}/statkeys` (field `stat-key[].key`) contains
`'VCF-CF Compliance|esx.lockdown-mode|Compliant'` exactly: same prefix, dot
and hyphen kept in the control id, same case, `Compliant` suffix. The
esx.tls-ciphers definition matches `'VCF-CF Compliance|esx.tls-ciphers|Compliant'`
the same way. The source agrees: `ComplianceDecisions.complianceStats` pushes
`K + ctrl.scgId + "|Compliant"` and the generator emits the same string.

The host also still carries the retired profile-scoped keys
(`VCF-CF Compliance|VMware_SCG_9.0|...|Compliant`, `..._9.1|...`), last written
at 1:30 PM on 2026-09-10 and 11:21 AM today. No definition references them, so they are
inert history.

### 2. The symptom evaluates, and "=" on the dotted key works

`GET /api/symptoms?resourceId={esx01}&activeOnly=true` at 12:52 PM:

| Symptom | Active since | Message |
|---|---|---|
| ctl_esx_lockdown_mode_noncompliant (and the other five with Compliant = 0) | 12:47:25 PM | `HT equals 0 = 0` |
| collection_host_unreadable | 11:46:39 AM | `HT above 3 > 0` |
| score_warning / score_critical | 2:28 PM on 2026-08-27 | `HT below 64.28... < 95 / < 80` |

The operator encodes as `EQ`, value `"0.0"`, `NUMERIC`, `STATIC`. The working
collection symptoms encode as `GT` with the same types. describe.xml's
`operator="="` and `value="0"` normalize to `EQ` / `"0.0"` on install. The
coordinator's corpus hypotheses (the `0` vs `0.0` value, and a dot or hyphen in the
key's middle segment) are **refuted by live state**: those exact
definitions are active.

**Control experiment on "= 1"** (the `collection_host_failed` symptom,
condition `collection_failed EQ 1.0`): it is active on vcf-lab-wld01-esx02,
the only host with `collection_failed = 1`. It is absent on the nine hosts with 0.

### The first-sample lag (the actual cause), shown twice

Minute-level history (`GET /api/resources/{id}/stats?statKey=...&rollUpType=LATEST&intervalType=MINUTES&intervalQuantifier=1`):

| Host / key | Samples today | Symptom active since |
|---|---|---|
| wld02-esx01 `esx.lockdown-mode\|Compliant` (new key) | 11:46 = 0, 12:47 = 0 | 12:47:25 PM (2nd sample) |
| wld02-esx01 `unreadable_count` (key exists for weeks) | ...11:21 = 3, 11:46 = 3, 12:47 = 4 | 11:46:39 AM (1st post-install sample) |
| wld01-esx02 `collection_failed` (new key, build 65) | 11:46 = 1, 12:47 = 1 | 12:47:26 PM (2nd sample) |
| wld01-esx02 `unreadable_count` (existing key) | ...11:21 = 52, 11:46 = 48 | 11:46:39 AM |

The symptom definitions all come from one describe.xml and install together.
The unreadable symptom fired at 11:46 AM, so the definitions were
present for the 11:46 sample. The pattern holds on two keys and two hosts: a
condition on an existing key fires on the first eligible sample, and a condition
on a newly created key fires one sample later. This matches the analytics engine
registering a newly pushed stat key on its first sample and only
threshold-evaluating it after that. That internal mechanism is **inference**.
The observable behavior is **evidence**.

Symptom-to-alert lag: 11:46:39 AM to 11:51:21 AM (collection, esx01), and 12:47:25 PM to 12:52:08 PM
(per-control, esx01). That is about 4m45s, one analytics cycle.

So with a 60-minute adapter interval, **worst-case time from a fresh install
(or any newly introduced key) to a visible per-control alert is about one hour
plus one collection plus about 5 minutes**. For a key that already exists, it is
one collection plus about 5 minutes.

### 3. Policy enablement

The per-control alerts are demonstrably enabled in the policy in effect for
these hosts, because they fire (336 active). The collection and score alerts
also fire. No policy step is needed. The policy detail read was not
re-attempted: `GET /api/policies/{id}` returned 500 on both instances
before (compliance_enablement_markers.md, marker 6), and the firing alerts
answer the question directly.

### 4. Metric vs property, and condition type

`Compliant` is a **metric**. It appears in `/statkeys` and `/stats/latest` and
is pushed via `stitcher.pushStats`. `Actual` / `Expected` / `Description` /
`profile_name` are properties (`pushProperties`). The symptom's condition is
`type="metric"` in describe.xml and `CONDITION_HT` (metric hard threshold)
installed. These match.

## Implications

- **Code:** none. describe.xml, the generator, and the adapter are correct for
  the per-control path.
- **Verification protocol (installer, qa-tester, ops-recon):** after installing
  a build that **introduces a new pushed key**, or on a fresh install, "zero
  alerts" is not a finding until **two adapter collections plus about 5 minutes**
  have passed since the first push of that key. Check in this order:
  `stats` history has 2 or more samples, then `/api/symptoms?activeOnly=true`
  shows the symptom, then `/api/alerts` about 5 minutes later. If a symptom is
  active and no alert appears after one more analytics cycle, that is a real
  alert-side problem (policy or definition). Before that point, it is timing.
- A side observation, not investigated: esx01 `esx.tls-ciphers|Compliant`
  went from 0 at 11:46 AM to -1 (unreadable, not evaluated) at 12:47 PM, and
  `unreadable_count` went from 3 to 4. This is why tls-ciphers is not among esx01's
  alerts, and it is adapter read behavior, not an alert defect.

## How to confirm live

```
GET /api/alerts?resourceId=<host>&activeOnly=true
  -> AlertDefinition-vcfcf_compliance-vcfcf_compliance_ctl_* rows, one per
     control whose latest Compliant = 0
GET /api/symptoms?resourceId=<host>&activeOnly=true
  -> matching *_ctl_*_noncompliant rows, message "HT equals 0 = 0"
```

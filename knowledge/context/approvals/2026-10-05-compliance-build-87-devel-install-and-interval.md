# Scott's go: compliance build 87 on devel, and the three devel instances to a 5 minute interval

Date: 2026-10-05 (America/Chicago).

Asked, two decisions: (1) install `dist/vcfcf_sdk_compliance.0.0.0.87.pak`
(sha256 `c02671aecb4293b3c104a3262f734f592261dc63f962915b62684c9e7980d6cf`)
on devel, replacing build 85 and carrying build 86 (super metrics retired,
Overview tiles on ComplianceWorld, alert cancelCycle 3, all 143 alerts
prefixed "VCF Content Factory Compliance Alert:", esxcli hung-host fix,
docs parity); rollback is reinstalling 85. (2) Set the collection interval
on the three existing devel compliance adapter instances (mgmt, wld01,
wld02) from 60 to 5 minutes through the adapter API, because a pak upgrade
does not change an existing instance's stored interval (proven on the
build 85 upgrade, 2026-10-02).

Scott (verbatim):

> yes and yes

Earlier, on the interval (2026-10-05, verbatim): "A2> SO an upgrade won't
change the collection timer?" and, on the alert cancel cycles, "3> let's set
the alarm cycle cancel to 3"; on phase 3, "A1> OK".

Scope: devel only; this pak; the interval field on those three instances
only. Not a go for prod, a PR merge, a `v*` tag, or any devel host or
vCenter change (Scott said "4> I will change something" himself for the
drift proof). Install gate: `knowledge/context/reviews/compliance-build-87.md`
(APPROVE, 0 BLOCKING, 0 WARNING).

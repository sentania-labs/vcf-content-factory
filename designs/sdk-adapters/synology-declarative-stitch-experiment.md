# synology build 25 — declarative datastore stitch experiment (DEF-006)

## Initial prompt (verbatim, 2026-07-02 session)

> Let's scan a bunch of different paks and see how they do it.  Can we
> match it via naa id? then ask for the datastore name,?

(Following: "There's no reason to flip. The framework is the product" —
the prod CP instance stays as the standing DEF-006 repro; and "I'd
rather not start a PR until we have this solved because I presume it
will take tooling updates.")

## Vision

Test whether the platform's property-driven relationship mechanism —
proven live for Oracle (`relationships|VirtualMachine_parent =
oracledemo`, zero adapter API calls, running on our prod CP today) —
binds a `VMWARE::Datastore` from a **path-valued** property, so the
Synology stitch works from a Cloud Proxy with zero credentials.

- **Binding values are 100% NAS-derivable** (live-confirmed on prod
  2026-07-02, matching vendor bytecode exactly):
  - block: `VMFS:|naa.<lun-naa>|` (e.g. `VMFS:|naa.6001405d023e…|`)
  - NFS: `<nas-ip>/<export-path>` (e.g. `172.16.3.52/volume1/wld01`)
  - platform match key: the Datastore identifier `DataStrorePath`
    (sic — platform's own misspelling), identType=2.
- **Experiment (build 25):** clone the vendor descriptor construct
  (TraversalSpecKind ResourcePath `…::child||VMWARE::Datastore::~child`
  + `Datastore_parent` isProperty placeholder — grammar quoted in
  `context/api-maps/tvs-declarative-stitching.md`) into synology's
  describe.xml, and have the adapter report
  `relationships|Datastore_parent = <path value>` on each LUN/NFS
  resource, built purely from Synology API data.
- **Isolation:** the runtime credentialed stitcher stays as-is; on the
  prod CP it is dead (DEF-006, 401 every cycle), so any new edge on
  that box is attributable only to the property mechanism.
- **Test ladder:** devel install (regression + property visible) →
  prod CP (the decisive zero-credential binding test). Edge appears on
  CP → DEF-006 closes; then `tooling` codifies the mechanism into the
  framework (RelationshipBuilder property emission + descriptor
  support) so every pak inherits it, and ONE PR ships the whole story.
- **Open uncertainty the experiment resolves:** the correlation engine
  has only ever been observed binding a *name* value (Oracle). Whether
  it binds `DataStrorePath`-valued properties is exactly what build 25
  determines. Negative result = documented dead end; fall back to the
  CaSA node-cert path (cleanroom spec pending).

## Evidence base

- `context/api-maps/tvs-declarative-stitching.md` — descriptor grammar,
  quoted from 12+ storage paks.
- `context/api-maps/tvs-datastore-binding-value.md` — binding values
  from vendor bytecode; platform matches `DataStrorePath`.
- `context/investigations/recon_log.md` (2026-07-01/02) + live prod
  reads — Oracle property mechanism + live `DataStrorePath` forms.
- DEF-006 in `context/defects.md` — the gap this closes.

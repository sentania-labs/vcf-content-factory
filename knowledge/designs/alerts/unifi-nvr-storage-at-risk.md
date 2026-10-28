# Design: UniFi NVR Storage At Risk (alert)

## Initial prompt

Scott, 2026-10-28, after I reported the devel Protect NVR's primary volume shows `health: "atrisk"` with an `io_err` on slot 0: "The protect disk being full just means it's at its retention max - so \"normal\"" ... "Regarding it being at risk. You build the alerts not monitor them :)"

## Vision

- Ships in the UniFi SDK pak (`content/sdk-adapters/unifi/`), build 19.
- Target: adapterKind `unifi_controller`, resourceKind `UniFiNvr` (and per-drive detail if Protect exposes it per disk).
- Publish Protect's own storage health from the bootstrap NVR record (the fields build 18's NVR storage capture found: volume `health`, per-drive state / `io_err`), present-only, values as Protect sends them.
- Alert when Protect reports the volume or a drive as not healthy (e.g. `atrisk`, degraded, failed, io errors), severity from Protect's own level. Do NOT alert on usage percent: Protect fills to its retention limit by design, so ~99% full is normal.
- Recommendation: check the drive in Protect's storage page, replace the drive in the named slot; single-drive volumes lose recordings on failure.
- The devel NVR currently reports `atrisk` with `io_err` on slot 0, so the alert is expected to fire there: that is the proof.

## Revision after review (2026-10-28, knowledge/context/reviews/unifi-build-19.md)

Resolved from the corpus (Scott's rule "alert on Protect's own verdict", OEM practice of mirroring the vendor's own health judgement, same as Synology's `storage_status` from DSM Storage Manager):
- Publish one `Storage|volume_display_health`: the health Protect's storage page actually displays, computed with the console UI's own rule (including the `lacking_disk:atrisk` exception only when `/api/system` `raid` shows `had_most < expected` or no raid block; when `raid` cannot be read, do not apply the exception).
- Symptoms on that: Failed (CRITICAL), At Risk (WARNING), and an unrecognised value (WARNING, NOT_REGEX of the known set).
- Drive Failed / Drive Not Healthy stay (Protect's drive states; spare-with-reason counts as at risk).
- Dropped from the alert: the pak's own bad-sector threshold (Protect's `too_many_bad_sectors` reason already feeds Drive Not Healthy), the raw I/O-errors regex and the always-on "issue other than missing drive" helper. Raw values stay published as properties for context.

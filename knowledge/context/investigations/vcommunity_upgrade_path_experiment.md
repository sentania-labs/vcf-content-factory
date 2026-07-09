# vCommunity upgrade-path experiment: classic Java pak over containerized pak

**Date:** 2026-06-10
**Instance:** devel (`vcf-lab-operations-devel`, VCF Ops 9.0.2) — RULE-009, devel only
**Investigator:** api-explorer
**Question (one sentence):** Can a classic Java SDK adapter pak perform an
in-place UPGRADE of an installed containerized (Python Integration SDK) pak
that shares the same pak name and adapter kind?

**VERDICT: NOT VIABLE** as a same-identity in-place upgrade. The install is
*accepted* (no rejection, no signature complaint, version bumps), but the
platform does NOT re-register the adapter kind — it stays `DOCKERIZED` with the
old describe.xml, the shipped Java JAR is never wired in, and no instance can
run on a non-container collector. The result is a silent split-brain that is
worse than an honest rejection. **Take the side-by-side fork** (distinct
adapter kind key) for the Tier 2 vCommunity rewrite.

---

## 1. Containerized vs classic pak structural comparison (deliverable)

Original: `iSDK_VCFOperationsvCommunity` 0.2.8, from
`vmbro/VCF-Operations-vCommunity` GitHub Release v0.2.8 (asset
`VCFOperationsvCommunity_0.2.8.pak`, 464 KB — asset present, no source build
needed). Adapter kind `VCFOperationsvCommunity`.

| Aspect | Containerized (Python Integration SDK) | Classic (Java SDK, factory build) |
|---|---|---|
| Inner adapter archive | `adapter.zip` | `adapters.zip` |
| Adapter payload | **`<kind>.conf`** marker file only | **`<kind>.jar`** + `lib/vcfcf-adapter-base.jar` |
| `<kind>.conf` contents | `KINDKEY`, `API_VERSION`, `API_PROTOCOL`, `API_PORT`, **`REGISTRY=ghcr.io`**, **`REPOSITORY=/vmbro/vcf-operations-vcommunity`**, **`DIGEST=sha256:…`** | (no `.conf` at all) |
| Code execution | OCI image pulled + run by a **Cloud Proxy** container runtime | Java runs **in-collector** on the analytics node |
| `commands.cfg` / `Dockerfile` | present in source tree (not in pak) — `python app/adapter.py <method>` | none |
| `<kind>/conf/describe.xml` | **yes** (identical schema) | **yes** (identical schema) |
| `<kind>/conf/version.txt`, images, resources | yes | yes |
| Outer `manifest.txt` `adapters` | `["adapter.zip"]` | `["adapters.zip"]` |
| Outer `manifest.txt` `adapter_kinds` | `["VCFOperationsvCommunity"]` | `["VCFOperationsvCommunity"]` |

**The `.conf` file is the container marker.** A containerized adapter ships
*no code* in the pak — only the OCI image coordinates (registry / repository /
digest) the Cloud Proxy pulls at runtime. A classic adapter ships the JAR and
runs in the collector. Both carry the *same* `describe.xml` schema and the same
`<AdapterKind key>` + `<ResourceIdentifier key>` set, which is what made
same-identity upgrade *look* plausible on paper.

### How the platform records the distinction

The Suite API exposes the discriminator on the registered adapter kind:

```
GET /api/adapterkinds/VCFOperationsvCommunity
  → {"adapterKindType":"DOCKERIZED", …}
```

Enumerated across all 21 installed kinds on devel:

- `DOCKERIZED` — `VCFOperationsvCommunity` (the containerized original)
- `OPENAPI`   — `vRealizeOpsMgrAPI`
- `GENERAL`   — **everything else**, including every classic Java SDK adapter
  (`vcfcf_compliance`, `synology_diskstation`, `unifi_controller`) and all
  MPB-built and built-in adapters.

So a true classic-over-container upgrade would have to flip the registered
`adapterKindType` from `DOCKERIZED` → `GENERAL` in place. It does not.

---

## 2. Install original containerized pak (baseline)

`python3 -m vcfops_managementpacks install VCFOperationsvCommunity_0.2.8.pak --profile devel`

Outcome: clean install. Upload pakId `iSDKVCFOperationsvCommunity-028`, server
name "VCF Operations vCommunity" 0.2.8. `isPakInstalling` flipped False after
~110s; post-install verify: `adapterKind='VCFOperationsvCommunity'
isInstalled=true`. Registered as `adapterKindType: DOCKERIZED` with resource
kinds `Cluster Compute Resource`, `Host System`,
`VCFOperationsvCommunity_adapter_instance`, `Virtual Machine`.

---

## 3. Adapter-instance creation on devel — BLOCKED (no Cloud Proxy)

devel has only the built-in local collector (`id=1`, "VCF Operations
Collector…Cluster Node"); no Cloud Proxy with a container runtime.

```
POST /api/adapters  (adapterKindKey=VCFOperationsvCommunity, collectorId=1)
  → 500 {"errorMessage":"Failed to create adapter instance.
         Collector is not compatible with adapter type."}
```

Earlier attempts (credential-by-id, then inline credential) returned 400
`Credential Id … Allowed values are = "[]"` and the same 500. **No adapter
instance object can exist on devel for the DOCKERIZED kind.** Instance-survival
across the upgrade is therefore only *partially* answerable — see §5: it is
moot, because the upgrade never produces a runnable classic kind anyway.

> Side effect noted: inline-credential POSTs that hit the 500 still *created*
> the credential record (orphaned). All such records were deleted in cleanup.

---

## 4. Build minimal same-identity classic Java pak — TOOLSET GAP found

Route: `scaffold-sdk` → rewrite to the vCommunity identity (pak name
`iSDK_VCFOperationsvCommunity`, kind `VCFOperationsvCommunity`, v1.0.0). The
adapter-instance `ResourceKind` key and all `ResourceIdentifier` keys
(`host`, `port`, `esxi_*_config_file`, `vm_*_config_file`, `win_*_config_file`,
`serviceMonitoring`, `winEventMonitoring`) plus the `vsphere_user` credential
kind (`user`/`password`/`winUser`/`winPass`) were mirrored from the original's
describe.xml so instance-config compatibility was genuinely on the table.
Stub `test()`/`collect()`. Keyed constructors `super(ADAPTER_KIND)` /
`super(ADAPTER_KIND, dir, id)` per `knowledge/lessons/controller-describe-bare-instantiation.md`.

**TOOLSET GAP — factory rejects mixed-case adapter kind keys.**
`vcfops_managementpacks/sdk_project.py:137` enforces
`re.fullmatch(r"[a-z][a-z0-9_]*", adapter_kind)`. Both `validate-sdk` and
`build-sdk` hard-fail on `VCFOperationsvCommunity`:

```
adapter_kind must be lowercase alphanumeric + underscore, starting with a
letter; got 'VCFOperationsvCommunity'
```

But VCF Ops itself accepts and registers mixed-case kinds (the live original
proves it). **The factory pipeline cannot build a pak whose adapter kind key
matches the containerized original.** A same-identity classic rewrite is
un-buildable through `build-sdk` as the tool stands. (Did not edit
`vcfops_*/` — that is the `tooling` agent's domain.)

Workaround for the experiment: built once with a lowercase placeholder kind
(`vcfoperationsvcommunity_probe`) to obtain the classic pak layout and a
compiled v2 adapter, then **manually recompiled** the adapter class with the
real `VCFOperationsvCommunity` constant (`javac` against
`adapter_runtime/vrops-adapters-sdk-2.2.jar` + `vcfcf-adapter-base.jar`) and
hand-assembled the pak: renamed the `<kind>/` directory, fixed the
`<AdapterKind key>` in describe.xml, rewrote both manifests to the vCommunity
identity, and re-zipped `adapters.zip` with explicit directory entries (per the
silent-fail note in `installer.py` `_verify_adapter_registered`). Result:
`iSDK_VCFOperationsvCommunity_classic_1.0.0.pak` — name
`iSDK_VCFOperationsvCommunity`, version 1.0.0, kind `VCFOperationsvCommunity`,
classic Java (JAR + lib, no `.conf`).

---

## 5. Upgrade install of classic pak over the installed container — the result

`install iSDK_VCFOperationsvCommunity_classic_1.0.0.pak --profile devel`

**Accepted, no rejection, no signature complaint:**

```
Upload accepted: pakId='iSDKVCFOperationsvCommunity-100'
Server name: 'iSDK_VCFOperationsvCommunity'  version: '1.0.0'
… isPakInstalling flipped False after ~70s …
OK: Install completed and verified: iSDK_VCFOperationsvCommunity 1.0.0
   (adapterKind='VCFOperationsvCommunity' isInstalled=true)
```

The pak namespace recognised it as the *same* pak (compressed pakId
`iSDKVCFOperationsvCommunity-…`, suffix `028` → `100`) and processed it as a
version update. Signature checking is bypassed (`ignoreSignatureChecking=true`)
— no signing barrier surfaced.

**But the registration did NOT convert. Split-brain state:**

| Check (post-upgrade) | Result | Interpretation |
|---|---|---|
| `GET /api/adapterkinds/VCFOperationsvCommunity` → `adapterKindType` | **`DOCKERIZED`** (unchanged) | Kind never re-registered as classic |
| Resource kinds | `Cluster Compute Resource`, `Host System`, `Virtual Machine`, `…_adapter_instance` (**the original's**) | New describe.xml (`VcommProbeWorld`) **NOT applied** |
| `GET /api/solutions` → `version` | **`1.0.0`** (bumped) | Pak/manifest shell *was* replaced |
| `getIntegrations` icon / version | classic factory icon, `1.0.0` | Outer-shell metadata updated |
| `getIntegrations` description / vendor | **still the original's** "bring your own content…", vendor "Onur Yuzseven, Broadcom" | describe/registration layer untouched |
| `POST /api/adapters` on local collector | **500 "Collector is not compatible with adapter type"** | Kind is STILL container-typed; classic JAR is dead weight |

**The platform updated the pak version and outer manifest but kept the live
adapter-kind registration (type=DOCKERIZED + original describe.xml).** The
shipped Java JAR is on disk but never wired in; the collector would still try
to launch a container, not the JAR. Because the kind stays `DOCKERIZED`, the
non-container collector still refuses instance creation — exactly as before the
"upgrade." Instance-survival is moot: there can be no running classic instance.

This is strictly worse than an honest rejection: an operator sees "upgrade
succeeded, version 1.0.0" while the adapter is silently still the old container
adapter (and, on a real Cloud-Proxy instance, the digest the old `.conf`
pointed at — the new code is never executed).

---

## 6. Cleanup

`uninstall iSDK_VCFOperationsvCommunity --profile devel` → completed cleanly
(`isUnremovable=False`, no built-in guard tripped). Post-uninstall:

- `GET /api/adapterkinds/VCFOperationsvCommunity` → **404** (deregistered)
- `GET /api/solutions` → no vCommunity entry
- adapter instances → 0
- credentials with real `adapterKindKey=VCFOperationsvCommunity` → **0**
- experiment-named credentials (`vcomm*`, `*upgrade-test`, `*inline*`,
  `*pu-cred`) → **0**

**Clean-up verified: yes.** devel left with no vCommunity solution, adapter
kind, instance, or experiment credential.

### Bonus findings on cleanup

1. **`?adapterKindKey=` on `/api/credentials` is a leaky filter.** Querying
   `GET /api/credentials?adapterKindKey=VCFOperationsvCommunity` *after* the
   kind was deregistered returned 6 credentials that actually belong to OTHER
   kinds (`VMWARE`, `vcfcf_compliance` ×2, `synology_diskstation`,
   `unifi_controller`) — pre-existing devel creds sharing a credential-field
   shape. They correctly 409 on delete (in use by their real adapters) and were
   left untouched. When auditing "did my pak's credentials get cleaned," verify
   each candidate's *real* `adapterKindKey` via the unfiltered list — do not
   trust the filtered query and do not bulk-delete its results.
2. **Credential cascade-on-uninstall is not the whole story.**
   `knowledge/lessons/pak-uninstall-cascades-credentials.md` documents creds *cascading
   away* on uninstall; here the vCommunity-scoped creds I created were gone
   (cascade + my own deletes), but the leaky-filter behavior above means a naive
   "remaining creds" count can read non-zero from unrelated kinds. No
   data-loss occurred to other adapters' creds.

---

## Implications for the vCommunity Tier 2 design

(`knowledge/designs/managementpacks/vcommunity.md` — which already scopes upgrade
compatibility as **NOT** a requirement; this experiment confirms that was the
right call and closes the "would-be-cool upgrade pak" door empirically.)

1. **Do not attempt a same-identity upgrade pak.** A classic pak with kind
   `VCFOperationsvCommunity` installs as a version bump but never converts the
   DOCKERIZED registration — the Java code never runs. There is no in-place
   container→classic migration path on VCF Ops 9.0.2 via the pak install flow.
2. **Use a distinct adapter kind key** for the Tier 2 rewrite (the design's
   open question "must NOT collide with the original" is now a hard
   requirement, not a nicety). Side-by-side install is the only viable shape;
   the two adapters coexist as separate kinds.
3. **Migration story for existing users** is uninstall-old + install-new +
   recreate instances/credentials, NOT an upgrade. Key-namespace continuity
   (`vCommunity|` property/metric keys) still gives ported content mechanical
   continuity, but it is not an upgrade contract.
4. **Factory toolset gap to route to `tooling`:** `sdk_project.py` rejects
   mixed-case adapter kind keys (`[a-z][a-z0-9_]*`). VCF Ops accepts mixed
   case. This only matters if a future build must match an external mixed-case
   kind; the vCommunity Tier 2 rewrite should pick a fresh lowercase kind
   anyway (e.g. `vcfcf_vcommunity`), so it is **not a blocker for this design**
   — but worth a validator note so the next person who needs an exact-match
   kind isn't surprised.

## Open / follow-up questions

- On a real Cloud-Proxy instance (where the DOCKERIZED kind *can* run), does
  the same split-brain upgrade leave the OLD image digest active, or does the
  version bump confuse the proxy's image pull? Could not test on devel (no
  Cloud Proxy). Likely irrelevant given the side-by-side decision, but it is
  the one piece of platform behavior this experiment could not reach.
- Does VCF Ops offer any *supported* container→classic migration affordance
  (e.g. a different install action than `mainAction=install`)? Not surfaced in
  this experiment; not pursued since the design doesn't need it.

## Artifacts (all in `/tmp`, removed after the experiment)

- `/tmp/vcomm_exp/VCFOperationsvCommunity_0.2.8.pak` — original (GitHub)
- `/tmp/vcomm_exp/sdk/vcomm_upgrade_probe/` — stub adapter project
- `/tmp/vcomm_exp/dist/iSDK_VCFOperationsvCommunity_classic_1.0.0.pak` —
  hand-retargeted same-identity classic pak

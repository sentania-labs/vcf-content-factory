# MP signing chain — characterization (2026-05-16)

**Question asked**: "MP signing. What is the chain of that?"

**Short answer**: It's broken in multiple, instructive ways. There IS a signing chain, but it's a single self-signed VMware root, signed with cryptographically deprecated primitives, **and the cert expired on 2026-01-03** — yet paks dated 2025-12-30 are being signed with it and presumably accepted by appliances 4+ months past expiry.

## Pak structure on disk

Every signed `.pak` (which is just a zip) has at the OUTER zip top level:

```
signature.cert       — ~1908 bytes; hybrid file (see below)
signature.mf         — variable; SHA-1 manifest of all OTHER top-level files
<other top-level pak files>
```

## `signature.mf` — file hash manifest

Plain text, one line per file:

```
SHA1(adapters.zip)= ad3e3f40735afacc09a0e12f8ac0ff7427631038
SHA1(dell16.png)= d87872c508e63ccd7c6ea7f11ec3da7c23742cfc
SHA1(eula.txt)= 2124feddda13ac9322b9e758bf0537efb3e1e8fd
SHA1(manifest.txt)= f53a91b2eeba1ef1653414e81285057936b803aa
...
```

**SHA-1** for every file hash. SHA-1 has been considered cryptographically broken since 2017 (SHAttered collision). Modern code-signing has used SHA-256 minimum for 10+ years.

The hashes cover only the OUTER pak's top-level files. The inner archive (`adapters.zip`, `<adapter>.zip`, etc.) is hashed as a single opaque blob. Files INSIDE the inner archive are not individually signed — integrity is transitive through the inner-zip checksum.

## `signature.cert` — hybrid signature + cert container

The format is NON-STANDARD. It's NOT a plain X.509 cert and NOT a PKCS#7. It's:

```
SHA1(signature.mf)= <hex-encoded RSA signature of signature.mf, ~512 bytes for 2048-bit key>
-----BEGIN CERTIFICATE-----
<base64 PEM of the X.509 cert>
-----END CERTIFICATE-----
```

The first line is the actual **RSA signature** (raw, not PKCS#7-wrapped) of `signature.mf`'s bytes, using the cert's private key. The PEM block is the cert that contains the verifier's public key.

This is a homemade signature format — not Authenticode, not Java jarsigner, not PKCS#7 / CMS. The verifier must:
1. Parse the first line as a hex RSA signature
2. Parse the PEM block as the X.509 cert
3. Use the cert's public key to verify the signature against `signature.mf`'s bytes
4. Compute SHA-1 of every other top-level file and check against the manifest
5. (Optionally) verify the cert chain — but there's no chain to verify (self-signed)

## The cert itself — one cert for the entire ecosystem

```
Subject:    C=US, ST=California, L=Palo Alto, O="VMware, Inc."
Issuer:     C=US, ST=California, L=Palo Alto, O="VMware, Inc."
                                                  ^^^^^^^^^^^^
                                                  SELF-SIGNED
Validity:   Not Before: Feb 26 22:17:41 2010 GMT
            Not After:  Jan  3 22:17:41 2026 GMT   ← EXPIRED ~4 MONTHS AGO
                                                     (today: 2026-05-16)
Serial:     a1:fb:c4:bb:70:32:a4:99
SHA1 FP:    53:D8:32:35:CE:BC:C5:5D:70:AD:D0:3A:3E:46:2A:F3:B2:D9:6F:2F

Public Key: RSA 2048-bit
            Modulus: ...
            Exponent: 3                  ← SMALL EXPONENT (Bleichenbacher-vulnerable
                                            without strict PKCS#1 v1.5 padding)
Signature Algorithm: sha1WithRSAEncryption  ← DEPRECATED (SHA-1)
```

**One cert, ecosystem-wide.** Verified identical SHA-1 fingerprint across:
- Broadcom-internal devel paks (`AppOSUCPAdapter-902025137916.pak`, dated 2025-12-30)
- Broadcom-internal devel paks (`vim-902025137884.pak`, dated 2025-12-30)
- Third-party marketplace pak (`DellStorageAdapter-01.04.0301_signed.pak`, signature dated 2023-09-07)

**Implications**:
- The marketplace **re-signs vendor paks at upload** with VMware's private key. Vendors don't bring their own signing identity into the pak.
- Compromise of the single VMware private key compromises the entire signing ecosystem retroactively — every pak ever signed.
- The cert was issued in 2010 for ~16-year validity. It expired on 2026-01-03.
- Paks dated **2025-12-30** are signed with this cert — Broadcom's signing infrastructure didn't roll the cert before expiry.

## Community paks: unsigned

Track B / community paks ship with a **zero-byte `signature.cert`**.

```
$ unzip -p VCFOperationsvCommunity_0.2.8.pak signature.cert | wc -c
0
```

The vCommunity pak was downloaded from a community GitHub release (not the marketplace), and it ships as if it were going to be signed but with an empty cert. The appliance must accept this — either by skipping signature validation when the cert is empty, by treating empty-cert paks as "unsigned community" (lower trust level), or via an admin toggle.

Some appliance install paths reportedly accept unsigned paks behind an admin flag; the pak format itself reserves the slot.

## What enforces the signature?

**Not the install hooks.** The pak ships `validate.py` / `preAdapters.py` / `postAdapters.py` that the platform invokes during install:

```python
# Dell's validate.py — entire content:
print('Entering validate a simple Pak file')
print('Entering check if VCOPS_BASE is set')
try:
   os.environ['VCOPS_BASE']
except KeyError as e:
   exitValidateScript('Failed-VCOPS_BASE check failed', 1)
print('VCOPS_BASE check passed')
sys.exit()
```

No signature check. The hooks just confirm the install context exists.

**Validation is appliance-side**, in the install service that consumes the pak before unpacking it onto disk. That service is NOT in the corpus we decompiled — the SDK + adapter jars we have are the runtime side. The install service is part of the appliance's `vcops-suite-api` / `vcops-platform` services. (Future investigation: find the appliance install package.)

The presence of `vrops-trustmanager-3.0-SNAPSHOT.jar` in `common-lib/` is a SEPARATE concern — that's the SSL trust manager for outbound HTTPS connections, with a `NoopTrustManager` (literally accepts everything) variant and an `NdcTrustManager` (network-deployed-cert). The MPB runtime also bundles a `com.bluemedora.vropscertificatechecker.LaxTrustManager` — "lax" being the cryptographer's red flag.

## Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                     .pak (outer zip)                             │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  signature.cert    ── SHA1(signature.mf)=<rsa-sig>               │
│                       -----BEGIN CERTIFICATE-----                │
│                         (VMware self-signed, expired 2026-01-03) │
│                       -----END CERTIFICATE-----                  │
│                                                                  │
│  signature.mf      ── SHA1(adapter.zip)=<hash>                   │
│                       SHA1(manifest.txt)=<hash>                  │
│                       SHA1(eula.txt)=<hash>                      │
│                       ...                                        │
│                                                                  │
│  adapters.zip      ── (inner archive — NOT individually signed;  │
│                        protected only by the outer SHA-1 hash)   │
│  manifest.txt                                                    │
│  eula.txt                                                        │
│  validate.py       ── (does NOT validate the signature)          │
│  preAdapters.py                                                  │
│  postAdapters.py                                                 │
└──────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼ upload to appliance
              ┌────────────────────────────────────────┐
              │ Appliance install service              │
              │  (not in our decompiled corpus)        │
              │  Presumably:                           │
              │  1. Parse signature.cert (split        │
              │     hex-line from PEM block)           │
              │  2. RSA-verify hex-line over           │
              │     signature.mf using cert pubkey     │
              │  3. SHA-1-verify each top-level file   │
              │     against signature.mf entries       │
              │  4. (?) Verify cert validity dates →   │
              │     currently failing if enforced,     │
              │     since cert expired 2026-01-03      │
              │  5. (?) Pin cert by fingerprint        │
              │     against a hardcoded VMware root    │
              └────────────────────────────────────────┘
```

## Why this matters for VCF-CF

If VCF-CF generates paks that will be installed on customer appliances:

1. **VCF-CF will need access to VMware's signing private key**, OR the marketplace upload path needs to accept VCF-generated paks for re-signing. The former is unlikely (private key in customer-side software is a non-starter); the latter is realistic if VCF-CF is a Broadcom internal tool that submits to the marketplace pipeline.

2. **For internal deployments** (customer signs their own paks for their own appliances), the appliance must have an admin override to trust customer-provided certs. Confirm this exists before designing.

3. **For the unsigned path** (community style with zero-byte cert), confirm the appliance accepts unsigned paks and under what conditions (admin flag? all-or-nothing?). This is the path-of-least-resistance for an internal VCF-CF MVP.

4. **The signing format is homegrown** — VCF-CF can implement it trivially (no need for jarsigner or Authenticode tooling). Effectively:
   ```bash
   # compute the manifest
   for f in <top-level files except signature.*>; do
       echo "SHA1($f)= $(sha1sum $f | awk '{print $1}')" >> signature.mf
   done
   # sign with VMware's key (or your own)
   echo "SHA1(signature.mf)= $(openssl dgst -sha1 -sign <key> signature.mf | xxd -p | tr -d '\n')" > signature.cert
   echo "-----BEGIN CERTIFICATE-----" >> signature.cert
   base64 <cert.der> >> signature.cert
   echo "-----END CERTIFICATE-----" >> signature.cert
   # bundle
   zip <name>.pak signature.cert signature.mf <other files>
   ```

5. **The current scheme has multiple cryptographic weaknesses Broadcom should fix** (SHA-256 hashes, RSA-PSS or ECDSA signatures, per-vendor signing identity, automated cert rotation) — but VCF-CF is a consumer of the existing format, not its custodian. If Broadcom modernizes the format, VCF-CF will need to follow.

## Open follow-ups

1. **Find the appliance install service** and verify (a) whether cert-validity is enforced and (b) whether zero-byte-cert paks have a defined acceptance policy. — **ANSWERED in Pass 23**, see below.
2. **Confirm marketplace re-signing**: download a vendor pak from the marketplace AND that same vendor's GitHub releases page; compare the cert. If marketplace download is VMware-signed and GitHub release is vendor-signed (or unsigned), re-signing is confirmed.
3. **Check whether the platform has a signing-cert refresh mechanism** — given the cert is now expired, either Broadcom has issued a successor (and pak signers are using a different file we haven't seen) or the appliance has switched to fingerprint-pinning mode that ignores validity dates. Either way, VCF-CF needs to know. — **Partially answered in Pass 23**: enforcement is currently "skip dates", so the cert continues to function without rotation.
4. **Investigate VCF Operations 9.x changes** — the corpus is from VCF Operations 9.0/9.1 timeframe; future versions may have moved to a modern scheme (Sigstore, SLSA, etc.).

---

## 2026-05-16 — Pass 23 update: empirical appliance behavior

Field-confirmed against `vcf-lab-operations-devel` (VCF Operations
9.0.2.0.25137838) via Navani's cross-workspace data pull (bundle at
`workspaces/lab-admin/exports/vcf-mp-cleanroom-2026-05-16/sig-logs/`).
Three findings updating the questions above:

1. **Cert-validity is NOT enforced.** Paks built 2025-12-30 (signed
   with this expired cert), uploaded April 2026, come back
   `signed:true, signatureValid:true, certificateUntrusted:false`.
   The appliance trusts the cert. Behavior is "skip dates" — either
   `notBefore`/`notAfter` are explicitly bypassed, or the appliance
   pins by SHA-1 fingerprint against a hardcoded VMware root and
   never consults the cert's own validity window.
2. **Unsigned paks (zero-byte signature.cert OR missing signature
   files entirely) are accepted and installed in full.** 42 distinct
   unsigned-install records across the devel log corpus, including
   GitLab-1001, Rubrik-11025, SynologyDSM-1001, SynologyNAS-1001,
   VCFContentFactoryUniFiIntegration-1005, and 4
   VCFContentFactoryvSphereStoragePaths-200x paks. Each shows a
   complete STAGE → CLEANUP cycle in
   `casa_pak_history_<pakID>.json`. The `invalid_reason` field is
   recorded ("The PAK file ... is not signed") but **not enforced as
   a gate**. No admin flag required.
3. **Signature checking is opt-in at the API layer.** The
   `findPakInformation`/`getPakInformation` calls take an optional
   `checkSignature` parameter; the common case is
   `checkSignature=null` (the UI doesn't ask for signature info).
   When a check IS requested, results populate the `uploadLocal`
   JSON record but never gate the install path.

**The authoritative writeup of the appliance install + signing
behavior now lives in [`spec/16-platform-install-and-signing.md`](../spec/16-platform-install-and-signing.md).**
This file (pak-signing-chain.md) remains the authoritative reference
for the **on-disk cryptographic format** of the signature files;
spec/16 is the authoritative reference for **what the appliance does
with them**.

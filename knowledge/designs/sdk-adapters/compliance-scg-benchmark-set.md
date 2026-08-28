# Compliance adapter: SCG-only benchmark set (8.0, 9.0, 9.1)

## Initial prompt

Verbatim from the owner, 2026-08-25:

> okay for now: we are only going to ship SCG 8.0 SCG 9.0 and SCG 9.1 -
> hopefully this simiplyfies things.  I mean we have SCG 8 archived, and
> 9.0 and 9.1 available from an upsream source.

Context: he had just reviewed
https://github.com/vmware/vcf-security-and-compliance-guidelines and
confirmed the VCF 9.1 Security Configuration & Hardening Guide is now
published (cloud-foundation/9.1, VERSION 910-20260612-01) with a full
controls CSV. Our reference clone already carries it and the 9.1
controls CSV has no upstream changes since.

## Vision

The compliance adapter ships exactly three benchmarks, all from the
one vendor source (vmware/vcf-security-and-compliance-guidelines):

- **SCG 8.0**: keep as-is. Source: vsphere/8.0 controls CSV (the
  8.x-generation guidance lives under the vsphere tree upstream; there
  is no cloud-foundation/8.x).
- **SCG 9.0**: keep as-is. Source: cloud-foundation/9.0 controls CSV.
- **SCG 9.1**: NEW. Source: cloud-foundation/9.1
  vcf-security-configuration-guide-91-controls.csv from the reference
  clone, following the same canonical-profile pipeline the existing
  SCG profiles use (CANONICAL_SCHEMA.md in the adapter repo).
- **CIS vSphere 8**: REMOVED. "Only ... SCG 8.0 SCG 9.0 and SCG 9.1"
  is the owner's explicit scope; dropping CIS is part of the
  simplification, authorized by the verbatim quote above.

Unchanged: adapter Java, scoring rules (unreadable-is-not-compliant),
identity/stitching. This is a benchmark-profile change, not an engine
change, unless the loader turns out to hard-code the benchmark list.

#!/usr/bin/env python3
"""
VKS Marker Recon — identify property markers usable to classify VKS-related
VMs in a VCF 5.2 / vSphere 8 / Aria Operations 8 / VKS 8 environment.

Goal: figure out which `summary|config|productName`, `summary|config|type`,
name patterns, or other properties an Ops super metric `where:` clause
should use to identify VKS supervisor / control plane / worker / pod-VM /
vCLS / regular workload VMs in VCF 8, so the existing
`[VCF Content Factory] VKS Core Consumption` SMs (built for VCF 9) can be
extended to support both versions.

Usage:
    export VCFOPS_HOST=aria-ops-8.example.com
    export VCFOPS_USER=admin
    export VCFOPS_PASSWORD='...'
    # optional, defaults to "Local":
    export VCFOPS_AUTH_SOURCE='Local'
    # optional, set to "false" to skip TLS verification:
    export VCFOPS_VERIFY_SSL=true

    python3 scripts/vks_marker_recon.py

Read-only. No mutations. No content created. Uses suite-api endpoints
that are stable across Aria Ops 8.x and VCF Operations 9.x.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter, defaultdict
from typing import Any

import requests
import urllib3

# Properties most likely to discriminate VM type. The VKS 9 SMs already
# use summary|config|productName and summary|config|type; we want to
# learn which values appear in a VKS 8 environment.
INTERESTING_PROPS = [
    "summary|config|productName",
    "summary|config|type",
    "summary|managedObjectName",
    "config|guestFullName",
    "config|guestId",
    "summary|config|managedBy|extension",
    "summary|config|managedBy|type",
    "summary|config|annotation",
]

# Known name fragments worth bucketing — these are the patterns the VKS 9
# SMs and historical TKGS deployments use. Hits indicate a candidate
# name-based marker.
NAME_PATTERNS = {
    "supervisor_cp_old":      r"^SupervisorControlPlaneVM\s*\(",
    "supervisor_cp_new":      r"^vSphereSupervisorControlPlane",
    "vcls":                   r"^vCLS-",
    "tkc_cp":                 r"-control-plane-",
    "tkc_workers_v9":         r"node-pool",
    "tkc_workers_v8":         r"-md-\d+-",
    "tkc_workers_legacy":     r"-workers-",
    "vmservice":              r"^vmservice-",
    "podvm":                  r"^pod-",
    "namespace_managed":      r"^[a-z0-9-]+-(deployment|sts|ds)-",
}

# Resource kinds we care about. Pod is a separate kind in VCF 9 (vSphere
# native pods); in VCF 8 it may or may not exist depending on enablement.
TARGET_KINDS = ["VirtualMachine", "Pod"]


def env(name: str, default: str | None = None, *, required: bool = False) -> str:
    val = os.environ.get(name, default)
    if required and not val:
        sys.exit(f"FATAL: env var {name} is required")
    return val or ""


def make_session() -> requests.Session:
    sess = requests.Session()
    verify = env("VCFOPS_VERIFY_SSL", "true").lower() != "false"
    sess.verify = verify
    if not verify:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    return sess


def acquire_token(sess: requests.Session, host: str) -> str:
    body = {
        "username":   env("VCFOPS_USER", required=True),
        "password":   env("VCFOPS_PASSWORD", required=True),
        "authSource": env("VCFOPS_AUTH_SOURCE", "Local"),
    }
    r = sess.post(
        f"https://{host}/suite-api/api/auth/token/acquire",
        json=body,
        headers={"Accept": "application/json"},
        timeout=30,
    )
    if r.status_code != 200:
        sys.exit(f"FATAL: auth failed {r.status_code}: {r.text[:300]}")
    token = r.json().get("token")
    if not token:
        sys.exit(f"FATAL: auth response missing 'token': {r.text[:300]}")
    return token


def list_resources(sess, host, token, kind: str) -> list[dict]:
    """Page through all VirtualMachine (or Pod) resources."""
    out: list[dict] = []
    page = 0
    while True:
        r = sess.get(
            f"https://{host}/suite-api/api/resources",
            params={
                "resourceKind": kind,
                "page":         page,
                "pageSize":     1000,
            },
            headers={
                "Accept":        "application/json",
                "Authorization": f"vRealizeOpsToken {token}",
            },
            timeout=60,
        )
        if r.status_code == 404:
            print(f"  ! resource kind {kind!r} not present on this instance — skipping")
            return out
        if r.status_code != 200:
            sys.exit(f"FATAL: list {kind} page {page} -> {r.status_code}: {r.text[:300]}")
        body = r.json()
        chunk = body.get("resourceList", [])
        out.extend(chunk)
        meta = body.get("pageInfo", {}) or {}
        if not chunk or meta.get("page", 0) + 1 >= meta.get("totalPages", 1):
            break
        page += 1
    return out


def get_properties(sess, host, token, resource_id: str) -> dict[str, str]:
    """Return a flat dict of {propertyKey: latestValue} for one resource."""
    r = sess.get(
        f"https://{host}/suite-api/api/resources/{resource_id}/properties",
        headers={
            "Accept":        "application/json",
            "Authorization": f"vRealizeOpsToken {token}",
        },
        timeout=30,
    )
    if r.status_code != 200:
        return {}
    out: dict[str, str] = {}
    for p in (r.json().get("property") or []):
        key = p.get("name")
        # The wire format puts the value under "values" for time-series
        # and "value" for single-shot properties; tolerate both.
        val = p.get("value")
        if val is None:
            vals = p.get("values") or []
            if vals:
                val = vals[-1]
        if key and val is not None:
            out[key] = str(val)
    return out


def name_pattern_buckets(name: str) -> list[str]:
    hits = []
    for label, pat in NAME_PATTERNS.items():
        if re.search(pat, name):
            hits.append(label)
    return hits


def main() -> int:
    host = env("VCFOPS_HOST", required=True)
    sess = make_session()
    token = acquire_token(sess, host)

    print(f"# VKS Marker Recon")
    print(f"# Target host: {host}")
    print()

    for kind in TARGET_KINDS:
        print(f"## Resource kind: {kind}")
        resources = list_resources(sess, host, token, kind)
        print(f"  total: {len(resources)}")
        if not resources:
            print()
            continue

        # For VirtualMachine we fetch properties to bucket. For Pod the
        # name alone tells us almost everything we need (and Pod
        # property bags are sparse).
        prop_combo_counts: Counter = Counter()
        prop_value_counts: dict[str, Counter] = defaultdict(Counter)
        examples: dict[tuple, list[str]] = defaultdict(list)
        name_bucket_counts: Counter = Counter()
        name_examples: dict[str, list[str]] = defaultdict(list)
        unmatched: list[str] = []

        for i, res in enumerate(resources):
            rid = (res.get("identifier") or "")
            rname = (res.get("resourceKey", {}) or {}).get("name", "?")

            buckets = name_pattern_buckets(rname)
            for b in buckets:
                name_bucket_counts[b] += 1
                if len(name_examples[b]) < 5:
                    name_examples[b].append(rname)
            if not buckets and len(unmatched) < 20:
                unmatched.append(rname)

            if kind != "VirtualMachine":
                continue

            props = get_properties(sess, host, token, rid)
            combo = tuple(props.get(k, "") for k in INTERESTING_PROPS)
            prop_combo_counts[combo] += 1
            if len(examples[combo]) < 5:
                examples[combo].append(rname)
            for k in INTERESTING_PROPS:
                v = props.get(k, "")
                if v:
                    prop_value_counts[k][v] += 1

            if (i + 1) % 50 == 0:
                print(f"  ... fetched properties for {i + 1}/{len(resources)}", file=sys.stderr)

        print()
        print(f"### Name-pattern hits ({kind})")
        if not name_bucket_counts:
            print("  (no known name patterns matched)")
        for label, n in name_bucket_counts.most_common():
            samples = ", ".join(name_examples[label][:3])
            print(f"  - {label:24} {n:5}    e.g. {samples}")
        if unmatched and kind == "VirtualMachine":
            print(f"  unmatched (sample, up to 20): {unmatched[:20]}")
        print()

        if kind != "VirtualMachine":
            continue

        print(f"### Distinct values per property")
        for k in INTERESTING_PROPS:
            counts = prop_value_counts[k]
            if not counts:
                print(f"  {k}: (no values observed)")
                continue
            print(f"  {k}:")
            for val, n in counts.most_common(15):
                preview = val if len(val) <= 80 else val[:77] + "..."
                print(f"      {n:5}  {preview!r}")
        print()

        print(f"### Top property combinations")
        print(f"  (one row per unique {INTERESTING_PROPS} tuple)")
        for combo, n in prop_combo_counts.most_common(20):
            print(f"  {n:5} VMs  productName={combo[0]!r:50}  type={combo[1]!r}")
            for ex in examples[combo][:3]:
                print(f"        e.g. {ex}")
        print()

    print("# DONE")
    print()
    print("Suggested next steps:")
    print("  1. For each VKS marker (supervisor / TKC node / VM Service / vCLS / regular VM),")
    print("     identify which property combo above corresponds. Most likely candidates:")
    print("       - Supervisor CP:  productName='vSphere Supervisor' (v9) OR")
    print("                         name starts with 'SupervisorControlPlaneVM' (v8 fallback)")
    print("       - TKC cluster:    productName='vSphere Kubernetes Service Cluster Node Image' (v9)")
    print("                         vs. older TKGS patterns (v8): check productName values above")
    print("       - vCLS:           name starts with 'vCLS-'")
    print("       - VM Service:     name starts with 'vmservice-' (newer) OR")
    print("                         managedBy.type contains 'kubernetes' (varies by release)")
    print("       - Regular VMs:    summary|config|type='default'")
    print("  2. For the v8 markers we can use, port them into a new SM variant or extend the")
    print("     existing SM where: clauses (single-condition only — compound && silently fails).")
    print("  3. If no v8 marker discriminates the same set as v9, fall back to multi-SM")
    print("     subtraction (Total - Supervisor - vCLS - VMService = TKC + Regular, etc.).")


if __name__ == "__main__":
    main()

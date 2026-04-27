#!/usr/bin/env python3
"""
VKS Marker Recon — figure out which properties VCF Operations exposes on
VirtualMachine resources so we can pick markers that classify VMs by role
(Supervisor CP, VKS guest, VM Service, vSphere Pod, vCLS, Regular)
deterministically and version-agnostically.

This is the second-pass recon. The first pass found that the obvious
managedBy paths (`summary|config|managedBy|extension`,
`summary|config|managedBy|type`) returned empty in the v8 lab — but we
don't know whether (a) VCF Operations doesn't surface managedBy at all,
or (b) it surfaces it under a different property key. This pass tries
many candidate paths systematically AND dumps the full property bag of
one representative VM per name-pattern category, so we can see exactly
what VCF Operations exposes.

Run this against:
- A VCF 5.2 / Aria Operations 8.18 environment (the original target).
- A VCF Operations 9.x PROD environment that actually has Supervisor +
  VKS workloads (devel doesn't have them).

Usage:
    export VCFOPS_HOST=<your-ops-host>
    export VCFOPS_USER=<read-capable-account>
    export VCFOPS_PASSWORD='...'
    # optional, defaults to "Local":
    export VCFOPS_AUTH_SOURCE='Local'
    # optional, set to "false" to skip TLS verification:
    export VCFOPS_VERIFY_SSL=true

    python3 scripts/vks_marker_recon.py

Read-only. No mutations. No content created.
Suite-API endpoints used (auth/token, resources, properties,
relationships) are stable across Aria Ops 8.x and VCF Operations 9.x.
"""
from __future__ import annotations

import os
import re
import sys
from collections import Counter, defaultdict

import requests
import urllib3

# Properties the VKS 9 SMs already use, plus a wider sweep of `managedBy`
# path candidates. The first-pass recon probed only a few of these; this
# pass tries every variant we can think of so we can pin down whether
# VCF Operations exposes ManagedBy.extensionKey at all.
INTERESTING_PROPS = [
    # Already in production use by SMs:
    "summary|config|productName",
    "summary|config|type",
    "config|guestFullName",
    "summary|parentFolder",
    # Identity / display:
    "summary|managedObjectName",
    # ManagedBy candidates — try EVERY variant. PowerShell uses
    # ExtensionData.Config.ManagedBy.ExtensionKey in vSphere SDK; VCF Ops
    # may surface this under any of these path shapes.
    "summary|managedBy|extension",
    "summary|managedBy|extensionKey",
    "summary|managedBy|type",
    "summary|config|managedBy|extension",
    "summary|config|managedBy|extensionKey",
    "summary|config|managedBy|type",
    "config|managedBy|extension",
    "config|managedBy|extensionKey",
    "config|managedBy|type",
    "managedBy|extension",
    "managedBy|extensionKey",
    "managedBy|type",
    # Resource-pool / namespace candidates — PowerShell checks
    # resourcePool.ExtensionData.Namespace; we want to find the equivalent.
    "summary|parentResourcePool",
    "summary|parent",
    "config|annotation",
    "summary|config|annotation",
    # Misc that might surface useful identity hints:
    "config|extraConfig",
]

# Known name fragments worth bucketing — these tell us which VM is which
# at name-pattern level so the deep-dump can pick a representative.
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
    out: list[dict] = []
    page = 0
    while True:
        r = sess.get(
            f"https://{host}/suite-api/api/resources",
            params={"resourceKind": kind, "page": page, "pageSize": 1000},
            headers={
                "Accept":        "application/json",
                "Authorization": f"vRealizeOpsToken {token}",
            },
            timeout=60,
        )
        if r.status_code == 404:
            print(f"  ! resource kind {kind!r} not present — skipping")
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
        val = p.get("value")
        if val is None:
            vals = p.get("values") or []
            if vals:
                val = vals[-1]
        if key and val is not None:
            out[key] = str(val)
    return out


def get_parent_resourcepools(sess, host, token, resource_id: str) -> list[dict]:
    """
    Return the list of parent resources whose resourceKind is ResourcePool.
    Uses the Suite-API relationships endpoint with relationshipType=PARENT.
    """
    r = sess.get(
        f"https://{host}/suite-api/api/resources/{resource_id}/relationships",
        params={"relationshipType": "PARENT"},
        headers={
            "Accept":        "application/json",
            "Authorization": f"vRealizeOpsToken {token}",
        },
        timeout=30,
    )
    if r.status_code != 200:
        return []
    body = r.json()
    out: list[dict] = []
    for res in (body.get("resourceList") or []):
        rk = (res.get("resourceKey") or {})
        if rk.get("resourceKindKey") == "ResourcePool":
            out.append(res)
    return out


def get_resource_by_id(sess, host, token, resource_id: str) -> dict:
    r = sess.get(
        f"https://{host}/suite-api/api/resources/{resource_id}",
        headers={
            "Accept":        "application/json",
            "Authorization": f"vRealizeOpsToken {token}",
        },
        timeout=30,
    )
    if r.status_code != 200:
        return {}
    return r.json()


def name_pattern_buckets(name: str) -> list[str]:
    return [label for label, pat in NAME_PATTERNS.items() if re.search(pat, name)]


def deep_dump_vm(sess, host, token, res: dict) -> None:
    """Print the full property bag and parent ResourcePool info for one VM."""
    rid = res.get("identifier") or ""
    rname = (res.get("resourceKey", {}) or {}).get("name", "?")

    print(f"  --- DEEP DUMP: {rname} (id={rid}) ---")
    print()

    props = get_properties(sess, host, token, rid)
    print(f"  Total properties exposed: {len(props)}")
    if not props:
        print("  (no properties returned — VM may have no collected properties)")
    else:
        # Sort for stable output. Print key=value, truncate long values.
        for key in sorted(props.keys()):
            v = props[key]
            preview = v if len(v) <= 120 else v[:117] + "..."
            print(f"    {key} = {preview!r}")
    print()

    # Parent ResourcePool — useful for the namespace-RP marker the
    # PowerShell script uses to discriminate VKS guest vs VM Service.
    parents = get_parent_resourcepools(sess, host, token, rid)
    print(f"  Parent ResourcePool count: {len(parents)}")
    for rp in parents:
        rp_id = rp.get("identifier") or ""
        rp_name = (rp.get("resourceKey") or {}).get("name", "?")
        print(f"    RP: {rp_name} (id={rp_id})")
        # Pull the RP's own properties — namespace info, if any, lives here.
        rp_props = get_properties(sess, host, token, rp_id)
        print(f"      RP properties (total {len(rp_props)}):")
        # Print only the ones likely to indicate "namespace RP"
        ns_likely = [k for k in rp_props if "namespace" in k.lower()
                     or "wcp" in k.lower()
                     or "tanzu" in k.lower()
                     or "kubernetes" in k.lower()
                     or "managedBy" in k.lower()
                     or "managed_by" in k.lower()]
        if ns_likely:
            for k in sorted(ns_likely):
                v = rp_props[k]
                preview = v if len(v) <= 120 else v[:117] + "..."
                print(f"        {k} = {preview!r}")
        else:
            print(f"        (no namespace/wcp/tanzu/kubernetes/managedBy keys)")
        # Also print first 10 keys for orientation
        sample = sorted(rp_props.keys())[:10]
        if sample:
            print(f"      RP property sample (first 10 keys, alphabetical):")
            for k in sample:
                v = rp_props[k]
                preview = v if len(v) <= 80 else v[:77] + "..."
                print(f"        {k} = {preview!r}")
    print()


def main() -> int:
    host = env("VCFOPS_HOST", required=True)
    sess = make_session()
    token = acquire_token(sess, host)

    print(f"# VKS Marker Recon (v2 — adds managedBy probes + deep dumps)")
    print(f"# Target host: {host}")
    print()

    # We'll do a deep dump for one representative VM in each name-pattern
    # category. Track which buckets we've already deep-dumped to avoid
    # exploding output.
    deep_dumped_buckets: set[str] = set()
    representative_vms: list[dict] = []

    for kind in TARGET_KINDS:
        print(f"## Resource kind: {kind}")
        resources = list_resources(sess, host, token, kind)
        print(f"  total: {len(resources)}")
        if not resources:
            print()
            continue

        prop_value_counts: dict[str, Counter] = defaultdict(Counter)
        prop_combo_counts: Counter = Counter()
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
                # Pick this VM as the representative for its bucket if we
                # haven't grabbed one yet.
                if b not in deep_dumped_buckets and kind == "VirtualMachine":
                    representative_vms.append(res)
                    deep_dumped_buckets.add(b)

            if not buckets and len(unmatched) < 20:
                unmatched.append(rname)

            if kind != "VirtualMachine":
                continue

            props = get_properties(sess, host, token, rid)
            combo = tuple(props.get(k, "") for k in (
                "summary|config|productName",
                "summary|config|type",
            ))
            prop_combo_counts[combo] += 1
            if len(examples[combo]) < 5:
                examples[combo].append(rname)
            for k in INTERESTING_PROPS:
                v = props.get(k, "")
                if v:
                    prop_value_counts[k][v] += 1

            if (i + 1) % 50 == 0:
                print(f"  ... fetched properties for {i + 1}/{len(resources)}",
                      file=sys.stderr)

        # If no name-pattern matched any VM, grab a few random VMs as
        # representatives so we can still see what properties exist.
        if not deep_dumped_buckets and kind == "VirtualMachine":
            representative_vms.extend(resources[:3])

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

        print(f"### Distinct values per probed property")
        any_managedby_hit = False
        for k in INTERESTING_PROPS:
            counts = prop_value_counts[k]
            if not counts:
                # Suppress the noisy "(no values observed)" lines for the
                # managedBy variants — list a single summary line at the end.
                if "managedBy" in k:
                    continue
                print(f"  {k}: (no values observed)")
                continue
            if "managedBy" in k:
                any_managedby_hit = True
            print(f"  {k}:")
            for val, n in counts.most_common(15):
                preview = val if len(val) <= 80 else val[:77] + "..."
                print(f"      {n:5}  {preview!r}")
        if not any_managedby_hit:
            print(f"  (none of the {sum(1 for k in INTERESTING_PROPS if 'managedBy' in k)} "
                  f"managedBy|* path candidates returned values on this instance)")
        print()

        print(f"### Top productName + type combinations")
        for combo, n in prop_combo_counts.most_common(20):
            print(f"  {n:5} VMs  productName={combo[0]!r:50}  type={combo[1]!r}")
            for ex in examples[combo][:3]:
                print(f"        e.g. {ex}")
        print()

    # ── Deep dumps ────────────────────────────────────────────────────────
    print()
    print(f"## Deep dumps (one representative VM per name-pattern category)")
    print(f"   (each dump = full property bag + parent ResourcePool info)")
    print()
    for res in representative_vms:
        deep_dump_vm(sess, host, token, res)

    print("# DONE")
    print()
    print("Looking at the output, the questions to answer are:")
    print("  1. Which managedBy|* path (if any) returned values? That's the")
    print("     property key our where: clauses can use.")
    print("  2. In the deep dumps, look for any property containing")
    print("     'managedBy', 'wcp', 'eam', 'tanzu', 'kubernetes', or")
    print("     'namespace'. Those are the marker candidates.")
    print("  3. For the parent ResourcePool of a VM, does any property")
    print("     indicate it's a vSphere namespace (Workload Management)")
    print("     pool? That's how we'd discriminate VKS guests (RP without")
    print("     namespace) from VM Service VMs (RP with namespace), per")
    print("     the PowerShell script's logic.")
    print()
    print("Send the output back; we'll convert findings into SM where:")
    print("clauses (single-condition only — the framework's compound &&")
    print("limitation still applies).")


if __name__ == "__main__":
    main()

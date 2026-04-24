#!/usr/bin/env python3
"""
VKS marker recon for VCF / Aria Operations 8.x environments.

Purpose
-------
We built the VKS Core Consumption dashboard against vSphere 9
classifier values (`Summary|Configuration|Type` = `VMOperator`,
`SupervisorControlPlane`, etc.). In vSphere 8 the values (and
possibly property keys) differ. This script captures the data
needed to diff v8 against v9 from any VCF/Aria Ops 8.x instance.

Hand this script to someone with a v8 lab. They run it; two files
drop out; they email them back.

Outputs (in cwd):
  * `vks-marker-recon-<host>-<stamp>.csv`
      one row per VirtualMachine with the classifier properties
      we care about
  * `adapter-describe-VMWARE-<host>-<stamp>.xml`
      full VMware adapter describe (best-effort; some 8.x
      builds gate this endpoint)

Usage
-----
  python3 vks_marker_recon_v8.py --host ops.example.com --user admin

Prompts for password. Or set env vars VCFOPS_HOST / VCFOPS_USER /
VCFOPS_PASSWORD (auth source defaults to Local).

Dependencies: Python 3.8+, `requests`. No other deps.
"""
from __future__ import annotations

import argparse
import csv
import getpass
import json
import os
import sys
from datetime import datetime, timezone

try:
    import requests
except ImportError:
    sys.exit("Missing dependency. Install with:  pip install requests")

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# Property keys we want to capture. The API keys use pipe separators
# and lowercase/camelCase — they are NOT the same as the UI labels
# (e.g. UI shows "Summary | Configuration | Type" but the API key
# is typically `summary|config|vmType` or similar). We try several
# likely candidates and record whichever return data. The adapter
# describe XML is the authoritative source of truth.
CANDIDATE_KEYS = [
    "summary|config|vmType",
    "summary|config|guestFullName",
    "summary|config|product|name",
    "config|guestFullName",
    "config|product|name",
    "summary|guest|guestFullName",
    "summary|guest|guestOS",
    "summary|parentCluster",
    "summary|parentDatacenter",
    "summary|parentHost",
    "summary|parentVcenter",
]


def auth(base_url: str, user: str, password: str, auth_source: str) -> str:
    r = requests.post(
        f"{base_url}/suite-api/api/auth/token/acquire",
        json={"username": user, "password": password, "authSource": auth_source},
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        verify=False,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["token"]


def H(token: str) -> dict:
    return {"Authorization": f"OpsToken {token}", "Accept": "application/json"}


def get_version(base_url: str, token: str) -> dict:
    try:
        r = requests.get(f"{base_url}/suite-api/api/versions/current",
                         headers=H(token), verify=False, timeout=30)
        if r.ok:
            return r.json()
    except Exception:
        pass
    return {}


def get_vmware_adapter_kind(base_url: str, token: str) -> str:
    r = requests.get(f"{base_url}/suite-api/api/adapterkinds",
                     headers=H(token), verify=False, timeout=30)
    r.raise_for_status()
    for ak in r.json().get("adapter-kind", []):
        if ak.get("key") in ("VMWARE", "VMware", "vCenter"):
            return ak["key"]
    return "VMWARE"


def get_adapter_describe(base_url: str, token: str, ak_key: str) -> str | None:
    """Best-effort adapter describe retrieval. Path varies by version."""
    paths = [
        f"/suite-api/api/adapterkinds/{ak_key}/describe",
        f"/suite-api/internal/adapterkinds/{ak_key}/adapter-describe",
        f"/suite-api/api/adapterkinds/{ak_key}/resourcekinds",
    ]
    for path in paths:
        try:
            r = requests.get(
                f"{base_url}{path}",
                headers={**H(token),
                         "X-Ops-API-use-unsupported": "true",
                         "Accept": "application/xml"},
                verify=False, timeout=60,
            )
            if r.ok and r.text.strip().startswith("<"):
                return r.text
        except Exception:
            continue
    return None


def list_vms(base_url: str, token: str) -> list[dict]:
    out = []
    page = 0
    while True:
        r = requests.get(
            f"{base_url}/suite-api/api/resources",
            params={"resourceKind": "VirtualMachine",
                    "adapterKind": "VMWARE",
                    "page": page, "pageSize": 1000},
            headers=H(token), verify=False, timeout=120,
        )
        r.raise_for_status()
        body = r.json()
        out.extend(body.get("resourceList", []))
        pi = body.get("pageInfo", {})
        total = pi.get("totalCount", 0)
        if (pi.get("page", 0) + 1) * pi.get("pageSize", 1000) >= total:
            break
        page += 1
        if page > 200:
            break
    return out


def get_properties(base_url: str, token: str,
                   resource_ids: list[str], keys: list[str]) -> dict:
    r = requests.post(
        f"{base_url}/suite-api/api/resources/properties/latest/query",
        json={"resourceIds": resource_ids, "propertyKeys": keys},
        headers={**H(token), "Content-Type": "application/json"},
        verify=False, timeout=120,
    )
    r.raise_for_status()
    out = {}
    for entry in r.json().get("values", []):
        rid = entry.get("resourceId")
        props = {}
        contents = entry.get("property-contents", {}).get("property-content", [])
        for item in contents:
            k = item.get("statKey")
            vals = item.get("values") or item.get("data") or []
            if vals:
                props[k] = vals[-1]
        out[rid] = props
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    p.add_argument("--host", default=os.environ.get("VCFOPS_HOST"))
    p.add_argument("--user", default=os.environ.get("VCFOPS_USER", "admin"))
    p.add_argument("--password", default=os.environ.get("VCFOPS_PASSWORD"))
    p.add_argument("--auth-source",
                   default=os.environ.get("VCFOPS_AUTH_SOURCE", "Local"))
    args = p.parse_args()

    if not args.host:
        args.host = input("VCF/Aria Ops hostname: ").strip()
    if not args.password:
        args.password = getpass.getpass(f"Password for {args.user}@{args.host}: ")

    base_url = f"https://{args.host}" if not args.host.startswith("http") else args.host

    print(f"[1/5] Auth to {base_url} as {args.user}...")
    token = auth(base_url, args.user, args.password, args.auth_source)

    print("[2/5] Ops version...")
    version = get_version(base_url, token)
    print(f"       {version.get('releaseName', '?')} / "
          f"{version.get('versionAndBuild', '?')}")

    print("[3/5] VMware adapter kind...")
    ak_key = get_vmware_adapter_kind(base_url, token)
    print(f"       adapter kind: {ak_key}")

    print("[4/5] Adapter describe (best-effort)...")
    describe_xml = get_adapter_describe(base_url, token, ak_key)
    if describe_xml:
        print(f"       captured {len(describe_xml)} bytes")
    else:
        print("       endpoint not accessible on this build; skipping")

    print("[5/5] Sampling VirtualMachine properties...")
    vms = list_vms(base_url, token)
    print(f"       {len(vms)} VMs found")

    id_to_name = {vm["identifier"]:
                  vm.get("resourceKey", {}).get("name", vm["identifier"])
                  for vm in vms}

    all_props: dict[str, dict] = {}
    ids = list(id_to_name.keys())
    batch = 200
    for i in range(0, len(ids), batch):
        chunk = ids[i:i + batch]
        all_props.update(get_properties(base_url, token, chunk, CANDIDATE_KEYS))
        print(f"       ...{min(i + batch, len(ids))}/{len(ids)}")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    safe_host = args.host.replace(":", "_").replace("/", "_")

    csv_path = f"vks-marker-recon-{safe_host}-{stamp}.csv"
    with open(csv_path, "w", newline="") as f:
        # Collect all keys that actually returned data — keeps CSV lean
        present_keys = sorted({k for props in all_props.values() for k in props})
        writer = csv.writer(f)
        writer.writerow(["vm_name", "resource_id"] + present_keys)
        for rid, name in id_to_name.items():
            row = [name, rid]
            props = all_props.get(rid, {})
            for k in present_keys:
                row.append(props.get(k, ""))
            writer.writerow(row)
    print(f"\n-> {csv_path}")

    meta_path = f"vks-marker-recon-{safe_host}-{stamp}.meta.json"
    with open(meta_path, "w") as f:
        json.dump({
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "ops_host": args.host,
            "ops_version": version,
            "vmware_adapter_kind": ak_key,
            "vm_count": len(vms),
            "candidate_keys_queried": CANDIDATE_KEYS,
            "keys_with_data": sorted(
                {k for props in all_props.values() for k in props}),
            "adapter_describe_captured": bool(describe_xml),
        }, f, indent=2, default=str)
    print(f"-> {meta_path}")

    if describe_xml:
        xml_path = f"adapter-describe-{ak_key}-{safe_host}-{stamp}.xml"
        with open(xml_path, "w") as f:
            f.write(describe_xml)
        print(f"-> {xml_path}")

    print("\nDone. Send all three files back to the factory team.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

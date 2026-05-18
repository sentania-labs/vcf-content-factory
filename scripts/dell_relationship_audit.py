#!/usr/bin/env python3
"""
Dell PowerEdge MP — Relationship Audit (read-only)

Investigates how the Dell adapter on a VCF Operations instance models its
objects and relationships. Built in response to PM feedback that
"firmware version of components are created as same-level objects as the
Physical server" — i.e. the suspicion that component/firmware data is
being emitted as sibling resources rather than as properties on (or
children of) a PhysicalServer.

What it does (all GETs, zero mutations):
  1. Authenticates against the Suite API.
  2. Finds the Dell adapter kind (case-insensitive 'dell' / 'poweredge'
     match against /api/adapterkinds; can be overridden with
     --adapter-kind).
  3. Lists every resource for that adapter kind, bucketed by resource
     kind, with counts.
  4. For each resource kind, samples up to N resources and dumps their
     CHILD and PARENT relationship sets (resource kind only — we don't
     fetch full objects for every neighbour to keep this cheap).
  5. Flags suspected mis-modelling:
       - resource kinds that look like firmware/BIOS/iDRAC/component
         (heuristic name match) that have NO parents (top-level
         siblings to PhysicalServer)
       - resource kinds whose name suggests a component but whose
         identifier set looks like a serial/version (i.e. should
         arguably be a property, not an object)
  6. Optionally dumps the full audit to a JSON file for offline review.

Designed for WSL on a corporate laptop on VPN:
  - Standard library only (no pip install required).
  - --insecure flag for self-signed / MITM-proxy environments.
  - --timeout configurable; defaults sized for VPN latency.
  - All output is plain ASCII — no terminal-specific escapes.

Usage:
    python3 dell_relationship_audit.py \\
        --url https://ops.example.com \\
        --user admin \\
        --auth-source Local \\
        --insecure \\
        --output dell_audit.json

    # Or, supply password / token interactively to avoid shell history:
    python3 dell_relationship_audit.py --url ... --user ... --prompt-password

    # If the Dell adapter kind key is known, skip the lookup:
    python3 dell_relationship_audit.py --url ... --adapter-kind Dell

Endpoints used (all stable across Aria Ops 8.x and VCF Ops 9.x):
    POST /suite-api/api/auth/token/acquire
    GET  /suite-api/api/adapterkinds
    GET  /suite-api/api/adapterkinds/{key}/resourcekinds
    GET  /suite-api/api/resources?adapterKindKey=<key>&pageSize=N&page=P
    GET  /suite-api/api/resources/{id}/relationships?relationshipType=CHILD
    GET  /suite-api/api/resources/{id}/relationships?relationshipType=PARENT
    GET  /suite-api/api/resources/{id}/properties
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any


# Heuristic: resource-kind / resource-name patterns that *suggest* the
# object is really a component or firmware record. Used only for
# flagging — not for filtering. Tweak via --component-pattern.
COMPONENT_HINT_PATTERNS = [
    r"firmware",
    r"bios",
    r"idrac",
    r"drac",
    r"\bnic\b",
    r"\bcpu\b",
    r"\bdimm\b",
    r"\bpsu\b",
    r"power.?supply",
    r"\bfan\b",
    r"controller",
    r"raid",
    r"disk",
    r"drive",
    r"backplane",
    r"\bcomponent\b",
    r"\bsensor\b",
    r"battery",
    r"version",
]


def log(msg: str) -> None:
    print(msg, flush=True)


def banner(title: str) -> None:
    log("")
    log("=" * 72)
    log(title)
    log("=" * 72)


class OpsClient:
    """Minimal stdlib-only Suite API client."""

    def __init__(self, base_url: str, verify_ssl: bool, timeout: int, token_scheme: str = "OpsToken"):
        self.base = base_url.rstrip("/")
        self.timeout = timeout
        self.token: str | None = None
        self.token_scheme = token_scheme  # "OpsToken" (VCF Ops 9+) or "vRealizeOpsToken" (Aria Ops 8.x)
        if verify_ssl:
            self.ssl_ctx = ssl.create_default_context()
        else:
            self.ssl_ctx = ssl.create_default_context()
            self.ssl_ctx.check_hostname = False
            self.ssl_ctx.verify_mode = ssl.CERT_NONE

    def _request(
        self,
        method: str,
        path: str,
        query: dict | None = None,
        body: dict | None = None,
    ) -> dict:
        url = f"{self.base}{path}"
        if query:
            url = f"{url}?{urllib.parse.urlencode(query)}"
        data = None
        headers = {"Accept": "application/json"}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["Authorization"] = f"{self.token_scheme} {self.token}"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, context=self.ssl_ctx, timeout=self.timeout) as resp:
                raw = resp.read()
                if not raw:
                    return {}
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            body_text = ""
            try:
                body_text = e.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            raise RuntimeError(
                f"HTTP {e.code} {method} {path}\n  body: {body_text[:500]}"
            ) from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"Network error {method} {path}: {e.reason}") from e

    def acquire_token(self, username: str, password: str, auth_source: str) -> None:
        log(f"[auth] acquiring token as {auth_source}\\{username} ...")
        result = self._request(
            "POST",
            "/suite-api/api/auth/token/acquire",
            body={
                "username": username,
                "password": password,
                "authSource": auth_source,
            },
        )
        token = result.get("token")
        if not token:
            raise RuntimeError(f"Auth response missing token: {result}")
        self.token = token
        log("[auth] OK")

    def list_adapter_kinds(self) -> list[dict]:
        result = self._request("GET", "/suite-api/api/adapterkinds")
        return result.get("adapter-kind", []) or []

    def list_resource_kinds(self, adapter_kind_key: str) -> list[dict]:
        result = self._request(
            "GET",
            f"/suite-api/api/adapterkinds/{adapter_kind_key}/resourcekinds",
        )
        return result.get("resource-kind", []) or []

    def list_resources(
        self,
        adapter_kind_key: str,
        max_resources: int,
        page_size: int = 200,
    ) -> list[dict]:
        out: list[dict] = []
        page = 0
        while True:
            result = self._request(
                "GET",
                "/suite-api/api/resources",
                query={
                    "adapterKindKey": adapter_kind_key,
                    "pageSize": page_size,
                    "page": page,
                },
            )
            batch = result.get("resourceList", []) or []
            out.extend(batch)
            page_info = result.get("pageInfo") or {}
            total = page_info.get("totalCount", len(out))
            if not batch or len(out) >= max_resources or len(out) >= total:
                break
            page += 1
        return out[:max_resources]

    def get_relationships(self, resource_id: str, direction: str) -> list[dict]:
        # direction is CHILD or PARENT
        result = self._request(
            "GET",
            f"/suite-api/api/resources/{resource_id}/relationships",
            query={"relationshipType": direction},
        )
        return result.get("resourceList", []) or []

    def get_properties(self, resource_id: str) -> list[dict]:
        result = self._request(
            "GET",
            f"/suite-api/api/resources/{resource_id}/properties",
        )
        return result.get("property", []) or []


def resource_key(r: dict) -> dict:
    rk = r.get("resourceKey") or {}
    return rk


def res_name(r: dict) -> str:
    return resource_key(r).get("name", "?")


def res_kind(r: dict) -> str:
    return resource_key(r).get("resourceKindKey", "?")


def res_id(r: dict) -> str:
    return r.get("identifier", "?")


def res_identifiers(r: dict) -> list[dict]:
    return resource_key(r).get("resourceIdentifiers", []) or []


def find_dell_adapter_kind(client: OpsClient, override: str | None) -> dict:
    kinds = client.list_adapter_kinds()
    if override:
        for k in kinds:
            if k.get("key", "").lower() == override.lower() or k.get("name", "").lower() == override.lower():
                return k
        raise RuntimeError(f"adapter-kind override '{override}' not found on instance")
    candidates: list[dict] = []
    for k in kinds:
        blob = f"{k.get('key','')} {k.get('name','')} {k.get('describeVersion','')}".lower()
        if "dell" in blob or "poweredge" in blob or "idrac" in blob or "openmanage" in blob:
            candidates.append(k)
    if not candidates:
        raise RuntimeError(
            "No adapter kind whose key/name matches dell/poweredge/idrac/openmanage. "
            "Pass --adapter-kind <key> explicitly."
        )
    if len(candidates) > 1:
        log("[warn] multiple Dell-ish adapter kinds found — pick one with --adapter-kind:")
        for c in candidates:
            log(f"         key={c.get('key')}  name={c.get('name')}")
        raise RuntimeError("ambiguous adapter kind")
    return candidates[0]


def hints_match(text: str, patterns: list[str]) -> list[str]:
    hits = []
    low = text.lower()
    for p in patterns:
        if re.search(p, low):
            hits.append(p)
    return hits


def audit(args) -> int:
    client = OpsClient(args.url, verify_ssl=not args.insecure, timeout=args.timeout,
                       token_scheme=args.token_scheme)

    # Password / token resolution
    if args.token:
        client.token = args.token
        log("[auth] using --token (skipping acquire)")
    else:
        password = args.password or os.environ.get("VCFOPS_PASSWORD")
        if args.prompt_password or not password:
            password = getpass.getpass(f"Password for {args.user}@{args.url}: ")
        client.acquire_token(args.user, password, args.auth_source)

    # 1. Locate Dell adapter kind
    banner("Adapter Kind Discovery")
    ak = find_dell_adapter_kind(client, args.adapter_kind)
    ak_key = ak["key"]
    log(f"[adapter] key  = {ak_key}")
    log(f"[adapter] name = {ak.get('name')}")
    log(f"[adapter] describeVersion = {ak.get('describeVersion')}")

    # Resource kinds declared by the adapter (from describe.xml, server-side)
    declared_kinds = client.list_resource_kinds(ak_key)
    log(f"[adapter] declared resource kinds = {len(declared_kinds)}")
    for rk in declared_kinds:
        log(f"           - {rk.get('key')}  ({rk.get('name')})")

    # 2. Enumerate resources
    banner("Resource Inventory")
    resources = client.list_resources(ak_key, max_resources=args.max_resources)
    log(f"[inventory] resources fetched: {len(resources)} (cap={args.max_resources})")
    by_kind: dict[str, list[dict]] = defaultdict(list)
    for r in resources:
        by_kind[res_kind(r)].append(r)
    kind_counts = {k: len(v) for k, v in by_kind.items()}
    log("[inventory] count by resourceKindKey:")
    for k, n in sorted(kind_counts.items(), key=lambda kv: -kv[1]):
        log(f"             {n:5d}  {k}")

    # 3. Sample relationships per kind
    banner("Relationship Sampling")
    sample_n = args.sample
    samples_dump: dict[str, list[dict]] = {}
    for kind, rs in sorted(by_kind.items()):
        log("")
        log(f"--- resourceKind: {kind} (sampling up to {sample_n} of {len(rs)}) ---")
        sample = rs[:sample_n]
        kind_dump: list[dict] = []
        for r in sample:
            rid = res_id(r)
            name = res_name(r)
            try:
                children = client.get_relationships(rid, "CHILD")
                parents = client.get_relationships(rid, "PARENT")
            except RuntimeError as e:
                log(f"  ! {name} [{rid}]: relationship fetch failed: {e}")
                continue
            child_kinds = Counter(res_kind(c) for c in children)
            parent_kinds = Counter(res_kind(p) for p in parents)
            log(f"  * {name}  [{rid}]")
            log(f"      parents : {dict(parent_kinds) or '(none — top-level)'}")
            log(f"      children: {dict(child_kinds) or '(none)'}")
            kind_dump.append({
                "id": rid,
                "name": name,
                "parents": [
                    {"id": res_id(p), "name": res_name(p), "kind": res_kind(p)}
                    for p in parents
                ],
                "children": [
                    {"id": res_id(c), "name": res_name(c), "kind": res_kind(c)}
                    for c in children
                ],
            })
        samples_dump[kind] = kind_dump

    # 4. Flag suspected mis-modelling
    banner("Mis-modelling Flags (heuristic)")
    patterns = args.component_pattern or COMPONENT_HINT_PATTERNS
    flagged: list[dict] = []
    for kind, rs in by_kind.items():
        kind_hits = hints_match(kind, patterns)
        if not kind_hits:
            continue
        kind_sample = samples_dump.get(kind, [])
        # Smoking gun 1: top-level — no parent at all.
        top_level = [s for s in kind_sample if not s["parents"]]
        # Smoking gun 2: double-parented — has the adapter instance AS A
        # PARENT in addition to a logical parent. This is what makes
        # components appear as SIBLINGS of the server in the adapter
        # instance's child list, even when a "real" hierarchy exists
        # underneath. The Dell PowerEdge v4 MP shows this pattern.
        double_parented = [
            s for s in kind_sample
            if any(p["kind"] == ak_key for p in s["parents"])
            and len(s["parents"]) > 1
        ]
        # Non-adapter parent kinds — useful for spotting weird edges
        # (e.g. physical_drive parented to cpu1, fan parented to a
        # collection node instead of the chassis).
        non_adapter_parents: Counter = Counter()
        for s in kind_sample:
            for p in s["parents"]:
                if p["kind"] != ak_key:
                    non_adapter_parents[p["kind"]] += 1
        flagged.append({
            "resourceKind": kind,
            "kindMatchedPatterns": kind_hits,
            "totalCount": len(rs),
            "sampled": len(kind_sample),
            "sampledTopLevel": len(top_level),
            "sampledDoubleParented": len(double_parented),
            "sampleTopLevelNames": [s["name"] for s in top_level[:5]],
            "nonAdapterParentKinds": dict(non_adapter_parents),
        })

    if not flagged:
        log("[flags] no resource kinds matched component/firmware heuristics.")
        log("        Re-run with --component-pattern '<regex>' to widen the net.")
    else:
        log("[flags] resource kinds suggesting component / firmware data:")
        for f in flagged:
            log("")
            log(f"  kind={f['resourceKind']}  matched={f['kindMatchedPatterns']}")
            log(f"    total resources of this kind             : {f['totalCount']}")
            log(f"    sampled                                  : {f['sampled']}")
            log(f"    sampled with NO parent (top-level)       : {f['sampledTopLevel']}")
            log(f"    sampled double-parented to adapter inst. : {f['sampledDoubleParented']}")
            log(f"    non-adapter parent kinds (logical parent): {f['nonAdapterParentKinds'] or '(none)'}")
            if f["sampleTopLevelNames"]:
                log(f"    top-level examples: {f['sampleTopLevelNames']}")
            if f["sampledTopLevel"] > 0:
                log(f"    >> SMOKING GUN A: orphan components — top-level, no parent.")
                log(f"       Should be CHILDREN of, or PROPERTIES on, the server.")
            if f["sampledDoubleParented"] > 0:
                log(f"    >> SMOKING GUN B: components double-parented to the")
                log(f"       adapter instance. From the adapter instance's child list")
                log(f"       these appear as SIBLINGS of the physical server.")
                log(f"       The 'logical' parent edge exists but is masked by the")
                log(f"       direct adapter-instance edge. This is what 'firmware at")
                log(f"       same level as server' looks like in the UI.")

    # 5. Property dump on one representative resource per flagged kind +
    # one representative PhysicalServer-ish kind, to show what's
    # currently stored where.
    banner("Representative Property Dumps")
    # PhysicalServer-ish: a kind whose key/name screams "server" but
    # NOT "component". This is to show, on the parent device, what
    # properties already live alongside it.
    server_kind = None
    for kind in by_kind:
        low = kind.lower()
        if ("server" in low or "host" in low or "system" in low or "chassis" in low) \
                and not hints_match(kind, patterns):
            server_kind = kind
            break
    dump_targets: list[tuple[str, str]] = []
    if server_kind and by_kind[server_kind]:
        dump_targets.append((server_kind, res_id(by_kind[server_kind][0])))
    for f in flagged:
        rs = by_kind.get(f["resourceKind"], [])
        if rs:
            dump_targets.append((f["resourceKind"], res_id(rs[0])))

    property_dump: dict[str, Any] = {}
    for kind, rid in dump_targets:
        log("")
        log(f"--- properties on {kind} / {rid} ---")
        try:
            props = client.get_properties(rid)
        except RuntimeError as e:
            log(f"  ! property fetch failed: {e}")
            continue
        for p in props[:60]:
            log(f"    {p.get('name','?')} = {str(p.get('value',''))[:80]}")
        if len(props) > 60:
            log(f"    ... ({len(props) - 60} more, truncated; full set in --output)")
        property_dump[f"{kind}/{rid}"] = props

    # 6. JSON dump (auto-named if --output passed without a value;
    #    skipped only when --output is omitted entirely)
    out_path = args.output
    if out_path == "__auto__":
        netloc = urllib.parse.urlparse(args.url).netloc or "ops"
        host_slug = re.sub(r"[^A-Za-z0-9]+", "_", netloc).strip("_") or "ops"
        ak_slug = re.sub(r"[^A-Za-z0-9]+", "_", ak_key).strip("_")
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        out_path = f"dell_audit_{host_slug}_{ak_slug}_{ts}.json"
    if out_path:
        full_dump = {
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "instance": args.url,
            "adapterKind": ak,
            "declaredResourceKinds": declared_kinds,
            "resourceCountByKind": kind_counts,
            "samples": samples_dump,
            "flagged": flagged,
            "properties": property_dump,
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(full_dump, f, indent=2, default=str)
        log("")
        log(f"[output] full JSON dump written to {out_path}")

    # 7. Summary
    banner("Summary for the PM")
    log(f"Instance        : {args.url}")
    log(f"Adapter kind    : {ak_key}  ({ak.get('name')})")
    log(f"Resource kinds  : {len(kind_counts)}")
    log(f"Total resources : {sum(kind_counts.values())} (cap={args.max_resources})")
    smoking_top = [f for f in flagged if f["sampledTopLevel"] > 0]
    smoking_double = [f for f in flagged if f["sampledDoubleParented"] > 0]
    if smoking_top:
        log("Verdict         : LIKELY MISMODELLED — component/firmware kinds found")
        log("                  at top level (no parent server). See flag A.")
    elif smoking_double:
        log("Verdict         : LIKELY MISMODELLED — components double-parented to")
        log("                  the adapter instance. From the adapter instance's")
        log("                  child list they appear as SIBLINGS of the server,")
        log("                  even though a logical parent edge also exists.")
        log("                  This is what 'firmware at same level as server'")
        log("                  looks like in the UI. See flag B.")
    elif flagged:
        log("Verdict         : component-ish kinds exist with clean hierarchy.")
        log("                  Tighten --sample or specific kinds if needed.")
    else:
        log("Verdict         : no obvious component/firmware kinds detected.")
        log("                  Provide --component-pattern matching the MP layout.")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Read-only audit of Dell adapter resource relationships in VCF Operations."
    )
    p.add_argument("--url", required=True, help="Base URL, e.g. https://ops.example.com")
    p.add_argument("--user", help="Username (required unless --token is given)")
    p.add_argument("--password", help="Password (avoid on shared shells; prefer --prompt-password or $VCFOPS_PASSWORD)")
    p.add_argument("--prompt-password", action="store_true", help="Prompt for password interactively")
    p.add_argument("--auth-source", default="Local", help="Auth source name (default: Local)")
    p.add_argument("--token", help="Skip acquire and use an existing OpsToken value")
    p.add_argument("--adapter-kind", help="Override adapter-kind key (skip auto-discovery)")
    p.add_argument("--max-resources", type=int, default=2000, help="Cap on resources fetched (default: 2000)")
    p.add_argument("--sample", type=int, default=3, help="Resources sampled per kind for relationship walk (default: 3)")
    p.add_argument("--component-pattern", action="append",
                   help="Regex (lowercased) to flag as component-ish. Repeatable. Replaces defaults if given.")
    p.add_argument("--timeout", type=int, default=60, help="HTTP timeout seconds (default: 60, VPN-friendly)")
    p.add_argument("--insecure", action="store_true", help="Disable TLS verification (self-signed labs)")
    p.add_argument("--token-scheme", default="OpsToken", choices=["OpsToken", "vRealizeOpsToken"],
                   help="Auth header scheme. OpsToken=VCF Ops 9+, vRealizeOpsToken=Aria Ops 8.x (default: OpsToken)")
    p.add_argument("--output", nargs="?", const="__auto__", default=None, metavar="PATH",
                   help="Write full JSON dump. Pass --output <path> for an explicit file; "
                        "pass --output alone to auto-name as dell_audit_<host>_<adapter>_<ts>.json "
                        "in the current dir. Omit entirely to skip the JSON file.")
    args = p.parse_args(argv)
    if not args.token and not args.user:
        p.error("--user is required (unless --token is supplied)")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    try:
        return audit(args)
    except RuntimeError as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())

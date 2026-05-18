#!/usr/bin/env python3
"""
MP Describe Recon — read-only

Pulls a target adapter kind's declared statkey tree and a few sampled
resources' actually-collected statkeys, so we can diff how MPB-built
packs vs Python-Integration-SDK packs (and vendor packs) declare and
emit per-instance attribute groups in describe.xml.

The decisive signal is the colon character in attribute keys:

    Hardware|Power:PS1|Power Output Watts
                  ^^^^
                  instance segment — present means the group is
                  declared with instanced="true" in describe.xml.

This script catalogs each resource kind's group/attribute paths and
flags any with an embedded colon. It also samples a small number of
live resources per kind to dump their actually-collected statkey paths,
so we can see whether the runtime is honoring the declared shape.

Designed for sneaker-net from WSL on a corporate laptop:
- Standard library only (no pip install required).
- --insecure for self-signed / MITM-proxy environments.
- All output is plain ASCII + a JSON dump.

Run twice — once against the BC instance hosting our v4 Dell pak,
once against the lvn instance hosting Onur's HardwarevCommunity pak —
and send both JSON dumps back here for the structural diff.

Usage:
    # v1: against our v4 Dell pak instance
    python3 mp_describe_recon.py \\
        --url https://10.x.x.x \\
        --user admin --auth-source Local --insecure \\
        --adapter-kind mpb_vcf_content_factory_dell_poweredge_v4 \\
        --output mp_describe_ours_v4.json

    # v2: against Onur's HardwarevCommunity pak instance
    python3 mp_describe_recon.py \\
        --url https://apdvvcfops01.lvn.broadcom.net \\
        --user admin --auth-source Local --insecure \\
        --adapter-kind HardwarevCommunity \\
        --output mp_describe_onur_hardware.json

Auto-discovery for --adapter-kind is supported — pass --adapter-name-hint
"poweredge" or "hardwarev" to fuzzy-match by key/name. If unsure, omit
both and the script lists every adapter kind on the instance so you can
pick.

Endpoints used (all stable Suite API, all read-only):
    POST /suite-api/api/auth/token/acquire
    GET  /suite-api/api/adapterkinds
    GET  /suite-api/api/adapterkinds/{ak}/resourcekinds
    GET  /suite-api/api/adapterkinds/{ak}/resourcekinds/{rk}/statkeys
    GET  /suite-api/api/resources?adapterKindKey=...&resourceKindKey=...
    GET  /suite-api/api/resources/{id}/stats/latest
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
from collections import Counter
from datetime import datetime, timezone
from typing import Any


def log(msg: str) -> None:
    print(msg, flush=True)


def banner(title: str) -> None:
    log("")
    log("=" * 72)
    log(title)
    log("=" * 72)


class OpsClient:
    def __init__(self, base_url: str, verify_ssl: bool, timeout: int,
                 token_scheme: str = "OpsToken"):
        self.base = base_url.rstrip("/")
        self.timeout = timeout
        self.token: str | None = None
        self.token_scheme = token_scheme
        if verify_ssl:
            self.ssl_ctx = ssl.create_default_context()
        else:
            self.ssl_ctx = ssl.create_default_context()
            self.ssl_ctx.check_hostname = False
            self.ssl_ctx.verify_mode = ssl.CERT_NONE

    def _request(self, method: str, path: str,
                 query: dict | None = None,
                 body: dict | None = None) -> dict:
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
            body={"username": username, "password": password, "authSource": auth_source},
        )
        token = result.get("token")
        if not token:
            raise RuntimeError(f"Auth response missing token: {result}")
        self.token = token
        log("[auth] OK")

    def list_adapter_kinds(self) -> list[dict]:
        return self._request("GET", "/suite-api/api/adapterkinds").get("adapter-kind", []) or []

    def list_resource_kinds(self, ak: str) -> list[dict]:
        return self._request(
            "GET",
            f"/suite-api/api/adapterkinds/{urllib.parse.quote(ak, safe='')}/resourcekinds",
        ).get("resource-kind", []) or []

    def list_statkeys(self, ak: str, rk: str) -> list[dict]:
        return self._request(
            "GET",
            f"/suite-api/api/adapterkinds/{urllib.parse.quote(ak, safe='')}"
            f"/resourcekinds/{urllib.parse.quote(rk, safe='')}/statkeys",
        ).get("resourceTypeAttributes", []) or []

    def list_resources(self, ak: str, rk: str, page_size: int = 25) -> list[dict]:
        # NB: the Suite API expects `adapterKind` / `resourceKind` — NOT the
        # `*Key` suffixed names. Using the wrong names silently returns the
        # unfiltered global resource list (page 0). Pre-2026-05-18 versions of
        # this script and `dell_relationship_audit.py` had that bug.
        return self._request(
            "GET",
            "/suite-api/api/resources",
            query={"adapterKind": ak, "resourceKind": rk, "pageSize": page_size},
        ).get("resourceList", []) or []

    def get_latest_stats(self, rid: str) -> list[dict]:
        result = self._request(
            "GET",
            f"/suite-api/api/resources/{urllib.parse.quote(rid, safe='')}/stats/latest",
        )
        values = result.get("values", []) or []
        out: list[dict] = []
        for v in values:
            stats = (v.get("stat-list") or {}).get("stat") or []
            for s in stats:
                out.append(s)
        return out


def find_adapter_kind(client: OpsClient, override: str | None, hint: str | None) -> dict:
    kinds = client.list_adapter_kinds()
    if override:
        for k in kinds:
            if k.get("key", "").lower() == override.lower() or k.get("name", "").lower() == override.lower():
                return k
        raise RuntimeError(f"adapter-kind override '{override}' not found on instance")

    if hint:
        candidates = [
            k for k in kinds
            if hint.lower() in k.get("key", "").lower() or hint.lower() in k.get("name", "").lower()
        ]
        if len(candidates) == 1:
            return candidates[0]
        if not candidates:
            raise RuntimeError(f"hint '{hint}' matched no adapter kinds")
        log(f"[warn] hint '{hint}' matched {len(candidates)} adapter kinds — choose one:")
        for c in candidates:
            log(f"         key={c.get('key')}  name={c.get('name')}")
        raise RuntimeError("ambiguous adapter kind")

    log("[adapterkinds] no --adapter-kind / --adapter-name-hint supplied; listing:")
    for k in kinds:
        log(f"  key={k.get('key')}  name={k.get('name')}  describeVer={k.get('describeVersion')}")
    raise RuntimeError("specify --adapter-kind <key> or --adapter-name-hint <substring>")


def categorize_statkey(key: str) -> dict:
    """Decompose a statkey path. The colon character separates an
    instance segment within a group (e.g. 'Hardware|Power:PS1|Output'),
    which is the wire form of describe.xml's instanced='true'.

    Returns:
      {
        'groups': ['Hardware', 'Power'],
        'instance': 'PS1',          # None if no colon present
        'attribute': 'Output',
        'has_instance': True,
      }
    """
    parts = key.split("|")
    leaf = parts[-1] if parts else key
    middle = parts[:-1]
    instance = None
    groups: list[str] = []
    for seg in middle:
        if ":" in seg:
            grp, inst = seg.split(":", 1)
            groups.append(grp)
            instance = inst  # last-wins; for nested instance groups (rare) capture last
        else:
            groups.append(seg)
    return {
        "groups": groups,
        "instance": instance,
        "attribute": leaf,
        "has_instance": instance is not None,
    }


def summarize_keys(keys: list[str], statkey_objects: list[dict] | None = None) -> dict:
    """Per-statkey decomposition + group-shape summary.

    The DECLARED `instanceType=INSTANCED` flag on each `resource-kind-attribute`
    (Suite API schema) is the authoritative signal that the attribute lives in
    an instanced ResourceGroup in describe.xml. The colon-segment in the key
    string only shows up in COLLECTED stats (the runtime substitutes the actual
    instance id at emit time), so a declared statkey list never has colons by
    itself — even for kinds that emit instanced data.

    If `statkey_objects` is provided (the raw items from `/statkeys`), we read
    `instanceType` directly. Otherwise we fall back to colon-detection (useful
    when keys come from /stats/latest which exposes the collected, instance-
    substituted form).
    """
    decoded = [{"key": k, **categorize_statkey(k)} for k in keys]
    if statkey_objects is not None:
        # Stitch instanceType onto each decoded entry.
        by_key = {(s.get("key") or ""): s for s in statkey_objects}
        instanced_count = 0
        for d in decoded:
            so = by_key.get(d["key"]) or {}
            d["instanceType"] = so.get("instanceType")
            d["declaredInstanced"] = (so.get("instanceType") == "INSTANCED")
            if d["declaredInstanced"]:
                instanced_count += 1
    else:
        instanced_count = sum(1 for d in decoded if d["has_instance"])
    # Also keep the wire-level colon evidence (useful on /stats/latest dumps).
    colon_count = sum(1 for d in decoded if d["has_instance"])
    group_shapes: Counter = Counter()
    for d in decoded:
        shape = "|".join(d["groups"]) + (":<inst>" if d["has_instance"] else "")
        group_shapes[shape] += 1
    return {
        "totalKeys": len(decoded),
        "instancedKeys": instanced_count,   # declared OR (fallback) colon-detected
        "colonInstanceKeys": colon_count,   # wire-level colon detections only
        "groupShapes": dict(group_shapes),
        "samples": decoded[:30],
    }


def audit_one_adapter(client: OpsClient, ak: dict, args) -> dict:
    """Pull statkey tree + (optional) live resource sample for one adapter kind.
    Returns the per-adapter dump structure that lands in the JSON output."""
    ak_key = ak["key"]
    banner(f"Adapter Kind: {ak_key}")
    log(f"key  = {ak_key}")
    log(f"name = {ak.get('name')}")
    log(f"describeVersion = {ak.get('describeVersion')}")
    log(f"adapterKindType = {ak.get('adapterKindType')}")

    kinds = client.list_resource_kinds(ak_key)
    log(f"declared resource kinds: {len(kinds)}")
    for rk in kinds:
        log(f"  - {rk.get('key')}  ({rk.get('name')})")

    log("")
    log("[statkeys]")
    per_kind: dict[str, dict] = {}
    for rk in kinds:
        rk_key = rk["key"]
        try:
            sks = client.list_statkeys(ak_key, rk_key)
        except RuntimeError as e:
            log(f"  ! {rk_key}: statkey fetch failed: {e}")
            per_kind[rk_key] = {"error": str(e)}
            continue
        key_strings = [s.get("key", "") for s in sks if s.get("key")]
        # Pass the full statkey objects so summarize_keys reads instanceType
        # directly rather than colon-splitting (which never fires on declared
        # statkeys — colons only show up on collected stats).
        summary = summarize_keys(key_strings, statkey_objects=sks)
        per_kind[rk_key] = {
            "kindName": rk.get("name"),
            **summary,
            "rawStatkeys": sks if args.raw else None,
        }
        verdict = "INSTANCED PRESENT" if summary["instancedKeys"] > 0 else "no instance markers"
        log(f"  * {rk_key}: {summary['totalKeys']} statkeys "
            f"({summary['instancedKeys']} declared instanced) — {verdict}")
        if summary["instancedKeys"] > 0:
            for shape, n in sorted(summary["groupShapes"].items(), key=lambda kv: -kv[1])[:6]:
                if ":<inst>" in shape:
                    log(f"      instanced shape: {shape}  ×{n}")

    live_samples: dict[str, list[dict]] = {}
    if args.sample > 0:
        log("")
        log("[live samples]")
        for rk in kinds:
            rk_key = rk["key"]
            try:
                resources = client.list_resources(ak_key, rk_key, page_size=args.sample)
            except RuntimeError as e:
                log(f"  ! {rk_key}: resource list failed: {e}")
                continue
            if not resources:
                continue
            rk_dump: list[dict] = []
            for r in resources[:args.sample]:
                rid = r.get("identifier")
                try:
                    stats = client.get_latest_stats(rid)
                except RuntimeError as e:
                    log(f"  ! {rk_key} / {rid}: stats fetch failed: {e}")
                    continue
                stat_keys = [
                    (s.get("statKey", {}).get("key", "") if isinstance(s.get("statKey"), dict)
                     else s.get("statKey", ""))
                    for s in stats
                ]
                stat_keys = [k for k in stat_keys if k]
                summary = summarize_keys(stat_keys)
                rk_dump.append({
                    "id": rid,
                    "name": (r.get("resourceKey") or {}).get("name"),
                    **summary,
                })
                log(f"  {rk_key}: {(r.get('resourceKey') or {}).get('name')} — "
                    f"{summary['totalKeys']} live keys ({summary['instancedKeys']} instanced)")
            live_samples[rk_key] = rk_dump

    return {
        "adapterKind": ak,
        "resourceKinds": kinds,
        "perKindStatkeys": per_kind,
        "liveResourceSamples": live_samples,
    }


def audit(args) -> int:
    client = OpsClient(args.url, verify_ssl=not args.insecure, timeout=args.timeout,
                       token_scheme=args.token_scheme)
    if args.token:
        client.token = args.token
        log("[auth] using --token (skipping acquire)")
    else:
        password = args.password or os.environ.get("VCFOPS_PASSWORD")
        if args.prompt_password or not password:
            password = getpass.getpass(f"Password for {args.user}@{args.url}: ")
        client.acquire_token(args.user, password, args.auth_source)

    # All-adapters mode: enumerate every adapter kind on the instance,
    # statkey trees only (skip live sampling by default — too expensive
    # across dozens of adapters). Useful when one instance hosts several
    # reference packs and you want them all in one JSON.
    if args.all_adapters:
        all_kinds = client.list_adapter_kinds()
        if args.all_adapters_filter:
            pat = re.compile(args.all_adapters_filter, re.IGNORECASE)
            all_kinds = [
                k for k in all_kinds
                if pat.search(k.get("key", "") or "") or pat.search(k.get("name", "") or "")
            ]
        log(f"[all-adapters] {len(all_kinds)} adapter kind(s) to audit "
            f"(filter={args.all_adapters_filter or '(none)'})")
        if args.sample > 0 and not args.all_adapters_with_live:
            log(f"[all-adapters] live-resource sampling disabled by default; "
                f"pass --all-adapters-with-live to enable.")
            args.sample = 0
        adapters_dump: list[dict] = []
        for ak in all_kinds:
            try:
                adapters_dump.append(audit_one_adapter(client, ak, args))
            except RuntimeError as e:
                log(f"  ! {ak.get('key')}: audit failed: {e}")
                adapters_dump.append({"adapterKind": ak, "error": str(e)})
        out_path = _resolve_output_path(args.output, args.url, "all_adapters")
        if out_path:
            dump = {
                "generatedAt": datetime.now(timezone.utc).isoformat(),
                "instance": args.url,
                "mode": "all-adapters",
                "filter": args.all_adapters_filter,
                "adapters": adapters_dump,
            }
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(dump, f, indent=2, default=str)
            log("")
            log(f"[output] full JSON dump written to {out_path}")
        banner("Verdict (all-adapters)")
        instanced_adapters = [
            a for a in adapters_dump
            if any(v.get("instancedKeys", 0) > 0 for v in (a.get("perKindStatkeys") or {}).values())
        ]
        log(f"adapters with instanced groups: {len(instanced_adapters)} / {len(adapters_dump)}")
        for a in instanced_adapters:
            log(f"  * {a['adapterKind'].get('key')}  ({a['adapterKind'].get('name')})")
        return 0

    # Single-adapter mode (original behavior).
    ak = find_adapter_kind(client, args.adapter_kind, args.adapter_name_hint)
    one = audit_one_adapter(client, ak, args)
    ak_key = ak["key"]
    kinds = one["resourceKinds"]
    per_kind = one["perKindStatkeys"]
    live_samples = one["liveResourceSamples"]

    out_path = _resolve_output_path(args.output, args.url, ak_key)

    if out_path:
        dump = {
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "instance": args.url,
            "adapterKind": ak,
            "resourceKinds": kinds,
            "perKindStatkeys": per_kind,
            "liveResourceSamples": live_samples,
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(dump, f, indent=2, default=str)
        log("")
        log(f"[output] full JSON dump written to {out_path}")

    banner("Verdict")
    any_instanced = any(
        v.get("instancedKeys", 0) > 0 for v in per_kind.values()
    )
    if any_instanced:
        log("INSTANCED groups detected — this adapter declares per-instance attribute")
        log("groups (the `Hardware|Power:PS1|Watts` colon-syntax). This is the")
        log("describe.xml shape Pattern A requires. Send the JSON back.")
    else:
        log("No instanced groups detected. All keys are flat group|attribute paths.")
        log("This adapter uses Pattern C (separate resource per sub-component).")
        log("Send the JSON back regardless — the absence is just as diagnostic.")
    return 0


def _resolve_output_path(output: str | None, url: str, slug_seed: str) -> str | None:
    """Auto-name JSON output when --output is given without a value."""
    if output != "__auto__":
        return output
    netloc = urllib.parse.urlparse(url).netloc or "ops"
    host_slug = re.sub(r"[^A-Za-z0-9]+", "_", netloc).strip("_") or "ops"
    ak_slug = re.sub(r"[^A-Za-z0-9]+", "_", slug_seed).strip("_") or "adapter"
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"mp_describe_recon_{host_slug}_{ak_slug}_{ts}.json"


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Read-only describe.xml shape recon for VCF Operations management packs."
    )
    p.add_argument("--url", required=True, help="Base URL")
    p.add_argument("--user", help="Username (required unless --token)")
    p.add_argument("--password", help="Password (prefer --prompt-password or $VCFOPS_PASSWORD)")
    p.add_argument("--prompt-password", action="store_true")
    p.add_argument("--auth-source", default="Local")
    p.add_argument("--token", help="Skip acquire and use an existing token")
    p.add_argument("--token-scheme", default="OpsToken", choices=["OpsToken", "vRealizeOpsToken"])
    p.add_argument("--adapter-kind", help="Exact adapter kind key (single-adapter mode)")
    p.add_argument("--adapter-name-hint", help="Substring fuzzy-match against adapterkinds list")
    p.add_argument("--all-adapters", action="store_true",
                   help="Enumerate every adapter kind on the instance. Captures statkey "
                        "trees only by default (no live sampling — too expensive at scale). "
                        "Use --all-adapters-filter to scope; --all-adapters-with-live to re-enable.")
    p.add_argument("--all-adapters-filter", metavar="REGEX",
                   help="Limit --all-adapters to adapter kinds whose key/name matches this regex.")
    p.add_argument("--all-adapters-with-live", action="store_true",
                   help="Allow live-resource sampling under --all-adapters (slower).")
    p.add_argument("--sample", type=int, default=2, help="Resources sampled per kind (default 2; 0 = skip)")
    p.add_argument("--raw", action="store_true", help="Include raw statkey objects in JSON dump")
    p.add_argument("--timeout", type=int, default=60)
    p.add_argument("--insecure", action="store_true")
    p.add_argument("--output", nargs="?", const="__auto__", default=None, metavar="PATH",
                   help="JSON dump path. --output alone auto-names; omit to skip.")
    args = p.parse_args(argv)
    if not args.token and not args.user:
        p.error("--user is required unless --token is supplied")
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

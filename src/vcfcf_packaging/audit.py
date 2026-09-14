"""Factory entry point to the build-time dependency audit (M2 row 3).

The offline half (``audit_bundle_dependencies``, ``analyze_staged_bundle``,
``print_audit_summary``, ``AuditError``, ``AuditResult``, the staged-bundle
parsers) lives in ``vcfcf_core.packaging.audit`` and takes an already-built
``DescribeCache``. This module keeps ``run_dependency_audit``: make the
factory's describe cache (its location and credentials), optionally
live-refresh the pairs the bundle references, then run the core audit and
merge the auto-added entries into the bundle in place.

Every other name resolves through module ``__getattr__`` to the identical
core object; to monkeypatch a name the running audit sees, patch
``vcfcf_core.packaging.audit``.
"""
from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Literal

from vcfcf_core.packaging import audit as _core
from vcfcf_core.packaging.audit import AuditError, AuditResult, audit_bundle_dependencies

if TYPE_CHECKING:
    from vcfcf_core.packaging.loader import Bundle


def run_dependency_audit(
    bundle: "Bundle",
    label: str,
    *,
    live_describe: bool,
    audit_mode: "Literal['auto', 'strict', 'lax']" = "auto",
    skip_audit: bool = False,
) -> "AuditResult | None":
    """Run the build-time dependency audit for ``bundle``, in place.

    Shared implementation for the "make/refresh a describe cache, optionally
    live-refresh the pairs this bundle references, run the audit, merge any
    auto-added entries into bundle.builtin_metric_enables" sequence that used
    to be duplicated near-verbatim in ``builder.build_bundle`` and
    ``discrete_builder.build_discrete`` (issue #77).

    Args:
        bundle:        The (real or synthetic) Bundle to audit.
        label:         Human-readable label for the --skip-audit warning
                       message (e.g. a bundle path or "dashboard 'Foo'").
        live_describe: If True and a live client is configured, refresh the
                       describe cache for every adapter/resource kind pair
                       this bundle references before auditing.
        audit_mode:    "auto" (default), "strict", or "lax", see
                       ``audit_bundle_dependencies``.
        skip_audit:    If True, skip the audit entirely (returns None).

    Returns:
        The ``AuditResult``, or ``None`` if ``skip_audit`` is True. Callers
        are responsible for calling ``print_audit_summary`` themselves (the
        two call sites print it at slightly different points relative to the
        zip build) and for handling ``AuditError`` raised by
        ``audit_bundle_dependencies``.
    """
    if skip_audit:
        print(
            f"  WARN: --skip-audit is set; dependency audit skipped for {label}. "
            "Metric references will NOT be validated.",
            file=sys.stderr,
        )
        return None

    from .describe import make_cache, DescribeCacheError

    describe_cache = make_cache(live=live_describe)

    if live_describe and getattr(describe_cache, "_client", None) is not None:
        from vcfcf_core.packaging.deps import extract_metric_references

        refs = extract_metric_references(bundle)
        pairs_needed: set[tuple[str, str]] = {
            (r.adapter_kind, r.resource_kind) for r in refs
        }
        for ak, rk in sorted(pairs_needed):
            try:
                describe_cache.refresh(ak, rk)
            except DescribeCacheError as exc:
                print(
                    f"  WARN: could not refresh describe cache for {ak}/{rk}: {exc}",
                    file=sys.stderr,
                )

    audit_result = audit_bundle_dependencies(bundle, describe_cache, mode=audit_mode)

    if audit_result.auto_added:
        bundle.builtin_metric_enables = list(bundle.builtin_metric_enables) + audit_result.auto_added

    return audit_result


def __getattr__(name: str):
    """Every name this module does not define itself resolves to core."""
    try:
        return getattr(_core, name)
    except AttributeError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None

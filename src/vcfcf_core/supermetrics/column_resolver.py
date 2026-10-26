"""Resolve ``supermetric:"<name>"`` view columns to one super metric, scoped
to the content set the view belongs to (issues #270 and #266).

A view column may name a super metric by display name. Display names are
unique within a content set (the factory's ``content/``, one third-party
project, one SDK-adapter pak) but not across sets: a third-party project
may ship an SM whose name matches a factory one. A flat ``{name: uuid}`` map
cannot tell those apart, so the column bound to whichever was loaded, or
failed when the view's own set was not in the map at all.

The rule (#270):

1. the view's own content set first;
2. then the fallback set (``"factory"`` by default), when it is a different
   set and the view's own set is not isolated (``isolated``): a third-party
   view may name a factory SM; the factory isolates SDK-adapter paks, whose
   build ships only the pak's own SMs;
3. otherwise the name is unresolved.

Two different SMs (different ids) sharing the name inside the set that
answers is ambiguous and raises :class:`SmColumnResolutionError`; it never
picks one. The same SM loaded twice (same id) is one candidate. A set whose
SM YAML could not be loaded (``broken_sets``) also raises when the search
reaches it, rather than falling through to the next set: a third-party
project whose SMs failed to load must not quietly bind to a same-named
factory SM.

The content set of an object is ``set_of(obj)``; the default is its
``provenance`` (``"factory"``, a third-party slug, or ``""``). The factory
passes a key that also tells SDK-adapter paks apart (by provenance alone a
pak's files read as ``"factory"`` or ``""``, the same for every pak); this
module knows nothing about the repo layout.

Every :class:`SmColumnResolutionError` carries a ``kind``: ``"ambiguous"``,
``"broken"`` (a set that did not load), ``"unusable"`` (resolves, but must
not be rendered, e.g. no id yet); :meth:`SmColumnResolver.column_problems`
adds ``"unresolved"``. Callers grade by kind (validate warns on
``"unusable"``, everything else is an error).

Every consumer resolves through one instance, so they cannot disagree: the
renderer (:meth:`SmColumnResolver.uuid_for`, passed as ``sm_resolver``),
the sync preflight and the post-import walker
(:meth:`SmColumnResolver.resolve`).
"""
from __future__ import annotations

import re
from typing import Callable, Dict, Iterable, List, Mapping, Optional

# Same shapes as vcfcf_core.dashboards.render (_SM_COLUMN_PREFIX_RE /
# _SM_COLUMN_REF_RE): token case-insensitive, optional ``@``, name exact.
# Kept here so this module does not import the renderer; a test pins them
# equal.
SM_COLUMN_PREFIX_RE = re.compile(r"(?i:@?supermetric)\s*:")
SM_COLUMN_REF_RE = re.compile(r'''(?i:@?supermetric):["'](.+?)["']$''')

DEFAULT_FALLBACK_SET = "factory"


class SmColumnResolutionError(ValueError):
    """A ``supermetric:"<name>"`` column cannot be bound to exactly one SM.

    ``kind`` is ``"ambiguous"``, ``"broken"`` or ``"unusable"`` (see the
    module docstring)."""

    def __init__(self, message: str, kind: str = "ambiguous") -> None:
        super().__init__(message)
        self.kind = kind


def column_sm_name(attribute: str) -> Optional[str]:
    """The SM display name a well-formed name-form column attribute names,
    else None (a plain metric, an ``sm_<uuid>`` key, or a malformed token)."""
    m = SM_COLUMN_REF_RE.match((attribute or "").strip())
    return m.group(1) if m else None


def _default_set_of(obj) -> str:
    return getattr(obj, "provenance", "") or ""


def _set_label(key: str) -> str:
    return repr(key) if key else "(no content set)"


def _where(sm) -> str:
    return str(getattr(sm, "source_path", None) or getattr(sm, "id", "") or sm.name)


class SmColumnResolver:
    """Name to SM resolution for view columns, scoped by content set.

    Args:
        supermetrics: every SM a column may resolve to (``SuperMetricDef`` or
            anything with ``id``, ``name`` and the attribute ``set_of`` reads).
        set_of: content-set key of an SM or a view; default ``provenance``.
        fallback_set: the set tried after the view's own; None disables the
            fallback.
        unusable: ``{lowercased id: reason}`` for SMs that resolve but must
            not be rendered (for example one loaded with an in-memory stand-in
            id because its YAML has none yet): :meth:`uuid_for` raises with
            the reason instead of emitting an id the instance does not know.
        broken_sets: ``{set key: reason}`` for content sets whose SM YAML did
            not load; a search that reaches one raises with the reason.
        isolated: ``(set key) -> bool``; a view whose own set is isolated
            never falls back (default: no set is isolated).
    """

    def __init__(
        self,
        supermetrics: Iterable,
        set_of: Optional[Callable[[object], str]] = None,
        fallback_set: Optional[str] = DEFAULT_FALLBACK_SET,
        unusable: Optional[Mapping[str, str]] = None,
        broken_sets: Optional[Mapping[str, str]] = None,
        isolated: Optional[Callable[[str], bool]] = None,
    ) -> None:
        self._set_of = set_of or _default_set_of
        self._broken = dict(broken_sets or {})
        self._isolated = isolated or (lambda key: False)
        self._fallback = fallback_set
        self._unusable = {k.lower(): v for k, v in (unusable or {}).items()}
        # {(set, name): [sm, ...]} distinct by id, load order kept.
        self._by_set_name: Dict[tuple, List] = {}
        for sm in supermetrics:
            if not getattr(sm, "name", ""):
                continue
            key = (self._set_of(sm), sm.name)
            bucket = self._by_set_name.setdefault(key, [])
            sid = (getattr(sm, "id", "") or "").lower()
            if sid and any((getattr(o, "id", "") or "").lower() == sid for o in bucket):
                continue
            bucket.append(sm)

    def set_of(self, obj) -> str:
        return self._set_of(obj)

    def _sets_for(self, view) -> List[str]:
        own = self._set_of(view)
        order = [own]
        if (self._fallback is not None and self._fallback != own
                and not self._isolated(own)):
            order.append(self._fallback)
        return order

    def resolve(self, view, name: str):
        """The SM ``name`` means in a column of ``view``, or None when no set
        in reach defines it. Raises :class:`SmColumnResolutionError` when the
        set that defines it holds more than one SM of that name."""
        for key in self._sets_for(view):
            if key in self._broken:
                raise SmColumnResolutionError(
                    f'view "{getattr(view, "name", "?")}" names super metric '
                    f'"{name}", which cannot be resolved: the super metric '
                    f"YAML of content set {_set_label(key)} did not load "
                    f"({self._broken[key]})",
                    kind="broken",
                )
            cands = self._by_set_name.get((key, name), [])
            if len(cands) == 1:
                return cands[0]
            if len(cands) > 1:
                where = "; ".join(_where(sm) for sm in cands)
                raise SmColumnResolutionError(
                    f'view "{getattr(view, "name", "?")}" names super metric '
                    f'"{name}", which is ambiguous: {len(cands)} super metrics '
                    f"in content set {_set_label(key)} share that display name "
                    f"({where}). Rename one; a display name must be unique "
                    f"within its content set."
                )
        return None

    def uuid_for(self, view, name: str) -> Optional[str]:
        """The renderer's ``sm_resolver``: the resolved SM's id, or None when
        unresolved (the renderer raises its own error). Raises
        :class:`SmColumnResolutionError` on ambiguity or an unusable SM."""
        sm = self.resolve(view, name)
        if sm is None:
            return None
        sid = getattr(sm, "id", "") or ""
        reason = self._unusable.get(sid.lower())
        if reason or not sid:
            raise SmColumnResolutionError(
                f'view "{getattr(view, "name", "?")}" names super metric '
                f'"{name}" ({_where(sm)}), which cannot be rendered: '
                f"{reason or 'it has no id'}",
                kind="unusable",
            )
        return sid

    def describe_scope(self, view) -> str:
        """The sets searched for ``view``, for an unresolved-name message."""
        return " then ".join(_set_label(k) for k in self._sets_for(view))

    def column_errors(self, views: Iterable) -> List[str]:
        """One message per name-form column of ``views`` that does not bind
        to exactly one renderable SM. Empty means every such column resolves
        the way the renderer will resolve it."""
        return [msg for _kind, msg in self.column_problems(views)]

    def column_problems(self, views: Iterable) -> List[tuple]:
        """``(kind, message)`` per name-form column of ``views`` that does not
        bind to exactly one renderable SM; ``kind`` is ``"unresolved"`` or the
        :class:`SmColumnResolutionError` kind."""
        errors: List[tuple] = []
        for view in views:
            for col in getattr(view, "columns", None) or []:
                name = column_sm_name(getattr(col, "attribute", "") or "")
                if name is None:
                    continue
                where = (
                    f'view "{getattr(view, "name", "?")}" column '
                    f'"{getattr(col, "display_name", "")}"'
                )
                try:
                    uid = self.uuid_for(view, name)
                except SmColumnResolutionError as exc:
                    errors.append((exc.kind, f"{where}: {exc}"))
                    continue
                if uid is None:
                    errors.append(("unresolved",
                        f'{where} names super metric "{name}", which is in no '
                        f"loaded super metric YAML of content set "
                        f"{self.describe_scope(view)}"
                    ))
        return errors

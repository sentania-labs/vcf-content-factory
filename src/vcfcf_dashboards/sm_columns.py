"""The factory's super metric corpus for ``supermetric:"<name>"`` view
columns (issues #270 and #266).

``vcfcf_core.supermetrics.column_resolver.SmColumnResolver`` binds a column
to the SM of the view's own content set, then the factory's. This module
supplies the factory-layout half the core may not know:

- which content set a file belongs to (:func:`content_set_of`): the
  factory's ``content/``, one ``third_party/<slug>/`` project, or one
  ``content/sdk-adapters/<name>/`` pak. Provenance cannot tell paks apart:
  a pak repo has its own ``content/`` child, so the provenance root sniff
  stops at the pak and its files read as ``""`` (``"factory"`` for a pak
  without one), the same for every pak. The path tells them apart;
- pak isolation: a pak view never falls back to a factory SM, matching
  ``build-sdk`` / ``validate-sdk``, whose scope is the pak's bundled SMs
  only (a pak ships nothing else);
- the corpus: the SM YAML under a primary directory (``--supermetrics-dir``,
  default ``content/supermetrics``), ``content/supermetrics``, every
  ``third_party/*/supermetrics`` and every
  ``content/sdk-adapters/*/supermetrics``, relative to the working
  directory like the rest of the dashboards CLI;
- read-only loading: an id-less YAML is never given a minted id. It gets an
  in-memory stand-in so its formula can still be checked, and the resolver
  marks it unusable, so a column naming it fails loudly instead of shipping
  an id the instance has never seen.

The same corpus and resolver feed the renderer (``build_import_zip``'s
``sm_resolver``), the pre-import referent check and the post-import walker,
so the three cannot disagree about which SM a column means.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Dict, List, Optional, Tuple

from vcfcf_core.supermetrics.column_resolver import SmColumnResolver

DEFAULT_SUPERMETRICS = Path("content/supermetrics")
SDK_ADAPTERS = Path("content/sdk-adapters")
THIRD_PARTY = Path("third_party")


def content_set_of(obj) -> str:
    """Content-set key of a loaded SM or view.

    ``"sdk-adapter:<name>"`` for a file under ``content/sdk-adapters/<name>/``,
    otherwise the object's ``provenance`` (``"factory"``, a third-party slug,
    or ``""`` for an object with no known place).

    The path as given (made absolute, symlinks kept) is checked first, then
    the symlink-resolved path: a pak symlinked into
    ``content/sdk-adapters/<name>`` from elsewhere keeps its key.
    """
    src = getattr(obj, "source_path", None)
    if src:
        candidates = [Path(src).absolute().parts]
        try:
            candidates.append(Path(src).resolve().parts)
        except OSError:
            pass
        for parts in candidates:
            key = _pak_key(parts)
            if key:
                return key
    return getattr(obj, "provenance", "") or ""


def _pak_key(parts) -> str:
    for i in range(len(parts) - 3, -1, -1):
        if parts[i] == "content" and parts[i + 1] == "sdk-adapters":
            return f"sdk-adapter:{parts[i + 2]}"
    return ""


def is_pak_set(key: str) -> bool:
    """A pak's content set: isolated, no fallback to the factory set."""
    return key.startswith("sdk-adapter:")


def load_sm_dir_readonly(directory) -> Tuple[list, str, List[str]]:
    """Load the SM YAML under ``directory`` without writing.

    Returns ``(defs, error, idless)``: an absent directory is
    ``([], "", [])``, a load failure ``([], message, [])``; ``idless`` lists
    the stand-in ids given to YAML that has no ``id`` yet. Loaded without the
    framework-prefix rule (a validate gate, RULE-006, not a sync gate).
    """
    sm_dir = Path(directory)
    if not sm_dir.exists():
        return [], "", []
    idless: List[str] = []
    try:
        from vcfcf_core.supermetrics import loader as _core
        from vcfcf_supermetrics.loader import _preview_id, _provenance_of

        def _stand_in(path: Path) -> str:
            sid = _preview_id(path)
            idless.append(sid)
            return sid

        defs = _core.load_dir(
            sm_dir, enforce_framework_prefix=False,
            on_missing_id=_stand_in, provenance_of=_provenance_of,
        )
        return defs, "", idless
    except Exception as e:  # noqa: BLE001  caller decides how loud to be
        return [], str(e), []


def sm_corpus_dirs(primary) -> List[Path]:
    """The SM directories besides ``primary`` that a column may resolve to:
    ``content/supermetrics`` (when ``primary`` points elsewhere), every
    ``third_party/*/supermetrics`` and every
    ``content/sdk-adapters/*/supermetrics`` that exists, de-duplicated."""
    candidates = [DEFAULT_SUPERMETRICS]
    for root in (THIRD_PARTY, SDK_ADAPTERS):
        if root.is_dir():
            candidates.extend(proj / "supermetrics" for proj in sorted(root.iterdir()))
    seen = {Path(primary).resolve()}
    dirs: List[Path] = []
    for d in candidates:
        if d.is_dir() and d.resolve() not in seen:
            seen.add(d.resolve())
            dirs.append(d)
    return dirs


@dataclass
class SmCorpus:
    """Every SM a view column may name, and what failed to load."""
    defs: list = field(default_factory=list)
    primary_dir: str = str(DEFAULT_SUPERMETRICS)
    primary_error: str = ""
    extra_errors: List[Tuple[Path, str]] = field(default_factory=list)
    idless: Dict[str, str] = field(default_factory=dict)
    broken_sets: Dict[str, str] = field(default_factory=dict)
    _resolver: Optional[SmColumnResolver] = field(default=None, repr=False, compare=False)

    def resolver(self) -> SmColumnResolver:
        """The one resolver over this corpus (built once, then shared by the
        column check, the renderer, the referent check and the walker)."""
        if self._resolver is None:
            self._resolver = SmColumnResolver(
                self.defs, set_of=content_set_of, unusable=self.idless,
                broken_sets=self.broken_sets, isolated=is_pak_set,
            )
        return self._resolver


def load_sm_corpus(primary=DEFAULT_SUPERMETRICS) -> SmCorpus:
    """Load the column corpus read-only (see the module docstring)."""
    corpus = SmCorpus(primary_dir=str(primary))
    _NO_ID = (
        "its YAML has no id yet; run `python3 -m vcfcf_supermetrics validate` "
        "(or validate its project) to mint one, then sync"
    )
    defs, err, idless = load_sm_dir_readonly(primary)
    corpus.primary_error = err
    if err:
        corpus.broken_sets[_dir_set(primary)] = f"{primary}: {err}"
    corpus.defs.extend(defs)
    corpus.idless.update({i: _NO_ID for i in idless})
    for extra in sm_corpus_dirs(primary):
        more, extra_err, more_idless = load_sm_dir_readonly(extra)
        if extra_err:
            corpus.extra_errors.append((extra, extra_err))
            corpus.broken_sets[_dir_set(extra)] = f"{extra}: {extra_err}"
        corpus.defs.extend(more)
        corpus.idless.update({i: _NO_ID for i in more_idless})
    return corpus


def _dir_set(directory) -> str:
    """Content-set key of the SMs an SM directory holds."""
    from vcfcf_common.provenance import provenance_from_path

    probe = Path(directory) / "_.yaml"
    return content_set_of(SimpleNamespace(
        source_path=probe, provenance=provenance_from_path(probe)))


def column_errors(views, corpus: Optional[SmCorpus] = None) -> List[Tuple[str, str]]:
    """``(kind, message)`` for every ``supermetric:"<name>"`` column of
    ``views`` that does not bind to exactly one renderable SM of the corpus;
    empty when all do. ``kind`` is ``"unresolved"``, ``"ambiguous"``,
    ``"broken"`` (its set's SM YAML did not load) or ``"unusable"`` (the SM
    has no id yet)."""
    corpus = corpus if corpus is not None else load_sm_corpus()
    return corpus.resolver().column_problems(views)

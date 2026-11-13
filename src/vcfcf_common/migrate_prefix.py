"""``python3 -m vcfcf_common migrate-prefix``: rewrite the retired content prefix.

Factory content names moved from ``[VCF Content Factory] `` to ``[VCF CF] ``
on 2026-11-12 (``vcfcf_core.naming``). The loaders reject the old spelling,
so a checkout that still carries it stops validating until this command
has run over it. It rewrites the bracketed label, as text, in the files that
hold content names and by-name references, which keeps comments, quoting
and key order exactly as they were:

- display names (``name:``) and every by-name reference: ``supermetric:"<name>"``
  view columns, ``@supermetric:"<name>"`` formulas, ``view:`` / ``dashboard:``
  references in dashboards, reports and navigations, ``customgroup:``,
  symptom and recommendation references in alerts, and prose in
  ``description:`` blocks that names other content;
- bundle and release manifests under ``bundles/``.

Ids are never touched (they contain no prefix; every rewritten YAML file is
re-parsed and must equal the original with only its strings rewritten), and
``[VCF Content Factory](https://...)`` Markdown links are kept.

Layouts, picked from ``ROOT`` (default: the current directory):

- **factory checkout**: YAML under ``content/`` (except
  ``content/sdk-adapters/``, each an independent pak repo that is migrated on
  its own), ``third_party/`` (except ``debug/`` captures) and ``bundles/``.
  Nothing else in the tree is read, so historical records (investigations,
  reviews, designs, changelogs, recon logs) stay as written even when the
  command is pointed at the repo root.
- **pak repo** (``ROOT/adapter.yaml`` exists, either a standalone pak
  checkout or ``content/sdk-adapters/<name>/``): its YAML (``adapter.yaml``
  and the bundled content), ``README.md`` / ``REFERENCE.md`` at the root,
  ``docs/**/*.md``, ``tests/**/*.py``, any ``describe.xml`` and
  ``*.properties``. ``CHANGELOG*`` and release notes are history and are
  never rewritten.

It refuses to write into a git tree with uncommitted changes unless
``--force`` is given (``--dry-run`` writes nothing and skips the check), and
running it twice changes nothing the second time.
"""
from __future__ import annotations

import argparse
import difflib
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

import yaml

from vcfcf_core.naming import (
    CLEANUP_COMMAND,
    FACTORY_PREFIX_LABEL,
    LEGACY_FACTORY_PREFIX_LABEL,
    rewrite_legacy_prefix,
)

#: Directory names never descended into, in either layout.
_SKIP_DIRS = frozenset({
    ".git", ".github", ".venv", "venv", "node_modules", "__pycache__",
    "build", "dist", "target", "out", ".pytest_cache",
})

#: Factory roots and the file suffixes read under each.
_FACTORY_ROOTS = ("content", "third_party", "bundles")
_YAML_SUFFIXES = frozenset({".yaml", ".yml"})

#: Content-type directory names, for the per-type counts.
_CONTENT_TYPES = (
    "supermetrics", "views", "dashboards", "customgroups", "symptoms",
    "alerts", "recommendations", "reports", "managementpacks",
)


def _is_history(path: Path) -> bool:
    """CHANGELOG and release-notes files record the past: never rewritten."""
    stem = path.name.lower()
    return stem.startswith("changelog") or "release-notes" in stem or "release_notes" in stem


@dataclass
class FileChange:
    path: Path
    count: int
    new_text: str
    lines: List[tuple] = field(default_factory=list)  # (lineno, old, new)
    name_renamed: bool = False
    kind: str = "other"


@dataclass
class Plan:
    root: Path
    layout: str  # "factory" | "pak"
    changes: List[FileChange] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    untouched: List[tuple] = field(default_factory=list)  # (path, count) left as is
    pak_dirs: List[Path] = field(default_factory=list)


def detect_layout(root: Path) -> Optional[str]:
    if (root / "adapter.yaml").is_file():
        return "pak"
    if any((root / r).is_dir() for r in _FACTORY_ROOTS):
        return "factory"
    return None


def _walk(base: Path, skip_extra: Iterable[str] = ()) -> Iterable[Path]:
    skip = _SKIP_DIRS | set(skip_extra)
    if not base.is_dir():
        return
    stack = [base]
    while stack:
        d = stack.pop()
        try:
            entries = sorted(d.iterdir())
        except OSError:
            continue
        for e in entries:
            if e.is_dir():
                if e.name not in skip and not e.is_symlink():
                    stack.append(e)
            elif e.is_file():
                yield e


def _factory_files(root: Path, plan: Plan) -> Iterable[Path]:
    content = root / "content"
    sdk = content / "sdk-adapters"
    if sdk.is_dir():
        plan.pak_dirs = sorted(p for p in sdk.iterdir() if (p / "adapter.yaml").is_file())
    for r in _FACTORY_ROOTS:
        base = root / r
        skip = {"debug"} if r == "third_party" else ({"sdk-adapters"} if r == "content" else set())
        for p in _walk(base, skip):
            if p.suffix.lower() in _YAML_SUFFIXES and not _is_history(p):
                yield p
            else:
                _note_untouched(p, plan)


def _pak_file_selected(root: Path, p: Path) -> bool:
    if _is_history(p):
        return False
    rel = p.relative_to(root)
    top = rel.parts[0] if len(rel.parts) > 1 else ""
    suffix = p.suffix.lower()
    if suffix in _YAML_SUFFIXES:
        return True
    if p.name == "describe.xml" or suffix == ".properties":
        return True
    if suffix == ".md":
        return (len(rel.parts) == 1 and p.name in ("README.md", "REFERENCE.md")) or top == "docs"
    if suffix == ".py":
        return top == "tests"
    return False


def _pak_files(root: Path, plan: Plan) -> Iterable[Path]:
    for p in _walk(root):
        if _pak_file_selected(root, p):
            yield p
        else:
            _note_untouched(p, plan)


def _note_untouched(p: Path, plan: Plan) -> None:
    """Record a file outside the rewrite set that still mentions the label."""
    try:
        text = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return
    n = text.count(LEGACY_FACTORY_PREFIX_LABEL)
    if n:
        plan.untouched.append((p, n))


def _deep_rewrite(obj):
    if isinstance(obj, str):
        return rewrite_legacy_prefix(obj)[0]
    if isinstance(obj, list):
        return [_deep_rewrite(x) for x in obj]
    if isinstance(obj, dict):
        return {_deep_rewrite(k): _deep_rewrite(v) for k, v in obj.items()}
    return obj


def _kind_of(root: Path, p: Path, layout: str) -> str:
    rel = p.relative_to(root).parts
    if layout == "factory":
        if rel[0] == "bundles":
            return "bundles"
        for part in rel[1:-1]:
            if part in _CONTENT_TYPES:
                return part
        return rel[0]
    if p.name == "adapter.yaml" and len(rel) == 1:
        return "adapter.yaml"
    for part in rel[:-1]:
        if part in _CONTENT_TYPES:
            return part
    return rel[0] if len(rel) > 1 else p.name


def _plan_file(root: Path, p: Path, layout: str, plan: Plan) -> None:
    try:
        text = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return
    new_text, count = rewrite_legacy_prefix(text)
    if not count:
        if LEGACY_FACTORY_PREFIX_LABEL in text:
            # Only Markdown links remain: not names, left as is.
            plan.untouched.append((p, text.count(LEGACY_FACTORY_PREFIX_LABEL)))
        return
    change = FileChange(path=p, count=count, new_text=new_text, kind=_kind_of(root, p, layout))
    if p.suffix.lower() in _YAML_SUFFIXES:
        try:
            before = yaml.safe_load(text)
            after = yaml.safe_load(new_text)
        except yaml.YAMLError as e:
            plan.errors.append(f"{p}: not rewritten, the YAML does not parse: {e}")
            return
        if after != _deep_rewrite(before):
            plan.errors.append(
                f"{p}: not rewritten, the rewrite would change more than string "
                f"values (report this as a bug)"
            )
            return
        if isinstance(before, dict) and isinstance(before.get("name"), str):
            change.name_renamed = before["name"] != after.get("name")
    old_lines = text.splitlines()
    new_lines = new_text.splitlines()
    # SequenceMatcher, not zip: a label wrapped across two lines is joined
    # onto one, so the line counts can differ.
    sm = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag != "equal":
            change.lines.append((i1 + 1, "\n".join(old_lines[i1:i2]), "\n".join(new_lines[j1:j2])))
    plan.changes.append(change)


def build_plan(root: Path) -> Plan:
    """Everything the command would rewrite under *root*, without writing."""
    root = root.resolve()
    layout = detect_layout(root)
    if layout is None:
        raise ValueError(
            f"{root}: neither a factory checkout (no content/, third_party/ or "
            f"bundles/) nor a pak repo (no adapter.yaml)"
        )
    plan = Plan(root=root, layout=layout)
    files = _factory_files(root, plan) if layout == "factory" else _pak_files(root, plan)
    for p in files:
        _plan_file(root, p, layout, plan)
    return plan


def apply_plan(plan: Plan) -> None:
    for c in plan.changes:
        c.path.write_text(c.new_text, encoding="utf-8")


def dirty_state(root: Path) -> Optional[str]:
    """None when *root* is in a clean git tree, else a reason it is not known clean."""
    try:
        r = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain"],
            capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as e:
        return f"git status could not run ({e})"
    if r.returncode != 0:
        return f"not a git working tree ({r.stderr.strip() or 'git status failed'})"
    if r.stdout.strip():
        n = len(r.stdout.strip().splitlines())
        return f"the tree has {n} uncommitted change(s)"
    return None


def summarize(plan: Plan) -> dict:
    """Per-kind counts: files, names renamed, other occurrences rewritten."""
    out: dict = {}
    for c in plan.changes:
        row = out.setdefault(c.kind, {"files": 0, "names": 0, "references": 0})
        row["files"] += 1
        row["names"] += 1 if c.name_renamed else 0
        row["references"] += c.count - (1 if c.name_renamed else 0)
    return out


def _rel(plan: Plan, p: Path) -> str:
    try:
        return str(p.relative_to(plan.root))
    except ValueError:
        return str(p)


def print_plan(plan: Plan, dry_run: bool, out=None) -> None:
    out = out or sys.stdout
    verb = "would rewrite" if dry_run else "rewrote"
    print(f"migrate-prefix: {plan.layout} layout at {plan.root}", file=out)
    print(f'  "{LEGACY_FACTORY_PREFIX_LABEL}" -> "{FACTORY_PREFIX_LABEL}"', file=out)
    for c in plan.changes:
        print(f"  {verb} {_rel(plan, c.path)} ({c.count})", file=out)
        if dry_run:
            for lineno, a, b in c.lines:
                for line in a.splitlines():
                    print(f"      {lineno}: - {line.strip()}", file=out)
                for line in b.splitlines():
                    print(f"      {lineno}: + {line.strip()}", file=out)
    counts = summarize(plan)
    total = sum(c.count for c in plan.changes)
    print(f"  total: {total} occurrence(s) in {len(plan.changes)} file(s)", file=out)
    for kind in sorted(counts):
        row = counts[kind]
        print(f"    {kind}: {row['files']} file(s), {row['names']} name(s) renamed, "
              f"{row['references']} reference/prose occurrence(s)", file=out)
    for p, n in plan.untouched:
        print(f"  left as is: {_rel(plan, p)} ({n}; history, a Markdown link, or "
              f"outside the rewrite set)", file=out)
    for d in plan.pak_dirs:
        print(f"  pak repo not migrated here (its own repo): run "
              f"`python3 -m vcfcf_common migrate-prefix {_rel(plan, d)}`", file=out)
    for e in plan.errors:
        print(f"  ERROR: {e}", file=out)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python3 -m vcfcf_common migrate-prefix",
        description=(
            f'Rewrite the retired "{LEGACY_FACTORY_PREFIX_LABEL}" content-name '
            f'prefix to "{FACTORY_PREFIX_LABEL}" in content names and by-name '
            f"references (factory checkout or pak repo)."
        ),
    )
    ap.add_argument("root", nargs="?", default=".",
                    help="factory checkout or pak repo root (default: .)")
    ap.add_argument("--dry-run", action="store_true",
                    help="list every change, write nothing")
    ap.add_argument("--force", action="store_true",
                    help="write even when the git tree has uncommitted changes")
    args = ap.parse_args(list(argv) if argv is not None else None)

    root = Path(args.root)
    try:
        plan = build_plan(root)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    if not args.dry_run and plan.changes and not args.force:
        reason = dirty_state(plan.root)
        if reason:
            print(f"REFUSED: {reason}. The rewrite should land as its own reviewable diff: commit first, "
                  f"or pass --force.", file=sys.stderr)
            return 1

    print_plan(plan, args.dry_run)
    if plan.errors:
        print("Nothing written: fix the errors above first.", file=sys.stderr)
        return 1
    if args.dry_run:
        return 0
    if not plan.changes:
        print("Nothing to migrate.")
        return 0
    apply_plan(plan)
    print("Next: run the validation chain, sync the renamed content, then remove "
          f"the old-named copies the sync left behind with `{CLEANUP_COMMAND}` "
          f"(dry run by default).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Preflight doctor for the VCF Content Factory (bootstrap-v2 Phase 1/1b).

Invoked by the SessionStart hook by file path, i.e.
``python3 "$CLAUDE_PROJECT_DIR/src/vcfops_common/doctor.py"`` (the
``python -m vcfops_common doctor`` form also works, but depends on an
ambient PYTHONPATH=src, which the hook cannot assume).
Pure stdlib (yaml/requests/jmespath are only *checked* for importability,
never imported). No bash: git is invoked directly via subprocess so the
doctor works on native Windows. pathlib throughout; the repo root is
anchored to this module's location, never to Path.cwd() (issue #76).

Report-by-exception: one green line when everything is fine, deltas only
otherwise. Always exits 0; the output is informational for the hook.

Sections:
  - Upstream alignment (ELI5 summary of incoming commits, grouped by area).
  - Ahead-commit classification: core vs environment/state vs mixed.
    Report only; nothing is pulled or pushed, ever.
  - Credential readiness per the VCFOPS_<PROFILE>_* scheme in _env.py.
    Prints profile names and missing VAR NAMES only, never values (RULE-008).
  - Environment sanity: python >= 3.9, requests/yaml/jmespath importable,
    MPB runtime JARs present (warn, not fail).
  - Bootstrap health: surfaces the `.bootstrap-status` summary lines the
    bootstrap scripts write (see BOOTSTRAP_STATUS_CONTRACT below).
  - Concierge first-run (Phase 1b): unconfigured clone => greeting line +
    machine-readable CHECKLIST-JSON block for the orchestrator.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Constants and contracts
# ---------------------------------------------------------------------------

GREETING = (
    "Hello, it looks like this is an unconfigured copy of the "
    "VCF Content Factory. Do you want me to get it ready for you?"
)

# Contract for scripts/bootstrap_references.sh and
# scripts/bootstrap_managed_paks.sh (orchestrator-owned): after each run,
# each script REPLACES its own line in `.bootstrap-status` at repo root
# (filter out any line naming itself, write its fresh line, move into
# place), so the file holds at most one line per script and no script can
# evict another's. Line format:
#
#   <iso8601-utc> <script-name> cloned=<n> updated=<n> failed=<n> failures=<comma-list-or-->
#
# e.g.  2026-08-20T14:03:11Z bootstrap_references cloned=2 updated=1 failed=1 failures=dell-emc-mp
#
# The doctor takes the LAST line per script name, which is robust to a
# hand-edited or legacy append-style file as well. BOTH scripts in
# KNOWN_BOOTSTRAP_SCRIPTS must have a line: a script that dies before its
# status write (hook timeout, missing registry) leaves none, and the
# other script's clean record must not cover for it, so a missing record
# (or a missing file) is its own delta.
# Field 1 (the timestamp) is parsed: the SessionStart hook runs both
# bootstrap scripts and then the doctor sequentially in one composite
# command, so data older than STALE_AFTER_HOURS means a script did not
# run at all (it failed, hit its per-script timeout, or the checkout is
# read-only) and the doctor says so. Timestamps must be ISO8601 UTC
# (trailing `Z` accepted); an unparseable one degrades to an "age
# unknown" line, never a crash.
BOOTSTRAP_STATUS_FILE = ".bootstrap-status"

# Both scripts must have a line before bootstrap health counts as good.
KNOWN_BOOTSTRAP_SCRIPTS: Tuple[str, ...] = (
    "bootstrap_references",
    "bootstrap_managed_paks",
)

# Paths that are environment/state: local by nature, never PR-nudged.
# Everything NOT matching this list is classified core (portable and a
# PR candidate). Keep this list small and specific.
# Note: knowledge/context/reviews/ is deliberately NOT here: review
# reports are committed alongside framework PRs by convention, so they
# are core (PR candidates), not local state.
LOCAL_STATE_PREFIXES: Tuple[str, ...] = (
    "knowledge/context/curation/",
    "knowledge/context/investigations/",
)

_GIT_TIMEOUT = 10          # seconds, per plumbing call
_FETCH_TIMEOUT = 15        # seconds; fail-open when offline
_PROBE_TIMEOUT = 10        # seconds; venv interpreter dependency probe

_REQUIRED_PROFILE_SUFFIXES = ("HOST", "USER", "PASSWORD")
# Longest-first so _AUTH_SOURCE is not misparsed as _SOURCE etc.
_KNOWN_PROFILE_SUFFIXES = ("AUTH_SOURCE", "VERIFY_SSL", "PASSWORD", "HOST", "USER")

_CHECK_MODULES = ("requests", "yaml", "jmespath")

_ADAPTER_RUNTIME_REL = Path("src/vcfops_managementpacks/adapter_runtime")


# ---------------------------------------------------------------------------
# Repo root anchoring (never cwd)
# ---------------------------------------------------------------------------

def find_repo_root() -> Path:
    """Anchor to the repo root via this module's location on disk.

    doctor.py lives at <root>/src/vcfops_common/doctor.py, so the root is
    two parents up from the package directory. Works from any cwd.

    ASSUMPTION: the from-source checkout layout (`src/vcfops_common/`).
    That is the framework's only shipped install model. A pip-installed
    copy would anchor into site-packages and misreport; if that model
    ever ships, switch to `git rev-parse --show-toplevel` with this as
    the fallback.
    """
    return Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Git plumbing (injectable for tests; no shell, no bash)
# ---------------------------------------------------------------------------

GitRunner = Callable[[Sequence[str], int], Tuple[int, str]]


def _make_git_runner(root: Path) -> GitRunner:
    def run(args: Sequence[str], timeout: int = _GIT_TIMEOUT) -> Tuple[int, str]:
        try:
            proc = subprocess.run(
                ["git", "-C", str(root), *args],
                capture_output=True,
                # git writes UTF-8; decode it as such rather than letting
                # Python pick the locale codec (cp1252 on Windows, which
                # would raise on any non-ASCII commit subject or path).
                # errors="replace" so a stray undecodable byte mangles one
                # character instead of losing the whole preflight.
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
            return proc.returncode, proc.stdout
        except (OSError, subprocess.TimeoutExpired, UnicodeDecodeError):
            return 1, ""
    return run


# ---------------------------------------------------------------------------
# Ahead-commit classification
# ---------------------------------------------------------------------------

def classify_path(path: str) -> str:
    """'local' for environment/state paths, 'core' for everything else."""
    p = path.replace("\\", "/")
    for prefix in LOCAL_STATE_PREFIXES:
        if p.startswith(prefix):
            return "local"
    return "core"


def classify_commit(paths: Sequence[str]) -> str:
    """Classify one commit by its touched paths: core | local | mixed."""
    kinds = {classify_path(p) for p in paths if p}
    if kinds == {"core"}:
        return "core"
    if kinds == {"local"}:
        return "local"
    if not kinds:
        return "core"  # empty commit; treat as core (PR-reviewable)
    return "mixed"


def area_for_path(path: str) -> str:
    """Plain-language area label for the ELI5 incoming-change summary."""
    p = path.replace("\\", "/")
    if p.startswith(("src/", "tests/")):
        return "tooling fixes"
    if p.startswith("content/"):
        parts = p.split("/")
        return f"new {parts[1]}" if len(parts) > 1 else "new content"
    if p.startswith(("knowledge/rules/", "knowledge/lessons/")):
        return "rules and lessons"
    if p.startswith("knowledge/"):
        return "knowledge and docs"
    if p.startswith(".claude/"):
        return "agent config"
    if p.startswith("scripts/"):
        return "scripts"
    if p.startswith(("bundles/", "dist/")):
        return "packaging"
    if "/" not in p:
        return "docs"
    return "other changes"


@dataclass
class Commit:
    sha: str
    subject: str
    paths: List[str] = field(default_factory=list)

    @property
    def area(self) -> str:
        """Dominant area (most touched paths) for grouping."""
        counts: Dict[str, int] = {}
        for p in self.paths:
            a = area_for_path(p)
            counts[a] = counts.get(a, 0) + 1
        if not counts:
            return "other changes"
        return max(counts, key=lambda a: counts[a])

    @property
    def classification(self) -> str:
        return classify_commit(self.paths)


def _parse_commit_log(raw: str) -> List[Commit]:
    """Parse `git log --pretty=format:%x01%h%x02%s --name-only` output."""
    commits: List[Commit] = []
    for record in raw.split("\x01"):
        record = record.strip("\n")
        if not record:
            continue
        head, _, body = record.partition("\x02")
        if not body:
            continue
        lines = body.splitlines()
        subject = lines[0].strip()
        paths = [ln.strip() for ln in lines[1:] if ln.strip()]
        commits.append(Commit(sha=head.strip(), subject=subject, paths=paths))
    return commits


# ---------------------------------------------------------------------------
# Upstream alignment
# ---------------------------------------------------------------------------

@dataclass
class UpstreamState:
    available: bool = False          # git + upstream ref usable at all
    fetch_ok: bool = False
    upstream: str = ""
    ahead: List[Commit] = field(default_factory=list)
    behind: List[Commit] = field(default_factory=list)
    dirty: bool = False
    note: str = ""


def _tracking_remote(git: GitRunner) -> str:
    """Name of the remote this branch tracks, defaulting to 'origin'.

    Fetching a hardcoded 'origin' cannot refresh a checkout that tracks
    e.g. 'upstream/main', which would silently produce a stale (and
    possibly wrongly green) comparison.
    """
    rc, out = git(["rev-parse", "--abbrev-ref", "HEAD"], _GIT_TIMEOUT)
    branch = out.strip() if rc == 0 else ""
    remotes: List[str] = []
    rc, out = git(["remote"], _GIT_TIMEOUT)
    if rc == 0:
        remotes = [r.strip() for r in out.splitlines() if r.strip()]
    if branch:
        rc, out = git(["config", "--get", f"branch.{branch}.remote"], _GIT_TIMEOUT)
        configured = out.strip() if rc == 0 else ""
        if configured and (not remotes or configured in remotes):
            return configured
    if remotes:
        return "origin" if "origin" in remotes else remotes[0]
    return "origin"


def inspect_upstream(git: GitRunner) -> UpstreamState:
    st = UpstreamState()
    rc, _ = git(["rev-parse", "--git-dir"], _GIT_TIMEOUT)
    if rc != 0:
        st.note = "git not available; upstream check skipped"
        return st

    remote = _tracking_remote(git)
    rc, out = git(["fetch", remote, "--quiet"], _FETCH_TIMEOUT)
    st.fetch_ok = rc == 0

    rc, out = git(["rev-parse", "--abbrev-ref", "@{upstream}"], _GIT_TIMEOUT)
    if rc == 0 and out.strip():
        st.upstream = out.strip()
    else:
        rc, out = git(["rev-parse", "--abbrev-ref", "HEAD"], _GIT_TIMEOUT)
        branch = out.strip() if rc == 0 else ""
        if branch:
            candidate = f"{remote}/{branch}"
            rc, _ = git(["rev-parse", "--verify", "--quiet", candidate], _GIT_TIMEOUT)
            if rc == 0:
                st.upstream = candidate
    if not st.upstream:
        st.note = "no upstream tracking branch; alignment check skipped"
        return st
    st.available = True

    # Untracked files count as dirty: offering a pull while the user has
    # local work sitting in the tree violates never-touch-a-dirty-tree.
    rc, out = git(["status", "--porcelain"], _GIT_TIMEOUT)
    st.dirty = rc == 0 and bool(out.strip())

    log_fmt = ["log", "--pretty=format:\x01%h\x02%s", "--name-only"]
    rc, out = git(log_fmt + [f"HEAD..{st.upstream}"], _GIT_TIMEOUT)
    if rc == 0:
        st.behind = _parse_commit_log(out)
    rc, out = git(log_fmt + [f"{st.upstream}..HEAD"], _GIT_TIMEOUT)
    if rc == 0:
        st.ahead = _parse_commit_log(out)
    return st


def _render_behind(st: UpstreamState) -> List[str]:
    lines = [f"behind {st.upstream} by {len(st.behind)} commit(s), incoming changes:"]
    grouped: Dict[str, List[Commit]] = {}
    for c in st.behind:
        grouped.setdefault(c.area, []).append(c)
    for area in sorted(grouped):
        lines.append(f"  {area}: {len(grouped[area])}")
        for c in grouped[area]:
            lines.append(f"    - {c.subject}")
    if st.dirty:
        lines.append(
            "  local tree has uncommitted or untracked changes; resolve them "
            "before pulling"
        )
    elif st.ahead:
        # Diverged: a fast-forward pull cannot succeed, do not offer one.
        lines.append(
            "  branch has diverged (both ahead and behind); a rebase or "
            "merge decision is needed, do not pull blindly"
        )
    else:
        lines.append(
            "additionalContext: repo is behind "
            f"{st.upstream} on a clean tree; offer the user a fast-forward "
            "pull (git pull --ff-only). Do not pull without asking."
        )
    return lines


def _render_ahead(st: UpstreamState) -> List[str]:
    lines = [f"ahead of {st.upstream} by {len(st.ahead)} commit(s):"]
    buckets = {"core": [], "local": [], "mixed": []}  # type: Dict[str, List[Commit]]
    for c in st.ahead:
        buckets[c.classification].append(c)
    if buckets["core"]:
        lines.append("  core (PR candidates):")
        lines += [f"    {c.sha} {c.subject}" for c in buckets["core"]]
    if buckets["local"]:
        lines.append("  environment/state (keep local, no PR needed):")
        lines += [f"    {c.sha} {c.subject}" for c in buckets["local"]]
    if buckets["mixed"]:
        lines.append("  mixed (contains both, split before PR):")
        lines += [f"    {c.sha} {c.subject}" for c in buckets["mixed"]]
    if buckets["core"]:
        lines.append(
            f"additionalContext: {len(buckets['core'])} core commit(s) are "
            "ahead of upstream; offer to open a PR for the core work. Do not "
            "suggest pushing environment/state commits. Nothing is pushed "
            "automatically."
        )
    return lines


# ---------------------------------------------------------------------------
# Credential readiness (names only, never values: RULE-008)
# ---------------------------------------------------------------------------

@dataclass
class ProfileStatus:
    name: str
    missing: List[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return not self.missing


def find_env_file(start: Path) -> Optional[Path]:
    """First `.env` found walking up from `start`, or None.

    Mirrors ``_env.load_dotenv``, which walks upward through every
    parent: a `.env` kept above the repo root is a supported setup that
    the CLIs resolve fine, so the doctor must not call it unconfigured.
    """
    here = start.resolve()
    for candidate in [here, *here.parents]:
        env_file = candidate / ".env"
        if env_file.is_file():
            return env_file
    return None


def _env_keys(env_file: Path) -> List[str]:
    """Return KEY names with a NON-EMPTY value in a .env file.

    Values are inspected only for emptiness and never returned, stored,
    or logged (RULE-008). Empty values are treated as undefined because
    ``resolve_profile_credentials()`` rejects them, so counting
    ``VCFOPS_PROD_PASSWORD=`` as present would let the doctor print
    "profiles ready" right before every real CLI call fails.

    May raise OSError / UnicodeDecodeError (e.g. a Windows editor saved
    the file as UTF-16, or the file is unreadable); the caller degrades.
    """
    keys: List[str] = []
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        # Same trivial unquoting as _env._parse_into_environ, so a value
        # of "" or '' is recognized as empty rather than two characters.
        # Note one deliberate divergence: this strips AFTER unquoting
        # (_env.py:83-84 does not), so a quoted all-whitespace value like
        # PASSWORD="  " is called missing here even though the real
        # loader would accept it. That errs toward telling the user to
        # fix a credential that almost certainly does not work, which is
        # the safe direction for a preflight.
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
            val = val[1:-1].strip()
        elif val and val[0] not in ("'", '"'):
            hash_idx = val.find("#")
            if hash_idx != -1:
                val = val[:hash_idx].strip()
        if key and val:
            keys.append(key)
    return keys


def inspect_credentials(
    root: Path,
    environ: Optional[Dict[str, str]] = None,
) -> Tuple[bool, List[ProfileStatus], str]:
    """Return (env_file_found, per-profile status, note).

    The `.env` is located by the same upward walk `_env.load_dotenv`
    uses, so a file kept above the repo root counts. Profile/key NAMES
    are unioned with ``VCFOPS_*`` names carrying a non-empty value in
    the process environment, matching _env.py's contract that a real
    shell export always wins over the file. Only NAMES are ever
    retained or printed; values are inspected for emptiness and
    discarded (RULE-008). ``note`` is non-empty when a `.env` was found
    but could not be parsed; the check then runs on exported vars alone.
    """
    if environ is None:
        # Blanked at the boundary (RULE-008 defense in depth): the only
        # property this function needs from a value is empty vs
        # non-empty, so no real secret is ever held in doctor memory.
        environ = {
            k: ("x" if (v or "").strip() else "")
            for k, v in os.environ.items()
            if k.startswith("VCFOPS_")
        }
    env_file = find_env_file(root)
    env_file_exists = env_file is not None
    note = ""
    keys: set = set()
    if env_file is not None:
        try:
            keys = set(_env_keys(env_file))
        except (OSError, UnicodeDecodeError) as exc:
            note = (
                f".env exists but could not be read: {env_file} "
                f"({type(exc).__name__}); checking exported vars only"
            )
    # Empty exported values are undefined too: resolve_profile_credentials()
    # rejects them, so `export VCFOPS_PROD_PASSWORD=` is not a credential.
    keys |= {
        k for k, v in environ.items()
        if k.startswith("VCFOPS_") and (v or "").strip()
    }
    seen: Dict[str, set] = {}
    for key in keys:
        if not key.startswith("VCFOPS_"):
            continue
        rest = key[len("VCFOPS_"):]
        for suffix in _KNOWN_PROFILE_SUFFIXES:
            if rest.endswith("_" + suffix):
                name = rest[: -(len(suffix) + 1)]
                if name and name.isidentifier():
                    seen.setdefault(name, set()).add(suffix)
                break
    # A profile EXISTS only if its _HOST var is defined (same contract as
    # _env.py:available_profiles()). Other suffixes without a matching HOST
    # (e.g. VCFOPS_PROD_SSH_PASSWORD, an SSH credential) are ignored.
    profiles = {n: sfx for n, sfx in seen.items() if "HOST" in sfx}
    statuses: List[ProfileStatus] = []
    for name in sorted(profiles):
        missing = [
            f"VCFOPS_{name}_{sfx}"
            for sfx in _REQUIRED_PROFILE_SUFFIXES
            if sfx not in profiles[name]
        ]
        statuses.append(ProfileStatus(name=name.lower(), missing=missing))
    return env_file_exists, statuses, note


# ---------------------------------------------------------------------------
# Environment sanity
# ---------------------------------------------------------------------------

@dataclass
class EnvSanity:
    python_ok: bool = True
    python_version: str = ""
    missing_modules: List[str] = field(default_factory=list)
    missing_jars: List[str] = field(default_factory=list)
    checked_interpreter: str = "current"  # "current" or the venv python path

    @property
    def jars_present(self) -> bool:
        return not self.missing_jars


def venv_python(root: Path) -> Optional[Path]:
    """Path to the repo venv's interpreter, or None if there is no venv."""
    for rel in ("bin/python3", "bin/python", "Scripts/python.exe"):
        candidate = root / ".venv" / rel
        if candidate.is_file():
            return candidate
    return None


def _probe_modules(interpreter: Path, modules: Sequence[str]) -> Optional[List[str]]:
    """Ask another interpreter which of `modules` it cannot import.

    Returns the missing list, or None if the probe could not run (the
    caller then falls back to checking the current interpreter). Uses
    find_spec in the child, so nothing is actually imported.
    """
    code = (
        "import importlib.util, sys\n"
        "missing = []\n"
        "for m in sys.argv[1:]:\n"
        "    try:\n"
        "        found = importlib.util.find_spec(m) is not None\n"
        "    except Exception:\n"
        "        found = False\n"
        "    if not found:\n"
        "        missing.append(m)\n"
        "print(' '.join(missing))\n"
    )
    try:
        proc = subprocess.run(
            [str(interpreter), "-c", code, *modules],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=_PROBE_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired, UnicodeDecodeError, ValueError):
        return None
    if proc.returncode != 0:
        return None
    # Only the names we asked about may come back. A venv python that
    # prints anything else on stdout (site warnings, banners, a chatty
    # sitecustomize) would otherwise fabricate "missing modules" and, in
    # the first-run path, dump every token into the CHECKLIST-JSON line.
    # Any unexpected token means the probe is untrustworthy: fail it and
    # let the caller fall back to the current interpreter.
    expected = set(modules)
    reported = proc.stdout.split()
    if any(tok not in expected for tok in reported):
        return None
    return reported


def inspect_environment(
    root: Path,
    check_import: Optional[Callable[[str], bool]] = None,
    *,
    probe: Callable[[Path, Sequence[str]], Optional[List[str]]] = _probe_modules,
) -> EnvSanity:
    es = EnvSanity()
    es.python_version = "%d.%d.%d" % sys.version_info[:3]
    es.python_ok = sys.version_info >= (3, 9)

    # Dependency check, reconciled across BOTH interpreters. The hook's
    # interpreter is often NOT the repo venv (Claude may be started
    # outside an activated virtualenv) and the concierge installs deps
    # into <root>/.venv, so checking only the current interpreter reports
    # FIRST-RUN forever on a correctly set up machine (Codex P1). But
    # checking only the venv has the mirror-image failure: an ambient
    # python3 that has everything, next to a bare or dep-less .venv,
    # would also report FIRST-RUN forever. A module therefore counts as
    # missing only when BOTH interpreters lack it, i.e. when no
    # interpreter on this machine can run the CLIs.
    if check_import is None:
        def check_import(name: str) -> bool:  # noqa: F811
            try:
                return importlib.util.find_spec(name) is not None
            except (ImportError, ValueError):
                return False
    current_missing = [m for m in _CHECK_MODULES if not check_import(m)]

    venv_missing: Optional[List[str]] = None
    # Nothing missing here means nothing can be missing in the
    # intersection, so skip the subprocess entirely in the common case.
    if current_missing:
        vpy = venv_python(root)
        # Skip the subprocess only when we are ALREADY running inside
        # that venv (sys.prefix points at it); a same-named interpreter
        # is not the same environment.
        already_in_venv = False
        try:
            already_in_venv = Path(sys.prefix).resolve() == (root / ".venv").resolve()
        except OSError:
            pass
        if vpy is not None and not already_in_venv:
            venv_missing = probe(vpy, _CHECK_MODULES)
            if venv_missing is not None:
                es.checked_interpreter = f"current + {vpy}"

    if venv_missing is None:
        es.missing_modules = current_missing
    else:
        # Intersection: missing here AND missing there.
        venv_set = set(venv_missing)
        es.missing_modules = [m for m in current_missing if m in venv_set]

    # Tier 1 MPB runtime: the builder needs adapter_runtime/mpb_adapter3.jar
    # (constant-pool source for the per-adapter JAR) AND at least one
    # adapter_runtime/lib/*.jar. Without either it still emits a pak, but
    # one carrying ADAPTER_JAR_GAP / LIB_GAP placeholders that cannot run
    # (src/vcfops_managementpacks/builder.py). Any-jar-present was too
    # loose: a Tier 2 SDK jar alone would have passed.
    runtime_dir = root / _ADAPTER_RUNTIME_REL
    if not (runtime_dir / "mpb_adapter3.jar").is_file():
        es.missing_jars.append("adapter_runtime/mpb_adapter3.jar")
    lib_dir = runtime_dir / "lib"
    if not (lib_dir.is_dir() and any(lib_dir.glob("*.jar"))):
        es.missing_jars.append("adapter_runtime/lib/*.jar")
    return es


# ---------------------------------------------------------------------------
# Bootstrap health
# ---------------------------------------------------------------------------

_STATUS_LINE_RE = re.compile(r"^(\S+)\s+(\S+)\s+(.*)$")

# Reserved key under which the parsed line's field-1 timestamp is stored,
# chosen so it cannot collide with a real `key=value` token.
TIMESTAMP_KEY = "__ts__"

# Bootstrap data older than this is reported as stale. The hook runs the
# doctor immediately after both bootstrap scripts, so a stale timestamp
# means a script did not run at all (failed, or a read-only checkout).
STALE_AFTER_HOURS = 24


def _safe_int(value: str) -> Optional[int]:
    """int() that returns None on garbage instead of raising."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_age_hours(stamp: str, *, now: Optional[datetime] = None) -> Optional[float]:
    """Age in hours of an ISO8601 UTC timestamp, or None if unparseable.

    Accepts the trailing-``Z`` form the bootstrap scripts write (which
    ``datetime.fromisoformat`` does not accept before 3.11) and treats a
    naive timestamp as UTC. Never raises: garbage returns None so the
    caller degrades, same discipline as ``_safe_int``.
    """
    if not stamp:
        return None
    text = stamp.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return (current - parsed).total_seconds() / 3600.0


def unrecorded_bootstrap_scripts(
    bootstrap: Dict[str, Dict[str, str]],
) -> List[str]:
    """Known bootstrap scripts with no line in `.bootstrap-status`.

    A script that dies before its status write (hook timeout, missing
    registry) leaves no line, and the other script's clean record must
    not stand in for it: an absent record is its own delta.
    """
    return [s for s in KNOWN_BOOTSTRAP_SCRIPTS if s not in bootstrap]


def read_bootstrap_status(root: Path) -> Tuple[Dict[str, Dict[str, str]], str]:
    """Parse `.bootstrap-status`; last line per script name wins.

    Returns (status, note). ``note`` is non-empty when the file exists
    but could not be read; the doctor degrades to an attention line
    instead of crashing (always-exit-0 contract).
    """
    path = root / BOOTSTRAP_STATUS_FILE
    result: Dict[str, Dict[str, str]] = {}
    if not path.is_file():
        return result, ""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return result, (
            f"{BOOTSTRAP_STATUS_FILE} exists but could not be read "
            f"({type(exc).__name__}); bootstrap health unknown"
        )
    for raw in text.splitlines():
        m = _STATUS_LINE_RE.match(raw.strip())
        if not m:
            continue
        stamp, script, rest = m.groups()
        kv: Dict[str, str] = {}
        for tok in rest.split():
            if "=" in tok:
                k, _, v = tok.partition("=")
                if k != TIMESTAMP_KEY:  # reserved, cannot be spoofed by a token
                    kv[k] = v
        kv[TIMESTAMP_KEY] = stamp
        result[script] = kv
    return result, ""


# ---------------------------------------------------------------------------
# First-run detection and concierge checklist (Phase 1b)
# ---------------------------------------------------------------------------

def _venv_ok(root: Path, env: EnvSanity) -> bool:
    """A machine counts as configured if a .venv exists, we ARE in a venv,
    or the core deps import fine (system-managed python is a valid setup)."""
    if (root / ".venv").is_dir():
        return True
    if sys.prefix != getattr(sys, "base_prefix", sys.prefix):
        return True
    core_missing = [m for m in env.missing_modules if m != "jmespath"]
    return not core_missing


def build_checklist(
    root: Path,
    env: EnvSanity,
    env_file_exists: bool,
    profiles: List[ProfileStatus],
    bootstrap: Dict[str, Dict[str, str]],
) -> List[Dict[str, str]]:
    core_missing = [m for m in env.missing_modules if m != "jmespath"]
    items: List[Dict[str, str]] = []
    items.append({
        "id": "python",
        "status": "ok" if env.python_ok else "fail",
        "detail": f"python {env.python_version}"
        + ("" if env.python_ok else " (need >= 3.9; install via apt / winget / brew)"),
    })
    items.append({
        "id": "venv",
        "status": "ok" if _venv_ok(root, env) else "fail",
        "detail": "create .venv: python -m venv .venv, then install deps into it",
    })
    items.append({
        "id": "deps",
        "status": "ok" if not core_missing else "fail",
        "detail": (
            "all core modules importable" if not core_missing
            else "missing: " + ", ".join(core_missing)
            + "; pip install -r requirements.txt (ask for a corporate mirror "
            "index URL if pypi is blocked)"
        ),
    })
    complete = [p.name for p in profiles if p.complete]
    items.append({
        "id": "credentials",
        "status": "ok" if complete else "fail",
        "detail": (
            "profiles ready: " + ", ".join(complete) if complete
            else "no complete VCFOPS profile in .env or exported vars; "
            "run the credential wizard"
        ),
    })
    unrecorded = unrecorded_bootstrap_scripts(bootstrap)
    counts = [_safe_int(kv.get("failed", "0") or "0") for kv in bootstrap.values()]
    unparseable = any(c is None for c in counts)
    failed_total = sum(c for c in counts if c is not None)
    if unrecorded:
        boot_status = "unknown"
        boot_detail = (
            "no run recorded for " + ", ".join(unrecorded)
            + "; fetch the reference repos and managed paks "
            "(scripts/bootstrap_references.sh and "
            "scripts/bootstrap_managed_paks.sh on unix; a native Windows "
            "port is tracked as issue #89)"
        )
    elif unparseable:
        boot_status = "unknown"
        boot_detail = (
            f"{BOOTSTRAP_STATUS_FILE} has unparseable status line(s); "
            "re-run the bootstrap fetches"
        )
    else:
        boot_status = "ok" if failed_total == 0 else "fail"
        boot_detail = f"{len(bootstrap)} bootstrap script(s) recorded, {failed_total} failure(s)"
    items.append({"id": "bootstrap-clones", "status": boot_status, "detail": boot_detail})
    items.append({
        "id": "recheck",
        "status": "pending",
        "detail": "re-run `python -m vcfops_common doctor` after fixes for one green line",
    })
    return items


def is_first_run(
    root: Path,
    env: EnvSanity,
    env_file_exists: bool,
    profiles: Optional[List[ProfileStatus]] = None,
) -> bool:
    core_missing = [m for m in env.missing_modules if m != "jmespath"]
    # A missing .env alone is NOT first-run when a complete profile is
    # exported in the shell environment (_env.py: exports win over the
    # file). Such a user is configured, not unconfigured.
    has_complete_profile = any(p.complete for p in (profiles or []))
    creds_absent = not env_file_exists and not has_complete_profile
    return creds_absent or bool(core_missing) or not _venv_ok(root, env)


# ---------------------------------------------------------------------------
# Main report
# ---------------------------------------------------------------------------

def run_doctor(
    root: Optional[Path] = None,
    *,
    git: Optional[GitRunner] = None,
    check_import: Optional[Callable[[str], bool]] = None,
    environ: Optional[Dict[str, str]] = None,
    out: Callable[[str], None] = print,
) -> int:
    root = root or find_repo_root()
    git = git or _make_git_runner(root)

    env = inspect_environment(root, check_import)
    env_file_exists, profiles, cred_note = inspect_credentials(root, environ)
    bootstrap, bootstrap_note = read_bootstrap_status(root)

    # --- Phase 1b: concierge first-run -----------------------------------
    if is_first_run(root, env, env_file_exists, profiles):
        out("FIRST-RUN DETECTED")
        out(f"additionalContext: {GREETING}")
        checklist = build_checklist(root, env, env_file_exists, profiles, bootstrap)
        out("CHECKLIST-JSON: " + json.dumps({"items": checklist}))
        return 0

    attention: List[str] = []

    # --- Upstream ---------------------------------------------------------
    st = inspect_upstream(git)
    if st.note:
        attention.append(st.note)
    if st.available:
        if st.behind:
            attention += _render_behind(st)
        if st.ahead:
            attention += _render_ahead(st)

    # --- Credentials ------------------------------------------------------
    if cred_note:
        attention.append(cred_note)
    complete = [p.name for p in profiles if p.complete]
    incomplete = [p for p in profiles if not p.complete]
    for p in incomplete:
        attention.append(
            f"profile '{p.name}' is incomplete, missing: " + ", ".join(p.missing)
        )
    if not profiles:
        attention.append("no VCFOPS profiles defined (.env or exported vars)")
        attention.append(
            "additionalContext: no credential profiles are configured; offer "
            "the user the credential setup wizard."
        )

    # --- Environment ------------------------------------------------------
    if not env.python_ok:
        attention.append(
            f"python {env.python_version} is below the 3.9 minimum"
        )
    if env.missing_modules:
        attention.append(
            "missing python module(s): " + ", ".join(env.missing_modules)
            + f" [checked: {env.checked_interpreter}]"
            + " (pip install -r requirements.txt)"
        )
    if not env.jars_present:
        attention.append(
            "MPB Tier 1 runtime incomplete under src/vcfops_managementpacks/, "
            "missing: " + ", ".join(env.missing_jars)
            + "; pak builds would still succeed but produce a nonfunctional "
            "pak (an ADAPTER_JAR_GAP or LIB_GAP placeholder, or, when lib/ "
            "exists but is empty, silently no library JARs at all). See "
            "Getting_Started.md for how to obtain them (warn only)."
        )

    # --- Bootstrap health -------------------------------------------------
    if bootstrap_note:
        attention.append(bootstrap_note)
    unrecorded = unrecorded_bootstrap_scripts(bootstrap)
    if unrecorded and not bootstrap_note:
        attention.append(
            "no bootstrap run recorded for " + ", ".join(unrecorded)
            + "; reference repos and/or managed pak clones may be missing or "
            "stale (the script may have failed or timed out before writing)"
        )
    for script, kv in sorted(bootstrap.items()):
        # Age: the hook runs the doctor right after both bootstrap
        # scripts, so a stale line means a script did not run at all
        # (failed, or a read-only checkout kept an old file).
        stamp = kv.get(TIMESTAMP_KEY, "")
        age_hours = _safe_age_hours(stamp)
        if age_hours is None:
            attention.append(
                f"{script}: unparseable timestamp in {BOOTSTRAP_STATUS_FILE} "
                f"({stamp!r}); bootstrap age unknown"
            )
        elif age_hours >= STALE_AFTER_HOURS:
            days = age_hours / 24.0
            age_text = (
                f"{days:.0f} day(s)" if days >= 1 else f"{age_hours:.0f} hour(s)"
            )
            attention.append(
                f"{script}: bootstrap health is {age_text} stale (last recorded "
                f"run {stamp}); the script may not be running"
            )
        failed = _safe_int(kv.get("failed", "0") or "0")
        if failed is None:
            attention.append(
                f"{script}: unparseable {BOOTSTRAP_STATUS_FILE} line "
                f"(failed={kv.get('failed', '')!r}); re-run the bootstrap script"
            )
        elif failed:
            failures = kv.get("failures", "-")
            attention.append(
                f"{script}: {failed} clone/update failure(s): {failures}"
            )

    # --- Emit -------------------------------------------------------------
    if not attention:
        sync = f"in sync with {st.upstream}" if st.available else "upstream unknown"
        if st.available and not st.fetch_ok:
            sync += " as of last fetch (offline?)"
        prof = ", ".join(complete) if complete else "none"
        out(f"doctor: all green ({sync}; profiles ready: {prof}; environment ok)")
        return 0

    out(f"doctor: {len(attention)} line(s) need attention")
    for line in attention:
        out(line)
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entry. Belt-and-braces: no bug in the doctor may ever break
    session start, so any unexpected exception degrades to one line and
    exit 0 (the hook contract)."""
    try:
        return run_doctor()
    except Exception as exc:  # noqa: BLE001 (deliberate catch-all, hook contract)
        print(f"doctor: internal error ({type(exc).__name__}); "
              "preflight skipped this session")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

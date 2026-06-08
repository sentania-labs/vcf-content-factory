"""Registry reader for independently-versioned SDK management-pack adapters.

Parses ``context/managed_paks.md`` into a list of :class:`ManagedPak` entries.
HTML-comment blocks (the entry template) are skipped, mirroring the field
names and parse logic of ``scripts/bootstrap_managed_paks.sh``.

Public API
----------
load_registry(registry_path) -> List[ManagedPak]
    Parse the registry file and return all live (non-comment) entries.

lookup_by_adapter_name(name, registry_path) -> ManagedPak | None
    Look up an entry by the adapter directory name (``content/sdk-adapters/<name>``).

lookup_by_adapter_kind(adapter_kind, registry_path) -> ManagedPak | None
    Look up an entry by its ``adapter_kind:`` field (e.g. ``vcfcf_compliance``).

derived_latest_release_url(pak) -> str
    Return ``<remote>/releases/latest`` for a ManagedPak.

derived_api_latest_url(pak) -> str
    Return the GitHub REST API form, e.g.
    ``https://api.github.com/repos/<owner>/<repo>/releases/latest``.

Registry file format (from context/managed_paks.md)
----------------------------------------------------
Each non-commented entry has at least::

    ### <name>

    - **Remote:** https://github.com/<owner>/<repo>
    - **Target:** `content/sdk-adapters/<name>/`
    - **adapter_kind:** vcfcf_<name>

Lines inside ``<!-- ... -->`` comment blocks are skipped entirely.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


# ---------------------------------------------------------------------------
# Public data types
# ---------------------------------------------------------------------------

@dataclass
class ManagedPak:
    """One entry in the managed-paks registry."""
    name: str           # adapter directory name under content/sdk-adapters/
    remote: str         # https://github.com/<owner>/<repo>
    target: str         # content/sdk-adapters/<name>/
    adapter_kind: str   # vcfcf_<name>


# ---------------------------------------------------------------------------
# Regex patterns (mirror bootstrap_managed_paks.sh field extractions)
# ---------------------------------------------------------------------------

_REMOTE_RE = re.compile(r"\*\*Remote:\*\*\s+(https://[^\s]+)")
_TARGET_RE = re.compile(r"\*\*Target:\*\*\s+`content/sdk-adapters/([^/`]+)/?`")
_ADAPTER_KIND_RE = re.compile(r"\*\*adapter_kind:\*\*\s+(\S+)")

# GitHub https remote pattern for deriving the API URL:
#   https://github.com/<owner>/<repo>  -->  owner, repo
_GITHUB_REMOTE_RE = re.compile(
    r"https://github\.com/([^/]+)/([^/\s]+?)(?:\.git)?$"
)

# Default registry path relative to the package file.
_DEFAULT_REGISTRY_PATH = Path(__file__).parent.parent / "context" / "managed_paks.md"


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def load_registry(registry_path: "str | Path | None" = None) -> List[ManagedPak]:
    """Parse the managed-paks registry and return all live entries.

    Skips lines inside HTML comment blocks (``<!-- ... -->``), which is where
    the entry template is embedded.

    Args:
        registry_path: Path to the registry markdown file.  Defaults to
            ``context/managed_paks.md`` relative to the repo root.

    Returns:
        A list of :class:`ManagedPak` entries in document order.

    Raises:
        FileNotFoundError: if the registry file does not exist.
    """
    if registry_path is None:
        registry_path = _DEFAULT_REGISTRY_PATH
    registry_path = Path(registry_path)
    if not registry_path.exists():
        raise FileNotFoundError(f"managed_paks registry not found: {registry_path}")

    entries: List[ManagedPak] = []
    current_remote: Optional[str] = None
    current_name: Optional[str] = None
    current_target: Optional[str] = None
    current_adapter_kind: Optional[str] = None
    in_comment = False

    lines = registry_path.read_text(encoding="utf-8").splitlines()
    for line in lines:
        # Track HTML comment blocks — skip all content inside them.
        # A line may open and close the same comment (e.g. <!-- foo -->).
        if "<!--" in line:
            in_comment = True
        if in_comment:
            if "-->" in line:
                in_comment = False
            continue

        # --- Remote ---
        m = _REMOTE_RE.search(line)
        if m:
            current_remote = m.group(1).rstrip("/")
            continue

        # --- Target ---
        m = _TARGET_RE.search(line)
        if m:
            current_name = m.group(1)
            current_target = f"content/sdk-adapters/{current_name}/"
            continue

        # --- adapter_kind ---
        m = _ADAPTER_KIND_RE.search(line)
        if m:
            current_adapter_kind = m.group(1)
            # All three required fields collected — emit the entry.
            if current_remote and current_name and current_adapter_kind:
                entries.append(ManagedPak(
                    name=current_name,
                    remote=current_remote,
                    target=current_target or f"content/sdk-adapters/{current_name}/",
                    adapter_kind=current_adapter_kind,
                ))
            # Reset for next entry.
            current_remote = None
            current_name = None
            current_target = None
            current_adapter_kind = None
            continue

    return entries


def lookup_by_adapter_name(
    name: str,
    registry_path: "str | Path | None" = None,
) -> Optional[ManagedPak]:
    """Return the registry entry whose adapter directory name matches ``name``.

    ``name`` is the leaf directory name under ``content/sdk-adapters/``, e.g.
    ``"compliance"`` for ``content/sdk-adapters/compliance/``.

    Returns ``None`` if no entry matches.
    """
    for pak in load_registry(registry_path):
        if pak.name == name:
            return pak
    return None


def lookup_by_adapter_kind(
    adapter_kind: str,
    registry_path: "str | Path | None" = None,
) -> Optional[ManagedPak]:
    """Return the registry entry whose ``adapter_kind`` field matches.

    Returns ``None`` if no entry matches.
    """
    for pak in load_registry(registry_path):
        if pak.adapter_kind == adapter_kind:
            return pak
    return None


# ---------------------------------------------------------------------------
# URL derivations
# ---------------------------------------------------------------------------

def derived_latest_release_url(pak: ManagedPak) -> str:
    """Return the human-browsable latest-release URL for a managed pak.

    Derived as ``<remote>/releases/latest``.  Never stored in the registry
    (stays version-free).
    """
    return f"{pak.remote}/releases/latest"


def derived_api_latest_url(pak: ManagedPak) -> Optional[str]:
    """Return the GitHub REST API latest-release URL for a managed pak.

    Returns ``https://api.github.com/repos/<owner>/<repo>/releases/latest``
    for GitHub remotes, or ``None`` if the remote is not a recognized GitHub
    HTTPS remote.
    """
    m = _GITHUB_REMOTE_RE.match(pak.remote)
    if not m:
        return None
    owner, repo = m.group(1), m.group(2)
    return f"https://api.github.com/repos/{owner}/{repo}/releases/latest"

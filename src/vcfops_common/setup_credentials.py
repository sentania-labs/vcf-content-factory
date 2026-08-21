"""Interactive credential wizard (bootstrap-v2 Phase 2).

    python3 -m vcfops_common setup

Run BY THE USER in their own terminal. Inside a Claude session the flow
is: Claude tells the user to type ``! python3 -m vcfops_common setup``;
the ``!`` prefix runs it interactively in-session, and because the
password is read with :func:`getpass.getpass` it is typed but never
echoed, so no secret ever lands in the transcript.

Design: knowledge/designs/bootstrap-v2.md
§"Phase 2: credential wizard (no secrets in the transcript)".

RULE-008 posture (absolute, and the reason several obvious shortcuts are
not taken here):

  - The password is read only via a silent prompt. It is never accepted
    on argv (``--password`` is rejected with a pointer to this wizard),
    never echoed, never written to a temp file, never logged.
  - Nothing that could carry the password is printed: not the token, not
    a response body, not a raw exception. Every string that reaches an
    output stream on a failure path goes through :func:`_scrub`, which
    redacts the password (raw and percent-encoded) and caps length.
  - The written ``.env`` is never printed back, not even a diff.
  - Existing values are re-read from ``.env`` for prompt defaults, but
    only for the NON-secret suffixes (HOST / USER / AUTH_SOURCE /
    VERIFY_SSL). The wizard never reads an existing PASSWORD value.
  - The file is created with mode 0600 via ``os.open`` rather than
    written and then chmod-ed, so the secret is never briefly readable
    by other users. The write goes through a same-directory temp file
    that is 0600 from creation, is unlinked in a ``finally``, and is
    swapped in with ``os.replace``; see :func:`write_env_file` for why
    that is both safer for the operator and RULE-008-clean, and for
    what happens when ``.env`` is a symlink.

Windows portability: pure stdlib plus ``requests`` (imported lazily, and
optional: without it the wizard offers to skip live validation).
``getpass`` is silent on Windows too. No bash. The repo root is anchored
to this module's location on disk exactly the way ``doctor.py`` does it,
never to ``Path.cwd()``.

Non-interactive safety: if stdin is not a TTY the wizard refuses and
exits 2 rather than reading a password from a pipe or hanging. The
SessionStart hook must never be able to trigger a prompt.
"""
from __future__ import annotations

import getpass
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

# The profile scheme is _env.py's, not a parallel convention:
#   VCFOPS_<PROFILE>_HOST / _USER / _PASSWORD / _AUTH_SOURCE / _VERIFY_SSL
PROFILE_PREFIX = "VCFOPS_"
SECRET_SUFFIX = "PASSWORD"
# Written (and prompted) in this order.
PROFILE_SUFFIXES: Tuple[str, ...] = (
    "HOST",
    "USER",
    "PASSWORD",
    "AUTH_SOURCE",
    "VERIFY_SSL",
)
# Suffixes safe to read back off disk for prompt defaults. PASSWORD is
# deliberately absent (RULE-008).
_ECHOABLE_SUFFIXES: Tuple[str, ...] = ("HOST", "USER", "AUTH_SOURCE", "VERIFY_SSL")

DEFAULT_PROFILE = "prod"
DEFAULT_AUTH_SOURCE = "Local"
DEFAULT_VERIFY_SSL = True

_ACQUIRE_PATH = "/suite-api/api/auth/token/acquire"
_ACQUIRE_TIMEOUT = 20  # seconds

_MAX_DETAIL = 300  # cap on any scrubbed diagnostic string

_USAGE = """usage: python3 -m vcfops_common setup [--profile NAME] [--no-validate]

Interactive credential wizard. Run it yourself in a terminal; inside a
Claude session type it with a leading `!`:

    ! python3 -m vcfops_common setup

Prompts for profile name, host, user, auth source and verify-SSL (these
echo), then the password twice via a silent prompt (never echoed, never
written to the transcript). Validates by acquiring a token, then merges
the profile into .env at the repo root.

options:
  --profile NAME   pre-seed the profile name prompt (not a secret)
  --no-validate    skip the live token check (offline / air-gapped setup)
"""

_PASSWORD_ON_ARGV = (
    "refusing to accept a password on the command line: argv is visible "
    "in the process list, shell history and the session transcript "
    "(RULE-008). Run `python3 -m vcfops_common setup` with no password "
    "flag and type it at the silent prompt instead."
)


# ---------------------------------------------------------------------------
# Repo root anchoring (never cwd): same contract as doctor.find_repo_root
# ---------------------------------------------------------------------------

def find_repo_root() -> Path:
    """Anchor to the repo root via this module's location on disk.

    setup_credentials.py lives at <root>/src/vcfops_common/, so the root
    is two parents up from the package directory. Works from any cwd.
    """
    return Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Scrubbing: nothing derived from a secret may reach an output stream
# ---------------------------------------------------------------------------

def _scrub(text: object, secrets: Sequence[str] = ()) -> str:
    """Redact secrets from a diagnostic string and cap its length.

    Applied to every string that reaches stdout/stderr on a failure
    path. A requests exception can quote a URL, a header or a chunk of a
    response body, any of which could embed a credential, so the raw
    text is never trusted. Percent-encoded forms are redacted too
    because a URL-ish rendering may have escaped the value.
    """
    out = "" if text is None else str(text)
    out = out.replace("\r", " ").replace("\n", " ")
    variants: List[str] = []
    for secret in secrets:
        if not secret:
            continue
        variants.append(secret)
        try:
            from urllib.parse import quote  # noqa: PLC0415 (stdlib, cheap)

            variants.append(quote(secret, safe=""))
            variants.append(quote(secret))
        except Exception:  # pragma: no cover - urllib is always importable
            pass
    # Longest first so a short variant cannot leave a fragment of a
    # longer one behind.
    for variant in sorted(set(variants), key=len, reverse=True):
        out = out.replace(variant, "***")
    if len(out) > _MAX_DETAIL:
        out = out[:_MAX_DETAIL] + "..."
    return out


# ---------------------------------------------------------------------------
# Value formatting / .env line surgery
# ---------------------------------------------------------------------------

_NEEDS_QUOTING = re.compile(r"[\s#'\"]")

# Matches an assignment line for KEY, active or commented out, with or
# without an `export ` prefix. A commented-out line is treated as a
# placeholder slot the wizard may take over (that is how a .env created
# from .env.example gets its fake `change-me` entries replaced in place
# instead of shadowed by an appended duplicate).
def _assignment_re(key: str) -> "re.Pattern[str]":
    return re.compile(
        r"^(?P<indent>\s*)(?P<hash>#\s*)?(?P<export>export\s+)?"
        + re.escape(key)
        + r"\s*=",
    )


def format_value(value: str, *, always_quote: bool = False) -> str:
    """Render a value for a .env line that ``_env.py`` reads back exactly.

    ``_env._parse_into_environ`` strips one layer of matching outer
    quotes and does no escape processing, so single-quoting round-trips
    any value that has no newline, including values containing quotes,
    ``#`` or spaces. Newlines are rejected upstream (see
    :func:`validate_secret`) because the .env format has no multiline
    form.
    """
    if always_quote or value == "" or _NEEDS_QUOTING.search(value):
        return "'" + value + "'"
    return value


def _unquote(value: str) -> str:
    """The subset of unquoting ``_env.py`` performs, for reading defaults."""
    val = value.strip()
    if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
        return val[1:-1]
    if val and val[0] not in ("'", '"'):
        idx = val.find("#")
        if idx != -1:
            val = val[:idx].rstrip()
    return val


def _uses_export(lines: Sequence[str]) -> bool:
    """Match the file's existing style for newly appended lines."""
    for line in lines:
        if re.match(r"^\s*#?\s*export\s+VCFOPS_", line):
            return True
    return False


def profile_key(profile: str, suffix: str) -> str:
    return f"{PROFILE_PREFIX}{profile.upper()}_{suffix}"


def read_profile_defaults(env_path: Optional[Path], profile: str) -> Dict[str, str]:
    """Existing NON-secret values for `profile`, for prompt defaults.

    PASSWORD is never read (RULE-008): rotating a password means typing
    the new one, and the wizard has no reason to hold the old one.
    Unreadable files degrade to no defaults rather than raising.
    """
    defaults: Dict[str, str] = {}
    if env_path is None or not env_path.is_file():
        return defaults
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return defaults
    for suffix in _ECHOABLE_SUFFIXES:
        pattern = _assignment_re(profile_key(profile, suffix))
        for line in lines:
            m = pattern.match(line)
            if m and not m.group("hash"):
                value = _unquote(line[m.end():])
                if value:
                    defaults[suffix] = value
    return defaults


def _comment_out_assignments(lines: Sequence[str]) -> List[str]:
    """Comment out every active assignment when seeding .env from .env.example.

    The template ships placeholder credentials (`change-me`, an
    example.com host). Copying them in live would hand the doctor three
    complete-looking profiles that fail against a host that does not
    exist, so the seeded copy keeps the template's comments and
    structure as documentation with every assignment inert. The wizard
    then takes over the slots for the profile being configured.
    """
    out: List[str] = []
    active = re.compile(r"^\s*(export\s+)?[A-Za-z_][A-Za-z0-9_]*\s*=")
    for line in lines:
        out.append("# " + line if active.match(line) else line)
    return out


_SEED_HEADER = (
    "# Created by `python3 -m vcfops_common setup` from .env.example.",
    "# Every line copied from the template was commented out: the template's",
    "# placeholder credentials are not real. Live values are written below by",
    "# the wizard. Never commit this file.",
    "",
)


def merge_profile_lines(
    lines: Sequence[str],
    profile: str,
    values: Dict[str, str],
) -> List[str]:
    """Return `lines` with `profile`'s vars set, updated in place if present.

    Unrelated content, comments and ordering survive untouched. An
    existing (or commented-out placeholder) assignment for a key is
    rewritten where it sits, so re-running the wizard rotates a password
    rather than appending a second, shadowing definition. Keys with no
    slot in the file are appended as one titled section.
    """
    result = list(lines)
    export = _uses_export(result)
    prefix = "export " if export else ""
    appended: List[str] = []
    for suffix in PROFILE_SUFFIXES:
        if suffix not in values:
            continue
        key = profile_key(profile, suffix)
        rendered = (
            f"{prefix}{key}={format_value(values[suffix], always_quote=suffix == SECRET_SUFFIX)}"
        )
        pattern = _assignment_re(key)
        # Last match wins: _env.py's parser keeps the FIRST definition of
        # a key, but a later duplicate would be resurrected by any tool
        # that reads last-wins, so rewrite the last slot and neutralize
        # earlier active duplicates below.
        hits = [i for i, line in enumerate(result) if pattern.match(line)]
        if hits:
            target = hits[-1]
            original = result[target]
            m = pattern.match(original)
            # Preserve the ORIGINAL line's style exactly (an `export`-less
            # line stays export-less even in an export-style file); only
            # appended lines follow the file's predominant style.
            keep_export = "export " if (m and m.group("export")) else ""
            result[target] = f"{keep_export}{key}={format_value(values[suffix], always_quote=suffix == SECRET_SUFFIX)}"
            for dup in hits[:-1]:
                dm = pattern.match(result[dup])
                if dm and not dm.group("hash"):
                    result[dup] = "# " + result[dup] + "   # superseded by the line below"
        else:
            appended.append(rendered)
    if appended:
        if result and result[-1].strip():
            result.append("")
        result.append(
            f"# --- VCF Operations: {profile.lower()} profile "
            "(written by `python3 -m vcfops_common setup`) ---"
        )
        result.extend(appended)
    return result


def write_env_file(path: Path, lines: Sequence[str]) -> None:
    """Write .env atomically, with owner-only permissions.

    `.env` holds EVERY credential the factory has and is gitignored, so
    there is no `git restore` after a bad write. Writing in place with
    O_TRUNC would truncate the file BEFORE the new text lands, and any
    failure in between (a full disk, a permissions change mid-run, a
    value the UTF-8 encoder rejects) would leave a zero-byte `.env`:
    the operator adding a `devel` profile silently loses their working
    `prod` and `qa` ones. So: write a sibling temp file, then
    ``os.replace`` it onto the target, which is atomic on POSIX and on
    Windows. Either the old file survives intact or the new one is
    complete; there is no in-between state.

    RULE-008 is satisfied by the temp file's PROPERTIES, not by its
    absence: it is created ``O_EXCL`` with mode 0600 (never readable by
    anyone else, never a pre-existing file we were tricked into
    writing), it lives in the same directory as `.env` (same
    filesystem, so the replace is atomic and it never lands in a
    world-writable /tmp), and it is unlinked in a ``finally`` so it
    cannot outlive the run on any failure path.

    Symlink note: if `.env` is a symlink, the link is resolved first and
    the TARGET is replaced, so a user who points `.env` at a shared
    location keeps that indirection instead of having the wizard
    silently overwrite the link with a regular file.

    On Windows the ``os.open`` mode is ignored and ``os.chmod`` is
    effectively a no-op, which is the documented "applied where
    supported, silently skipped where not" behavior.
    """
    text = "\n".join(lines).rstrip("\n") + "\n"

    target = path
    try:
        if path.is_symlink():
            target = Path(os.path.realpath(str(path)))
    except OSError:
        target = path

    tmp: Optional[Path] = None
    try:
        # O_EXCL: never adopt an existing file. A stale sibling from a
        # killed run must not be written into (it could be anything).
        for attempt in range(100):
            candidate = target.with_name(target.name + f".tmp{os.getpid()}-{attempt}")
            try:
                fd = os.open(
                    str(candidate),
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    0o600,
                )
            except FileExistsError:
                continue
            tmp = candidate
            break
        else:  # pragma: no cover - 100 collisions is not a real scenario
            raise OSError("could not create a temporary file next to .env")

        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
            fh.flush()
            try:
                os.fsync(fh.fileno())
            except OSError:
                pass  # best effort; not all filesystems support it
        if os.name != "nt":
            try:
                os.chmod(str(tmp), 0o600)
            except OSError:
                pass
        os.replace(str(tmp), str(target))
        tmp = None  # ownership transferred; nothing to clean up
    finally:
        if tmp is not None:
            try:
                os.unlink(str(tmp))
            except OSError:
                pass


class EnvReadError(Exception):
    """The existing .env could not be READ (so nothing was written).

    Distinct from a write failure so the operator is told which
    operation actually failed: "could not write .env" is simply wrong
    for a .env an editor saved as UTF-16, and sends them looking at
    permissions instead of at the file's encoding.
    """


def merge_profile_into_env(
    root: Path,
    profile: str,
    values: Dict[str, str],
) -> Tuple[Path, bool]:
    """Merge one profile into <root>/.env. Returns (path, created).

    Creates the file from .env.example (assignments commented out) when
    absent. Never returns or prints file contents.

    Raises ``ValueError`` if any value cannot be stored (see
    ``storable_error``) and ``EnvReadError`` if the existing file could
    not be read; in both cases nothing has been written.
    """
    for suffix, value in values.items():
        problem = storable_error(value, suffix)
        if problem:
            # Names only, never the value (RULE-008).
            raise ValueError(f"VCFOPS_{profile.upper()}_{suffix}: {problem}")
    path = root / ".env"
    created = False
    if path.is_file():
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError) as exc:
            raise EnvReadError(type(exc).__name__) from None
    else:
        created = True
        example = root / ".env.example"
        lines = list(_SEED_HEADER)
        if example.is_file():
            try:
                lines.extend(_comment_out_assignments(
                    example.read_text(encoding="utf-8").splitlines()
                ))
            except (OSError, UnicodeDecodeError):
                pass
    write_env_file(path, merge_profile_lines(lines, profile, values))
    return path, created


# ---------------------------------------------------------------------------
# Input validation (non-secret fields echo; the secret never does)
# ---------------------------------------------------------------------------

_PROFILE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


def validate_profile_name(name: str) -> Optional[str]:
    """None if OK, else an error message. Matches _env.py's key scheme."""
    name = name.strip()
    if not name:
        return "profile name cannot be empty"
    if not _PROFILE_RE.match(name) or not name.upper().isidentifier():
        return (
            "profile name must start with a letter and contain only "
            "letters, digits and underscores (it becomes part of the "
            "VCFOPS_<PROFILE>_HOST variable name)"
        )
    return None


def normalize_host(raw: str) -> Tuple[Optional[str], Optional[str]]:
    """Return (host, error). Accepts a pasted URL, rejects embedded creds."""
    host = raw.strip()
    if not host:
        return None, "host cannot be empty"
    for scheme in ("https://", "http://"):
        if host.lower().startswith(scheme):
            host = host[len(scheme):]
    host = host.split("/", 1)[0].strip()
    if not host:
        return None, "host cannot be empty"
    if "@" in host:
        return None, (
            "the host must not contain credentials (user:pass@host). Enter "
            "the hostname only; the user and password are prompted "
            "separately and the password is never echoed"
        )
    if re.search(r"\s", host):
        return None, "host cannot contain whitespace"
    return host, None


def storable_error(value: str, label: str) -> Optional[str]:
    """None if `value` can be stored in a .env line, else why not.

    Two structural facts of the file format, checked for EVERY field,
    not just the password:

    - A newline ends a line. A value carrying one splits into a second
      line that parses as its own assignment, and since
      ``_env._parse_into_environ`` keeps the FIRST definition of a key
      (_env.py:85), an injected ``VCFOPS_<P>_PASSWORD=`` line SHADOWS
      the password the wizard just validated: the profile would then
      hold a credential that was never checked, right after the wizard
      told the user the host accepted it. Not reachable through a real
      TTY prompt (the line discipline ends the line at Enter), but the
      ``ask`` seam is public and a future non-prompt caller is not
      bound by a terminal's behavior.
    - The file is written as UTF-8. A value UTF-8 cannot encode (a lone
      surrogate, which is exactly what PEP-383 surrogateescape decoding
      produces from a non-UTF-8 byte typed at the prompt under
      ``LC_ALL=C``) raises UnicodeEncodeError at write time, i.e. after
      the point of no return, so it is rejected here at the source.

    Says nothing about the value itself: the label names the field, and
    the message never quotes the content.
    """
    if "\n" in value or "\r" in value:
        return f"{label} cannot contain a newline (the .env format has no multiline form)"
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return (
            f"{label} contains a character that cannot be stored in .env "
            "(the file is UTF-8; this usually means a keystroke your "
            "terminal did not decode as text). Retype it, or set the "
            "profile up in a UTF-8 terminal."
        )
    return None


def validate_secret(secret: str) -> Optional[str]:
    """None if the password is storable in .env, else an error message."""
    if not secret:
        return "password cannot be empty"
    return storable_error(secret, "password")


# ---------------------------------------------------------------------------
# Live validation
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    ok: bool
    kind: str      # ok | auth | tls | network | http | skipped | unexpected
    message: str   # already scrubbed; safe to print


def acquire_token(
    host: str,
    user: str,
    password: str,
    auth_source: str,
    verify_ssl: bool,
    *,
    timeout: int = _ACQUIRE_TIMEOUT,
) -> ValidationResult:
    """POST /api/auth/token/acquire and classify the outcome.

    Returns a printable classification and NOTHING else: never the
    token, never the response body, never a raw exception string. Bodies
    can echo request fields and exceptions can quote a URL, so both are
    reduced to a status code or an exception class name, and whatever
    survives is scrubbed of the password anyway (defense in depth).
    """
    try:
        import requests  # noqa: PLC0415 (optional at first-run time)
    except ImportError:
        return ValidationResult(
            False, "skipped",
            "python module 'requests' is not installed, so the credentials "
            "cannot be checked against the host right now",
        )
    try:  # quiet the self-signed-cert warning; cosmetic, never fatal
        import urllib3  # noqa: PLC0415

        if not verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    except Exception:  # noqa: BLE001 (cosmetic only)
        pass

    url = f"https://{host}{_ACQUIRE_PATH}"
    try:
        resp = requests.post(
            url,
            json={"username": user, "password": password, "authSource": auth_source},
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            verify=verify_ssl,
            timeout=timeout,
        )
    except Exception as exc:  # noqa: BLE001 (classified below, never re-raised)
        name = type(exc).__name__
        detail = _scrub(exc, [password])
        if "SSL" in name or "Certificate" in name:
            return ValidationResult(
                False, "tls",
                f"TLS verification failed ({name}): {detail}. If this host "
                "uses a self-signed certificate, answer 'no' to verify-SSL.",
            )
        if "Timeout" in name:
            return ValidationResult(
                False, "network",
                f"the host did not answer within {timeout}s ({name}): {detail}",
            )
        if "ConnectionError" in name or "ProxyError" in name:
            return ValidationResult(
                False, "network",
                f"the host could not be reached ({name}): {detail}",
            )
        return ValidationResult(
            False, "unexpected",
            f"the token request failed ({name}): {detail}",
        )

    status = getattr(resp, "status_code", 0)
    if status == 200:
        return ValidationResult(True, "ok", "token acquired")
    if status in (401, 403):
        return ValidationResult(
            False, "auth",
            f"the host answered but rejected the credentials (HTTP {status}). "
            "Check the user name and auth source, and retype the password.",
        )
    return ValidationResult(
        False, "http",
        f"unexpected response from the token endpoint (HTTP {status}); "
        "response body not shown",
    )


Validator = Callable[[str, str, str, str, bool], ValidationResult]


# ---------------------------------------------------------------------------
# Prompting
# ---------------------------------------------------------------------------

class Aborted(Exception):
    """User pressed Ctrl-D / Ctrl-C, or input ran out."""


def _ask_line(
    ask: Callable[[str], str],
    out: Callable[[str], None],
    label: str,
    *,
    default: Optional[str] = None,
    check: Optional[Callable[[str], Optional[str]]] = None,
) -> str:
    suffix = f" [{default}]" if default not in (None, "") else ""
    while True:
        try:
            raw = ask(f"{label}{suffix}: ")
        except (EOFError, KeyboardInterrupt):
            raise Aborted()
        value = (raw or "").strip()
        if not value and default is not None:
            value = default
        if check is not None:
            err = check(value)
            if err:
                out(f"  {err}")
                continue
        elif not value:
            out("  a value is required")
            continue
        return value


def _ask_bool(
    ask: Callable[[str], str],
    out: Callable[[str], None],
    label: str,
    default: bool,
) -> bool:
    hint = "Y/n" if default else "y/N"
    while True:
        try:
            raw = ask(f"{label} [{hint}]: ")
        except (EOFError, KeyboardInterrupt):
            raise Aborted()
        value = (raw or "").strip().lower()
        if not value:
            return default
        if value in ("y", "yes", "true", "1"):
            return True
        if value in ("n", "no", "false", "0"):
            return False
        out("  answer yes or no")


def _ask_password(
    ask_secret: Callable[[str], str],
    out: Callable[[str], None],
) -> str:
    """Silent prompt, entered twice. Never echoes, never reports the value."""
    while True:
        try:
            first = ask_secret("password (not echoed): ")
            second = ask_secret("password (again): ")
        except (EOFError, KeyboardInterrupt):
            raise Aborted()
        err = validate_secret(first)
        if err:
            out(f"  {err}")
            continue
        if first != second:
            out("  the two entries did not match; try again")
            continue
        return first


# ---------------------------------------------------------------------------
# Wizard
# ---------------------------------------------------------------------------

def _parse_args(argv: Sequence[str]) -> Tuple[Optional[Dict[str, object]], str, int]:
    """Return (options, message, exit_code). options is None to stop."""
    opts: Dict[str, object] = {"profile": None, "validate": True}
    args = list(argv)
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("-h", "--help"):
            return None, _USAGE, 0
        if arg.startswith("--password"):
            return None, _PASSWORD_ON_ARGV, 2
        if arg == "--no-validate":
            opts["validate"] = False
        elif arg == "--profile":
            i += 1
            if i >= len(args):
                return None, "--profile needs a value", 2
            opts["profile"] = args[i]
        elif arg.startswith("--profile="):
            opts["profile"] = arg.split("=", 1)[1]
        else:
            return None, f"unknown option: {arg}\n{_USAGE}", 2
        i += 1
    return opts, "", 0


def run_setup(
    argv: Optional[Sequence[str]] = None,
    *,
    root: Optional[Path] = None,
    ask: Optional[Callable[[str], str]] = None,
    ask_secret: Optional[Callable[[str], str]] = None,
    out: Callable[[str], None] = print,
    err: Optional[Callable[[str], None]] = None,
    validator: Optional[Validator] = None,
    isatty: Optional[Callable[[], bool]] = None,
) -> int:
    """Run the wizard. Returns 0 on success, 1 on abort, 2 on refusal.

    Every collaborator is injectable so the tests can drive the whole
    flow with a planted fake secret and assert it never reaches an
    output stream, without a TTY and without a network.
    """
    root = root or find_repo_root()
    ask = ask or input
    ask_secret = ask_secret or getpass.getpass
    if err is None:
        def err(line: str) -> None:  # noqa: F811
            print(line, file=sys.stderr)
    validator = validator or acquire_token
    if isatty is None:
        def isatty() -> bool:  # noqa: F811
            try:
                return bool(sys.stdin.isatty())
            except (AttributeError, ValueError):
                return False

    opts, message, code = _parse_args(argv if argv is not None else [])
    if opts is None:
        (out if code == 0 else err)(message.rstrip("\n"))
        return code

    # Non-interactive safety: never read a password from a pipe, never
    # hang a hook waiting for one.
    if not isatty():
        err(
            "vcfops setup needs an interactive terminal and stdin is not a "
            "TTY, so it is refusing to run (a piped or hook-driven run "
            "could read a password from the pipe, which RULE-008 "
            "forbids). Run it yourself in a terminal:\n"
            "    python3 -m vcfops_common setup\n"
            "Inside a Claude session, type it with a leading `!` so it runs "
            "interactively:\n"
            "    ! python3 -m vcfops_common setup"
        )
        return 2

    out("VCF Content Factory credential setup")
    out("  The password prompt is silent: what you type is never echoed,")
    out("  never stored in shell history, and never written to the session")
    out("  transcript. Everything else you type here is not secret.")
    out("")

    try:
        profile = _ask_line(
            ask, out, "profile name",
            default=(opts["profile"] or DEFAULT_PROFILE),  # type: ignore[arg-type]
            check=validate_profile_name,
        ).strip()

        env_path = root / ".env"
        prior = read_profile_defaults(env_path, profile)
        if prior:
            out(f"  profile '{profile}' already exists; press Enter to keep a value")

        host = ""
        while True:
            raw_host = _ask_line(ask, out, "host", default=prior.get("HOST"))
            host, host_err = normalize_host(raw_host)
            if host:
                break
            out(f"  {host_err}")

        user = _ask_line(ask, out, "user", default=prior.get("USER"))
        auth_source = _ask_line(
            ask, out, "auth source",
            default=prior.get("AUTH_SOURCE") or DEFAULT_AUTH_SOURCE,
        )
        prior_verify = prior.get("VERIFY_SSL")
        verify_default = (
            prior_verify.lower() not in ("false", "0", "no", "off")
            if prior_verify
            else DEFAULT_VERIFY_SSL
        )
        verify_ssl = _ask_bool(ask, out, "verify SSL certificate?", verify_default)

        while True:
            password = _ask_password(ask_secret, out)

            if not opts["validate"]:
                out("")
                out("Live validation skipped (--no-validate).")
                break

            out("")
            out(f"Checking these credentials against {host} ...")
            result = validator(host, user, password, auth_source, verify_ssl)
            # Only the classification is printed; the result message is
            # already scrubbed, and is scrubbed again here because a
            # caller-supplied validator is not trusted to have done it.
            if result.ok:
                out("  OK: the host accepted these credentials.")
                break
            out(f"  FAILED ({result.kind}): {_scrub(result.message, [password])}")

            if result.kind == "skipped":
                if _ask_bool(ask, out, "save the profile without checking it?", True):
                    break
                out("Nothing was written.")
                return 1
            if _ask_bool(ask, out, "re-enter the credentials?", True):
                if result.kind in ("tls", "network", "http"):
                    if _ask_bool(ask, out, "change the host or SSL settings too?", False):
                        while True:
                            raw_host = _ask_line(ask, out, "host", default=host)
                            new_host, host_err = normalize_host(raw_host)
                            if new_host:
                                host = new_host
                                break
                            out(f"  {host_err}")
                        user = _ask_line(ask, out, "user", default=user)
                        auth_source = _ask_line(ask, out, "auth source", default=auth_source)
                        verify_ssl = _ask_bool(
                            ask, out, "verify SSL certificate?", verify_ssl
                        )
                else:
                    user = _ask_line(ask, out, "user", default=user)
                    auth_source = _ask_line(ask, out, "auth source", default=auth_source)
                continue
            if _ask_bool(ask, out, "save this profile anyway (it did not work)?", False):
                break
            out("Nothing was written. Re-run the wizard when you have "
                "working credentials.")
            return 1

        values = {
            "HOST": host,
            "USER": user,
            "PASSWORD": password,
            "AUTH_SOURCE": auth_source,
            "VERIFY_SSL": "true" if verify_ssl else "false",
        }
        try:
            path, created = merge_profile_into_env(root, profile, values)
        except EnvReadError as exc:
            # Read failure, not a write failure: the existing file is
            # untouched, and telling the operator "could not write"
            # would send them after permissions when the real cause is
            # usually an editor that saved .env as UTF-16.
            err(f"could not READ the existing {root / '.env'} "
                f"({_scrub(exc, [password])}); it was left untouched and "
                "nothing was written. Check the file's encoding (it must "
                "be UTF-8) and that you can read it.")
            return 1
        except ValueError as exc:
            err(f"cannot store this profile: {_scrub(exc, [password])}. "
                "Nothing was written.")
            return 1
        except OSError as exc:
            err(f"could not write .env ({type(exc).__name__}): "
                f"{_scrub(exc, [password])}. Your existing .env was left "
                "unchanged (the new file is written alongside and swapped "
                "in only once it is complete).")
            return 1
    except Aborted:
        out("")
        out("Cancelled. Nothing was written.")
        return 1

    out("")
    verb = "created" if created else "updated"
    out(f"Profile '{profile}' {verb} in {path} (owner-only permissions"
        + ("; chmod is not applied on Windows" if os.name == "nt" else "")
        + ").")
    out("  The file's contents are deliberately not shown.")
    if profile.lower() != DEFAULT_PROFILE:
        out(f"  '{profile}' is not the default profile: pass --profile "
            f"{profile.lower()} to the CLIs, or set VCFOPS_PROFILE={profile.lower()}.")
    out("  Re-run this wizard any time to add another profile or rotate a "
        "password.")
    out("  Next: python3 -m vcfops_common doctor")
    return 0


def main(
    argv: Optional[Sequence[str]] = None,
    *,
    out: Callable[[str], None] = print,
    err: Optional[Callable[[str], None]] = None,
    **kw,
) -> int:
    """CLI entry.

    Belt-and-braces catch-all, mirroring ``doctor.main()``: this is the
    one function in the framework that holds a live password in its
    frame locals, so an unhandled exception must never print a
    traceback (which renders frame locals and chained exception
    payloads). Only the exception's CLASS NAME is reported.

    ``str(exc)`` and ``repr(exc)`` are both deliberately avoided:
    ``repr(UnicodeEncodeError)`` embeds the entire offending string,
    which at write time is the whole `.env` text, password included.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    if err is None:
        def err(line: str) -> None:  # noqa: F811
            print(line, file=sys.stderr)
    try:
        return run_setup(args, out=out, err=err, **kw)
    except (Aborted, KeyboardInterrupt):
        out("")
        out("Cancelled. Nothing was written.")
        return 1
    except Exception as exc:  # noqa: BLE001 (deliberate: no traceback, ever)
        err(
            f"vcfops setup failed unexpectedly ({type(exc).__name__}). "
            "Details are withheld on purpose: this command holds your "
            "password in memory and an error report could echo it "
            "(RULE-008). Your .env is never left half-written: it is "
            "either untouched or fully updated. Run "
            "`python3 -m vcfops_common doctor` to see which, then re-run "
            "`python3 -m vcfops_common setup`."
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

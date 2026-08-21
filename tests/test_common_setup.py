"""Tests for the credential wizard (bootstrap-v2 Phase 2).

Fast, offline, no real secrets: the token acquisition is always a stub
and the "password" is a planted marker string that the leak tests then
hunt for across stdout and stderr on every exit path.

Covered per the Phase 2 brief:
  - the profile is written and re-read correctly (through _env.py, the
    real consumer, not a private parser);
  - an existing profile is updated in place, not duplicated;
  - a planted fake secret never appears on stdout or stderr, on the
    success path and on every failure path;
  - non-TTY stdin refuses without prompting;
  - .env is created from .env.example when absent (with the template's
    placeholder credentials inert);
  - existing unrelated content and comments survive a merge.
"""
from __future__ import annotations

import os
import re
import stat
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vcfops_common import _env  # noqa: E402
from vcfops_common import setup_credentials as sc  # noqa: E402

# A marker that cannot occur by accident and exercises the awkward
# characters .env has to survive: quote, hash, space, backslash.
SECRET = "PLANTED-s3cr3t #'\" \\pw"
SIMPLE_SECRET = "PLANTED-simple-pw"


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------

class Driver:
    """Scripted stand-in for input()/getpass() plus captured streams."""

    def __init__(self, answers, secrets):
        self.answers = list(answers)
        self.secrets = list(secrets)
        self.out_lines = []
        self.err_lines = []
        self.prompts = []

    def ask(self, prompt):
        self.prompts.append(prompt)
        if not self.answers:
            raise EOFError
        return self.answers.pop(0)

    def ask_secret(self, prompt):
        self.prompts.append(prompt)
        if not self.secrets:
            raise EOFError
        return self.secrets.pop(0)

    def out(self, line):
        self.out_lines.append(str(line))

    def err(self, line):
        self.err_lines.append(str(line))

    @property
    def stdout(self):
        return "\n".join(self.out_lines)

    @property
    def stderr(self):
        return "\n".join(self.err_lines)

    @property
    def streams(self):
        return self.stdout + "\n" + self.stderr

    @property
    def prompt_text(self):
        return "\n".join(self.prompts)


def ok_validator(*args, **kw):
    return sc.ValidationResult(True, "ok", "token acquired")


def failing_validator(kind, message):
    def _v(*args, **kw):
        return sc.ValidationResult(False, kind, message)
    return _v


def run(tmp_path, answers, secrets, *, validator=ok_validator, argv=()):
    d = Driver(answers, secrets)
    code = sc.run_setup(
        list(argv),
        root=tmp_path,
        ask=d.ask,
        ask_secret=d.ask_secret,
        out=d.out,
        err=d.err,
        validator=validator,
        isatty=lambda: True,
    )
    return code, d


def read_env(tmp_path):
    return (tmp_path / ".env").read_text(encoding="utf-8")


def resolve(tmp_path, profile, monkeypatch):
    """Re-read a written profile the way the real CLIs do."""
    for key in [k for k in os.environ if k.startswith("VCFOPS_")]:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(_env, "_LOADED", False)
    monkeypatch.chdir(tmp_path)
    try:
        return _env.resolve_profile_credentials(profile)
    finally:
        monkeypatch.setattr(_env, "_LOADED", False)


# ---------------------------------------------------------------------------
# Write + re-read
# ---------------------------------------------------------------------------

def test_profile_is_written_and_read_back_by_env_resolver(tmp_path, monkeypatch):
    code, d = run(
        tmp_path,
        answers=["prod", "ops.example.com", "svc-user", "Local", "n"],
        secrets=[SECRET, SECRET],
    )
    assert code == 0
    creds = resolve(tmp_path, "prod", monkeypatch)
    assert creds.host == "ops.example.com"
    assert creds.user == "svc-user"
    assert creds.password == SECRET          # exact round-trip, quotes and all
    assert creds.auth_source == "Local"
    assert creds.verify_ssl is False
    assert creds.profile_name == "prod"


def test_defaults_are_profile_prod_local_and_verify_true(tmp_path, monkeypatch):
    # Empty answers accept every echoed default.
    code, d = run(
        tmp_path,
        answers=["", "ops.example.com", "svc-user", "", ""],
        secrets=[SIMPLE_SECRET, SIMPLE_SECRET],
    )
    assert code == 0
    creds = resolve(tmp_path, None, monkeypatch)
    assert (creds.profile_name, creds.auth_source, creds.verify_ssl) == (
        "prod", "Local", True)


def test_prompt_order_matches_the_brief(tmp_path):
    _, d = run(
        tmp_path,
        answers=["qa", "ops.example.com", "svc-user", "Local", "y"],
        secrets=[SIMPLE_SECRET, SIMPLE_SECRET],
    )
    labels = [p.split(" [")[0].split(":")[0] for p in d.prompts]
    assert labels[:7] == [
        "profile name", "host", "user", "auth source",
        "verify SSL certificate?", "password (not echoed)", "password (again)",
    ]


def test_host_url_paste_is_normalized_and_embedded_creds_rejected(tmp_path, monkeypatch):
    code, d = run(
        tmp_path,
        answers=[
            "prod",
            "https://user:pw@ops.example.com",   # rejected
            "https://ops.example.com/suite-api", # normalized
            "svc-user", "Local", "y",
        ],
        secrets=[SIMPLE_SECRET, SIMPLE_SECRET],
    )
    assert code == 0
    assert "must not contain credentials" in d.stdout
    assert resolve(tmp_path, "prod", monkeypatch).host == "ops.example.com"


def test_second_profile_does_not_disturb_the_first(tmp_path, monkeypatch):
    run(tmp_path, ["prod", "a.example.com", "u1", "Local", "y"],
        [SIMPLE_SECRET, SIMPLE_SECRET])
    run(tmp_path, ["devel", "b.example.com", "u2", "AD", "n"],
        [SECRET, SECRET])
    prod = resolve(tmp_path, "prod", monkeypatch)
    devel = resolve(tmp_path, "devel", monkeypatch)
    assert (prod.host, prod.user, prod.password) == (
        "a.example.com", "u1", SIMPLE_SECRET)
    assert (devel.host, devel.user, devel.password, devel.auth_source) == (
        "b.example.com", "u2", SECRET, "AD")


# ---------------------------------------------------------------------------
# Update in place, no duplicates
# ---------------------------------------------------------------------------

def test_existing_profile_is_updated_in_place_not_duplicated(tmp_path, monkeypatch):
    run(tmp_path, ["prod", "old.example.com", "olduser", "Local", "y"],
        ["old-password-value", "old-password-value"])
    first = read_env(tmp_path)
    run(tmp_path, ["prod", "new.example.com", "newuser", "AD", "n"],
        [SECRET, SECRET])
    text = read_env(tmp_path)

    for suffix in sc.PROFILE_SUFFIXES:
        key = "VCFOPS_PROD_" + suffix
        active = [
            ln for ln in text.splitlines()
            if re.match(r"^\s*(export\s+)?" + key + r"\s*=", ln)
        ]
        assert len(active) == 1, f"{key} defined {len(active)} times"

    assert "old.example.com" not in text
    assert "olduser" not in text
    assert "old-password-value" not in text
    creds = resolve(tmp_path, "prod", monkeypatch)
    assert (creds.host, creds.user, creds.password, creds.verify_ssl) == (
        "new.example.com", "newuser", SECRET, False)
    assert len(text.splitlines()) == len(first.splitlines())


def test_password_rotation_keeps_host_and_user_as_defaults(tmp_path, monkeypatch):
    run(tmp_path, ["prod", "keep.example.com", "keepuser", "Local", "n"],
        ["first-pw", "first-pw"])
    # Enter through host / user / auth source / verify: all defaults.
    code, d = run(tmp_path, ["prod", "", "", "", ""], [SECRET, SECRET])
    assert code == 0
    assert "already exists" in d.stdout
    creds = resolve(tmp_path, "prod", monkeypatch)
    assert (creds.host, creds.user, creds.verify_ssl) == (
        "keep.example.com", "keepuser", False)
    assert creds.password == SECRET


def test_prompt_defaults_never_expose_an_existing_password(tmp_path):
    run(tmp_path, ["prod", "keep.example.com", "keepuser", "Local", "y"],
        [SECRET, SECRET])
    _, d = run(tmp_path, ["prod", "", "", "", ""],
               [SIMPLE_SECRET, SIMPLE_SECRET])
    assert SECRET not in d.prompt_text
    assert SECRET not in d.streams
    # And the reader used for defaults never returns a PASSWORD value.
    defaults = sc.read_profile_defaults(tmp_path / ".env", "prod")
    assert "PASSWORD" not in defaults
    assert SECRET not in "".join(defaults.values())


# ---------------------------------------------------------------------------
# Leak hunting: the planted secret on every exit path
# ---------------------------------------------------------------------------

def test_no_secret_on_stdout_or_stderr_on_success(tmp_path):
    code, d = run(tmp_path, ["prod", "ops.example.com", "u", "Local", "y"],
                  [SECRET, SECRET])
    assert code == 0
    assert SECRET not in d.streams
    assert SECRET not in d.prompt_text


@pytest.mark.parametrize(
    "kind,message",
    [
        ("auth", "rejected"),
        ("tls", "certificate verify failed"),
        ("network", "could not be reached"),
        ("http", "unexpected response"),
        ("unexpected", "boom"),
    ],
)
def test_no_secret_on_any_validation_failure_path(tmp_path, kind, message):
    # Fail, decline re-entry, decline saving anyway: nothing written.
    code, d = run(
        tmp_path,
        answers=["prod", "ops.example.com", "u", "Local", "y", "n", "n"],
        secrets=[SECRET, SECRET],
        validator=failing_validator(kind, message),
    )
    assert code == 1
    assert not (tmp_path / ".env").exists(), "a known-bad profile was written"
    assert SECRET not in d.streams
    assert SECRET not in d.prompt_text


def test_a_validator_that_leaks_the_secret_is_scrubbed_before_printing(tmp_path):
    leaky = failing_validator("auth", f"rejected: password={SECRET} url=x")
    code, d = run(
        tmp_path,
        answers=["prod", "ops.example.com", "u", "Local", "y", "n", "n"],
        secrets=[SECRET, SECRET],
        validator=leaky,
    )
    assert code == 1
    assert SECRET not in d.streams
    assert "***" in d.stdout


def test_no_secret_when_the_env_write_fails(tmp_path, monkeypatch):
    def boom(*a, **kw):
        raise OSError(f"disk full while writing {SECRET}")
    monkeypatch.setattr(sc, "merge_profile_into_env", boom)
    code, d = run(tmp_path, ["prod", "ops.example.com", "u", "Local", "y"],
                  [SECRET, SECRET])
    assert code == 1
    assert SECRET not in d.streams


def test_no_secret_when_the_two_entries_mismatch(tmp_path):
    code, d = run(
        tmp_path,
        answers=["prod", "ops.example.com", "u", "Local", "y"],
        secrets=[SECRET, "typo", SECRET, SECRET],
    )
    assert code == 0
    assert "did not match" in d.stdout
    assert SECRET not in d.streams


def test_no_secret_on_abort(tmp_path):
    code, d = run(tmp_path, ["prod", "ops.example.com", "u", "Local", "y"],
                  [])  # EOF at the password prompt
    assert code == 1
    assert "Nothing was written" in d.stdout
    assert not (tmp_path / ".env").exists()


def test_scrub_redacts_raw_and_percent_encoded_forms():
    from urllib.parse import quote
    text = f"url=https://u:{quote(SECRET, safe='')}@h/x body={SECRET}"
    scrubbed = sc._scrub(text, [SECRET])
    assert SECRET not in scrubbed
    assert quote(SECRET, safe="") not in scrubbed
    assert "***" in scrubbed


def test_scrub_flattens_newlines_and_caps_length():
    scrubbed = sc._scrub("a\nb\r\n" + "x" * 5000, [])
    assert "\n" not in scrubbed and "\r" not in scrubbed
    assert len(scrubbed) <= sc._MAX_DETAIL + 3


# ---------------------------------------------------------------------------
# Non-TTY refusal
# ---------------------------------------------------------------------------

def test_non_tty_stdin_refuses_without_prompting(tmp_path):
    d = Driver([], [SECRET])
    code = sc.run_setup(
        [], root=tmp_path, ask=d.ask, ask_secret=d.ask_secret,
        out=d.out, err=d.err, validator=ok_validator, isatty=lambda: False,
    )
    assert code == 2
    assert d.prompts == []
    assert not (tmp_path / ".env").exists()
    assert "not a TTY" in d.stderr
    assert "! python3 -m vcfops_common setup" in d.stderr
    assert SECRET not in d.streams


def test_password_on_argv_is_refused(tmp_path):
    for arg in ("--password", "--password=" + SECRET):
        d = Driver([], [])
        code = sc.run_setup(
            [arg], root=tmp_path, ask=d.ask, ask_secret=d.ask_secret,
            out=d.out, err=d.err, validator=ok_validator, isatty=lambda: True,
        )
        assert code == 2
        assert d.prompts == []
        assert "RULE-008" in d.stderr
        assert SECRET not in d.streams


def test_unknown_option_and_help(tmp_path):
    d = Driver([], [])
    assert sc.run_setup(["--nope"], root=tmp_path, ask=d.ask,
                        ask_secret=d.ask_secret, out=d.out, err=d.err,
                        isatty=lambda: True) == 2
    d2 = Driver([], [])
    assert sc.run_setup(["--help"], root=tmp_path, ask=d2.ask,
                        ask_secret=d2.ask_secret, out=d2.out, err=d2.err,
                        isatty=lambda: True) == 0
    assert "credential wizard" in d2.stdout


# ---------------------------------------------------------------------------
# File creation and preservation
# ---------------------------------------------------------------------------

EXAMPLE = """\
# Copy to .env and fill in real credentials. NEVER commit .env.

# --- VCF Operations: prod profile ---
export VCFOPS_PROD_HOST=vcfops.lab.example.com
export VCFOPS_PROD_USER=svc-claude-poc
export VCFOPS_PROD_PASSWORD='change-me'
export VCFOPS_PROD_AUTH_SOURCE=Local
export VCFOPS_PROD_VERIFY_SSL=false

# --- Synology DSM ---
export SYNO_HOST=nas.lab.example.com
export SYNO_PASSWORD='change-me'
"""


def test_env_is_created_from_example_with_placeholders_inert(tmp_path, monkeypatch):
    (tmp_path / ".env.example").write_text(EXAMPLE, encoding="utf-8")
    code, d = run(tmp_path, ["prod", "real.example.com", "realuser", "Local", "n"],
                  [SECRET, SECRET])
    assert code == 0
    text = read_env(tmp_path)
    # The template's comments survive as documentation...
    assert "NEVER commit .env" in text
    assert "--- Synology DSM ---" in text
    # ...but no placeholder credential is live.
    assert not re.search(r"^\s*(export\s+)?SYNO_PASSWORD\s*=", text, re.M)
    assert "created" in d.stdout.lower()
    creds = resolve(tmp_path, "prod", monkeypatch)
    assert (creds.host, creds.user, creds.password) == (
        "real.example.com", "realuser", SECRET)
    # The placeholder slots were taken over, not shadowed by duplicates.
    assert len([ln for ln in text.splitlines()
                if re.match(r"^\s*(export\s+)?VCFOPS_PROD_HOST\s*=", ln)]) == 1
    # The template's fake prod credentials are gone, not merely shadowed.
    assert "vcfops.lab.example.com" not in text
    assert "svc-claude-poc" not in text


def test_env_is_created_when_example_is_absent(tmp_path, monkeypatch):
    code, _ = run(tmp_path, ["prod", "real.example.com", "u", "Local", "y"],
                  [SECRET, SECRET])
    assert code == 0
    assert (tmp_path / ".env").is_file()
    assert resolve(tmp_path, "prod", monkeypatch).password == SECRET


def test_unrelated_content_and_comments_survive(tmp_path, monkeypatch):
    original = (
        "# my hand-written notes\n"
        "\n"
        "# --- ssh ---\n"
        "export SSH_USER=scott   # inline comment\n"
        "OTHER_TOOL_TOKEN='keep me'\n"
        "\n"
        "# --- VCF Operations: qa ---\n"
        "export VCFOPS_QA_HOST=qa.example.com\n"
        "export VCFOPS_QA_USER=qauser\n"
        "export VCFOPS_QA_PASSWORD='qa-pw'\n"
    )
    (tmp_path / ".env").write_text(original, encoding="utf-8")
    code, _ = run(tmp_path, ["prod", "prod.example.com", "produser", "Local", "y"],
                  [SECRET, SECRET])
    assert code == 0
    text = read_env(tmp_path)
    for line in original.splitlines():
        if line.strip():
            assert line in text, f"lost line: {line!r}"
    qa = resolve(tmp_path, "qa", monkeypatch)
    assert (qa.host, qa.user, qa.password) == ("qa.example.com", "qauser", "qa-pw")


def test_no_export_prefix_style_is_preserved(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        "VCFOPS_QA_HOST=qa.example.com\nVCFOPS_QA_USER=qauser\n"
        "VCFOPS_QA_PASSWORD='qa-pw'\n",
        encoding="utf-8",
    )
    run(tmp_path, ["prod", "p.example.com", "u", "Local", "y"],
        [SIMPLE_SECRET, SIMPLE_SECRET])
    text = read_env(tmp_path)
    assert "export VCFOPS_PROD_HOST" not in text
    assert "VCFOPS_PROD_HOST=p.example.com" in text
    assert resolve(tmp_path, "prod", monkeypatch).password == SIMPLE_SECRET


@pytest.mark.skipif(os.name == "nt", reason="POSIX permissions only")
def test_env_file_is_owner_only(tmp_path):
    run(tmp_path, ["prod", "ops.example.com", "u", "Local", "y"],
        [SIMPLE_SECRET, SIMPLE_SECRET])
    mode = stat.S_IMODE((tmp_path / ".env").stat().st_mode)
    assert mode == 0o600


@pytest.mark.skipif(os.name == "nt", reason="POSIX permissions only")
def test_existing_loose_permissions_are_tightened(tmp_path):
    env = tmp_path / ".env"
    env.write_text("# pre-existing\n", encoding="utf-8")
    os.chmod(env, 0o644)
    run(tmp_path, ["prod", "ops.example.com", "u", "Local", "y"],
        [SIMPLE_SECRET, SIMPLE_SECRET])
    assert stat.S_IMODE(env.stat().st_mode) == 0o600


# ---------------------------------------------------------------------------
# Unit-level helpers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value", [
    SECRET, "simple", "with space", "has#hash", "has'quote", 'has"double',
    "trailing\\", "'balanced'", "=equals=", "  padded  ",
])
def test_format_value_round_trips_through_the_real_env_parser(
    tmp_path, monkeypatch, value
):
    (tmp_path / ".env").write_text(
        "VCFOPS_RT_HOST=h\nVCFOPS_RT_USER=u\n"
        f"VCFOPS_RT_PASSWORD={sc.format_value(value, always_quote=True)}\n",
        encoding="utf-8",
    )
    assert resolve(tmp_path, "rt", monkeypatch).password == value


def test_validate_secret_rejects_empty_and_multiline():
    assert sc.validate_secret("") is not None
    assert sc.validate_secret("a\nb") is not None
    assert sc.validate_secret("ok") is None


@pytest.mark.parametrize("name,bad", [
    ("prod", False), ("qa", False), ("my_lab2", False),
    ("", True), ("2prod", True), ("has-dash", True), ("has space", True),
    ("dot.name", True),
])
def test_validate_profile_name(name, bad):
    assert (sc.validate_profile_name(name) is not None) is bad


def test_acquire_token_classifies_without_leaking(monkeypatch):
    import types

    class Resp:
        def __init__(self, status):
            self.status_code = status

    fake = types.SimpleNamespace()

    def post_ok(*a, **kw):
        return Resp(200)

    def post_401(*a, **kw):
        return Resp(401)

    def post_500(*a, **kw):
        return Resp(500)

    class FakeSSLError(Exception):
        pass
    FakeSSLError.__name__ = "SSLError"

    class FakeConnectionError(Exception):
        pass
    FakeConnectionError.__name__ = "ConnectionError"

    class FakeTimeout(Exception):
        pass
    FakeTimeout.__name__ = "ConnectTimeout"

    def raiser(exc):
        def _p(*a, **kw):
            raise exc(f"boom with {SECRET} inside")
        return _p

    cases = [
        (post_ok, True, "ok"),
        (post_401, False, "auth"),
        (post_500, False, "http"),
        (raiser(FakeSSLError), False, "tls"),
        (raiser(FakeConnectionError), False, "network"),
        (raiser(FakeTimeout), False, "network"),
        (raiser(RuntimeError), False, "unexpected"),
    ]
    for post, ok, kind in cases:
        fake.post = post
        monkeypatch.setitem(sys.modules, "requests", fake)
        result = sc.acquire_token(
            "h.example.com", "u", SECRET, "Local", False, timeout=1)
        assert (result.ok, result.kind) == (ok, kind)
        assert SECRET not in result.message


def test_acquire_token_without_requests_reports_skipped(monkeypatch):
    # None in sys.modules makes `import requests` raise ImportError, which
    # is the first-run case: deps not installed yet.
    monkeypatch.setitem(sys.modules, "requests", None)
    result = sc.acquire_token("h", "u", SECRET, "Local", True)
    assert (result.ok, result.kind) == (False, "skipped")
    assert SECRET not in result.message


def test_no_validate_flag_skips_the_check(tmp_path, monkeypatch):
    def explode(*a, **kw):
        raise AssertionError("validator must not be called with --no-validate")
    code, d = run(
        tmp_path, ["prod", "ops.example.com", "u", "Local", "y"],
        [SECRET, SECRET], validator=explode, argv=["--no-validate"],
    )
    assert code == 0
    assert "skipped" in d.stdout.lower()
    assert resolve(tmp_path, "prod", monkeypatch).password == SECRET


def test_profile_flag_preseeds_the_prompt(tmp_path, monkeypatch):
    code, d = run(
        tmp_path, ["", "ops.example.com", "u", "Local", "y"],
        [SIMPLE_SECRET, SIMPLE_SECRET], argv=["--profile", "devel"],
    )
    assert code == 0
    assert "[devel]" in d.prompts[0]
    assert resolve(tmp_path, "devel", monkeypatch).host == "ops.example.com"
    assert "VCFOPS_PROFILE=devel" in d.stdout


def test_skipped_validation_offers_to_save(tmp_path, monkeypatch):
    code, d = run(
        tmp_path,
        answers=["prod", "ops.example.com", "u", "Local", "y", "y"],
        secrets=[SECRET, SECRET],
        validator=failing_validator("skipped", "'requests' is not installed"),
    )
    assert code == 0
    assert resolve(tmp_path, "prod", monkeypatch).password == SECRET
    assert SECRET not in d.streams


def test_retry_after_auth_failure_then_success(tmp_path, monkeypatch):
    calls = []

    def flaky(host, user, password, auth_source, verify_ssl):
        calls.append(user)
        if len(calls) == 1:
            return sc.ValidationResult(False, "auth", "HTTP 401")
        return sc.ValidationResult(True, "ok", "token acquired")

    code, d = run(
        tmp_path,
        # profile, host, user, auth, verify, retry?=y, user, auth
        answers=["prod", "ops.example.com", "wronguser", "Local", "y",
                 "y", "rightuser", "Local"],
        secrets=[SECRET, SECRET, SECRET, SECRET],
        validator=flaky,
    )
    assert code == 0
    assert calls == ["wronguser", "rightuser"]
    assert resolve(tmp_path, "prod", monkeypatch).user == "rightuser"
    assert SECRET not in d.streams


def test_save_anyway_after_declining_retry(tmp_path, monkeypatch):
    code, d = run(
        tmp_path,
        answers=["prod", "ops.example.com", "u", "Local", "y", "n", "y"],
        secrets=[SECRET, SECRET],
        validator=failing_validator("auth", "HTTP 401"),
    )
    assert code == 0
    assert resolve(tmp_path, "prod", monkeypatch).password == SECRET
    assert SECRET not in d.streams


def test_network_failure_allows_changing_the_host(tmp_path, monkeypatch):
    seen = []

    def flaky(host, user, password, auth_source, verify_ssl):
        seen.append((host, verify_ssl))
        if len(seen) == 1:
            return sc.ValidationResult(False, "tls", "certificate verify failed")
        return sc.ValidationResult(True, "ok", "token acquired")

    code, d = run(
        tmp_path,
        # profile, host, user, auth, verify=y, retry=y, change host=y,
        # host, user, auth, verify=n
        answers=["prod", "bad.example.com", "u", "Local", "y",
                 "y", "y", "good.example.com", "u", "Local", "n"],
        secrets=[SECRET, SECRET, SECRET, SECRET],
        validator=flaky,
    )
    assert code == 0
    assert seen == [("bad.example.com", True), ("good.example.com", False)]
    creds = resolve(tmp_path, "prod", monkeypatch)
    assert (creds.host, creds.verify_ssl) == ("good.example.com", False)
    assert SECRET not in d.streams


def test_in_place_update_keeps_each_line_own_export_style():
    lines = [
        "export VCFOPS_PROD_HOST=old",   # export style
        "VCFOPS_PROD_USER=olduser",      # no export, in the same file
    ]
    merged = sc.merge_profile_lines(lines, "prod", {"HOST": "new", "USER": "u2"})
    assert merged[0] == "export VCFOPS_PROD_HOST=new"
    assert merged[1] == "VCFOPS_PROD_USER=u2"


def test_merge_profile_lines_neutralizes_earlier_duplicates():
    lines = [
        "export VCFOPS_PROD_HOST=a",
        "# unrelated",
        "export VCFOPS_PROD_HOST=b",
    ]
    merged = sc.merge_profile_lines(lines, "prod", {"HOST": "c"})
    active = [ln for ln in merged
              if re.match(r"^\s*(export\s+)?VCFOPS_PROD_HOST\s*=", ln)]
    assert active == ["export VCFOPS_PROD_HOST=c"]
    assert "# unrelated" in merged


# ---------------------------------------------------------------------------
# Durability of .env (framework review B-1): a failed write must never
# destroy the operator's other profiles. .env is gitignored, so a
# zero-byte file is unrecoverable.
# ---------------------------------------------------------------------------

PRE_EXISTING = (
    "# hand-written note\n"
    "OTHER_TOKEN='keep me'\n"
    "export VCFOPS_QA_HOST=qa.example.com\n"
    "export VCFOPS_QA_USER=qauser\n"
    "export VCFOPS_QA_PASSWORD='qa-pw'\n"
)


def test_failed_write_leaves_env_byte_identical_and_no_temp_behind(tmp_path):
    env = tmp_path / ".env"
    env.write_text(PRE_EXISTING, encoding="utf-8")
    before = env.read_bytes()

    real_fdopen = os.fdopen

    def exploding_fdopen(fd, *a, **kw):
        fh = real_fdopen(fd, *a, **kw)

        class Exploding:
            def __enter__(self_inner):
                fh.__enter__()
                return self_inner

            def __exit__(self_inner, *exc):
                return fh.__exit__(*exc)

            def write(self_inner, _text):
                raise OSError(28, "No space left on device")

            def __getattr__(self_inner, name):
                return getattr(fh, name)

        return Exploding()

    monkey = pytest.MonkeyPatch()
    monkey.setattr(sc.os, "fdopen", exploding_fdopen)
    try:
        code, d = run(tmp_path, ["prod", "ops.example.com", "u", "Local", "y"],
                      [SECRET, SECRET])
    finally:
        monkey.undo()

    assert code == 1
    assert env.read_bytes() == before, "the operator's .env was damaged"
    assert "qa-pw" in env.read_text(encoding="utf-8")
    assert "OTHER_TOKEN" in env.read_text(encoding="utf-8")
    siblings = [p.name for p in tmp_path.iterdir() if p.name.startswith(".env.")]
    assert siblings == [], f"temp file left behind: {siblings}"
    assert SECRET not in d.streams


def test_failed_write_says_the_existing_file_survived(tmp_path):
    env = tmp_path / ".env"
    env.write_text(PRE_EXISTING, encoding="utf-8")

    def boom(*a, **kw):
        raise OSError(13, "Permission denied")

    monkey = pytest.MonkeyPatch()
    monkey.setattr(sc, "write_env_file", boom)
    try:
        code, d = run(tmp_path, ["prod", "ops.example.com", "u", "Local", "y"],
                      [SECRET, SECRET])
    finally:
        monkey.undo()
    assert code == 1
    assert "left unchanged" in d.stderr
    assert SECRET not in d.streams


def test_unreadable_env_reports_a_read_failure_not_a_write_failure(tmp_path):
    env = tmp_path / ".env"
    env.write_bytes(PRE_EXISTING.encode("utf-16"))   # an editor saved UTF-16
    before = env.read_bytes()
    code, d = run(tmp_path, ["prod", "ops.example.com", "u", "Local", "y"],
                  [SECRET, SECRET])
    assert code == 1
    assert "could not READ" in d.stderr
    assert "could not write" not in d.stderr
    assert env.read_bytes() == before
    assert SECRET not in d.streams


def test_write_env_file_replaces_the_target_of_a_symlink(tmp_path):
    real = tmp_path / "elsewhere.env"
    real.write_text("# original\n", encoding="utf-8")
    link = tmp_path / ".env"
    link.symlink_to(real)
    sc.write_env_file(link, ["VCFOPS_PROD_HOST=h"])
    assert link.is_symlink(), "the symlink was replaced by a regular file"
    assert real.read_text(encoding="utf-8").strip() == "VCFOPS_PROD_HOST=h"


# ---------------------------------------------------------------------------
# Unstorable values (framework review W-1 / W-2)
# ---------------------------------------------------------------------------

LONE_SURROGATE = "pw\udcff"   # what surrogateescape yields for a stray byte


def test_password_that_utf8_cannot_encode_is_rejected_at_the_prompt(tmp_path):
    env = tmp_path / ".env"
    env.write_text(PRE_EXISTING, encoding="utf-8")
    before = env.read_bytes()
    code, d = run(
        tmp_path,
        answers=["prod", "ops.example.com", "u", "Local", "y"],
        # first attempt unstorable, second fine
        secrets=[LONE_SURROGATE, LONE_SURROGATE, SIMPLE_SECRET, SIMPLE_SECRET],
    )
    assert code == 0
    assert "cannot be stored" in d.stdout
    assert LONE_SURROGATE not in d.streams
    text = env.read_text(encoding="utf-8")
    assert "qa-pw" in text and "OTHER_TOKEN" in text
    assert env.read_bytes() != before  # the good password did get written


def test_newline_in_a_non_password_field_cannot_shadow_the_password(tmp_path, monkeypatch):
    """_env.py keeps the FIRST definition of a key, so a value carrying a
    newline could inject a duplicate PASSWORD line that shadows the one
    the wizard validated. Every field is guarded, not just the secret."""
    injected = "u\nVCFOPS_PROD_PASSWORD=injected"
    code, d = run(
        tmp_path,
        answers=["prod", "ops.example.com", injected, "Local", "y"],
        secrets=[SECRET, SECRET],
    )
    assert code == 1
    assert not (tmp_path / ".env").exists()
    assert "cannot store this profile" in d.stderr
    assert "USER" in d.stderr          # names the field...
    assert "injected" not in d.stderr  # ...but never quotes the value
    assert SECRET not in d.streams


def test_merge_rejects_unstorable_values_before_touching_the_file(tmp_path):
    env = tmp_path / ".env"
    env.write_text(PRE_EXISTING, encoding="utf-8")
    before = env.read_bytes()
    with pytest.raises(ValueError):
        sc.merge_profile_into_env(tmp_path, "prod", {"USER": "a\nb"})
    with pytest.raises(ValueError):
        sc.merge_profile_into_env(tmp_path, "prod", {"PASSWORD": LONE_SURROGATE})
    assert env.read_bytes() == before


def test_storable_error_names_the_field_without_quoting_the_value():
    assert sc.storable_error("fine", "USER") is None
    msg = sc.storable_error("a\nb", "USER")
    assert msg and "USER" in msg and "a\nb" not in msg
    msg = sc.storable_error(LONE_SURROGATE, "PASSWORD")
    assert msg and "PASSWORD" in msg and LONE_SURROGATE not in msg


# ---------------------------------------------------------------------------
# main() catch-all (framework review W-1)
# ---------------------------------------------------------------------------

def test_main_never_prints_a_traceback_or_the_secret(tmp_path, monkeypatch):
    def leaky(*a, **kw):
        raise RuntimeError(f"leaky {SECRET} boom")

    monkeypatch.setattr(sc, "run_setup", leaky)
    d = Driver([], [])
    code = sc.main([], out=d.out, err=d.err)
    assert code == 1
    assert SECRET not in d.streams
    assert "RuntimeError" in d.stderr        # class name only...
    assert "leaky" not in d.stderr           # ...never the message
    assert "Traceback" not in d.streams


def test_main_reports_a_unicode_error_without_echoing_the_payload(tmp_path, monkeypatch):
    def raiser(*a, **kw):
        # repr() of this exception embeds the whole offending string,
        # which at write time would be the entire .env text.
        return "x".encode("ascii") + LONE_SURROGATE.encode("utf-8")

    monkeypatch.setattr(sc, "run_setup", raiser)
    d = Driver([], [])
    code = sc.main([], out=d.out, err=d.err)
    assert code == 1
    assert "UnicodeEncodeError" in d.stderr
    assert LONE_SURROGATE not in d.streams


def test_main_abort_goes_through_the_injected_out(tmp_path, monkeypatch):
    def aborter(*a, **kw):
        raise sc.Aborted()

    monkeypatch.setattr(sc, "run_setup", aborter)
    d = Driver([], [])
    assert sc.main([], out=d.out, err=d.err) == 1
    assert "Cancelled" in d.stdout
    assert d.stderr == ""


def test_doctor_hands_off_the_exact_wizard_command(tmp_path):
    """The concierge checklist must name the command the user types.

    'run the credential wizard' is not actionable; the orchestrator has
    to tell the user the literal string, with the `!` prefix, or it will
    invent a way to collect the password itself.
    """
    from vcfops_common import doctor

    items = doctor.build_checklist(
        tmp_path, doctor.EnvSanity(), False, [], {})
    creds = [i for i in items if i["id"] == "credentials"][0]
    assert "! python3 -m vcfops_common setup" in creds["detail"]

    lines = []
    doctor.run_doctor(
        tmp_path,
        git=lambda args, timeout=0: (1, ""),
        check_import=lambda name: True,
        environ={"VCFOPS_PROD_HOST": "h", "VCFOPS_PROD_USER": "u",
                 "VCFOPS_PROD_PASSWORD": "p"},
        out=lines.append,
    )
    # (that run has a complete profile, so only the checklist path above
    # carries the handoff; assert the no-profile path too)
    lines = []
    doctor.run_doctor(
        tmp_path,
        git=lambda args, timeout=0: (1, ""),
        check_import=lambda name: True,
        environ={},
        out=lines.append,
    )
    text = "\n".join(lines)
    assert "! python3 -m vcfops_common setup" in text


def test_find_repo_root_is_not_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = sc.find_repo_root()
    assert (root / "src" / "vcfops_common" / "setup_credentials.py").is_file()
    assert root != tmp_path

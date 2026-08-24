"""Guards for the shipped PowerShell installer (issues #106 and #104).

install.ps1 runs on customers' Windows machines, so native-Windows
correctness is in scope even though the factory itself is POSIX-only
(RULE-018 carves out shipped artifacts).

Two layers here:

1. Static checks that run everywhere, including the Linux-only CI runner.
   They pin the shape of the TLS gate and the advisory feature so a future
   edit cannot silently re-nest or delete them.
2. A behaviour harness executed by whatever PowerShell is available
   (``pwsh``), skipped when there is none.

Neither layer proves Windows PowerShell 5.1 compatibility: 5.1 is
.NET Framework and does not exist off Windows.  Only a windows-latest
runner can prove that.  See knowledge/context/authoring/guide_powershell.md.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = REPO_ROOT / "src" / "vcfops_packaging" / "templates" / "install.ps1"
HARNESS = Path(__file__).resolve().parent / "fixtures" / "install_ps1_advisory_harness.ps1"


@pytest.fixture(scope="module")
def script_text() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Issue #106 -- TLS 1.2 must not be gated on -SkipSslVerify
# ---------------------------------------------------------------------------
class TestTlsGate:
    def test_security_protocol_is_set_exactly_once(self, script_text: str) -> None:
        hits = re.findall(r"ServicePointManager\]::SecurityProtocol\s*=", script_text)
        assert len(hits) == 1, (
            "SecurityProtocol should be assigned once, at script startup. "
            f"Found {len(hits)} assignments."
        )

    def test_security_protocol_ors_rather_than_replaces(self, script_text: str) -> None:
        # A bare assignment would downgrade a machine already permitting TLS 1.3.
        assert re.search(
            r"ServicePointManager\]::SecurityProtocol\s*=\s*\n?\s*"
            r"\[System\.Net\.ServicePointManager\]::SecurityProtocol\s+-bor\s+"
            r"\[System\.Net\.SecurityProtocolType\]::Tls12",
            script_text,
        ), "TLS 1.2 must be OR-ed into the existing SecurityProtocol value"

    def test_tls_block_is_not_nested_under_skipsslverify(self, script_text: str) -> None:
        """The reported bug: only operators disabling cert checks got TLS 1.2.

        Checked structurally by indentation.  The assignment lives inside the
        `PSVersion.Major -lt 6` guard (4 spaces) and nothing deeper, so a
        re-nesting under `if ($SkipSslVerify)` would push it to 8.
        """
        for line in script_text.splitlines():
            if "ServicePointManager]::SecurityProtocol =" in line:
                indent = len(line) - len(line.lstrip())
                assert indent == 4, f"TLS assignment is nested too deep: {line!r}"

    def test_tls_assignment_precedes_first_skipsslverify_branch(self, script_text: str) -> None:
        tls_at = script_text.index("ServicePointManager]::SecurityProtocol =")
        branch_at = script_text.index("if ($SkipSslVerify) {")
        assert tls_at < branch_at, "TLS 1.2 must be set before any request or bypass branch"

    def test_duplicate_trustall_class_is_gone(self, script_text: str) -> None:
        assert "public class TrustAllCertsVcf2" not in script_text, (
            "the second near-duplicate policy class should be collapsed into "
            "Disable-CertificateValidationLegacy"
        )
        assert script_text.count("public class TrustAllCertsVcf ") == 1

    def test_param_variable_is_not_shadowed_by_script_scope_state(
        self, script_text: str
    ) -> None:
        """`param()` variables are already script-scope in a script.

        `$script:SkipSslVerify = $false` was therefore the same variable as
        the `-SkipSslVerify` switch and clobbered it, making both cert-bypass
        call sites dead code and turning the post-prompt guard into
        `X -and -not X`.
        """
        # Comment lines are exempt: the fix documents the old name on purpose.
        offenders = [
            (i, line.strip())
            for i, line in enumerate(script_text.splitlines(), 1)
            if "$script:SkipSslVerify" in line and not line.lstrip().startswith("#")
        ]
        assert not offenders, (
            f"internal prompt state must not share a name with the parameter: {offenders}"
        )
        assert "$script:SslPromptDeclined = $false" in script_text
        assert "if ($script:SslPromptDeclined) {" in script_text

    def test_cert_bypass_helper_guards_both_ps_version_and_type_redefinition(
        self, script_text: str
    ) -> None:
        start = script_text.index("function Disable-CertificateValidationLegacy")
        body = script_text[start:start + 1600]
        assert "if ($PSVersionTable.PSVersion.Major -ge 6) { return }" in body, (
            "ICertificatePolicy does not exist on .NET Core; PS 7+ must return early"
        )
        assert "if (-not ('TrustAllCertsVcf' -as [type]))" in body, (
            "Add-Type cannot redefine a type already present in the session"
        )


# ---------------------------------------------------------------------------
# Issue #104 -- advisory parity with install.py
# ---------------------------------------------------------------------------
class TestAdvisoryFeature:
    def test_helpers_exist(self, script_text: str) -> None:
        for fn in (
            "function Get-BoundedNames",
            "function Get-DashboardAdvisoryNames",
            "function Get-ViewAdvisoryNames",
            "function Get-AllSkippedSummaries",
            "function Write-AdvisoryTrailer",
        ):
            assert fn in script_text, f"missing {fn}"

    def test_flag_condition_matches_python(self, script_text: str) -> None:
        assert "if ($imported -eq 0 -and $skipped -gt 0)" in script_text, (
            "imported==0 AND skipped>0 is the whole test; warning on any skip "
            "cries wolf on every re-sync"
        )

    def test_mid_stream_summary_warn_matches_install_py(self, script_text: str) -> None:
        """The mid-stream WARN keeps the skipped>0 term, matching install.py.

        Narrowing it to imported=0 (as an apparent cry-wolf fix) was a
        regression: the named advisory that replaced it covers DASHBOARDS and
        VIEW_DEFINITIONS only, so SUPER_METRICS and REPORTS were left with no
        signal at all. If this is ever narrowed, both templates narrow
        together.
        """
        assert (
            'if (($osState -ne "FINISHED" -and $osState -ne "") '
            '-or $osFailed -gt 0 -or $osSkipped -gt 0) {'
        ) in script_text
        py = (REPO_ROOT / "src" / "vcfops_packaging" / "templates" / "install.py").read_text(
            encoding="utf-8"
        )
        assert (
            'if os_state not in ("FINISHED", "") or os_failed > 0 or os_skipped > 0:'
        ) in py, "install.py's condition moved; the PowerShell mirror must move with it"

    def test_status_envelope_is_read_through_probes(self, script_text: str) -> None:
        """StrictMode + $ErrorActionPreference='Stop' makes a dot-access to a
        missing field a terminating error, and this code runs AFTER content
        has been imported: an escape leaves a partial install.
        """
        assert "function Get-PropValue" in script_text
        assert "function Write-ImportSummaryWarnings" in script_text
        for unguarded in (
            "if ($s.operationSummaries)",
            "foreach ($os in $s.operationSummaries)",
            "if ($os.state)",
            "if ($os.failed)",
            "if ($os.skipped)",
            "$($os.imported)",
            "$state = $s.state",
            "if ($s.endTime)",
        ):
            assert unguarded not in script_text, (
                f"unguarded property access {unguarded!r} throws when the field is absent"
            )

    def test_advisories_never_reach_the_warnings_list(self, script_text: str) -> None:
        start = script_text.index("function Install-Dashboard")
        body = script_text[start:script_text.index("function Install-SmEnable")]
        assert "$Ctx.Advisories.Add(" in body
        assert "$Ctx.Warnings.Add(" not in body, (
            "advisories must not fail an install that genuinely succeeded"
        )

    def test_trailer_printed_in_both_summary_branches(self, script_text: str) -> None:
        start = script_text.index("function Invoke-Install {")
        body = script_text[start:script_text.index("function Invoke-Uninstall {")]
        assert body.count("Write-AdvisoryTrailer -Advisories") == 2, (
            "the trailer prints in the warning branch and the success branch"
        )
        assert "Done. No failures, but see the attention list at the end of this output." in body
        assert "Done. All content installed successfully." in body

    def test_bounding_constants_match_python(self, script_text: str) -> None:
        assert "$script:AdvisoryNameMaxChars = 120" in script_text
        assert "$script:AdvisoryNamesMax = 20" in script_text
        py = (REPO_ROOT / "src" / "vcfops_packaging" / "templates" / "install.py").read_text(
            encoding="utf-8"
        )
        assert "_ADVISORY_NAME_MAX_CHARS = 120" in py
        assert "_ADVISORY_NAMES_MAX = 20" in py


# ---------------------------------------------------------------------------
# PS 5.1 hygiene (static; see module docstring for the verification ceiling)
# ---------------------------------------------------------------------------
class TestPowerShellCompat:
    def test_ascii_only(self, script_text: str) -> None:
        bad = [
            (i, line)
            for i, line in enumerate(script_text.splitlines(), 1)
            if any(ord(ch) > 126 for ch in line)
        ]
        assert not bad, f"non-ASCII causes mojibake under 5.1 default encoding: {bad[:5]}"

    def test_no_ps7_only_operators(self, script_text: str) -> None:
        """Scans the raw lines, comments included.

        Stripping at the first `#` truncates on a `#` inside a string literal
        and blinds the check for the rest of that line, so nothing is
        stripped. A comment that merely mentions `&&` would be a false
        positive; that is the cheap direction to be wrong in.
        """
        offenders = []
        for i, line in enumerate(script_text.splitlines(), 1):
            hits = [op for op in ("??", "?.", "&&", "||") if op in line]
            # PowerShell 7 ternary: `<cond> ? <a> : <b>`. A bare `?` bounded by
            # whitespace has no other meaning in 5.1-compatible source.
            if re.search(r"\s\?\s", line):
                hits.append("ternary ? :")
            if hits:
                offenders.append((i, hits, line.strip()))
        assert not offenders, f"PS 7-only syntax is a parse error on 5.1: {offenders[:5]}"


# ---------------------------------------------------------------------------
# Shipped-template signal hygiene (both installers)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("template", ["install.py", "install.ps1"])
def test_no_false_template_version_stamp(template: str) -> None:
    """Neither shipped installer may carry its own version stamp.

    Both templates used to declare `TEMPLATE_VERSION = "2026-04-18-1"` with a
    comment claiming it was injected at build time and read by
    `check-staleness`. Both sentences were false: `builder.py` and
    `discrete_builder.py` copy the templates verbatim (`read_text` ->
    `writestr`), and `cmd_check_staleness` reads `template_version` out of the
    zip's `vcfops_manifest.json`, which the builders stamp from
    `template_version.CURRENT_TEMPLATE_VERSION`.

    A stale literal sitting in customer-facing code claiming to be the
    staleness signal is worse than no signal: it is what a reader diagnosing
    a staleness problem finds first.
    """
    text = (REPO_ROOT / "src" / "vcfops_packaging" / "templates" / template).read_text(
        encoding="utf-8"
    )
    # \b does not match inside CURRENT_TEMPLATE_VERSION (underscore is a word
    # character), so this pins the bare stamp only.
    hits = [
        (i, line.strip())
        for i, line in enumerate(text.splitlines(), 1)
        if re.search(r"\bTEMPLATE_VERSION\b", line)
    ]
    assert not hits, f"{template} carries a template version stamp: {hits}"
    assert "injected at build time" not in text, (
        f"{template} still claims a build-time stamp that does not happen"
    )


# ---------------------------------------------------------------------------
# Issue #101 -- shipped templates must pin text encoding explicitly
# ---------------------------------------------------------------------------
SHIPPED_PY_TEMPLATES = [
    ("vcfops_packaging", "install.py"),
    ("vcfops_managementpacks", "post-install.py"),
]


@pytest.mark.parametrize("package,template", SHIPPED_PY_TEMPLATES)
def test_shipped_templates_pin_text_encoding(package: str, template: str) -> None:
    """Every text-mode I/O call in a shipped Python template names its encoding.

    RULE-018 makes the factory POSIX-only, but it explicitly does not govern
    the artifacts the factory ships.  These two run on a customer's machine,
    which may be native Windows, where Python defaults text I/O to cp1252.  A
    view name carrying a non-cp1252 character then fails to decode on the
    customer's box, not ours.  On POSIX this is a no-op (already UTF-8) except
    under LANG=C, where it turns a crash into a success.

    The scan is AST-based on purpose: a flat grep reports a multi-line call as
    a violation when the argument is simply on a later line.
    """
    import ast

    path = REPO_ROOT / "src" / package / "templates" / template
    tree = ast.parse(path.read_text(encoding="utf-8"))
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute):
            name = func.attr
        elif isinstance(func, ast.Name):
            name = func.id
        else:
            continue
        if name not in {"open", "read_text", "write_text"}:
            continue
        if name == "open":
            mode = None
            if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                mode = node.args[1].value
            for kw in node.keywords:
                if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                    mode = kw.value.value
            # Binary mode has no encoding; passing one is a TypeError.
            if isinstance(mode, str) and "b" in mode:
                continue
        if "encoding" not in {kw.arg for kw in node.keywords}:
            offenders.append((node.lineno, name))
    assert not offenders, (
        f"{template} has text I/O with no explicit encoding= at {offenders}"
    )


# ---------------------------------------------------------------------------
# Issue #108 -- the SM ghost-state retry is SUPER_METRICS only
# ---------------------------------------------------------------------------
class TestSmGhostStateRetryStaysNarrow:
    """Anti-generalisation pins for the retry ported in #108.

    #114 bisected the identical `imported=0/skipped=N` signature on the
    dashboard and view paths and found an unrelated cause: create-only mode
    (`force=false`), where the skip is idempotent and a retry is a guaranteed
    no-op that still costs a round trip plus a 30s import-busy backoff.
    Evidence: knowledge/context/api-surface/content_import_skip_semantics.md.

    The behavioural half lives in the harness; these are the cheap static pins
    that survive a runner with no PowerShell.
    """

    def test_only_super_metrics_content_type_is_tested(self, script_text: str) -> None:
        body = re.search(
            r"function Get-SmGhostStateSkipCount \{(.*?)\n\}\n",
            script_text,
            re.S,
        )
        assert body, "Get-SmGhostStateSkipCount not found in install.ps1"
        code = "\n".join(
            line for line in body.group(1).splitlines() if not line.strip().startswith("#")
        )
        for content_type in ("DASHBOARDS", "VIEW_DEFINITIONS", "REPORTS"):
            assert content_type not in code, (
                f"{content_type} must not participate in the SM ghost-state retry"
            )
        assert code.count("SUPER_METRICS") == 1, (
            "exactly one contentType comparison, against SUPER_METRICS"
        )

    def test_install_dashboard_does_not_call_the_sm_retry(
        self, script_text: str
    ) -> None:
        body = re.search(
            r"function Install-Dashboard\(\$Ctx\) \{(.*?)\n\}\n", script_text, re.S
        )
        assert body, "Install-Dashboard not found in install.ps1"
        assert "Get-SmGhostStateSkipCount" not in body.group(1), (
            "the SM ghost-state retry must not be wired into the dashboard path"
        )

    def test_install_supermetrics_retries_the_same_zip(self, script_text: str) -> None:
        body = re.search(
            r"function Install-Supermetrics\(\$Ctx\) \{(.*?)\n\}\n", script_text, re.S
        )
        assert body, "Install-Supermetrics not found in install.ps1"
        code = body.group(1)
        assert "$null = Import-ContentZip" not in code.split("Get-SmGhostStateSkipCount")[0], (
            "the first import's status must be captured, not discarded"
        )
        assert '-Label "super metrics (retry)"' in code, (
            "the retry must re-import the same zip under a distinguishable label"
        )

    def test_python_installer_keeps_its_side_of_the_parity(self) -> None:
        """The port is only meaningful while both sides agree."""
        py = (
            REPO_ROOT / "src" / "vcfops_packaging" / "templates" / "install.py"
        ).read_text(encoding="utf-8")
        assert 'contentType") == "SUPER_METRICS"' in py, (
            "install.py lost the SUPER_METRICS filter the PowerShell port mirrors"
        )
        assert "super metrics (retry)" in py, (
            "install.py lost the ghost-state retry install.ps1 now mirrors"
        )


# ---------------------------------------------------------------------------
# Create-on-failed-lookup: the class the #109 sweep introduced
# ---------------------------------------------------------------------------
class TestFailedLookupsDoNotMutate:
    """A converted lookup must not let an error envelope look like "not found".

    `Get-PropList` returns `@()` for an error envelope, which is right for a
    reader and wrong for a decision. A lookup that branches on emptiness then
    takes the not-found branch on a request it knows failed: on
    `Upsert-CustomGroup` that CREATED a duplicate custom group and printed
    "OK  Created", and on the uninstall paths it claimed "already removed?"
    about an instance it had failed to read. Pre-sweep these sites threw,
    which was uglier and safer.

    The behavioural coverage is in the harness (it asserts zero POST/PUT/DELETE
    after a failed lookup). These are the static pins that survive a runner
    with no PowerShell.
    """

    # Every function whose lookup result drives a mutation or a state claim.
    GUARDED = [
        "Upsert-CustomGroup",
        "Get-SupermetricsByName",
        "Find-CustomGroupIds",
        "Install-Symptoms",
        "Install-Alerts",
        "Uninstall-Symptoms",
        "Uninstall-Alerts",
    ]

    @pytest.mark.parametrize("func", GUARDED)
    def test_lookup_is_status_checked(self, script_text: str, func: str) -> None:
        body = re.search(
            rf"function {re.escape(func)}[ (](.*?)\n\}}\n", script_text, re.S
        )
        assert body, f"{func} not found in install.ps1"
        assert "Assert-LookupOk" in body.group(1), (
            f"{func} branches on a lookup result without checking the status "
            "first; an error envelope will be read as 'not found'"
        )

    def test_guard_refuses_rather_than_warning(self, script_text: str) -> None:
        body = re.search(
            r"function Assert-LookupOk \{(.*?)\n\}\n", script_text, re.S
        )
        assert body, "Assert-LookupOk not found in install.ps1"
        assert "Write-Fail" in body.group(1), (
            "the guard must stop, not warn: we do not know what is on the "
            "instance, so continuing means guessing"
        )

    def test_status_classification_is_consistent(self, script_text: str) -> None:
        """Get-StatusCode and Get-PropValue must agree on what an error envelope is.

        This diff routes the same object through both. If one treats a shape as
        a hashtable error envelope and the other as a PSCustomObject, a
        "checked the status" guard silently stops guarding.
        """
        body = re.search(r"function Get-StatusCode\(\$resp\) \{(.*?)\n\}\n", script_text, re.S)
        assert body, "Get-StatusCode not found"
        # Comments are stripped: the body explains why [hashtable] is wrong,
        # and that prose must not trip the check on the code.
        code = "\n".join(
            ln for ln in body.group(1).splitlines() if not ln.strip().startswith("#")
        )
        assert "[System.Collections.IDictionary]" in code, (
            "Get-StatusCode must classify with IDictionary, matching Get-PropValue"
        )
        assert "[hashtable]" not in code, (
            "the narrower [hashtable] test diverges from Get-PropValue"
        )


# ---------------------------------------------------------------------------
# The output-purity pin must stay receiver-keyed
# ---------------------------------------------------------------------------
def test_void_call_allowlist_is_receiver_keyed() -> None:
    """The harness's void-call allowlist must key on RECEIVER.METHOD.

    This pin exists because the first version of that allowlist keyed on the
    method name and listed "Add" -- while its own comment cited
    `ArrayList.Add()` as the classic instance of the bug. It therefore excused
    exactly the trap it was written to catch: injecting an ArrayList `.Add()`
    into `Import-ContentZip` passed the whole suite while flipping the return
    type from PSCustomObject to Object[] and silently disabling the #108
    ghost-state retry.

    `[List[T]].Add` is void; `[ArrayList].Add` returns the insertion index.
    The method name cannot decide, so an entry that is not receiver-qualified
    is not a weaker check, it is a broken one.
    """
    text = HARNESS.read_text(encoding="utf-8")
    block = re.search(r"\$voidCalls = @\((.*?)\n\)", text, re.S)
    assert block, "the void-call allowlist is gone or was renamed"
    entries = re.findall(r"'([^']+)'", block.group(1))
    assert entries, "the void-call allowlist is empty"
    unqualified = [e for e in entries if not e.startswith("$")]
    assert not unqualified, (
        "void-call allowlist entries must be receiver-qualified "
        f"(e.g. '$content.Add'), not bare method names: {unqualified}"
    )
    assert "$voidMethods" not in text, (
        "the name-keyed allowlist is back; it excuses ArrayList.Add"
    )
    # The three assertions above validate the DECLARATION. They do not, on
    # their own, establish that the declaration is the list the live check
    # consults -- a harness that leaves $voidCalls in place as a decoy while
    # the comparison reverts to a name-keyed list passes all of them and
    # excuses the ArrayList injection again. Pin the comparison itself.
    assert "$voidCalls -notcontains" in text, (
        "the void-call check no longer consults $voidCalls; the allowlist "
        "above may be a decoy while the live comparison is name-keyed"
    )


# ---------------------------------------------------------------------------
# Behaviour harness
# ---------------------------------------------------------------------------
def _run_installer(tmp_path: Path, args: list[str], env_extra: dict | None = None):
    """Run the real install.ps1 in an empty directory.

    It exits 1 at "No bundles found", which is after the SSL/TLS preamble has
    executed, so the preamble's observable side effects can be asserted
    against the shipped file rather than a retyped copy.
    """
    import os

    env = dict(os.environ)
    env.pop("VCFOPS_VERIFY_SSL", None)
    env.update(env_extra or {})
    return subprocess.run(
        ["pwsh", "-NoProfile", "-File", str(TEMPLATE), *args],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=300,
        env=env,
    )


_BYPASS_WARNING = "TLS certificate verification disabled."


@pytest.mark.skipif(shutil.which("pwsh") is None, reason="PowerShell not installed")
class TestSkipSslVerifyIsReachable:
    """Reachability of the cert-bypass branch, measured on the real script.

    Before the fix all three of these produced no warning at all, because
    line 105 had already overwritten the parameter.
    """

    def test_flag_reaches_the_bypass(self, tmp_path: Path) -> None:
        proc = _run_installer(tmp_path, ["-SkipSslVerify"])
        assert _BYPASS_WARNING in (proc.stdout + proc.stderr), (
            "-SkipSslVerify must reach the cert-bypass branch"
        )

    def test_env_var_reaches_the_bypass(self, tmp_path: Path) -> None:
        proc = _run_installer(tmp_path, [], {"VCFOPS_VERIFY_SSL": "false"})
        assert _BYPASS_WARNING in (proc.stdout + proc.stderr), (
            "VCFOPS_VERIFY_SSL=false must reach the cert-bypass branch"
        )

    def test_no_bypass_without_opt_in(self, tmp_path: Path) -> None:
        proc = _run_installer(tmp_path, [])
        assert _BYPASS_WARNING not in (proc.stdout + proc.stderr), (
            "verification must stay on unless the operator opts out"
        )


# ---------------------------------------------------------------------------
# Issue #119 -- install.ps1's Get-Content reads must name their encoding
# ---------------------------------------------------------------------------
class TestPowerShellReadsArePinned:
    """The PowerShell half of #101.

    `Get-Content -Raw` with no `-Encoding` is the system ANSI code page on
    Windows PowerShell 5.1 (.NET Framework) and UTF-8 on PowerShell 7 (.NET
    Core), so the same installer decodes the same bundle differently depending
    on which PowerShell the customer runs. Measured under pwsh 7 on Linux: the
    same UTF-8 bytes read through a cp1252 decoder yield mojibake that
    ConvertFrom-Json parses without complaint, so the customer gets a
    SUCCESSFUL install carrying corrupted content names -- not a crash.

    The authoritative version of this check is the AST-based one in the
    harness. This line-based sibling exists so a runner with no PowerShell
    still catches a regression; it is exact for this file because all three
    Get-Content calls are single-line. If one ever wraps, the harness is the
    one that stays right.
    """

    def test_every_get_content_names_an_encoding(self, script_text: str) -> None:
        offenders = [
            (i, ln.strip())
            for i, ln in enumerate(script_text.splitlines(), 1)
            if "Get-Content" in ln
            and not ln.strip().startswith("#")
            and "-Encoding" not in ln
        ]
        assert not offenders, (
            "Get-Content with no -Encoding decodes as system ANSI on "
            f"PowerShell 5.1: {offenders}"
        )

    def test_readalltext_site_is_left_alone(self, script_text: str) -> None:
        """[System.IO.File]::ReadAllText already defaults to UTF-8 on both runtimes.

        Pinned as a negative: #119 records this site explicitly so nobody
        "fixes" it into inconsistency with the -Encoding UTF8 sites.
        """
        assert "[System.IO.File]::ReadAllText($Path)" in script_text


# ---------------------------------------------------------------------------
# Issue #118 -- narration must never be able to fail an install
# ---------------------------------------------------------------------------
class TestPythonInstallerPinsStdout:
    """#101 pinned file I/O. This is the other half: stdout.

    install.py prints bundle-sourced content names. On native Windows with
    stdout redirected to a file or a pipe, Python encodes stdout with the
    locale encoding, so a name outside cp1252 raises UnicodeEncodeError AFTER
    the object has already been created on the instance.

    Reproduced on Linux with PYTHONIOENCODING=cp1252 (the analogue the #101
    review used, since there is no windows-latest runner): printing a CJK
    content name exits 1 with UnicodeEncodeError before the fix and exits 0
    with UTF-8 bytes on stdout after it.
    """

    @pytest.fixture(scope="class")
    def py_text(self) -> str:
        return (
            REPO_ROOT / "src" / "vcfops_packaging" / "templates" / "install.py"
        ).read_text(encoding="utf-8")

    def test_stdio_is_reconfigured(self, py_text: str) -> None:
        assert 'reconfigure(encoding="utf-8", errors="replace")' in py_text, (
            "install.py must pin stdout/stderr to UTF-8"
        )

    def test_errors_replace_is_present(self, py_text: str) -> None:
        """errors='replace' is the point, not utf-8 alone.

        Pinning the encoding without it still raises on an unencodable code
        point. A mangled character in a printed name is cosmetic; a traceback
        after a successful import is not.
        """
        body = re.search(
            r"def _pin_stdio_encoding\(\) -> None:(.*?)\n\n\n", py_text, re.S
        )
        assert body, "_pin_stdio_encoding not found in install.py"
        assert 'errors="replace"' in body.group(1)
        assert "sys.stdout" in body.group(1) and "sys.stderr" in body.group(1), (
            "stderr needs it too: _die() writes there, and a message about a "
            "failure must not itself fail"
        )

    def test_it_runs_before_the_bootstrap_print(self, py_text: str) -> None:
        """Module scope, not main().

        _bootstrap_requests() prints a temp-directory path that can carry a
        non-ASCII Windows username, and it runs at import time, so a call
        inside main() would already be too late.
        """
        call_at = py_text.index("\n_pin_stdio_encoding()")
        bootstrap_at = py_text.index("\n_bootstrap_requests()")
        main_at = py_text.index("\ndef main()")
        assert call_at < bootstrap_at < main_at, (
            "_pin_stdio_encoding() must run before _bootstrap_requests()"
        )

    def test_post_install_needs_no_equivalent(self) -> None:
        """Recorded so the #118 sweep is closed, not just narrowed.

        post-install.py runs on the VCF Ops appliance (Linux), and it prints
        nothing: its only console write is one sys.stderr.write of an OSError
        message. Everything else goes to a log file already opened with
        encoding="utf-8" by #101.
        """
        text = (
            REPO_ROOT / "src" / "vcfops_managementpacks" / "templates"
            / "post-install.py"
        ).read_text(encoding="utf-8")
        prints = [
            ln.strip()
            for ln in text.splitlines()
            if re.match(r"^\s*(print\(|sys\.stdout)", ln)
        ]
        assert not prints, (
            "post-install.py has grown a print; re-open #118 for the "
            f"appliance path: {prints}"
        )


# ---------------------------------------------------------------------------
# Issue #116 -- the Ext.Direct / dashboard.action envelope family
# ---------------------------------------------------------------------------
class TestExtDirectEnvelopesAreGuarded:
    """The third envelope shape, on the uninstall path.

    #109 swept every Invoke-Api-derived read onto Get-PropValue. The UI
    Ext.Direct path was not in that sweep: those responses come from
    Invoke-WebRequest + ConvertFrom-Json as an ARRAY of envelopes, and the
    callers read `$result[0].type`. That is TWO failures, not one, and
    verified under pwsh 7 with Set-StrictMode -Version Latest they are
    different exceptions: `@()[0]` is IndexOutOfRangeException, a missing
    member is PropertyNotFoundException. Routing only the member read through
    Get-PropValue swaps the second for the first.

    Behavioural coverage is in the harness. These are the static pins that
    survive a runner with no PowerShell.
    """

    # Every function that touches an Ext.Direct or dashboard.action response.
    EXT_DIRECT_CALLERS = [
        "Get-AllViews",
        "Remove-View",
        "Get-AllReports",
        "Remove-Reports",
    ]

    @pytest.mark.parametrize("func", EXT_DIRECT_CALLERS)
    def test_no_raw_envelope_index(self, script_text: str, func: str) -> None:
        body = re.search(
            rf"function {re.escape(func)}[ ({{](.*?)\n\}}\n", script_text, re.S
        )
        assert body, f"{func} not found in install.ps1"
        assert "$result[0]" not in body.group(1), (
            f"{func} indexes the envelope array directly; an empty array is "
            "IndexOutOfRangeException before any member read is reached"
        )
        assert "Get-ExtDirectResult" in body.group(1), (
            f"{func} must read its envelope through the guard"
        )

    def test_guard_handles_both_get_propvalue_shapes(
        self, script_text: str
    ) -> None:
        body = re.search(
            r"function Get-ExtDirectResult \{(.*?)\n\}\n", script_text, re.S
        )
        assert body, "Get-ExtDirectResult not found in install.ps1"
        code = "\n".join(
            ln for ln in body.group(1).splitlines() if not ln.strip().startswith("#")
        )
        # The null case cannot be folded into the Count case: @($null).Count
        # is 1, not 0.
        assert "$null -eq $Response" in code, (
            "a null response must be rejected separately from an empty array"
        )
        assert ".Count -eq 0" in code, "the empty-array index guard is missing"
        assert "Get-PropValue" in code, (
            "member reads belong to the existing helper, not a second idiom"
        )
        assert "[System.Collections.IDictionary]" in code, (
            "must classify with IDictionary, matching Get-PropValue and "
            "Get-StatusCode"
        )

    def test_envelope_type_is_enumerated_not_just_tested_for_exception(
        self, script_text: str
    ) -> None:
        """Codex P2 on PR #123: the guard grew its own residual-else.

        Testing only `$type -eq "exception"` and falling through on anything
        else made `[{}]` a SUCCESS: Get-PropValue reads the absent member as
        "", the exception test misses, and the two delete callers omit
        -RequireResult, so the helper returned cleanly and the uninstall
        printed "Deleted" for a delete the server never acknowledged.

        StrictMode used to throw on the missing `.type` and the caller
        reported a warning, so this guard turned loud-but-correct into
        quiet-and-wrong -- a narrower instance of the defect it was written to
        close. Accept "rpc" explicitly; everything else refuses.
        """
        body = re.search(
            r"function Get-ExtDirectResult \{(.*?)\n\}\n", script_text, re.S
        )
        assert body, "Get-ExtDirectResult not found in install.ps1"
        code = "\n".join(
            ln for ln in body.group(1).splitlines() if not ln.strip().startswith("#")
        )
        assert '$type -ne "rpc"' in code, (
            "the accept list must be enumerated; an unrecognised type cannot "
            "fall through to the success path"
        )
        assert '$type -eq "exception"' in code, (
            "the handled-refusal branch must still name the server's message"
        )
        assert "did not acknowledge" in code, (
            "the residual branch must refuse with a sentence, not return"
        )
        # Absent and blank are different bugs and must read differently.
        #
        # A presence check on "$hasType" is NOT enough, and was caught by its
        # own negative control: flipping the initialiser to $true leaves the
        # token in place, keeps a token-match green, and makes every absent
        # type report as blank. Pin the semantics, not the identifier.
        assert "$hasType = $false" in code, (
            "$hasType must start false, or an absent type reports as blank"
        )
        assert 'if (-not $hasType) { "absent" }' in code, (
            "the 'absent' wording must be conditioned on the probe; "
            'Get-PropValue reports both absent and blank as ""'
        )

    def test_result_less_rpc_success_is_still_accepted(
        self, script_text: str
    ) -> None:
        """The positive control the enumeration must not break.

        dashboard_delete_api.md:94 records a real deleteReportDefinitions
        success as {"type":"rpc"} with no result key at all. That is precisely
        why Remove-View and Remove-Reports omit -RequireResult, so the type
        check must be what rejects a malformed envelope, never the presence of
        a result.
        """
        body = re.search(
            r"function Get-ExtDirectResult \{(.*?)\n\}\n", script_text, re.S
        )
        assert body, "Get-ExtDirectResult not found in install.ps1"
        code = "\n".join(
            ln for ln in body.group(1).splitlines() if not ln.strip().startswith("#")
        )
        assert "$RequireResult -and $null -eq $payload" in code, (
            "an absent result may only refuse when the caller asked for one"
        )
        for func in ("Remove-View", "Remove-Reports"):
            fn = re.search(
                rf"function {re.escape(func)} \{{(.*?)\n\}}\n", script_text, re.S
            )
            assert fn, f"{func} not found"
            # Comments explain WHY -RequireResult is omitted; that prose must
            # not trip the check on the code.
            fn_code = "\n".join(
                ln for ln in fn.group(1).splitlines()
                if not ln.strip().startswith("#")
            )
            assert "-RequireResult" not in fn_code, (
                f"{func} must not demand a result payload; the recorded "
                "success for this call carries none"
            )

    def test_guard_refuses_rather_than_reporting_an_empty_list(
        self, script_text: str
    ) -> None:
        """-RequireResult is this family's Assert-LookupOk.

        An unreadable envelope degraded to "no such content" makes the
        uninstall print "not found (already removed?)" about content that is
        still on the instance. Same class as the create-on-failed-lookup
        guard, one path over.
        """
        assert '-What "View list" -Fatal -RequireResult' in script_text
        assert '-What "Report list" -Fatal -RequireResult' in script_text

    @pytest.mark.parametrize(
        "func,expected",
        [("Get-AllViews", "View list"), ("Get-AllReports", "Report list")],
    )
    def test_no_residual_else_returns_an_empty_list(
        self, script_text: str, func: str, expected: str
    ) -> None:
        """The case -RequireResult does NOT close: wrong shape.

        A present `result` that is a string, a bool, or an array is not an
        exception, not null and not absent, so it reaches the shape test and
        falls through it. With no `else`, the function returns an empty list
        and the uninstall prints "not found (already removed?)" about content
        that is still on the instance. That is verbatim the third bullet in
        knowledge/lessons/unenumerated-exit-status-is-not-a-verdict.md: a safe
        default for READING became an unsafe default for DECIDING.
        """
        body = re.search(
            rf"function {re.escape(func)} \{{(.*?)\n\}}\n", script_text, re.S
        )
        assert body, f"{func} not found in install.ps1"
        code = body.group(1)
        assert "} else {" in code, (
            f"{func} has a shape test with no else; an unenumerated shape "
            "falls through to an empty list"
        )
        assert "Write-Fail" in code, (
            f"{func} must refuse an unrecognised shape, not report zero items"
        )
        assert "unrecognised shape" in code
        assert f"{expected} failed" in code

    # The per-item reads: these objects came off the wire the same way.
    @pytest.mark.parametrize(
        "func", ["Uninstall-Dashboards", "Uninstall-Views", "Uninstall-Reports"]
    )
    def test_thumbnail_reads_go_through_get_propvalue(
        self, script_text: str, func: str
    ) -> None:
        body = re.search(
            rf"function {re.escape(func)}\(\$Ctx\) \{{(.*?)\n\}}\n",
            script_text,
            re.S,
        )
        assert body, f"{func} not found in install.ps1"
        code = "\n".join(
            ln for ln in body.group(1).splitlines() if not ln.strip().startswith("#")
        )
        # Scoped to the loop that enumerates the WIRE objects
        # (`foreach ($x in $allDash|$allViews|$allReports)`) and no further.
        # The later `foreach ($d in $toDelete)` loops read hashtables this
        # function literally built three lines earlier, so their keys are
        # present by construction -- worth stating, because StrictMode throws
        # PropertyNotFoundException on a missing hashtable key too, not only
        # on a missing PSObject member.
        loop = re.search(r"foreach \(\$(\w+) in \$all\w+\) \{(.*?)\n    \}", code, re.S)
        assert loop, f"{func} no longer enumerates a UI-API list"
        var, block = loop.group(1), loop.group(2)
        offenders = re.findall(rf"\${var}\.\w+", block)
        assert not offenders, (
            f"{func} dot-accesses a UI-API object: {offenders}"
        )


# ---------------------------------------------------------------------------
# Issue #121 -- the import-wait timeout names the last-seen HTTP status
# ---------------------------------------------------------------------------
class TestImportWaitTimeoutNamesTheStatus:
    def test_timeout_sentence_carries_the_status(self, script_text: str) -> None:
        assert 'timed out; state=$state (last status HTTP $sc)' in script_text, (
            "an empty state= reads as 'the server said nothing was happening' "
            "when the truth may be 'we never got a usable answer'"
        )
        assert 'timed out; state=$state"' not in script_text

    def test_python_import_poll_cannot_reach_the_ambiguous_state(self) -> None:
        """Scoped to install.py's IMPORT poll, and true only of that loop.

        install.py's import poll `_die`s on the first non-200
        ("Import status check failed (<code>)"), so its `state` at timeout is
        always from a 200 and cannot be the ambiguous empty string.
        install.ps1 deliberately keeps polling through a transient non-200
        (the import is already running by then), which is what creates the
        ambiguity the status name resolves there.

        An earlier version of this docstring generalised that to "both
        installers name a status on the path where one exists". That was
        false: install.py's PRIOR-EXPORT wait does tolerate a non-200, exactly
        as PowerShell does, and named neither status nor state. Covered by the
        test below rather than by widening this claim.
        """
        py = (
            REPO_ROOT / "src" / "vcfops_packaging" / "templates" / "install.py"
        ).read_text(encoding="utf-8")
        assert "Import status check failed ({s.status_code})" in py, (
            "install.py's import poll must keep dying on a non-200; if it "
            "starts tolerating one, it inherits install.ps1's ambiguity and "
            "needs the same last-seen tracking"
        )

    def test_python_prior_export_wait_names_the_last_seen_signal(self) -> None:
        """The real parity gap, one loop earlier than #121 pointed.

        install.ps1's prior-export wait got `(last seen: $lastSeen)` in #120.
        Its Python sibling tolerates a non-200 the same way and said neither
        status nor state, so an empty `state` read as "the server said nothing
        was happening" when the truth was "we never got a usable answer".
        """
        py = (
            REPO_ROOT / "src" / "vcfops_packaging" / "templates" / "install.py"
        ).read_text(encoding="utf-8")
        assert '_die("Timed out waiting for prior export to finish")' not in py, (
            "the bare prior-export timeout is back"
        )
        assert "(last seen: {last_seen})" in py
        body = re.search(
            r"deadline = time\.monotonic\(\) \+ timeout_s\n(.*?)\n\n",
            py,
            re.S,
        )
        assert body, "the prior-export wait loop moved"
        assert 'last_seen = f"HTTP {g.status_code}"' in body.group(1), (
            "a non-200 must be recorded, not silently skipped; that branch is "
            "the whole reason the state at timeout is not evidence"
        )


@pytest.mark.skipif(shutil.which("pwsh") is None, reason="PowerShell not installed")
def test_advisory_harness() -> None:
    proc = subprocess.run(
        ["pwsh", "-NoProfile", "-File", str(HARNESS), str(TEMPLATE)],
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, f"harness failed:\n{proc.stdout}\n{proc.stderr}"
    assert "ALL ASSERTIONS PASSED" in proc.stdout

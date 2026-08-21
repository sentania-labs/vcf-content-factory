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

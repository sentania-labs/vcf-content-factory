"""Push-time release guard: RULE-014 / RULE-012 refusal matrix via real git push.

Covers `.githooks/pre-push` (dispatcher) and `scripts/version_line_guard.sh`
(policy) end to end, plus the bootstrap scripts' `no-upstream` -> Unknown
rendering. Written for the PR #151 framework review
(knowledge/context/reviews/framework/release-guard-pr151-2026-09-10.md),
whose BLOCKING finding (B1: a tag on a commit with no adapter.yaml made the
guard discard a 0.x refusal for another tag in the same push) passed the
whole suite because nothing exercised the guard.

Fixture per test, all under tmp_path (no shared state, so no xdist group):

  <tmp>/factory/                         fake factory
      scripts -> <repo>/scripts          symlink (the code under test)
      src -> <repo>/src                  symlink (the defect gate)
      .githooks -> <repo>/.githooks      symlink (the hook under test)
      knowledge/context/defects.md       this test's own registry
      content/sdk-adapters/fixturepak/   pak git repo, core.hooksPath set
  <tmp>/remotes/vcf-content-factory-sdk-fixturepak.git   bare origin

The origin URL ends in `vcf-content-factory-sdk-fixturepak.git`, so the
guard derives pak name `fixturepak` exactly as it does for a real clone.
Every assertion checks BOTH the push exit code and what actually reached
the bare remote (git ls-remote), because "the hook said no" and "the tag
did not land" are different claims.

Bootstrap cases run the real bootstrap scripts offline: the registry
entry's https URL is never used because the clone already exists, and the
clone's origin is the local bare repo, so `git fetch` needs no network.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PAK = "fixturepak"

if shutil.which("git") is None or shutil.which("bash") is None:
    pytest.skip("git and bash are required for the release guard tests",
                allow_module_level=True)

_EMPTY_REGISTRY = "# Defect registry\n\n## Defects\n"

_BLOCKER_REGISTRY = f"""\
# Defect registry

## Defects

### DEF-001

- **Title:** Fixture blocker
- **Severity:** blocking
- **Status:** open
- **Affects:** {PAK}
- **First-seen:** build 1 (2026-01-01)
- **Source:** knowledge/context/reviews/fixture.md
- **Summary:** Open blocking defect naming the fixture pak.
"""

V0 = 'version: "0.3.0"\nadapter_kind: "vcfcf_fixturepak"\n'
V1 = 'version: "1.0.0"\nadapter_kind: "vcfcf_fixturepak"\n'


class Fixture:
    """A fake factory, a pak clone inside it, and a bare origin."""

    def __init__(self, tmp: Path, registry: "str | None" = _EMPTY_REGISTRY):
        self.tmp = tmp
        self.factory = tmp / "factory"
        self.pak = self.factory / "content" / "sdk-adapters" / PAK
        self.bare = tmp / "remotes" / f"vcf-content-factory-sdk-{PAK}.git"
        self.registry = self.factory / "knowledge" / "context" / "defects.md"

        # Interpreter shim: the guard calls bare `python3`; pin it to the
        # interpreter running this suite (the one that has yaml installed).
        self.bin = tmp / "bin"
        self.bin.mkdir()
        (self.bin / "python3").symlink_to(sys.executable)

        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith("GIT_")}
        self.env.update({
            "PATH": f"{self.bin}{os.pathsep}{os.environ.get('PATH', '')}",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid",
        })

        (self.factory / "knowledge" / "context").mkdir(parents=True)
        self.pak.parent.mkdir(parents=True)
        for name in ("scripts", "src", ".githooks"):
            (self.factory / name).symlink_to(REPO_ROOT / name)
        if registry is not None:
            self.registry.write_text(registry, encoding="utf-8")

        self.bare.parent.mkdir(parents=True)
        self.git("init", "-q", "--bare", "-b", "main", str(self.bare), cwd=tmp)
        self.git("init", "-q", "-b", "main", str(self.pak), cwd=tmp)
        self.git("remote", "add", "origin", str(self.bare))

        # History: a 0.x commit then a 1.x commit, tags on each.
        (self.pak / "adapter.yaml").write_text(V0)
        self.git("add", "adapter.yaml")
        self.git("commit", "-qm", "0.x")
        self.git("tag", "v0.3.0")
        self.git("tag", "-a", "v0.3.0-annot", "-m", "annotated 0.x")
        (self.pak / "adapter.yaml").write_text(V1)
        self.git("commit", "-qam", "1.x")
        self.git("tag", "v1.0.0")
        self.git("tag", "-a", "v1.0.0-annot", "-m", "annotated 1.x")

        # A tag on a commit with no adapter.yaml, and one on a commit whose
        # version is single-quoted 0.x. Plumbing, so the tree is untouched.
        self.git("tag", "v2-noyaml", self.commit_with({"README": "readme\n"}))
        self.git("tag", "v3-squote", self.commit_with(
            {"adapter.yaml": "version: '0.5.0'\nadapter_kind: 'vcfcf_fixturepak'\n"}))

        self.git("push", "-q", "--no-verify", "-u", "origin", "main")
        self.git("config", "core.hooksPath", str(self.factory / ".githooks"))

    # -- helpers ---------------------------------------------------------
    def git(self, *args, cwd: "Path | None" = None, input: "str | None" = None,
            check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args], cwd=cwd or self.pak, env=self.env, input=input,
            capture_output=True, text=True, check=check,
        )

    def commit_with(self, files: dict) -> str:
        entries = []
        for name, content in files.items():
            blob = self.git("hash-object", "-w", "--stdin", input=content).stdout.strip()
            entries.append(f"100644 blob {blob}\t{name}\n")
        tree = self.git("mktree", input="".join(entries)).stdout.strip()
        return self.git("commit-tree", tree, "-m", "plumbing").stdout.strip()

    def push(self, *refs, env_extra: "dict | None" = None) -> subprocess.CompletedProcess:
        env = dict(self.env, **(env_extra or {}))
        return subprocess.run(
            ["git", "push", "origin", *refs], cwd=self.pak, env=env,
            capture_output=True, text=True, timeout=120,
        )

    def seed_remote_tag(self, tag: str) -> None:
        self.git("push", "-q", "--no-verify", "origin", tag)

    def remote_tags(self) -> set:
        out = self.git("ls-remote", "--tags", str(self.bare)).stdout
        tags = set()
        for line in out.splitlines():
            ref = line.split("\t", 1)[1]
            tags.add(ref[len("refs/tags/"):].removesuffix("^{}"))
        return tags

    def remote_head(self, branch: str = "main") -> str:
        out = self.git("ls-remote", str(self.bare), f"refs/heads/{branch}").stdout
        return out.split("\t", 1)[0] if out else ""


def _report(res: subprocess.CompletedProcess) -> str:
    return f"rc={res.returncode}\n--- stdout\n{res.stdout}\n--- stderr\n{res.stderr}"


def assert_refused(fx: Fixture, res, *, rule: str, not_landed) -> None:
    assert res.returncode != 0, _report(res)
    assert "release guard: push refused" in res.stderr, _report(res)
    assert f"REFUSED ({rule})" in res.stderr, _report(res)
    landed = fx.remote_tags() & set(not_landed)
    assert not landed, f"refused push still landed {landed}\n{_report(res)}"


def assert_allowed(fx: Fixture, res, *, landed) -> None:
    assert res.returncode == 0, _report(res)
    assert "push refused" not in res.stderr, _report(res)
    missing = set(landed) - fx.remote_tags()
    assert not missing, f"allowed push did not land {missing}\n{_report(res)}"


@pytest.fixture
def fx(tmp_path):
    return Fixture(tmp_path)


# ---------------------------------------------------------------------------
# 1-6: the basic matrix
# ---------------------------------------------------------------------------

def test_01_branch_only_push_allowed(fx):
    fx.git("commit", "-q", "--allow-empty", "-m", "branch work")
    local = fx.git("rev-parse", "HEAD").stdout.strip()
    res = fx.push("main")
    assert res.returncode == 0, _report(res)
    assert "release guard" not in res.stderr, _report(res)
    assert fx.remote_head() == local
    assert fx.remote_tags() == set()


@pytest.mark.parametrize("tag", ["v0.3.0-annot", "v0.3.0"],
                         ids=["annotated", "lightweight"])
def test_02_zero_x_tag_refused(fx, tag):
    res = fx.push(tag)
    assert_refused(fx, res, rule="RULE-014", not_landed=[tag])


@pytest.mark.parametrize("tag", ["v1.0.0", "v1.0.0-annot"],
                         ids=["lightweight", "annotated"])
def test_03_one_x_tag_allowed(fx, tag):
    res = fx.push(tag)
    assert_allowed(fx, res, landed=[tag])


def test_04_tag_deletion_allowed_while_tree_is_zero_x(fx):
    fx.seed_remote_tag("v0.3.0")
    assert "v0.3.0" in fx.remote_tags()
    (fx.pak / "adapter.yaml").write_text(V0)  # working tree back on 0.x
    res = fx.push("--delete", "v0.3.0")
    assert res.returncode == 0, _report(res)
    assert "push refused" not in res.stderr, _report(res)
    assert "v0.3.0" not in fx.remote_tags()


def test_05_old_zero_x_tag_refused_while_tree_is_one_x(fx):
    assert (fx.pak / "adapter.yaml").read_text() == V1
    res = fx.push("v0.3.0-annot")
    assert_refused(fx, res, rule="RULE-014", not_landed=["v0.3.0-annot"])


@pytest.mark.parametrize("order", [("v1.0.0", "v0.3.0-annot"),
                                   ("v0.3.0-annot", "v1.0.0")],
                         ids=["good-first", "bad-first"])
def test_06_mixed_batch_refused(fx, order):
    res = fx.push(*order)
    assert_refused(fx, res, rule="RULE-014", not_landed=order)


# ---------------------------------------------------------------------------
# 7-9: per-tag adapter.yaml reads (B1, fail safe, quoting)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("order", [("v2-noyaml", "v0.3.0"),
                                   ("v0.3.0", "v2-noyaml")],
                         ids=["noyaml-first", "zero-x-first"])
def test_07_noyaml_tag_does_not_discard_zero_x_refusal(fx, order):
    """Review B1: an unreadable tag must not turn a reached refusal into 'not guarded'."""
    res = fx.push(*order)
    assert_refused(fx, res, rule="RULE-014", not_landed=["v0.3.0"])
    assert fx.remote_tags() == set(), _report(res)


def test_08_noyaml_tag_plus_good_tag_allowed_with_warning(fx):
    res = fx.push("v2-noyaml", "v1.0.0")
    assert_allowed(fx, res, landed=["v2-noyaml", "v1.0.0"])
    assert "not guarded" in res.stderr, _report(res)
    assert "no RULE-014 verdict for v2-noyaml" in res.stderr, _report(res)


def test_09_single_quoted_zero_x_version_refused(fx):
    res = fx.push("v3-squote")
    assert_refused(fx, res, rule="RULE-014", not_landed=["v3-squote"])


# ---------------------------------------------------------------------------
# 10-14: the defect gate and its fail-safe paths
# ---------------------------------------------------------------------------

def test_10_open_blocking_defect_refused(fx):
    fx.registry.write_text(_BLOCKER_REGISTRY, encoding="utf-8")
    res = fx.push("v1.0.0-annot")
    assert_refused(fx, res, rule="RULE-012", not_landed=["v1.0.0-annot"])
    assert "Refused by RULE-012" in res.stderr, _report(res)


class TestPython3Absent:
    @pytest.fixture
    def nopy(self, fx):
        # Replace the interpreter shim with one that behaves like a missing
        # binary (exit 127), first on PATH so no real python3 is reached.
        shim = fx.bin / "python3"
        shim.unlink()
        shim.write_text("#!/bin/sh\nexit 127\n")
        shim.chmod(0o755)
        return fx

    def test_11a_one_x_tag_allowed_not_guarded(self, nopy):
        res = nopy.push("v1.0.0")
        assert_allowed(nopy, res, landed=["v1.0.0"])
        assert "not guarded" in res.stderr, _report(res)
        assert "defect gate could not run (exit 127)" in res.stderr, _report(res)

    def test_11b_zero_x_tag_still_refused(self, nopy):
        res = nopy.push("v0.3.0")
        assert_refused(nopy, res, rule="RULE-014", not_landed=["v0.3.0"])


@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0,
                    reason="root ignores chmod 000, so the registry stays readable")
def test_12_unreadable_registry_allowed(fx):
    fx.registry.chmod(0o000)
    try:
        res = fx.push("v1.0.0")
    finally:
        fx.registry.chmod(0o644)
    assert_allowed(fx, res, landed=["v1.0.0"])
    assert "not guarded" in res.stderr, _report(res)


def test_13_dist_present_no_adapter_kind_gate_still_runs(fx):
    """Review W2: the informational dist/ block must not kill the RULE-012 gate."""
    (fx.factory / "dist").mkdir()
    (fx.pak / "adapter.yaml").write_text('version: "1.0.0"\n')  # no adapter_kind
    fx.registry.write_text(_BLOCKER_REGISTRY, encoding="utf-8")
    res = fx.push("v1.0.0")
    assert_refused(fx, res, rule="RULE-012", not_landed=["v1.0.0"])


def test_14_absent_registry_allowed_and_warning_surfaced(tmp_path):
    """Review W5: the hook must not swallow the gate's absent-registry WARNING."""
    fx = Fixture(tmp_path, registry=None)
    assert not fx.registry.exists()
    res = fx.push("v1.0.0")
    assert_allowed(fx, res, landed=["v1.0.0"])
    assert "WARNING: no defect registry" in res.stderr, _report(res)


# ---------------------------------------------------------------------------
# 15: bootstrap scripts render no-upstream as Unknown
# ---------------------------------------------------------------------------

def _status_line(fx: Fixture, script: str) -> str:
    text = (fx.factory / ".bootstrap-status").read_text()
    lines = [ln for ln in text.splitlines() if f" {script} " in ln]
    assert len(lines) == 1, text
    return lines[0]


def _run_bootstrap(fx: Fixture, script: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(fx.factory / "scripts" / f"{script}.sh"), "--update"],
        cwd=fx.factory, env=fx.env, capture_output=True, text=True, timeout=120,
    )


def _write_pak_registry(fx: Fixture) -> None:
    (fx.factory / "knowledge" / "context" / "managed_paks.md").write_text(
        f"- **Remote:** https://example.invalid/sentania-labs/vcf-content-factory-sdk-{PAK}\n"
        f"- **Target:** `content/sdk-adapters/{PAK}/`\n")


class TestBootstrapManagedPaks:
    @pytest.mark.parametrize("how", ["detached", "unset-upstream"])
    def test_15a_no_upstream_renders_unknown(self, fx, how):
        _write_pak_registry(fx)
        if how == "detached":
            fx.git("checkout", "-q", "--detach", "HEAD")
        else:
            fx.git("branch", "--unset-upstream")
        res = _run_bootstrap(fx, "bootstrap_managed_paks")
        assert res.returncode == 0, _report(res)
        assert f"Unknown:  {PAK}" in res.stdout, _report(res)
        assert f"Current:  {PAK}" not in res.stdout, _report(res)
        assert f"unknown={PAK}" in _status_line(fx, "bootstrap_managed_paks").split()

    def test_15b_tracking_level_renders_current(self, fx):
        _write_pak_registry(fx)
        res = _run_bootstrap(fx, "bootstrap_managed_paks")
        assert res.returncode == 0, _report(res)
        assert f"Current:  {PAK}" in res.stdout, _report(res)
        assert "unknown=-" in _status_line(fx, "bootstrap_managed_paks").split()


class TestBootstrapReferences:
    @pytest.fixture
    def ref(self, fx):
        refs = fx.factory / "reference" / "references"
        refs.mkdir(parents=True)
        fx.git("clone", "-q", str(fx.bare), str(refs / "refslug"), cwd=fx.tmp)
        (fx.factory / "knowledge" / "context" / "reference_sources.md").write_text(
            "- **URL:** https://example.invalid/x/refslug\n"
            "- **Local path:** `reference/references/refslug/`\n")
        return refs / "refslug"

    def test_15c_detached_renders_unknown(self, fx, ref):
        fx.git("checkout", "-q", "--detach", "HEAD", cwd=ref)
        res = _run_bootstrap(fx, "bootstrap_references")
        assert res.returncode == 0, _report(res)
        assert "Unknown:  refslug" in res.stdout, _report(res)
        assert "unknown=refslug" in _status_line(fx, "bootstrap_references").split()

    def test_15d_tracking_level_renders_current(self, fx, ref):
        res = _run_bootstrap(fx, "bootstrap_references")
        assert res.returncode == 0, _report(res)
        assert "Current:  refslug" in res.stdout, _report(res)
        assert "unknown=-" in _status_line(fx, "bootstrap_references").split()

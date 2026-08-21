# Windows-host portability: three measured defects, one meta-rule

Measured on a Windows 11 clone (Git Bash, Python 3.12, MSYS2) on a
corporate-managed machine with Developer Mode policy-blocked
(`HKLM\SOFTWARE\Policies\Microsoft\Windows\Appx\AllowDevelopmentWithoutDevLicense
= 0`). See `knowledge/designs/bootstrap-v2.md`'s "Windows portability"
section for the companion policy this lesson doesn't repeat: **logic in
Python, shell only as optional convenience** for bootstrap-level tooling,
plus the `AGENTS.md` symlink-materialization caveat. This lesson covers
three narrower, measured defects found fixing `tests/`, `scripts/`, and
`src/vcfops_*/` for the same box.

**1. Tests must not depend on privileged syscalls.** `Path.symlink_to()` /
`os.symlink()` need `SeCreateSymbolicLinkPrivilege`. Developer Mode grants
it; corporate policy can — and on this box did — deny it, raising
`OSError: [WinError 1314] A required privilege is not held by the client`.
A test that symlinks `content/` into a tmp dir to make loader paths resolve
fails outright, unrelated to what it's actually testing. Fix per site, not
with a blanket "always copytree": if the code under test only *reads* the
linked tree, `shutil.copytree()` (with `ignore=shutil.ignore_patterns(...)`
to skip anything large/irrelevant) is a drop-in, privilege-free
replacement. If the symlink exists so a **subprocess** spawned with a
different `cwd` can `import` a package (Python's `-m` flag implicitly adds
the child's cwd to `sys.path[0]`), the fix is to point `PYTHONPATH` at the
real package directory (an absolute path, so it's cwd-independent) instead
of materializing a link at all — see `tests/test_cli_phase4.py`'s
`_make_factory_copy()`. Always trace *why* a symlink exists before
replacing it; sometimes (as in `tests/test_bundle_composer_phase4.py`'s
`vcfops_common` symlink) the comment claiming it's needed is stale and the
code path it claims to serve doesn't actually key off that path — delete
it and prove the test still passes.

**2. No subprocess in a per-item loop in shell scripts.** MSYS2/Git-Bash
has no real `fork()` — every subprocess spawn pays Windows process-creation
cost. Measured: `git ls-files` spawned once per citation (up to 4×) in
`scripts/path_reference_audit.sh` cost ~199 ms/spawn on this box vs ~5 ms
on Linux — a **40×** penalty. Against a few thousand citations that put a
CI-fast (~30 s on Linux) script over 20 minutes on Windows. Fix: hoist the
repeated subprocess out of the loop entirely — build one in-memory index
from a single invocation (`git ls-files -z` into a bash associative array,
here) and do O(1) lookups per item instead. Two traps found doing this:
(a) plain `git ls-files` C-escapes non-ASCII paths (`"kn\303\244.md"`) —
build the index from `-z` output read with `read -r -d ''`, or the index
never matches a real path; (b) a directory-prefix test (`git ls-files --
"${p}/"`, true if *anything* is tracked under `p/`) is not the same
question as an exact-path hash lookup — it needs its own precomputed set
(every ancestor directory of every tracked file), not just a file-path
hash. The general form of this lesson: any shell loop whose body spawns a
process, sized by input volume rather than a fixed setup cost, is an
MSYS2 landmine even when it's invisible on Linux.

**3. Always pass `encoding=` explicitly on text I/O.** `Path.read_text()`
/ `Path.write_text()` / `open()` in text mode default to the **platform
preferred encoding** — UTF-8 on POSIX, but `cp1252` on Windows (unless
`PYTHONUTF8=1` is set process-wide, which is an environment workaround,
not a code fix, and doesn't travel with the repo). 64 call sites across
`src/vcfops_*/` had no explicit `encoding=`; two of them
(`vcfops_packaging/templates/install.py`, `.../templates/post-install.py`)
ship *inside every bundle zip / pak* and run on the **customer's**
machine, not the authoring box — so this isn't just a dev-inconvenience,
it's a shipped defect. Adding `encoding="utf-8"` explicitly is a pure
no-op on POSIX (matches the existing default) and only ever *fixes* a
POSIX case (`LANG=C`, where Python would otherwise default to ASCII and
crash on non-ASCII content) — never a regression.

## Meta-lesson: every portability fix is a single code path

None of the three fixes above branch on `sys.platform` / `os.name` /
`platform.system()`. A platform branch is the thing that rots — the
untaken branch stops being exercised in CI (which runs POSIX) and silently
drifts out of correctness until the next person hits it fresh, at which
point it's exactly as broken as if the branch had never been added. Prefer
a single mechanism that is provably a no-op or a pure speedup on POSIX
(explicit UTF-8, `copytree` instead of `symlink_to`, a hoisted index
instead of a per-item subprocess) over two mechanisms gated by platform
detection. If a site genuinely can't be fixed that way, leave it alone and
report it as an open question rather than forcing a platform branch to
appear "fixed."

**Source.** `tooling` agent portability pass, 2026-08-20: three sites in
`tests/test_bundle_composer_phase4.py` / `tests/test_cli_phase4.py`
(symlinked `content/`, `third_party/`, `vcfops_common`, and per-package
symlinks into a subprocess-`cwd` factory copy), `scripts/path_reference_audit.sh`
(`is_git_tracked()`'s per-citation `git ls-files` spawns), and 54 genuine
text-I/O sites across `src/vcfops_*/` (of 64 flagged by a line-based grep —
10 were false positives where a multi-line `write_text()` call already
carried `encoding="utf-8"` on a later line; a paren-balanced parse, not a
flat `grep -v encoding=`, is what actually tells you which sites are real
gaps).

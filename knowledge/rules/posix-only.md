---
id: RULE-018
---

# RULE-018: The factory runs on POSIX only

The supported environments for running this framework are **Linux, macOS,
and WSL**. Native Windows is not supported and no work will be spent making
it work. Windows users run the factory under WSL; VS Code's WSL extension
makes that a first-class workflow, so the cost to the user is one extension
and no ongoing friction.

This is a scope decision, not a technical limitation, and it is deliberate:
supporting native Windows means either a second implementation of every
shell script or a permanent set of platform branches, and a platform branch
is the half that rots. Declaring the boundary costs a user one install and
saves the framework an indefinite maintenance tail.

**What this means when you are working:**

- **Do not add `sys.platform` or `os.name` branches** to make something work
  on native Windows. If you catch yourself writing one, the answer is the
  policy, not the branch.
- **Shell scripts under `scripts/` are fine.** They do not need Python ports
  for portability reasons. Port one only if it earns its keep some other
  way (speed, testability, correctness).
- **`os.symlink` in tests is fine.** WSL grants it; Windows Developer Mode
  is irrelevant to us now.
- Do not spend review or agent time on native-Windows defects. Close them
  citing this rule.

**The one carve-out, and it is not optional.** This rule governs the
**factory**, not the **artifacts the factory ships**.
`src/vcfops_packaging/templates/install.py` and `install.ps1` run on a
customer's machine, which we do not control and about which we get no say.
Those must keep working on native Windows, which in practice means explicit
`encoding="utf-8"` on every text read and write in `templates/`, since
Python defaults to the locale encoding (cp1252) there. A content author
authoring a view name containing `✓` or `→` must not produce a bundle that
crashes on a customer's laptop.

**If violated:** Either the framework accumulates platform branches that
nobody can test and that rot silently, or a shipped bundle crashes on a
customer's machine because a dev-environment policy was applied to an
artifact that leaves the building.

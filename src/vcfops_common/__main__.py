"""CLI entry point: python -m vcfops_common <subcommand>.

Subcommands:
  doctor: session-start preflight (bootstrap-v2 Phase 1/1b). Always
            exits 0; output is informational for the SessionStart hook.
"""
from __future__ import annotations

import sys
from typing import Optional, Sequence

_USAGE = """usage: python -m vcfops_common <subcommand>

subcommands:
  doctor    session-start preflight: upstream alignment, credential
            readiness, environment sanity, bootstrap health, first-run
            concierge checklist. Always exits 0.
"""


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help"):
        print(_USAGE, end="")
        return 0
    if args[0] == "doctor":
        from .doctor import main as doctor_main  # noqa: PLC0415
        return doctor_main(args[1:])
    print(f"unknown subcommand: {args[0]}", file=sys.stderr)
    print(_USAGE, end="", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

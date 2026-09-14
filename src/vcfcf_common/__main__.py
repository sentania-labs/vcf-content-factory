"""CLI entry point: python -m vcfops_common <subcommand>.

Subcommands:
  doctor: session-start preflight (bootstrap-v2 Phase 1/1b). Always
            exits 0; output is informational for the SessionStart hook.
  setup:  interactive credential wizard (bootstrap-v2 Phase 2). Must be
            run by the user in a real terminal; refuses a non-TTY stdin
            so no hook or pipe can ever feed it a password.
"""
from __future__ import annotations

import sys
from typing import Optional, Sequence

_USAGE = """usage: python -m vcfops_common <subcommand>

subcommands:
  doctor    session-start preflight: upstream alignment, credential
            readiness, environment sanity, bootstrap health, first-run
            concierge checklist. Always exits 0.
  setup     interactive credential wizard: prompts for a profile and
            writes it to .env. The password is read with a silent
            prompt, so it never reaches the transcript. Run it in your
            own terminal (in a Claude session, prefix with `!`).
"""


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help"):
        print(_USAGE, end="")
        return 0
    if args[0] == "doctor":
        from .doctor import main as doctor_main  # noqa: PLC0415
        return doctor_main(args[1:])
    if args[0] == "setup":
        from .setup_credentials import main as setup_main  # noqa: PLC0415
        return setup_main(args[1:])
    print(f"unknown subcommand: {args[0]}", file=sys.stderr)
    print(_USAGE, end="", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

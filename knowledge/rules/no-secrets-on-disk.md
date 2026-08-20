---
id: RULE-008
---

# RULE-008: Never write secrets to disk

Credentials flow via profile-prefixed env vars (`VCFOPS_PROD_*`, `VCFOPS_QA_*`, `VCFOPS_DEVEL_*`) sourced from `.env`. Select profile with `--profile` or `VCFOPS_PROFILE`. Never commit credentials to the repo.

## Secrets never reach the transcript either

Disk is not the only leak surface. A secret is equally lost once it lands
in the conversation transcript, a shell history, or a process list, all of
which outlive the moment and are readable by anyone with the session.

- **Never `source .env`** in a bash command. Sourcing exports every secret
  into that shell, where any later `env`, `printenv`, or error dump prints
  them. The CLIs load `.env` themselves via `src/vcfops_common/_env.py`;
  pass `--profile <name>` instead.
- **Never put a secret on argv.** `--password` is visible in `ps`, in
  shell history, and in the transcript when an agent composes the command.
  It is retained for scripting only and is documented as not recommended;
  the interactive path is the sanctioned one.
- **Never ask the user to paste a password into chat**, and never echo one
  back. The sanctioned entry path is the credential wizard
  (`python3 -m vcfops_common setup`), which reads the password with a
  silent prompt so it is typed but never displayed.
- **Report credentials by variable NAME, never by value.** The preflight
  doctor reports which profiles are incomplete and which variables are
  missing; it never reads a value into its output.
- **Scrub error paths.** An exception can carry a URL with embedded
  credentials or a response body containing a token. Print the exception
  type, not the payload.

**If violated:** Secrets leak into version control, transcripts, or shell
history, and the repo becomes unsuitable for public sharing or multi-user
environments. A secret that reached a transcript must be treated as
compromised and rotated, not merely deleted.

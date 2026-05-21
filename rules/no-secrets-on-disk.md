---
id: RULE-010
---

# RULE-010: Never write secrets to disk

Credentials flow via profile-prefixed env vars (`VCFOPS_PROD_*`, `VCFOPS_QA_*`, `VCFOPS_DEVEL_*`) sourced from `.env`. Select profile with `--profile` or `VCFOPS_PROFILE`. Never commit credentials to the repo.

**If violated:** Secrets leak into version control and the repo becomes unsuitable for public sharing or multi-user environments.

---
id: RULE-003
decision_refs: []
---

# RULE-003: Never write secrets to disk

Credentials flow via profile-prefixed env vars (`VCFOPS_PROD_*`, `VCFOPS_QA_*`, `VCFOPS_DEVEL_*`) sourced from `.env`. Select profile with `--profile` or `VCFOPS_PROFILE`.

**If violated:** Secrets leak into version control and the repo becomes unsuitable for public sharing or multi-user environments.

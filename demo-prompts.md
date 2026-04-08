# Demo Prompts Log

A chronological list of the significant prompts used to build this demo,
captured so the demo can be reproduced or replayed against a fresh
Claude session. Trivial follow-ups, typo fixes, and confirmations are
omitted; only the prompts that *moved the work forward* are listed.

The intent is that running these prompts in order against a Claude
session that has access to this repo, valid `VCFOPS_*` env vars, and
permission to run the dedicated tools should reproduce the demo.

## Phase 1 — Connectivity

1. **"okay the env is set. can you do a test query of VCF operations
   for installed supermetrics"**
   - Ran `python3 -m vcfops_supermetrics list` against the lab.
   - Surfaced an initial DNS / FQDN issue in `.env`; reran after fix.

2. **"please list them all"**
   - Listed the 44 installed super metrics with the `[Custom]` ones
     called out separately.

## Phase 2 — Authoring a super metric from a natural-language ask

3. **"Please create a super metric that allows an administrator to
   identify if there is a VM with snapshot space consumed greater
   than the amount of allocated disk space."**
   - Per CLAUDE.md hard rule #2 (no fabricated metric keys), refused
     to guess and asked for the exact stat keys.

4. **"Please use your access to VCF operations to discover VM metrics
   (updated claude.md to allow this)"**
   - Used `/api/resources/{id}/statkeys` against a sample VM.
   - Found `diskspace|snapshot` and `diskspace|provisionedSpace`
     (later corrected to `config|hardware|diskSpace`).
   - Authored `supermetrics/vm_snapshot_exceeds_provisioned.yaml`.
   - Validated and noted that `sync` cannot assign object type.

5. **"yes install it and enable it for the Default policy"**
   - `sync` upserted the metric.
   - Investigated `/api/policies/*` and reported that the documented
     `policy-settings` schema only covers
     vcPricing/workloadAutomation/capacity — no super metric
     enablement. Manual UI step required.

## Phase 3 — Object type assignment

6. **"Great first attempt - however you did not include an object type
   that this should be calculated on. … please add this to claude.md
   as a rule"**
   - Added a rule to CLAUDE.md mandating an object-type field on every
     super metric YAML, defaulting to the object of interest.

7. **"I believe the object type is part of the json spec. see this
   example I had previously built …"** *(user pasted an exported
   super metric JSON containing a `resourceKinds` array)*
   - Confirmed the undocumented `resourceKinds` field on
     `/api/supermetrics`.
   - Wired `object_type` through loader → client → API as
     `resourceKinds`.
   - Flagged that GET `/api/supermetrics/{id}` strips the field, so
     UI verification is still required.

8. **"how'd you determine the object_type is the parameter vs.
   resourcekind that exists in the exported json of a supermetric?"**
   - Came clean: `object_type` was a naming choice on my part, not
     grounded. The wire format is a list of
     `{resourceKindKey, adapterKindKey}` pairs.

9. **"please update everything including claude.md to refer to VCF
   operations nomenclature."**
   - Renamed YAML field to `resource_kinds`, with
     `resource_kind_key` and `adapter_kind_key` matching the wire
     names exactly.
   - Updated loader, client, CLI, all 5 YAML files, and CLAUDE.md.

## Phase 4 — Policies investigation

10. **"please examine the policies section of the api spec. I'd like
    you to determine if we can enable [super metrics in a policy] via
    API"**
    - Cataloged every `/api/policies/*` endpoint and the
      `policy-settings` schema.
    - Confirmed: documented JSON endpoints cannot enable a super
      metric in a policy. Only path is
      `/api/policies/export` → edit ZIP → `/api/policies/import`,
      which is undocumented and brittle.

## Phase 5 — Demo polish

11. **"please push our supermetrics to vcf operations - but I'd like
    them all to be slightly renamed `[AI Content] <…>` to make them
    easily identifiable for demo"**
    - Prefixed all 5 YAML names with `[AI Content] `.
    - Discovered the API rejects multi-line formulas
      (`"must match .+"`); added `_normalize_formula` in `client.py`
      to collapse whitespace before sending.
    - Re-synced; all 5 created/updated successfully.

## Phase 6 — Views and dashboards (in progress)

12. **"since we are working this up as a demo. Please keep track and
    document the significant prompts I've given so I can recreate this
    as needed. Let's turn our attention to views and dashboards. …
    create a dashboard that provides a view of virtual machines with
    key CPU and memory performance metrics, filterable (likely by an
    object list interaction to our view) by vCenter."**
    - Created this prompt log.
    - (Investigation of dashboard authoring path in progress.)

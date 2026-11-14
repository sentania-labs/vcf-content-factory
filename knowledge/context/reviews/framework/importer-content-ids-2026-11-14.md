# Framework review: content id grammar and minted recommendation keys

- Branch: `fix/minted-recommendation-id`, commit `28b1b9ed` on `7cd551ee`
- Area: `src/vcfcf_core/content_ids.py` (new), `src/vcfcf_core/importer/convert.py`,
  `src/vcfcf_extractor/importer.py`, `src/vcfcf_core/alerts/loader.py`,
  `src/vcfcf_core/packaging/pak_content.py`, `src/vcfcf_managementpacks/buildkit.py`
- Reviewer: framework-reviewer, 2026-11-14 (static, pre-PR; no live instance)
- Verdict: **CHANGES REQUESTED** (1 BLOCKING, 4 WARNING, 1 NIT)

## Checks re-run

| Check | Result |
|---|---|
| Validate chain (7 packages) on the branch | all exit 0 |
| `bash scripts/path_reference_audit.sh` | clear (2 standing-exception warnings, unchanged) |
| pytest, full suite (`-m "" --override-ini addopts=`, serial; xdist is not installed here) | branch 4996 passed / 8 failed / 12 skipped; base 4954 / 8 / 12 |
| pytest delta by test name | +42 PASSED, all new: 40 in `tests/test_content_id_grammar.py`, plus `test_core_contract.py::test_core_module_imports_with_no_environment[vcfcf_core.content_ids]` and `::test_core_module_static_contract[vcfcf_core/content_ids.py]`. No test changed state. The same 8 fail on base and branch (environment: 2 in `test_gap_b_f_d.py` JMESPath, 5 in `test_common_doctor.py` venv, 1 in `test_dashboard_import_all_skipped.py` RecursionError) |
| Wire grammar over `reference/references/` (all content-side definitions, describe.xml excluded because the gate does not read it) | 0 refused out of 844 dashboards, 2858 views, 502 reports, 234 SMs, 327 alerts, 960 symptoms, 260 recommendations |
| Pak gate `id_grammar_errors` over 120 `.pak` files (repo `dist/`, every `content/sdk-adapters/*/dist`, `/mnt/holding` builds and backups, reference vendor paks) | 2 hits, both `vcfcf_sdk_vcommunity.0.0.0.17.pak` (the bug pak, a true positive). 0 false positives on vendor or factory paks |
| Recommendation loader over every recommendation YAML (repo `content/`, `third_party/`, `tests/`, `bundles/`, all `content/sdk-adapters/*`, `/mnt/holding`) | 43 files, the same result on base and branch, 0 newly refused |
| Byte stability on the real pak (`vCommunity_0.8.1-...-releasedimage.pak`, read-only), base vs branch, `--ids mint` | A (plain) and B (`--map-kind` + `--describe`): only `recommendations/vcommunitycollectionwarnings.yaml` (the `id:` line), `id_map.tsv` (one row) and `report.json` (`objects[n].id`) differ. **Confirmed.** Note: `--layout pak` exits 1 on base and branch alike for this pak (PAK CHECK on dashboards, unrelated), so the trees compared are `--layout third-party` |
| Kit isolation | assembled kit 1.0.29 into scratch; `sdk_buildkit.pak_content` and `sdk_buildkit.alerts_loader` import `content_ids` from the kit and refuse the 0.0.0.17 key |

## BLOCKING

### B1. A minted key embeds the adapter kind verbatim: kinds with spaces exit 5

`src/vcfcf_core/content_ids.py:108` (`mint_recommendation_key`), called from
`src/vcfcf_core/importer/convert.py` `final_id`.

The mint is `Recommendation-df-{adapter_kind}-{uuid}` with no change to the
kind. Adapter kind keys with spaces are real: `EP Ops Adapter`
(`reference/references/tkopton_aria_operations_content/SSLCheckFiles/tkopton-certificate-expiring.xml`)
and `vCenter Operations Adapter` (the Ops self-monitoring kind, in the product's
policy exports). The YAML rule (`xs:ID`) refuses the minted key, so the
post-mint check reports it as a converter bug.

Failing input: the synthetic test source (`test_import_local._build_source`,
alert, symptoms and recommendation only) with every `adapterKind="VMWARE"`
changed to `adapterKind="vCenter Operations Adapter"`, run with
`import-local <src> --layout third-party --ids mint --mint-namespace probe --naming unprefixed --verify`:

```
INTERNAL ERROR recommendation probeRecommendationKey ...: minted id
'Recommendation-df-vCenter Operations Adapter-8511815e-a67c-525c-b739-52f37b0ff6c2'
is refused by its type's grammar: ... is not an XML id
FAILED alert ... references recommendation probeRecommendationKey, which did not convert
exit 5
```

On base the same run exits 0 with `Recommendation-8511815e-...`, which the
product refuses. So this is not a regression against working output. It is
the stated fix failing for a real class of input: the converter mints an id
that its own grammar refuses, which the code defines as an internal error, and
the only way around it is a hand-written `--id-map` row. The YAML `xs:ID` rule
is correct here. The pak's own `content/alertdefs/alertDefinitionSchema.xsd`
declares `Recommendation/@key` as `xs:ID` and every `ref` as `xs:IDREF`, so the
fix belongs in the mint, not in a looser grammar. This is the key-derivation
anchor class (`6c59f6b`: a key built from context without the right transform).

Smallest fix: build the kind segment through the same character rule, for
example `re.sub(r"[^A-Za-z0-9_.\-]", "_", adapter_kind)` (this keeps it
deterministic and `xs:ID`-valid), and add a test that mints for
`EP Ops Adapter` and `vCenter Operations Adapter`.

## WARNING

### W1. A recommendation's minted key depends on which referencing alert comes first

`src/vcfcf_core/importer/convert.py:703`
(`rec_kind.setdefault(ref, o.payload.get("adapterKind") or "")`) and `:718`.

The kind used to be "unused on the wire". Now it is part of the key, so the
order of the source affects the id. Failing input: one alert file that holds
two alerts referencing the same recommendation, one on `VMWARE` and one on
`KindB`. The order `VMWARE, KindB` mints
`Recommendation-df-VMWARE-8511815e-...`; the order `KindB, VMWARE` mints
`Recommendation-df-KindB-8511815e-...`. Same objects, different key, so a
re-export with its alerts in another order re-ids the recommendation. That
breaks the "rerun updates rather than duplicates" promise (RULE-007 stability;
`importer_offline_conversion.md` §ids). A first alert with an empty
`adapterKind` also pins `""`, and the fallback then writes `VMWARE` even when a
later alert has a kind. Fix: choose the kind order-independently (for example
the sorted-first non-empty kind, or a note and a fixed rule when they differ),
and test both orders.

### W2. The report note says the kind is unused on the wire; under `--ids mint` it is in the key

`src/vcfcf_core/importer/convert.py:720-723`. Failing input: any recommendation
that no alert references, run with `--ids mint`. The report says "VMWARE is
written (unused on the wire: the explicit id is rendered)", but the minted key
is `Recommendation-df-VMWARE-<uuid>`. The fix is to say so under mint.

### W3. Evidence and inference in the docs and the gate

- `knowledge/context/wire-formats/alert_fidelity_wire_format.md:148`: "the
  product adding `-df-` itself (reported from the same install)" next to
  "What the stored id of a bare key is exactly ... is not recorded in the repo".
  Either cite where it is recorded or mark it as an unverified report.
- Same doc, `:160-163`, and `importer_offline_conversion.md:215`: the minted
  form `Recommendation-df-<kind>-<uuid5>` has **not** been seen installing on any
  instance. The vCommunity Java 1.0.0.18 changelog lists it as unreleased, and
  only the prefix rule in the error message supports it. Say "inferred from the
  error text and the export shape; not yet installed". Before release, the
  orchestrator needs one install of a pak carrying it ("done means seen
  working"). The same applies to a kind segment that is not the pak's adapter
  kind (`KindB`, the `VMWARE` fallback): whether the product checks it is not
  recorded.
- `src/vcfcf_core/content_ids.py:80-84` and doc `:156,172` drop the `xs:ID` rule
  from the wire check because "the product's own exports carry keys with
  spaces". Both such exports in the corpus are **policy** exports
  (`AriaOperationsContent/vropstopdashboard/SampleDefaultPolicy.xml`,
  `hol-2501-lab-files/HOL-2501-11/Module 5/autoscale-policy.xml`), not
  content-import alert files. The pak XSD
  (`content/alertdefs/alertDefinitionSchema.xsd`) types the key `xs:ID`.
  Failing input for the gate:
  `wire_id_problem("recommendation", "Recommendation-df-EP Ops Adapter-x")`
  returns `None`. A factory alert YAML on `EP Ops Adapter` with no explicit
  recommendation id derives exactly this key (`loader.py:191`) and passes
  loader and gate. Either keep the `xs:ID` rule for `content/alertdefs/` in the
  gate, or record that a space key is not known to be refused, with the policy
  export named as the only evidence.
- The loader rule now refuses `Recommendation-<x>` on every path (REST sync,
  content-zip sync, pak). It was measured on the pak path
  (`AlertDefinitionServiceImpl.importAlertDefinitions`). That the content-zip
  sync path reaches the same service is likely but not stated as inference.
  The practical effect is narrow (only YAML minted on main before this fix
  carries such keys, and re-minting clears it), but the doc should say which
  path was measured.

### W4. Kit release notes do not announce the new build failure

`.github/release-notes-buildkit.md:5` ("Behavior since 1.0.29"). Kit 1.0.29 is
not tagged yet, and `build-sdk`/`validate-sdk` in the kit now refuse a pak whose
built `content/` carries a refused recommendation key, an empty symptom or
alert id, or a non-UUID view, dashboard, report or super metric id
(`sdk_builder.py:3431` through `check_pak_content`). The notes say nothing
about this, nor about the #367 content gate it extends. Add a bullet with the
adoption line: the six registered paks pass, and vCommunity Java 0.0.0.17
content fails until it is re-minted.

## NIT

### N1. A lower-case `recommendation-` prefix is refused without evidence

`src/vcfcf_core/content_ids.py:88`. Lower-case keys are refused although the
importer's case behaviour is not recorded. This is honestly labelled a factory
caution, and the corpus has no content-side instance (describe.xml's
`recommendation-<n>` keys are outside the gate's `content/` scope). It is
acceptable as is. Mention in the loader message that this case is a factory
caution, not the measured product rule, so a user who hits it knows which
kind of rule stopped them.

## Dimensions proven safe

- Global/pak leak (`00d3382`): no renderer changed. The loader adds only a
  refusal, and corpus-wide nothing that loaded before is refused now. The gate
  runs only on `check_pak_content` (SDK build, validate-sdk, kit). The
  standalone content-import path renders the same bytes as before.
- Stale-zip discipline: no file in the CLAUDE.md "After tooling changes" list
  is touched (`pak_content.py` is not `assembly.py`; `alerts/loader.py` is not
  `alerts/render.py`). No rendered byte changes, so no rebuild and no
  `CURRENT_TEMPLATE_VERSION` bump is needed. The kit tarball does change
  (W4).
- Cascade: a kept `Recommendation-<uuid>` source key fails that recommendation,
  and its alert fails as "references recommendation ..., which did not convert".
  A kept non-UUID symptom id now fails at plan time with a mint/map hint
  instead of at verification (better message, same outcome class).
- `--id-map`: header, comment and blank lines are skipped and the reported
  line number is the physical line (a bad row on line 4 after header, comment
  and blank was reported as `line 4`). `Recommendation-df-` with nothing after
  it is refused; `Recommendation-ud-ok` is accepted. Exit 2 in both refusals.
- Determinism and collisions: the uuid5 is unchanged (same namespace, type
  and source id), so two recommendations cannot collide. Only the kind segment
  varies (W1).
- `--map-kind`: the minted key follows the re-pointed kind
  (`Recommendation-df-ProbeKind-...` on the real pak). `--rename` and
  `--naming` do not touch the key.

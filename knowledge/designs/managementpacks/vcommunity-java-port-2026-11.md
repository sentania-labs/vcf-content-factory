# vCommunity (e1-rahabok 0.8.1) Java SDK port

- **Type:** managementpack
- **Slug:** vcommunity-java-port-2026-11
- **Authored YAML:** not assigned yet (new pak repo, private until the
  licensing record is complete; name and adapter kind pending the owner's
  decision)
- **Date:** 2026-11-12
- **Status:** drafted

## Initial prompt

> User: Based on our previous experience porting the vcommunity pak to Java
> and its pieces, our recent experience with the python paks, observing nick
> wilsons experience using his VCF-cf fork to port his vsan metrics and
> network metrics pak to our Java sdk.  Perform a fresh evaluation of porting
> e1's update of the vcommunity pak.
>
> Present a plan to migrate all content, metrics and properties.  It should
> provide full content parity and initially full configuration parity.
>
> Assess providing this as an upgrade path friendly vs clean VCF-cf
> branding, -as well as if there is value in resurrecting our pre-split port
> effort.

> User: Include onurs as well as it is an ancestor of e1's to make sure we
> don't miss anything

> User: Documentation will change and be irrelevant in many cases for our
> new Java pak.

> User (after the evaluation and plan were presented): So let's begin, but
> keep the repo private until all are documented.
>
> The edited views - we need to give them their own identity so we don't
> overwrite OoTB - otherwise an upgrade will stomp them.  So I'm leaning
> towards a reauthor.

The turns about licensing and contributor consent are deliberately not
reproduced here. The owner is handling that record; the pak repo stays
private until it is complete, and the license chosen is MIT.

## Vision

A Tier 2 Java SDK management pack with full parity to
`e1-rahabok/VCF-vCommunity-Adapter` 0.8.1 (the continuation of
`vmbro/VCF-Operations-vCommunity`), built fresh from the current SDK
template, not from the retired 2026 Java port.

- **Keys:** the 254 keys the Python collectors publish (85 metrics, 169
  properties) plus the three check-list-driven families, with identical key
  strings and instance names, landing on the same objects (228 on VMWARE and
  Container objects, 26 on three own object types). The published keys are
  the contract, not the declarations in `definition.py`.
- **Configuration:** initially identical: the 19 instance fields, the
  four-field credential, the six check-list files.
- **Content:** every dashboard, view, report, super metric, alert and
  symptom of 0.8.1. Views that began as edited built-in views are
  re-authored through the factory pipeline under ids of their own, so the
  pak never overwrites built-in content and an upgrade never removes it.
- **Identity:** a new lowercase adapter kind with factory vendor and display
  name; the `vCommunity|` key namespace is kept so history on vCenter
  objects can continue and upstream content keeps resolving. Not an in-place
  upgrade of the Python pack (tested not viable 2026-06-10).
- **Documentation:** written new for the Java pak; upstream docs are a
  behavior reference only.
- **Out of scope:** the Hardware vCommunity pack; content and keys that the
  0.8.1 line itself dropped.

## Decisions (owner, 2026-11-12)

- **Names:** repo `sentania-labs/vcf-content-factory-sdk-vcommunity-java`
  (private for now), adapter kind `vcfcf_vcommunity`, display name
  `VCF Content Factory vCommunity`. "The names you propose are fine."
- **Key tree:** `vCommunity|…` unchanged.
- **Content names:** upstream names, `content_naming: unprefixed`. A
  re-authored view whose title equals a built-in view's title gets a
  distinct title.
- **Report honestly:** "I agree with your plan- report honestly". Same key
  names and the same values whenever the read works. A failed or missing
  read sends nothing for that key and is counted in collection health; it
  never becomes a zero, False or other definite value (the map lists 152
  rows where upstream does that). The host license key is masked. A bad
  check-list entry is skipped and reported, not fatal to the cycle. Every
  deviation from upstream is listed in the design.
- **Content route:** grow the factory YAML route (view schema, importer,
  dashboards, reports, alerts) rather than add a raw passthrough.
- **Map:** `knowledge/context/api-maps/vcommunity-e1-collection-map.md` and
  `vcommunity-e1-key-map.tsv`.

Evaluation inputs (session scratch, to be distilled into the API map and the
design): inventory of 0.8.1, ancestor diff against the vmbro line, review of
the retired port, and the outside-user and vsanperf porting experience.

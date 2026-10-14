# Compliance build 93: Auto only, certificate accept dialog, minimal account dialog

- **Type:** managementpack (Tier 2 SDK adapter change), build 93
- **Slug:** compliance-build-93-auto-only-cert-accept
- **Adapter repo:** `content/sdk-adapters/compliance/`
- **Date:** 2026-10-13
- **Builds on:** build 92 (`compliance-build-92-drop-custom-skip-cancel.md`)
- **Status:** go from Scott 2026-10-13 ("okay - go ahead."); build 92 identity result PASS (remove, do not hide); build 93 installed on devel 2026-10-13 4:19 PM (54ca857, pak 6c436c55): identity, dialog, name check PASS; accept dialog seen on an IP host; not-collected marker unproven (adapter issue #43); merged to main via PR #47 and released as v1.0.0.93 (CI build on sdk-buildkit 1.0.11, 2026-10-13 8:53 PM)
  authoring starts when the build 92 identity result and the Advanced
  Settings placement investigation are in

## Initial prompt (Scott, verbatim, 2026-10-13)

> where did we settle on the SSL validation cert for MP ? can we move Allow
> insecure SSL to advanced settings? and efault to true "Prompt the user to
> trust and accept the cert"

> I don't see custom, but I see all different SCGs. If we have this set to
> auto - the pulldown can just go away right?

> So the main configs would be now: Host / Credential / Collector / Advanced
> Settings: Override File Name / Read vcenter settings (true false pulldown)
> / Allow Insecure (true false pulldown) <-basically instructs fi the user
> must "accept" a self signed cert?

> if we are prompting the user always - they can then accept whatever and
> this setting is meaningless

> okay - go ahead.

## Vision

The account dialog is: Host, Credential, Collector (native), and under
Advanced Settings: Overrides file name, Read vCenter appliance settings.
Nothing else.

1. **Compliance Profile setting removed.** Every instance runs Auto (by
   version). An account that stored a fixed version logs one INFO line
   naming the stored value and runs Auto. The bundled profiles and
   manual-review overlay are unchanged.
2. **Instance-wide pin returns to the overrides file.** `<Profile
   version="..."/>` without `kind` pins the whole instance; with `kind`
   pins one object type; kind wins over instance. The file is the one place
   for version decisions. Template, docs and tests updated (build 92's
   rejection of the kind-less form is reverted).
3. **Allow Insecure SSL removed.** The adapter validates the vCenter
   certificate against the platform trust store, always. The adapter
   implements the framework hook `certificateCheckUrls` returning the
   vCenter's HTTPS root so Validate Connection shows Ops's Review and
   Accept Certificate dialog; the accepted certificate is stored on the
   instance and trusted on every cycle. Hostname mismatch is not covered
   by acceptance: the error text and docs say to enter vCenter by the name
   on its certificate, as the native vCenter adapter does. An account that
   stored `allowInsecure=true` logs one WARN and validates strictly; if its
   certificate is not yet accepted it goes to the certificate error state
   with the message "open the account and Validate Connection to accept
   the certificate".
4. **Advanced Settings placement.** `overrides_file` and
   `read_appliance_settings` sit under the dialog's Advanced Settings
   expander. Mechanism: per
   `knowledge/context/investigations/2026-10-13-account-dialog-advanced-settings-and-cert-accept.md`
   (pending). `read_appliance_settings` becomes a true/false enum rather
   than a free string.
5. **Docs**: installing.md loses the TLS opt-out section and the literal
   "true" footnote, gains the accept-dialog walkthrough and the hostname
   rule; overrides.md gains the instance-wide pin; README and
   data-reference updated; generated docs regenerate.

Identity-bearing settings removed by this build: `benchmark_profile`,
`allowInsecure`. **Decision gate:** if the build 92 devel install shows
accounts survive the removal of `custom_profile_path` intact (same id,
save unchanged succeeds), 93 removes both. If not, 93 keeps both as
`hidden` identifiers with their old defaults and the adapter ignores them.

## Verification on devel (separate go)

Upgrade over 92; the three accounts keep their ids; open wld01, the
dialog shows Host, Credential, Collector and the two advanced fields only;
Validate Connection on wld01 (whose certificate is untrusted today) shows
the accept dialog, accepting it lets Validate pass, and the next cycle
collects with the stored certificate; the overrides pin for the instance
works through the file; mgmt (trusted certificate) validates with no
prompt.

## Out of scope

- The buildkit release if the hook is missing from the version CI builds
  against (the investigation says which); if so, 93 waits on that tag.

## Scope extension (Scott, verbatim, 2026-10-13)

> also ensure that unifi and synology handle SSL verification identically

The same TLS model applies to the unifi and synology adapters (own repos,
own builds): strict validation against the platform trust store, the
`certificateCheckUrls` hook returning the controller / DSM HTTPS root so
Validate Connection offers the accept dialog, `allowInsecure` removed with
the same stored-value handling, hostname rule in the docs. Those targets
are self-signed almost everywhere, so the accept dialog is the normal path
for them, not the exception. Order: compliance 93 proves the hook on
devel first; then unifi and synology get one build each with the same
change, serially (one author at a time), each reviewed and installed on
devel under its own go.

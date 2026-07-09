# MP authoring design principles

Rules and patterns for deciding *what to ship* in a management pack
when the target API exposes more than MPB's grammar can express
cleanly. Complements `management_pack_authoring.md` (which covers
*how* to write the YAML) by codifying the *what not to ship* rules
that prevent shipping fragile constructs.

The framework's goal is paks that behave the same on day 1 and day
N+500 across every customer's hardware fleet. Authoring decisions
that depend on hidden invariants (response ordering, single-element
result sets, vendor stability) are bugs waiting to bite a stranger.

## Principle 1: No fragile constructs

A pattern is **fragile** if it relies on any of:

- **Stable element ordering in a JSON array** the vendor does not
  contractually guarantee (e.g. assuming `radio_table[0]` is always
  the 2.4 GHz radio).
- **Cardinality assumptions** that the vendor can change in a
  firmware update (e.g. dual-band APs reordering to add a 6 GHz
  radio at index 0 in a Wi-Fi 6E refresh).
- **Display-name parsing** for identifiers that should come from a
  stable field.
- **Substring/regex extraction** from a free-form string field
  when a structured field is available elsewhere in the response.
- **Index access into chained/paginated arrays** where the slice
  varies per request.

If the only way to extract a value within MPB's grammar would
require a fragile construct, **do not ship it**. The cost of a
silent wrong-band metric or a swapped device identifier is much
higher than the loss of the data point — and the customer has no
way to know they're being lied to.

## Principle 2: Three options when MPB grammar can't express it

When the API exposes data MPB can't extract through clean grammar,
choose one of three exits — never invent a fragile workaround:

1. **Drop scope.** The metric/property is out of v1. Document the
   deferral in the design artifact (`designs/<mp>.md` §Risks) and
   move on. Most cases land here.

2. **Wait for MPB grammar support.** If the gap is a known
   roadmap item (jq filter projection is targeted for MPB 9.2 per
   first-party confirmation), park the work. The YAML stays clean
   and ships when the runtime catches up. Note the deferral in
   `knowledge/context/known_limitations.md`. Caveat: 9.2's jq addon is
   bolted onto a Jackson-`JsonNode`/dot-path engine, not a
   replacement of it — predicate support will be a feature flag
   on top of the existing grammar, not a generalized JMESPath
   evaluator. Re-verify the actual capability surface when 9.2
   ships.

3. **Escalate to Tier 2 (native SDK pak).** Some patterns require
   imperative collection logic that no declarative grammar will
   ever express well — multi-step session enrichment, cross-row
   joins with conditional logic, response transforms based on
   per-element state. These belong in a Tier 2 native Java/Kotlin
   SDK pak, not in Tier 1 (MPB-built). The framework's Tier 2
   pipeline is on the roadmap; for now, log the requirement as a
   future Tier 2 candidate in the design artifact.

The orchestrator should surface this decision tree the moment an
authoring agent reports a grammar gap. Don't ship "good enough"
with a fragile workaround.

## Principle 3: Verify before deferring

Before declaring something a grammar gap, the agent should verify
the gap empirically when feasible:

1. Author the simplest version of the expression that *should*
   work (one metric, one path, no chaining).
2. Run it through the MPB pipeline on devel via the design import
   API (or through the factory pak on a lab instance).
3. Capture the adapter log + collected sample. If the value
   doesn't appear and the log shows the expression was ignored or
   produced an empty result, that's confirmation.

This protects against false negatives ("MPB doesn't support X")
that would have worked with a small expression tweak. It also
protects against false positives where an agent decides the
grammar works without checking, ships fragile code, and a customer
catches the lie.

The radio-metric investigation (Case Study 1 below) followed this
process: empirical test → cleanroom spec review → first-party
engineer confirmation → consensus that the runtime parser predates
predicate support. All three layers agreed before we dropped the
metrics from scope.

## Principle 4: The label is the metric key

MPB derives metric keys from labels at the runtime layer
(see `mpb_explicit_key_investigation_2026_05_16.md` for the
algorithm). The factory honors this same derivation so paks built
either way emit identical keys. **Choose labels that derive to
clean keys**:

- Avoid `%`, `.`, `()`, double-spaces in labels.
- Prefer `Pct` over `%`, `Seconds` over `(s)`, `1m` over `(1m)`.
- The `key:` field in YAML is an authoring-side identifier (used
  for in-YAML cross-references); it is not the on-wire key.

This is a corollary of "no fragile constructs": a key that depends
on YAML override drift between factory and MPB pipelines IS a
fragile construct — content authored against one path silently
breaks against the other. The fix is to remove the divergence at
the source.

## Principle 5: Document the deferral

Every dropped or deferred capability gets recorded in three
places:

1. **`knowledge/context/known_limitations.md`** — durable note: what's
   missing, why, when it might come back.
2. **`designs/<mp>.md` §Risks** — design-time decision record:
   what the user was promised vs what shipped.
3. **`content/managementpacks/<mp>.yaml`** comment header — a
   one-line `# Deferred: <feature> pending <gating event>. See
   knowledge/context/known_limitations.md §<n>.` so the next reader
   doesn't have to dig.

Future authors should encounter the deferral before they re-invent
the same investigation. Sessions are cheap; rediscovering the same
limitation three times is expensive.

## Case Study 1: UniFi radio metrics (deferred)

**Context.** UniFi's `/devices` response includes a `radio_table[]`
array with one entry per radio band on the device. Each row has
fields like `radio: "ng"|"na"`, `channel`, `tx_power`, `tx_retries`.
The natural extraction is by predicate:
`radio_table[?radio=='ng'].tx_retries` for the 2.4 GHz band.

**The gap (definitive).** MPB's runtime expression grammar is
much narrower than JMESPath. Cleanroom-team empirical bound from
54 distinct compiled paths across two reference paks (UniFi +
phpIPAM):

- **100% pure dot-notation field navigation.** Arbitrary nesting
  works (`securityConfiguration.saeConfiguration.anticloggingThresholdSeconds`)
  but nothing beyond field traversal.
- **Exactly one wildcard form: `data.*`** — iterate the top-level
  array. Confirmed across both paks.
- **Zero occurrences** of brackets `[]`, predicate projections
  `[?...]`, pipes `|`, slice `[start:end]`, or function calls.
- **Designer-side `expressionParts[].originId` encodes collection
  mode as one of two literal strings:** `"base"` (single object,
  no iteration) or `"data.*"` (iterate top-level array). Trailing
  path uses pure dot-notation. No nested `data.*.X.*` observed.
- **Backing engine:** Jackson `JsonNode` via
  `BuilderQueryJsonNodeParserKt` — NOT Jayway JsonPath, NOT
  JMESPath. So even when MPB 9.2 adds a jq tag-on, it's bolted
  onto a dot-path engine, not a replacement of it.

**Verification (three independent confirmations).**
1. Empirical: side-by-side test of factory pak (prod) and MPB
   pipeline (devel) — both produced only the 8 base metrics, no
   radio metrics or properties.
2. Cleanroom corpus analysis: 54 compiled paths sampled across
   UniFi + phpIPAM reference paks, zero predicate use.
3. First-party: MPB's principal engineer confirmed jq filter
   support is planned for MPB 9.2 — but this is an addon, not a
   change to the underlying grammar.

**The fragile alternative we rejected.** Index access
(`radio_table[0]` / `radio_table[1]`) would have shipped, but
relied on UniFi never reordering and tri-band Wi-Fi 6E APs never
appearing in the customer's fleet. Both are out of our control
and would produce silent wrong-band metric labels — a worse
failure mode than not shipping the metric at all.

**The decision.** Drop the 8 radio metrics + 6 radio properties
from UniFi 1.0.0.13. Documented in `knowledge/context/known_limitations.md`
§"MPB runtime: dot-path + `data.*` grammar only" and in the UniFi
YAML header comment.

**The structural pattern (for the future).** Even with 9.2's jq
addon, the natural MPB shape for per-element data is a **separate
ResourceKind per band**, fed by either (a) a flat `radios`
endpoint iterated via `data.*`, or (b) a chained request per band
using `objectBinding.requestMatchIdExpression` with
`@@@MPB_QUOTE_REQUEST_PARAMETERS`. UniFi's existing Track-C MP
already follows the "one kind per concept" pattern (clients,
devices, networks, wifi_broadcasts). Re-adding radios should
follow the same pattern, not retrofit predicates into the device
expression. If neither (a) nor (b) is feasible against the UniFi
API surface, the radios are a **Tier-2 promotion candidate** —
imperative collection logic with `JsonNode` fan-out, not a
declarative grammar fit.

## Related

- `context/management_pack_authoring.md` — *how* to write MP YAML
- `knowledge/context/known_limitations.md` — current capability boundaries
- `context/mpb_explicit_key_investigation_2026_05_16.md` — label→key
  derivation algorithm
- `context/mpb_designer_wire_format.md` — runtime expression form,
  including the structured expression model that has no predicate
- `context/mp_chain_authoring.md` — chained metricSets (the
  alternative to filter projections for per-element extraction)
- `.claude/agents/mp-designer.md` — design-time TOOLSET GAP path
- `.claude/agents/mp-author.md` — authoring-time refusal rules

# MPB Adapter Runtime Variable Scopes

Definitive reference for all variable substitution scopes supported
by the MPB adapter runtime (Gen-2, VCF Ops 9.x). Derived from
bytecode analysis of the `SubstitutionFields` and
`FieldSubstitutionKt` classes in `mpb_adapter-9.0.1-patch-1.jar`,
cross-validated against factory-built template.json files and
reference design exports.

**Date:** 2026-05-17
**Source:** `com.vmware.mpb.FieldSubstitutionKt.getSubstitutionFields()`
bytecode; `com.vmware.mpb.SubstitutionFields` class model;
`com.vmware.mpb.client.SubstitutionFieldsKt.withSubstitutions()`.

---

## Exhaustive list of supported variable scopes

The runtime's `FieldSubstitutionKt.getSubstitutionFields()` method
parses all `${...}` tokens in a string using the regex
`\$\{.*?[}]` and classifies each into exactly one of 7 categories,
checked in this order:

| # | Prefix / match | Scope name | Example | Source |
|---|---|---|---|---|
| 1 | `authentication.session.<key>` | SESSION | `${authentication.session.set_cookie}` | Session token response fields extracted during auth |
| 2 | `authentication.basic` (exact) | BASIC | `${authentication.basic}` | Auto-computed `Basic <base64>` string |
| 3 | `requestParameters.<key>` | PARENT_REQUEST_PARAMS | `${requestParameters.pool_id}` | Chained-request per-row values from parent |
| 4 | `constants.<key>` | CONSTANTS | `${constants.base_url}` | Top-level `BuilderConstant` entries |
| 5 | `authentication.credentials.<key>` | CREDENTIAL | `${authentication.credentials.api_token}` | User-input credential fields |
| 6 | `configuration.<key>` | CONFIG_PARAM | `${configuration.mpb_hostname}` | Adapter instance configuration parameters |
| 7 | (anything else) | UNKNOWN | (falls through to unknown set) | Unrecognized; logged at runtime |

**These are the ONLY supported scopes.** The parser is a sequential
if/elif chain with no extensibility. Any `${...}` token that does
not match scopes 1-6 falls into the `unknown` set.

---

## No time/date variables exist

**The MPB adapter runtime does NOT support any built-in time or date
variables.** Specifically, the following do NOT exist:

- `${now}`, `${timestamp}`, `${currentTime}`
- `${collection.startTime}`, `${collection.endTime}`
- `${epoch}`, `${date}`, `${time}`
- `${schedule.*}` or `${interval.*}`
- Any relative time expression function or format
- Any date arithmetic or formatting function

The 7 scopes listed above are exhaustive. There is no plugin or
extension mechanism for adding new variable scopes -- the parser is
hard-coded Kotlin bytecode.

---

## Expression namespaces in template.json

Template.json uses three distinct expression syntaxes, each for a
different context:

### 1. Body field extraction: `@@@MPB_QUOTE_BODY`

Used in `expression`, `listExpression`, and `attributeExpression`
fields within resource metrics and chaining parameters.

```
"${@@@MPB_QUOTE_BODY data.viewer.zones[0].httpRequests1hGroups[0].sum.requests @@@MPB_QUOTE}"
```

Evaluated by `ResourceQueryHelperKt` against the JSON response body.

### 2. Request parameter reference: `@@@MPB_QUOTE_REQUEST_PARAMETERS`

Used in `objectBinding.requestMatchIdExpression` to reference a
chained request parameter value for object binding.

```
"${@@@MPB_QUOTE_REQUEST_PARAMETERS id_zone @@@MPB_QUOTE}"
```

Extracts the chained parameter value used in the current request
iteration for matching to a resource.

### 3. UUID reference: `${<uuid>}`

Used in `objectBinding.resourceMatcherExpression` and
relationship `expression` fields to reference a
`resourceMatchers[].id` or `matchIdentifiers[].id`.

```
"${5eb46776-7ee5-53d2-b413-f67e94e2af19}"
```

### 4. Variable substitution: `${scope.key}`

Used in request `path`, `params[].value`, `headers[].value`, and
`body` fields. These are the 6 scopes documented above.

```
"Bearer ${authentication.credentials.api_token}"
"/zones/${requestParameters.id_zone}/dns_analytics/report"
"${configuration.mpb_hostname}"
```

---

## Implications for time-dependent API requests

Since no time variables are available, APIs that require time
parameters must use one of these workarounds:

### Workaround 1: Hardcoded relative time strings (preferred)

Many APIs accept relative time strings natively. The Cloudflare DNS
Analytics endpoint accepts `since=-5minutes&until=now` as literal
query parameter values. These are passed through as static strings
in `params[].value` -- the MPB runtime sends them verbatim, and the
target API interprets them.

Example from the factory's Cloudflare template.json:
```json
"params": [
  {"id": "since", "key": "since", "value": "-5minutes"},
  {"id": "until", "key": "until", "value": "now"}
]
```

This works because `-5minutes` and `now` are Cloudflare API
features, not MPB runtime features. The adapter runtime sends them
as opaque strings.

### Workaround 2: Fixed lookback windows

For APIs that require absolute timestamps (ISO 8601, epoch), there
is no MPB-native solution. Options:

1. **Use a wider aggregation window** (e.g., last-1-hour dataset
   instead of last-5-minutes). The Cloudflare GraphQL
   `httpRequests1hGroups` dataset was chosen for this reason --
   it returns the aggregate for the most recent hour with no time
   parameter required (just `limit: 1`).

2. **Avoid the time-parameterized endpoint entirely** and use an
   alternative endpoint that returns "latest" or "current" data.
   Many monitoring APIs have a `/latest` or `/current` endpoint
   that returns the most recent data point.

3. **Promote to Tier 2** if the only available endpoint requires
   absolute timestamps and has no relative-time or latest-data
   alternative. A Tier 2 (native Java) adapter can compute
   timestamps programmatically.

### Workaround 3: Configuration parameter hack

A `configuration` parameter could theoretically hold a
time-related default value (e.g., `mpb_lookback_minutes` with
default `"5"`), but this is a static string -- it does not update
per collection cycle. Only useful as a user-adjustable constant.

---

## Side finding: `${credentials.<key>}` shorthand

The factory's Cloudflare template.json contains:
```
"path": "/accounts/${credentials.account_id}/pages/projects"
```

This uses `${credentials.account_id}` (without the
`authentication.` prefix), which does NOT match any of the 6
supported scopes. It would fall into the `unknown` set. The correct
form is `${authentication.credentials.account_id}`. This is likely
a rendering bug in the factory's template renderer that would cause
the Pages Projects request to fail at runtime (the `account_id`
would not be substituted, leaving the literal
`${credentials.account_id}` in the URL path).

---

## Constants scope (unused by factory, potentially useful)

The `constants` scope references top-level `BuilderConstant` entries
in the template.json. The factory currently emits `"constants": []`
for all paks. Constants could be used to define reusable values
like API version prefixes, but they are static per-design -- they
cannot vary per collection cycle.

```json
"constants": [
  {"id": "abc123", "key": "api_version", "value": "v4"}
]
```

Referenced as `${constants.api_version}`.

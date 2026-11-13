Portable Tier 2 SDK adapter build toolchain (jar-free).

<!-- Order: "Behavior since" sections newest first, so the latest release is at the top. Add a new release's section directly below this comment. The standing reference sections (Consumer contract, Version pinning, Checksum) stay at the end. -->

## Behavior since 1.0.29

- `validate-sdk` and `build-sdk` refuse bundled content under VCF
  Operations stock ids (factory issue #345). A view, dashboard, report
  template, symptom or alert whose id is in the kit's
  `stock_ids_baseline.json` (4282 ids from clean 8.18.7, 9.0.2 and 9.1.1
  exports) is an error naming the YAML file, the id, the type, the stock
  object's name and the versions it is stock in: installing such a pak
  overwrites the stock object and uninstalling it deletes it. The baseline
  holds no super metric or recommendation ids yet: definitions of those
  types are scanned but not checked, and the pass line says so.
  `build-sdk` checks the bundled content before the compile and every
  definition in the built pak after it; a `--release` build deletes a pak
  that fails. References to stock ids are fine.
- Fail closed: without `stock_ids_baseline.json` beside `stock_ids.py`, or
  when a member of the built pak cannot be read (nested too deep, not a
  readable zip, oversized, encrypted or unsupported compression, text that
  does not decode), every `validate-sdk` and `build-sdk` fails.
- Escape hatch: adapter.yaml `stock_id_allowlist`, a list of entries with
  exactly `type`, `id` and a non-blank `reason`. An allowlisted hit is a
  warning on every build; an entry that matches nothing is a warning too.
  Absent by default.
- New `python3 -m sdk_buildkit stock-id-check <path> [...]`: read-only list
  of every definition in a packed or unpacked pak, content zip or export
  whose id is a stock id. Exit 0 clean, 2 stock ids found, 1 cannot check
  (unreadable content, nothing to check, or no baseline). The pass line
  states how many definitions of which types were compared.
- Kit contents: `stock_ids.py` (the factory's
  `vcfcf_core/stock_ids/guard.py`, byte for byte) and
  `stock_ids_baseline.json`.
- Adoption: a pak whose bundled content carries a stock id fails its next
  build; mint new ids for that content. A pak with no such content builds
  as before, and pak bytes do not change. Repos on the floating
  `sdk-buildkit-v1` tag get the guard on their next CI run (the six
  registered paks pass it); repos pinned to an exact `sdk-buildkit-v1.0.x`
  tag must bump their pin to `sdk-buildkit-v1.0.29` to get it.

- `SuiteApiStitcher.post(path, jsonBody)` for the Suite API's read-style POST
  queries (`/api/resources/query`, `/api/resources/stats/latest/query`,
  `/api/resources/properties/latest/query`, `/api/resources/stats/query`).
  It throws like `get` (`SuiteApiHttpException` on a non-2xx, one 401
  retry). Only a path of `[A-Za-z0-9_-]` segments whose last segment is
  exactly `query`, with at most one `?key=value&...` query string, is
  accepted; anything else (a `#` fragment, `;`, `%`, `\`, `.` or `..`
  segments, whitespace) is refused before a token is fetched or a
  connection is opened. The response is read whole into memory, up to
  8 MiB by default (`post(path, jsonBody, maxResponseBytes)` sets another
  cap); a larger body throws `ResponseTooLargeException`, without any of
  the body. Read timeout 30 s: bound the resource ids per query and use
  `page`/`pageSize` where the endpoint takes them. Bodies are never logged.
- `SuiteApiStitcher.pushEvents(events)` with the new `SuiteApiEvent` pushes
  events onto any resource, foreign ones included, through
  `POST /api/events/bulk`. `NOTIFICATION` events are refused, not sent: the
  Suite API answers 200 and silently discards them on another adapter's
  resource (untested on a pak's own resource; refused everywhere because
  the call cannot tell the two apart). Send `DIAGNOSTIC`. A cancel time of
  0 or less is unset; a set cancel time before 2000-01-01 is refused (the
  framework's rule; the spec floors only the start time). Never throws;
  count from the returned `SuiteApiBatchResult` (events, not resources).
- Numeric property values: `pushTypedPropertiesBatch` and `pushTypedBatch`
  take `String` or `Number` values and send numbers as `"data":[...]`.
  Every number is sent as a double (`5` as `5.0`; a fractional `BigDecimal`
  is rounded), and an integer whose magnitude exceeds 2^53 is dropped and
  counted rather than sent as a different number: send a `String` when the
  exact value matters. Null, NaN and infinite values are dropped and
  counted, never sent. Keep one type per key (numeric samples on a key with
  string history are untested). `pushPropertiesBatch` and `pushBatch` are
  unchanged and send the same bytes as before (pinned by golden bodies).
- Icon hints `content_library`, `library_item`, `vm_template`.
- No pak changes behaviour until it calls the new methods; a rebuild alone
  changes nothing on the wire.

## Behavior since 1.0.28

- Release builds accept only SDK jars the kit knows (factory issue #343). A
  release build is `build-sdk --release` (only the pak repos' tag workflow
  passes it) or any `build-sdk` / `validate-sdk` run with
  `--require-sdk-compat` (`VCFCF_SDK_COMPAT_REQUIRED=1`). In it the
  `--sdk-jar` jar must be one of the two 9.0 jars in the Consumer contract
  table and every `--sdk-compat-jar` one of the four, with no override.
  Another line's jar as `--sdk-jar` stops the build naming its line and
  telling you to pass it with `--sdk-compat-jar`; a jar the kit does not
  know stops it with its sha256. Before, any file passed as the primary jar
  was compiled against and shipped, with only a SKIPPED notice on the 9.0
  leg.
- Hand builds (no `--release`, no `--require-sdk-compat`) make the same
  check, print one boxed warning saying what the jar is (or that it is
  unknown), that the pak may not run on every supported line and that a
  release build would refuse it, and build. `validate-sdk` warns and still
  exits 0. `conf/version.txt` `Adapter-Version-Ref` still records what it
  can for an unknown jar.
- `VCFCF_RELEASE_BUILD` and `VCFCF_SDK_COMPAT_REQUIRED` are read the same
  way everywhere: surrounding whitespace ignored, case-insensitive, `1`,
  `true` or `yes`.
- The framework jar's manifest records the sha256 of the SDK jar it was
  compiled against (`X-Vcfcf-Sdk-Sha256`). `build-sdk` rebuilds the
  framework jar whenever that is not the current primary jar, so a release
  build never reuses one a hand build compiled against another jar. A
  framework jar built by an older kit is rebuilt once.
- Test Connection no longer overrides a pak's `conf/logging.properties`
  (factory issue #322). It used to raise every logger it looked up to
  INFO, which added an INFO entry for the adapter class and the helpers
  Test Connection builds: every account added afterwards then lost a
  `DEBUG` level set in the file for those names, and copied their instance
  lines into `collector.log`, until the next log4j reload or collector
  restart. Now the raise is skipped when the pak's own file has a key
  covering the name, already loaded or still to be loaded by the SDK; an
  entry from another pak's file does not count. Under that entry Test
  Connection INFO did not reach `collector.log` before either; WARN and
  ERROR still do, so keep Test Connection diagnostics in the result
  message or at WARN. A pak without the file, and every pak on 8.18 (whose
  SDK never reads the file), behaves as before. Proven in a harness
  against the 9.0.2 and 8.18.7 SDK jars, not yet on a live collector.
- `resources/resources.properties` at the pak root writes `VENDOR=` as
  raw UTF-8, as `DISPLAY_NAME=` and `DESCRIPTION=` always were. Its reader
  is the platform's pak manager, which decodes the file as UTF-8 and knows
  no `\uXXXX` escape; 1.0.26 and 1.0.27 wrote a non-ASCII vendor that way.
  Paks with an ASCII vendor (every pak that sets none) are unchanged.
- Pak bytes: inside `lib/vcfcf-adapter-base.jar`, the manifest shows
  1.0.28 and gains the `X-Vcfcf-Sdk-Sha256` line,
  `com/vcfcf/adapter/VcfCfAdapter.class` changes, two inner classes are
  new (`VcfCfAdapter$Log4jHandles`, `VcfCfAdapter$PakKeys`), and three
  inner classes differ only in line numbers. Nothing else changes unless
  the pak sets a non-ASCII `vendor`.
- Adoption: no source change. A pak repo whose release workflow already
  checks a known jar's sha256 is unaffected; one that passes any other jar
  to `build-sdk --release` now fails its tag build. A pak on the floating
  major gets this on its next build; a pinned pak bumps `BUILDKIT_TAG` to
  `sdk-buildkit-v1.0.28` and its committed SHA256SUMS.

## Behavior since 1.0.27

- The overview pages (`overview.packed`, light and dark) HTML-escape the
  adapter.yaml `name` (in `<title>` and `<h1>`) and `description` (in
  `<p>`), as 1.0.26 does for `vendor` and `vendor_contact` (factory issue
  #338). Until now they were written raw, so `&`, `<` or `>` broke the
  page and markup in a description rendered as markup. `"` and `'` become
  entities, and non-ASCII a numeric character reference. A multi-line
  description keeps its line breaks.
- With plain ASCII and none of `& < > " '`, the two pages are byte-identical
  to 1.0.26; the `overview.packed` zip around them differs on every build,
  as before. Otherwise the page bytes change and the text it shows does not.
- `manifest.txt` and `resources/resources.properties` are unchanged.
- `validate-sdk` and `build-sdk` now apply the `vendor` character rule to
  `name` and `description`: they reject a control character (NUL and the
  rest of C0, DEL, U+0080-U+009F), U+2028/U+2029, a bidi control or an
  unpaired surrogate. A description may still span lines: line feed, CRLF
  and tab are allowed, a lone CR is not. A name must be one line; it is
  stripped of leading and trailing whitespace, and a blank name is rejected.
  Before, a C1 control showed as a different character on the page and a
  lone surrogate passed validation, then failed the build.
- Write `name` and `description` as plain text: `&amp;` now shows
  literally as `&amp;`.
- The Broadcom SDK jars are named for the platform version and build their
  bytes come from: `vrops-adapters-sdk-9.0.2.0.25137845.jar` (formerly
  `vrops-adapters-sdk-2.2.jar`), `vrops-adapters-sdk-8.18.7.25423534.jar`
  (formerly `-8.18.7.jar`) and `vrops-adapters-sdk-9.1.1.0100.25795063.jar`
  (formerly `-9.1.1.0100.jar`). Same bytes, same sha256. `2.2` was never a
  platform version. The former names still work wherever the kit looks a
  jar up by name, with one INFO line; a jar passed with `--sdk-jar`,
  `VCFCF_SDK_JAR` or `--sdk-compat-jar` may have any name and is identified
  by its sha256.
- The 9.0 line accepts a second jar: VCF Operations 9.0.2.0200 build
  25431135, the jar on a patched 9.0.2 appliance (sha256
  `a8e9ebbdc8c622fb89551d51870220e784f0097ed0800a6f490dfdc74a11119b`). Its
  480 classes are identical to 9.0.2.0's; only Maven metadata differs. It
  satisfies the 9.0 leg, so copying the jar from a current 9.0.2 appliance
  no longer fails a `--require-sdk-compat` run with "sha256 matches no
  known line".
- `conf/version.txt` `Adapter-Version-Ref` records the SDK jar the pak was
  compiled against as `<version>.<build>`, from its sha256
  (`9.0.2.0.25137845` or `9.0.2.0200.25431135`), whatever the file is
  called. It read `2.2` in factory builds and `N/A` in kit builds that pass
  `--sdk-jar`. An unknown jar gets the version from a
  `vrops-adapters-sdk-<version>.<build>.jar` name, else `unknown`. Every
  rebuilt pak's `conf/version.txt` changes; nothing else in the pak does.
- A javac older than the SDK jar's class files stops the build with a
  message naming the jar, its platform line, the Java it needs and the Java
  found, instead of "Framework compilation failed". The 9.0.2 jar needs JDK
  17 or newer; JDK 11 is not enough.
- When `VCFCF_SDK_JAR` is another line's jar, or a jar matching no known
  hash, the 9.0 leg's SKIPPED notice says so instead of telling you to set
  `VCFCF_SDK_JAR`.
- The instructions for obtaining the jar give the real appliance path,
  `/usr/lib/vmware-vcops/common/lib/vrops-adapters-sdk.jar`. The
  `/usr/lib/vmware-vcops/common-lib/` and `/usr/lib/vmware-vcops/suite-api/`
  paths named before exist on no appliance, and "any 9.x instance" was
  wrong: the jar differs per platform version. See Consumer contract below.
- Adoption: no change is required, and former jar names keep working. A
  pak repo that fetches the jar from a pinned commit of a jar repository
  must change the jar file name it asks for in the same commit that moves
  the pin to one holding the new names. No adapter.yaml change is needed
  for a name and description that already validate. A pak on the floating major gets this on its next build; a
  pinned pak bumps `BUILDKIT_TAG` to `sdk-buildkit-v1.0.27` and its
  committed SHA256SUMS.

## Behavior since 1.0.26

- A pak can name its own vendor, contact and licence (factory issue #336).
  Until now every kit-built pak presented `VCF Content Factory` as its
  vendor and shipped the factory MIT `LICENSE` as its `eula.txt`. New
  optional adapter.yaml keys:
  - `vendor`: stamped into both `manifest.txt` copies, the solution
    `resources/resources.properties` `VENDOR=` and both overview pages.
  - `vendor_contact`: a free-text line (email or URL) shown under the
    vendor on the overview pages only.
  - `eula_file`: a path, relative to the adapter project, to the text
    shipped as `eula.txt` in the outer pak and inside `adapters.zip`. It
    is read once at validation and shipped as read, minus a leading BOM.
- With none of the keys, a pak is byte-identical to one built with 1.0.25.
- With `eula_file` set, the factory MIT `LICENSE` also ships as
  `<adapter_kind>/lib/vcfcf-adapter-base-LICENSE.txt`, the notice for the
  bundled jar. The buildkit and `vcfcf-adapter-base.jar` stay MIT whatever
  licence the pak itself carries; the jar and its manifest are unchanged.
- `validate-sdk` and `build-sdk` reject a present but blank `vendor` or
  `vendor_contact`, a non-string, or one holding a control character,
  U+2028/U+2029, a bidi control or an unpaired surrogate. A YAML
  `"\ud83d\ude80"` escape is not paired, so write emoji raw. They reject an
  `eula_file` that is missing, not a regular file, outside the project, not
  UTF-8, contains NUL, or is empty or has no printable text.
- `build-sdk` prints the vendor and EULA source it stamped; on the default
  vendor it says how to set one. These lines are informational, not
  warnings.
- Kit assembly now fails if the factory `LICENSE` is missing, instead of
  writing a placeholder.
- Adoption: a pak repo bumps `BUILDKIT_TAG` to `sdk-buildkit-v1.0.26` and
  its committed SHA256SUMS, then adds the keys it wants. Paks that set none
  need no change.

## Behavior since 1.0.25

- Every Tier 2 pak build ships `<adapter_kind>/conf/logging.properties`
  with `<entry_class package>=INFO` (factory issue #313). The per-instance
  adapter log takes the level of the log4j entry covering a logger's name
  at first lookup, so without this file helper-class INFO lines were
  dropped unless a Test Connection had raised the name first.
- Optional adapter.yaml `logging:` stanza (`generate`, `level`, `loggers`).
  A `conf/logging.properties` in the adapter source ships unchanged and
  wins; `validate-sdk` warns on non-ASCII bytes or unknown level names in
  it. Extra `loggers:` names the collector's own log4j config already
  covers (`com.integrien.*`) are skipped by the SDK.
- **Test Connection INFO no longer reaches `collector.log`** once the pak
  is rebuilt (there is no instance log during Test Connection; WARN and
  ERROR still reach `collector.log`). Put Test Connection diagnostics that
  must be visible in the result message or log them at WARN; compliance's
  `logInfo("Test OK ...")` is one that now vanishes.
- `logging.level: DEBUG` is not absolute: a Test Connection still raises
  the names it looks up (the adapter class and its Test Connection
  helpers) to INFO for instances created afterwards, and copies their
  lines into `collector.log`, until the next log4j reload or collector
  restart. Adapter-base follow-up: factory #322.
- SDK 2.2 (9.0) and 9.1.1 only: the 8.18.7 SDK never reads the file, so
  it is inert on 8.18.
- Also carries the optional adapter.yaml `stitch_targets` stanza (factory
  #321, docs only), which shipped in the factory without a kit bump.
- Adoption: no adapter source change. Each pak repo bumps `BUILDKIT_TAG`
  to `sdk-buildkit-v1.0.25` and its committed SHA256SUMS, then rebuilds.

## Behavior since 1.0.24

- Batch Suite API pushes (compliance#17). `SuiteApiStitcher` (and
  `SuiteApiStitchClient`) gain `pushPropertiesBatch`, `pushStatsBatch` and
  `pushBatch`, which push onto many foreign resources through
  `POST /api/resources/properties` and `POST /api/resources/stats`: two
  calls per batch instead of two per object. Evidence: wire shape from spec + vendor examples; both batches proven landing live on 8.18.7, 9.0.2 and 9.1.1 (properties with a changed value).
  **Opt-in: a pak that keeps calling `pushProperties` / `pushStats` per
  object builds and behaves exactly as before.**
- `pushBatch(properties, stats, timestamp)` sends properties, then stats.
  Requests are capped at 100 resources and about 1 MB of JSON, whichever
  comes first (both overridable per call); one resource bigger than the
  byte cap goes alone. Resources are serialized and sent one request at a
  time, so memory stays near one request's JSON. Ids must be UUIDs; others
  are skipped with a WARN.
- Never throws. The token is fetched before each request; if it cannot be,
  the call stops before sending anything more. A 401 is retried once with a
  new token, as before. A batch refused with a 4xx other than 401 and 429
  (a bad entry) logs one WARN (the count and the first ids) and re-sends
  that batch's resources one by one to isolate it. A 5xx, a 429, a 401
  that survives the retry, or a timeout logs one WARN and stops the call:
  no re-send, no further batches, and `pushBatch` skips its stats half. A
  struggling or hung server gets one request, not one per object.
- Each call returns a `SuiteApiBatchResult` for the pak to count: sent,
  batchesOk, batchesFailed, fellBack, skipped (every resource no request
  delivered), dropped (null keys, null values, NaN or infinite stats) and
  stopped. `isClean()` is false if anything was skipped, dropped or failed.
- Every control character in a key or value is now escaped, in batch and
  per-id bodies alike; before, one such character made the body invalid
  JSON.
- **A 2xx does not mean every id landed.** The Suite API drops an id that
  matches no resource without an error and stores the rest. A stale id
  never shows in the result: catch it where ids are resolved (the pak's
  `ForeignResourceResolver` refresh).

## Behavior since 1.0.23

- Dynamic-threshold symptoms bundled in a pak now import. The kit wrote a
  `metric_dynamic` condition in the REST spelling (`type="metric"
  operator="DT_ABOVE"`) inside `content/symptomdefs` and
  `content/alertdefs`; VCF Ops 8.18 and 9.1 reject that with
  `Invalid operator:dt_above` and silently drop the symptom and every alert
  that uses it. It now writes the content-import form the vendor schema and
  vendor paks use: `type="dtmetric" operator="above|below|abnormal"`.
  Rebuild any pak that bundles a dynamic-threshold symptom (Synology does);
  other paks build byte-identical.
- `validate-sdk` and `build-sdk` refuse a `metric_dynamic` condition on a
  `Super Metric|` key (that needs the super-metric DT type, which the kit does
  not emit).

## Behavior since 1.0.22

- Vanished objects can be marked not existing (unifi#20). **Opt-in: no pak
  changes behaviour on this kit until it opts in.** A pak with
  `discoverOnCollect()` on opts in by overriding `kindsReadThisCycle()` to
  return the kinds its `enumerateResources` read in full that cycle; the
  default `null` marks nothing. For those kinds, a resource the platform
  knows that the enumeration has not delivered for 12 consecutive complete
  cycles is marked with `changeResourceState(rc, NOTEXIST)`, as the vSphere,
  vSAN and NSX adapters do. VCF Ops then shows it as Not Existing and
  deletes it after the Deleted Objects retention setting.
- Only the pak can say a kind was read in full. That a kind was delivered
  is not enough: a read that failed for one parent (one UniFi site's device
  list, one Synology share's NFS probe) still delivers the same kind from
  the other parents. Leave a kind out of `kindsReadThisCycle()` whenever any
  part of its read failed.
- An empty answer is not a complete read. An empty list, an empty child
  table on a registered device, or an error code inside a 200 body must
  leave the kind out, unless the source says positively that none exist.
  Otherwise one empty response repeated for 12 cycles marks a live
  inventory gone. The cost is that a kind's last object is never
  auto-removed.
- The threshold counts collection cycles, not time: 12 cycles is an hour at
  a 5-minute interval and 12 minutes at a 1-minute one.
  `notExistingMissedCycles()` changes it (0 turns marking off).
- Nothing is counted or marked in a cycle whose enumeration threw or
  delivered nothing, that was stopped, or in which every object failed.
  The adapter instance and its kind are never marked, nor are kinds in
  `notExistingExcludedKinds()` (synthetic and aggregate kinds, and kinds
  registered outside `enumerateResources`). Kinds compare ignoring case.
- **On first opt-in, every orphan goes.** Every object the platform still
  holds under a key no current enumeration produces is counted from the
  first cycle. Examples are Synology objects from before build 34's
  DiskStation re-key and UniFi `<mac>_0` ports from before #23. All of them
  are marked about 12 cycles after the upgrade and then deleted by the
  retention window (7 days by default, 6 hours on some labs), with their
  history. That is the correct end state, but it cannot be undone: check
  what the platform holds for the pak before opting in.
- A marked object is no longer collected while it stays missing. If the
  enumeration delivers it again while the platform still lists it, it is
  sent `START`. The SDK's own cache usually drops a resource once the
  platform confirms NOTEXIST (`AdapterCache.processNotExistingResponse`),
  and then no `START` can be sent: the object can return only through
  normal discovery (`addNewResource`). Neither path is verified on a live
  instance yet.
- Logging: one INFO line per cycle each for objects marked, objects sent
  `START`, objects back but no longer listed by the platform, and marked
  objects the platform no longer lists (count and first object).
- The miss counts are in memory: a collector restart delays a mark, never
  makes one early.
- On a Cloud Proxy, the ambient Suite API credential no longer tries the
  automation and maintenance credential files (compliance#58). Those files
  never authenticate from a proxy, and decrypting them made the platform's
  `Crypt` log an ERROR ("Crypt.decrypt_impl_v2: ... pad block corrupted")
  on every Test Connection. When the collector-injected credential is
  missing on a proxy, the framework now raises one clear error without
  calling `Crypt`, so the pak logs a single WARN with no stack. The proxy is
  detected from the collector's own `collector.properties`
  (`isUnifiedCloudProxy`, or `httpRelayEnabled=true` where that key is
  absent, as on 8.18). An analytics
  node, or a collector whose file cannot be read, keeps the old behaviour.
  Collection on a proxy still uses the injected credential, as before.
- When the platform `Crypt` cannot decrypt a credential file, it returns
  nothing instead of throwing. The framework now stops there with an error
  naming the file. Before, it went on to log in with no password, which
  failed with a 401.

Version note: 1.0.21 (#281) is the first kit with `SHA256SUMS`; this is 1.0.22.
Publish 1.0.21 before 1.0.22 so `sdk-buildkit-v1` never moves backwards.

## Behavior since 1.0.19

- A child object whose collect fails now shows `NO_DATA_RECEIVING` (#245).
  The SDK accepts only `NONE`, `DATA_RECEIVING` and `NO_DATA_RECEIVING` on a
  child object, the same on 8.18.7, 9.0 and 9.1.1; `ERROR` and `DOWN` only on
  the adapter instance. Before this kit, the `ERROR` or `DOWN` that
  `mapCollectException` returns (or the `ERROR` default) was refused by the
  SDK on the child, and the object kept its last status. The framework now
  moves any status a child cannot take to `NO_DATA_RECEIVING`. `ERROR` and
  `DOWN` still count as failures, so a cycle where every object fails still
  sets the account row to `ERROR` (or `DOWN`), as since 1.0.14.
- Logging: the expected `ERROR`/`DOWN` move is one INFO line per cycle
  (count and first object). A `mapCollectException` status the SDK refuses
  everywhere (for example `UNKNOWN`) is one WARN per status per adapter
  instance. A status the SDK does not take (`setResourceStatus` returns
  `false`) is logged at WARN every time, for objects and for the adapter
  instance, instead of being ignored.
- A failed collect logs its stack trace at WARN once per failure streak.
  While the same object keeps failing, each cycle logs one WARN line with
  the message and the streak length, and the stack trace at DEBUG. A
  success, or the object leaving the collected set, ends the streak.
- No pak source change. Rebuild every pak on this kit to pick it up.

Version note: this is 1.0.19, after 1.0.18.

## Behavior since 1.0.18

- The pak is compiled with `javac --release 11` instead of `-source 11
  -target 11`: Java 11 bytecode and the Java 11 class library, the Java the
  8.18 collector runs. A Java 12+ library call now fails the build. The
  framework had one (`ManagedHttpClient`'s DNS round-robin retry, a Java 16
  call); it is fixed in this kit, so rebuild every pak.
- The compile matrix covers every supported line, one leg each, nothing
  kept: 8.18.7 (`vrops-adapters-sdk-8.18.7.jar`, `--release 11`), 9.0 (the
  2.2 jar you already supply, `--release 17`) and 9.1.1.0100
  (`vrops-adapters-sdk-9.1.1.0100.jar`, `--release 25`). Each leg compiles
  at its line's collector Java, read from the jar's class files, on a JDK
  at least that new (JDK 17 for the first two, JDK 25 for 9.1.1.0100), and
  fails on a class or member the line's jar lacks or a Java API its
  collector's Java lacks. A Java-library miss is reported as such, not
  against the jar.
- `--sdk-compat-jar` repeats; `VCFCF_SDK_COMPAT_JARS` (colon-separated) is
  its env form, and the one-jar `VCFCF_SDK_COMPAT_JAR` still works. They
  add up.
- A supplied jar is matched to its line by sha256. Every line is expected:
  a line no jar covers prints the SKIPPED box, and with
  `--require-sdk-compat` it fails the build. `VCFCF_SDK_COMPAT_LEGS=<comma
  list of 8.18.7, 9.0, 9.1.1.0100>` narrows the lines a run must cover. A
  required pak build that supplies only the 9.1.1 jar now fails naming
  8.18.7 instead of passing.
- The 1.0.16 `[removal]` gate on the framework's own pass now runs on
  every leg; the framework-plus-adapter pass still only prints them.

Version note: 1.0.16 is the installer/shims round and 1.0.17 the
adapter-framework designs round; this is 1.0.18.

## Behavior since 1.0.17

- Opt-in certificate name checking for pak HTTP connections (#185, #206):
  `VcfCfAdapter.getPlatformSslContext(host)` and
  `HttpClientBuilder.platformSsl(adapter, host)` run the platform chain check
  and then require the certificate to name the dialled host. The no-argument
  forms are unchanged; the Suite API loopback never name-checks.
- Validate Connection certificate text (#205): a protected
  `certificateFailureMessage` hook, neutral default text pointing at the
  accept dialog, name-mismatch text naming the host, and the Allow Insecure
  SSL wording only when the describe declares that field.
- `onCycleStart()` on the adapter base (#221), called once per cycle before
  discovery; `needsRediscovery` is still called exactly once per cycle.
- `HttpClientBuilder.connectTimeout(Duration)` (#222), defaulting to the
  existing timeout, which stays the read budget.
- 1.0.16 is the installer and ThreadDeath round (factory #242); this kit
  carries both.

## Behavior since 1.0.16

- The adapter framework no longer references `java.lang.ThreadDeath`
  (deprecated for removal on Java 25 collectors, factory #242): the
  catch is `VirtualMachineError` plus a name-matched thread-kill check,
  with the same Java 17 behaviour, and the thread's interrupt status is
  restored when a certificate hook is interrupted. A pak rebuild on this
  kit picks it up with no source change.
- The framework compatibility pass (`check_framework_sdk_compat`) fails
  on any `[removal]` warning; the framework-plus-adapter pass in
  `build-sdk` and `validate-sdk` still only prints them.

## Behavior since 1.0.15

- `build-sdk` and `validate-sdk` take `--sdk-compat-jar <path to
  vrops-adapters-sdk-9.1.1.0100.jar>` (or `VCFCF_SDK_COMPAT_JAR`) to compile
  the framework and adapter a second time against the VCF Ops 9.1.1.0100 SDK
  jar on JDK 25+, and `--require-sdk-compat` (or
  `VCFCF_SDK_COMPAT_REQUIRED=1`) to fail instead of warn when that check
  cannot run; the pak itself is still compiled against the 2.2 jar.
- The default is a skip: with no 9.1.1.0100 jar, or no JDK 25+ (looked for
  on PATH, `JAVA_HOME`, `JAVA_HOME_<N>_X64`, or set
  `VCFCF_SDK_COMPAT_JAVAC=/path/to/javac`), a plain `build-sdk` prints a
  warning box and checks nothing against 9.1.1. A `--release` build under
  GitHub Actions also emits a `::warning::` annotation.
- The primary compile takes exactly one SDK jar: a second
  `vrops-adapters-sdk*.jar` beside it in `adapter_runtime/` now stops the
  build.

Version note: 1.0.13 is the defect-gate round (PR #246) and 1.0.14 the
adapter-framework round (PR #248); this is 1.0.15.

## Behavior since 1.0.11

- `pak-compare` gates against the closest reference pak: it exits 1 when
  that reference reports any BLOCKING finding, or when the comparison
  cannot run.
- `build-sdk` applies the same rule and fails the build on a BLOCKING
  finding by default. `--pak-compare-warn-only` restores the old
  warn-and-continue behavior for local experiments and is refused
  together with `--release`; `--release` builds also fail when no
  reference pak is available.
- javac runs with `-proc:none`: annotation processors in classpath jars
  never run.

A workflow that ran the old kit and relied on grepping the compare output
for "0 BLOCKING" now also fails on the exit code; under `set -o pipefail`
that is the intended gate.

## Consumer contract

The kit ships no Broadcom jars. It compiles its framework source and your
adapter against a Broadcom SDK jar that **you must supply**. That jar is a
Broadcom build artifact with no public redistribution channel and must not
ship in a public toolchain tarball (see redistribution survey 2026-06-09).

**Which jar.** The SDK jar is different on every platform version. What
ships is compiled against the VCF Operations 9.0.2 jar, either build below.
The other two lines' jars are optional compatibility checks. The kit
identifies a jar by its sha256, so the file name does not matter; these are
the names the kit itself uses, `vrops-adapters-sdk-<version>.<build>.jar`.

| Platform, build | File name in the kit | sha256 | Class files | JDK to read it | Role |
|---|---|---|---|---|---|
| VCF Operations 9.0.2.0, 25137845 | `vrops-adapters-sdk-9.0.2.0.25137845.jar` | `2d53a91fc2b9a99d9b685ed10c1e37a471c2f71f04e7ae0fb2c53fdaa14b4f54` | Java 17 | 17+ | **Required.** Compile target, and the 9.0 compatibility leg |
| VCF Operations 9.0.2.0200, 25431135 | `vrops-adapters-sdk-9.0.2.0200.25431135.jar` | `a8e9ebbdc8c622fb89551d51870220e784f0097ed0800a6f490dfdc74a11119b` | Java 17 | 17+ | Accepted in place of the 9.0.2.0 jar |
| Aria Operations 8.18.7, 25423534 | `vrops-adapters-sdk-8.18.7.25423534.jar` | `45d54c6403acf535c982a85d658b422f534c36c90ceab78a224dde67b2a640ea` | Java 11 | 11+ | Optional compatibility leg |
| VCF Operations 9.1.1.0100, 25795063 | `vrops-adapters-sdk-9.1.1.0100.25795063.jar` | `79f7b12340906359e04f3619dd87c7e67a9493b3fa5d86bdffe9242da67f46f7` | Java 25 | 25+ | Optional compatibility leg |

Everything that ships is compiled with `javac --release 11`, because the
8.18 collector runs Java 11, but the javac must be new enough to read the
jar's class files: JDK 17 or newer for a 9.0.2 jar. A javac that is too old
stops the build and says so.

Former names, still accepted: `vrops-adapters-sdk-2.2.jar` (the 9.0.2.0
jar), `vrops-adapters-sdk-8.18.7.jar`, `vrops-adapters-sdk-9.1.1.0100.jar`.

**Which builds accept which jars.** Release builds (`--release`,
`--require-sdk-compat`, `VCFCF_SDK_COMPAT_REQUIRED=1`): `--sdk-jar` must be
a 9.0 row, every `--sdk-compat-jar` any row, no override. Hand builds: any
jar, with a boxed warning for one that is not.

**Where it is on an appliance.** On every line the collector's jar is

    /usr/lib/vmware-vcops/common/lib/vrops-adapters-sdk.jar

with no version in the file name. It is world-readable. Copy it from an
appliance of the right version, to somewhere outside any repository's
working tree, and take its hash:

    scp root@<appliance>:/usr/lib/vmware-vcops/common/lib/vrops-adapters-sdk.jar .
    sha256sum vrops-adapters-sdk.jar

Find the hash in the table above and rename the copy to the file name on
that row. Do not name it before checking: a patched appliance of the same
version carries a different build of the jar. A jar from an appliance at a
build not in the table has a hash the kit does not know. A hand build
still compiles against it, with a warning; a release build (`--release` or
`--require-sdk-compat`) refuses it. A jar outside the table is a new kit
release, not a flag. Name it `vrops-adapters-sdk-<version>.<build>.jar`
from the appliance's own version and build. Partners with access can pull the jar from the Broadcom TAP / partner
SDK portal instead.

**Providing it to the build.**

    python3 -m sdk_buildkit build-sdk <adapter_dir> --sdk-jar /path/to/vrops-adapters-sdk-9.0.2.0.25137845.jar

or set `VCFCF_SDK_JAR` to the same path. `conf/version.txt`
`Adapter-Version-Ref` in the built pak records which jar it was compiled
against.

**The optional compatibility jars.** Pass the 8.18.7 and 9.1.1.0100 jars
to also compile the framework and adapter main source once per line, at
that line's collector Java, keeping nothing:

    python3 -m sdk_buildkit build-sdk <adapter_dir> \
        --sdk-jar /path/to/vrops-adapters-sdk-9.0.2.0.25137845.jar \
        --sdk-compat-jar /path/to/vrops-adapters-sdk-8.18.7.25423534.jar \
        --sdk-compat-jar /path/to/vrops-adapters-sdk-9.1.1.0100.25795063.jar \
        --require-sdk-compat

`VCFCF_SDK_COMPAT_JARS` (colon-separated) and the older one-jar
`VCFCF_SDK_COMPAT_JAR` do the same. Each leg needs a JDK at least as new as
its jar's class files (JDK 25+ for 9.1.1.0100), found on PATH, `JAVA_HOME`,
`JAVA_HOME_<N>_X64` or `VCFCF_SDK_COMPAT_JAVAC`. A line with no matching
jar or no new enough JDK is skipped with a warning; `--require-sdk-compat`
(`VCFCF_SDK_COMPAT_REQUIRED=1`) makes that a failure, and
`VCFCF_SDK_COMPAT_LEGS` (comma list of `8.18.7`, `9.0`, `9.1.1.0100`)
narrows the lines a run must cover.

**CI usage (adapter repo's build workflow).** This shows the floating
major for brevity. A release workflow should pin an exact version and
verify the tarball against a committed hash; see Version pinning below.

```yaml
- name: Download sdk-buildkit
  env:
    GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
  run: |
    gh release download @FLOATING_TAG@ \
      --repo sentania-labs/vcf-content-factory \
      --pattern 'sdk-buildkit-*.tgz*'
    sha256sum -c sdk-buildkit-*.tgz.sha256   # verify before use
    tar xzf sdk-buildkit-*.tgz

- name: Build adapter pak
  env:
    VCFCF_SDK_JAR: ${{ secrets.VCFCF_SDK_JAR_PATH }}   # path to the 9.0.2 SDK jar
  run: python3 -m sdk_buildkit build-sdk .
```

## Version pinning
- **Exact pin**: `@REF_NAME@`
- **Floating major**: `@FLOATING_TAG@`
  (always points at the latest backwards-compatible release of this major)

To pin, download this release's `SHA256SUMS` once, commit it to the pak
repo (for example `ci/sdk-buildkit.SHA256SUMS`), and verify every download
against the committed copy, never one fetched alongside the tarball:

```yaml
- name: Download and verify the pinned buildkit
  env:
    GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
  run: |
    gh release download @REF_NAME@ \
      --repo sentania-labs/vcf-content-factory \
      --pattern 'sdk-buildkit-@VERSION@.tgz'
    sha256sum -c ci/sdk-buildkit.SHA256SUMS
    tar xzf sdk-buildkit-@VERSION@.tgz
```

## Checksum

Each release carries `sdk-buildkit-<version>.tgz.sha256` (sha256sum
format) next to the tarball. Versioned releases since 1.0.21 also carry
`SHA256SUMS` (same format), the file an exact pin commits. Download the
tarball and its `.sha256` sidecar and run `sha256sum -c` before
extracting. A pattern of `sdk-buildkit-*.tgz` alone does not fetch the
checksum file.

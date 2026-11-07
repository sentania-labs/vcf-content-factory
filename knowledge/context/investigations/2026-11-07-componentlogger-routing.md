# componentLogger routing on the Cloud Proxy (factory #313), 2026-11-07

**Question.** Why did vsanperf build 8's `componentLogger(CycleEngine.class)` lines never
reach `VsanPerfAdapter_<id>.log` on the devel 9.0.2 Cloud Proxy, while compliance's
`componentLogger(VSphereClient.class)` lines do reach `ComplianceAdapter_<id>.log`? Is
compliance affected, and what should adapter-base change?

**Answer.** The thread, the logger class and the wrapper were all ruled out. What decides it
is whether a LoggerConfig for the **bare** logger name existed at INFO when the instance
logger was created. Nothing ships one: our paks have no `conf/logging.properties`. The only
thing that creates one is a side effect of Test Connection. On that path the SDK factory has
no instance appender, so `componentLogger` / `adapterLogger()` hand back a plain bare-name
logger, and `raiseToInfo` runs `Configurator.setLevel(<bare name>, INFO)`, which **adds** a
bare-name LoggerConfig at INFO to the live log4j configuration. Any instance logger created
later for that name, or for a dotted child of it, gets its instance-file appender at INFO.
Names never looked up during a Test Connection fall through to the collector root (WARN),
and their INFO is dropped.

- vsanperf: `VsanPerfAdapter` and `VsanJsonClient` were looked up in Test Connection.
  `CycleEngine` never was, so the cycle summary and the PERF lines were lost.
- Compliance: `ComplianceAdapter`, `VSphereClient` and `SuiteApiStitcher` were looked up in
  Test Connection. `ComplianceStitcher` never was, so **compliance is affected**: its INFO
  lines are missing every cycle.

Sources: SDK bytecode (`vrops-adapters-sdk-2.2.jar`, javap), the proxy's log4j config, and
log counts on `vcf-lab-operations-devel-collector`. All read-only.

## 1. Routing rule (SDK 2.2 bytecode, `AdapterLoggerFactoryImpl`)

- `getLogger(Class)` is just `getLogger(cls.getName())`. The two overloads behave the same.
- `getLogger(String name)` behaves differently depending on whether the factory has an
  instance appender:
  - **No instance appender** (Test Connection, describe path): returns
    `new Logger(LogManager.getLogger(name))`, the bare name, which logs to `collector.log`.
  - **Instance appender present**: the logger name is `"(" + instanceId + ") " + name`
    (concat recipe `(\u0001) \u0001`). If no LoggerConfig of exactly that name exists, it
    calls `createLoggerConfig(name, config)`:
    - `gov = config.getLoggerConfig(name)`. This is the most specific existing config for
      the *bare* name.
    - `appLevel = gov instanceof AdapterLoggerConfig ? gov.getLevelForAdapterLog() : gov.getLevel()`.
    - A new `LoggerConfig("(id) name", moreVerboseOf(appLevel, gov.getLevel()), additive=false)`.
    - The instance file appender is added **at `appLevel`**.
    - `copyAppenders(gov, new, gov.getLevel())` adds every appender found walking `gov` and
      its parents (root's `fileAppender` = `collector.log`), at `gov.getLevel()`.
- `AdapterLoggerConfig` entries come from
  `<ADAPTER_HOME>/<adapter jar base name>/conf/logging.properties` (concat recipe
  `\u0001\u0001\u0001\u0001conf\u0001logging.properties`). Keys other than
  `MaxFileSize`/`MaxBackupIndex` become `AdapterLoggerConfig(key, levelForAdapterLog=<value>,
  level=<governing level>, additive)`. This happens only when the key is currently governed
  by root. `onAfterReload` reloads these entries and re-creates every instance config, so a
  pak-shipped entry survives a log4j reload.
- The SDK `Logger.setLevel(CustomLevel)` is `Configurator.setLevel(logger.getName(), level)`.
  Log4j adds a new LoggerConfig when none has exactly that name. That makes it the writer of
  the bare-name entries:
  - On an instance logger, `"(id) X"` already exists. Only its level changes, never the
    appender filter, as the #228 note says.
  - On a bare Test Connection logger, it **creates** `X` at INFO, additive, with no
    appenders of its own.

The collector's static config has nothing for `com.vcfcf.*`
(`/usr/lib/vmware-vcops/user/conf/collector/log4j2.properties`, 161 lines, verbatim):

```
rootLogger.level = WARN
rootLogger.appenderRef.fileAppender.ref = fileAppender
...
logger.comintegrienalivecommonadapter3.name = com.integrien.alive.common.adapter3
logger.comintegrienalivecommonadapter3.level = ERROR
...
appender.fileAppender.fileName = ${env:ALIVE_BASE}/user/log/collector.log
```

`logging.properties` files on the proxy: only vendor paks (ServiceDiscoveryAdapter3,
AppOSUCPAdapter3, LogAssistAdapter, NSXTAdapter3, DiagnosticsAdapter3), for example
`com.vmware.adapter3.nsxt=INFO` and `com.vmware.adapter3.logassist = INFO`. There is none
under `vcfcf_compliance/` or `vcfcf_vsanperf/`.

**Rule.** A line reaches `<Adapter>_<id>.log` at INFO only if one of these holds when that
instance first looks up the name:

1. the pak's `conf/logging.properties` covers the name at INFO, or
2. a bare-name LoggerConfig at INFO exists for the name or a dotted parent, which in
   practice comes from a Test Connection in this collector JVM.

Otherwise the appender sits at root WARN: WARN and above pass, INFO is dropped. Where the
instance is in the thread context only affects the `instanceId=` field in the pattern, not
routing.

## 2. Counts on the proxy (devel 9.0.2 collector, 2026-11-07 ~06:20Z)

Instance logs roll at about 1 MB and keep one file, so the compliance logs cover
00:19Z-06:19Z only. Counts are by logger name after `(id)`.

| Log | Logger names (count) |
|---|---|
| `ComplianceAdapter_5379.log` | `...compliance.ComplianceAdapter` 2560, `...compliance.VSphereClient` 657, `...ComplianceAdapter.SuiteApiStitcher` 2, `...ComplianceStitcher` **0** |
| `ComplianceAdapter_5381.log` | 2669 / 648 / 2 / **0** |
| `ComplianceAdapter_5382.log` | 2525 / 648 / 2 / **0** |
| `VsanPerfAdapter_7083.log` (build 9, 03:29Z-06:18Z) | `...vsanperf.VsanPerfAdapter` 55, `...VsanPerfAdapter.SuiteApiStitcher` 16 |
| `VsanPerfAdapter_7084.log` | `VsanPerfAdapter` 7, `VsanPerfAdapter.SuiteApiStitcher` 2 |
| `VsanPerfAdapter_7086.log` | `VsanPerfAdapter` 2 |

- No vsanperf instance log has `CycleEngine` or `VsanJsonClient` as a logger name. Their
  only appearances are stack frames, 3 and 15 in `collector.log`, 2+10 and 1+5 in 7084 and
  7086.
- `ComplianceStitcher` appears 0 times in every adapter log and in all 16 `collector.log*`
  files.
- The `ComplianceStitcher` load does run every cycle. Each instance has 74
  `Stitcher loaded: N hosts` lines (adapter `logInfo`) and 74 `collection complete` lines.
  Each load calls `loadResourcesForKind`, which logs INFO
  `ComplianceStitcher: <kind> — processing N resource(s)` (`ComplianceStitcher.java:379`).
  So about 5 INFO lines per cycle are silently dropped.

Bare-name lines (no `(id)`) in `collector.log` are the Test Connection lookups. They line up
with the start of each instance log:

| Bare-name Test Connection lines | Instance log first line |
|---|---|
| `[com.vcfcf.adapters.compliance.ComplianceAdapter.logInfo]` at 00:18:56Z, 00:19:12Z, 00:19:40Z | compliance instance logs begin 00:19:00Z, 00:19:14Z, 00:19:43Z |
| `[com.vcfcf.adapters.vsanperf.VsanPerfAdapter.logInfo] - Test OK` at 03:29:09.676Z | 7083 begins 03:29:14.170Z |

Before 2026-11-07T00:18:56Z, `collector.log.1` and older carry no compliance line at all.

`(id)`-named vcfcf lines are **also duplicated into `collector.log`**: 7169 compliance
adapter-class lines and 1809 `VSphereClient` lines in the current file. That is the
`copyAppenders` path. The governing config is the Test-Connection-created bare INFO entry,
which is additive to root, so root's `fileAppender` is copied in at INFO. A pak-shipped
`logging.properties` entry would avoid this: its `level` stays at the governing WARN and
only `levelForAdapterLog` is INFO.

## 3. Compliance: logger acquisitions and one line each

All of them go through `componentLogger`. None use `Logger.getLogger` or `LoggerFactory`.

| Class (lookup site) | Looked up in Test Connection? | Representative line | In instance log? |
|---|---|---|---|
| `VSphereClient` (`ComplianceAdapter.java:191`, 376) | yes, `testSoapLogin` | `vSphere SOAP: N hosts` | yes |
| `SuiteApiStitcher` → `ComplianceAdapter.SuiteApiStitcher` (213, 424) | yes, `testSuiteApi`; a child of the adapter class anyway | `SuiteApiStitchClient: credential mechanism=...` | yes |
| `ComplianceStitcher` (215) | **no** | `ComplianceStitcher: <kind> — processing N resource(s)` | **no** (WARNs would pass) |
| `ComplianceAdapter` (3492, `logDebug`) | adapter logger raised in test | DEBUG only | n/a |

## 4. vsanperf build 8 vs compliance (source)

- The wrapper is the same as compliance's. Build 8's `VsanPerfAdapter.log(Logger)`
  (`66396ba`) is a plain delegate (`info→l.info`, `warn→l.warn`, `error→l.error`), exactly
  like compliance's `clientLog`.
- The handle the wrapper keeps is the one `componentLogger` already passed through
  `raiseToInfo`. Even if it hadn't been raised, the logger level is not the gate; the
  appender filter is.
- Threads: `CycleEngine.run` writes the summary from the caller thread, in the `finally` at
  `CycleEngine.java:425`, so it fires on failed cycles too. Its workers
  (`vsanperf-c<cycle>-w<n>`, line 979) log through the same handle. Threads don't change
  routing; both are lost.
- The decisive difference is Test Connection.
  - The build 8 tester calls `buildClient`, which uses
    `componentLogger(VsanJsonClient.class)` and `testSuiteApi()`, and the base raises the
    adapter class logger.
  - `CycleEngine` is created only in `configureAdapter`, so no bare
    `com.vcfcf.adapters.vsanperf.CycleEngine` entry ever existed and its instance appender
    sat at WARN.
  - The failing instance 7086 logged its adapter-class WARNs but not the summary INFO.
- Build 9 (`745f36a`) sends everything through `logInfo`/`logWarn`. That works only because
  the adapter class's bare entry exists after a Test Connection.
- Correction to `2026-11-06-vsanperf-proxy-logs.md` §2: "Cycle summary INFO line: None
  exists" was wrong. The summary has existed since build 7 at `CycleEngine.java:425`; it was
  filtered.

## 5. Predicted, not tested (each needs a mutation; ask Scott first)

- After a collector restart, or a log4j reconfigure that drops the runtime-added entries,
  with no Test Connection since, **every** INFO line of our paks is filtered, the adapter
  class's own included, until someone runs Test Connection and the instance is
  reconfigured. This probably also explains the "hot-reload gap" and the build-45
  "intermittent INFO disappearance" notes in `tier2_architecture.md` and the
  `VcfCfAdapter` javadoc.
- Test: restart the collector on the devel proxy and check that compliance instance logs
  carry only WARN until a Test Connection.

## 6. Recommended framework fix

1. **Primary: ship `conf/logging.properties` in every Tier 2 pak.** This is the vendor
   mechanism.
   - `build-sdk` should emit `<adapter package> = INFO` from `entry_class`, for example
     `com.vcfcf.adapters.compliance = INFO`. Optionally add `MaxBackupIndex`, since today
     only one roll is kept.
   - That gives every in-package logger, and the `<AdapterClass>.<Simple>` framework
     children, an `AdapterLoggerConfig` with `levelForAdapterLog=INFO`.
   - It does not depend on a Test Connection, it survives `onAfterReload`, and it stops the
     duplicate INFO copy into `collector.log`.
   - Operators can still turn it down by editing the file or with the platform level
     setting.
2. **Belt and braces in adapter-base.** In `componentLogger` and `adapterLogger()`, before
   asking the instance factory, make sure the bare name is INFO-enabled. Do it the same way
   Test Connection does by accident: if `!LogManager.getLogger(name).isInfoEnabled()`, call
   `Configurator.setLevel(name, INFO)`. Never lower an existing DEBUG (#224).
   - This only helps loggers created after it runs, and it is lost on a log4j reload, so it
     is secondary to item 1.
   - log4j-api/core are on the collector classpath, but adapter-base's compile classpath
     needs checking (tooling).
3. **Not recommended as the fix:** routing `componentLogger` through the adapter's own
   logger (the vsanperf build 9 workaround). It loses per-class names and still depends on
   the adapter class's bare entry existing, which is the same side effect.
4. **Text to correct:**
   - `tier2_architecture.md` §Logging: "Where the Cloud Proxy's package-scoped entry comes
     from ... is not established; the platform's per-adapter log-level setting is the likely
     writer" → it is the Test-Connection `Configurator.setLevel` side effect, and a
     `componentLogger` name never looked up in Test Connection gets WARN.
   - The claim that an in-package class "keeps its name and reaches the instance log" holds
     only under that side effect.
   - The vcfops-sdk-adapter skill's logging text and the `VcfCfAdapter` javadoc (around
     lines 3060-3105 and 3140-3150) need the same correction.
   - Once item 1 lands, the compliance `ComplianceStitcher` INFO lines need no pak change.

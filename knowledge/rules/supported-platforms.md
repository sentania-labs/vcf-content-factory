---
id: RULE-019
---

# RULE-019: Every Tier 2 pak works on 8.18, 9.0 and 9.1, and the build proves it

The factory supports three VCF Operations platform lines at once: 8.18
(Aria Operations 8.18.x), 9.0 and 9.1 and later. A Tier 2 (Java SDK) pak
is not done until it builds and runs on all three. Tier 1 (MPB) paks
have no compile step; for them only the release section below applies.
Stated by Scott in issue #212 (2026-10-13) and made a rule on 2026-10-24
("all paks need to work across 8.18, 9.0, and 9.1 since they are all
supported", "make sure your build jar files result in that").

**What the build must do**

- Compile the framework and the adapter against every supported
  platform's adapter SDK jar: the 8.18 jar (Java 11 bytecode), the 2.2
  jar (9.0.2, Java 17) and the 9.1.1.0100 jar (Java 25). One jar is the
  primary compile target (today 2.2); the others are compatibility legs.
  A leg that runs and fails fails the build; `--require-sdk-compat` makes
  a leg that cannot run (jar or JDK missing) fail too, and CI sets it.
- Ship bytecode the oldest supported collector's Java can load. The
  8.18.7 collector and Cloud Proxy run OpenJDK 11
  (`knowledge/context/investigations/2026-10-24-devel-8-18-sdk-jar-and-proxy-log.md`),
  so adapters ship Java 11 bytecode compiled with `--release 11`, and
  that stays for as long as 8.18 is supported.
- Use no platform feature a supported line lacks without a documented
  fallback (8.18 examples: no Allow Unsigned PAK switch, dangling
  localizationKey fails view import, DEF-018; the SDK members only 2.2
  and later carry are listed in the investigation above).

**What a release must show**

- The pak installed and collecting on one instance of each line
  (devel_8_18, devel, devel_9_1) before a `v*` tag, recorded in its build
  record under `knowledge/context/reviews/`. A line that could not be
  exercised is named as not exercised, never implied.

**Transition.** The build tooling cannot run two compatibility legs yet
and the jars are not in CI until the private sdk-runtime PR 7 merges;
issue #252 tracks the build side. Until it lands, the release section
is what binds: a tag is cut only with the three-line install record, and
the build record names which compile legs ran.

**If violated:** a pak that compiles only against 9.x bytecode fails to
load on an 8.18 collector, or uses an API the older SDK lacks and fails
at collection time, after it has shipped. Neither surfaces at build.

Related: `knowledge/context/tier2_architecture.md` sections "SDK jar by
platform version" and "Second compile target"; issues #211, #212, #252.

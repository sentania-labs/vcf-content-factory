# SDK paks are independent repos; the official artifact is the CI build

**Context.** Tier 2 Java SDK adapters used to live inside the factory repo,
be built locally by the factory's own `vcfops_managementpacks` tooling, and
have no independent versioning or release channel. They were moved out into
per-pak repos (`sentania-labs/vcf-content-factory-sdk-<name>`, gitignored,
cloned via the `knowledge/context/managed_paks.md` registry) so each versions and
releases on its own cadence.

## The principle (heed it)

1. **The official `.pak` is the CI build, never a dev/agent build.** The SDK
   build is fully deterministic — `build-sdk` is a plain Python CLI over
   `javac` + `jar` + zip, no LLM, no network. That is exactly what lets a
   headless runner produce the release artifact with **zero agent in the
   path**. A local `build-sdk` (by `sdk-adapter-author` or a developer) is a
   **preview**. The release is a `v*` git tag on the pak's own repo, whose CI
   pulls the published `sdk-buildkit` tarball and builds the pak. Do not treat
   a dev-built `.pak` in `dist/` as shippable. (Byte-identical reproducibility
   between dev and CI is explicitly *not* a goal — dev≠CI, CI wins.)

2. **The build kit is cut only by `tooling`, only on a tag.** The
   `sdk-buildkit` tarball (slim builder + runtime JARs + reference pak) is the
   single toolchain both consumers use: the factory's in-tree dev loop and the
   pak repos' CI. It is published *from* the factory by `tooling` running
   `build-buildkit`, via a factory CI workflow on a `sdk-buildkit-vX.Y.Z` tag.
   Cutting a new kit is a deliberate, semver-meaningful version bump — not a
   hand-rolled `gh release create`. Drift between the in-tree builder and the
   published kit is the failure this guards against: same tagged source, same
   kit, no divergence.

3. **Factory publish emits a pointer, not a binary.** A `/publish` that
   references an SDK pak records a pointer to `<remote>/releases/latest` (from
   the registry); it never rebuilds or mirrors the `.pak`. The pak's own
   GitHub Release is the single source of truth for the artifact. The registry
   stays SHA-free and version-free — "latest" is derived, so it never needs
   editing when a pak ships.

## Why it matters

Putting an agent or a developer's machine in the *release* path is how
non-reproducible, unattributable artifacts escape. Keeping the canonical build
deterministic and CI-only is also what makes the build/release path
**harness-agnostic** — no Claude, no plugin, no factory checkout required to
ship a pak. That portability is the point.

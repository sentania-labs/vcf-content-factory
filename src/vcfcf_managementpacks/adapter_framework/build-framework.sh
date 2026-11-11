#!/usr/bin/env bash
# build-framework.sh — build the vcfcf-adapter-base.jar framework JAR (v2).
#
# v2: classpath is the 9.0.2 SDK jar ONLY (adapter_runtime/
# vrops-adapters-sdk-9.0.2.0.25137845.jar, or the 9.0.2.0200 rebuild
# vrops-adapters-sdk-9.0.2.0200.25431135.jar; the former name
# vrops-adapters-sdk-2.2.jar still works).
# aria-ops-core, alive_common, alive_platform are NOT on the compile classpath.
# The framework now extends AdapterBase directly (com.integrien.alive.common.adapter3)
# and defines its own SPI types under com.vcfcf.adapter.spi.*
#
# If javac reports a "cannot find symbol" for any com.vmware.tvs.* class, STOP —
# that is a clean-room wall violation and must be reported as a TOOLSET GAP rather
# than silently re-adding the aria-ops-core dependency.
#
# Run once after any change to adapter_framework/src/**/*.java.
# The resulting JAR is placed in adapter_runtime/vcfcf-adapter-base.jar
# and used as compile-time dependency by all Tier 2 SDK adapters.
#
# Compatibility legs (issues #211, #252, RULE-019): after the primary compile
# (--release 11, the one that ships), the same main source (never the tests)
# is compiled again once per supported line, and the build fails on anything
# unresolved there. Nothing from a leg is kept. The legs are the 9.0.2 jar
# itself (the 9.0 line, at --release 17) and the jars in
# $VCFCF_SDK_COMPAT_JARS (colon-separated) and $VCFCF_SDK_COMPAT_JAR (one jar)
# together, or, when neither is set, every jar in adapter_runtime/ named in
# COMPAT_JAR_NAMES (or, when absent, COMPAT_JAR_FORMER_NAMES) below. A jar
# is matched to its line by sha256. Each leg
# compiles with --release <its line's collector Java> (8.18.7: 11, 9.0: 17,
# 9.1.1.0100: 25), so each line's own Java class library is checked, on a
# JDK at least that new (PATH, JAVA_HOME, JAVA_HOME_<N>_X64, or
# $VCFCF_SDK_COMPAT_JAVAC). Every line is expected: one no jar covers, or
# whose JDK is missing, is skipped with a loud warning, or fails when
# VCFCF_SDK_COMPAT_REQUIRED=1 unless $VCFCF_SDK_COMPAT_LEGS (comma list:
# 8.18.7,9.0,9.1.1.0100) narrows the set.
# The legs run in python3 (sdk_builder.check_framework_sdk_compat), the same
# code build-sdk and validate-sdk use. When no compat jar is present, the
# pass is not required and python3 cannot import vcfcf_managementpacks (or
# with --compat-only), it is skipped here in the shell, so a plain framework
# build still works without python3 or PyYAML.
#
# Known SDK jars (issue #343): a release run, VCFCF_SDK_COMPAT_REQUIRED=1
# (factory CI) or VCFCF_RELEASE_BUILD=1, accepts only SDK jars whose sha256
# is in KNOWN_SDK_JARS below: the primary jar must be a 9.0 line jar and
# every compat jar a known jar, with no override. Any other run prints a
# boxed warning for such a jar and goes on.
#
# Exit codes: 0 built (every leg passed or skipped), 1 the framework does not
# compile (primary pass, or on a leg), 3 a compat leg could not
# run (required but jar or JDK missing, misconfigured, or python3 cannot
# import vcfcf_managementpacks), or a release run refused an SDK jar (#343).
#
# Usage:
#   cd vcfcf_managementpacks/
#   ./adapter_framework/build-framework.sh                # build + compat pass
#   ./adapter_framework/build-framework.sh --compat-only  # compat pass only;
#       no 9.0.2 jar needed, nothing written (factory CI uses this)
#
# Requirements:
#   - javac from JDK 17 or newer: the 9.0.2 jar's class files are Java 17
#     (major 61), and an older javac cannot read them
#   - adapter_runtime/vrops-adapters-sdk-9.0.2.0.25137845.jar (or
#     -9.0.2.0200.25431135.jar, or the former name -2.2.jar); copy it from a
#     9.0.2 appliance: /usr/lib/vmware-vcops/common/lib/vrops-adapters-sdk.jar
#   - python3 with PyYAML (for the legs; without it they are skipped loudly)
#   - optional, one per compat leg: adapter_runtime/vrops-adapters-sdk-8.18.7.25423534.jar
#     (Java 11 class files, any JDK 11+) and
#     adapter_runtime/vrops-adapters-sdk-9.1.1.0100.25795063.jar (Java 25, JDK 25+);
#     the former names -8.18.7.jar and -9.1.1.0100.jar still work
#
# Output:
#   adapter_runtime/vcfcf-adapter-base.jar

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$SCRIPT_DIR/.."           # vcfcf_managementpacks/

SRC_DIR="$SCRIPT_DIR/src"
RUNTIME_DIR="$ROOT/adapter_runtime"
BUILD_DIR="/tmp/vcfcf-framework-build"
OUTPUT_JAR="$RUNTIME_DIR/vcfcf-adapter-base.jar"
# The 9.0.2 jar, under a current name or its former one. Keep in step with
# sdk_builder._SDK_COMPAT_LINES (the 9.0 line's jars).
PRIMARY_JAR_NAMES="vrops-adapters-sdk-9.0.2.0.25137845.jar vrops-adapters-sdk-9.0.2.0200.25431135.jar"
PRIMARY_JAR_FORMER_NAMES="vrops-adapters-sdk-2.2.jar"
# Known SDK jars by sha256: "<sha256>|<line>|<platform>" per line. Keep equal
# to sdk_builder._SDK_COMPAT_LINES (a test checks). The jar's line is decided
# by these hashes, never by its file name.
KNOWN_SDK_JARS="2d53a91fc2b9a99d9b685ed10c1e37a471c2f71f04e7ae0fb2c53fdaa14b4f54|9.0|VCF Operations 9.0.2.0 build 25137845
a8e9ebbdc8c622fb89551d51870220e784f0097ed0800a6f490dfdc74a11119b|9.0|VCF Operations 9.0.2.0200 build 25431135
45d54c6403acf535c982a85d658b422f534c36c90ceab78a224dde67b2a640ea|8.18.7|Aria Operations 8.18.7 build 25423534
79f7b12340906359e04f3619dd87c7e67a9493b3fa5d86bdffe9242da67f46f7|9.1.1.0100|VCF Operations 9.1.1.0100 build 25795063"
# sha256 the former name vrops-adapters-sdk-2.2.jar stood for (the 9.0.2.0 jar).
PRIMARY_FORMER_SHA="2d53a91fc2b9a99d9b685ed10c1e37a471c2f71f04e7ae0fb2c53fdaa14b4f54"

# sha256 of $1, or empty when no hashing tool is available.
sha256_of() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | awk '{print $1}'
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$1" | awk '{print $1}'
    elif command -v python3 >/dev/null 2>&1; then
        python3 -I -c 'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "$1"
    fi
}

COMPAT_ONLY=0
case "${1:-}" in
    "") ;;
    --compat-only) COMPAT_ONLY=1 ;;
    *) echo "usage: $0 [--compat-only]" >&2; exit 2 ;;
esac

# Compatibility legs (issues #211, #252); see the header. Keep in step with
# sdk_builder._SDK_COMPAT_JAR_NAMES and _SDK_COMPAT_JAR_FORMER_NAMES.
COMPAT_JAR_NAMES="vrops-adapters-sdk-8.18.7.25423534.jar vrops-adapters-sdk-9.1.1.0100.25795063.jar"
COMPAT_JAR_FORMER_NAMES="vrops-adapters-sdk-8.18.7.jar vrops-adapters-sdk-9.1.1.0100.jar"
COMPAT_COULD_NOT_RUN=3   # sdk_builder.COMPAT_COULD_NOT_RUN

# A switch value as sdk_builder reads it: str.strip().lower() (leading and
# trailing whitespace, newlines included, dropped; inner whitespace kept), so
# "1 " and " TRUE" are a release run on both sides (#343).
switch_value() {
    local v="${1:-}"
    v="${v#"${v%%[![:space:]]*}"}"
    v="${v%"${v##*[![:space:]]}"}"
    printf '%s' "$v" | tr '[:upper:]' '[:lower:]'
}

compat_required() {
    case "$(switch_value "${VCFCF_SDK_COMPAT_REQUIRED:-}")" in
        1|true|yes) return 0 ;;
        *) return 1 ;;
    esac
}

# A release run (#343): VCFCF_SDK_COMPAT_REQUIRED=1 (factory CI's sdk-compat
# job) or VCFCF_RELEASE_BUILD=1, the same two switches sdk_builder reads
# (_sdk_jar_release_mode). It accepts only known SDK jars, with no override;
# any other run warns and goes on.
release_mode() {
    compat_required && return 0
    case "$(switch_value "${VCFCF_RELEASE_BUILD:-}")" in
        1|true|yes) return 0 ;;
        *) return 1 ;;
    esac
}

# Returns 0 on pass or skip (skip prints a notice); 1 on a compile failure;
# COMPAT_COULD_NOT_RUN when the pass could not run.
any_compat_jar() {
    [ -n "${VCFCF_SDK_COMPAT_JAR:-}" ] && return 0
    [ -n "$(printf '%s' "${VCFCF_SDK_COMPAT_JARS:-}" | tr -d ':')" ] && return 0
    local name
    for name in $COMPAT_JAR_NAMES $COMPAT_JAR_FORMER_NAMES; do
        [ -f "$RUNTIME_DIR/$name" ] && return 0
    done
    return 1
}

python_can_run_legs() {
    PYTHONPATH="$ROOT/..${PYTHONPATH:+:$PYTHONPATH}" python3 -c \
        'import vcfcf_managementpacks.sdk_builder' >/dev/null 2>&1
}

compat_pass() {
    # Full builds run the legs whenever python3 can (the 9.0.2 jar is the
    # 9.0 leg); --compat-only with no jar has nothing to run.
    if ! any_compat_jar && ! compat_required \
            && { [ "$COMPAT_ONLY" -eq 1 ] || ! python_can_run_legs; }; then
        local why="none of $COMPAT_JAR_NAMES (or the former $COMPAT_JAR_FORMER_NAMES) is in adapter_runtime/ and neither"
        why="$why VCFCF_SDK_COMPAT_JARS nor VCFCF_SDK_COMPAT_JAR is set"
        if [ "$COMPAT_ONLY" -ne 1 ]; then
            why="$why, and python3 cannot import vcfcf_managementpacks (the legs need python3 with PyYAML)"
        fi
        echo "  ========================================================================"
        echo "  WARNING: SDK COMPAT CHECK SKIPPED: framework source vs every supported line's SDK jar"
        echo "    reason: $why"
        echo "    This run did NOT check the 8.18.7, 9.0 (--release 17) or 9.1.1.0100 legs."
        echo "    Set VCFCF_SDK_COMPAT_REQUIRED=1 to make a skipped check fail."
        echo "  ========================================================================"
        return 0
    fi
    echo "Compat pass: framework source once per supported line ..."
    local rc=0
    # A full build has applied the known-jar rule to the primary jar already
    # (#343); --compat-only leaves it to python.
    PYTHONPATH="$ROOT/..${PYTHONPATH:+:$PYTHONPATH}" python3 -c '
import sys
try:
    from vcfcf_managementpacks.sdk_builder import check_framework_sdk_compat
except Exception as exc:
    print("ERROR: the compat pass could not run: python3 cannot import "
          "vcfcf_managementpacks.sdk_builder (%s: %s). It needs python3 with "
          "PyYAML." % (type(exc).__name__, exc), file=sys.stderr)
    sys.exit(3)
sys.exit(check_framework_sdk_compat(check_primary=sys.argv[1] == "1"))
' "$COMPAT_ONLY" || rc=$?
    return "$rc"
}

compat_report_failure() {
    # $1: exit code from compat_pass
    if [ "$1" -eq 1 ]; then
        echo "COMPAT PASS FAILED: framework source does not compile for a supported" >&2
        echo "line (named in the ERROR above)." >&2
    else
        echo "COMPAT PASS COULD NOT RUN (exit $1): see the ERROR above; at least" >&2
        echo "one supported line was not checked." >&2
    fi
}

if [ "$COMPAT_ONLY" -eq 1 ]; then
    rc=0
    compat_pass || rc=$?
    if [ "$rc" -ne 0 ]; then
        compat_report_failure "$rc"
    fi
    exit "$rc"
fi

# ---- Preflight checks -------------------------------------------------------

if ! command -v javac &>/dev/null; then
    echo "ERROR: javac not found. Install JDK 17 or newer (the 9.0.2 SDK jar's class files are Java 17)." >&2
    echo "  Ubuntu/Debian: sudo apt-get install -y openjdk-17-jdk" >&2
    echo "  RHEL/CentOS:   sudo dnf install -y java-17-openjdk-devel" >&2
    exit 1
fi

JAVA_VERSION=$(javac -version 2>&1 | awk '{print $2}' | cut -d. -f1)
if [ "${JAVA_VERSION}" = "1" ]; then
    JAVA_VERSION=$(javac -version 2>&1 | awk '{print $2}' | cut -d. -f2)
fi

echo "Using: $(javac -version 2>&1)"

SDK_JAR=""
FOUND_JARS=""
for name in $PRIMARY_JAR_NAMES $PRIMARY_JAR_FORMER_NAMES; do
    if [ -f "$RUNTIME_DIR/$name" ]; then
        FOUND_JARS="${FOUND_JARS:+$FOUND_JARS }$name"
        [ -z "$SDK_JAR" ] && SDK_JAR="$RUNTIME_DIR/$name"
    fi
done
if [ -z "$SDK_JAR" ]; then
    echo "ERROR: the 9.0.2 SDK jar is not in $RUNTIME_DIR (looked for: $PRIMARY_JAR_NAMES $PRIMARY_JAR_FORMER_NAMES)." >&2
    echo "  Copy it from a VCF Operations 9.0.2 appliance (9.0.2.0 or 9.0.2.0200) and name it" >&2
    echo "  after its build (sha256 in adapter_runtime/PROVENANCE.md):" >&2
    echo "    scp root@<appliance>:/usr/lib/vmware-vcops/common/lib/vrops-adapters-sdk.jar \\" >&2
    echo "        $RUNTIME_DIR/vrops-adapters-sdk-9.0.2.0.25137845.jar" >&2
    exit 1
fi
if [ "$FOUND_JARS" != "$(basename "$SDK_JAR")" ]; then
    echo "ERROR: adapter_runtime/ must hold exactly one 9.0.2 SDK jar; found: $FOUND_JARS. Remove the others." >&2
    exit 1
fi
# What the jar is, by sha256 (never by its file name).
SDK_SHA="$(sha256_of "$SDK_JAR" 2>/dev/null || true)"
SDK_LINE=""
SDK_PLATFORM=""
if [ -n "$SDK_SHA" ]; then
    KNOWN_ROW="$(printf '%s\n' "$KNOWN_SDK_JARS" | grep "^$SDK_SHA|" || true)"
    if [ -n "$KNOWN_ROW" ]; then
        SDK_LINE="$(printf '%s' "$KNOWN_ROW" | cut -d'|' -f2)"
        SDK_PLATFORM="$(printf '%s' "$KNOWN_ROW" | cut -d'|' -f3)"
    fi
fi
if [ -n "$SDK_LINE" ]; then
    SDK_IDENTITY="$SDK_PLATFORM ($SDK_LINE line)"
elif [ -n "$SDK_SHA" ]; then
    SDK_IDENTITY="its sha256 $(printf '%s' "$SDK_SHA" | cut -c1-12) matches no known SDK jar"
else
    SDK_IDENTITY="not hash-checked: no sha256sum, shasum or python3"
fi
for name in $PRIMARY_JAR_FORMER_NAMES; do
    if [ "$(basename "$SDK_JAR")" = "$name" ]; then
        if [ "$SDK_SHA" = "$PRIMARY_FORMER_SHA" ]; then
            echo "INFO: $name is the former name of vrops-adapters-sdk-9.0.2.0.25137845.jar; it still works."
        else
            echo "INFO: $name is the former name of vrops-adapters-sdk-9.0.2.0.25137845.jar, but this file is not that jar ($SDK_IDENTITY)."
        fi
    fi
done

# Known SDK jars only in a release run (#343, same rule as
# sdk_builder._check_sdk_jars): the framework jar is compiled against this
# jar and ships in every pak, so it must be a known 9.0 line jar. A release
# run stops (exit 3, no override); any other run prints the box and goes on.
PRIMARY_PROBLEM=""
if [ -z "$SDK_SHA" ]; then
    PRIMARY_PROBLEM="$(basename "$SDK_JAR") was not hash-checked (no sha256sum, shasum or python3), so which jar it is is unknown."
elif [ -z "$SDK_LINE" ]; then
    PRIMARY_PROBLEM="$(basename "$SDK_JAR") has sha256 $SDK_SHA, which matches no known SDK jar (adapter_runtime/PROVENANCE.md)."
elif [ "$SDK_LINE" != "9.0" ]; then
    PRIMARY_PROBLEM="$(basename "$SDK_JAR") is $SDK_PLATFORM, the $SDK_LINE line's jar, not a 9.0 line jar; pass it as a compat jar (VCFCF_SDK_COMPAT_JARS) instead."
fi
if [ -n "$PRIMARY_PROBLEM" ]; then
    if release_mode; then
        echo "ERROR: a release run (VCFCF_SDK_COMPAT_REQUIRED=1 or VCFCF_RELEASE_BUILD=1) compiles the framework only against a known 9.0 line SDK jar, and there is no override (#343):" >&2
        echo "  $PRIMARY_PROBLEM" >&2
        echo "  Known 9.0 jars: vrops-adapters-sdk-9.0.2.0.25137845.jar (VCF Operations 9.0.2.0 build 25137845)" >&2
        echo "  or vrops-adapters-sdk-9.0.2.0200.25431135.jar (VCF Operations 9.0.2.0200 build 25431135)." >&2
        echo "  Adding a jar is a buildkit release (knowledge/context/tier2_architecture.md, \"Adding an SDK jar\")." >&2
        exit "$COMPAT_COULD_NOT_RUN"
    fi
    echo "  ========================================================================"
    echo "  WARNING: SDK JAR A RELEASE BUILD WOULD REFUSE: build-framework.sh"
    echo "    - $PRIMARY_PROBLEM"
    echo "    This run continues, but a pak carrying this framework jar may not"
    echo "    run on every supported platform line."
    echo "    A release run (VCFCF_SDK_COMPAT_REQUIRED=1 or VCFCF_RELEASE_BUILD=1)"
    echo "    refuses it (#343)."
    echo "  ========================================================================"
fi

# A javac older than the jar's class files cannot read it. Read the jar's
# highest class-file major (python3; skipped without it, javac then reports).
JAR_JAVA=$(python3 -I -c '
import sys, zipfile
best = 0
with zipfile.ZipFile(sys.argv[1]) as zf:
    for info in zf.infolist():
        if info.filename.endswith(".class"):
            head = zf.open(info).read(8)
            if head[:4] == b"\xca\xfe\xba\xbe":
                best = max(best, int.from_bytes(head[6:8], "big"))
print(best - 44 if best else "")
' "$SDK_JAR" 2>/dev/null || true)
if [ -n "$JAR_JAVA" ] && [ -n "$JAVA_VERSION" ] && [ "$JAVA_VERSION" -lt "$JAR_JAVA" ] 2>/dev/null; then
    if [ -n "$SDK_LINE" ] && [ "$SDK_LINE" != "9.0" ]; then
        # Another line's jar under a 9.0.2 name: a newer JDK would compile
        # the framework against the wrong line's API.
        echo "ERROR: $(basename "$SDK_JAR") is the $SDK_LINE line's SDK jar ($SDK_PLATFORM), not a 9.0.2 jar." >&2
        echo "  The framework must compile against a 9.0.2 jar: vrops-adapters-sdk-9.0.2.0.25137845.jar" >&2
        echo "  (VCF Operations 9.0.2.0 build 25137845) or vrops-adapters-sdk-9.0.2.0200.25431135.jar" >&2
        echo "  (VCF Operations 9.0.2.0200 build 25431135); a 9.0.2 jar needs JDK 17 or newer." >&2
        echo "  (javac $JAVA_VERSION cannot read this jar either: its class files are Java $JAR_JAVA.)" >&2
        exit 1
    fi
    echo "ERROR: javac $JAVA_VERSION cannot read $(basename "$SDK_JAR") ($SDK_IDENTITY):" >&2
    echo "  its class files are Java $JAR_JAVA (class-file major $((JAR_JAVA + 44))), so it needs JDK $JAR_JAVA or newer;" >&2
    echo "  found $(javac -version 2>&1) ($(command -v javac)). Install JDK $JAR_JAVA+ and put its javac first on PATH." >&2
    exit 1
fi

# ---- Classpath verification -------------------------------------------------
# v2 compile classpath: the 9.0.2 SDK jar ONLY.
# We explicitly do NOT include aria-ops-core, alive_common, or alive_platform.
# If compilation fails for any com.vmware.tvs.* or alive* symbol, it is a
# clean-room wall violation — do not add those JARs; report it instead.

CP="$SDK_JAR"

echo "Compile classpath (v2 — SDK only):"
echo "  $SDK_JAR"
echo ""
echo "NOT on classpath (eliminated in v2):"
echo "  aria-ops-core-*.jar   (com.vmware.tvs.* — removed)"
echo "  alive_common.jar      (no longer needed)"
echo "  alive_platform.jar    (no longer needed)"
echo ""

# ---- Compile ----------------------------------------------------------------

echo "Collecting Java sources from $SRC_DIR ..."
SOURCES=$(find "$SRC_DIR" -name "*.java" | sort)
SRC_COUNT=$(echo "$SOURCES" | wc -l)

if [ -z "$SOURCES" ]; then
    echo "ERROR: no .java files found under $SRC_DIR" >&2
    exit 1
fi

echo "Found $SRC_COUNT source files"

rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# --release 11, not -source/-target: it also limits the JDK library API to
# Java 11, the 8.18 collector's runtime (issue #252, RULE-019), so a Java 12+
# call fails here instead of on that collector. Same as sdk_builder._JAVA_RELEASE.
# -proc:none: no annotation processor found in a classpath jar runs at compile
# time (sdk-runtime#1); same as every sdk_builder javac call.
echo "Compiling (--release 11) ..."
# shellcheck disable=SC2086
javac --release 11 \
    -proc:none \
    -cp "$CP" \
    -d "$BUILD_DIR" \
    $SOURCES 2>&1

COMPILE_STATUS=$?

if [ $COMPILE_STATUS -ne 0 ]; then
    echo "" >&2
    echo "COMPILATION FAILED." >&2
    echo "If error is 'cannot find symbol' for com.vmware.tvs.* or alive*:" >&2
    echo "  → clean-room wall violation — do NOT add aria-ops-core to the classpath." >&2
    echo "    Report this as a TOOLSET GAP instead." >&2
    rm -rf "$BUILD_DIR"
    exit $COMPILE_STATUS
fi

echo "Compilation successful — no aria-ops-core symbols referenced."

# ---- Compatibility legs (other platforms' SDK jars) -------------------------
COMPAT_RC=0
compat_pass || COMPAT_RC=$?
if [ "$COMPAT_RC" -ne 0 ]; then
    compat_report_failure "$COMPAT_RC"
    echo "vcfcf-adapter-base.jar was NOT written." >&2
    rm -rf "$BUILD_DIR"
    exit "$COMPAT_RC"
fi

# ---- Verify no TVS residue --------------------------------------------------
# Check that no class in the compiled output references com.vmware.tvs
TVS_REFS=$(grep -r --include="*.class" -l "tvs" "$BUILD_DIR" 2>/dev/null || true)
if [ -n "$TVS_REFS" ]; then
    echo "WARNING: compiled classes may contain com.vmware.tvs references:" >&2
    echo "$TVS_REFS" >&2
    echo "Inspect with: javap -c <classfile> | grep tvs" >&2
    # Not fatal — constant-pool strings can contain 'tvs' in log messages.
fi

# ---- Package ----------------------------------------------------------------
# The manifest carries the framework version (the buildkit version) and the
# factory commit, so a collector or a pak shows which framework it runs
# (issue #214). Same attributes as sdk_builder._ensure_framework_jar().
#   VCFCF_FRAMEWORK_VERSION overrides the version (default: BUILDKIT_VERSION
#   in buildkit.py); the commit gets "-dirty" when adapter_framework/src has
#   uncommitted changes.

FW_VERSION="${VCFCF_FRAMEWORK_VERSION:-}"
if [ -z "$FW_VERSION" ]; then
    FW_VERSION=$(sed -n 's/^BUILDKIT_VERSION *= *"\([^"]*\)".*/\1/p' "$ROOT/buildkit.py" 2>/dev/null | head -1)
fi
FW_VERSION="${FW_VERSION:-unknown}"
FW_COMMIT="unknown"
if command -v git &>/dev/null && FW_HEAD=$(git -C "$SCRIPT_DIR" rev-parse HEAD 2>/dev/null); then
    FW_COMMIT="$FW_HEAD"
    if [ -n "$(git -C "$SCRIPT_DIR" status --porcelain -- "$SRC_DIR" 2>/dev/null)" ]; then
        FW_COMMIT="$FW_COMMIT-dirty"
    fi
fi
MANIFEST_FILE="$BUILD_DIR.manifest"
printf 'Implementation-Title: vcfcf-adapter-base\nImplementation-Version: %s\nImplementation-Vendor: VCF Content Factory\nX-Vcfcf-Source-Commit: %s\n' \
    "$FW_VERSION" "$FW_COMMIT" > "$MANIFEST_FILE"

echo "Packaging JAR ..."
jar cfm "$OUTPUT_JAR" "$MANIFEST_FILE" -C "$BUILD_DIR" .
rm -f "$MANIFEST_FILE"

echo "Built: $OUTPUT_JAR ($(du -h "$OUTPUT_JAR" | cut -f1))"
echo "Stamped: vcfcf-adapter-base $FW_VERSION (source $FW_COMMIT)"

# ---- Cleanup ----------------------------------------------------------------
rm -rf "$BUILD_DIR"

echo ""
echo "v2 framework built successfully."
echo "Compile classpath: $(basename "$SDK_JAR") only."
echo "alive_common.jar, alive_platform.jar, aria-ops-core-*.jar: NOT required."

#!/usr/bin/env bash
# run_stitch_tests.sh: compile the adapter framework and run the Suite API
# stitch Java test suites (com.vcfcf.adapter.stitch.*Test) against one SDK jar.
#
# The suites are plain main() programs (no JUnit). Several capture log text
# through LogCapture, which needs log4j-api and log4j-core at runtime; the
# SDK jar does not carry them. Without them those suites print "SKIP: all"
# and pass, so this script treats a skipped suite as a failure unless
# VCFCF_STITCH_ALLOW_SKIP=1.
#
# Usage (from anywhere):
#   src/vcfcf_managementpacks/adapter_framework/run_stitch_tests.sh
#
# Environment:
#   VCFCF_SDK_JAR          SDK jar to compile and run against (default: the
#                          first of vrops-adapters-sdk-9.0.2.0.25137845.jar,
#                          vrops-adapters-sdk-9.0.2.0200.25431135.jar and the
#                          former name vrops-adapters-sdk-2.2.jar found in
#                          src/vcfcf_managementpacks/adapter_runtime/)
#   VCFCF_LOG4J_CLASSPATH  colon-separated jars carrying log4j-api and
#                          log4j-core 2.x (for example the two public
#                          org.apache.logging.log4j jars from Maven Central)
#                          (default: every jar in adapter_runtime/lib/, if any)
#   VCFCF_STITCH_RELEASE   javac --release (default 11, the release that ships)
#   VCFCF_STITCH_ALLOW_SKIP=1  let a suite that skips for want of log4j pass
#   VCFCF_SDK_COMPAT_REQUIRED=1 (or VCFCF_RELEASE_BUILD=1)  release run: the
#                          SDK jar must be a known jar of a supported line
#                          (sha256 in KNOWN_SDK_JARS below), else exit 3;
#                          otherwise an unknown jar only warns (#343)
#   JAVA_HOME              JDK to use (default: javac and java on PATH); it must
#                          read the SDK jar's class files: JDK 17+ for the 9.0.2
#                          jar, 11+ for 8.18.7, 25+ for 9.1.1.0100
#
# Exit codes: 0 every suite passed, 1 a suite failed or skipped,
# 3 setup missing (SDK jar, JDK, or a framework compile error), or a release
# run refused an SDK jar (#343).

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_DIR="$SCRIPT_DIR/../adapter_runtime"
SDK_JAR="${VCFCF_SDK_JAR:-}"
if [ -z "$SDK_JAR" ]; then
    for name in vrops-adapters-sdk-9.0.2.0.25137845.jar \
                vrops-adapters-sdk-9.0.2.0200.25431135.jar \
                vrops-adapters-sdk-2.2.jar; do
        if [ -f "$RUNTIME_DIR/$name" ]; then
            SDK_JAR="$RUNTIME_DIR/$name"
            if [ "$name" = vrops-adapters-sdk-2.2.jar ]; then
                # The name alone proves nothing: say "former name" only
                # when the bytes are the 9.0.2.0 jar's.
                sha=""
                if command -v sha256sum >/dev/null 2>&1; then
                    sha="$(sha256sum "$SDK_JAR" | awk '{print $1}')"
                elif command -v shasum >/dev/null 2>&1; then
                    sha="$(shasum -a 256 "$SDK_JAR" | awk '{print $1}')"
                fi
                if [ "$sha" = 2d53a91fc2b9a99d9b685ed10c1e37a471c2f71f04e7ae0fb2c53fdaa14b4f54 ]; then
                    echo "run_stitch_tests: INFO: $name is the former name of" \
                         "vrops-adapters-sdk-9.0.2.0.25137845.jar; it still works"
                elif [ -n "$sha" ]; then
                    echo "run_stitch_tests: INFO: $name is the former name of" \
                         "vrops-adapters-sdk-9.0.2.0.25137845.jar, but this file is" \
                         "not that jar (sha256 $(printf '%s' "$sha" | cut -c1-12))"
                else
                    echo "run_stitch_tests: INFO: $name is the former name of" \
                         "vrops-adapters-sdk-9.0.2.0.25137845.jar; this file was not" \
                         "hash-checked (no sha256sum or shasum)"
                fi
            fi
            break
        fi
    done
    SDK_JAR="${SDK_JAR:-$RUNTIME_DIR/vrops-adapters-sdk-9.0.2.0.25137845.jar}"
fi
RELEASE="${VCFCF_STITCH_RELEASE:-11}"

if [ -n "${JAVA_HOME:-}" ]; then
    JAVAC="$JAVA_HOME/bin/javac"
    JAVA="$JAVA_HOME/bin/java"
else
    JAVAC="$(command -v javac || true)"
    JAVA="$(command -v java || true)"
fi
if [ -z "$JAVAC" ] || [ ! -x "$JAVAC" ] || [ -z "$JAVA" ] || [ ! -x "$JAVA" ]; then
    echo "run_stitch_tests: no JDK (set JAVA_HOME or put javac and java on PATH)" >&2
    exit 3
fi
if [ ! -f "$SDK_JAR" ]; then
    echo "run_stitch_tests: SDK jar not found: $SDK_JAR (set VCFCF_SDK_JAR)" >&2
    exit 3
fi

# Known SDK jars (#343). This script ships nothing and runs against any
# supported line's jar, so the jar plays a compat jar's part: a release run
# (VCFCF_SDK_COMPAT_REQUIRED=1 or VCFCF_RELEASE_BUILD=1) needs a known jar
# of any line, with no override; any other run warns and goes on. Keep the
# table equal to KNOWN_SDK_JARS in build-framework.sh and
# sdk_builder._SDK_COMPAT_LINES (a test checks).
KNOWN_SDK_JARS="2d53a91fc2b9a99d9b685ed10c1e37a471c2f71f04e7ae0fb2c53fdaa14b4f54|9.0|VCF Operations 9.0.2.0 build 25137845
a8e9ebbdc8c622fb89551d51870220e784f0097ed0800a6f490dfdc74a11119b|9.0|VCF Operations 9.0.2.0200 build 25431135
45d54c6403acf535c982a85d658b422f534c36c90ceab78a224dde67b2a640ea|8.18.7|Aria Operations 8.18.7 build 25423534
79f7b12340906359e04f3619dd87c7e67a9493b3fa5d86bdffe9242da67f46f7|9.1.1.0100|VCF Operations 9.1.1.0100 build 25795063"
# A switch value as sdk_builder reads it: str.strip().lower() (leading and
# trailing whitespace, newlines included, dropped; inner whitespace kept), so
# "1 " and " TRUE" are a release run on both sides (#343).
switch_value() {
    local v="${1:-}"
    v="${v#"${v%%[![:space:]]*}"}"
    v="${v%"${v##*[![:space:]]}"}"
    printf '%s' "$v" | tr '[:upper:]' '[:lower:]'
}

is_true() {
    case "$(switch_value "${1:-}")" in
        1|true|yes) return 0 ;;
        *) return 1 ;;
    esac
}
JAR_SHA=""
if command -v sha256sum >/dev/null 2>&1; then
    JAR_SHA="$(sha256sum "$SDK_JAR" | awk '{print $1}')"
elif command -v shasum >/dev/null 2>&1; then
    JAR_SHA="$(shasum -a 256 "$SDK_JAR" | awk '{print $1}')"
fi
JAR_PROBLEM=""
if [ -z "$JAR_SHA" ]; then
    JAR_PROBLEM="$(basename "$SDK_JAR") was not hash-checked (no sha256sum or shasum), so which jar it is is unknown."
# A here-string, not printf | grep -q: grep -q exits on the first match, the
# writer can take SIGPIPE, and pipefail turns a match into "unknown jar".
elif ! grep -q "^$JAR_SHA|" <<<"$KNOWN_SDK_JARS"; then
    JAR_PROBLEM="$(basename "$SDK_JAR") has sha256 $JAR_SHA, which matches no known SDK jar (adapter_runtime/PROVENANCE.md)."
fi
if [ -n "$JAR_PROBLEM" ]; then
    if is_true "${VCFCF_SDK_COMPAT_REQUIRED:-}" || is_true "${VCFCF_RELEASE_BUILD:-}"; then
        echo "run_stitch_tests: a release run (VCFCF_SDK_COMPAT_REQUIRED=1 or VCFCF_RELEASE_BUILD=1)" \
             "runs only against a known SDK jar, and there is no override (#343): $JAR_PROBLEM" >&2
        exit 3
    fi
    echo "  ========================================================================"
    echo "  WARNING: SDK JAR A RELEASE RUN WOULD REFUSE: run_stitch_tests"
    echo "    - $JAR_PROBLEM"
    echo "    This run continues, but its results say nothing about a supported line."
    echo "    A release run (VCFCF_SDK_COMPAT_REQUIRED=1 or VCFCF_RELEASE_BUILD=1)"
    echo "    refuses it (#343)."
    echo "  ========================================================================"
fi

# A javac older than the jar's class files cannot read it: say so plainly.
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
JAVAC_MAJOR=$("$JAVAC" -version 2>&1 | awk '{print $2}' | cut -d. -f1)
if [ "$JAVAC_MAJOR" = "1" ]; then   # javac 1.8.0_x
    JAVAC_MAJOR=$("$JAVAC" -version 2>&1 | awk '{print $2}' | cut -d. -f2)
fi
if [ -n "$JAR_JAVA" ] && [ -n "$JAVAC_MAJOR" ] && [ "$JAVAC_MAJOR" -lt "$JAR_JAVA" ] 2>/dev/null; then
    echo "run_stitch_tests: javac $JAVAC_MAJOR ($JAVAC) cannot read $(basename "$SDK_JAR"):" \
         "its class files are Java $JAR_JAVA, so it needs JDK $JAR_JAVA or newer" \
         "(set JAVA_HOME)" >&2
    exit 3
fi

LOG4J_CP="${VCFCF_LOG4J_CLASSPATH:-}"
if [ -z "$LOG4J_CP" ] && [ -d "$RUNTIME_DIR/lib" ]; then
    for j in "$RUNTIME_DIR"/lib/*.jar; do
        [ -f "$j" ] && LOG4J_CP="${LOG4J_CP:+$LOG4J_CP:}$j"
    done
fi

OUT="$(mktemp -d "${TMPDIR:-/tmp}/vcfcf-stitch-tests.XXXXXX")"
trap 'rm -rf "$OUT"' EXIT
mkdir -p "$OUT/main" "$OUT/test"

MAIN_SRCS=()
while IFS= read -r -d '' f; do MAIN_SRCS+=("$f"); done \
    < <(find "$SCRIPT_DIR/src" -name '*.java' -print0)
TEST_SRCS=("$SCRIPT_DIR/test/com/vcfcf/adapter/LogCapture.java")
SUITES=()
while IFS= read -r -d '' f; do
    TEST_SRCS+=("$f")
    case "$f" in
        *Test.java) SUITES+=("com.vcfcf.adapter.stitch.$(basename "$f" .java)") ;;
    esac
done < <(find "$SCRIPT_DIR/test/com/vcfcf/adapter/stitch" -name '*.java' -print0 | sort -z)

echo "run_stitch_tests: $("$JAVAC" -version 2>&1), --release $RELEASE, SDK $(basename "$SDK_JAR")"
if ! "$JAVAC" --release "$RELEASE" -proc:none -nowarn -cp "$SDK_JAR" \
        -d "$OUT/main" "${MAIN_SRCS[@]}"; then
    echo "run_stitch_tests: framework source does not compile" >&2
    exit 3
fi
if ! "$JAVAC" --release "$RELEASE" -proc:none -nowarn -cp "$SDK_JAR:$OUT/main" \
        -d "$OUT/test" "${TEST_SRCS[@]}"; then
    echo "run_stitch_tests: stitch tests do not compile" >&2
    exit 1
fi

CP="$OUT/test:$OUT/main:$SDK_JAR${LOG4J_CP:+:$LOG4J_CP}"
rc=0
for suite in "${SUITES[@]}"; do
    echo "=== $suite"
    log="$OUT/$suite.log"
    "$JAVA" -cp "$CP" "$suite" > "$log" 2>&1
    status=$?
    grep -v '^  PASS: ' "$log"
    if [ "$status" -ne 0 ]; then
        echo "run_stitch_tests: $suite FAILED (exit $status)" >&2
        rc=1
    elif grep -q '^  SKIP: all ' "$log" && [ "${VCFCF_STITCH_ALLOW_SKIP:-0}" != 1 ]; then
        echo "run_stitch_tests: $suite SKIPPED all its tests (log4j-api/log4j-core not on" \
             "VCFCF_LOG4J_CLASSPATH); set VCFCF_STITCH_ALLOW_SKIP=1 to accept" >&2
        rc=1
    fi
done
[ "$rc" -eq 0 ] && echo "run_stitch_tests: ${#SUITES[@]} suites passed"
exit "$rc"

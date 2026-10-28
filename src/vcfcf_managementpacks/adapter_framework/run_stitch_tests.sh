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
#   VCFCF_SDK_JAR          SDK jar to compile and run against
#                          (default: src/vcfcf_managementpacks/adapter_runtime/vrops-adapters-sdk-2.2.jar)
#   VCFCF_LOG4J_CLASSPATH  colon-separated jars carrying log4j-api and
#                          log4j-core 2.x (for example the two public
#                          org.apache.logging.log4j jars from Maven Central)
#                          (default: every jar in adapter_runtime/lib/, if any)
#   VCFCF_STITCH_RELEASE   javac --release (default 11, the release that ships)
#   VCFCF_STITCH_ALLOW_SKIP=1  let a suite that skips for want of log4j pass
#   JAVA_HOME              JDK to use (default: javac and java on PATH); JDK 11+
#
# Exit codes: 0 every suite passed, 1 a suite failed or skipped,
# 3 setup missing (SDK jar, JDK, or a framework compile error).

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_DIR="$SCRIPT_DIR/../adapter_runtime"
SDK_JAR="${VCFCF_SDK_JAR:-$RUNTIME_DIR/vrops-adapters-sdk-2.2.jar}"
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

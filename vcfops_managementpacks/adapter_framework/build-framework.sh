#!/usr/bin/env bash
# build-framework.sh — build the vcfcf-adapter-base.jar framework JAR.
#
# Run this once after any change to adapter_framework/src/**/*.java.
# The resulting JAR is placed in adapter_runtime/vcfcf-adapter-base.jar
# and is used as a compile-time and runtime dependency by all Tier 2
# SDK adapters built by sdk_builder.py.
#
# Usage:
#   cd vcfops_managementpacks/
#   ./adapter_framework/build-framework.sh
#
# Requirements:
#   - javac (JDK 11 or newer; JDK 17 recommended)
#   - JARs in adapter_runtime/:
#       aria-ops-core-8.0.0.jar
#       alive_common.jar
#       alive_platform.jar
#       vrops-adapters-sdk-2.2.jar
#
# Output:
#   adapter_runtime/vcfcf-adapter-base.jar

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$SCRIPT_DIR/.."           # vcfops_managementpacks/

SRC_DIR="$SCRIPT_DIR/src"
RUNTIME_DIR="$ROOT/adapter_runtime"
BUILD_DIR="/tmp/vcfcf-framework-build"
OUTPUT_JAR="$RUNTIME_DIR/vcfcf-adapter-base.jar"

# ---- Preflight checks -------------------------------------------------------

if ! command -v javac &>/dev/null; then
    echo "ERROR: javac not found. Install JDK 11+ (recommended: JDK 17)." >&2
    echo "  Ubuntu/Debian: sudo apt-get install -y openjdk-17-jdk" >&2
    echo "  RHEL/CentOS:   sudo dnf install -y java-17-openjdk-devel" >&2
    exit 1
fi

JAVA_VERSION=$(javac -version 2>&1 | awk '{print $2}' | cut -d. -f1)
if [ "${JAVA_VERSION}" -lt 11 ] 2>/dev/null; then
    echo "ERROR: JDK 11 or newer required; found $(javac -version 2>&1)" >&2
    exit 1
fi

echo "Using: $(javac -version 2>&1)"

# ---- Build classpath --------------------------------------------------------

# Collect all JARs in adapter_runtime/ as compile-time classpath
CP=""
for jar in "$RUNTIME_DIR"/*.jar; do
    [ -f "$jar" ] || continue
    # Skip the framework JAR itself (we're building it)
    [[ "$(basename "$jar")" == "vcfcf-adapter-base.jar" ]] && continue
    CP="${CP}:${jar}"
done
CP="${CP#:}"  # strip leading colon

if [ -z "$CP" ]; then
    echo "ERROR: no JARs found in $RUNTIME_DIR — cannot build classpath." >&2
    echo "  Required: aria-ops-core-8.0.0.jar, alive_common.jar, alive_platform.jar," >&2
    echo "            vrops-adapters-sdk-2.2.jar" >&2
    exit 1
fi

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

echo "Compiling (source/target 11) ..."
# shellcheck disable=SC2086
javac -source 11 -target 11 \
    -cp "$CP" \
    -d "$BUILD_DIR" \
    $SOURCES

echo "Compilation successful"

# ---- Package ----------------------------------------------------------------

echo "Packaging JAR ..."
jar cf "$OUTPUT_JAR" -C "$BUILD_DIR" .

echo "Built: $OUTPUT_JAR ($(du -h "$OUTPUT_JAR" | cut -f1))"

# ---- Cleanup ----------------------------------------------------------------
rm -rf "$BUILD_DIR"

echo "Done."

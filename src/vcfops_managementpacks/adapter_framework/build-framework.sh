#!/usr/bin/env bash
# build-framework.sh — build the vcfcf-adapter-base.jar framework JAR (v2).
#
# v2: classpath is vrops-adapters-sdk-2.2.jar ONLY.
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
# Usage:
#   cd vcfops_managementpacks/
#   ./adapter_framework/build-framework.sh
#
# Requirements:
#   - javac (JDK 11 or newer; JDK 17 recommended)
#   - adapter_runtime/vrops-adapters-sdk-2.2.jar
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
SDK_JAR="$RUNTIME_DIR/vrops-adapters-sdk-2.2.jar"

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

if [ ! -f "$SDK_JAR" ]; then
    echo "ERROR: SDK JAR not found: $SDK_JAR" >&2
    exit 1
fi

# ---- Classpath verification -------------------------------------------------
# v2 compile classpath: vrops-adapters-sdk-2.2.jar ONLY.
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

echo "Compiling (source/target 11) ..."
# shellcheck disable=SC2086
javac -source 11 -target 11 \
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

echo "Packaging JAR ..."
jar cf "$OUTPUT_JAR" -C "$BUILD_DIR" .

echo "Built: $OUTPUT_JAR ($(du -h "$OUTPUT_JAR" | cut -f1))"

# ---- Cleanup ----------------------------------------------------------------
rm -rf "$BUILD_DIR"

echo ""
echo "v2 framework built successfully."
echo "Compile classpath: vrops-adapters-sdk-2.2.jar only."
echo "alive_common.jar, alive_platform.jar, aria-ops-core-*.jar: NOT required."

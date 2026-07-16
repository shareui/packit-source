#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Builds the self-written Kotlin dexes (sources in /kotlin/) into
# packit/dex/<name>.dex. Reflection + Xposed based, so it compiles against
# android.jar + the compile-only Xposed stubs in kotlin/stubs (never shipped),
# and R8 tree-shakes kotlin-stdlib so the dex stays tiny.
#
# Toolchain discovery order:
#   1. environment variables (ANDROID_HOME / ANDROID_SDK_ROOT, KOTLINC, ...)
#   2. the default Android Studio locations on Linux (~/Android/Sdk, etc.)
#   3. otherwise: print what to export and exit.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

SRC_DIR="$REPO_ROOT/kotlin/src"
STUB_DIR="$REPO_ROOT/kotlin/stubs"
OUT_DIR="$REPO_ROOT/kotlin-build"
DEX_OUT_BASE="$REPO_ROOT/packit/dex"
MIN_API=26

# what to build: "<dexName>=<keepClassFqn>"
PACKAGES=(
  "badges=kawaii.packetik.badges.BadgesNative"
  "openfile=kawaii.packetik.openfile.OpenFileNative"
)

die() { echo "error: $*" >&2; exit 1; }
info() { echo "[kotlin-build] $*"; }

# ---------------------------------------------------------------- Android SDK
ANDROID_SDK="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}"
if [[ -z "$ANDROID_SDK" ]]; then
  for cand in "$HOME/Android/Sdk" "$HOME/Library/Android/sdk" "/usr/lib/android-sdk" "/opt/android-sdk"; do
    [[ -d "$cand" ]] && { ANDROID_SDK="$cand"; break; }
  done
fi
[[ -n "$ANDROID_SDK" && -d "$ANDROID_SDK" ]] || die "Android SDK not found.
  Install Android Studio (default SDK path ~/Android/Sdk) or export ANDROID_HOME=/path/to/Android/Sdk"

# build-tools (latest) -> d8.jar (contains D8 and R8)
BUILD_TOOLS_DIR="$ANDROID_SDK/build-tools"
[[ -d "$BUILD_TOOLS_DIR" ]] || die "no build-tools under $ANDROID_SDK — install one via Android Studio SDK Manager (or sdkmanager 'build-tools;34.0.0')"
BUILD_TOOLS="$(ls -1 "$BUILD_TOOLS_DIR" | sort -V | tail -n1)"
D8_JAR="$BUILD_TOOLS_DIR/$BUILD_TOOLS/lib/d8.jar"
[[ -f "$D8_JAR" ]] || die "d8.jar not found at $D8_JAR"

# android.jar (latest platform), overridable via ANDROID_JAR
ANDROID_JAR="${ANDROID_JAR:-}"
if [[ -z "$ANDROID_JAR" ]]; then
  PLAT="$(ls -1d "$ANDROID_SDK"/platforms/android-* 2>/dev/null | sort -V | tail -n1 || true)"
  [[ -n "$PLAT" ]] && ANDROID_JAR="$PLAT/android.jar"
fi
[[ -n "$ANDROID_JAR" && -f "$ANDROID_JAR" ]] || die "android.jar not found.
  Install a platform via Android Studio SDK Manager (e.g. 'platforms;android-34') or export ANDROID_JAR=/path/to/android.jar"

# ---------------------------------------------------------------- Kotlin
KOTLINC="${KOTLINC:-}"
if [[ -z "$KOTLINC" ]]; then
  if command -v kotlinc >/dev/null 2>&1; then
    KOTLINC="$(command -v kotlinc)"
  elif [[ -n "${KOTLIN_HOME:-}" && -x "$KOTLIN_HOME/bin/kotlinc" ]]; then
    KOTLINC="$KOTLIN_HOME/bin/kotlinc"
  else
    # Android Studio bundled Kotlin plugin
    for base in "$HOME/android-studio" "/opt/android-studio" "/usr/local/android-studio" \
                "$HOME/.local/share/JetBrains/Toolbox/apps/android-studio"*/ \
                /snap/android-studio/current/android-studio; do
      cand="$base/plugins/Kotlin/kotlinc/bin/kotlinc"
      [[ -x "$cand" ]] && { KOTLINC="$cand"; break; }
    done
  fi
fi
[[ -n "$KOTLINC" && -x "$KOTLINC" ]] || die "kotlinc not found.
  Install the Kotlin compiler and put it on PATH, or export KOTLINC=/path/to/kotlinc
  (Android Studio bundles it under <studio>/plugins/Kotlin/kotlinc/bin/kotlinc)"

KOTLIN_HOME_RESOLVED="$(cd "$(dirname "$KOTLINC")/.." && pwd)"
KOTLIN_STDLIB="${KOTLIN_STDLIB:-$KOTLIN_HOME_RESOLVED/lib/kotlin-stdlib.jar}"
[[ -f "$KOTLIN_STDLIB" ]] || die "kotlin-stdlib.jar not found at $KOTLIN_STDLIB — export KOTLIN_STDLIB=/path/to/kotlin-stdlib.jar"
KOTLIN_ANNOTATIONS="$(ls -1 "$KOTLIN_HOME_RESOLVED"/lib/annotations-*.jar 2>/dev/null | head -n1 || true)"

command -v javac >/dev/null 2>&1 || die "javac not found — install a JDK (17+) and put it on PATH"
JAVA_HOME_LIB="${JAVA_HOME:-$(dirname "$(dirname "$(readlink -f "$(command -v javac)")")")}"

info "SDK=$ANDROID_SDK build-tools=$BUILD_TOOLS"
info "android.jar=$ANDROID_JAR"
info "kotlinc=$KOTLINC (home=$KOTLIN_HOME_RESOLVED)"

# ---------------------------------------------------------------- build
rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR/stubs" "$OUT_DIR/classes"

info "compiling Xposed compile-only stubs (javac)"
javac -d "$OUT_DIR/stubs" $(find "$STUB_DIR" -name '*.java')

info "compiling Kotlin sources (kotlinc)"
"$KOTLINC" \
  -no-stdlib -jvm-target 1.8 \
  -classpath "$ANDROID_JAR:$OUT_DIR/stubs:$KOTLIN_STDLIB" \
  -d "$OUT_DIR/classes" \
  $(find "$SRC_DIR" -name '*.kt')

# R8 keep rules: keep every self-written class + members (called reflectively
# from Python by name); strip and shrink everything else (kotlin-stdlib).
RULES="$OUT_DIR/rules.pro"
{
  echo "-keep class kawaii.packetik.** { *; }"
  echo "-dontobfuscate"
  echo "-dontoptimize"
  echo "-dontwarn de.robv.android.xposed.**"
  echo "-dontwarn org.jetbrains.annotations.**"
  echo "-dontwarn kotlin.**"
} > "$RULES"

R8_CP=("$OUT_DIR/stubs")
[[ -n "$KOTLIN_ANNOTATIONS" ]] && R8_CP+=("$KOTLIN_ANNOTATIONS")
R8_CLASSPATH_ARGS=()
for cp in "${R8_CP[@]}"; do R8_CLASSPATH_ARGS+=(--classpath "$cp"); done

info "dexing + shrinking with R8"
mkdir -p "$OUT_DIR/dex"
java -cp "$D8_JAR" com.android.tools.r8.R8 \
  --release --min-api "$MIN_API" \
  --lib "$ANDROID_JAR" --lib "$JAVA_HOME_LIB" \
  "${R8_CLASSPATH_ARGS[@]}" \
  --pg-conf "$RULES" \
  --output "$OUT_DIR/dex" \
  $(find "$OUT_DIR/classes" -name '*.class') \
  "$KOTLIN_STDLIB"

[[ -f "$OUT_DIR/dex/classes.dex" ]] || die "R8 produced no classes.dex"

# NOTE: .dex is arch-independent Dalvik bytecode; a single copy serves all ABIs.
for entry in "${PACKAGES[@]}"; do
  name="${entry%%=*}"
  mkdir -p "$DEX_OUT_BASE"
  cp "$OUT_DIR/dex/classes.dex" "$DEX_OUT_BASE/$name.dex"
  info "-> $DEX_OUT_BASE/$name.dex ($(wc -c < "$DEX_OUT_BASE/$name.dex") bytes)"
done

info "done."

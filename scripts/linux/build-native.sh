#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
LIBS_DIR="$ROOT_DIR/libs"
OUTPUT_DIR="$ROOT_DIR/native-build"
ARM64_DIR="$OUTPUT_DIR/arm64-v8a"
ARMV7_DIR="$OUTPUT_DIR/armeabi-v7a"

mkdir -p "$ARM64_DIR"
mkdir -p "$ARMV7_DIR"

if [ -z "$ANDROID_NDK_HOME" ]; then
    if [ -d "$HOME/Android/Sdk/ndk" ]; then
        ANDROID_NDK_HOME=$(ls -1d "$HOME/Android/Sdk/ndk"/* 2>/dev/null | sort -V | tail -n 1)
    elif [ -d "$HOME/Android/Sdk/ndk-bundle" ]; then
        ANDROID_NDK_HOME="$HOME/Android/Sdk/ndk-bundle"
    fi
fi

if [ -z "$ANDROID_NDK_HOME" ]; then
    echo "Error: ANDROID_NDK_HOME is not set and NDK was not found in standard paths (~/Android/Sdk/ndk)."
    echo "Please set it to your NDK path, e.g., export ANDROID_NDK_HOME=/opt/android-sdk/ndk/25.1.8937393"
    exit 1
fi

echo "Using NDK: $ANDROID_NDK_HOME"

TOOLCHAIN_FILE="$ANDROID_NDK_HOME/build/cmake/android.toolchain.cmake"
if [ ! -f "$TOOLCHAIN_FILE" ]; then
    echo "Error: Could not find android.toolchain.cmake at $TOOLCHAIN_FILE"
    exit 1
fi

LIBRARIES=("libachiv" "libbithash" "libexport" "libpackitdb" "libpacklight" "libscl" "libsearch")

build_arch() {
    local arch=$1
    local out_dir=$2
    local build_dir="$LIBS_DIR/build-$arch"

    echo "Building for $arch..."

    for lib in "${LIBRARIES[@]}"; do
        echo "Building $lib for $arch..."
        local lib_src="$LIBS_DIR/$lib"
        local lib_build="$build_dir/$lib"

        cmake -B "$lib_build" -S "$lib_src" \
            -DCMAKE_TOOLCHAIN_FILE="$TOOLCHAIN_FILE" \
            -DANDROID_ABI="$arch" \
            -DANDROID_PLATFORM=android-21 \
            -DCMAKE_BUILD_TYPE=Release

        cmake --build "$lib_build" --config Release --verbose

        find "$lib_build" -name "*.so" -exec cp -f {} "$out_dir/" \;
    done
}

build_arch "arm64-v8a" "$ARM64_DIR"
build_arch "armeabi-v7a" "$ARMV7_DIR"

echo "Build complete. Compiled libraries are in $OUTPUT_DIR"

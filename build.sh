#!/bin/bash

set -e

META="packit/mf/meta.yml"

if [ ! -d "packit" ]; then
    echo "error: packit/ not found"
    exit 1
fi

if [ ! -f "refmap.yml" ]; then
    echo "error: refmap.yml not found"
    exit 1
fi

if [ ! -f "$META" ]; then
    echo "error: $META not found"
    exit 1
fi

VERSION=$(grep '^version:' "$META" | sed 's/version: *"//' | sed 's/"//')
OUTPUT_FILE="packit-${VERSION}.eaf"

mkdir -p builds

rm -f packit-*.eaf packit-*.zip
zip -r "builds/${OUTPUT_FILE}" packit refmap.yml
echo "created: builds/${OUTPUT_FILE}"
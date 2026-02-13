#!/bin/bash

set -e

TIME=$(date +"%Y%m%d_%H%M%S")
OUTPUT_FILE="packit-${TIME}.eaf"

mkdir -p builds

if [ ! -d "packit" ]; then
    echo "error: packit/ not found"
    exit 1
fi

if [ ! -f "refmap.yml" ]; then
    echo "error: refmap.yml not found"
    exit 1
fi

rm -f packit-*.eaf packit-*.zip
zip -r "builds/${OUTPUT_FILE}" packit refmap.yml
echo "created: builds/${OUTPUT_FILE}"
#!/bin/bash

set -e

META="packit/mf/meta.yml"
ADD_VERSION=true

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

if [ "$ADD_VERSION" = true ]; then
    BASE=$(echo "$VERSION" | sed 's/\.[0-9]*$//')
    NUM=$(echo "$VERSION" | grep -o '[0-9]*$')
    NEW_NUM=$((NUM + 1))
    NEW_VERSION="${BASE}.${NEW_NUM}"
    sed -i "s/^version: \"${VERSION}\"/version: \"${NEW_VERSION}\"/" "$META"
    VERSION="$NEW_VERSION"
    echo "version bumped: ${NEW_VERSION}"
fi

OUTPUT_FILE="packit-${VERSION}.eaf"

mkdir -p builds

rm -f builds/packit-*.eaf builds/packit-*.zip
zip -P oxf -r "builds/${OUTPUT_FILE}" packit refmap.yml
echo "created: builds/${OUTPUT_FILE}"

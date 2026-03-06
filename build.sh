#!/bin/bash

set -e

ADD_VERSION=true
ADD_PASSWORD=true

META="packit/mf/meta.yml"
PASSWORD="oxf"

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

if [ "$ADD_PASSWORD" = true ]; then
    zip -P "$PASSWORD" -r "builds/${OUTPUT_FILE}" packit refmap.yml
else
    zip -r "builds/${OUTPUT_FILE}" packit refmap.yml
fi

echo "created: builds/${OUTPUT_FILE}"

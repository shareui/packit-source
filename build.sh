#!/bin/bash

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

zip -r "builds/${OUTPUT_FILE}" packit refmap.yml

if [ $? -eq 0 ]; then
    echo "created: builds/${OUTPUT_FILE}"
else
    echo "error: zip failed"
    exit 1
fi

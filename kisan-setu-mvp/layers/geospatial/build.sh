#!/bin/bash
# Build Lambda Layer for geospatial dependencies (rasterio, pyproj, numpy, Pillow)
# Uses pip --platform to download pre-built Linux x86_64 wheels (works on any host OS).
# Docker method available as fallback with --docker flag.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="$SCRIPT_DIR/python"

echo "=== Building Geospatial Lambda Layer ==="

# Clean previous build
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

if [ "$1" = "--docker" ] && docker info &>/dev/null; then
    echo "Using Docker build (x86_64 emulation)..."
    docker run --rm \
      --platform linux/amd64 \
      --entrypoint "" \
      -v "$SCRIPT_DIR:/build" \
      public.ecr.aws/lambda/python:3.11 \
      bash -c "
        pip install --upgrade pip &&
        pip install -r /build/requirements.txt -t /build/python --no-cache-dir --only-binary=:all:
      "
else
    echo "Using pip --platform for Linux x86_64 wheels..."
    pip install \
      -r "$SCRIPT_DIR/requirements.txt" \
      -t "$BUILD_DIR" \
      --platform manylinux2014_x86_64 \
      --implementation cp \
      --python-version 3.11 \
      --only-binary=:all: \
      --no-cache-dir
fi

# Remove unnecessary files to reduce layer size
find "$BUILD_DIR" -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
find "$BUILD_DIR" -type d -name 'tests' -exec rm -rf {} + 2>/dev/null || true
find "$BUILD_DIR" -type d -name 'test' -exec rm -rf {} + 2>/dev/null || true
find "$BUILD_DIR" -name '*.pyc' -delete 2>/dev/null || true
find "$BUILD_DIR" -name '*.pyo' -delete 2>/dev/null || true
find "$BUILD_DIR" -name '*.dist-info' -type d -exec rm -rf {} + 2>/dev/null || true

# Show layer size
LAYER_SIZE=$(du -sh "$BUILD_DIR" | cut -f1)
echo "Layer size: $LAYER_SIZE"
echo "Layer built at: $BUILD_DIR"
echo ""
echo "To deploy, run 'cdk deploy' from the project root."

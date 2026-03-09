#!/bin/bash

# Build Lambda deployment packages
# Syncs common/ module and installs dependencies for all Lambdas.
# Uses Docker if available, falls back to pip with --platform flag.
#
# Usage:
#   ./build_lambda_packages.sh          # Build with Docker or fallback
#   ./sync_common.sh                    # Quick common/ sync only (no pip install)
#   docker build -f Dockerfile.lambda . # Full Docker-based build

set -e

# ── Step 1: Always sync common/ to all Lambda directories ──
echo "📁 Syncing lambda/common/ to all Lambda directories..."
for dir in lambda/orchestrator lambda/processor lambda/voice lambda/router lambda/credit lambda/satellite; do
    if [ -d "$dir" ]; then
        rm -rf "$dir/common"
        cp -r lambda/common "$dir/common"
        echo "  ✓ $dir"
    fi
done
echo "✅ Common module synced"
echo ""

# ── Step 2: Install dependencies ──

build_lambda() {
    local lambda_dir=$1
    local lambda_name=$2

    echo "📦 Building $lambda_name..."

    if [ ! -f "$lambda_dir/requirements.txt" ]; then
        echo "  ⚠️  No requirements.txt, skipping pip install"
        return
    fi

    # Create temporary build directory
    local build_dir="$lambda_dir/.build"
    rm -rf "$build_dir"
    mkdir -p "$build_dir"

    # Build using Docker
    docker run --rm \
        -v "$PWD/$lambda_dir:/var/task" \
        -v "$PWD/$lambda_dir/.build:/asset-output" \
        -v "$PWD/lambda/common:/common" \
        public.ecr.aws/lambda/python:3.11 \
        bash -c "pip install -r /var/task/requirements.txt -t /asset-output && cp -r /var/task/*.py /asset-output/ && if [ -d /common ]; then cp -r /common /asset-output/; fi"

    # Move built dependencies into lambda directory
    cd "$lambda_dir"
    find . -maxdepth 1 -type d ! -name '.' ! -name '..' ! -name '.build' -exec rm -rf {} + 2>/dev/null || true
    find . -maxdepth 1 -name '*.dist-info' -exec rm -rf {} + 2>/dev/null || true
    find . -maxdepth 1 -name '*.so' -delete 2>/dev/null || true

    if [ -d ".build" ]; then
        mv .build/* . 2>/dev/null || true
        rm -rf .build
    fi

    cd - > /dev/null
    echo "✅ $lambda_name built successfully"
}

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "ℹ️  Docker not running. Using pip with --platform flag..."
    echo ""

    for lambda_dir in lambda/orchestrator lambda/processor lambda/voice; do
        if [ -f "$lambda_dir/requirements.txt" ]; then
            echo "📦 Installing dependencies for $(basename $lambda_dir)..."
            cd "$lambda_dir"

            find . -maxdepth 1 -type d ! -name '.' ! -name '..' -exec rm -rf {} + 2>/dev/null || true
            find . -maxdepth 1 -name '*.dist-info' -exec rm -rf {} + 2>/dev/null || true
            find . -maxdepth 1 -name '*.so' -delete 2>/dev/null || true

            pip install --platform manylinux2014_x86_64 --only-binary=:all: --target . -r requirements.txt

            cd - > /dev/null
            echo "✅ $(basename $lambda_dir) done"
        fi
    done

    echo ""
    echo "✅ All Lambda packages ready (common/ synced + dependencies installed)"
    echo "🚀 Run: cdk deploy"
    exit 0
fi

echo "🐳 Building with Docker..."
echo ""
build_lambda "lambda/orchestrator" "Orchestrator"
build_lambda "lambda/processor" "Document Processor"
build_lambda "lambda/voice" "Voice Handler"

echo ""
echo "✅ All Lambda packages built successfully!"
echo "🚀 Run: cdk deploy"

#!/bin/bash

# Build Lambda deployment packages using Docker
# This ensures all dependencies are Linux-compatible

set -e

echo "🐳 Building Lambda packages with Docker..."

# Function to build a Lambda package
build_lambda() {
    local lambda_dir=$1
    local lambda_name=$2
    
    echo "📦 Building $lambda_name..."
    
    # Check if requirements.txt exists
    if [ ! -f "$lambda_dir/requirements.txt" ]; then
        echo "⚠️  No requirements.txt found for $lambda_name, skipping..."
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
    
    # Clean up old dependencies in lambda directory
    cd "$lambda_dir"
    find . -maxdepth 1 -type d ! -name '.' ! -name '..' ! -name '.build' -exec rm -rf {} + 2>/dev/null || true
    find . -maxdepth 1 -name '*.dist-info' -exec rm -rf {} + 2>/dev/null || true
    find . -maxdepth 1 -name '*.so' -delete 2>/dev/null || true
    
    # Move built dependencies to lambda directory
    if [ -d ".build" ]; then
        mv .build/* . 2>/dev/null || true
        rm -rf .build
    fi
    
    cd - > /dev/null
    
    echo "✅ $lambda_name built successfully"
}

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    echo ""
    echo "Falling back to manual pip install with --platform flag..."
    
    # Fallback to manual installation
    for lambda_dir in lambda/orchestrator lambda/processor lambda/voice; do
        if [ -f "$lambda_dir/requirements.txt" ]; then
            echo "📦 Installing dependencies for $lambda_dir..."
            cd "$lambda_dir"

            # Clean up old dependencies
            find . -maxdepth 1 -type d ! -name '.' ! -name '..' -exec rm -rf {} + 2>/dev/null || true
            find . -maxdepth 1 -name '*.dist-info' -exec rm -rf {} + 2>/dev/null || true
            find . -maxdepth 1 -name '*.so' -delete 2>/dev/null || true

            # Install with Linux platform
            pip install --platform manylinux2014_x86_64 --only-binary=:all: --target . -r requirements.txt

            # Copy common module
            if [ -d "../common" ]; then
                echo "📁 Copying common module to $lambda_dir..."
                rm -rf common
                cp -r ../common .
            fi

            cd - > /dev/null
            echo "✅ Dependencies installed for $lambda_dir"
        fi
    done
    
    exit 0
fi

# Build Lambda packages
build_lambda "lambda/orchestrator" "Orchestrator"
build_lambda "lambda/processor" "Document Processor"
build_lambda "lambda/voice" "Voice Handler"

echo ""
echo "✅ All Lambda packages built successfully!"
echo "🚀 You can now run: cdk deploy"

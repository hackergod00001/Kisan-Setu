#!/bin/bash
#
# Build Lambda Layer for common library with correct Python folder structure
#
# Lambda Layers must follow this structure:
#   python/lib/python3.11/site-packages/<your_package>
#
# This allows Lambda to import: from common import DynamoDBAccess

set -e

echo "🔨 Building common library Lambda Layer..."

# Clean up previous build
rm -rf lambda/.layer-build
mkdir -p lambda/.layer-build

# Create correct Python path structure for Lambda Layer
LAYER_DIR="lambda/.layer-build/python/lib/python3.11/site-packages"
mkdir -p "$LAYER_DIR"

# Copy common library to correct location
echo "📁 Copying common library..."
cp -r lambda/common "$LAYER_DIR/common"

# Verify structure
echo "✅ Layer structure created:"
tree -L 5 lambda/.layer-build || find lambda/.layer-build -type f | head -20

echo ""
echo "✅ Common library Lambda Layer built successfully!"
echo "📦 Layer location: lambda/.layer-build/"
echo ""
echo "This layer will be deployed by CDK as 'CommonLibraryLayer'"

#!/bin/bash
# Quick sync of common/ module to all Lambda directories
# Run this before `cdk deploy` if you've changed files in lambda/common/

set -e
cd "$(dirname "$0")"

echo "Syncing lambda/common/ to all Lambda directories..."
for dir in lambda/orchestrator lambda/processor lambda/voice lambda/router lambda/credit lambda/satellite; do
    if [ -d "$dir" ]; then
        rm -rf "$dir/common"
        cp -r lambda/common "$dir/common"
        echo "  ✓ $dir/common"
    fi
done
echo "Done! You can now run: cdk deploy"

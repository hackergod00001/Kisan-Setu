#!/bin/bash

# Comprehensive deployment script for Kisan-Setu MVP
# Handles Lambda packaging and CDK deployment

set -e

echo "🚀 Kisan-Setu MVP Deployment"
echo "============================"
echo ""

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Virtual environment not activated"
    echo "Activating .venv..."
    source .venv/bin/activate || {
        echo "❌ Failed to activate virtual environment"
        echo "Please run: python3 -m venv .venv && source .venv/bin/activate"
        exit 1
    }
fi

# Step 1: Build Lambda packages
echo "📦 Step 1: Building Lambda packages..."
./build_lambda_packages.sh

echo ""
echo "☁️  Step 2: Deploying to AWS..."

# Step 2: Deploy with CDK
cdk deploy --require-approval never

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📋 Next steps:"
echo "1. Test by sending a WhatsApp message to your business number"
echo "2. Check logs: aws logs tail /aws/lambda/KisanSetuMVPStack-BedrockOrchestratorF1D5335E-8c6vEjDJfHEl --follow --region ap-south-1"
echo "3. Update WhatsApp token if needed: ./deploy_meta_whatsapp.sh"

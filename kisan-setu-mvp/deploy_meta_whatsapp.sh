#!/bin/bash

# Meta WhatsApp Deployment Script for Kisan-Setu
# Deploy with your Meta WhatsApp Business API credentials

set -e

echo "🚀 Kisan-Setu Meta WhatsApp Setup"
echo "===================================="
echo ""

# Your Meta WhatsApp credentials
PHONE_NUMBER_ID="1043444535519617"
BUSINESS_ACCOUNT_ID="1249840547247394"
TEST_NUMBER="+15551778394"

echo "📋 Configuration:"
echo "  Phone Number ID: $PHONE_NUMBER_ID"
echo "  Business Account ID: $BUSINESS_ACCOUNT_ID"
echo "  Test Number: $TEST_NUMBER"
echo ""

# Check if credentials already exist in Secrets Manager
echo "🔐 Checking AWS Secrets Manager..."
SECRET_EXISTS=$(aws secretsmanager describe-secret \
  --secret-id kisan-setu/whatsapp/credentials \
  --region ap-south-1 2>/dev/null || echo "")

if [ -n "$SECRET_EXISTS" ]; then
    echo "✓ Credentials already exist in Secrets Manager"
    echo ""
    
    # Check if access token is provided for update
    if [ -n "$WHATSAPP_API_TOKEN" ]; then
        echo "🔄 Updating credentials in Secrets Manager..."
        aws secretsmanager update-secret \
          --secret-id kisan-setu/whatsapp/credentials \
          --secret-string "{
            \"WHATSAPP_ACCESS_TOKEN\": \"$WHATSAPP_API_TOKEN\",
            \"PHONE_NUMBER_ID\": \"$PHONE_NUMBER_ID\",
            \"BUSINESS_ACCOUNT_ID\": \"$BUSINESS_ACCOUNT_ID\",
            \"VERIFY_TOKEN\": \"kisan-setu-verify-2026\"
          }" \
          --region ap-south-1
        echo "✓ Credentials updated"
        echo ""
    else
        echo "ℹ️  Using existing credentials (to update, set WHATSAPP_API_TOKEN)"
        echo ""
    fi
else
    # Credentials don't exist, require token
    if [ -z "$WHATSAPP_API_TOKEN" ]; then
        echo "❌ Error: WHATSAPP_API_TOKEN not found"
        echo ""
        echo "Please set your access token:"
        echo "  export WHATSAPP_API_TOKEN='EAAxxxxxxxxxxxxx'"
        echo ""
        echo "Get your token from:"
        echo "  Meta App Dashboard > WhatsApp > API Setup"
        echo "  (Copy the 'Temporary access token')"
        exit 1
    fi
    
    echo "🔐 Storing credentials in AWS Secrets Manager..."
    aws secretsmanager create-secret \
      --name kisan-setu/whatsapp/credentials \
      --secret-string "{
        \"WHATSAPP_ACCESS_TOKEN\": \"$WHATSAPP_API_TOKEN\",
        \"PHONE_NUMBER_ID\": \"$PHONE_NUMBER_ID\",
        \"BUSINESS_ACCOUNT_ID\": \"$BUSINESS_ACCOUNT_ID\",
        \"VERIFY_TOKEN\": \"kisan-setu-verify-2026\"
      }" \
      --region ap-south-1
    echo "✓ Credentials stored in Secrets Manager"
    echo ""
fi

# Deploy CDK stack
echo "🚀 Deploying CDK stack..."
echo ""
cdk deploy --all --require-approval never

echo ""
echo "✓ CDK deployment complete"
echo ""

# Get API Gateway URL
echo "🔗 Getting API Gateway URL..."
API_ID=$(aws apigateway get-rest-apis \
  --query "items[?name=='KisanSetuAPI'].id" \
  --output text \
  --region ap-south-1 2>/dev/null)

if [ -n "$API_ID" ]; then
    WEBHOOK_URL="https://${API_ID}.execute-api.ap-south-1.amazonaws.com/prod/webhook"
    echo "✓ Webhook URL: $WEBHOOK_URL"
    echo ""
    echo "📋 Next Steps:"
    echo "=============="
    echo ""
    echo "1. Configure Meta Webhook:"
    echo "   - Go to: Meta App Dashboard > WhatsApp > Configuration"
    echo "   - Click 'Edit' next to Webhook"
    echo "   - Callback URL:"
    echo "     $WEBHOOK_URL"
    echo "   - Verify Token: kisan-setu-verify-2026"
    echo "   - Click 'Verify and Save'"
    echo ""
    echo "2. Subscribe to Webhook Fields:"
    echo "   - Check: messages"
    echo "   - Check: message_status (optional)"
    echo "   - Click 'Subscribe'"
    echo ""
    echo "3. Test the integration:"
    echo "   - Send WhatsApp message to your business number"
    echo "   - You should receive a response!"
    echo ""
else
    echo "⚠️  Could not find API Gateway"
    echo "   The webhook URL will be available after deployment completes"
    echo ""
fi

echo "✅ Meta WhatsApp setup complete!"
echo ""
echo "🔄 To update token (expires in 24 hours):"
echo "   export WHATSAPP_API_TOKEN='new_token'"
echo "   ./deploy_meta_whatsapp.sh"

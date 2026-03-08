#!/bin/bash

# Update WhatsApp Access Token in AWS Secrets Manager
# Usage: ./update_whatsapp_token.sh YOUR_NEW_PERMANENT_TOKEN

NEW_TOKEN="$1"

if [ -z "$NEW_TOKEN" ]; then
  echo "❌ Error: Please provide the new permanent token"
  echo "Usage: ./update_whatsapp_token.sh YOUR_NEW_PERMANENT_TOKEN"
  exit 1
fi

echo "🔄 Updating WhatsApp access token..."

# Create updated credentials JSON
cat > /tmp/whatsapp-creds.json << EOL
{
  "WHATSAPP_ACCESS_TOKEN": "$NEW_TOKEN",
  "PHONE_NUMBER_ID": "1043444535519617",
  "BUSINESS_ACCOUNT_ID": "1249840547247394",
  "VERIFY_TOKEN": "kisan-setu-verify-2026"
}
EOL

# Update the secret in AWS
aws secretsmanager update-secret \
  --secret-id kisan-setu/whatsapp/credentials \
  --secret-string file:///tmp/whatsapp-creds.json

if [ $? -eq 0 ]; then
  echo "✅ WhatsApp token updated successfully!"
  echo "🎯 Your new permanent token (60 days) is now active"
  echo "🧪 Test by sending a WhatsApp message"
  rm /tmp/whatsapp-creds.json
else
  echo "❌ Failed to update token"
  exit 1
fi

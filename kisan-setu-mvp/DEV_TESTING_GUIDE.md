# Dev Environment Testing Guide

## 🎯 Dev Environment Overview

Your **development environment** is fully deployed and isolated from production. Here's what you have:

### ✅ Dev Infrastructure Created

**API Gateway & Webhook:**
- **Dev Webhook URL**: `https://chf0n7zrjd.execute-api.ap-south-1.amazonaws.com/prod/webhook`
- **API Gateway Endpoint**: `https://chf0n7zrjd.execute-api.ap-south-1.amazonaws.com/prod/`
- **API Key ID**: `x7dvv3bafj` (for protected endpoints)

**DynamoDB:**
- **Table Name**: `dev-KisanSetuData`
- **Status**: ACTIVE (empty, 0 items)
- **Isolated**: Separate from production data

**S3 Buckets:**
- Raw images: `s3://kisan-setu-dev-raw-682366718780`
- Processed data: `s3://kisan-setu-dev-processed-682366718780`
- Archive: `s3://kisan-setu-dev-archive-682366718780`
- Dashboard: `s3://kisan-setu-dev-dashboard-682366718780`

**AppSync GraphQL API:**
- **GraphQL URL**: `https://vguvd4kogvb3tnofkn45urnkk4.appsync-api.ap-south-1.amazonaws.com/graphql`
- **API ID**: `jpusfo5bbbgpjcafjrrl6rj6cq`
- **Auth**: Cognito User Pools (no API key)

**Cognito User Pool:**
- **User Pool ID**: `ap-south-1_jqOcFr9x4`
- **Client ID**: `a8e3co32m6shpafead54feuv0`

**Lambda Functions:**
- All 8 Lambda functions deployed with `dev-` prefix
- Lambda Layer attached and working
- Bug fixes deployed

**Dashboard:**
- **CloudFront URL**: `https://d99dov0h5oi6u.cloudfront.net`

---

## 🔧 Option 1: Test with Existing WhatsApp Number (Recommended)

You can use your existing **production WhatsApp number** to test the dev environment without creating a new number.

### Step 1: Update Webhook in Meta Business Suite

1. Go to **Meta Business Suite**: https://business.facebook.com/
2. Navigate to **WhatsApp** → **API Setup**
3. Find **Webhook Configuration**
4. **Temporarily** update the webhook URL:
   ```
   Current (Production): https://YOUR_PROD_WEBHOOK_URL/webhook
   Change to (Dev):      https://chf0n7zrjd.execute-api.ap-south-1.amazonaws.com/prod/webhook
   ```
5. **Verify Token**: Keep the same token `kisan-setu-verify-2026`
6. Click **Verify and Save**

### Step 2: Test WhatsApp Messages

Send messages to your WhatsApp number:

**Text Message:**
```
Hello, what is the weather forecast for my farm?
```
Expected: Message routed to Bedrock Orchestrator, response generated

**Image Message:**
- Send a photo of a ledger or document
- Expected: Image uploaded to S3, processed by OCR, data extracted

**Voice Message:**
- Send a voice note
- Expected: Audio transcribed, processed, response sent back

### Step 3: Verify Data in Dev Environment

Check DynamoDB:
```bash
aws dynamodb scan \
  --table-name dev-KisanSetuData \
  --region ap-south-1 \
  --limit 5
```

Check S3 uploads:
```bash
aws s3 ls s3://kisan-setu-dev-raw-682366718780/ --recursive | tail -10
```

Check CloudWatch Logs:
```bash
aws logs tail /aws/lambda/KisanSetuMVPStack-dev-MessageRouter8CD84FD1-1A5Q1R9pzkHF \
  --region ap-south-1 \
  --since 10m \
  --follow
```

### Step 4: Restore Production Webhook

**IMPORTANT**: After testing, restore production webhook:
1. Go back to Meta Business Suite
2. Change webhook URL back to production
3. Verify and save

---

## 🔧 Option 2: Create New Test Number (Isolated Testing)

If you want completely isolated testing without affecting production:

### Step 1: Create Test WhatsApp Number

1. Go to **Meta Business Suite**
2. Navigate to **WhatsApp** → **Phone Numbers**
3. Click **Add Phone Number**
4. Options:
   - **Use existing number** (personal test number)
   - **Get new number** (from Meta - may require verification)

### Step 2: Configure Test Number Webhook

1. Select the new test number
2. Configure webhook:
   ```
   Webhook URL: https://chf0n7zrjd.execute-api.ap-south-1.amazonaws.com/prod/webhook
   Verify Token: kisan-setu-verify-2026
   ```
3. Subscribe to message events

### Step 3: Update WhatsApp Credentials in Dev

The dev environment uses a separate AWS Secrets Manager secret:

```bash
# Get current secret value
aws secretsmanager get-secret-value \
  --secret-id kisan-setu/dev/whatsapp/credentials \
  --region ap-south-1 \
  --query 'SecretString' \
  --output text | jq '.'

# Update with test number credentials
aws secretsmanager put-secret-value \
  --secret-id kisan-setu/dev/whatsapp/credentials \
  --region ap-south-1 \
  --secret-string '{
    "phone_number_id": "YOUR_TEST_NUMBER_ID",
    "business_account_id": "YOUR_BUSINESS_ACCOUNT_ID",
    "access_token": "YOUR_TEST_ACCESS_TOKEN",
    "webhook_verify_token": "kisan-setu-verify-2026"
  }'
```

### Step 4: Test with Test Number

Send messages to the test number and verify as in Option 1.

---

## 🧪 Testing Checklist

### Basic Functionality Tests

- [ ] **Webhook Verification**
  ```bash
  curl "https://chf0n7zrjd.execute-api.ap-south-1.amazonaws.com/prod/webhook?hub.mode=subscribe&hub.verify_token=kisan-setu-verify-2026&hub.challenge=test123"
  ```
  Expected: Returns "test123"

- [ ] **Text Message Processing**
  - Send: "Hello"
  - Check: CloudWatch logs show message received
  - Check: Response sent back via WhatsApp
  - Check: DynamoDB has message record

- [ ] **Image Processing (Ledger)**
  - Send: Photo of a ledger/receipt
  - Check: Image uploaded to S3 raw bucket
  - Check: OCR processing triggered
  - Check: Extracted data in DynamoDB

- [ ] **Voice Processing**
  - Send: Voice note in Hindi/English
  - Check: Audio uploaded to S3
  - Check: Transcription completed
  - Check: Response generated

- [ ] **Credit Score Query**
  - Send: "What is my credit score?"
  - Check: Credit calculator Lambda invoked
  - Check: Score calculated from transaction history

- [ ] **Satellite Imagery Query**
  - Send: "Show me my farm health"
  - Check: Satellite analyzer invoked
  - Check: NDVI calculation performed
  - Check: Heatmap generated (if coordinates available)

### GraphQL API Tests

Test offline sync functionality:

```bash
# 1. Create Cognito user
aws cognito-idp admin-create-user \
  --user-pool-id ap-south-1_jqOcFr9x4 \
  --username test-farmer \
  --temporary-password Test123! \
  --region ap-south-1

# 2. Get JWT token (use Cognito auth flow)
# 3. Test GraphQL mutation
curl -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "query": "mutation { syncOfflineTransactions(transactions: [{id: \"test1\", amount: 100, timestamp: \"2026-03-18T10:00:00Z\"}]) { syncedCount conflicts { transactionId reason } } }"
  }' \
  https://vguvd4kogvb3tnofkn45urnkk4.appsync-api.ap-south-1.amazonaws.com/graphql
```

### Lambda Layer Tests

Verify imports work correctly:

```bash
# Test any Lambda function
aws lambda invoke \
  --function-name KisanSetuMVPStack-dev-DocumentProcessor3D49A083-ZmBslFT2GrJ5 \
  --payload '{"test": true}' \
  --region ap-south-1 \
  /tmp/lambda-output.json

# Check logs for import errors
aws logs tail /aws/lambda/KisanSetuMVPStack-dev-DocumentProcessor3D49A083-ZmBslFT2GrJ5 \
  --region ap-south-1 \
  --since 5m
```

---

## 📊 Monitoring Dev Environment

### CloudWatch Logs

**View MessageRouter logs:**
```bash
aws logs tail /aws/lambda/KisanSetuMVPStack-dev-MessageRouter8CD84FD1-1A5Q1R9pzkHF \
  --region ap-south-1 \
  --since 30m \
  --follow
```

**View all Lambda function logs:**
```bash
for func in $(aws lambda list-functions --region ap-south-1 --query 'Functions[?contains(FunctionName, `dev`)].FunctionName' --output text); do
  echo "=== $func ==="
  aws logs tail "/aws/lambda/$func" --region ap-south-1 --since 10m | head -20
  echo ""
done
```

### DynamoDB Items

**Count items:**
```bash
aws dynamodb scan \
  --table-name dev-KisanSetuData \
  --select COUNT \
  --region ap-south-1
```

**View recent items:**
```bash
aws dynamodb scan \
  --table-name dev-KisanSetuData \
  --limit 10 \
  --region ap-south-1 | jq '.Items'
```

### S3 Bucket Contents

**Raw bucket (uploaded images/audio):**
```bash
aws s3 ls s3://kisan-setu-dev-raw-682366718780/ --recursive
```

**Processed bucket (OCR results, transcriptions):**
```bash
aws s3 ls s3://kisan-setu-dev-processed-682366718780/ --recursive
```

---

## 🔍 Debugging Common Issues

### Issue: Webhook Verification Fails

**Check:**
```bash
curl -v "https://chf0n7zrjd.execute-api.ap-south-1.amazonaws.com/prod/webhook?hub.mode=subscribe&hub.verify_token=kisan-setu-verify-2026&hub.challenge=test123"
```

**Expected Response:** HTTP 200, body: "test123"

**If fails:**
- Check API Gateway logs
- Verify Lambda function deployed correctly
- Check MessageRouter CloudWatch logs

### Issue: Messages Not Processed

**Check Lambda function status:**
```bash
aws lambda get-function \
  --function-name KisanSetuMVPStack-dev-MessageRouter8CD84FD1-1A5Q1R9pzkHF \
  --region ap-south-1 \
  --query 'Configuration.State'
```

**Check for errors:**
```bash
aws logs filter-log-events \
  --log-group-name /aws/lambda/KisanSetuMVPStack-dev-MessageRouter8CD84FD1-1A5Q1R9pzkHF \
  --region ap-south-1 \
  --filter-pattern ERROR \
  --since 1h
```

### Issue: WhatsApp Secret Not Found

**Check if secret exists:**
```bash
aws secretsmanager describe-secret \
  --secret-id kisan-setu/dev/whatsapp/credentials \
  --region ap-south-1
```

**If doesn't exist, create it:**
```bash
aws secretsmanager create-secret \
  --name kisan-setu/dev/whatsapp/credentials \
  --description "WhatsApp credentials for dev environment" \
  --secret-string '{
    "phone_number_id": "YOUR_PHONE_NUMBER_ID",
    "business_account_id": "YOUR_BUSINESS_ACCOUNT_ID",
    "access_token": "YOUR_ACCESS_TOKEN",
    "webhook_verify_token": "kisan-setu-verify-2026"
  }' \
  --region ap-south-1
```

### Issue: DynamoDB Access Denied

**Check Lambda execution role:**
```bash
aws lambda get-function \
  --function-name KisanSetuMVPStack-dev-MessageRouter8CD84FD1-1A5Q1R9pzkHF \
  --region ap-south-1 \
  --query 'Configuration.Role'
```

**Verify role has DynamoDB permissions**

---

## 🎯 Complete End-to-End Test Flow

### Scenario: Farmer Uploads Ledger Image

1. **Farmer sends ledger photo via WhatsApp**
   - Image shows: Date, Crop, Quantity, Price

2. **System processes:**
   ```
   WhatsApp → API Gateway → MessageRouter Lambda
             → DocumentProcessor Lambda
             → Textract OCR
             → Extract: quantity=100kg, price=₹5000, crop=onion
             → Store in DynamoDB (dev-KisanSetuData)
             → Upload image to S3 (kisan-setu-dev-raw-682366718780)
   ```

3. **Verification steps:**
   ```bash
   # Check DynamoDB for transaction
   aws dynamodb query \
     --table-name dev-KisanSetuData \
     --key-condition-expression "PK = :pk" \
     --expression-attribute-values '{":pk":{"S":"FARMER#test-farmer"}}' \
     --region ap-south-1

   # Check S3 for image
   aws s3 ls s3://kisan-setu-dev-raw-682366718780/ledger-images/ --recursive

   # Check CloudWatch logs
   aws logs tail /aws/lambda/KisanSetuMVPStack-dev-DocumentProcessor3D49A083-ZmBslFT2GrJ5 \
     --region ap-south-1 \
     --since 5m
   ```

4. **Expected outcome:**
   - Farmer receives confirmation message
   - Transaction stored in dev DynamoDB
   - Image archived in dev S3

---

## 🚦 Next Steps

After dev testing is complete:

1. ✅ Verify all functionality works in dev
2. ✅ Fix any issues found
3. ✅ Commit and push fixes to `dev` branch
4. ✅ Merge `dev` → `staging`
5. ✅ Deploy to staging environment
6. ✅ Test staging (closer to production)
7. ⏳ **Wait for judging period to end** (15 days)
8. ✅ Merge `staging` → `master`
9. ✅ Deploy to production (with manual approval)

---

## 📞 Quick Reference

| Resource | Value |
|----------|-------|
| **Webhook URL** | `https://chf0n7zrjd.execute-api.ap-south-1.amazonaws.com/prod/webhook` |
| **Verify Token** | `kisan-setu-verify-2026` |
| **DynamoDB Table** | `dev-KisanSetuData` |
| **S3 Raw Bucket** | `s3://kisan-setu-dev-raw-682366718780` |
| **GraphQL URL** | `https://vguvd4kogvb3tnofkn45urnkk4.appsync-api.ap-south-1.amazonaws.com/graphql` |
| **Dashboard** | `https://d99dov0h5oi6u.cloudfront.net` |
| **AWS Region** | `ap-south-1` |

---

## ⚠️ Important Notes

1. **Production Isolation**: Dev environment is completely isolated. Testing in dev will NOT affect production data or users.

2. **WhatsApp Number**: Recommended to use Option 1 (temporarily switch webhook) for quick testing. Remember to restore production webhook after testing.

3. **Secrets**: Dev uses separate AWS Secrets Manager entry (`kisan-setu/dev/whatsapp/credentials`). Production secrets are not affected.

4. **Cost**: Dev environment costs ~$5-10/month when idle. Delete after testing if needed to reduce costs.

5. **Data**: Dev DynamoDB is empty. You'll need to create test data by sending messages or using seed_data.py script.

---

**Ready to test!** Start with Option 1 for quick testing, or Option 2 for fully isolated testing.

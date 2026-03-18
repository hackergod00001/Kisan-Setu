# Complete Setup Guide: Dev Testing + GitHub Actions

This guide covers:
1. ✅ Setting up dev WhatsApp test number (Option 2)
2. ✅ Configuring GitHub Actions to enable CI/CD
3. ✅ Testing the complete flow

---

## Part 1: Set Up Dev WhatsApp Test Number (Option 2)

### Step 1: Get WhatsApp Test Number Credentials

You need to get credentials from Meta Business Suite for a test number:

1. Go to **Meta Business Suite**: https://business.facebook.com/
2. Navigate to **WhatsApp** → **API Setup**
3. Either:
   - Use an existing test number, OR
   - Add a new phone number

4. Get these values:
   - **Phone Number ID**: Find in API Setup page
   - **Business Account ID**: In settings
   - **Access Token**: Generate a permanent token (not temporary)
   - **Webhook Verify Token**: `kisan-setu-verify-2026`

### Step 2: Create AWS Secret for Dev Environment

Once you have the credentials, create the secret in AWS:

```bash
aws secretsmanager create-secret \
  --name kisan-setu/dev/whatsapp/credentials \
  --description "WhatsApp credentials for dev environment" \
  --secret-string '{
    "phone_number_id": "YOUR_PHONE_NUMBER_ID_HERE",
    "business_account_id": "YOUR_BUSINESS_ACCOUNT_ID_HERE",
    "access_token": "YOUR_PERMANENT_ACCESS_TOKEN_HERE",
    "webhook_verify_token": "kisan-setu-verify-2026"
  }' \
  --region ap-south-1
```

**Replace** `YOUR_PHONE_NUMBER_ID_HERE`, `YOUR_BUSINESS_ACCOUNT_ID_HERE`, and `YOUR_PERMANENT_ACCESS_TOKEN_HERE` with actual values.

### Step 3: Configure Test Number Webhook

In Meta Business Suite, for your test number:

1. **Webhook URL**: `https://chf0n7zrjd.execute-api.ap-south-1.amazonaws.com/prod/webhook`
2. **Verify Token**: `kisan-setu-verify-2026`
3. Click **Verify and Save**

### Step 4: Subscribe to Events

Make sure these events are subscribed:
- ✅ messages
- ✅ message_status
- ✅ messaging_optins
- ✅ message_echoes

### Step 5: Test the Setup

Send a test message to your WhatsApp test number:

```
Hello from dev environment!
```

**Verify:**
```bash
# Check CloudWatch logs
aws logs tail /aws/lambda/KisanSetuMVPStack-dev-MessageRouter8CD84FD1-1A5Q1R9pzkHF \
  --region ap-south-1 \
  --since 5m \
  --follow

# Check DynamoDB
aws dynamodb scan \
  --table-name dev-KisanSetuData \
  --region ap-south-1 \
  --limit 5
```

---

## Part 2: Configure GitHub Actions (Enable CI/CD)

### Why GitHub Actions Aren't Running Yet

GitHub Actions workflows are created but **won't run until you add the required secrets and environments**. This is a security feature.

### Step 1: Add GitHub Secrets

Go to your GitHub repository: https://github.com/hackergod00001/Kisan-Setu

1. Click **Settings** (top menu)
2. In left sidebar: **Secrets and variables** → **Actions**
3. Click **New repository secret**

Add these **3 secrets**:

#### Secret 1: AWS_ACCESS_KEY_ID
```
Name: AWS_ACCESS_KEY_ID
Value: <GET FROM /tmp/github-actions-credentials.json - AccessKeyId field>
```
**To get the value:**
```bash
cat /tmp/github-actions-credentials.json | jq -r '.AccessKeyId'
```
Click **Add secret**

#### Secret 2: AWS_SECRET_ACCESS_KEY
```
Name: AWS_SECRET_ACCESS_KEY
Value: <GET FROM /tmp/github-actions-credentials.json - SecretAccessKey field>
```
⚠️ **IMPORTANT**: Get the full secret key value
**To get the value:**
```bash
cat /tmp/github-actions-credentials.json | jq -r '.SecretAccessKey'
```
Click **Add secret**

#### Secret 3: AWS_ACCOUNT_ID
```
Name: AWS_ACCOUNT_ID
Value: 682366718780
```
Click **Add secret**

**Verification**: You should now see 3 secrets listed:
- AWS_ACCESS_KEY_ID
- AWS_SECRET_ACCESS_KEY
- AWS_ACCOUNT_ID

### Step 2: Create GitHub Environments

Still in **Settings**, click **Environments** (left sidebar)

#### Create Environment 1: development

1. Click **New environment**
2. Name: `development` (lowercase, exactly this)
3. **Protection rules**: None needed (auto-deploy)
4. Click **Configure environment**
5. No changes needed, just save

#### Create Environment 2: staging

1. Click **New environment**
2. Name: `staging` (lowercase, exactly this)
3. **Protection rules** (optional):
   - ☐ Required reviewers: Add yourself (optional)
4. Click **Configure environment** → Save

#### Create Environment 3: production

1. Click **New environment**
2. Name: `production` (lowercase, exactly this)
3. **Protection rules** (⚠️ CRITICAL):
   - ✅ **Required reviewers**: Add 1-2 people (at least yourself)
   - ✅ **Deployment branches**: Selected branches only
     - Add: `master`
4. Click **Configure environment** → Save

**Verification**: You should see 3 environments:
- development
- staging
- production

### Step 3: Trigger GitHub Actions

Now that secrets and environments are configured, GitHub Actions will run automatically on:
- Push to `dev` branch → Deploy to development
- Push to `staging` branch → Deploy to staging
- Push to `master` branch → **Wait for approval** → Deploy to production

**Test it now:**

```bash
cd kisan-setu-mvp

# Make a small test change
echo "# GitHub Actions test" >> README.md

git add README.md
git commit -m "Test GitHub Actions deployment"
git push origin dev
```

**Watch deployment:**
1. Go to **Actions** tab in GitHub
2. You should see a workflow running: "Kisan-Setu Deployment Pipeline"
3. Click on it to watch real-time deployment

### Step 4: Monitor First Deployment

The workflow will:
1. ✅ Build Lambda Layer
2. ✅ Deploy to dev environment
3. ✅ Verify deployment
4. ✅ Show outputs

**If it fails**, check:
- Secrets are added correctly (no typos)
- Environments are named exactly: `development`, `staging`, `production`
- IAM user `github-actions-kisan-setu` exists and has permissions

---

## Part 3: Complete Testing Flow

### Test 1: Text Message

**Send to test number:**
```
What is my credit score?
```

**Verify:**
```bash
# Check logs
aws logs tail /aws/lambda/KisanSetuMVPStack-dev-MessageRouter8CD84FD1-1A5Q1R9pzkHF \
  --region ap-south-1 \
  --since 5m

# Check DynamoDB for message
aws dynamodb scan \
  --table-name dev-KisanSetuData \
  --region ap-south-1
```

### Test 2: Image Upload (Ledger)

**Send a photo** of a receipt/ledger to test number

**Verify:**
```bash
# Check S3 for uploaded image
aws s3 ls s3://kisan-setu-dev-raw-682366718780/ledger-images/ --recursive

# Check processing logs
aws logs tail /aws/lambda/KisanSetuMVPStack-dev-DocumentProcessor3D49A083-ZmBslFT2GrJ5 \
  --region ap-south-1 \
  --since 5m
```

### Test 3: Voice Note

**Send a voice note** (Hindi or English) to test number

**Verify:**
```bash
# Check S3 for audio
aws s3 ls s3://kisan-setu-dev-raw-682366718780/voice-messages/ --recursive

# Check transcription logs
aws logs tail /aws/lambda/KisanSetuMVPStack-dev-VoiceHandlerE91162FD-Vam3UsPjVaJH \
  --region ap-south-1 \
  --since 5m
```

### Test 4: GraphQL Sync (Offline Transactions)

```bash
# Create test user
aws cognito-idp admin-create-user \
  --user-pool-id ap-south-1_jqOcFr9x4 \
  --username test-farmer-dev \
  --user-attributes Name=phone_number,Value=+919876543210 \
  --temporary-password Test123! \
  --region ap-south-1

# Test GraphQL mutation (after getting JWT token)
curl -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "query": "mutation { syncOfflineTransactions(transactions: [{id: \"test1\", farmerId: \"test-farmer-dev\", amount: 100, cropType: \"onion\", timestamp: \"2026-03-18T10:00:00Z\"}]) { syncedCount conflicts { transactionId } } }"
  }' \
  https://vguvd4kogvb3tnofkn45urnkk4.appsync-api.ap-south-1.amazonaws.com/graphql
```

---

## Part 4: GitHub Actions Deployment Flow

### Automatic Deployments

| Action | Branch | Environment | Approval | Result |
|--------|--------|-------------|----------|--------|
| Push code | `dev` | development | ❌ None | Auto-deploy to dev |
| Push code | `staging` | staging | ⚠️ Optional | Auto-deploy to staging |
| Push code | `master` | production | ✅ **Required** | Deploy after approval |

### Manual Deployment

1. Go to **Actions** tab
2. Click **Kisan-Setu Deployment Pipeline**
3. Click **Run workflow**
4. Select:
   - Branch: Choose branch
   - Environment: Choose environment
5. Click **Run workflow**

### Production Deployment (Manual Approval)

When code is pushed to `master`:

1. Workflow starts automatically
2. Builds Lambda Layer
3. **Pauses at production deployment** ⏸️
4. **You receive notification** (if configured)
5. Go to Actions → Click workflow run
6. Click **Review deployments**
7. Select **production**
8. Click **Approve and deploy** ✅
9. Deployment proceeds
10. Production updated

---

## Troubleshooting

### Issue: GitHub Actions Not Triggering

**Check:**
1. Are secrets added? (Settings → Secrets and variables → Actions)
2. Are environments created? (Settings → Environments)
3. Are secret names exactly: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_ACCOUNT_ID`
4. Are environment names exactly: `development`, `staging`, `production`

**Fix:**
- Double-check spelling (case-sensitive!)
- Ensure no extra spaces in secret values
- Re-add secrets if needed

### Issue: WhatsApp Messages Not Processed

**Check:**
```bash
# 1. Secret exists
aws secretsmanager describe-secret \
  --secret-id kisan-setu/dev/whatsapp/credentials \
  --region ap-south-1

# 2. Lambda has permissions
aws lambda get-function \
  --function-name KisanSetuMVPStack-dev-MessageRouter8CD84FD1-1A5Q1R9pzkHF \
  --region ap-south-1

# 3. Check logs for errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/KisanSetuMVPStack-dev-MessageRouter8CD84FD1-1A5Q1R9pzkHF \
  --region ap-south-1 \
  --filter-pattern ERROR \
  --since 1h
```

### Issue: Deployment Fails in GitHub Actions

**Common causes:**
1. **IAM permissions**: User `github-actions-kisan-setu` needs AdministratorAccess
2. **CDK bootstrap**: May need to run `cdk bootstrap` in region
3. **Secrets incorrect**: Double-check AWS_SECRET_ACCESS_KEY
4. **Environment names**: Must be exactly `development`, `staging`, `production`

**View logs:**
- Go to Actions tab
- Click failed workflow run
- Expand failed step to see error

---

## Quick Commands Reference

```bash
# Check dev infrastructure
aws cloudformation describe-stacks \
  --stack-name KisanSetuMVPStack-dev \
  --region ap-south-1

# Check webhook
curl "https://chf0n7zrjd.execute-api.ap-south-1.amazonaws.com/prod/webhook?hub.mode=subscribe&hub.verify_token=kisan-setu-verify-2026&hub.challenge=test"

# View recent logs
aws logs tail /aws/lambda/KisanSetuMVPStack-dev-MessageRouter8CD84FD1-1A5Q1R9pzkHF \
  --region ap-south-1 \
  --since 10m

# Check DynamoDB items
aws dynamodb scan \
  --table-name dev-KisanSetuData \
  --region ap-south-1 \
  --limit 10

# Check S3 uploads
aws s3 ls s3://kisan-setu-dev-raw-682366718780/ --recursive

# List Lambda functions
aws lambda list-functions \
  --region ap-south-1 \
  --query 'Functions[?contains(FunctionName, `dev`)].FunctionName'
```

---

## Next Steps

After completing this setup:

1. ✅ Dev WhatsApp test number configured
2. ✅ GitHub Actions secrets added
3. ✅ GitHub environments created
4. ✅ Test complete flow in dev
5. ✅ Verify GitHub Actions deploy to dev
6. ✅ Merge dev → staging
7. ✅ Test staging deployment
8. ⏳ **Wait 15 days** (judging period)
9. ✅ Merge staging → master
10. ✅ Approve production deployment

---

## Summary Checklist

### Part 1: Dev WhatsApp Setup
- [ ] Get test number credentials from Meta
- [ ] Create AWS secret: `kisan-setu/dev/whatsapp/credentials`
- [ ] Configure webhook in Meta Business Suite
- [ ] Test: Send message to test number
- [ ] Verify: Check CloudWatch logs and DynamoDB

### Part 2: GitHub Actions Setup
- [ ] Add secret: `AWS_ACCESS_KEY_ID`
- [ ] Add secret: `AWS_SECRET_ACCESS_KEY`
- [ ] Add secret: `AWS_ACCOUNT_ID`
- [ ] Create environment: `development`
- [ ] Create environment: `staging`
- [ ] Create environment: `production` (with approval)
- [ ] Test: Push to dev branch
- [ ] Verify: Check Actions tab for deployment

### Part 3: Complete Testing
- [ ] Test text messages
- [ ] Test image uploads (ledgers)
- [ ] Test voice notes
- [ ] Test GraphQL sync
- [ ] Verify all data in DynamoDB
- [ ] Check S3 for uploaded files
- [ ] Review CloudWatch logs

**All done? Proceed to staging deployment! 🚀**

# Kisan-Setu Troubleshooting Guide

This guide covers common issues and their solutions when deploying and running Kisan-Setu.

## 🚨 Common Deployment Issues

### 1. boto3 Module Not Found in Lambda

**Symptom**: Lambda function fails with `ModuleNotFoundError: No module named 'boto3'`

**Cause**: Lambda package wasn't built with dependencies

**Solution**:
```bash
cd kisan-setu-mvp
./build_lambda_packages.sh
cdk deploy
```

---

### 2. Docker Not Running

**Symptom**: `Cannot connect to the Docker daemon`

**Solution**:
```bash
# macOS/Windows: Start Docker Desktop
# Linux:
sudo systemctl start docker

# Verify
docker info

# Then retry deployment
./deploy.sh
```

**Alternative**: Deploy without Docker (uses pip fallback)
```bash
./build_lambda_packages.sh  # Will use pip fallback
cdk deploy
```

---

### 3. CDK Bootstrap Required

**Symptom**: `This stack uses assets, so the toolkit stack must be deployed`

**Solution**:
```bash
cdk bootstrap aws://ACCOUNT-ID/ap-south-1
```

---

### 4. Lambda Permission Errors

**Symptom**: `User is not authorized to perform: lambda:InvokeFunction`

**Cause**: IAM permissions not properly configured

**Solution**:
```bash
# Redeploy to update IAM roles
./deploy_meta_whatsapp.sh
```

---

## 📱 WhatsApp Integration Issues

### 5. WhatsApp Messages Not Received

**Symptom**: Send message to WhatsApp number, no response

**Diagnosis Steps**:

1. **Check webhook is configured**:
   - Go to Meta Developer Console
   - WhatsApp → Configuration
   - Verify Callback URL is set
   - Verify Verify Token is `kisan-setu-verify-2026`

2. **Check webhook verification**:
```bash
# Get webhook URL
aws cloudformation describe-stacks \
  --stack-name KisanSetuMVPStack \
  --query "Stacks[0].Outputs[?OutputKey=='WebhookURL'].OutputValue" \
  --output text \
  --region ap-south-1

# Test webhook verification (should return challenge)
curl "YOUR_WEBHOOK_URL?hub.mode=subscribe&hub.verify_token=kisan-setu-verify-2026&hub.challenge=test123"
```

3. **Check Lambda logs**:
```bash
aws logs tail /aws/lambda/KisanSetuMVPStack-MessageRouter --follow --region ap-south-1
```

4. **Verify credentials in Secrets Manager**:
```bash
aws secretsmanager get-secret-value \
  --secret-id kisan-setu/whatsapp/credentials \
  --region ap-south-1 \
  --query SecretString \
  --output text
```

**Common Fixes**:
- Webhook URL mismatch → Update in Meta Console
- Wrong verify token → Should be `kisan-setu-verify-2026`
- Expired access token → Update in Secrets Manager
- Not subscribed to webhook fields → Subscribe to `messages` and `message_status`

---

### 6. WhatsApp Access Token Expired

**Symptom**: `Error code 190: Access token has expired`

**Cause**: Meta access tokens expire every 24 hours (temporary tokens) or 60 days (permanent tokens)

**Solution**:
```bash
# Get new token from Meta Developer Console
# Update Secrets Manager
aws secretsmanager update-secret \
  --secret-id kisan-setu/whatsapp/credentials \
  --secret-string '{"PHONE_NUMBER_ID":"1043444535519617","ACCESS_TOKEN":"NEW_TOKEN","VERIFY_TOKEN":"kisan-setu-verify-2026"}' \
  --region ap-south-1

# No need to redeploy - Lambda reads from Secrets Manager at runtime
```

---

### 7. Webhook Verification Fails

**Symptom**: Meta Console shows "Webhook verification failed"

**Cause**: Router Lambda not returning correct challenge response

**Solution**:
1. Check Lambda logs for errors
2. Verify Lambda has correct environment variable `WEBHOOK_VERIFY_TOKEN=kisan-setu-verify-2026`
3. Test manually:
```bash
curl "YOUR_WEBHOOK_URL?hub.mode=subscribe&hub.verify_token=kisan-setu-verify-2026&hub.challenge=test123"
# Should return: test123
```

---

## 🤖 Bedrock Issues

### 8. Bedrock Access Denied

**Symptom**: `AccessDeniedException: Could not access model`

**Cause**: Model access not enabled in Bedrock

**Solution**:
1. Go to AWS Console → Bedrock → Model access
2. Request access to:
   - Claude 3.5 Sonnet v2
   - Titan Embeddings G1 - Text
3. Wait for approval (5-30 minutes)
4. Check email for approval notification

---

### 9. Bedrock Agent Not Found

**Symptom**: `ResourceNotFoundException: Agent UUQPVM0ULJ not found`

**Cause**: Agent doesn't exist or wrong ID

**Solution**:

**Option 1**: System falls back to direct model calls (no action needed)

**Option 2**: Create the agent:
1. Go to AWS Console → Bedrock → Agents
2. Create new agent:
   - Name: Kisan-Setu Agent
   - Model: Claude 3.5 Sonnet v2
   - Instructions: "You are an agricultural assistant for Indian farmers"
3. Create alias
4. Update `infrastructure_stack.py` with new IDs
5. Redeploy

---

## 📄 Document Processing Issues

### 10. Textract Extraction Fails

**Symptom**: Image uploaded but no data extracted

**Diagnosis**:
```bash
# Check processor logs
aws logs tail /aws/lambda/KisanSetuMVPStack-DocumentProcessor --follow --region ap-south-1
```

**Common Causes**:
- Image too large (>5MB) → Compress image
- Image format not supported → Use JPG or PNG
- Poor image quality → Use better lighting/focus
- Textract quota exceeded → Check AWS quotas

---

### 11. Image Upload Timeout

**Symptom**: WhatsApp shows "Processing..." but never completes

**Cause**: Lambda timeout (60 seconds)

**Solution**:
- Image is too large → Compress before sending
- Textract is slow → Normal for complex documents, wait longer
- Check Lambda timeout in infrastructure_stack.py (currently 60s)

---

## 🗣️ Voice Processing Issues

### 12. Voice Transcription Fails

**Symptom**: Voice message sent but no transcription

**Diagnosis**:
```bash
# Check voice handler logs
aws logs tail /aws/lambda/KisanSetuMVPStack-VoiceHandler --follow --region ap-south-1
```

**Common Causes**:
- Audio format not supported → WhatsApp should send OGG/OPUS
- Audio too short (<1 second) → Record longer message
- Transcribe quota exceeded → Check AWS quotas
- Language not supported → Check Transcribe language support

---

## 🗄️ Database Issues

### 13. DynamoDB Table Not Found

**Symptom**: `ResourceNotFoundException: Table KisanSetuData not found`

**Cause**: Table wasn't created or wrong region

**Solution**:
```bash
# Check if table exists
aws dynamodb describe-table --table-name KisanSetuData --region ap-south-1

# If not found, create it (CDK should do this)
cdk deploy
```

---

### 14. DynamoDB Throttling

**Symptom**: `ProvisionedThroughputExceededException`

**Cause**: Too many requests (unlikely with on-demand pricing)

**Solution**:
- Check if table is in on-demand mode
- If provisioned mode, increase capacity
- Add exponential backoff in code (already implemented)

---

## 🧪 Testing Issues

### 15. Tests Fail with Import Errors

**Symptom**: `ModuleNotFoundError` when running pytest

**Solution**:
```bash
# Activate virtual environment
cd kisan-setu-mvp
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run tests
pytest tests/ -v
```

---

### 16. Integration Tests Fail

**Symptom**: Tests pass locally but fail in CI/CD

**Cause**: Missing AWS credentials or wrong region

**Solution**:
```bash
# Set AWS credentials in CI/CD environment
export AWS_ACCESS_KEY_ID=xxx
export AWS_SECRET_ACCESS_KEY=xxx
export AWS_DEFAULT_REGION=ap-south-1

# Or use --integration flag to skip integration tests
pytest tests/ -v -m "not integration"
```

---

## 🔐 Security Issues

### 17. Secrets Manager Access Denied

**Symptom**: `AccessDeniedException: User is not authorized to perform: secretsmanager:GetSecretValue`

**Cause**: Lambda role doesn't have permission

**Solution**:
```bash
# Redeploy to update IAM permissions
./deploy.sh
```

---

### 18. S3 Access Denied

**Symptom**: `AccessDeniedException: Access Denied` when uploading to S3

**Cause**: Lambda role doesn't have S3 permissions

**Solution**:
```bash
# Check bucket exists
aws s3 ls s3://kisan-setu-raw-ACCOUNT_ID --region ap-south-1

# Redeploy to update permissions
./deploy.sh
```

---

## 🌐 API Gateway Issues

### 19. API Gateway 502 Bad Gateway

**Symptom**: Webhook returns 502 error

**Cause**: Lambda function crashed or timed out

**Solution**:
1. Check Lambda logs for errors
2. Increase Lambda timeout if needed
3. Check Lambda memory usage
4. Verify Lambda has correct handler configured

---

### 20. API Gateway 403 Forbidden

**Symptom**: Webhook returns 403 error

**Cause**: API Gateway resource policy or Lambda permission issue

**Solution**:
```bash
# Redeploy to fix permissions
cdk deploy
```

---

## 📊 Monitoring & Debugging

### Check All Lambda Functions

```bash
# List all functions
aws lambda list-functions \
  --query "Functions[?contains(FunctionName, 'KisanSetu')].FunctionName" \
  --region ap-south-1

# Check specific function
aws lambda get-function \
  --function-name FUNCTION_NAME \
  --region ap-south-1
```

### Monitor Logs in Real-Time

```bash
# Router (webhook handler)
aws logs tail /aws/lambda/KisanSetuMVPStack-MessageRouter --follow --region ap-south-1

# Orchestrator (AI responses)
aws logs tail /aws/lambda/KisanSetuMVPStack-BedrockOrchestrator --follow --region ap-south-1

# Document Processor
aws logs tail /aws/lambda/KisanSetuMVPStack-DocumentProcessor --follow --region ap-south-1

# Voice Handler
aws logs tail /aws/lambda/KisanSetuMVPStack-VoiceHandler --follow --region ap-south-1
```

### Check CloudWatch Metrics

```bash
# Lambda invocations
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=KisanSetuMVPStack-MessageRouter \
  --start-time 2026-03-07T00:00:00Z \
  --end-time 2026-03-07T23:59:59Z \
  --period 3600 \
  --statistics Sum \
  --region ap-south-1

# Lambda errors
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Errors \
  --dimensions Name=FunctionName,Value=KisanSetuMVPStack-MessageRouter \
  --start-time 2026-03-07T00:00:00Z \
  --end-time 2026-03-07T23:59:59Z \
  --period 3600 \
  --statistics Sum \
  --region ap-south-1
```

---

## 🔄 Recovery Procedures

### Complete Redeployment

If everything is broken:
```bash
cd kisan-setu-mvp

# 1. Clean build
rm -rf lambda/*/bin lambda/*/lib lambda/*/*.dist-info

# 2. Rebuild packages
./build_lambda_packages.sh

# 3. Redeploy
cdk deploy --require-approval never

# 4. Reconfigure webhook in Meta Console
```

### Reset WhatsApp Credentials

```bash
# Update credentials
aws secretsmanager update-secret \
  --secret-id kisan-setu/whatsapp/credentials \
  --secret-string '{"PHONE_NUMBER_ID":"1043444535519617","ACCESS_TOKEN":"NEW_TOKEN","VERIFY_TOKEN":"kisan-setu-verify-2026"}' \
  --region ap-south-1

# Test
curl "YOUR_WEBHOOK_URL?hub.mode=subscribe&hub.verify_token=kisan-setu-verify-2026&hub.challenge=test"
```

---

## 📞 Getting Help

### Check Logs First
Always check CloudWatch logs before asking for help. They contain detailed error messages.

### Useful Commands
```bash
# Get stack outputs
aws cloudformation describe-stacks \
  --stack-name KisanSetuMVPStack \
  --region ap-south-1

# Check Lambda environment variables
aws lambda get-function-configuration \
  --function-name FUNCTION_NAME \
  --region ap-south-1

# Test Lambda directly
aws lambda invoke \
  --function-name KisanSetuMVPStack-MessageRouter \
  --payload '{"test": "data"}' \
  response.json \
  --region ap-south-1
```

### Documentation References
- Main README: `kisan-setu-mvp/README.md`
- Implementation Status: `IMPLEMENTATION_STATUS_AND_TASKS.md`
- Deployment Scripts: `kisan-setu-mvp/DEPLOYMENT_SCRIPTS.md`
- Testing Guide: `kisan-setu-mvp/tests/TESTING-GUIDE.md`

---

## 🎯 Quick Fixes Checklist

When something doesn't work, try these in order:

- [ ] Check CloudWatch logs for errors
- [ ] Verify AWS credentials are configured
- [ ] Verify webhook URL matches deployment
- [ ] Verify WhatsApp credentials in Secrets Manager
- [ ] Verify Bedrock model access is enabled
- [ ] Redeploy: `./deploy.sh`
- [ ] Test with simple message: "Hello"
- [ ] Check all Lambda functions are deployed
- [ ] Verify API Gateway endpoint is accessible
- [ ] Check DynamoDB table exists

---

**Last Updated**: March 2026

# Dev Environment Testing Checklist

**Date**: _________
**Tester**: _________
**Start Time**: _________
**End Time**: _________

---

## Pre-Testing Setup (5 minutes)

### 1. Verify Dev Webhook is Working
```bash
curl "https://chf0n7zrjd.execute-api.ap-south-1.amazonaws.com/prod/webhook?hub.mode=subscribe&hub.verify_token=kisan-setu-verify-2026&hub.challenge=test123"
```
- [ ] **Expected**: Returns `test123`
- [ ] **Actual**: __________

### 2. Backup Production Webhook URL
```bash
echo "Production webhook: <YOUR_PROD_WEBHOOK_URL>" > /tmp/webhook-backup.txt
cat /tmp/webhook-backup.txt
```
- [ ] **Production Webhook URL**: _________________________________
- [ ] **Saved to file**: Yes / No

### 3. Optional: Backup Production Database
```bash
aws dynamodb create-backup \
  --table-name KisanSetuData \
  --backup-name "pre-dev-testing-$(date +%Y%m%d-%H%M%S)"
```
- [ ] **Backup created**: Yes / No / Skipped
- [ ] **Backup ARN**: _________________________________

---

## Switch to Dev Webhook (2 minutes)

### 4. Update Meta WhatsApp Configuration
1. [ ] Go to [Meta Business Suite](https://business.facebook.com/)
2. [ ] Navigate to: **WhatsApp** → **Configuration** → **Webhook**
3. [ ] Click **Edit** webhook URL
4. [ ] Enter: `https://chf0n7zrjd.execute-api.ap-south-1.amazonaws.com/prod/webhook`
5. [ ] Enter Verify Token: `kisan-setu-verify-2026`
6. [ ] Subscribe to message events
7. [ ] Click **Save**
8. [ ] **Verification successful**: Yes / No
9. [ ] **Time switched**: __________

---

## Testing Phase (30-60 minutes)

### 5. Test Text Messages
- [ ] Send a simple text message: "Hello"
- [ ] Check CloudWatch logs:
  ```bash
  aws logs tail /aws/lambda/dev-MessageRouter --follow
  ```
- [ ] Verify message in DynamoDB:
  ```bash
  aws dynamodb scan --table-name dev-KisanSetuData --max-items 5
  ```
- [ ] **Status**: ✅ Pass / ❌ Fail
- [ ] **Notes**: _________________________________

### 6. Test Document Processing (Upload Ledger Image)
- [ ] Upload a document image (e.g., ledger photo)
- [ ] Check S3 raw bucket:
  ```bash
  aws s3 ls s3://dev-kisan-setu-raw-682366718780/ --recursive | tail -5
  ```
- [ ] Check CloudWatch logs for processor:
  ```bash
  aws logs tail /aws/lambda/dev-DocumentProcessor --follow
  ```
- [ ] Verify processed document in S3:
  ```bash
  aws s3 ls s3://dev-kisan-setu-processed-682366718780/ --recursive | tail -5
  ```
- [ ] **Status**: ✅ Pass / ❌ Fail
- [ ] **Notes**: _________________________________

### 7. Test Voice Messages
- [ ] Send a voice message
- [ ] Check CloudWatch logs:
  ```bash
  aws logs tail /aws/lambda/dev-VoiceHandler --follow
  ```
- [ ] Verify transcription response received
- [ ] **Status**: ✅ Pass / ❌ Fail
- [ ] **Notes**: _________________________________

### 8. Test Credit Score Calculation
- [ ] Send message: "What is my credit score?"
- [ ] Check orchestrator logs:
  ```bash
  aws logs tail /aws/lambda/dev-BedrockOrchestrator --follow
  ```
- [ ] Check credit calculator logs:
  ```bash
  aws logs tail /aws/lambda/dev-CreditCalculator --follow
  ```
- [ ] Verify credit score response received
- [ ] **Status**: ✅ Pass / ❌ Fail
- [ ] **Notes**: _________________________________

### 9. Test Knowledge Base Query
- [ ] Send message: "How do I apply for a loan?"
- [ ] Check knowledge base logs:
  ```bash
  aws logs tail /aws/lambda/dev-KnowledgeBase --follow
  ```
- [ ] Verify helpful response received
- [ ] **Status**: ✅ Pass / ❌ Fail
- [ ] **Notes**: _________________________________

### 10. Test Satellite Imagery Request
- [ ] Send message: "Show me satellite image of my farm" (with GPS location)
- [ ] Check satellite analyzer logs:
  ```bash
  aws logs tail /aws/lambda/dev-SatelliteAnalyzer --follow
  ```
- [ ] Verify NDVI response received
- [ ] **Status**: ✅ Pass / ❌ Fail
- [ ] **Notes**: _________________________________

### 11. Verify Data Isolation
- [ ] Check production DynamoDB is untouched:
  ```bash
  aws dynamodb describe-table --table-name KisanSetuData --query 'Table.ItemCount'
  ```
- [ ] Check production CloudWatch logs are silent:
  ```bash
  aws logs tail /aws/lambda/MessageRouter --since 30m
  ```
- [ ] **Production unchanged**: ✅ Yes / ❌ No
- [ ] **Notes**: _________________________________

---

## Restore Production Webhook (2 minutes) ⚠️ CRITICAL

### 12. Switch Back to Production
1. [ ] Go to [Meta Business Suite](https://business.facebook.com/)
2. [ ] Navigate to: **WhatsApp** → **Configuration** → **Webhook**
3. [ ] Click **Edit** webhook URL
4. [ ] Restore production URL from backup:
   ```bash
   cat /tmp/webhook-backup.txt
   ```
5. [ ] Enter production webhook URL: _________________________________
6. [ ] Enter production verify token
7. [ ] Subscribe to message events
8. [ ] Click **Save**
9. [ ] **Time restored**: __________

### 13. Verify Production is Working
- [ ] Send test message to production number
- [ ] Check production CloudWatch logs:
  ```bash
  aws logs tail /aws/lambda/MessageRouter --follow
  ```
- [ ] Verify message processed correctly
- [ ] **Production working**: ✅ Yes / ❌ No
- [ ] **Notes**: _________________________________

---

## Post-Testing Analysis

### 14. Review Dev Environment Data
- [ ] Total messages in dev DynamoDB:
  ```bash
  aws dynamodb scan --table-name dev-KisanSetuData --select COUNT
  ```
- [ ] Total files in dev S3:
  ```bash
  aws s3 ls s3://dev-kisan-setu-raw-682366718780/ --recursive | wc -l
  ```
- [ ] **Total test messages**: __________
- [ ] **Total files uploaded**: __________

### 15. Check for Errors
- [ ] Review CloudWatch Insights for errors:
  ```bash
  # Check for errors in last hour
  aws logs filter-log-events \
    --log-group-name /aws/lambda/dev-MessageRouter \
    --filter-pattern "ERROR" \
    --start-time $(($(date +%s) - 3600))000
  ```
- [ ] **Errors found**: Yes / No
- [ ] **Error count**: __________
- [ ] **Critical errors**: _________________________________

---

## Summary

### Overall Test Results
- [ ] **All tests passed**: Yes / No
- [ ] **Tests passed**: _____ / 10
- [ ] **Total testing duration**: _____ minutes
- [ ] **Production downtime**: _____ minutes
- [ ] **Issues found**: _________________________________

### Next Steps
- [ ] Fix any issues found in dev
- [ ] Update test documentation
- [ ] Ready to deploy to staging: Yes / No
- [ ] **Notes**: _________________________________

---

## Emergency Rollback Procedure

If something goes wrong:

1. **Immediately restore production webhook** (see Step 12 above)
2. **Verify production is working** (see Step 13 above)
3. **Document the issue** in Notes section
4. **Contact team** if production is affected

**Emergency Production Webhook URL**: _________________________________

---

## Sign-off

**Tester Signature**: _________________________________
**Date**: _________________________________
**Ready for Staging**: ✅ Yes / ❌ No

---

## Quick Reference Commands

### Monitor All Lambdas
```bash
# Terminal 1: Router
aws logs tail /aws/lambda/dev-MessageRouter --follow

# Terminal 2: Orchestrator
aws logs tail /aws/lambda/dev-BedrockOrchestrator --follow

# Terminal 3: Processor
aws logs tail /aws/lambda/dev-DocumentProcessor --follow
```

### Check DynamoDB
```bash
# Count items
aws dynamodb scan --table-name dev-KisanSetuData --select COUNT

# View recent items
aws dynamodb scan --table-name dev-KisanSetuData --max-items 5
```

### Check S3 Buckets
```bash
# Raw uploads
aws s3 ls s3://dev-kisan-setu-raw-682366718780/ --recursive | tail -10

# Processed documents
aws s3 ls s3://dev-kisan-setu-processed-682366718780/ --recursive | tail -10
```

### Webhook URLs
- **Dev**: `https://chf0n7zrjd.execute-api.ap-south-1.amazonaws.com/prod/webhook`
- **Production**: _________________________________

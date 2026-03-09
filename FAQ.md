# Kisan-Setu Frequently Asked Questions (FAQ)

## 🚀 Getting Started

### Q: What is Kisan-Setu?
**A**: Kisan-Setu is a WhatsApp-based agricultural assistant for Indian farmers. It uses AWS Bedrock (Claude AI), Textract for document digitization, and provides features like credit scoring, satellite crop analysis, and voice support in multiple Indian languages.

### Q: What do I need to get started?
**A**: You need:
- AWS Account with Bedrock access
- Meta WhatsApp Business Account
- Python 3.11+
- Node.js 18+ (for CDK)
- AWS CLI configured
- Docker (optional, but recommended)

### Q: How long does setup take?
**A**: 
- Code deployment: 5 minutes
- WhatsApp webhook configuration: 15 minutes
- Testing: 10 minutes
- **Total: ~30 minutes** (assuming you have AWS and Meta accounts ready)

### Q: Do I need to write any code?
**A**: No! All code is already implemented. You only need to:
1. Deploy the infrastructure
2. Configure WhatsApp webhook
3. Test

---

## 💰 Cost & Pricing

### Q: How much does it cost to run?
**A**: For 1000 farmers with 10K messages/month:
- Lambda: $5-10
- Textract: $5-10
- Bedrock: $20-30
- DynamoDB: $2-5
- S3: $1-2
- Other services: $5-10
- **Total: ~$45-80/month**

### Q: Is there a free tier?
**A**: Yes! AWS Free Tier includes:
- Lambda: 1M requests/month free
- DynamoDB: 25GB storage free
- S3: 5GB storage free
- Bedrock: Pay per use (no free tier)

For small-scale testing, you might stay within free tier limits.

### Q: What's the most expensive component?
**A**: Bedrock (Claude AI) is typically the most expensive at $20-30/month for moderate usage. You can reduce costs by:
- Caching common responses
- Using shorter prompts
- Implementing rate limiting

---

## 📱 WhatsApp Integration

### Q: Do I need a WhatsApp Business Account?
**A**: Yes, you need a Meta WhatsApp Business Account. You can create one for free at https://developers.facebook.com/

### Q: Can I use my personal WhatsApp number?
**A**: No, you need a separate business phone number. Meta provides a test number for development.

### Q: How do I get a WhatsApp access token?
**A**: 
1. Go to Meta Developer Console
2. Create an app → Add WhatsApp product
3. Go to WhatsApp → Getting Started
4. Copy the temporary access token (expires in 24 hours)
5. For production, generate a permanent token (expires in 60 days)

### Q: Why does my access token expire?
**A**: 
- Temporary tokens: Expire in 24 hours (for testing)
- Permanent tokens: Expire in 60 days (for production)
- System access tokens: Never expire (requires business verification)

To update expired token:
```bash
aws secretsmanager update-secret \
  --secret-id kisan-setu/whatsapp/credentials \
  --secret-string '{"PHONE_NUMBER_ID":"xxx","ACCESS_TOKEN":"NEW_TOKEN","VERIFY_TOKEN":"kisan-setu-verify-2026"}' \
  --region ap-south-1
```

### Q: Can farmers use any WhatsApp account?
**A**: Yes! Farmers can message your business number from any personal WhatsApp account. No app installation needed.

### Q: What message types are supported?
**A**: 
- ✅ Text messages
- ✅ Images (ledgers, receipts)
- ✅ Voice messages
- ✅ Location sharing
- ❌ Videos (not implemented)
- ❌ Documents (not implemented)

---

## 🤖 AI & Bedrock

### Q: What AI model is used?
**A**: The system uses a 5-model fallback chain via AWS Bedrock's Converse API with APAC inference profiles:

1. **Amazon Nova Pro** (primary — available without Marketplace subscription)
2. **Amazon Nova Lite** (fast, cheap fallback)
3. **Claude 3.7 Sonnet** (requires AWS Marketplace subscription)
4. **Claude 3.5 Sonnet v2** (requires AWS Marketplace subscription)
5. **Claude 3 Haiku** (requires AWS Marketplace subscription)

For multimodal (image) processing, the chain is: Claude 3.7 Sonnet → Claude 3.5 Sonnet v2 → Nova Pro → Claude 3 Haiku → Nova Lite.

Each model has a circuit breaker (3 failures → 60s cooldown) and exponential backoff retries. If one model is throttled or unavailable, the system automatically tries the next.

### Q: Do I need to create a Bedrock Agent?
**A**: No, it's optional. The system works in two modes:
1. **With Agent**: Full tool integration (credit scoring, satellite analysis, etc.)
2. **Without Agent**: Direct model calls (still works, just fewer features)

If agent doesn't exist, system automatically falls back to direct model calls.

### Q: How do I enable Bedrock model access?
**A**: 
1. Go to AWS Console → Bedrock → Model access
2. Click "Manage model access"
3. Select all models used in the fallback chain:
   - Amazon Nova Pro
   - Amazon Nova Lite
   - Claude 3.7 Sonnet (requires APAC inference profile)
   - Claude 3.5 Sonnet v2 (requires APAC inference profile)
   - Claude 3 Haiku (requires APAC inference profile)
   - Titan Embeddings G1 - Text
4. Click "Request model access"
5. Wait 5-30 minutes for approval

### Q: What languages are supported?
**A**: Currently:
- English (en)
- Hindi (hi-IN)
- Marathi (mr-IN)
- Tamil (ta-IN)

Easy to add more languages by updating the language mappings in the code.

### Q: Can I use a different AI model?
**A**: Yes! You can modify `orchestrator.py` to use:
- Different Claude versions
- Other Bedrock models (Llama, Mistral, etc.)
- OpenAI (requires code changes)

---

## 📄 Document Processing

### Q: What types of documents can be processed?
**A**: 
- Handwritten ledgers
- Printed receipts
- Bills
- Invoices
- Any document with text

### Q: What's the accuracy of text extraction?
**A**: AWS Textract achieves ~98.4% accuracy on:
- Printed text: 99%+
- Handwritten text: 95-98%
- Tables: 95%+

Accuracy depends on image quality.

### Q: What image formats are supported?
**A**: 
- JPG/JPEG
- PNG
- PDF (single page)

### Q: What's the maximum image size?
**A**: 
- WhatsApp limit: 5MB
- Textract limit: 10MB
- Recommended: <2MB for faster processing

### Q: How long does processing take?
**A**: 
- Simple document: 2-5 seconds
- Complex ledger: 5-10 seconds
- Large image: 10-20 seconds

---

## 🗣️ Voice Processing

### Q: What languages can be transcribed?
**A**: Amazon Transcribe supports 30+ languages including:
- Hindi
- English
- Tamil
- Telugu
- Marathi
- Bengali
- And more

### Q: How accurate is voice transcription?
**A**: 
- Clear audio: 90-95% accuracy
- Noisy audio: 70-85% accuracy
- Accented speech: 80-90% accuracy

### Q: What audio formats are supported?
**A**: WhatsApp sends voice messages in OGG/OPUS format, which is automatically supported.

### Q: Is there a duration limit?
**A**: 
- WhatsApp limit: 16 minutes
- Transcribe limit: 4 hours
- Recommended: <2 minutes for faster processing

---

## 🛰️ Satellite Analysis

### Q: What satellite data is used?
**A**: AWS SageMaker Geospatial uses:
- Sentinel-2 (10m resolution)
- Landsat 8 (30m resolution)
- MODIS (250m resolution)

### Q: How often is satellite data updated?
**A**: 
- Sentinel-2: Every 5 days
- Landsat 8: Every 16 days
- MODIS: Daily

### Q: What can satellite analysis detect?
**A**: 
- Crop health (NDVI)
- Vegetation coverage
- Water stress
- Yield predictions
- Field boundaries

### Q: Is satellite analysis free?
**A**: SageMaker Geospatial charges per query:
- ~$0.10-0.50 per analysis
- Depends on area size and resolution

---

## 💳 Credit Scoring

### Q: How is credit score calculated?
**A**: Based on:
- Transaction history (40%)
- Payment regularity (30%)
- Crop diversity (15%)
- Land size (10%)
- Other factors (5%)

### Q: What's a good credit score?
**A**: 
- 750-850: Excellent
- 650-749: Good
- 550-649: Fair
- Below 550: Poor

### Q: Can farmers see their credit score?
**A**: Yes! They can ask via WhatsApp:
- "What is my credit score?"
- "मेरा क्रेडिट स्कोर क्या है?"

---

## 🗄️ Data Storage

### Q: Where is data stored?
**A**: 
- Farmer profiles: DynamoDB
- Images: S3 (encrypted)
- Transactions: DynamoDB
- Logs: CloudWatch

### Q: Is data encrypted?
**A**: Yes!
- At rest: AES-256 encryption
- In transit: TLS 1.2+
- Secrets: AWS Secrets Manager

### Q: How long is data retained?
**A**: 
- Active data: Indefinitely
- Archived images: 90 days (configurable)
- Logs: 30 days (configurable)

### Q: Can data be deleted?
**A**: Yes, you can implement GDPR-compliant deletion by:
1. Deleting DynamoDB records
2. Deleting S3 objects
3. Removing from backups

---

## 🧪 Testing

### Q: How do I test without sending real WhatsApp messages?
**A**: 
1. Use pytest integration tests:
```bash
pytest tests/ -v
```

2. Invoke Lambda directly:
```bash
aws lambda invoke \
  --function-name KisanSetuMVPStack-MessageRouter \
  --payload file://test-event.json \
  response.json
```

3. Use Meta's test phone number

### Q: What tests are included?
**A**: 
- Unit tests: 30+ files
- Integration tests: 15+ files
- Property-based tests: 10+ files
- Bug fix verification tests
- Total: 50+ test files

### Q: How do I run tests?
**A**: 
```bash
cd kisan-setu-mvp
source .venv/bin/activate
pytest tests/ -v
```

---

## 🔧 Deployment

### Q: Which deployment script should I use?
**A**: 
- **First time**: `./deploy_meta_whatsapp.sh` (includes WhatsApp setup)
- **Regular updates**: `./deploy.sh` (automated build + deploy)
- **Manual control**: `./build_lambda_packages.sh` then `cdk deploy`

### Q: Do I need Docker?
**A**: No, but recommended. Without Docker:
- May have dependency compatibility issues
- Slower builds
- Less reliable

With Docker:
- Guaranteed Linux-compatible dependencies
- Faster builds (after first time)
- Matches Lambda runtime exactly

### Q: How long does deployment take?
**A**: 
- First deployment: 3-5 minutes
- Subsequent deployments: 1-2 minutes
- With Docker (first time): 5-7 minutes

### Q: Can I deploy to multiple regions?
**A**: Yes, but you need to:
1. Update `cdk.json` with target region
2. Bootstrap CDK in that region
3. Deploy
4. Update WhatsApp webhook URL

Currently configured for: `ap-south-1` (Mumbai)

---

## 🐛 Troubleshooting

### Q: Messages sent but no response?
**A**: Check in order:
1. CloudWatch logs for errors
2. Webhook configured in Meta Console
3. WhatsApp credentials in Secrets Manager
4. Lambda functions are deployed
5. API Gateway endpoint is accessible

See `TROUBLESHOOTING.md` for detailed solutions.

### Q: How do I check logs?
**A**: 
```bash
# Router logs
aws logs tail /aws/lambda/KisanSetuMVPStack-MessageRouter --follow --region ap-south-1

# Orchestrator logs
aws logs tail /aws/lambda/KisanSetuMVPStack-BedrockOrchestrator --follow --region ap-south-1
```

### Q: Lambda function not found?
**A**: 
```bash
# List all functions
aws lambda list-functions \
  --query "Functions[?contains(FunctionName, 'KisanSetu')].FunctionName" \
  --region ap-south-1

# If empty, redeploy
./deploy.sh
```

---

## 🔐 Security

### Q: Is the system secure?
**A**: Yes! Security features:
- IAM roles with least privilege
- Encrypted data at rest and in transit
- Secrets stored in AWS Secrets Manager
- VPC isolation (optional)
- CloudWatch monitoring
- SNS alerts for critical errors

### Q: How are WhatsApp credentials stored?
**A**: In AWS Secrets Manager with:
- Automatic encryption
- Access logging
- IAM-based access control
- Rotation support

### Q: Can I enable MFA?
**A**: Yes, enable MFA on:
- AWS root account
- IAM users
- Meta Developer account

### Q: What about PII (Personally Identifiable Information)?
**A**: 
- Phone numbers are hashed
- Names are encrypted
- GPS coordinates are anonymized
- Comply with local data protection laws

---

## 📊 Monitoring

### Q: How do I monitor system health?
**A**: 
1. CloudWatch Dashboards (create custom)
2. CloudWatch Alarms (set up for errors)
3. SNS alerts (already configured)
4. Lambda metrics (invocations, errors, duration)

### Q: What metrics should I track?
**A**: 
- Lambda invocations
- Lambda errors
- Lambda duration
- API Gateway requests
- DynamoDB read/write capacity
- Bedrock token usage
- S3 storage size

### Q: How do I set up alerts?
**A**: 
```bash
# Already configured: SNS topic for critical errors
# Add email subscription:
aws sns subscribe \
  --topic-arn arn:aws:sns:ap-south-1:ACCOUNT_ID:kisan-setu-critical-alerts \
  --protocol email \
  --notification-endpoint your-email@example.com
```

---

## 🚀 Production Readiness

### Q: Is this production-ready?
**A**: Yes, but consider:
- ✅ All core features implemented
- ✅ Error handling and logging
- ✅ Security best practices
- ✅ Comprehensive tests
- ⚠️ Need to set up monitoring dashboards
- ⚠️ Need to configure backup strategy
- ⚠️ Need to set up CI/CD pipeline

### Q: What's missing for production?
**A**: 
1. ~~Admin dashboard~~ ✅ Now implemented (S3-hosted static dashboard with live message feed, credit charts, NDVI map, ledger preview)
2. Monitoring dashboards
3. Backup and disaster recovery
4. Load testing
5. Performance optimization
6. Cost optimization
7. Documentation for farmers

### Q: How many users can it handle?
**A**: 
- Current setup: 1000-5000 farmers
- With optimization: 10,000-50,000 farmers
- With scaling: 100,000+ farmers

Bottlenecks:
- Bedrock rate limits (can request increase)
- Lambda concurrency (default 1000, can increase)
- DynamoDB throughput (on-demand scales automatically)

---

## 📚 Additional Resources

### Q: Where can I find more documentation?
**A**: 
- Main README: `kisan-setu-mvp/README.md`
- Implementation Status: `IMPLEMENTATION_STATUS_AND_TASKS.md`
- Troubleshooting: `TROUBLESHOOTING.md`
- Deployment Scripts: `kisan-setu-mvp/DEPLOYMENT_SCRIPTS.md`
- Testing Guide: `kisan-setu-mvp/tests/TESTING-GUIDE.md`
- Design Docs: `.kiro/specs/kisan-setu/`

### Q: How do I contribute?
**A**: 
1. Fork the repository
2. Create a feature branch
3. Make changes
4. Run tests: `pytest tests/ -v`
5. Submit pull request

### Q: Where can I get help?
**A**: 
1. Check `TROUBLESHOOTING.md`
2. Check CloudWatch logs
3. Review AWS documentation
4. Check Meta WhatsApp documentation

---

**Last Updated**: March 2026

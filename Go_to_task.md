# Personal Go-To Task List

## 🎯 Current Status
All code is implemented. Only configuration needed to make it work.

## ⚡ Quick Start (30 minutes to working system)

### 1. Deploy Infrastructure (5 min)
```bash
cd kisan-setu-mvp
./deploy_meta_whatsapp.sh
```

### 2. Configure WhatsApp Webhook (15 min)

Get webhook URL:
```bash
aws cloudformation describe-stacks \
  --stack-name KisanSetuMVPStack \
  --query "Stacks[0].Outputs[?OutputKey=='WebhookURL'].OutputValue" \
  --output text \
  --region ap-south-1
```

Then:
1. Go to Meta Developer Console
2. WhatsApp → Configuration
3. Set Callback URL (from above)
4. Set Verify Token: `kisan-setu-verify-2026`
5. Subscribe to: messages, message_status

### 3. Test (10 min)

Monitor logs:
```bash
aws logs tail /aws/lambda/KisanSetuMVPStack-MessageRouter --follow --region ap-south-1
```

Send "Hello" to your WhatsApp Business number.

## 📋 Detailed Tasks

See `IMPLEMENTATION_STATUS_AND_TASKS.md` for complete task breakdown.

## 🔗 Important Links

- **Meta Developer Console**: https://developers.facebook.com/
- **AWS Console (ap-south-1)**: https://ap-south-1.console.aws.amazon.com/
- **Bedrock Console**: https://ap-south-1.console.aws.amazon.com/bedrock/

## 📝 Credentials

**WhatsApp Credentials** (in AWS Secrets Manager):
- Secret Name: `kisan-setu/whatsapp/credentials`
- Phone Number ID: 1043444535519617
- Verify Token: `kisan-setu-verify-2026`

**Bedrock Agent**:
- Agent ID: UUQPVM0ULJ
- Agent Alias ID: A2TGFPMFXZ
- (May need to verify/create)

## 🐛 Troubleshooting

### No response from WhatsApp?
1. Check CloudWatch logs for errors
2. Verify webhook is configured in Meta Console
3. Verify Secrets Manager has credentials
4. Check webhook URL matches deployment

### Lambda errors?
```bash
# List all functions
aws lambda list-functions --query "Functions[?contains(FunctionName, 'KisanSetu')].FunctionName" --region ap-south-1

# Check specific function logs
aws logs tail /aws/lambda/FUNCTION_NAME --follow --region ap-south-1
```

### Bedrock errors?
- Verify model access is enabled in Bedrock console
- Check if agent exists (may need to create)
- System will fall back to direct model calls if agent missing

## ✅ Success Checklist

- [ ] Infrastructure deployed
- [ ] Webhook configured in Meta Console
- [ ] Test message sent and received response
- [ ] Image upload tested
- [ ] Voice message tested
- [ ] Error handling tested

## 📚 Documentation

- Main README: `kisan-setu-mvp/README.md`
- Implementation Status: `IMPLEMENTATION_STATUS_AND_TASKS.md`
- Spec Files: `.kiro/specs/kisan-setu/`

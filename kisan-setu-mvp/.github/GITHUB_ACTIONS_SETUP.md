# GitHub Actions Setup Guide

This guide explains how to configure GitHub Actions for automated deployment of the Kisan-Setu MVP across multiple environments.

## Overview

We have two GitHub Actions workflows:

1. **`test.yml`** - Runs on every push/PR to `dev`, `staging`, or `master`
   - Unit tests
   - Property-based tests
   - Integration tests (with LocalStack)
   - Code quality checks
   - Security scanning

2. **`deploy.yml`** - Deploys to AWS environments based on branch
   - `dev` branch → Development environment
   - `staging` branch → Staging environment
   - `master` branch → Production environment (with manual approval)

## Required GitHub Secrets

You must configure the following secrets in your GitHub repository settings:

### AWS Credentials

Navigate to: **Repository Settings → Secrets and variables → Actions → New repository secret**

| Secret Name | Description | How to Get |
|-------------|-------------|------------|
| `AWS_ACCESS_KEY_ID` | AWS IAM Access Key ID | Create IAM user with deployment permissions |
| `AWS_SECRET_ACCESS_KEY` | AWS IAM Secret Access Key | From IAM user creation |
| `AWS_ACCOUNT_ID` | Your AWS Account ID | Found in AWS Console (top-right menu) |

### Creating IAM User for GitHub Actions

1. Go to AWS IAM Console → Users → Create User
2. User name: `github-actions-kisan-setu`
3. Attach policies:
   - `AdministratorAccess` (for full CDK deployment capabilities)
   - OR create a custom policy with minimum permissions (see below)
4. Create access key → CLI access → Copy Access Key ID and Secret Access Key
5. Add these to GitHub Secrets

### Minimum IAM Permissions (Recommended for Production)

Instead of `AdministratorAccess`, create a custom policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cloudformation:*",
        "lambda:*",
        "dynamodb:*",
        "s3:*",
        "iam:*",
        "apigateway:*",
        "appsync:*",
        "cognito-idp:*",
        "sns:*",
        "kms:*",
        "cloudfront:*",
        "cloudwatch:*",
        "logs:*"
      ],
      "Resource": "*"
    }
  ]
}
```

## GitHub Environment Protection Rules

### Setting Up Environment Protection

1. Go to **Repository Settings → Environments**
2. Create three environments:

#### 1. Development Environment
- Name: `development`
- Protection rules: None (auto-deploy on push to `dev`)
- URL: Your dev CloudFront URL (from CDK outputs)

#### 2. Staging Environment
- Name: `staging`
- Protection rules:
  - ✅ Required reviewers: 1 (optional)
- URL: Your staging CloudFront URL

#### 3. Production Environment
- Name: `production`
- Protection rules:
  - ✅ **Required reviewers**: At least 1-2 people
  - ✅ **Wait timer**: 5 minutes (optional)
  - Deployment branch: Only `master`
- URL: Your production CloudFront URL

### How Manual Approval Works

When code is pushed to `master`:

1. GitHub Actions triggers the `deploy-prod` job
2. The workflow **pauses** and waits for approval
3. Designated reviewers receive a notification
4. Reviewer must manually approve the deployment
5. Only after approval does the deployment proceed

## Workflow Triggers

### Automatic Deployments

| Branch | Environment | Trigger | Approval Required |
|--------|-------------|---------|-------------------|
| `dev` | Development | Push to dev | ❌ No |
| `staging` | Staging | Push to staging | ⚠️ Optional |
| `master` | Production | Push to master | ✅ **Yes** |

### Manual Deployments

You can also trigger deployments manually:

1. Go to **Actions** tab in GitHub
2. Select **Kisan-Setu Deployment Pipeline**
3. Click **Run workflow**
4. Select branch and environment
5. Click **Run workflow**

## Deployment Flow

### Dev Deployment (Automatic)
```
Push to dev → Build Layer → Deploy to Dev → ✅ Complete
```

### Staging Deployment (Automatic)
```
Push to staging → Build Layer → Deploy to Staging → ✅ Complete
```

### Production Deployment (Manual Approval)
```
Push to master → Build Layer → ⏸️ Wait for Approval
                               ↓
                          [Reviewer Approves]
                               ↓
                    Backup Production → Deploy to Prod → ✅ Complete
```

## Monitoring Deployments

### View Workflow Status

1. Go to **Actions** tab in GitHub repository
2. See all workflow runs with status indicators
3. Click on a run to see detailed logs

### CloudFormation Status

Each deployment step verifies the CloudFormation stack status:

- `CREATE_COMPLETE` - Initial deployment successful
- `UPDATE_COMPLETE` - Update deployment successful
- `ROLLBACK_COMPLETE` - Deployment failed and rolled back

### Lambda Layer Verification

After deployment, verify Lambda Layer is attached:

```bash
# Check dev environment
aws lambda get-function-configuration \
  --function-name <dev-function-name> \
  --region ap-south-1 \
  --query 'Layers[*].Arn'

# Should show: arn:aws:lambda:ap-south-1:ACCOUNT_ID:layer:dev-kisan-setu-common:N
```

## Troubleshooting

### Deployment Fails with "Provisioned Concurrency" Error

**Solution**: The infrastructure already disables provisioned concurrency for dev/staging. If you see this in production, wait 5 minutes and retry.

### CDK Bootstrap Error

**Solution**: The workflow automatically runs `cdk bootstrap`, but if it fails:

```bash
cd kisan-setu-mvp
cdk bootstrap aws://YOUR_ACCOUNT_ID/ap-south-1
```

### Lambda Layer Not Found

**Solution**: The workflow builds the layer in the `build-layer` job. Check that:
1. `build_common_layer.sh` is executable
2. `lambda/common/` directory exists with all required files

### AWS Credentials Invalid

**Solution**:
1. Verify secrets are set correctly in GitHub
2. Check IAM user has required permissions
3. Ensure access key is active (not deleted or rotated)

## Post-Deployment Verification

After successful deployment, verify:

1. **CloudFormation Stack Status**
   ```bash
   aws cloudformation describe-stacks \
     --stack-name KisanSetuMVPStack-<env> \
     --region ap-south-1
   ```

2. **Lambda Functions Count**
   ```bash
   aws lambda list-functions \
     --region ap-south-1 \
     --query "Functions[?contains(FunctionName, '<env>')].FunctionName"
   ```

3. **API Gateway Endpoint**
   - Check CDK outputs for webhook URL
   - Test with `curl` or Postman

4. **DynamoDB Table**
   ```bash
   aws dynamodb describe-table \
     --table-name <env>-KisanSetuData \
     --region ap-south-1
   ```

## Rollback Procedure

If a deployment fails or causes issues:

### Automatic Rollback
CloudFormation automatically rolls back failed deployments to the previous working state.

### Manual Rollback

1. **Via CloudFormation Console**:
   - Go to CloudFormation → Select stack
   - Actions → Continue update rollback

2. **Via Git**:
   ```bash
   # Revert the commit
   git revert <commit-hash>
   git push origin <branch>

   # GitHub Actions will automatically deploy the reverted code
   ```

## Best Practices

### Before Deploying to Production

1. ✅ Test thoroughly in dev environment
2. ✅ Deploy to staging and validate
3. ✅ Run full test suite (`pytest tests/`)
4. ✅ Review CloudFormation changeset
5. ✅ Notify team of upcoming production deployment
6. ✅ Have rollback plan ready

### During Production Deployment

1. ✅ Monitor CloudWatch logs during deployment
2. ✅ Keep AWS Console open to track stack progress
3. ✅ Be ready to manually rollback if needed
4. ✅ Test critical endpoints immediately after deployment

### After Production Deployment

1. ✅ Run smoke tests on production endpoints
2. ✅ Check CloudWatch metrics for errors
3. ✅ Monitor WhatsApp webhook for incoming messages
4. ✅ Verify Lambda functions are executing correctly

## Security Notes

### Secret Management

- ❌ **Never commit AWS credentials to Git**
- ✅ Always use GitHub Secrets for sensitive values
- ✅ Rotate IAM access keys every 90 days
- ✅ Use separate IAM users for dev/staging/prod (recommended)

### Environment Isolation

- Dev environment has `dev-` prefix on all resources
- Staging environment has `staging-` prefix
- Production has no prefix (backward compatible)
- Each environment is completely isolated

### Production Safety

- Manual approval required for production deployments
- Automatic backup before production deployment
- CloudFormation rollback on failure
- No changes to production during judging period (next 15 days)

## Support

For issues with GitHub Actions:
1. Check workflow logs in Actions tab
2. Review CloudFormation events in AWS Console
3. Check this documentation for troubleshooting steps
4. Contact DevOps team if issue persists

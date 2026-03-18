# GitHub Actions Setup - Step-by-Step Guide

## ✅ Completed Steps

The following has already been configured:

1. ✅ **IAM User Created**: `github-actions-kisan-setu`
   - ARN: `arn:aws:iam::682366718780:user/github-actions-kisan-setu`
   - Permissions: AdministratorAccess
   - Access Keys: Created and saved

2. ✅ **AWS Account ID**: `682366718780`

3. ✅ **GitHub Actions Workflows Created**:
   - `.github/workflows/test.yml` - Testing pipeline
   - `.github/workflows/deploy.yml` - Deployment pipeline

## 🔧 Manual Configuration Required

You need to complete the following steps in GitHub:

---

## Step 1: Add GitHub Secrets

### Instructions:

1. Go to your GitHub repository: https://github.com/hackergod00001/Kisan-Setu
2. Click **Settings** (top menu)
3. In left sidebar, click **Secrets and variables** → **Actions**
4. Click **New repository secret** button

### Add These 3 Secrets:

#### Secret 1: AWS_ACCESS_KEY_ID
```
Name: AWS_ACCESS_KEY_ID
Value: AKIAZ5YBZ2M6LCLRNNVG
```
**Note**: The full access key ID is shown above.

#### Secret 2: AWS_SECRET_ACCESS_KEY
```
Name: AWS_SECRET_ACCESS_KEY
Value: <SEE /tmp/github-actions-credentials.json ON YOUR LOCAL MACHINE>
```
**⚠️ IMPORTANT**:
- Open `/tmp/github-actions-credentials.json` on your local machine
- Copy the **full** `SecretAccessKey` value (not the masked version)
- This is the ONLY time you'll see this secret key
- If lost, you'll need to create new access keys

#### Secret 3: AWS_ACCOUNT_ID
```
Name: AWS_ACCOUNT_ID
Value: 682366718780
```

### Verify Secrets Added:
After adding all 3 secrets, you should see:
- ✅ AWS_ACCESS_KEY_ID
- ✅ AWS_SECRET_ACCESS_KEY
- ✅ AWS_ACCOUNT_ID

---

## Step 2: Create GitHub Environments

### Instructions:

1. Still in **Settings**, click **Environments** (left sidebar)
2. Click **New environment** button
3. Create 3 environments as described below

### Environment 1: development

**Name**: `development` (must be lowercase, exactly this spelling)

**Configuration**:
- ❌ No protection rules
- ❌ No deployment branches restriction
- Environment URL (optional): Will be populated after first deployment

**Click "Configure environment"** → **Save protection rules**

---

### Environment 2: staging

**Name**: `staging` (must be lowercase, exactly this spelling)

**Configuration** (Optional Protection Rules):
- ☐ Required reviewers: 0 (or 1 if you want approval for staging)
- ☐ Wait timer: 0 minutes
- ❌ No deployment branches restriction
- Environment URL (optional): Will be populated after first deployment

**Click "Configure environment"** → **Save protection rules**

---

### Environment 3: production

**Name**: `production` (must be lowercase, exactly this spelling)

**Configuration** (⚠️ CRITICAL - PRODUCTION PROTECTION):
- ✅ **Required reviewers**: Select 1-2 people who can approve production deployments
  - If you're the only team member, select yourself
  - For a team, select at least 2 reviewers
- ☐ Wait timer: 0 minutes (optional: set to 5-10 minutes for additional safety)
- ✅ **Deployment branches**: Selected branches only
  - Add pattern: `master`
- Environment URL (optional): Will be populated after first deployment

**Click "Configure environment"** → **Save protection rules**

---

## Step 3: Verify GitHub Actions Setup

### Test the Workflows:

1. Go to **Actions** tab in GitHub repository
2. You should see two workflows:
   - **Kisan-Setu CI/CD Pipeline** (test.yml)
   - **Kisan-Setu Deployment Pipeline** (deploy.yml)

### Trigger a Test Run:

Since the workflows are already configured, the next push to `dev` will automatically:
1. Run all tests (unit, property, integration)
2. Build the Lambda Layer
3. Deploy to the development environment

---

## Step 4: Retrieve AWS Credentials

The AWS credentials for GitHub Actions are saved in:
```
/tmp/github-actions-credentials.json
```

**View the credentials:**
```bash
cat /tmp/github-actions-credentials.json | jq '.'
```

**Output will show:**
```json
{
  "AccessKeyId": "AKIAZ5YBZ2M6LCLRNNVG",
  "SecretAccessKey": "<FULL_SECRET_KEY>",
  "Status": "Active"
}
```

**⚠️ SECURITY NOTES:**
- Copy the `SecretAccessKey` value now
- Delete `/tmp/github-actions-credentials.json` after adding to GitHub Secrets
- Never commit these credentials to Git
- Never share these credentials publicly

---

## Step 5: Test the Deployment Pipeline

Once GitHub Secrets and Environments are configured:

### Option A: Push to Dev (Automatic Deployment)
```bash
# Make a small change
cd kisan-setu-mvp
echo "# Test deployment" >> README.md
git add README.md
git commit -m "Test GitHub Actions deployment"
git push origin dev
```

Then:
1. Go to **Actions** tab in GitHub
2. Watch the deployment pipeline run
3. Verify dev environment deploys successfully

### Option B: Manual Workflow Trigger
1. Go to **Actions** tab
2. Click **Kisan-Setu Deployment Pipeline**
3. Click **Run workflow** (top right)
4. Select branch: `dev`
5. Select environment: `dev`
6. Click **Run workflow**

---

## Deployment Flow Summary

| Branch | Environment | Approval Required | Auto-Deploy |
|--------|-------------|-------------------|-------------|
| `dev` | development | ❌ No | ✅ Yes |
| `staging` | staging | ⚠️ Optional | ✅ Yes |
| `master` | production | ✅ **Required** | ❌ Manual approval |

---

## Production Deployment Process

When you're ready to deploy to production:

1. **Merge staging → master**:
   ```bash
   git checkout master
   git merge staging
   git push origin master
   ```

2. **GitHub Actions triggers**:
   - Workflow starts automatically
   - Builds Lambda Layer
   - **Pauses at production deployment** ⏸️

3. **Manual Approval Required**:
   - Designated reviewers receive notification
   - Go to **Actions** tab → Click on workflow run
   - Click **Review deployments**
   - Select **production** environment
   - Click **Approve and deploy**

4. **Deployment proceeds**:
   - Creates backup of production stack
   - Deploys to production with `context=prod`
   - Verifies deployment success
   - Sends completion notification

---

## Troubleshooting

### "Secret not found" Error
- ✅ Verify secret names are **exactly** as specified (case-sensitive)
- ✅ Verify secrets are added at **repository** level (not environment level)

### "Environment not found" Error
- ✅ Verify environment names are **exactly**: `development`, `staging`, `production`
- ✅ Check spelling (must be lowercase)

### "Unauthorized" or "Access Denied" Error
- ✅ Verify AWS credentials are correct
- ✅ Check IAM user has AdministratorAccess policy attached
- ✅ Ensure access keys are Active

### Deployment Fails with "Provisioned Concurrency" Error
- ✅ Already fixed in infrastructure for dev/staging
- ✅ If occurs in prod, wait 5 minutes and retry

---

## Security Checklist

Before going to production:

- ✅ AWS credentials added to GitHub Secrets (not hardcoded)
- ✅ Production environment has manual approval gate
- ✅ Only `master` branch can deploy to production
- ✅ At least 1 reviewer required for production deployments
- ✅ IAM user permissions reviewed (consider restricting from AdministratorAccess to minimum required)
- ✅ Access keys stored securely
- ✅ `/tmp/github-actions-credentials.json` deleted after setup

---

## Post-Setup Cleanup

After successfully configuring GitHub Secrets and testing deployment:

```bash
# Delete local credentials file
rm /tmp/github-actions-credentials.json

# Confirm deletion
ls /tmp/github-actions-credentials.json
# Should show: No such file or directory
```

---

## Next Steps

Once GitHub Actions is configured:

1. ✅ Test deployment to dev environment
2. ✅ Run full test suite against deployed dev environment
3. ✅ Deploy to staging environment
4. ✅ Validate staging deployment
5. ⏳ **Wait for judging period to end** (next 15 days)
6. ✅ Deploy to production after judging (with manual approval)

---

## Support

For detailed troubleshooting, see: [GITHUB_ACTIONS_SETUP.md](./GITHUB_ACTIONS_SETUP.md)

For questions or issues:
1. Check workflow logs in Actions tab
2. Review CloudFormation events in AWS Console
3. Consult documentation in `.github/` directory

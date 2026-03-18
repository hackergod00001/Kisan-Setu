# GitHub Environments - Simplified Setup

## Quick Setup (5 minutes)

### Step 1: Add GitHub Secrets First

Go to: **Repository Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add these 3 secrets:

| Secret Name | Value |
|------------|-------|
| `AWS_ACCESS_KEY_ID` | Get from `~/Documents/github-actions-credentials-backup.json` |
| `AWS_SECRET_ACCESS_KEY` | Get from `~/Documents/github-actions-credentials-backup.json` |
| `AWS_ACCOUNT_ID` | `682366718780` |

**To retrieve credentials:**
```bash
# Access Key ID
cat ~/Documents/github-actions-credentials-backup.json | jq -r '.AccessKeyId'

# Secret Access Key
cat ~/Documents/github-actions-credentials-backup.json | jq -r '.SecretAccessKey'
```

---

### Step 2: Create Environments

Go to: **Repository Settings** → **Environments** → **New environment**

#### **Environment 1: development**
1. Name: `development`
2. Click **Configure environment**
3. **Skip all protection rules** (leave everything unchecked)
4. **Optional**: Add environment URL after first deployment:
   - URL: Will be your CloudFront URL (add after deployment completes)
5. Click outside any field to auto-save

#### **Environment 2: staging**
1. Name: `staging`
2. Click **Configure environment**
3. **Optional protection rules** (only if you have GitHub Pro/Team):
   - ✅ Required reviewers: Add your username `@hackergod00001`
   - Leave unchecked if you have GitHub Free account
4. **Deployment branches**: Leave as "All branches" or add `staging` if desired
5. **Optional**: Add environment URL after deployment
6. Click outside any field to auto-save

#### **Environment 3: production**
1. Name: `production`
2. Click **Configure environment**
3. **Optional protection rules** (only if you have GitHub Pro/Team):
   - ✅ Required reviewers: Add your username `@hackergod00001`
   - ✅ Wait timer: 5 minutes (optional)
4. **Deployment branches**: Click "Selected branches"
   - Add deployment branch rule: `master`
   - This ensures only `master` branch can deploy to production
5. **Optional**: Add environment URL after deployment
6. Click outside any field to auto-save

---

### Step 3: Verify Setup

#### Check Secrets:
Go to: **Settings** → **Secrets and variables** → **Actions**

You should see:
- ✅ `AWS_ACCESS_KEY_ID`
- ✅ `AWS_SECRET_ACCESS_KEY`
- ✅ `AWS_ACCOUNT_ID`

#### Check Environments:
Go to: **Settings** → **Environments**

You should see:
- ✅ `development`
- ✅ `staging`
- ✅ `production`

---

## About Required Reviewers

### If You Have GitHub Free Account:
- **Required reviewers won't work** (GitHub Pro/Team/Enterprise only)
- Your environments will auto-deploy without approval
- This is **fine for development and staging**
- For production, you'll need to be careful about what you push to `master`

### If You Have GitHub Pro/Team:
- Required reviewers will work
- Manual approval required before production deployment
- Reviewers get notification and must approve in GitHub Actions UI

---

## About Environment URLs

### When to Add URLs:
1. **After first deployment** - CloudFormation outputs will show CloudFront URLs
2. **URLs are optional** - They're just for quick reference in GitHub UI
3. **Where to find URLs**:
   ```bash
   # After CDK deployment completes, check outputs:
   cd kisan-setu-mvp

   # Dev CloudFront URL:
   aws cloudformation describe-stacks \
     --stack-name KisanSetuMVPStack-dev \
     --query 'Stacks[0].Outputs[?OutputKey==`DashboardURL`].OutputValue' \
     --output text

   # Staging CloudFront URL:
   aws cloudformation describe-stacks \
     --stack-name KisanSetuMVPStack-staging \
     --query 'Stacks[0].Outputs[?OutputKey==`DashboardURL`].OutputValue' \
     --output text

   # Production CloudFront URL:
   aws cloudformation describe-stacks \
     --stack-name KisanSetuMVPStack \
     --query 'Stacks[0].Outputs[?OutputKey==`DashboardURL`].OutputValue' \
     --output text
   ```

---

## Testing GitHub Actions

Once you've completed Steps 1-2 above, test the workflow:

### Option 1: Push to dev branch
```bash
cd kisan-setu-mvp
git checkout dev
git commit --allow-empty -m "Test GitHub Actions deployment"
git push origin dev
```

Then check: **Repository** → **Actions** tab

You should see:
- ✅ Workflow "Kisan-Setu Deployment Pipeline" running
- ✅ "deploy-dev" job executing
- ✅ Building Lambda Layer
- ✅ Deploying to AWS

### Option 2: Manual workflow dispatch
1. Go to: **Actions** → **Kisan-Setu Deployment Pipeline**
2. Click **Run workflow**
3. Select environment: `dev`
4. Click **Run workflow**

---

## Troubleshooting

### "Required reviewers not saving"
- **Cause**: GitHub Free account
- **Solution**: Skip required reviewers, use careful git workflow instead

### "Can't find environment URL field"
- **Cause**: URL field only appears after environment is created
- **Solution**: Create environment first, then edit to add URL

### "GitHub Actions not running"
- **Check 1**: All 3 secrets added?
- **Check 2**: All 3 environments created?
- **Check 3**: Did you push to `dev`, `staging`, or `master` branch?
- **Check 4**: Check **Actions** tab for error messages

### "AWS credentials invalid"
- **Check**: Credentials in `/tmp/github-actions-credentials.json` or `~/Documents/github-actions-credentials-backup.json`
- **Solution**: Re-add secrets with correct values

---

## Current Status

✅ **Dev environment deployed** (manually via local CDK)
- Webhook URL: `https://chf0n7zrjd.execute-api.ap-south-1.amazonaws.com/prod/webhook`
- DynamoDB: `dev-KisanSetuData`
- Ready for testing

⏳ **Staging environment** - Not yet created
⏳ **Production environment** - Frozen (judging period)

---

## Next Steps

1. ✅ Add 3 GitHub Secrets (Step 1 above)
2. ✅ Create 3 GitHub Environments (Step 2 above)
3. 🔄 Test dev environment with WhatsApp (see `DEV_TESTING_CHECKLIST.md`)
4. 🔄 After dev testing passes, deploy to staging:
   ```bash
   git checkout staging
   git merge dev
   git push origin staging
   ```
5. ⏸️ Wait for 15-day judging period to end
6. 🔄 Deploy to production after judging ends

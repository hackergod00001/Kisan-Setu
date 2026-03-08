# Deployment Scripts Reference

This document explains the deployment scripts and when to use each one.

## 📜 Available Scripts

### 1. `deploy.sh` - Full Automated Deployment (Recommended)

**What it does:**
- Builds Lambda packages with Linux-compatible dependencies
- Deploys entire infrastructure to AWS
- Handles everything in one command

**When to use:**
- First-time deployment
- After making code changes to Lambda functions
- When you want a complete redeployment

**Requirements:**
- Docker running (optional, falls back to manual pip install)
- AWS credentials configured
- Virtual environment activated

**Usage:**
```bash
./deploy.sh
```

---

### 2. `build_lambda_packages.sh` - Lambda Package Builder

**What it does:**
- Builds Lambda deployment packages using Docker
- Installs Linux-compatible Python dependencies
- Falls back to manual pip install if Docker isn't available

**When to use:**
- Before deploying if you've updated Lambda dependencies
- To rebuild packages without deploying
- When you want to verify package contents

**Requirements:**
- Docker running (optional)
- Python 3.11+

**Usage:**
```bash
./build_lambda_packages.sh
```

**How it works:**
1. Checks if Docker is running
2. If Docker available: Uses `public.ecr.aws/lambda/python:3.11` image to build packages
3. If Docker not available: Falls back to `pip install --platform manylinux2014_x86_64`
4. Cleans up old dependencies and installs fresh ones

---

### 3. `deploy_meta_whatsapp.sh` - WhatsApp Setup & Quick Deploy

**What it does:**
- Stores WhatsApp credentials in AWS Secrets Manager
- Deploys infrastructure
- Configures webhook URL
- Sends test message

**When to use:**
- Setting up WhatsApp integration for the first time
- Updating WhatsApp access token (expires every 24 hours)
- Quick deployment with WhatsApp configuration

**Requirements:**
- `WHATSAPP_API_TOKEN` environment variable set
- Meta WhatsApp Business Account

**Usage:**
```bash
# Set your token
export WHATSAPP_API_TOKEN='EAAxxxxxxxxxxxxx'

# Deploy
./deploy_meta_whatsapp.sh
```

---

## 🔄 Deployment Workflows

### First-Time Setup
```bash
# 1. Activate virtual environment
source .venv/bin/activate

# 2. Set WhatsApp token
export WHATSAPP_API_TOKEN='your_token'

# 3. Deploy everything
./deploy_meta_whatsapp.sh
```

### Regular Development Workflow
```bash
# 1. Make code changes to Lambda functions

# 2. Deploy with automated build
./deploy.sh

# 3. Test
# Send WhatsApp message or run pytest
```

### Updating WhatsApp Token (Daily)
```bash
# Token expires every 24 hours
export WHATSAPP_API_TOKEN='new_token'
./deploy_meta_whatsapp.sh
```

### Manual Build + Deploy
```bash
# 1. Build packages
./build_lambda_packages.sh

# 2. Deploy
cdk deploy --require-approval never
```

---

## 🐳 Docker vs Non-Docker Deployment

### With Docker (Recommended)
**Pros:**
- Guaranteed Linux-compatible dependencies
- Consistent builds across different machines
- Matches Lambda runtime environment exactly

**Cons:**
- Requires Docker to be installed and running
- Slightly slower first build (downloads image)

### Without Docker (Fallback)
**Pros:**
- Works without Docker
- Faster if you already have dependencies cached

**Cons:**
- May have compatibility issues with some packages
- Requires manual platform specification

---

## 🔧 Troubleshooting

### "Docker is not running"
```bash
# Start Docker Desktop (macOS/Windows)
# Or start Docker daemon (Linux)
sudo systemctl start docker

# Verify
docker info
```

### "Module not found" errors in Lambda
```bash
# Rebuild packages with Docker
./build_lambda_packages.sh

# Redeploy
cdk deploy
```

### "Access token expired"
```bash
# Get new token from Meta Developer Console
# Update and redeploy
export WHATSAPP_API_TOKEN='new_token'
./deploy_meta_whatsapp.sh
```

### CDK deployment fails
```bash
# Check AWS credentials
aws sts get-caller-identity

# Bootstrap CDK (one-time)
cdk bootstrap

# Try again
./deploy.sh
```

---

## 📊 Deployment Comparison

| Script | Build Packages | Deploy CDK | Configure WhatsApp | Time |
|--------|---------------|------------|-------------------|------|
| `deploy.sh` | ✅ | ✅ | ❌ | ~2 min |
| `build_lambda_packages.sh` | ✅ | ❌ | ❌ | ~30 sec |
| `deploy_meta_whatsapp.sh` | ❌ | ✅ | ✅ | ~2 min |
| Manual CDK | ❌ | ✅ | ❌ | ~1 min |

---

## 🎯 Best Practices

1. **Use `deploy.sh` for most deployments** - It handles everything automatically
2. **Keep Docker running** - Ensures consistent builds
3. **Update WhatsApp token daily** - Use `deploy_meta_whatsapp.sh`
4. **Test locally first** - Run `pytest` before deploying
5. **Check logs after deployment** - Verify Lambda functions work correctly

---

## 📝 Environment Variables

### Required
- `AWS_PROFILE` or AWS credentials configured
- `WHATSAPP_API_TOKEN` (for WhatsApp setup)

### Optional
- `AWS_REGION` (defaults to ap-south-1)
- `CDK_DEFAULT_ACCOUNT` (auto-detected)
- `CDK_DEFAULT_REGION` (auto-detected)

---

## 🚀 Quick Commands

```bash
# Full deployment
./deploy.sh

# Update WhatsApp token
export WHATSAPP_API_TOKEN='new_token' && ./deploy_meta_whatsapp.sh

# Rebuild packages only
./build_lambda_packages.sh

# Deploy without building
cdk deploy

# Check deployment status
aws cloudformation describe-stacks --stack-name KisanSetuMVPStack --region ap-south-1

# View logs
aws logs tail /aws/lambda/KisanSetuMVPStack-BedrockOrchestratorF1D5335E-8c6vEjDJfHEl --follow --region ap-south-1
```

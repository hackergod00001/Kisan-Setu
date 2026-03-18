#!/usr/bin/env python3
"""
Kisan-Setu MVP CDK App

Supports multi-environment deployment via --context environment=<env>:
  - dev: Development environment (isolated testing)
  - staging: Pre-production environment (final validation)
  - prod: Production environment (current resources, no prefix)

Example usage:
  cdk deploy --context environment=dev
  cdk deploy --context environment=staging
  cdk deploy --context environment=prod
"""

import aws_cdk as cdk
from infrastructure_stack import KisanSetuMVPStack

app = cdk.App()

# Get environment from context (default to 'dev' for safety)
environment = app.node.try_get_context("environment") or "dev"

# Create stack with environment-specific name
stack_name = f"KisanSetuMVPStack-{environment}" if environment != "prod" else "KisanSetuMVPStack"

KisanSetuMVPStack(
    app, stack_name,
    environment=environment,
    env=cdk.Environment(
        account=app.node.try_get_context("account"),
        region=app.node.try_get_context("region") or "ap-south-1"
    ),
    description=f"Kisan-Setu MVP Infrastructure Stack ({environment} environment)"
)

app.synth()

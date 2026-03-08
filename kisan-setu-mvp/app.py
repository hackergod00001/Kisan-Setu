#!/usr/bin/env python3
"""
Kisan-Setu MVP CDK App
"""

import aws_cdk as cdk
from infrastructure_stack import KisanSetuMVPStack

app = cdk.App()

KisanSetuMVPStack(
    app, "KisanSetuMVPStack",
    env=cdk.Environment(
        account=app.node.try_get_context("account"),
        region=app.node.try_get_context("region") or "ap-south-1"
    ),
    description="Kisan-Setu MVP Infrastructure Stack"
)

app.synth()

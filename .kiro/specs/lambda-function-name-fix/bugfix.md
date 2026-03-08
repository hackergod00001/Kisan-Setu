# Bugfix Requirements Document

## Introduction

The router Lambda function is failing to invoke downstream Lambda functions (BedrockOrchestrator, VoiceAgent, CreditCalculator, SatelliteAnalyzer) because environment variables in the CDK infrastructure stack contain hardcoded logical function names instead of the actual CDK-generated physical function names. This prevents the WhatsApp message processing pipeline from functioning end-to-end, as messages cannot be routed to the AI processing components.

The bug occurs in `kisan-setu-mvp/infrastructure_stack.py` where environment variables are set using string literals (e.g., `"BedrockOrchestrator"`) instead of referencing the CDK Lambda construct's `function_name` property, which contains the actual deployed name with stack prefix and hash suffix (e.g., `"KisanSetuMVPStack-BedrockOrchestratorF1D5335E-8c6vEjDJfHEl"`).

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN the router Lambda function attempts to invoke a downstream Lambda using the `BEDROCK_ORCHESTRATOR_FUNCTION` environment variable THEN the system fails with "Function not found" error because the value is `"BedrockOrchestrator"` instead of the actual CDK-generated name

1.2 WHEN the router Lambda function attempts to invoke a downstream Lambda using the `VOICE_AGENT_FUNCTION` environment variable THEN the system fails with "Function not found" error because the value is `"VoiceAgent"` instead of the actual CDK-generated name

1.3 WHEN the router Lambda function attempts to invoke a downstream Lambda using the `CREDIT_CALCULATOR_FUNCTION` environment variable THEN the system fails with "Function not found" error because the value is `"CreditCalculator"` instead of the actual CDK-generated name

1.4 WHEN the router Lambda function attempts to invoke a downstream Lambda using the `SATELLITE_ANALYZER_FUNCTION` environment variable THEN the system fails with "Function not found" error because the value is `"SatelliteAnalyzer"` instead of the actual CDK-generated name

### Expected Behavior (Correct)

2.1 WHEN the router Lambda function attempts to invoke a downstream Lambda using the `BEDROCK_ORCHESTRATOR_FUNCTION` environment variable THEN the system SHALL successfully invoke the Lambda function using the actual CDK-generated physical function name

2.2 WHEN the router Lambda function attempts to invoke a downstream Lambda using the `VOICE_AGENT_FUNCTION` environment variable THEN the system SHALL successfully invoke the Lambda function using the actual CDK-generated physical function name

2.3 WHEN the router Lambda function attempts to invoke a downstream Lambda using the `CREDIT_CALCULATOR_FUNCTION` environment variable THEN the system SHALL successfully invoke the Lambda function using the actual CDK-generated physical function name

2.4 WHEN the router Lambda function attempts to invoke a downstream Lambda using the `SATELLITE_ANALYZER_FUNCTION` environment variable THEN the system SHALL successfully invoke the Lambda function using the actual CDK-generated physical function name

2.5 WHEN the CDK infrastructure stack is deployed or updated THEN the environment variables SHALL automatically contain the current CDK-generated physical function names without requiring manual updates

### Unchanged Behavior (Regression Prevention)

3.1 WHEN the router Lambda function receives a WhatsApp webhook event THEN the system SHALL CONTINUE TO successfully receive and parse the incoming message

3.2 WHEN the router Lambda function performs webhook verification THEN the system SHALL CONTINUE TO successfully verify the webhook challenge

3.3 WHEN the router Lambda function reads environment variables for function names THEN the system SHALL CONTINUE TO use the same environment variable names (`BEDROCK_ORCHESTRATOR_FUNCTION`, `VOICE_AGENT_FUNCTION`, `CREDIT_CALCULATOR_FUNCTION`, `SATELLITE_ANALYZER_FUNCTION`)

3.4 WHEN downstream Lambda functions are invoked successfully THEN the system SHALL CONTINUE TO pass the correct payload and context to those functions

3.5 WHEN the CDK stack is synthesized THEN the system SHALL CONTINUE TO create all Lambda functions with their CDK-generated physical names including stack prefix and hash suffix

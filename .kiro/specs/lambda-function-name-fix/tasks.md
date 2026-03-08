# Implementation Plan

- [x] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - Environment Variables Contain Hardcoded Strings
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate the bug exists
  - **Scoped PBT Approach**: Scope the property to the four concrete failing environment variables (BEDROCK_ORCHESTRATOR_FUNCTION, VOICE_AGENT_FUNCTION, CREDIT_CALCULATOR_FUNCTION, SATELLITE_ANALYZER_FUNCTION)
  - Test that environment variables contain hardcoded string literals instead of CDK construct references
  - For each of the four buggy environment variables, verify the value is a hardcoded string (e.g., "BedrockOrchestrator") and NOT a Lambda construct reference
  - Inspect deployed Lambda environment variables using AWS CLI or boto3 to confirm hardcoded values
  - Attempt Lambda invocation with hardcoded function names and verify "Function not found" errors occur
  - Run test on UNFIXED infrastructure
  - **EXPECTED OUTCOME**: Test FAILS (this is correct - it proves the bug exists)
  - Document counterexamples found:
    - Environment variable values (e.g., BEDROCK_ORCHESTRATOR_FUNCTION="BedrockOrchestrator")
    - Lambda invocation errors (e.g., boto3.client('lambda').invoke() raises ClientError: "Function not found: BedrockOrchestrator")
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Non-Buggy Environment Variables Unchanged
  - **IMPORTANT**: Follow observation-first methodology
  - Observe behavior on UNFIXED infrastructure for non-buggy environment variables
  - Capture all environment variables from router_lambda and orchestrator_lambda on UNFIXED infrastructure
  - Write property-based tests capturing observed behavior patterns:
    - For all environment variables NOT in [BEDROCK_ORCHESTRATOR_FUNCTION, VOICE_AGENT_FUNCTION, CREDIT_CALCULATOR_FUNCTION, SATELLITE_ANALYZER_FUNCTION], verify values remain unchanged
    - Test DYNAMODB_TABLE, S3_BUCKET_RAW, S3_BUCKET_PROCESSED, S3_BUCKET_ARCHIVE remain unchanged
    - Test REGION, WEBHOOK_VERIFY_TOKEN, WHATSAPP_SECRET_NAME remain unchanged
    - Test PROCESSOR_FUNCTION_NAME continues to use correct reference pattern
    - Test SNS_ALERT_TOPIC_ARN remains unchanged
  - Property-based testing generates many test cases for stronger guarantees
  - Run tests on UNFIXED infrastructure
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed infrastructure
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 3. Fix environment variable references in CDK infrastructure stack

  - [x] 3.1 Update router_lambda environment variables
    - Replace `"VOICE_AGENT_FUNCTION": "VoiceHandler"` with `"VOICE_AGENT_FUNCTION": voice_lambda.function_name`
    - Replace `"BEDROCK_ORCHESTRATOR_FUNCTION": "BedrockOrchestrator"` with `"BEDROCK_ORCHESTRATOR_FUNCTION": orchestrator_lambda.function_name`
    - Replace `"CREDIT_CALCULATOR_FUNCTION": "CreditCalculator"` with `"CREDIT_CALCULATOR_FUNCTION": credit_lambda.function_name`
    - Replace `"SATELLITE_ANALYZER_FUNCTION": "SatelliteAnalyzer"` with `"SATELLITE_ANALYZER_FUNCTION": satellite_lambda.function_name`
    - _Bug_Condition: isBugCondition(envVarAssignment) where envVarAssignment.variableName IN [BEDROCK_ORCHESTRATOR_FUNCTION, VOICE_AGENT_FUNCTION, CREDIT_CALCULATOR_FUNCTION, SATELLITE_ANALYZER_FUNCTION] AND envVarAssignment.value IS StringLiteral_
    - _Expected_Behavior: Environment variables contain Lambda construct's function_name property, resulting in CDK-generated physical function names_
    - _Preservation: Router Lambda continues to read environment variables using same variable names; webhook verification, message parsing, Lambda invocation payload structure remain unchanged; all other environment variables remain unchanged_
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 3.1, 3.2, 3.3, 3.4, 3.5_

  - [x] 3.2 Update orchestrator_lambda environment variable
    - Replace `"SATELLITE_ANALYZER_FUNCTION": "SatelliteAnalyzer"` with `"SATELLITE_ANALYZER_FUNCTION": satellite_lambda.function_name`
    - _Bug_Condition: Same as 3.1 for orchestrator_lambda's SATELLITE_ANALYZER_FUNCTION_
    - _Expected_Behavior: Environment variable contains Lambda construct's function_name property_
    - _Preservation: Orchestrator Lambda continues to read environment variable using same variable name; all other orchestrator environment variables remain unchanged_
    - _Requirements: 2.4, 2.5, 3.3, 3.4, 3.5_

  - [x] 3.3 Verify Lambda creation order
    - Confirm voice_lambda, credit_lambda, satellite_lambda, and orchestrator_lambda are created BEFORE router_lambda references them in environment variables
    - Verify CDK synthesis succeeds without circular dependency errors
    - _Requirements: 2.5, 3.5_

  - [x] 3.4 Deploy updated CDK stack
    - Run `cdk deploy` to deploy the fixed infrastructure
    - Verify deployment completes successfully
    - Confirm CloudFormation stack update shows environment variable changes
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 3.5 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Environment Variables Contain Physical Function Names
    - **IMPORTANT**: Re-run the SAME test from task 1 - do NOT write a new test
    - The test from task 1 encodes the expected behavior
    - When this test passes, it confirms the expected behavior is satisfied
    - Run bug condition exploration test from step 1 on FIXED infrastructure
    - Verify environment variables now contain CDK-generated physical function names (e.g., "KisanSetuMVPStack-BedrockOrchestratorF1D5335E-8c6vEjDJfHEl")
    - Verify Lambda invocations succeed with physical function names
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 3.6 Verify preservation tests still pass
    - **Property 2: Preservation** - Non-Buggy Environment Variables Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run preservation property tests from step 2 on FIXED infrastructure
    - Compare environment variables between UNFIXED and FIXED infrastructure
    - Verify only the four buggy environment variables changed
    - Verify all other environment variables remain exactly the same
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Confirm all tests still pass after fix (no regressions)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 4. Checkpoint - Ensure all tests pass
  - Verify bug condition test passes (environment variables contain physical function names)
  - Verify preservation tests pass (non-buggy environment variables unchanged)
  - Test end-to-end WhatsApp message flow through webhook to downstream Lambda invocations
  - Verify CloudWatch Logs show successful Lambda invocations with physical function names
  - Verify no "Function not found" errors occur in any message routing scenario
  - Ask the user if questions arise

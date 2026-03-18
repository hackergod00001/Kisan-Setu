"""
Bug Condition Exploration Test for Lambda Function Name Fix

**Validates: Requirements 1.1, 1.2, 1.3, 1.4**

This test explores the bug condition where environment variables in the router Lambda
contain hardcoded logical function names instead of CDK-generated physical function names.

CRITICAL: This test is EXPECTED TO FAIL on unfixed infrastructure.
- Test failure confirms the bug exists
- Test will pass after the fix is implemented

The test verifies:
1. Environment variables contain hardcoded strings (e.g., "BedrockOrchestrator")
2. Lambda invocation fails with "Function not found" errors
3. The four buggy environment variables are affected

This is a scoped property-based test focusing on the four concrete failing
environment variables identified in the bug analysis.
"""

import boto3
import pytest
import os
from hypothesis import given, strategies as st, settings, HealthCheck
from botocore.exceptions import ClientError

# AWS clients
lambda_client = boto3.client('lambda', region_name='ap-south-1')

# The four buggy environment variables
BUGGY_ENV_VARS = [
    'BEDROCK_ORCHESTRATOR_FUNCTION',
    'VOICE_AGENT_FUNCTION',
    'CREDIT_CALCULATOR_FUNCTION',
    'SATELLITE_ANALYZER_FUNCTION'
]

# Expected hardcoded values (the bug)
EXPECTED_HARDCODED_VALUES = {
    'BEDROCK_ORCHESTRATOR_FUNCTION': 'BedrockOrchestrator',
    'VOICE_AGENT_FUNCTION': 'VoiceHandler',
    'CREDIT_CALCULATOR_FUNCTION': 'CreditCalculator',
    'SATELLITE_ANALYZER_FUNCTION': 'SatelliteAnalyzer'
}


def get_router_lambda_name():
    """
    Find the router Lambda function name.
    
    The actual deployed name will be something like:
    "KisanSetuMVPStack-MessageRouterXXXXXXXX-YYYYYYYY"
    """
    try:
        # List all Lambda functions
        response = lambda_client.list_functions()
        
        # Find the MessageRouter function
        for function in response['Functions']:
            if 'MessageRouter' in function['FunctionName']:
                return function['FunctionName']
        
        # If not found, try with pagination
        while 'NextMarker' in response:
            response = lambda_client.list_functions(Marker=response['NextMarker'])
            for function in response['Functions']:
                if 'MessageRouter' in function['FunctionName']:
                    return function['FunctionName']
        
        raise ValueError("MessageRouter Lambda function not found")
    
    except Exception as e:
        pytest.skip(f"Could not find router Lambda: {str(e)}")


def get_lambda_environment_variables(function_name):
    """
    Get environment variables from a deployed Lambda function.
    
    Args:
        function_name: The Lambda function name
        
    Returns:
        Dictionary of environment variables
    """
    try:
        response = lambda_client.get_function_configuration(
            FunctionName=function_name
        )
        return response.get('Environment', {}).get('Variables', {})
    
    except Exception as e:
        pytest.skip(f"Could not get Lambda configuration: {str(e)}")


@pytest.mark.integration
def test_bug_condition_environment_variables_contain_hardcoded_strings():
    """
    Property 1: Bug Condition - Environment Variables Contain Hardcoded Strings
    
    **Validates: Requirements 1.1, 1.2, 1.3, 1.4**
    
    CRITICAL: This test MUST FAIL on unfixed code - failure confirms the bug exists.
    
    This test verifies that the four buggy environment variables contain hardcoded
    string literals instead of CDK-generated physical function names.
    
    Expected behavior on UNFIXED infrastructure:
    - BEDROCK_ORCHESTRATOR_FUNCTION = "BedrockOrchestrator" (hardcoded)
    - VOICE_AGENT_FUNCTION = "VoiceHandler" (hardcoded)
    - CREDIT_CALCULATOR_FUNCTION = "CreditCalculator" (hardcoded)
    - SATELLITE_ANALYZER_FUNCTION = "SatelliteAnalyzer" (hardcoded)
    
    Expected behavior on FIXED infrastructure:
    - Environment variables contain physical names like "KisanSetuMVPStack-BedrockOrchestratorXXX-YYY"
    - Physical names include stack prefix and hash suffix
    - Lambda functions can be invoked successfully
    """
    # Get the router Lambda function name
    router_function_name = get_router_lambda_name()
    print(f"\n✓ Found router Lambda: {router_function_name}")
    
    # Get environment variables
    env_vars = get_lambda_environment_variables(router_function_name)
    print(f"✓ Retrieved environment variables")
    
    # Check each buggy environment variable
    counterexamples = []
    
    for env_var_name in BUGGY_ENV_VARS:
        if env_var_name not in env_vars:
            counterexamples.append(f"Missing environment variable: {env_var_name}")
            continue
        
        actual_value = env_vars[env_var_name]
        expected_hardcoded = EXPECTED_HARDCODED_VALUES[env_var_name]
        
        print(f"\n{env_var_name}:")
        print(f"  Actual value: {actual_value}")
        print(f"  Expected hardcoded (bug): {expected_hardcoded}")
        
        # Check if it's a hardcoded string (the bug condition)
        # Physical function names have the pattern: "StackName-ConstructId-Hash"
        # Hardcoded names are just the construct ID without stack prefix or hash
        is_hardcoded = actual_value == expected_hardcoded
        is_physical_name = '-' in actual_value and len(actual_value) > 20
        
        if is_hardcoded:
            # BUG DETECTED: Environment variable contains hardcoded string
            counterexamples.append(
                f"{env_var_name} contains hardcoded string '{actual_value}' "
                f"instead of physical function name"
            )
            print(f"  ✗ BUG: Contains hardcoded string (not a physical function name)")
        elif is_physical_name:
            # FIXED: Environment variable contains physical function name
            print(f"  ✓ FIXED: Contains physical function name")
        else:
            # UNEXPECTED: Neither hardcoded nor physical name
            counterexamples.append(
                f"{env_var_name} has unexpected value '{actual_value}'"
            )
            print(f"  ? UNEXPECTED: Neither hardcoded nor physical name")
    
    # Report findings
    if counterexamples:
        print("\n" + "="*70)
        print("BUG CONDITION DETECTED - Counterexamples found:")
        print("="*70)
        for i, example in enumerate(counterexamples, 1):
            print(f"{i}. {example}")
        print("="*70)
        print("\nThis test FAILURE is EXPECTED on unfixed infrastructure.")
        print("It confirms the bug exists and needs to be fixed.")
        print("="*70)
        
        # Fail the test to document the bug
        pytest.fail(
            f"Bug condition detected: {len(counterexamples)} environment variables "
            f"contain hardcoded strings instead of physical function names. "
            f"See counterexamples above."
        )
    else:
        print("\n" + "="*70)
        print("BUG FIXED - All environment variables contain physical function names")
        print("="*70)


@pytest.mark.integration
@given(env_var_name=st.sampled_from(BUGGY_ENV_VARS))
@settings(
    max_examples=4,  # Test all 4 environment variables
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_bug_condition_lambda_invocation_fails_with_hardcoded_names(env_var_name):
    """
    Property 1: Bug Condition - Lambda Invocation Fails with Hardcoded Names
    
    **Validates: Requirements 1.1, 1.2, 1.3, 1.4**
    
    CRITICAL: This test MUST FAIL on unfixed code - failure confirms the bug exists.
    
    This property-based test verifies that attempting to invoke Lambda functions
    using the hardcoded names from environment variables results in "Function not found"
    errors.
    
    For each of the four buggy environment variables, we:
    1. Get the value from the router Lambda's environment
    2. Attempt to invoke a Lambda function with that name
    3. Expect a ClientError with "Function not found" (on unfixed infrastructure)
    4. Expect successful invocation (on fixed infrastructure)
    """
    # Get the router Lambda function name
    router_function_name = get_router_lambda_name()
    
    # Get environment variables
    env_vars = get_lambda_environment_variables(router_function_name)
    
    if env_var_name not in env_vars:
        pytest.skip(f"Environment variable {env_var_name} not found")
    
    function_name_from_env = env_vars[env_var_name]
    
    print(f"\n{'='*70}")
    print(f"Testing Lambda invocation: {env_var_name}")
    print(f"Function name from environment: {function_name_from_env}")
    print(f"{'='*70}")
    
    # Attempt to invoke the Lambda function
    try:
        # Use a minimal test payload
        import json
        test_payload = {
            'test': True,
            'source': 'bug_exploration_test'
        }
        
        response = lambda_client.invoke(
            FunctionName=function_name_from_env,
            InvocationType='RequestResponse',
            Payload=json.dumps(test_payload).encode()
        )
        
        # If we get here, the function exists and was invoked
        status_code = response['StatusCode']
        print(f"✓ Lambda invocation succeeded (StatusCode: {status_code})")
        print(f"✓ FIXED: Function '{function_name_from_env}' exists and can be invoked")
        
        # On fixed infrastructure, this should succeed
        # The test passes, indicating the bug is fixed
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        
        print(f"✗ Lambda invocation failed:")
        print(f"  Error Code: {error_code}")
        print(f"  Error Message: {error_message}")
        
        if error_code == 'ResourceNotFoundException':
            # BUG DETECTED: Function not found
            print(f"\n{'='*70}")
            print(f"BUG CONDITION DETECTED - Counterexample:")
            print(f"{'='*70}")
            print(f"Environment variable: {env_var_name}")
            print(f"Value: {function_name_from_env}")
            print(f"Error: Function not found")
            print(f"{'='*70}")
            print(f"\nThis test FAILURE is EXPECTED on unfixed infrastructure.")
            print(f"It confirms the bug exists: environment variable contains")
            print(f"hardcoded name '{function_name_from_env}' which doesn't exist.")
            print(f"{'='*70}")
            
            # Fail the test to document the bug
            pytest.fail(
                f"Bug condition detected: Lambda invocation failed for {env_var_name}. "
                f"Environment variable contains hardcoded name '{function_name_from_env}' "
                f"which doesn't exist. Error: {error_message}"
            )
        else:
            # Unexpected error
            print(f"✗ Unexpected error: {error_code}")
            pytest.fail(f"Unexpected error invoking Lambda: {error_code} - {error_message}")


@pytest.mark.integration
def test_bug_condition_summary():
    """
    Summary test that documents all counterexamples found.
    
    This test provides a comprehensive report of the bug condition across
    all four environment variables.
    """
    router_function_name = get_router_lambda_name()
    env_vars = get_lambda_environment_variables(router_function_name)
    
    print(f"\n{'='*70}")
    print("BUG CONDITION EXPLORATION - SUMMARY")
    print(f"{'='*70}")
    print(f"Router Lambda: {router_function_name}")
    print(f"{'='*70}")
    
    all_counterexamples = []
    
    for env_var_name in BUGGY_ENV_VARS:
        if env_var_name not in env_vars:
            print(f"\n{env_var_name}: MISSING")
            all_counterexamples.append(f"{env_var_name} is missing")
            continue
        
        value = env_vars[env_var_name]
        expected_hardcoded = EXPECTED_HARDCODED_VALUES[env_var_name]
        
        print(f"\n{env_var_name}:")
        print(f"  Value: {value}")
        
        # Check if hardcoded
        is_hardcoded = value == expected_hardcoded
        is_physical = '-' in value and len(value) > 20
        
        if is_hardcoded:
            print(f"  Status: ✗ HARDCODED (bug)")
            all_counterexamples.append(f"{env_var_name}={value} (hardcoded)")
            
            # Try to invoke
            try:
                lambda_client.get_function(FunctionName=value)
                print(f"  Function exists: ✓ (unexpected)")
            except ClientError as e:
                if e.response['Error']['Code'] == 'ResourceNotFoundException':
                    print(f"  Function exists: ✗ (Function not found)")
                    all_counterexamples.append(
                        f"Lambda invocation fails for {env_var_name}: Function not found"
                    )
        elif is_physical:
            print(f"  Status: ✓ PHYSICAL NAME (fixed)")
        else:
            print(f"  Status: ? UNEXPECTED")
            all_counterexamples.append(f"{env_var_name}={value} (unexpected format)")
    
    print(f"\n{'='*70}")
    print(f"COUNTEREXAMPLES FOUND: {len(all_counterexamples)}")
    print(f"{'='*70}")
    
    if all_counterexamples:
        for i, example in enumerate(all_counterexamples, 1):
            print(f"{i}. {example}")
        
        print(f"\n{'='*70}")
        print("CONCLUSION: Bug exists - environment variables contain hardcoded strings")
        print(f"{'='*70}")
        
        pytest.fail(
            f"Bug condition confirmed: {len(all_counterexamples)} counterexamples found. "
            f"Environment variables contain hardcoded strings instead of physical function names."
        )
    else:
        print("\nCONCLUSION: Bug fixed - all environment variables contain physical names")
        print(f"{'='*70}")


# ============================================================================
# PRESERVATION PROPERTY TESTS (Task 2)
# ============================================================================

"""
Preservation Property Tests for Lambda Function Name Fix

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**

These tests verify that for all environment variables where the bug condition
does NOT hold, the fixed infrastructure produces the same configuration as the
original infrastructure.

IMPORTANT: These tests should PASS on UNFIXED infrastructure to establish baseline.
They should also PASS on FIXED infrastructure to confirm no regressions.

The tests verify that only the four buggy environment variables change, and all
other environment variables remain exactly the same.
"""

# Non-buggy environment variables that should be preserved
ROUTER_PRESERVED_ENV_VARS = [
    'DYNAMODB_TABLE',
    'S3_BUCKET_RAW',
    'S3_BUCKET_PROCESSED',
    'S3_BUCKET_ARCHIVE',
    'REGION',
    'WHATSAPP_SECRET_NAME',
    'WEBHOOK_VERIFY_TOKEN',
    'PROCESSOR_FUNCTION_NAME',
    'SNS_ALERT_TOPIC_ARN'
]

ORCHESTRATOR_PRESERVED_ENV_VARS = [
    'DYNAMODB_TABLE',
    'REGION',
    'DOCUMENT_PROCESSOR_FUNCTION',
    'VOICE_AGENT_FUNCTION',
    'CREDIT_CALCULATOR_FUNCTION',
    'KNOWLEDGE_BASE_FUNCTION',
    'KNOWLEDGE_BASE_ID'
]

# Expected baseline values from UNFIXED infrastructure
# These are captured from the infrastructure_stack.py
EXPECTED_ROUTER_BASELINE = {
    'DYNAMODB_TABLE': 'KisanSetuData',
    'WEBHOOK_VERIFY_TOKEN': 'kisan-setu-verify-2026',
    'WHATSAPP_SECRET_NAME': 'kisan-setu/whatsapp/credentials'
}

EXPECTED_ORCHESTRATOR_BASELINE = {
    'DYNAMODB_TABLE': 'KisanSetuData',
    'KNOWLEDGE_BASE_ID': ''
}


def get_orchestrator_lambda_name():
    """
    Find the orchestrator Lambda function name.
    
    The actual deployed name will be something like:
    "KisanSetuMVPStack-BedrockOrchestratorXXXXXXXX-YYYYYYYY"
    """
    try:
        response = lambda_client.list_functions()
        
        for function in response['Functions']:
            if 'BedrockOrchestrator' in function['FunctionName']:
                return function['FunctionName']
        
        while 'NextMarker' in response:
            response = lambda_client.list_functions(Marker=response['NextMarker'])
            for function in response['Functions']:
                if 'BedrockOrchestrator' in function['FunctionName']:
                    return function['FunctionName']
        
        raise ValueError("BedrockOrchestrator Lambda function not found")
    
    except Exception as e:
        pytest.skip(f"Could not find orchestrator Lambda: {str(e)}")


@pytest.mark.integration
def test_preservation_router_lambda_non_buggy_env_vars_unchanged():
    """
    Property 2: Preservation - Router Lambda Non-Buggy Environment Variables Unchanged
    
    **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**
    
    This test verifies that all environment variables in the router Lambda that are
    NOT part of the four buggy variables remain unchanged after the fix.
    
    Expected behavior on UNFIXED infrastructure:
    - Test PASSES (establishes baseline)
    - All non-buggy environment variables have expected values
    
    Expected behavior on FIXED infrastructure:
    - Test PASSES (confirms no regressions)
    - All non-buggy environment variables still have the same values
    """
    router_function_name = get_router_lambda_name()
    env_vars = get_lambda_environment_variables(router_function_name)
    
    print(f"\n{'='*70}")
    print("PRESERVATION TEST - Router Lambda Non-Buggy Environment Variables")
    print(f"{'='*70}")
    print(f"Router Lambda: {router_function_name}")
    print(f"{'='*70}")
    
    preservation_failures = []
    
    for env_var_name in ROUTER_PRESERVED_ENV_VARS:
        if env_var_name not in env_vars:
            preservation_failures.append(
                f"Missing environment variable: {env_var_name}"
            )
            print(f"\n{env_var_name}: ✗ MISSING")
            continue
        
        actual_value = env_vars[env_var_name]
        print(f"\n{env_var_name}:")
        print(f"  Value: {actual_value}")
        
        # Check against baseline if we have one
        if env_var_name in EXPECTED_ROUTER_BASELINE:
            expected_value = EXPECTED_ROUTER_BASELINE[env_var_name]
            if actual_value == expected_value:
                print(f"  Status: ✓ MATCHES BASELINE")
            else:
                preservation_failures.append(
                    f"{env_var_name}: expected '{expected_value}', got '{actual_value}'"
                )
                print(f"  Status: ✗ DIFFERS FROM BASELINE")
                print(f"  Expected: {expected_value}")
        else:
            # For dynamic values (S3 buckets, ARNs, etc.), just verify they exist
            # and have reasonable format
            if actual_value:
                print(f"  Status: ✓ PRESENT (dynamic value)")
            else:
                preservation_failures.append(
                    f"{env_var_name}: empty or missing value"
                )
                print(f"  Status: ✗ EMPTY")
    
    print(f"\n{'='*70}")
    
    if preservation_failures:
        print(f"PRESERVATION FAILURES: {len(preservation_failures)}")
        print(f"{'='*70}")
        for i, failure in enumerate(preservation_failures, 1):
            print(f"{i}. {failure}")
        print(f"{'='*70}")
        
        pytest.fail(
            f"Preservation test failed: {len(preservation_failures)} environment "
            f"variables changed or missing. See details above."
        )
    else:
        print("PRESERVATION TEST PASSED - All non-buggy environment variables preserved")
        print(f"{'='*70}")


@pytest.mark.integration
def test_preservation_orchestrator_lambda_non_buggy_env_vars_unchanged():
    """
    Property 2: Preservation - Orchestrator Lambda Non-Buggy Environment Variables Unchanged
    
    **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**
    
    This test verifies that all environment variables in the orchestrator Lambda that
    are NOT the buggy SATELLITE_ANALYZER_FUNCTION variable remain unchanged after the fix.
    
    Expected behavior on UNFIXED infrastructure:
    - Test PASSES (establishes baseline)
    - All non-buggy environment variables have expected values
    
    Expected behavior on FIXED infrastructure:
    - Test PASSES (confirms no regressions)
    - All non-buggy environment variables still have the same values
    """
    orchestrator_function_name = get_orchestrator_lambda_name()
    env_vars = get_lambda_environment_variables(orchestrator_function_name)
    
    print(f"\n{'='*70}")
    print("PRESERVATION TEST - Orchestrator Lambda Non-Buggy Environment Variables")
    print(f"{'='*70}")
    print(f"Orchestrator Lambda: {orchestrator_function_name}")
    print(f"{'='*70}")
    
    preservation_failures = []
    
    for env_var_name in ORCHESTRATOR_PRESERVED_ENV_VARS:
        if env_var_name not in env_vars:
            preservation_failures.append(
                f"Missing environment variable: {env_var_name}"
            )
            print(f"\n{env_var_name}: ✗ MISSING")
            continue
        
        actual_value = env_vars[env_var_name]
        print(f"\n{env_var_name}:")
        print(f"  Value: {actual_value}")
        
        # Check against baseline if we have one
        if env_var_name in EXPECTED_ORCHESTRATOR_BASELINE:
            expected_value = EXPECTED_ORCHESTRATOR_BASELINE[env_var_name]
            if actual_value == expected_value:
                print(f"  Status: ✓ MATCHES BASELINE")
            else:
                preservation_failures.append(
                    f"{env_var_name}: expected '{expected_value}', got '{actual_value}'"
                )
                print(f"  Status: ✗ DIFFERS FROM BASELINE")
                print(f"  Expected: {expected_value}")
        else:
            # For dynamic values (function names, etc.), verify they exist
            # and have reasonable format
            if actual_value:
                print(f"  Status: ✓ PRESENT (dynamic value)")
            else:
                preservation_failures.append(
                    f"{env_var_name}: empty or missing value"
                )
                print(f"  Status: ✗ EMPTY")
    
    print(f"\n{'='*70}")
    
    if preservation_failures:
        print(f"PRESERVATION FAILURES: {len(preservation_failures)}")
        print(f"{'='*70}")
        for i, failure in enumerate(preservation_failures, 1):
            print(f"{i}. {failure}")
        print(f"{'='*70}")
        
        pytest.fail(
            f"Preservation test failed: {len(preservation_failures)} environment "
            f"variables changed or missing. See details above."
        )
    else:
        print("PRESERVATION TEST PASSED - All non-buggy environment variables preserved")
        print(f"{'='*70}")


@pytest.mark.integration
@given(env_var_name=st.sampled_from(ROUTER_PRESERVED_ENV_VARS))
@settings(
    max_examples=len(ROUTER_PRESERVED_ENV_VARS),
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_preservation_property_router_env_vars_remain_unchanged(env_var_name):
    """
    Property 2: Preservation - Router Environment Variables Remain Unchanged (Property-Based)
    
    **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**
    
    This property-based test generates test cases for each non-buggy environment
    variable in the router Lambda, verifying that they remain unchanged.
    
    Property: For all environment variables NOT in the buggy set, the value should
    remain consistent with the baseline infrastructure configuration.
    """
    router_function_name = get_router_lambda_name()
    env_vars = get_lambda_environment_variables(router_function_name)
    
    print(f"\n{'='*70}")
    print(f"Testing preservation of: {env_var_name}")
    print(f"{'='*70}")
    
    # Verify the environment variable exists
    if env_var_name not in env_vars:
        pytest.fail(
            f"Preservation property violated: {env_var_name} is missing from "
            f"router Lambda environment variables"
        )
    
    actual_value = env_vars[env_var_name]
    print(f"Value: {actual_value}")
    
    # Check against baseline if available
    if env_var_name in EXPECTED_ROUTER_BASELINE:
        expected_value = EXPECTED_ROUTER_BASELINE[env_var_name]
        if actual_value != expected_value:
            pytest.fail(
                f"Preservation property violated: {env_var_name} changed from "
                f"'{expected_value}' to '{actual_value}'"
            )
        print(f"✓ Matches baseline: {expected_value}")
    else:
        # For dynamic values, verify they're not empty and have reasonable format
        if not actual_value:
            pytest.fail(
                f"Preservation property violated: {env_var_name} is empty"
            )
        
        # Verify format based on variable type
        if 'FUNCTION_NAME' in env_var_name:
            # Should be a physical function name with stack prefix and hash
            if '-' not in actual_value or len(actual_value) < 20:
                pytest.fail(
                    f"Preservation property violated: {env_var_name} has invalid "
                    f"function name format: '{actual_value}'"
                )
            print(f"✓ Valid function name format")
        elif 'BUCKET' in env_var_name:
            # Should be a valid S3 bucket name
            if not actual_value.startswith('kisan-setu-'):
                pytest.fail(
                    f"Preservation property violated: {env_var_name} has invalid "
                    f"bucket name format: '{actual_value}'"
                )
            print(f"✓ Valid bucket name format")
        elif 'ARN' in env_var_name:
            # Should be a valid ARN
            if not actual_value.startswith('arn:aws:'):
                pytest.fail(
                    f"Preservation property violated: {env_var_name} has invalid "
                    f"ARN format: '{actual_value}'"
                )
            print(f"✓ Valid ARN format")
        else:
            print(f"✓ Present (dynamic value)")
    
    print(f"{'='*70}")


@pytest.mark.integration
@given(env_var_name=st.sampled_from(ORCHESTRATOR_PRESERVED_ENV_VARS))
@settings(
    max_examples=len(ORCHESTRATOR_PRESERVED_ENV_VARS),
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_preservation_property_orchestrator_env_vars_remain_unchanged(env_var_name):
    """
    Property 2: Preservation - Orchestrator Environment Variables Remain Unchanged (Property-Based)
    
    **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**
    
    This property-based test generates test cases for each non-buggy environment
    variable in the orchestrator Lambda, verifying that they remain unchanged.
    
    Property: For all environment variables NOT in the buggy set, the value should
    remain consistent with the baseline infrastructure configuration.
    """
    orchestrator_function_name = get_orchestrator_lambda_name()
    env_vars = get_lambda_environment_variables(orchestrator_function_name)
    
    print(f"\n{'='*70}")
    print(f"Testing preservation of: {env_var_name}")
    print(f"{'='*70}")
    
    # Verify the environment variable exists
    if env_var_name not in env_vars:
        pytest.fail(
            f"Preservation property violated: {env_var_name} is missing from "
            f"orchestrator Lambda environment variables"
        )
    
    actual_value = env_vars[env_var_name]
    print(f"Value: {actual_value}")
    
    # Check against baseline if available
    if env_var_name in EXPECTED_ORCHESTRATOR_BASELINE:
        expected_value = EXPECTED_ORCHESTRATOR_BASELINE[env_var_name]
        if actual_value != expected_value:
            pytest.fail(
                f"Preservation property violated: {env_var_name} changed from "
                f"'{expected_value}' to '{actual_value}'"
            )
        print(f"✓ Matches baseline: {expected_value}")
    else:
        # For dynamic values, verify they're not empty (except KNOWLEDGE_BASE_ID which can be empty)
        if not actual_value and env_var_name != 'KNOWLEDGE_BASE_ID':
            pytest.fail(
                f"Preservation property violated: {env_var_name} is empty"
            )
        
        # Verify format based on variable type
        if 'FUNCTION' in env_var_name:
            # Should be a physical function name with stack prefix and hash
            if '-' not in actual_value or len(actual_value) < 20:
                pytest.fail(
                    f"Preservation property violated: {env_var_name} has invalid "
                    f"function name format: '{actual_value}'"
                )
            print(f"✓ Valid function name format")
        elif env_var_name == 'KNOWLEDGE_BASE_ID':
            # Can be empty initially
            print(f"✓ Present (can be empty initially)")
        else:
            print(f"✓ Present (dynamic value)")
    
    print(f"{'='*70}")


@pytest.mark.integration
def test_preservation_summary():
    """
    Summary test that documents all preserved environment variables.
    
    This test provides a comprehensive report of preservation across both
    router and orchestrator Lambda functions.
    """
    router_function_name = get_router_lambda_name()
    router_env_vars = get_lambda_environment_variables(router_function_name)
    
    orchestrator_function_name = get_orchestrator_lambda_name()
    orchestrator_env_vars = get_lambda_environment_variables(orchestrator_function_name)
    
    print(f"\n{'='*70}")
    print("PRESERVATION TEST - SUMMARY")
    print(f"{'='*70}")
    
    # Router Lambda
    print(f"\nRouter Lambda: {router_function_name}")
    print(f"{'='*70}")
    
    router_failures = []
    for env_var_name in ROUTER_PRESERVED_ENV_VARS:
        if env_var_name not in router_env_vars:
            print(f"{env_var_name}: ✗ MISSING")
            router_failures.append(f"Router: {env_var_name} missing")
        else:
            value = router_env_vars[env_var_name]
            print(f"{env_var_name}: ✓ {value}")
    
    # Orchestrator Lambda
    print(f"\nOrchestrator Lambda: {orchestrator_function_name}")
    print(f"{'='*70}")
    
    orchestrator_failures = []
    for env_var_name in ORCHESTRATOR_PRESERVED_ENV_VARS:
        if env_var_name not in orchestrator_env_vars:
            print(f"{env_var_name}: ✗ MISSING")
            orchestrator_failures.append(f"Orchestrator: {env_var_name} missing")
        else:
            value = orchestrator_env_vars[env_var_name]
            print(f"{env_var_name}: ✓ {value}")
    
    # Summary
    all_failures = router_failures + orchestrator_failures
    
    print(f"\n{'='*70}")
    print(f"PRESERVATION FAILURES: {len(all_failures)}")
    print(f"{'='*70}")
    
    if all_failures:
        for i, failure in enumerate(all_failures, 1):
            print(f"{i}. {failure}")
        
        print(f"\n{'='*70}")
        print("CONCLUSION: Preservation test failed - some environment variables changed")
        print(f"{'='*70}")
        
        pytest.fail(
            f"Preservation test failed: {len(all_failures)} environment variables "
            f"changed or missing. See details above."
        )
    else:
        print("\nCONCLUSION: All non-buggy environment variables preserved")
        print(f"{'='*70}")

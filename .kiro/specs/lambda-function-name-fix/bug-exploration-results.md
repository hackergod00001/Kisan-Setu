# Bug Condition Exploration Results

## Test Execution Summary

**Date**: 2025-01-XX  
**Test File**: `kisan-setu-mvp/tests/test_bug_lambda_function_name_fix.py`  
**Infrastructure State**: UNFIXED  
**Test Status**: ✓ PASSED (Bug confirmed - tests failed as expected)

## Bug Confirmation

The bug condition exploration test successfully confirmed the existence of the bug described in the bugfix specification. All four environment variables in the router Lambda contain hardcoded logical function names instead of CDK-generated physical function names.

## Deployed Router Lambda

**Function Name**: `KisanSetuMVPStack-MessageRouter8CD84FD1-h6L1m4kKPfOf`

This is the actual CDK-generated physical name with:
- Stack prefix: `KisanSetuMVPStack`
- Construct ID: `MessageRouter`
- Hash: `8CD84FD1`
- Random suffix: `h6L1m4kKPfOf`

## Counterexamples Found

### 1. BEDROCK_ORCHESTRATOR_FUNCTION

**Environment Variable Value**: `BedrockOrchestrator`  
**Status**: ✗ HARDCODED (bug)  
**Function Exists**: ✗ No (Function not found)

**Issue**: The environment variable contains the hardcoded string "BedrockOrchestrator" instead of the physical function name like "KisanSetuMVPStack-BedrockOrchestratorXXXXXXXX-YYYYYYYY".

**Impact**: When the router Lambda attempts to invoke this function, it fails with "Function not found" error because no Lambda function with the name "BedrockOrchestrator" exists.

### 2. VOICE_AGENT_FUNCTION

**Environment Variable Value**: `VoiceHandler`  
**Status**: ✗ HARDCODED (bug)  
**Function Exists**: ✗ No (Function not found)

**Issue**: The environment variable contains the hardcoded string "VoiceHandler" instead of the physical function name.

**Impact**: Voice message routing fails because the Lambda function cannot be found.

### 3. CREDIT_CALCULATOR_FUNCTION

**Environment Variable Value**: `CreditCalculator`  
**Status**: ✗ HARDCODED (bug)  
**Function Exists**: ✗ No (Function not found)

**Issue**: The environment variable contains the hardcoded string "CreditCalculator" instead of the physical function name.

**Impact**: Credit calculation requests fail because the Lambda function cannot be found.

### 4. SATELLITE_ANALYZER_FUNCTION

**Environment Variable Value**: `SatelliteAnalyzer`  
**Status**: ✗ HARDCODED (bug)  
**Function Exists**: ✗ No (Function not found)

**Issue**: The environment variable contains the hardcoded string "SatelliteAnalyzer" instead of the physical function name.

**Impact**: Satellite analysis requests fail because the Lambda function cannot be found.

## Total Counterexamples: 8

1. BEDROCK_ORCHESTRATOR_FUNCTION=BedrockOrchestrator (hardcoded)
2. Lambda invocation fails for BEDROCK_ORCHESTRATOR_FUNCTION: Function not found
3. VOICE_AGENT_FUNCTION=VoiceHandler (hardcoded)
4. Lambda invocation fails for VOICE_AGENT_FUNCTION: Function not found
5. CREDIT_CALCULATOR_FUNCTION=CreditCalculator (hardcoded)
6. Lambda invocation fails for CREDIT_CALCULATOR_FUNCTION: Function not found
7. SATELLITE_ANALYZER_FUNCTION=SatelliteAnalyzer (hardcoded)
8. Lambda invocation fails for SATELLITE_ANALYZER_FUNCTION: Function not found

## Root Cause Confirmation

The test results confirm the hypothesized root cause in the design document:

**File**: `kisan-setu-mvp/infrastructure_stack.py`  
**Location**: Router Lambda environment variable configuration

The CDK infrastructure stack sets environment variables using hardcoded string literals:

```python
environment={
    # ... other variables ...
    "VOICE_AGENT_FUNCTION": "VoiceHandler",  # ✗ HARDCODED
    "BEDROCK_ORCHESTRATOR_FUNCTION": "BedrockOrchestrator",  # ✗ HARDCODED
    "CREDIT_CALCULATOR_FUNCTION": "CreditCalculator",  # ✗ HARDCODED
    "SATELLITE_ANALYZER_FUNCTION": "SatelliteAnalyzer",  # ✗ HARDCODED
}
```

Instead of using Lambda construct references:

```python
environment={
    # ... other variables ...
    "VOICE_AGENT_FUNCTION": voice_lambda.function_name,  # ✓ CORRECT
    "BEDROCK_ORCHESTRATOR_FUNCTION": orchestrator_lambda.function_name,  # ✓ CORRECT
    "CREDIT_CALCULATOR_FUNCTION": credit_lambda.function_name,  # ✓ CORRECT
    "SATELLITE_ANALYZER_FUNCTION": satellite_lambda.function_name,  # ✓ CORRECT
}
```

## Test Behavior

### Expected Behavior (UNFIXED Infrastructure)

✓ **Test FAILS** - This is the CORRECT outcome for unfixed infrastructure  
✓ Confirms bug exists  
✓ Documents counterexamples  
✓ Validates root cause hypothesis

### Expected Behavior (FIXED Infrastructure)

After implementing the fix:
- Test should PASS
- Environment variables should contain physical function names
- Lambda invocations should succeed
- No "Function not found" errors

## Next Steps

1. ✓ **Task 1 Complete**: Bug condition exploration test written and executed
2. **Task 2**: Write preservation property tests (before implementing fix)
3. **Task 3**: Implement the fix in infrastructure_stack.py
4. **Task 3.5**: Re-run this test on FIXED infrastructure (should pass)
5. **Task 3.6**: Verify preservation tests still pass

## Test Files

- **Test File**: `kisan-setu-mvp/tests/test_bug_lambda_function_name_fix.py`
- **Results File**: `.kiro/specs/lambda-function-name-fix/bug-exploration-results.md` (this file)

## Validation

This test validates the following requirements from bugfix.md:

- **Requirement 1.1**: BEDROCK_ORCHESTRATOR_FUNCTION bug confirmed
- **Requirement 1.2**: VOICE_AGENT_FUNCTION bug confirmed
- **Requirement 1.3**: CREDIT_CALCULATOR_FUNCTION bug confirmed
- **Requirement 1.4**: SATELLITE_ANALYZER_FUNCTION bug confirmed

All requirements validated with concrete counterexamples from deployed infrastructure.

# Code Audit Bugfixes Design

## Overview

Seven bugs were discovered during a line-by-line code audit of the Kisan Setu MVP. They fall into four categories: (A) stale model-name references in comments/docstrings, (B) dead code, (C) missing Lambda environment variables for KMS encryption and DynamoDB access, and (D) an unused GraphQL mutation argument. The fix strategy is purely additive for env vars, purely subtractive for dead code and the unused arg, and text-only for the comment corrections. No runtime logic changes are required.

## Glossary

- **Bug_Condition (C)**: The condition that triggers each bug — stale comment text, dead code presence, missing env var in CDK definition, or superfluous GraphQL argument
- **Property (P)**: The desired state after the fix — correct comments, no dead code, all required env vars present, clean mutation signature
- **Preservation**: All existing runtime behavior, model routing logic, resolver key logic, and other Lambda env vars must remain unchanged
- **`encryption_key.key_id`**: The CDK KMS key reference already available in `infrastructure_stack.py`, used by Processor/Credit/Orchestrator/Sync Lambdas
- **`INDIA_BOUNDS`**: An unused dictionary in `satellite_analyzer.py` (lines 56-60); `satellite_mock.py` has its own separate copy
- **`TransactionInput`**: The GraphQL input type that already contains `transactionId` as a field

## Bug Details

### Bug Condition

The bugs manifest across four files when any of the following conditions hold:

1. A developer reads the `BedrockOrchestrator` class docstring or the `COMPLEX_PATTERNS` comment or the `select_model()` cost-threshold log message in `orchestrator.py` and sees incorrect model names (Opus 4.6 / Sonnet 4 / Haiku 4.5 instead of Nova Pro / Nova Lite).
2. The `satellite_analyzer.py` module is loaded and defines `INDIA_BOUNDS` (lines 56-60) which is never referenced.
3. The VoiceHandler, Router, SatelliteAnalyzer, or KnowledgeBase Lambda functions are deployed without `KMS_KEY_ID` (and KnowledgeBase also without `DYNAMODB_TABLE`).
4. A client calls `updateTransaction(transactionId: ID!, input: TransactionInput!)` and must supply a top-level `transactionId` that the resolver completely ignores.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type {file, location, content}
  OUTPUT: boolean

  RETURN (
    (input.file == "orchestrator.py"
      AND input.content MATCHES /Opus 4\.6|Sonnet 4(?! v2)|Haiku 4\.5/)
    OR
    (input.file == "satellite_analyzer.py"
      AND input.content DEFINES "INDIA_BOUNDS"
      AND NOT input.content REFERENCES "INDIA_BOUNDS")
    OR
    (input.file == "infrastructure_stack.py"
      AND input.lambdaName IN ["VoiceHandler", "MessageRouter", "SatelliteAnalyzer", "KnowledgeBase"]
      AND "KMS_KEY_ID" NOT IN input.environmentVariables)
    OR
    (input.file == "infrastructure_stack.py"
      AND input.lambdaName == "KnowledgeBase"
      AND "DYNAMODB_TABLE" NOT IN input.environmentVariables)
    OR
    (input.file == "schema.graphql"
      AND input.mutation == "updateTransaction"
      AND input.args CONTAINS "transactionId: ID!")
  )
END FUNCTION
```

### Examples

- Reading `orchestrator.py` line 99: sees `# Complex queries → Opus 4.6 (deep reasoning)` — should say `Nova Pro`
- Reading `orchestrator.py` class docstring (line ~392): sees `Primary (Opus 4.6)` — should say `Primary (Nova Pro)`
- Reading `orchestrator.py` select_model log (line ~378): sees `Forcing secondary (Haiku 4.5)` — should say `Forcing secondary (Nova Lite)`
- Loading `satellite_analyzer.py`: `INDIA_BOUNDS` dict defined but grep shows zero references in the file
- Deploying VoiceHandler Lambda: env vars lack `KMS_KEY_ID`, so any code path calling `kms.decrypt()` will fail with a missing key error
- Deploying KnowledgeBase Lambda: env vars lack both `KMS_KEY_ID` and `DYNAMODB_TABLE`
- Calling `updateTransaction(transactionId: "tx-123", input: {...})`: the `transactionId` arg is ignored; resolver uses `input.farmerId` + `input.timestamp`

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- The LLMAdapter fallback chain (Nova Pro → Nova Lite → Claude 3.7 Sonnet → Claude 3.5 Sonnet v2 → Claude 3 Haiku) and all model routing logic remain identical
- `satellite_analyzer.py` runtime behavior (NDVI analysis, Sentinel-2 processing) is completely unaffected
- Processor, Credit, Orchestrator, and SyncHandler Lambdas retain all their existing environment variables including `KMS_KEY_ID`
- The `createTransaction` and `syncOfflineTransactions` mutations remain unchanged
- The `updateTransaction` resolver continues to use `input.farmerId` and `input.timestamp` as the DynamoDB composite key
- The Router Lambda retains all existing env vars (`DYNAMODB_TABLE`, S3 buckets, `REGION`, function names, etc.)
- `satellite_mock.py` retains its own separate `INDIA_BOUNDS` definition

**Scope:**
Only comments/docstrings, dead code, CDK environment blocks, and the GraphQL schema mutation signature are modified. No runtime logic is touched.

## Hypothesized Root Cause

Based on the code audit findings:

1. **Stale Model Names (#51)**: The orchestrator was originally written targeting Claude models (Opus/Sonnet/Haiku). When the project switched to Amazon Nova models, the `MODEL_TIERS` dict and module-level docstring were updated but three locations were missed: the class docstring, the `COMPLEX_PATTERNS` comment, and the `select_model()` log message.

2. **Dead Code (#52)**: `INDIA_BOUNDS` was likely defined during initial development of `satellite_analyzer.py` but the validation logic that used it was either removed or moved to `satellite_mock.py`, leaving the definition orphaned.

3. **Missing Env Vars (#53-#56)**: The `KMS_KEY_ID` env var was added to Lambdas that were identified early as needing encryption (Processor, Credit, Orchestrator, Sync) but was missed for VoiceHandler, Router, SatelliteAnalyzer, and KnowledgeBase. The KnowledgeBase Lambda also lacks `DYNAMODB_TABLE` because it was originally designed as a pure Bedrock KB query function, but later gained DynamoDB access needs.

4. **Unused GraphQL Arg (#35)**: The `updateTransaction` mutation was likely modeled after a pattern where the ID is passed separately from the input. However, the resolver was implemented to pull `transactionId` from `TransactionInput`, making the top-level arg redundant.

## Correctness Properties

Property 1: Bug Condition - Stale Model Names Corrected

_For any_ comment, docstring, or log message in `orchestrator.py` that previously referenced "Opus 4.6", "Sonnet 4", or "Haiku 4.5", the fixed file SHALL reference "Nova Pro" or "Nova Lite" as appropriate, matching the actual `MODEL_TIERS` configuration.

**Validates: Requirements 2.1, 2.2, 2.3**

Property 2: Bug Condition - Dead Code Removed

_For any_ module-level definition in `satellite_analyzer.py`, the fixed file SHALL NOT contain the `INDIA_BOUNDS` dictionary definition.

**Validates: Requirements 2.4**

Property 3: Bug Condition - Missing Env Vars Added

_For any_ Lambda function definition in `infrastructure_stack.py` for VoiceHandler, MessageRouter, SatelliteAnalyzer, or KnowledgeBase, the fixed CDK stack SHALL include `KMS_KEY_ID` set to `encryption_key.key_id` in the environment block. Additionally, KnowledgeBase SHALL include `DYNAMODB_TABLE` set to `"KisanSetuData"`.

**Validates: Requirements 2.5, 2.6, 2.7, 2.8**

Property 4: Bug Condition - Unused GraphQL Arg Removed

_For any_ call to the `updateTransaction` mutation in `schema.graphql`, the fixed schema SHALL accept only `input: TransactionInput!` without a separate `transactionId: ID!` argument.

**Validates: Requirements 2.9**

Property 5: Preservation - Runtime Logic Unchanged

_For any_ input that does NOT match the bug condition (i.e., actual model routing, satellite analysis, existing Lambda env vars, createTransaction/syncOfflineTransactions mutations), the fixed code SHALL produce exactly the same behavior as the original code.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7**

## Fix Implementation

### Changes Required

Assuming our root cause analysis is correct:

**File**: `kisan-setu-mvp/lambda/orchestrator/orchestrator.py`

**Specific Changes**:
1. **Class docstring (line ~392-395)**: Replace `Opus 4.6` → `Nova Pro`, `Sonnet 4` → `Nova Pro`, `Haiku 4.5` → `Nova Lite`
2. **COMPLEX_PATTERNS comment (line 99)**: Replace `# Complex queries → Opus 4.6 (deep reasoning)` → `# Complex queries → Nova Pro (deep reasoning)`
3. **select_model() log message (line ~378)**: Replace `Forcing secondary (Haiku 4.5)` → `Forcing secondary (Nova Lite)`

**File**: `kisan-setu-mvp/lambda/satellite/satellite_analyzer.py`

**Specific Changes**:
4. **Remove INDIA_BOUNDS (lines 56-60)**: Delete the `INDIA_BOUNDS = { ... }` dictionary definition and its preceding comment

**File**: `kisan-setu-mvp/infrastructure_stack.py`

**Specific Changes**:
5. **VoiceHandler Lambda**: Add `"KMS_KEY_ID": encryption_key.key_id` to the environment dict
6. **MessageRouter Lambda**: Add `"KMS_KEY_ID": encryption_key.key_id` to the environment dict
7. **SatelliteAnalyzer Lambda**: Add `"KMS_KEY_ID": encryption_key.key_id` to the environment dict
8. **KnowledgeBase Lambda**: Add `"KMS_KEY_ID": encryption_key.key_id` and `"DYNAMODB_TABLE": "KisanSetuData"` to the environment dict

**File**: `kisan-setu-mvp/schema.graphql`

**Specific Changes**:
9. **updateTransaction mutation**: Change `updateTransaction(transactionId: ID!, input: TransactionInput!): Transaction` → `updateTransaction(input: TransactionInput!): Transaction`

**File**: `kisan-setu-mvp/infrastructure_stack.py` (resolver)

**Specific Changes**:
10. **UpdateTransactionResolver**: No resolver change needed — the resolver already uses `$ctx.args.input.farmerId` and `$ctx.args.input.timestamp` as keys and never references `$ctx.args.transactionId`

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate the bugs on unfixed code, then verify the fixes work correctly and preserve existing behavior.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the bugs BEFORE implementing the fix. Confirm or refute the root cause analysis.

**Test Plan**: Write static analysis tests that grep/parse the source files for the buggy patterns. Run on UNFIXED code to confirm the bugs exist.

**Test Cases**:
1. **Stale Model Names Test**: Grep `orchestrator.py` for `Opus 4.6`, `Sonnet 4`, `Haiku 4.5` — expect matches on unfixed code (will fail assertion that they should NOT exist)
2. **Dead Code Test**: Parse `satellite_analyzer.py` AST for `INDIA_BOUNDS` definition and check for zero references — expect definition found with no references
3. **Missing Env Vars Test**: Parse `infrastructure_stack.py` CDK constructs and assert `KMS_KEY_ID` present in VoiceHandler/Router/Satellite/Knowledge env blocks — expect failures on unfixed code
4. **Unused Arg Test**: Parse `schema.graphql` and assert `updateTransaction` has no `transactionId` arg — expect failure on unfixed code

**Expected Counterexamples**:
- `orchestrator.py` line 99 contains "Opus 4.6", line 378 contains "Haiku 4.5", lines 392-394 contain all three stale names
- `satellite_analyzer.py` lines 56-60 define `INDIA_BOUNDS` with zero references
- `infrastructure_stack.py` VoiceHandler/Router/Satellite/Knowledge Lambda env blocks lack `KMS_KEY_ID`
- `schema.graphql` `updateTransaction` mutation has `transactionId: ID!` arg

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed code produces the expected behavior.

**Pseudocode:**
```
FOR ALL location WHERE isBugCondition(location) DO
  result := readFixedFile(location)
  ASSERT expectedContent(result)
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed code produces the same result as the original code.

**Pseudocode:**
```
FOR ALL location WHERE NOT isBugCondition(location) DO
  ASSERT readOriginalFile(location) == readFixedFile(location)
END FOR
```

**Testing Approach**: Since these are static code changes (no runtime logic modifications), preservation checking focuses on verifying that unchanged code sections remain identical and that CDK synth output for unaffected Lambdas is unchanged.

**Test Cases**:
1. **Model Routing Preservation**: Verify `MODEL_TIERS` dict values, `SIMPLE_PATTERNS`, `COMPLEX_PATTERNS` regex lists, and `select_model()` logic are unchanged
2. **Satellite Runtime Preservation**: Verify all functions in `satellite_analyzer.py` remain unchanged; only the dead `INDIA_BOUNDS` definition is removed
3. **Existing Env Vars Preservation**: Verify Processor/Credit/Orchestrator/Sync Lambda env blocks are unchanged; VoiceHandler/Router/Satellite/Knowledge retain all existing env vars
4. **Other Mutations Preservation**: Verify `createTransaction` and `syncOfflineTransactions` mutation signatures are unchanged
5. **Resolver Preservation**: Verify `UpdateTransactionResolver` request/response mapping templates are unchanged

### Unit Tests

- Assert `orchestrator.py` contains no occurrences of "Opus 4.6", "Sonnet 4" (standalone), or "Haiku 4.5"
- Assert `satellite_analyzer.py` does not define `INDIA_BOUNDS`
- Assert all 4 Lambda env blocks in `infrastructure_stack.py` include `KMS_KEY_ID`
- Assert KnowledgeBase Lambda env block includes `DYNAMODB_TABLE`
- Assert `schema.graphql` `updateTransaction` mutation signature is `updateTransaction(input: TransactionInput!): Transaction`

### Property-Based Tests

- Generate random file content searches across `orchestrator.py` and verify no stale model name patterns match
- Generate random Lambda function name selections from the CDK stack and verify all include `KMS_KEY_ID` in their environment
- Generate random GraphQL mutation calls to `updateTransaction` with only `input` arg and verify schema acceptance

### Integration Tests

- Run `cdk synth` and verify the CloudFormation template includes `KMS_KEY_ID` for all 8 Lambda functions (4 existing + 4 newly added)
- Run `cdk synth` and verify KnowledgeBase Lambda has both `KMS_KEY_ID` and `DYNAMODB_TABLE`
- Validate the GraphQL schema parses correctly after removing the `transactionId` arg from `updateTransaction`

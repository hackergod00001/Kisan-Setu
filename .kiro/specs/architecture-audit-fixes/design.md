# Architecture Audit Fixes — Bugfix Design

## Overview

A senior architect audit (March 14, 2026) of the Kisan-Setu MVP serverless application identified 28 defects spanning silent failure paths, security vulnerabilities, data integrity issues, credit score inaccuracies, and dead code. This design formalizes the bug conditions, preservation requirements, root cause analysis, and fix strategy across 5 phases: Critical Fixes, Security Hardening, Robustness, Credit Score Accuracy, and Cleanup.

The fix approach is incremental and phase-ordered — each phase can be deployed independently. All fixes target the CDK stack (`infrastructure_stack.py`), Lambda handlers, and shared modules under `lambda/common/`.

## Glossary

- **Bug_Condition (C)**: Any of the 28 identified defect conditions — missing env vars, hardcoded regions, public endpoints, per-invocation instantiation, dead code, score miscalculations, etc.
- **Property (P)**: The correct behavior for each defect — env vars present, region-dynamic ARNs, authenticated endpoints, module-level caching, accurate scores, no dead code.
- **Preservation**: Existing working behaviors that must remain unchanged — webhook verification, LLM tiered routing, deduplication, offline sync conflict resolution, voice transcription language support, non-affected credit sub-components.
- **infrastructure_stack.py**: CDK stack defining all Lambda functions, API Gateway, AppSync, S3 dashboard bucket, and SNS topic.
- **DynamoDBAccess**: Centralized data access class in `lambda/common/dynamodb_access.py` providing CRUD with audit trails and validation.
- **CreditEngine**: Credit scoring class in `lambda/credit/credit.py` calculating 0-100 reliability scores across 5 components.
- **LLMAdapter**: Model invocation adapter in `lambda/common/llm_adapter.py` with 5-model fallback chain and circuit breakers.
- **BedrockOrchestrator**: Main AI orchestration class in `lambda/orchestrator/orchestrator.py` handling text message processing.

## Bug Details

### Bug Condition

The 28 defects manifest across 5 categories. The overarching bug condition is: the system contains configuration errors, security gaps, robustness issues, scoring inaccuracies, and dead code that cause silent failures, data exposure, unbounded growth, incorrect scores, and deployment bloat.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type SystemConfiguration | Request | CreditInput | DeploymentPackage
  OUTPUT: boolean

  // Phase 1: Critical
  RETURN (input.lambda == 'VoiceHandler' AND 'BEDROCK_ORCHESTRATOR_FUNCTION' NOT IN input.envVars)
      OR (input.lambda == 'KnowledgeBase' AND input.regionDefault == 'us-east-1')
      OR (input.endpoint IN ['/process', '/credit', '/knowledge'] AND input.authMethod == NONE)
      OR (input.lambda == 'Orchestrator' AND input.instantiationScope == 'per-invocation')

  // Phase 2: Security
      OR (input.sensitiveWrite == true AND input.encryptionApplied == false)
      OR (input.resource == 'DashboardBucket' AND input.publicReadAccess == true)
      OR (input.resource == 'AppSyncAPI' AND input.authType == 'API_KEY')
      OR (input.messageType == 'text' AND input.sanitized == false)
      OR (input.sender != null AND input.rateLimitApplied == false)

  // Phase 3: Robustness
      OR (input.handler IN ['router','orchestrator','credit','satellite','sync'] AND input.usesDynamoDBAccess == false)
      OR (input.lambda == 'Orchestrator' AND input.timeout < input.calleeMaxTimeout)
      OR (input.circuitBreakerScope == 'per-invocation')
      OR (input.conversationItem == true AND input.ttlAttribute == null)
      OR (input.dashboardScale != input.backendScale)

  // Phase 4: Credit Score
      OR (input.method == '_calculate_dues_score' AND input.returnsHardcoded == true)
      OR (input.method == 'calculate_financial_behavior' AND input.maxReachable < 15.0)
      OR (input.statusField == 'fulfilled' AND input.otherStatusField == 'success')
      OR (input.envVarRead == 'DYNAMODB_TABLE_NAME' AND input.envVarSet == 'DYNAMODB_TABLE')

  // Phase 5: Cleanup
      OR (input.file IN ['sync_manager.py','_invoke_model','_invoke_fallback','error_handler_example.py','webhook_handler.py'] AND input.isDeadCode == true)
      OR (input.class IN ['MetaWhatsAppInterface','SatelliteAnalyzer','CreditEngine'] AND input.cachingScope == 'per-invocation')
      OR (input.lambda IN ['KnowledgeBase','SyncHandler'] AND 'SNS_ALERT_TOPIC_ARN' NOT IN input.envVars)
END FUNCTION
```

### Examples

- **1.1 VoiceHandler env var**: VoiceHandler invoked directly → reads `os.environ.get('BEDROCK_ORCHESTRATOR_FUNCTION')` → gets `None` → transcription succeeds but AI response never sent. Expected: env var present, orchestrator invoked.
- **1.2 Knowledge Base region**: KnowledgeBase Lambda starts → `bedrock_agent_runtime` client created with `us-east-1` → MODEL_ARN hardcoded to `us-east-1` → cross-region error when KB is in `ap-south-1`. Expected: region defaults to `ap-south-1`.
- **1.3 No API auth**: Attacker sends POST to `/credit?farmer_id=F001` → receives full credit score with no authentication. Expected: 403 without API key.
- **1.4 Per-invocation orchestrator**: Lambda warm invocation → new `BedrockOrchestrator()` created → circuit breaker state lost → failed model retried every time. Expected: module-level instance preserved across warm invocations.
- **1.15 Hardcoded dues score**: `_calculate_dues_score('any_farmer')` → returns 4.5 always → every farmer gets perfect dues score. Expected: query DynamoDB for actual outstanding dues.
- **1.17 Status inconsistency**: Transaction with `status='completed'` → `_calculate_fulfillment_score` defaults to `'fulfilled'` (mismatch, counts as unfulfilled) → `_calculate_success_score` defaults to `'success'` (mismatch, counts as unsuccessful). Expected: single consistent status value.
- **1.18 Env var mismatch**: `DynamoDBAccess` reads `DYNAMODB_TABLE_NAME` → not set → falls back to `'KisanSetuData'` → works by coincidence. CDK sets `DYNAMODB_TABLE`. Expected: `DynamoDBAccess` reads `DYNAMODB_TABLE`.

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Router-to-VoiceHandler event-based path (`orchestrator_function` in payload) must continue to work — the env var fix adds a fallback, not a replacement (Req 3.1)
- Knowledge Base retrieval and generation with valid `KNOWLEDGE_BASE_ID` must continue to function (Req 3.2)
- `/webhook` endpoint Meta verification (challenge-response) must remain unaffected by API key changes on other endpoints (Req 3.3)
- LLMAdapter tiered model routing (query complexity → model selection → daily cost threshold) must continue unchanged (Req 3.4)
- Existing unencrypted DynamoDB data must remain readable — encryption integration must handle legacy plaintext gracefully (Req 3.5)
- Dashboard HTML/JS/CSS content and demo data display must remain the same for authenticated users (Req 3.6)
- AppSync `syncOfflineTransactions` last-write-wins conflict resolution must continue working (Req 3.7)
- Normal WhatsApp messages (under length limit, no injection patterns) must process without rejection (Req 3.8)
- Messages sent at normal rates must process without delay or rejection (Req 3.9)
- CreditEngine 5-component model (supply consistency, quality metrics, transaction history, financial behavior, operational transparency) must continue producing scores (Req 3.10)
- Orchestrator calls to CreditCalculator (30s) and KnowledgeBase (60s) must complete within timeout (Req 3.11)
- Router deduplication (`MSGID#{message_id}` / `DEDUP` with 24h TTL) must continue working (Req 3.12)
- Non-affected credit sub-components (`_calculate_frequency_score`, `_calculate_adherence_score`, `_calculate_moisture_score`, etc.) must produce identical scores (Req 3.13)
- Lambda handlers using `os.environ.get('DYNAMODB_TABLE', 'KisanSetuData')` must continue connecting to the correct table (Req 3.14)
- VoiceAgent multi-language support (Hindi, English, Marathi, Tamil) must remain functional (Req 3.15)
- SyncHandler offline transaction processing (sort by timestamp, conflict detection, last-write-wins) must remain functional (Req 3.16)

**Scope:**
All inputs and code paths not directly related to the 28 identified defects must be completely unaffected. This includes all existing Lambda handler logic, DynamoDB access patterns used by handlers directly, AppSync resolver templates, and the WhatsApp webhook verification flow.

## Hypothesized Root Cause

Based on the audit, the root causes fall into clear categories:

1. **CDK Configuration Gaps**: Several Lambda functions are missing environment variables (`BEDROCK_ORCHESTRATOR_FUNCTION` for VoiceHandler, `SNS_ALERT_TOPIC_ARN` for KnowledgeBase/SyncHandler, `KMS_KEY_ID` for encryption). The Router has unused env vars (`CREDIT_CALCULATOR_FUNCTION`, `SATELLITE_ANALYZER_FUNCTION`). These are one-line CDK fixes.

2. **Hardcoded Values Instead of Configuration**: Knowledge Base hardcodes `us-east-1` region and MODEL_ARN. `DynamoDBAccess` reads `DYNAMODB_TABLE_NAME` while CDK sets `DYNAMODB_TABLE`. Credit scoring has hardcoded `_calculate_dues_score()` returning 4.5.

3. **MVP Security Shortcuts**: Dashboard S3 bucket has `public_read_access=True`. API Gateway endpoints have no authentication. AppSync uses API Key auth with no data isolation. No input sanitization or per-user rate limiting.

4. **Anti-Pattern: Per-Invocation Instantiation**: `BedrockOrchestrator`, `MetaWhatsAppInterface`, `SatelliteAnalyzer`, and `CreditEngine` are all created inside `handler()` functions instead of at module level, wasting warm invocation benefits and resetting circuit breaker state.

5. **Incomplete Implementation**: Encryption module exists but is never called in production. `DynamoDBAccess` class exists but all handlers bypass it with direct boto3 calls. Conversation items have no TTL.

6. **Dead Code Accumulation**: `sync_manager.py`, `_invoke_model()`, `_invoke_fallback()`, `error_handler_example.py`, `webhook_handler.py`, and unused Router env vars are all dead code shipped in deployment packages.

7. **Credit Score Logic Errors**: `_calculate_dues_score()` is a TODO stub. `_calculate_payment_score()` maxes at 10.5 and `_calculate_dues_score()` at 4.5, making `financial_behavior` max 8.7/15. `_calculate_fulfillment_score()` defaults to `'fulfilled'` while `_calculate_success_score()` defaults to `'success'` — inconsistent status field handling.

## Correctness Properties

Property 1: Bug Condition — Phase 1 Critical Fixes Applied

_For any_ Lambda invocation where a Phase 1 bug condition holds (missing VoiceHandler env var, hardcoded KB region, unauthenticated API endpoint, per-invocation orchestrator instantiation), the fixed system SHALL have the correct CDK configuration, region-dynamic ARNs, API key authentication on non-webhook endpoints, and module-level `BedrockOrchestrator` instantiation.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4**

Property 2: Bug Condition — Phase 2 Security Hardening Applied

_For any_ request or data write where a Phase 2 bug condition holds (unencrypted sensitive data, public dashboard, API-key-only AppSync, unsanitized input, no rate limiting), the fixed system SHALL encrypt sensitive fields before DynamoDB writes, require CloudFront+OAI for dashboard access, use Cognito for AppSync auth, sanitize and length-check WhatsApp messages, and enforce per-sender rate limits.

**Validates: Requirements 2.5, 2.6, 2.7, 2.8, 2.9**

Property 3: Bug Condition — Phase 3 Robustness Fixes Applied

_For any_ system state where a Phase 3 bug condition holds (DynamoDBAccess bypassed, timeout mismatch, ephemeral circuit breakers, no conversation TTL, score scale mismatch), the fixed system SHALL route DynamoDB writes through audit mechanisms, set Orchestrator timeout ≥ 180s, persist circuit breaker state at module level, add TTL to conversation items, and normalize dashboard score scale.

**Validates: Requirements 2.10, 2.11, 2.12, 2.13, 2.14**

Property 4: Bug Condition — Phase 4 Credit Score Accuracy Fixed

_For any_ credit score calculation where a Phase 4 bug condition holds (hardcoded dues score, unreachable financial_behavior max, inconsistent status fields, env var name mismatch), the fixed system SHALL query actual outstanding dues, ensure `financial_behavior` sub-components can reach 15.0, use a single consistent transaction status value, and read `DYNAMODB_TABLE` in `DynamoDBAccess`.

**Validates: Requirements 2.15, 2.16, 2.17, 2.18**

Property 5: Bug Condition — Phase 5 Cleanup Completed

_For any_ deployment package or Lambda invocation where a Phase 5 bug condition holds (dead code present, per-invocation class creation, missing SNS env vars), the fixed system SHALL have removed all dead code files/methods, moved class instantiation to module level with lazy init, and added `SNS_ALERT_TOPIC_ARN` to KnowledgeBase and SyncHandler CDK environments.

**Validates: Requirements 2.19, 2.20, 2.21, 2.22, 2.23, 2.24, 2.25, 2.26, 2.27, 2.28**

Property 6: Preservation — Existing Behavior Unchanged

_For any_ input where none of the 28 bug conditions hold, the fixed system SHALL produce exactly the same behavior as the original system, preserving webhook verification, LLM routing, deduplication, sync conflict resolution, voice language support, and all non-affected credit sub-components.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10, 3.11, 3.12, 3.13, 3.14, 3.15, 3.16**

## Fix Implementation

### Changes Required

Assuming our root cause analysis is correct:

**Phase 1: Critical Fixes**

**File**: `kisan-setu-mvp/infrastructure_stack.py`

1. **Add VoiceHandler env var**: Add `"BEDROCK_ORCHESTRATOR_FUNCTION": orchestrator_lambda.function_name` to VoiceHandler's environment dict.
2. **Add Orchestrator SNS env var**: Add `"SNS_ALERT_TOPIC_ARN": alert_topic.topic_arn` to Orchestrator's environment dict.

**File**: `kisan-setu-mvp/lambda/knowledge/knowledge_base.py`

3. **Fix region default**: Change `os.environ.get('REGION', 'us-east-1')` to `os.environ.get('REGION', 'ap-south-1')` for both the client and the REGION variable. Make MODEL_ARN use the REGION variable dynamically.

**File**: `kisan-setu-mvp/infrastructure_stack.py`

4. **Add API Gateway auth**: Add API key requirement to `/process`, `/credit`, `/knowledge` endpoints. Create a usage plan and API key.

**File**: `kisan-setu-mvp/lambda/orchestrator/orchestrator.py`

5. **Module-level orchestrator**: Move `BedrockOrchestrator()` instantiation to module level outside `handler()`. Use lazy initialization pattern.

**Phase 2: Security Hardening**

**File**: `kisan-setu-mvp/infrastructure_stack.py`

6. **Add KMS_KEY_ID env var**: Add `KMS_KEY_ID` to Orchestrator, DocumentProcessor, CreditCalculator, and SyncHandler Lambda environments.
7. **Secure dashboard bucket**: Remove `public_read_access=True`, re-enable `BlockPublicAccess`, add CloudFront distribution with OAI.
8. **AppSync Cognito auth**: Replace API_KEY authorization with Cognito User Pools.

**File**: `kisan-setu-mvp/lambda/router/router.py`

9. **Input sanitization**: Add max message length check (2000 chars), basic prompt injection detection, and special character sanitization before routing to orchestrator.
10. **Per-sender rate limiting**: Add DynamoDB-based rate limiting (10 messages/minute per phone number) with TTL counters.

**File**: `kisan-setu-mvp/lambda/common/dynamodb_access.py`

11. **Integrate encryption**: Call `encrypt_sensitive_fields()` in `create_farmer()`, `create_transaction()`, `save_credit_score()` before writes. Call `decrypt_sensitive_fields()` in corresponding read methods.

**Phase 3: Robustness**

**File**: `kisan-setu-mvp/infrastructure_stack.py`

12. **Fix Orchestrator timeout**: Change Orchestrator Lambda timeout from 60s to 180s.

**Files**: Multiple Lambda handlers

13. **DynamoDBAccess adoption or DynamoDB Streams**: Either refactor handlers to use `DynamoDBAccess` for writes, or document that audit trails are created via DynamoDB Streams (Option B/C from audit).

**File**: `kisan-setu-mvp/lambda/orchestrator/orchestrator.py`

14. **Conversation TTL**: Add `ttl` attribute (30 days from now) to conversation items in `_store_conversation` / `maintain_context`.
15. **Module-level circuit breaker persistence**: Ensured by fix #5 (module-level `BedrockOrchestrator`).

**File**: `kisan-setu-mvp/dashboard/app.js`

16. **Score scale normalization**: Change dashboard chart Y-axis to 0-100 scale to match CreditEngine output, or add a mapping function.

**Phase 4: Credit Score Accuracy**

**File**: `kisan-setu-mvp/lambda/credit/credit.py`

17. **Implement `_calculate_dues_score()`**: Replace hardcoded 4.5 with actual DynamoDB query for outstanding payment records.
18. **Fix `financial_behavior` max**: Adjust `_calculate_payment_score()` max and `_calculate_dues_score()` max so weighted sum can reach 15.0. Set payment max to ~21.43 (21.43 * 0.7 = 15.0) or normalize both sub-components to 15.0 before weighting.
19. **Standardize status field**: Use a single status value (e.g., `'completed'`) in both `_calculate_fulfillment_score()` and `_calculate_success_score()`.

**File**: `kisan-setu-mvp/lambda/common/dynamodb_access.py`

20. **Fix env var name**: Change `DYNAMODB_TABLE_NAME` to `DYNAMODB_TABLE` to match CDK configuration.

**Phase 5: Cleanup**

**Files**: Various

21. **Remove dead code**: Delete `sync_manager.py` (or move to tests), remove `_invoke_model()` and `_invoke_fallback()` from orchestrator, remove `error_handler_example.py` from `common/`, remove `webhook_handler.py`.
22. **Remove unused Router env vars**: Remove `CREDIT_CALCULATOR_FUNCTION` and `SATELLITE_ANALYZER_FUNCTION` from Router's CDK environment.
23. **Module-level caching**: Move `MetaWhatsAppInterface()` to module level in orchestrator and processor. Move `SatelliteAnalyzer()` to module level in satellite handler. Move `CreditEngine(table)` to module level in credit handler.
24. **Add missing SNS env vars**: Add `SNS_ALERT_TOPIC_ARN` to KnowledgeBase and SyncHandler Lambda environments in CDK.

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate the bugs on unfixed code, then verify the fixes work correctly and preserve existing behavior. Given the breadth of 28 defects across CDK, Lambda handlers, and shared modules, testing is organized by phase.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the bugs BEFORE implementing fixes. Confirm or refute the root cause analysis.

**Test Plan**: Write tests that verify each defect condition exists in the current codebase. Run on UNFIXED code to confirm failures.

**Test Cases**:
1. **VoiceHandler Env Var Test**: Assert `BEDROCK_ORCHESTRATOR_FUNCTION` is NOT in VoiceHandler CDK env vars (will confirm bug on unfixed code)
2. **KB Region Test**: Assert `knowledge_base.py` defaults to `us-east-1` (will confirm bug on unfixed code)
3. **API Auth Test**: Assert `/process`, `/credit`, `/knowledge` have no auth method configured (will confirm bug on unfixed code)
4. **Per-Invocation Test**: Assert `handler()` in orchestrator creates new `BedrockOrchestrator()` each call (will confirm bug on unfixed code)
5. **Dues Score Stub Test**: Assert `_calculate_dues_score()` returns 4.5 for any input (will confirm bug on unfixed code)
6. **Financial Behavior Max Test**: Assert `calculate_financial_behavior()` cannot exceed 8.7 (will confirm bug on unfixed code)
7. **Status Inconsistency Test**: Assert `_calculate_fulfillment_score` and `_calculate_success_score` use different default status values (will confirm bug on unfixed code)
8. **Env Var Mismatch Test**: Assert `DynamoDBAccess` reads `DYNAMODB_TABLE_NAME` while CDK sets `DYNAMODB_TABLE` (will confirm bug on unfixed code)

**Expected Counterexamples**:
- VoiceHandler env vars missing `BEDROCK_ORCHESTRATOR_FUNCTION`
- Knowledge Base client region defaults to `us-east-1`
- Credit sub-component maximums don't sum correctly
- Status field defaults are inconsistent between methods

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed code produces the expected behavior.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  result := fixedSystem(input)
  ASSERT expectedBehavior(result)
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed code produces the same result as the original.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT originalSystem(input) = fixedSystem(input)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many test cases automatically across the input domain
- It catches edge cases that manual unit tests might miss
- It provides strong guarantees that behavior is unchanged for all non-buggy inputs

**Test Plan**: Observe behavior on UNFIXED code first for non-bug inputs, then write property-based tests capturing that behavior.

**Test Cases**:
1. **Webhook Verification Preservation**: Verify Meta webhook challenge-response continues working after API key changes
2. **LLM Routing Preservation**: Verify query complexity classification and model selection unchanged
3. **Deduplication Preservation**: Verify `MSGID#{message_id}` / `DEDUP` pattern continues working
4. **Credit Sub-Component Preservation**: Verify `_calculate_frequency_score`, `_calculate_adherence_score`, `_calculate_moisture_score` produce identical results
5. **Sync Conflict Resolution Preservation**: Verify last-write-wins logic unchanged

### Unit Tests

- CDK stack assertions: verify env vars present/absent for each Lambda
- Knowledge Base region configuration tests
- API Gateway auth method assertions
- Credit score component max value tests
- Status field consistency tests
- Input sanitization boundary tests (length, injection patterns)
- Rate limiting counter tests
- Conversation TTL attribute presence tests
- Dashboard score scale tests

### Property-Based Tests

- Generate random transaction lists and verify `calculate_financial_behavior()` can reach 15.0 with correct sub-component maxes
- Generate random credit inputs and verify non-affected sub-components (`_calculate_frequency_score`, etc.) produce identical results before and after fix
- Generate random WhatsApp messages and verify sanitization only modifies messages exceeding length or containing injection patterns
- Generate random farmer IDs and verify `_calculate_dues_score()` queries DynamoDB instead of returning hardcoded value

### Integration Tests

- End-to-end VoiceHandler direct invocation → orchestrator forwarding
- Knowledge Base query in `ap-south-1` region
- API Gateway request with/without API key
- Credit score calculation with real transaction data
- Dashboard rendering with backend score data
- Conversation history with TTL expiration

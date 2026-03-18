# Implementation Plan

- [x] 1. Write bug condition exploration tests
  - **Property 1: Bug Condition** - Code Audit Bugs Exist in Unfixed Code
  - **CRITICAL**: This test MUST FAIL on unfixed code — failure confirms the bugs exist
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior — it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate all 7 bugs exist
  - **Scoped PBT Approach**: Scope properties to concrete failing cases for each bug
  - Write a property-based test file `kisan-setu-mvp/tests/test_code_audit_bugs.py` using Hypothesis
  - Test 1a — Stale Model Names: Read `orchestrator.py`, assert it does NOT contain "Opus 4.6", "Sonnet 4" (standalone, not "Sonnet v2"), or "Haiku 4.5" in comments/docstrings. On unfixed code these patterns exist at 3 locations (class docstring ~line 392, COMPLEX_PATTERNS comment line 99, select_model log line 377), so assertion FAILS
  - Test 1b — Dead Code: Read `satellite_analyzer.py`, assert `INDIA_BOUNDS` is NOT defined as a module-level variable. On unfixed code the definition exists at lines 56-60, so assertion FAILS
  - Test 1c — Missing Env Vars: Parse `infrastructure_stack.py` source, for each Lambda in [VoiceHandler, MessageRouter, SatelliteAnalyzer, KnowledgeBase] assert `KMS_KEY_ID` appears in its environment block. Also assert KnowledgeBase has `DYNAMODB_TABLE`. On unfixed code these are missing, so assertions FAIL
  - Test 1d — Unused GraphQL Arg: Read `schema.graphql`, assert `updateTransaction` mutation signature does NOT contain `transactionId: ID!` as a standalone argument. On unfixed code the arg exists, so assertion FAILS
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests FAIL (this is correct — it proves the bugs exist)
  - Document counterexamples found to understand root cause
  - Mark task complete when tests are written, run, and failures are documented
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9_

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Runtime Logic and Existing Config Unchanged
  - **IMPORTANT**: Follow observation-first methodology
  - **GOAL**: Capture baseline behavior of non-buggy code so regressions are detected after fix
  - Write preservation tests in `kisan-setu-mvp/tests/test_code_audit_preservation.py` using Hypothesis
  - Test 2a — Model Routing Preservation: Observe that `MODEL_TIERS` dict contains `apac.amazon.nova-pro-v1:0` and `apac.amazon.nova-lite-v1:0`, `SIMPLE_PATTERNS` list has 6+ patterns, `COMPLEX_PATTERNS` list exists. Assert these values are unchanged. Property: for all tier keys in MODEL_TIERS, model_id and cost fields match observed values
  - Test 2b — Satellite Runtime Preservation: Observe that `satellite_analyzer.py` contains all runtime functions (handler, analyze_satellite_data, etc.) and class definitions (SatelliteImage). Assert these are present and unchanged. Only `INDIA_BOUNDS` removal is expected
  - Test 2c — Existing Lambda Env Vars Preservation: Observe that Processor Lambda has `KMS_KEY_ID`, Credit Lambda has `KMS_KEY_ID`, Orchestrator Lambda has `KMS_KEY_ID`, SyncHandler has `KMS_KEY_ID`. Assert these remain present. Also observe Router Lambda has `DYNAMODB_TABLE`, S3 buckets, `REGION`, function names — assert these remain present
  - Test 2d — Other Mutations Preservation: Observe `createTransaction(input: TransactionInput!): Transaction` and `syncOfflineTransactions(transactions: [TransactionInput!]!): SyncResult` signatures. Assert these are unchanged after fix
  - Test 2e — Resolver Preservation: Observe UpdateTransactionResolver uses `$ctx.args.input.farmerId` and `$ctx.args.input.timestamp` as keys. Assert resolver mapping templates are unchanged
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

- [x] 3. Fix for code audit bugs (#51, #52, #53, #54, #55, #56, #35)

  - [x] 3.1 Fix stale model names in orchestrator.py (#51)
    - Replace class docstring (line ~392): `Primary (Opus 4.6)` → `Primary (Nova Pro)`, `Default (Sonnet 4)` → `Default (Nova Pro)`, `Secondary (Haiku 4.5)` → `Secondary (Nova Lite)`
    - Replace COMPLEX_PATTERNS comment (line 99): `# Complex queries → Opus 4.6 (deep reasoning)` → `# Complex queries → Nova Pro (deep reasoning)`
    - Replace select_model log (line 377): `Forcing secondary (Haiku 4.5)` → `Forcing secondary (Nova Lite)`
    - _Bug_Condition: isBugCondition(input) where input.file == "orchestrator.py" AND content MATCHES /Opus 4\.6|Sonnet 4(?! v2)|Haiku 4\.5/_
    - _Expected_Behavior: Comments/docstrings reference "Nova Pro" and "Nova Lite" matching MODEL_TIERS config_
    - _Preservation: MODEL_TIERS dict values, SIMPLE_PATTERNS, COMPLEX_PATTERNS regex lists, select_model() routing logic unchanged_
    - _Requirements: 2.1, 2.2, 2.3, 3.1_

  - [x] 3.2 Remove unused INDIA_BOUNDS from satellite_analyzer.py (#52)
    - Delete the `# India geographic bounds` comment and `INDIA_BOUNDS = { ... }` dict (lines 56-60)
    - _Bug_Condition: isBugCondition(input) where input.file == "satellite_analyzer.py" AND INDIA_BOUNDS defined with zero references_
    - _Expected_Behavior: INDIA_BOUNDS definition no longer exists in file_
    - _Preservation: All runtime functions (handler, analyze_satellite_data, SatelliteImage class) unchanged; satellite_mock.py retains its own INDIA_BOUNDS_
    - _Requirements: 2.4, 3.2_

  - [x] 3.3 Add KMS_KEY_ID to VoiceHandler Lambda (#53)
    - Add `"KMS_KEY_ID": encryption_key.key_id` to VoiceHandler environment dict in infrastructure_stack.py
    - _Bug_Condition: VoiceHandler Lambda env block missing KMS_KEY_ID_
    - _Expected_Behavior: VoiceHandler environment includes KMS_KEY_ID set to encryption_key.key_id_
    - _Preservation: All existing VoiceHandler env vars (DYNAMODB_TABLE, S3 buckets, REGION, SNS_ALERT_TOPIC_ARN, WHATSAPP_SECRET_NAME) unchanged_
    - _Requirements: 2.5, 3.7_

  - [x] 3.4 Add KMS_KEY_ID to Router Lambda (#54)
    - Add `"KMS_KEY_ID": encryption_key.key_id` to MessageRouter environment dict in infrastructure_stack.py
    - _Bug_Condition: MessageRouter Lambda env block missing KMS_KEY_ID_
    - _Expected_Behavior: MessageRouter environment includes KMS_KEY_ID set to encryption_key.key_id_
    - _Preservation: All existing Router env vars (DYNAMODB_TABLE, S3 buckets, REGION, function names, WHATSAPP_SECRET_NAME, WEBHOOK_VERIFY_TOKEN, SNS_ALERT_TOPIC_ARN) unchanged_
    - _Requirements: 2.6, 3.7_

  - [x] 3.5 Add KMS_KEY_ID to Satellite Lambda (#55)
    - Add `"KMS_KEY_ID": encryption_key.key_id` to SatelliteAnalyzer environment dict in infrastructure_stack.py
    - _Bug_Condition: SatelliteAnalyzer Lambda env block missing KMS_KEY_ID_
    - _Expected_Behavior: SatelliteAnalyzer environment includes KMS_KEY_ID set to encryption_key.key_id_
    - _Preservation: All existing Satellite env vars (DYNAMODB_TABLE, S3 buckets, REGION, SAGEMAKER_REGION, SENTINEL2_ARN, SNS_ALERT_TOPIC_ARN) unchanged_
    - _Requirements: 2.7_

  - [x] 3.6 Add KMS_KEY_ID and DYNAMODB_TABLE to Knowledge Lambda (#56)
    - Add `"KMS_KEY_ID": encryption_key.key_id` and `"DYNAMODB_TABLE": "KisanSetuData"` to KnowledgeBase environment dict in infrastructure_stack.py
    - _Bug_Condition: KnowledgeBase Lambda env block missing KMS_KEY_ID and DYNAMODB_TABLE_
    - _Expected_Behavior: KnowledgeBase environment includes both KMS_KEY_ID and DYNAMODB_TABLE_
    - _Preservation: Existing KnowledgeBase env vars (REGION, KNOWLEDGE_BASE_ID, SNS_ALERT_TOPIC_ARN) unchanged_
    - _Requirements: 2.8, 3.4_

  - [x] 3.7 Remove unused transactionId arg from updateTransaction mutation (#35)
    - In `schema.graphql`, change `updateTransaction(transactionId: ID!, input: TransactionInput!): Transaction` → `updateTransaction(input: TransactionInput!): Transaction`
    - No resolver change needed — resolver already uses `$ctx.args.input.farmerId` and `$ctx.args.input.timestamp`
    - _Bug_Condition: updateTransaction mutation signature contains standalone transactionId: ID! arg that resolver ignores_
    - _Expected_Behavior: updateTransaction accepts only input: TransactionInput!_
    - _Preservation: UpdateTransactionResolver request/response mapping templates unchanged; createTransaction and syncOfflineTransactions mutations unchanged_
    - _Requirements: 2.9, 3.5, 3.6_

  - [x] 3.8 Verify bug condition exploration tests now pass
    - **Property 1: Expected Behavior** - All Code Audit Bugs Fixed
    - **IMPORTANT**: Re-run the SAME tests from task 1 — do NOT write new tests
    - The tests from task 1 encode the expected behavior for all 7 bugs
    - When these tests pass, it confirms all bugs are fixed
    - Run `pytest kisan-setu-mvp/tests/test_code_audit_bugs.py -v`
    - **EXPECTED OUTCOME**: Tests PASS (confirms bugs are fixed)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9_

  - [x] 3.9 Verify preservation tests still pass
    - **Property 2: Preservation** - Runtime Logic and Existing Config Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 2 — do NOT write new tests
    - Run `pytest kisan-setu-mvp/tests/test_code_audit_preservation.py -v`
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Confirm all preservation tests still pass after fix (no regressions)

- [x] 4. Checkpoint - Ensure all tests pass
  - Run full test suite: `pytest kisan-setu-mvp/tests/test_code_audit_bugs.py kisan-setu-mvp/tests/test_code_audit_preservation.py -v`
  - Ensure all bug condition tests pass (bugs fixed)
  - Ensure all preservation tests pass (no regressions)
  - Ask the user if questions arise

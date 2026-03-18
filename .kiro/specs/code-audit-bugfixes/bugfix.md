# Bugfix Requirements Document

## Introduction

A line-by-line code audit of the Kisan Setu MVP project uncovered 7 bugs across 4 files. These include incorrect model name references in docstrings/comments, dead code, missing environment variables for KMS encryption and DynamoDB access in multiple Lambda functions, and an unused GraphQL mutation argument. These bugs affect documentation accuracy, code cleanliness, security posture (missing field-level encryption config), and API correctness.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN a developer reads the `BedrockOrchestrator` class docstring in `orchestrator.py` THEN the system displays incorrect model names "Opus 4.6", "Sonnet 4", and "Haiku 4.5" instead of the actual models (Nova Pro, Nova Pro, Nova Lite)

1.2 WHEN a developer reads the comment at line 99 of `orchestrator.py` THEN the system displays `# Complex queries → Opus 4.6` instead of `# Complex queries → Nova Pro (deep reasoning)`

1.3 WHEN the daily cost threshold is exceeded in `select_model()` THEN the system prints "Forcing secondary (Haiku 4.5)" instead of "Forcing secondary (Nova Lite)"

1.4 WHEN `satellite_analyzer.py` is loaded THEN the system defines an `INDIA_BOUNDS` dictionary that is never referenced anywhere in the file, constituting dead code

1.5 WHEN the VoiceHandler Lambda executes and attempts to interact with encrypted DynamoDB fields THEN the system has no `KMS_KEY_ID` environment variable available, preventing field-level decryption

1.6 WHEN the Router (MessageRouter) Lambda executes and interacts with DynamoDB for rate limiting THEN the system has no `KMS_KEY_ID` environment variable available, preventing field-level decryption of encrypted fields

1.7 WHEN the SatelliteAnalyzer Lambda executes and interacts with DynamoDB THEN the system has no `KMS_KEY_ID` environment variable available, preventing field-level decryption of encrypted fields

1.8 WHEN the KnowledgeBase Lambda executes THEN the system has neither `KMS_KEY_ID` nor `DYNAMODB_TABLE` environment variables available, preventing both field-level decryption and DynamoDB table access

1.9 WHEN a client calls the `updateTransaction` GraphQL mutation THEN the system requires a `transactionId` argument that is completely ignored by the resolver, which uses `input.farmerId` and `input.timestamp` as the DynamoDB key instead

### Expected Behavior (Correct)

2.1 WHEN a developer reads the `BedrockOrchestrator` class docstring in `orchestrator.py` THEN the system SHALL display the correct model names: "Primary (Nova Pro)", "Default (Nova Pro)", "Secondary (Nova Lite)"

2.2 WHEN a developer reads the complex query pattern comment in `orchestrator.py` THEN the system SHALL display `# Complex queries → Nova Pro (deep reasoning)`

2.3 WHEN the daily cost threshold is exceeded in `select_model()` THEN the system SHALL print "Forcing secondary (Nova Lite)"

2.4 WHEN `satellite_analyzer.py` is loaded THEN the system SHALL NOT define the unused `INDIA_BOUNDS` dictionary (dead code removed)

2.5 WHEN the VoiceHandler Lambda is deployed THEN the system SHALL include `KMS_KEY_ID` in its environment variables, set to `encryption_key.key_id`

2.6 WHEN the Router (MessageRouter) Lambda is deployed THEN the system SHALL include `KMS_KEY_ID` in its environment variables, set to `encryption_key.key_id`

2.7 WHEN the SatelliteAnalyzer Lambda is deployed THEN the system SHALL include `KMS_KEY_ID` in its environment variables, set to `encryption_key.key_id`

2.8 WHEN the KnowledgeBase Lambda is deployed THEN the system SHALL include both `KMS_KEY_ID` (set to `encryption_key.key_id`) and `DYNAMODB_TABLE` (set to `"KisanSetuData"`) in its environment variables

2.9 WHEN a client calls the `updateTransaction` GraphQL mutation THEN the system SHALL NOT require a separate `transactionId` argument, since the resolver uses `input.farmerId` and `input.timestamp` as the DynamoDB composite key (the `transactionId` is already part of `TransactionInput`)

### Unchanged Behavior (Regression Prevention)

3.1 WHEN the orchestrator processes queries using the LLMAdapter fallback chain THEN the system SHALL CONTINUE TO route queries through Nova Pro → Nova Lite → Claude 3.7 Sonnet → Claude 3.5 Sonnet v2 → Claude 3 Haiku (actual model routing logic is unchanged; only comments/docstrings are corrected)

3.2 WHEN `satellite_analyzer.py` processes satellite imagery and NDVI analysis THEN the system SHALL CONTINUE TO function identically (removing unused `INDIA_BOUNDS` has no effect on runtime behavior; `satellite_mock.py` has its own separate definition)

3.3 WHEN the Processor, Credit, Orchestrator, and SyncHandler Lambdas are deployed THEN the system SHALL CONTINUE TO have `KMS_KEY_ID` in their environment variables as before

3.4 WHEN the KnowledgeBase Lambda queries the Bedrock Knowledge Base THEN the system SHALL CONTINUE TO use `REGION`, `KNOWLEDGE_BASE_ID`, and `SNS_ALERT_TOPIC_ARN` environment variables as before

3.5 WHEN a client calls `createTransaction` or `syncOfflineTransactions` GraphQL mutations THEN the system SHALL CONTINUE TO function identically with no schema or resolver changes

3.6 WHEN a client calls `updateTransaction` with a `TransactionInput` THEN the system SHALL CONTINUE TO use `input.farmerId` and `input.timestamp` as the DynamoDB composite key for the update operation

3.7 WHEN the Router Lambda processes WhatsApp webhook messages THEN the system SHALL CONTINUE TO have access to all its existing environment variables (`DYNAMODB_TABLE`, S3 buckets, `REGION`, function names, etc.)

# Bugfix Requirements Document

## Introduction

A senior architect audit of the Kisan-Setu MVP codebase (March 14, 2026) identified 52 issues across the serverless Python/CDK application. This document captures the 29 highest-priority bugs organized into 5 phases: Critical Fixes, Security Hardening, Robustness, Credit Score Accuracy, and Cleanup. These bugs span silent failure paths, security vulnerabilities, data integrity issues, dead code, and misconfiguration across the CDK stack (`infrastructure_stack.py`), Lambda handlers, and shared modules.

## Bug Analysis

### Current Behavior (Defect)

**Phase 1: Critical Fixes**

1.1 WHEN VoiceHandler Lambda is invoked directly (not via Router) THEN the system silently drops the transcribed text because `BEDROCK_ORCHESTRATOR_FUNCTION` env var is missing from VoiceHandler's CDK definition — the user receives a transcription confirmation but never gets an AI response.

1.2 WHEN the Knowledge Base Lambda executes THEN the system defaults the Bedrock Agent Runtime client to `us-east-1` and hardcodes the MODEL_ARN to `us-east-1` region, causing cross-region errors since the app runs in `ap-south-1`.

1.3 WHEN a request is sent to `/process`, `/credit`, or `/knowledge` API Gateway endpoints THEN the system accepts the request with no authentication — any caller with the URL can invoke these Lambdas.

1.4 WHEN the Orchestrator Lambda handler is invoked THEN the system creates a new `BedrockOrchestrator()` instance per invocation, discarding circuit breaker state, LLMAdapter connections, and boto3 clients from previous warm invocations.

**Phase 2: Security Hardening**

1.5 WHEN sensitive data (phone numbers, prices, financial scores) is written to DynamoDB THEN the system stores it in plaintext because the encryption module (`encryption.py`) is never called in production code and `KMS_KEY_ID` is not set in any Lambda's environment.

1.6 WHEN a user accesses the dashboard S3 bucket URL THEN the system serves the FPO admin dashboard with no authentication because `public_read_access=True` and all `BlockPublicAccess` settings are disabled.

1.7 WHEN a client queries the AppSync GraphQL API THEN the system uses API Key authorization with no per-user or per-FPO data isolation — any API key holder can access all farmer data.

1.8 WHEN a WhatsApp text message is received THEN the system passes it directly to Bedrock LLM prompts without sanitization — no max length check, no prompt injection detection, no special character handling.

1.9 WHEN a single WhatsApp user sends many messages rapidly THEN the system processes all of them with no per-user rate limiting — only global API Gateway throttling (100 req/s) exists.

**Phase 3: Robustness**

1.10 WHEN Lambda handlers (router, orchestrator, credit, satellite, sync) write to DynamoDB THEN the system uses direct boto3 calls instead of the `DynamoDBAccess` class, bypassing audit trail creation and input validation.

1.11 WHEN the Orchestrator (60s timeout) synchronously invokes SatelliteAnalyzer (120s timeout) THEN the system is guaranteed to timeout because the caller's timeout is shorter than the callee's maximum execution time.

1.12 WHEN a Lambda cold start occurs THEN the system resets all circuit breaker state (failure counts, open/closed status) because state is stored in-memory and combined with per-invocation instantiation (#1.4), circuit breakers never accumulate failures.

1.13 WHEN conversation messages are stored in DynamoDB THEN the system stores them with no TTL attribute — conversation history grows unbounded (estimated 5M items/year for 500 farmers at 10 messages/day).

1.14 WHEN the CreditEngine produces a score (0-100 scale) and the dashboard displays it THEN the system shows mismatched scales because the dashboard chart uses 550-850 range (FICO-like) with hardcoded demo data.

**Phase 4: Credit Score Accuracy**

1.15 WHEN `_calculate_dues_score()` is called for any farmer THEN the system returns a hardcoded maximum score of 4.5 because the method is a TODO stub — every farmer gets a perfect outstanding-dues score.

1.16 WHEN `calculate_financial_behavior()` computes the weighted sum of sub-components THEN the system can only produce a maximum of 8.7 out of 15 points because `_calculate_payment_score()` maxes at 10.5 and `_calculate_dues_score()` maxes at 4.5, yielding `10.5*0.7 + 4.5*0.3 = 8.7`.

1.17 WHEN `_calculate_fulfillment_score()` checks transaction status THEN the system defaults to `'fulfilled'` while `_calculate_success_score()` defaults to `'success'` — if a transaction has an actual status value, one metric will always treat it as failed.

1.18 WHEN `DynamoDBAccess` reads the table name from environment THEN the system reads `DYNAMODB_TABLE_NAME` but CDK sets `DYNAMODB_TABLE` — the mismatch is masked by the hardcoded fallback `'KisanSetuData'` being coincidentally correct.

**Phase 5: Cleanup**

1.19 WHEN the Lambda deployment package is built THEN the system includes `sync_manager.py` which is dead code — not imported by `sync_handler.py` or any other file.

1.20 WHEN the Orchestrator module is loaded THEN the system includes `_invoke_model()` and `_invoke_fallback()` methods that are never called — all inference goes through `LLMAdapter.converse()`.

1.21 WHEN the Router Lambda is configured in CDK THEN the system sets `CREDIT_CALCULATOR_FUNCTION` and `SATELLITE_ANALYZER_FUNCTION` env vars that Router never reads or uses.

1.22 WHEN Lambda deployment packages are built THEN the system includes `error_handler_example.py` in every Lambda's `common/` directory — it is not imported anywhere.

1.23 WHEN the Lambda deployment package is built THEN the system includes `webhook_handler.py` which duplicates Router logic but is not deployed as a Lambda — all webhook handling uses `router.py`.

1.24 WHEN the Orchestrator or Processor handler is invoked THEN the system creates a new `MetaWhatsAppInterface()` per invocation, triggering a Secrets Manager API call to load WhatsApp credentials each time instead of caching at module level.

1.25 WHEN the SatelliteAnalyzer handler is invoked THEN the system creates a new `SatelliteAnalyzer()` instance per invocation — same per-invocation waste as #1.4.

1.26 WHEN the CreditEngine handler is invoked THEN the system creates a new `CreditEngine(table)` instance per invocation — unnecessary object creation overhead.

1.27 WHEN the KnowledgeBase Lambda encounters a critical error THEN the system cannot send SNS notifications because `SNS_ALERT_TOPIC_ARN` is missing from its CDK environment variables.

1.28 WHEN the SyncHandler Lambda encounters a critical error THEN the system cannot send SNS notifications because `SNS_ALERT_TOPIC_ARN` is missing from its CDK environment variables.

### Expected Behavior (Correct)

**Phase 1: Critical Fixes**

2.1 WHEN VoiceHandler Lambda is invoked directly THEN the system SHALL have `BEDROCK_ORCHESTRATOR_FUNCTION` env var set in CDK, enabling it to forward transcribed text to the Orchestrator and deliver an AI response to the user.

2.2 WHEN the Knowledge Base Lambda executes THEN the system SHALL use the `REGION` env var (defaulting to `ap-south-1`) for both the Bedrock Agent Runtime client and the MODEL_ARN construction, eliminating cross-region errors.

2.3 WHEN a request is sent to `/process`, `/credit`, or `/knowledge` API Gateway endpoints THEN the system SHALL require API key authentication, rejecting unauthenticated requests with 403.

2.4 WHEN the Orchestrator Lambda handler is invoked THEN the system SHALL reuse a module-level `BedrockOrchestrator()` instance, preserving circuit breaker state, LLMAdapter connections, and boto3 clients across warm invocations.

**Phase 2: Security Hardening**

2.5 WHEN sensitive data (phone numbers, prices, financial scores) is written to DynamoDB THEN the system SHALL encrypt those fields using the `EncryptionService` before storage, with `KMS_KEY_ID` configured in all relevant Lambda environments.

2.6 WHEN a user accesses the dashboard THEN the system SHALL require authentication via CloudFront with OAI, with `public_read_access` disabled and `BlockPublicAccess` re-enabled on the S3 bucket.

2.7 WHEN a client queries the AppSync GraphQL API THEN the system SHALL use Cognito User Pools for authorization with per-user data isolation, replacing API Key auth.

2.8 WHEN a WhatsApp text message is received THEN the system SHALL enforce a maximum message length (2000 chars), apply basic prompt injection detection, and sanitize special characters before passing to LLM prompts.

2.9 WHEN a single WhatsApp user sends messages THEN the system SHALL enforce per-sender rate limiting (e.g., max 10 messages/minute per phone number) using DynamoDB counters with TTL, returning a friendly "please wait" message when exceeded.

**Phase 3: Robustness**

2.10 WHEN Lambda handlers write to DynamoDB THEN the system SHALL use the `DynamoDBAccess` class (or an equivalent audit mechanism like DynamoDB Streams) to ensure audit trails are created for all data mutations.

2.11 WHEN the Orchestrator invokes SatelliteAnalyzer THEN the system SHALL have a timeout of at least 180s to accommodate SatelliteAnalyzer's 120s maximum execution time.

2.12 WHEN circuit breaker state is needed across invocations THEN the system SHALL persist state at module level (surviving warm invocations) and optionally in DynamoDB with TTL for cross-cold-start persistence.

2.13 WHEN conversation messages are stored in DynamoDB THEN the system SHALL include a TTL attribute (e.g., 30 days) so that old conversation items are automatically cleaned up.

2.14 WHEN the CreditEngine produces a score and the dashboard displays it THEN the system SHALL use a consistent scale — either normalize the dashboard to 0-100 or apply a documented mapping function from 0-100 to the display range.

**Phase 4: Credit Score Accuracy**

2.15 WHEN `_calculate_dues_score()` is called THEN the system SHALL query DynamoDB for actual outstanding payment records and compute a real score instead of returning a hardcoded maximum.

2.16 WHEN `calculate_financial_behavior()` computes the weighted sum THEN the system SHALL use sub-component maximums that correctly sum to 15.0 after weighting (e.g., payment max ~21.43 * 0.7 = 15.0 and dues max ~50.0 * 0.3 = 15.0, or simpler: adjust raw maxes so weighted sum reaches 15).

2.17 WHEN transaction status is checked in credit scoring THEN the system SHALL use a single standardized status field and value set (e.g., `'completed'`) consistently across `_calculate_fulfillment_score()` and `_calculate_success_score()`.

2.18 WHEN `DynamoDBAccess` reads the table name from environment THEN the system SHALL use `DYNAMODB_TABLE` to match the CDK-configured env var name.

**Phase 5: Cleanup**

2.19 WHEN the Lambda deployment package is built THEN the system SHALL NOT include `sync_manager.py` — it SHALL be removed or moved to test utilities.

2.20 WHEN the Orchestrator module is loaded THEN the system SHALL NOT contain the dead `_invoke_model()` and `_invoke_fallback()` methods.

2.21 WHEN the Router Lambda is configured in CDK THEN the system SHALL NOT include unused `CREDIT_CALCULATOR_FUNCTION` and `SATELLITE_ANALYZER_FUNCTION` env vars.

2.22 WHEN Lambda deployment packages are built THEN the system SHALL NOT include `error_handler_example.py` in the `common/` directory.

2.23 WHEN the Lambda deployment package is built THEN the system SHALL NOT include `webhook_handler.py`.

2.24 WHEN the Orchestrator or Processor handler is invoked THEN the system SHALL reuse a module-level `MetaWhatsAppInterface()` instance (with lazy initialization) to avoid redundant Secrets Manager API calls.

2.25 WHEN the SatelliteAnalyzer handler is invoked THEN the system SHALL reuse a module-level `SatelliteAnalyzer()` instance.

2.26 WHEN the CreditEngine handler is invoked THEN the system SHALL reuse a module-level `CreditEngine(table)` instance.

2.27 WHEN the KnowledgeBase Lambda encounters a critical error THEN the system SHALL have `SNS_ALERT_TOPIC_ARN` in its CDK environment variables to enable SNS notifications.

2.28 WHEN the SyncHandler Lambda encounters a critical error THEN the system SHALL have `SNS_ALERT_TOPIC_ARN` in its CDK environment variables to enable SNS notifications.

### Unchanged Behavior (Regression Prevention)

3.1 WHEN the Router Lambda invokes VoiceHandler with `orchestrator_function` in the event payload THEN the system SHALL CONTINUE TO forward transcribed text to the Orchestrator via the event-based path (the env var fix adds a fallback, not a replacement).

3.2 WHEN the Knowledge Base Lambda is invoked with a valid `KNOWLEDGE_BASE_ID` and `REGION` env var set THEN the system SHALL CONTINUE TO retrieve and generate responses from Bedrock Knowledge Base.

3.3 WHEN the `/webhook` endpoint receives a Meta WhatsApp verification request THEN the system SHALL CONTINUE TO verify the webhook token and respond with the challenge — webhook auth is unaffected by API key changes on other endpoints.

3.4 WHEN the Orchestrator processes a text message via `LLMAdapter.converse()` with the tiered model routing THEN the system SHALL CONTINUE TO select models based on query complexity and daily cost thresholds.

3.5 WHEN existing DynamoDB data is read (farmers, transactions, scores) THEN the system SHALL CONTINUE TO return correct results — encryption integration must handle both encrypted and unencrypted legacy data gracefully.

3.6 WHEN the dashboard is accessed by an authenticated user THEN the system SHALL CONTINUE TO serve the same HTML/JS/CSS content and display the same demo data.

3.7 WHEN the AppSync `syncOfflineTransactions` mutation is called THEN the system SHALL CONTINUE TO perform last-write-wins conflict resolution and return success/failure/conflict counts.

3.8 WHEN a WhatsApp message under 2000 characters with no injection patterns is received THEN the system SHALL CONTINUE TO process it normally without rejection or modification.

3.9 WHEN a user sends messages at a normal rate (under the rate limit) THEN the system SHALL CONTINUE TO process all messages without delay or rejection.

3.10 WHEN the CreditEngine calculates scores for farmers with transaction history THEN the system SHALL CONTINUE TO produce scores based on the 5-component model (supply consistency, quality metrics, transaction history, financial behavior, operational transparency).

3.11 WHEN the Orchestrator invokes CreditCalculator (30s timeout) or KnowledgeBase (60s timeout) THEN the system SHALL CONTINUE TO complete these calls within the Orchestrator's timeout window.

3.12 WHEN conversation deduplication checks are performed in the Router THEN the system SHALL CONTINUE TO use the `MSGID#{message_id}` / `DEDUP` pattern with 24-hour TTL.

3.13 WHEN the `_calculate_frequency_score()`, `_calculate_adherence_score()`, `_calculate_moisture_score()`, and other non-affected credit sub-components are called THEN the system SHALL CONTINUE TO produce the same scores as before.

3.14 WHEN Lambda handlers use `os.environ.get('DYNAMODB_TABLE', 'KisanSetuData')` THEN the system SHALL CONTINUE TO connect to the correct table — only `DynamoDBAccess` env var name changes.

3.15 WHEN the VoiceAgent transcribes audio and synthesizes speech THEN the system SHALL CONTINUE TO support Hindi, English, Marathi, and Tamil languages.

3.16 WHEN the SyncHandler processes offline transactions THEN the system SHALL CONTINUE TO sort by timestamp, detect conflicts, and apply last-write-wins resolution.

# Architecture Audit Fixes — Tasks

## Phase 1: Critical Fixes

- [x] 1.1 Add missing `BEDROCK_ORCHESTRATOR_FUNCTION` env var to VoiceHandler Lambda in `infrastructure_stack.py`
  - [x] 1.1.1 Add `"BEDROCK_ORCHESTRATOR_FUNCTION": orchestrator_lambda.function_name` to VoiceHandler environment dict
  - [x] 1.1.2 Add `"SNS_ALERT_TOPIC_ARN": alert_topic.topic_arn` to Orchestrator Lambda environment dict
- [x] 1.2 Fix Knowledge Base region hardcoding in `lambda/knowledge/knowledge_base.py`
  - [x] 1.2.1 Change default region from `us-east-1` to `ap-south-1` in `bedrock_agent_runtime` client initialization
  - [x] 1.2.2 Change default region from `us-east-1` to `ap-south-1` in `REGION` variable
  - [x] 1.2.3 Make `MODEL_ARN` use the `REGION` variable dynamically instead of hardcoded region
- [x] 1.3 Add API Gateway authentication to `/process`, `/credit`, `/knowledge` endpoints in `infrastructure_stack.py`
  - [x] 1.3.1 Create an API key and usage plan in the CDK stack
  - [x] 1.3.2 Set `api_key_required=True` on `/process`, `/credit`, `/knowledge` POST methods
  - [x] 1.3.3 Associate the usage plan with the API and API key
- [x] 1.4 Move `BedrockOrchestrator()` to module-level instantiation in `lambda/orchestrator/orchestrator.py`
  - [x] 1.4.1 Add module-level variable `_orchestrator = None` and lazy-init helper function
  - [x] 1.4.2 Update `handler()` to call the lazy-init helper instead of creating a new instance

## Phase 2: Security Hardening

- [x] 2.1 Integrate encryption for sensitive DynamoDB fields
  - [x] 2.1.1 Add `KMS_KEY_ID` env var to Orchestrator, DocumentProcessor, CreditCalculator, and SyncHandler Lambdas in `infrastructure_stack.py`
  - [x] 2.1.2 Integrate `encrypt_sensitive_fields()` into `DynamoDBAccess.create_farmer()`, `create_transaction()`, `save_credit_score()` in `dynamodb_access.py`
  - [x] 2.1.3 Integrate `decrypt_sensitive_fields()` into `DynamoDBAccess.get_farmer()`, `get_transactions()`, `get_credit_score()` with backward-compatible plaintext handling
- [x] 2.2 Secure dashboard S3 bucket in `infrastructure_stack.py`
  - [x] 2.2.1 Remove `public_read_access=True` and re-enable `BlockPublicAccess` on dashboard bucket
  - [x] 2.2.2 Add CloudFront distribution with Origin Access Identity (OAI) for dashboard bucket
- [x] 2.3 Switch AppSync from API Key to Cognito User Pools auth in `infrastructure_stack.py`
  - [x] 2.3.1 Create Cognito User Pool and User Pool Client in CDK
  - [x] 2.3.2 Update AppSync `authorization_config` to use Cognito User Pools instead of API_KEY
- [x] 2.4 Add input sanitization to Router in `lambda/router/router.py`
  - [x] 2.4.1 Add max message length check (2000 chars) in `route_to_bedrock_orchestrator()`
  - [x] 2.4.2 Add basic prompt injection detection (block messages containing known injection patterns)
  - [x] 2.4.3 Add special character sanitization before passing text to orchestrator
- [x] 2.5 Add per-sender rate limiting in `lambda/router/router.py`
  - [x] 2.5.1 Add DynamoDB-based rate limit check function (10 messages/minute per phone number with TTL counters)
  - [x] 2.5.2 Integrate rate limit check into `handle_meta_message()` before routing, return friendly "please wait" message when exceeded

## Phase 3: Robustness

- [x] 3.1 Document or implement DynamoDBAccess adoption for audit trails
  - [x] 3.1.1 Add code comments in each Lambda handler documenting that direct boto3 calls bypass `DynamoDBAccess` audit trails
  - [x] 3.1.2 Optionally: refactor critical write paths (credit score storage, transaction sync) to use `DynamoDBAccess` or add DynamoDB Streams-based audit
- [x] 3.2 Fix Orchestrator timeout mismatch in `infrastructure_stack.py`
  - [x] 3.2.1 Change Orchestrator Lambda timeout from `Duration.seconds(60)` to `Duration.seconds(180)`
- [x] 3.3 Ensure circuit breaker state persists across warm invocations
  - [x] 3.3.1 Verify that task 1.4 (module-level `BedrockOrchestrator`) resolves this — circuit breaker state in `LLMAdapter` survives warm invocations when the instance is module-level
- [x] 3.4 Add TTL to conversation items in `lambda/orchestrator/orchestrator.py`
  - [x] 3.4.1 Add `ttl` attribute (epoch timestamp 30 days from now) to conversation items in `maintain_context()` and any `_store_conversation` methods
  - [x] 3.4.2 Document that DynamoDB TTL must be enabled on the `KisanSetuData` table for the `ttl` attribute
- [x] 3.5 Normalize dashboard credit score scale in `kisan-setu-mvp/dashboard/app.js`
  - [x] 3.5.1 Change chart Y-axis from 550-850 range to 0-100 range to match CreditEngine output
  - [x] 3.5.2 Update demo data values from `[620, 635, 645, 660, 675, 685]` to 0-100 scale equivalents

## Phase 4: Credit Score Accuracy

- [x] 4.1 Implement real `_calculate_dues_score()` in `lambda/credit/credit.py`
  - [x] 4.1.1 Replace hardcoded `return 4.5` with DynamoDB query for outstanding payment records
  - [x] 4.1.2 Calculate score based on ratio of paid vs outstanding dues
- [x] 4.2 Fix `financial_behavior` max score to reach 15.0 in `lambda/credit/credit.py`
  - [x] 4.2.1 Normalize `_calculate_payment_score()` and `_calculate_dues_score()` so their weighted sum (0.7 + 0.3) can reach 15.0
  - [x] 4.2.2 Update method docstrings to reflect new max values
- [x] 4.3 Standardize transaction status field in `lambda/credit/credit.py`
  - [x] 4.3.1 Change `_calculate_fulfillment_score()` default from `'fulfilled'` to a consistent value (e.g., `'completed'`)
  - [x] 4.3.2 Change `_calculate_success_score()` default from `'success'` to the same consistent value
- [x] 4.4 Fix `DynamoDBAccess` env var name mismatch in `lambda/common/dynamodb_access.py`
  - [x] 4.4.1 Change `os.environ.get('DYNAMODB_TABLE_NAME', 'KisanSetuData')` to `os.environ.get('DYNAMODB_TABLE', 'KisanSetuData')` in both module-level and class `__init__`

## Phase 5: Cleanup

- [x] 5.1 Remove dead code files
  - [x] 5.1.1 Delete or move `lambda/sync/sync_manager.py` to `tests/lib/` (verify it's not imported anywhere)
  - [x] 5.1.2 Remove `_invoke_model()` and `_invoke_fallback()` methods from `lambda/orchestrator/orchestrator.py`
  - [x] 5.1.3 Delete `lambda/common/error_handler_example.py`
  - [x] 5.1.4 Delete `lambda/whatsapp/webhook_handler.py` (or move to `docs/reference/`)
- [x] 5.2 Remove unused Router env vars from `infrastructure_stack.py`
  - [x] 5.2.1 Remove `CREDIT_CALCULATOR_FUNCTION` and `SATELLITE_ANALYZER_FUNCTION` from Router Lambda environment dict
- [x] 5.3 Move class instantiation to module level for warm invocation reuse
  - [x] 5.3.1 Move `MetaWhatsAppInterface()` to module level with lazy init in `lambda/orchestrator/orchestrator.py` and `lambda/processor/processor.py`
  - [x] 5.3.2 Move `SatelliteAnalyzer()` to module level with lazy init in `lambda/satellite/satellite_analyzer.py`
  - [x] 5.3.3 Move `CreditEngine(table)` to module level with lazy init in `lambda/credit/credit.py`
- [x] 5.4 Add missing SNS env vars to KnowledgeBase and SyncHandler in `infrastructure_stack.py`
  - [x] 5.4.1 Add `"SNS_ALERT_TOPIC_ARN": alert_topic.topic_arn` to KnowledgeBase Lambda environment dict
  - [x] 5.4.2 Add `"SNS_ALERT_TOPIC_ARN": alert_topic.topic_arn` to SyncHandler Lambda environment dict

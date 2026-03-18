# Implementation Plan: Production Readiness (Phase 6)

## Overview

Harden the Kisan Setu MVP for production across 11 requirements: CloudWatch alarms, SNS email config, DynamoDB PITR, provisioned concurrency, dashboard live API integration, Redis dead code removal, per-function IAM roles, Bedrock Agent env var cleanup, module-level imports, idempotent seeding, and documentation updates. All CDK infrastructure changes target `infrastructure_stack.py`; standalone code changes target `dashboard/app.js`, `cost_optimization.py`, `satellite_mock.py`, and `seed_data.py`. Tests use pytest + hypothesis with aws_cdk.assertions for CDK template validation.

## Tasks

- [x] 1. Per-function least-privilege IAM roles
  - [x] 1.1 Create helper function `_create_lambda_role` and define 8 individual IAM roles with scoped permissions
    - Add `_create_lambda_role(self, name, extra_policies)` helper method to `KisanSetuMVPStack`
    - Create 8 roles following the permission matrix from the design (Router, Orchestrator, DocumentProcessor, VoiceHandler, CreditCalculator, SatelliteAnalyzer, KnowledgeBase, SyncHandler)
    - Scope DynamoDB permissions to `table.table_arn` and `f"{table.table_arn}/index/*"` instead of `AmazonDynamoDBFullAccess`
    - Scope S3 permissions to specific bucket ARNs (`raw_bucket`, `processed_bucket`, `archive_bucket`) instead of `AmazonS3FullAccess`
    - Assign each role to its corresponding Lambda function
    - Remove the shared `lambda_role` and all its policy statements
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8, 7.9, 7.10, 7.11, 7.12, 7.13_

  - [ ]* 1.2 Write property test for per-function IAM role isolation
    - **Property 2: Per-function IAM role isolation**
    - Synthesize the CDK template and verify each of the 8 Lambda functions has a unique IAM role with `AWSLambdaBasicExecutionRole` managed policy
    - **Validates: Requirements 7.1, 7.2**

  - [ ]* 1.3 Write property test for IAM resource scoping
    - **Property 3: IAM resource scoping — no wildcard DynamoDB or S3**
    - Extract all IAM policy statements from synthesized template, verify DynamoDB/S3 resource ARNs are never wildcards
    - **Validates: Requirements 7.12, 7.13**

  - [ ]* 1.4 Write unit tests for per-function IAM permissions
    - Test each of the 8 Lambda roles has correct specific permissions per the permission matrix (Req 7.3-7.10)
    - Test shared `lambda_role` is absent from the synthesized template (Req 7.11)
    - _Requirements: 7.3, 7.4, 7.5, 7.6, 7.7, 7.8, 7.9, 7.10, 7.11_

- [x] 2. CloudWatch alarms and SNS alert configuration
  - [x] 2.1 Add CloudWatch alarms for all Lambda functions and API Gateway
    - Add `aws_cloudwatch` and `aws_cloudwatch_actions` imports to `infrastructure_stack.py`
    - Create a `lambda_functions` dict mapping names to Lambda references
    - Loop over all 8 Lambda functions to create Errors and Throttles alarms (threshold 0, period 5 min, 1 eval period)
    - Create API Gateway 5xx alarm (threshold 0, period 5 min)
    - Create API Gateway p99 latency alarm (threshold 10000ms, period 5 min)
    - All alarms send notifications to `alert_topic` via `SnsAction`
    - Total: 18 alarms (8×2 Lambda + 2 API Gateway)
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [x] 2.2 Add SNS email subscription via CDK context parameter
    - Replace the commented-out email subscription with `self.node.try_get_context('alert_email')` pattern
    - When `alert_email` is provided, add `EmailSubscription` to `alert_topic`
    - When absent, deploy without subscription and without errors
    - _Requirements: 2.1, 2.2, 2.3_

  - [ ]* 2.3 Write property test for Lambda alarm completeness
    - **Property 1: Lambda alarm completeness**
    - Synthesize CDK template and verify every Lambda function has both Errors and Throttles alarms with threshold 0, period 300s, 1 eval period, and SNS alarm action
    - **Validates: Requirements 1.1, 1.2, 1.4**

  - [ ]* 2.4 Write unit tests for API Gateway alarms and SNS email
    - Test API Gateway 5xx alarm exists with correct config (Req 1.3)
    - Test API Gateway p99 latency alarm exists with threshold 10000ms (Req 1.5)
    - Test `alert_email` context provided → email subscription exists (Req 2.2)
    - Test `alert_email` context absent → no email subscription, no error (Req 2.3)
    - _Requirements: 1.3, 1.5, 2.2, 2.3_

- [x] 3. DynamoDB PITR and provisioned concurrency
  - [x] 3.1 Enable DynamoDB Point-in-Time Recovery via AwsCustomResource
    - Add `custom_resources as cr` import to `infrastructure_stack.py`
    - Create `AwsCustomResource` with `updateContinuousBackups` SDK call targeting `KisanSetuData`
    - Scope the custom resource policy to `dynamodb:UpdateContinuousBackups` and `dynamodb:DescribeContinuousBackups` on the table ARN
    - _Requirements: 3.1, 3.2_

  - [x] 3.2 Add provisioned concurrency for Router and Orchestrator Lambdas
    - Publish a version for Router and Orchestrator via `current_version`
    - Create `lambda_.Alias` with `alias_name="live"` and `provisioned_concurrent_executions=2` for each
    - Update API Gateway `/webhook` POST and GET integrations to use `router_alias` instead of `router_lambda`
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

  - [ ]* 3.3 Write unit tests for PITR and provisioned concurrency
    - Test PITR AwsCustomResource exists with correct SDK call parameters (Req 3.1)
    - Test Router provisioned concurrency = 2 (Req 4.1)
    - Test Orchestrator provisioned concurrency = 2 (Req 4.2)
    - Test Router and Orchestrator have version + alias (Req 4.3)
    - Test API Gateway webhook integration points to Router alias (Req 4.4)
    - _Requirements: 3.1, 4.1, 4.2, 4.3, 4.4_

- [x] 4. Checkpoint — Verify CDK infrastructure changes
  - Ensure all tests pass, ask the user if questions arise.
  - Run `cdk synth` to verify the template synthesizes without errors.

- [x] 5. Remove Bedrock Agent env vars from test files
  - Verify `BEDROCK_AGENT_ID` and `BEDROCK_AGENT_ALIAS_ID` are not present in any Lambda environment in `infrastructure_stack.py` (already confirmed absent)
  - Remove references to these env vars from test files (`test_orchestrator.py`, `test_bug_lambda_function_name_fix.py`) if present
  - _Requirements: 8.1, 8.2_

- [x] 6. Remove dead Redis code from CacheManager
  - [x] 6.1 Strip Redis code and simplify CacheManager to in-memory only
    - Remove `import redis` try/except block and `REDIS_AVAILABLE` flag from `cost_optimization.py`
    - Remove `REDIS_ENDPOINT` and `REDIS_PORT` environment variable references
    - Remove `redis_endpoint` and `redis_port` parameters from `CacheManager.__init__`
    - Remove `self.redis_client` initialization and Redis connection logic
    - Remove all Redis-specific branches from `get()`, `set()`, `delete()` methods
    - Retain in-memory cache with TTL-based expiry as sole mechanism
    - Update module docstring to reflect in-memory caching only
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [ ]* 6.2 Write property test for CacheManager in-memory round trip
    - **Property 4: CacheManager in-memory round trip**
    - Generate random string keys and values, verify set+get returns original value before TTL, returns None after TTL
    - **Validates: Requirements 6.5**

  - [ ]* 6.3 Write unit tests for CacheManager Redis removal
    - Test no Redis imports or references exist in module (Req 6.1-6.4)
    - Test module docstring mentions in-memory only (Req 6.6)
    - Test cache delete removes entry (Req 6.5)
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

- [x] 7. Module-level imports in Satellite Mock
  - [x] 7.1 Move imports to module level in `satellite_mock.py`
    - Move `numpy`, `PIL`, `boto3`, and `io` imports from inside `generate_mock_heatmap_url()` to module level
    - Add try/except guard for `numpy` and `PIL` with `IMAGING_AVAILABLE` flag
    - Set `np`, `Image`, `ImageDraw` to None when unavailable
    - Update `generate_mock_heatmap_url()` to check `IMAGING_AVAILABLE` flag and return None with warning log if False
    - _Requirements: 9.1, 9.2, 9.3_

  - [ ]* 7.2 Write unit tests for Satellite Mock imports
    - Test numpy/PIL imported at module level (Req 9.1)
    - Test module loads without error when numpy/PIL unavailable (Req 9.2)
    - Test `generate_mock_heatmap_url` returns None when `IMAGING_AVAILABLE` is False (Req 9.3)
    - _Requirements: 9.1, 9.2, 9.3_

- [x] 8. Idempotent seed script
  - [x] 8.1 Add conditional writes and summary reporting to `seed_data.py`
    - Add `from botocore.exceptions import ClientError` import
    - Create `_put_item_idempotent(item)` helper that uses `ConditionExpression='attribute_not_exists(PK)'`
    - Catch `ConditionalCheckFailedException` to skip existing items and log skip message
    - Replace all `table.put_item(Item=...)` calls with `_put_item_idempotent(item)` in all seed functions
    - Track created/skipped counts in each seed function
    - Print summary at completion: `Created: N, Skipped: M`
    - _Requirements: 10.1, 10.2, 10.3_

  - [ ]* 8.2 Write property test for seed script idempotent writes
    - **Property 5: Seed script idempotent writes**
    - Generate random DynamoDB items with PK/SK, call `_put_item_idempotent` twice, verify second call returns False and original item is unchanged
    - Use mocked DynamoDB table (moto or manual mock)
    - **Validates: Requirements 10.1, 10.2**

  - [ ]* 8.3 Write unit tests for seed script idempotency
    - Test second run skips existing items without error (Req 10.2)
    - Test summary output includes created and skipped counts (Req 10.3)
    - _Requirements: 10.2, 10.3_

- [x] 9. Checkpoint — Verify standalone Python changes
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Dashboard live API integration
  - [x] 10.1 Replace mock data with real API fetch calls in `dashboard/app.js`
    - Add `API_KEY` constant and `apiFetch(path)` helper with `x-api-key` header
    - Add `fetchWithRetry(path, retryDelay)` wrapper with error handling and 5-second retry
    - Replace `mockFarmers` array in `initSatelliteMap()` with `fetchFarmers()` API call
    - Replace mock `dates`/`scores` in `initCreditChart()` with `fetchCreditScores()` API call
    - Replace `addDemoMessages()` in `fetchMessages()` with real API fetch
    - Remove the `setInterval` that generates random demo messages at the bottom of the file
    - Keep the 5-second polling interval for `fetchMessages()`
    - Add error/retry UI via `showError()` when API requests fail
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

- [x] 11. Update all project documentation
  - [x] 11.1 Update `personal_go_to_task.md`
    - Mark all Phase 6 Production Readiness items as completed (✅)
    - Mark Informational items (#3, #6, #33, #34, #38) as completed
    - _Requirements: 11.1_

  - [x] 11.2 Update `README.md`
    - Add Phase 6 production readiness capabilities (CloudWatch alarms, least-privilege IAM, provisioned concurrency, PITR, live dashboard)
    - _Requirements: 11.2_

  - [x] 11.3 Update `architecture.md`
    - Document per-function IAM roles, CloudWatch alarms, and provisioned concurrency additions
    - _Requirements: 11.3_

  - [x] 11.4 Update `IMPLEMENTATION_STATUS_AND_TASKS.md`
    - Add Phase 6 section listing all completed production readiness tasks
    - _Requirements: 11.4_

  - [x] 11.5 Update `BENCHMARK_REPORT.md`
    - Add Phase 6 audit results
    - _Requirements: 11.5_

  - [x] 11.6 Update `FAQ.md`
    - Add Q&A entries for CloudWatch alarms, provisioned concurrency, PITR, per-function IAM, live dashboard
    - _Requirements: 11.6_

  - [x] 11.7 Update `TROUBLESHOOTING.md`
    - Add troubleshooting entries for CloudWatch alarms, provisioned concurrency, and PITR
    - _Requirements: 11.7_

  - [x] 11.8 Update `kisan-setu-mvp/README.md`
    - Reflect all production readiness changes
    - _Requirements: 11.8_

- [x] 12. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.
  - Run `cdk synth` to verify the full stack synthesizes correctly with all changes.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- All CDK tests use `aws_cdk.assertions` for CloudFormation template validation
- Python tests use `pytest` + `hypothesis`, run from `kisan-setu-mvp/` directory
- Task 11 (documentation) is intentionally last since it documents everything else

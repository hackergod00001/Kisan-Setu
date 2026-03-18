# Requirements Document

## Introduction

This document specifies the production readiness requirements for the Kisan Setu MVP — an AI-powered agricultural advisory platform for Indian farmers via WhatsApp. The system is deployed on AWS using CDK (Python), with 8 Lambda functions, a DynamoDB single-table, API Gateway, AppSync, and Bedrock AI.

Phase 6 addresses all remaining fixable items from the architecture audit: operational monitoring, security hardening via least-privilege IAM, data durability, performance optimization, dead code removal, dashboard live data integration, and seed script idempotency.

## Glossary

- **Infrastructure_Stack**: The single AWS CDK stack (`infrastructure_stack.py`) that defines all cloud resources for Kisan Setu MVP.
- **Lambda_Function**: An individual AWS Lambda function deployed as part of the Kisan Setu system. There are 8 Lambda functions: Router, Orchestrator, Document Processor, Voice Handler, Credit Calculator, Satellite Analyzer, Knowledge Base, and Sync Handler.
- **Router_Lambda**: The Lambda function that receives WhatsApp webhook events and routes messages to downstream Lambdas.
- **Orchestrator_Lambda**: The Lambda function that coordinates AI-powered responses using Bedrock, invoking downstream Lambdas as needed.
- **Alert_Topic**: The existing SNS topic (`kisan-setu-critical-alerts`) used for critical error notifications.
- **Dashboard**: The web-based monitoring dashboard (`dashboard/app.js`) served via CloudFront.
- **API_Gateway**: The REST API Gateway that exposes webhook, process, credit, and knowledge endpoints.
- **CacheManager**: The caching utility class in `lambda/common/cost_optimization.py` used by Lambda functions.
- **Seed_Script**: The `seed_data.py` script that populates the DynamoDB table with test data.
- **DynamoDB_Table**: The `KisanSetuData` single-table design DynamoDB table imported via `from_table_name` in the CDK stack.
- **Satellite_Mock**: The `satellite_mock.py` module that generates mock NDVI data and heatmap images.

## Requirements

### Requirement 1: CloudWatch Alarms for Lambda and API Gateway

**User Story:** As an operations engineer, I want CloudWatch alarms on Lambda errors, throttling, and API Gateway 5xx responses, so that the team is notified of production issues before users are impacted.

#### Acceptance Criteria

1. THE Infrastructure_Stack SHALL create a CloudWatch alarm for each Lambda_Function that triggers when the Errors metric exceeds 0 within a 5-minute evaluation period.
2. THE Infrastructure_Stack SHALL create a CloudWatch alarm for each Lambda_Function that triggers when the Throttles metric exceeds 0 within a 5-minute evaluation period.
3. THE Infrastructure_Stack SHALL create a CloudWatch alarm for the API_Gateway that triggers when the 5XXError metric exceeds 0 within a 5-minute evaluation period.
4. WHEN a CloudWatch alarm transitions to ALARM state, THE Infrastructure_Stack SHALL configure the alarm to send a notification to the Alert_Topic.
5. THE Infrastructure_Stack SHALL create a CloudWatch alarm for the API_Gateway that triggers when the Latency p99 metric exceeds 10000 milliseconds within a 5-minute evaluation period.

### Requirement 2: SNS Alert Subscriber Configuration Pattern

**User Story:** As a platform administrator, I want a documented and configurable pattern for adding SNS email subscribers, so that alert recipients can be managed without modifying CDK code.

#### Acceptance Criteria

1. THE Infrastructure_Stack SHALL accept an optional CDK context parameter named `alert_email` for specifying an SNS email subscriber.
2. WHEN the `alert_email` context parameter is provided, THE Infrastructure_Stack SHALL add an email subscription to the Alert_Topic using the provided address.
3. WHEN the `alert_email` context parameter is not provided, THE Infrastructure_Stack SHALL deploy without an SNS email subscription and without errors.

### Requirement 3: DynamoDB Point-in-Time Recovery

**User Story:** As a data engineer, I want Point-in-Time Recovery enabled on the DynamoDB table, so that data can be restored to any second within the last 35 days in case of accidental deletion or corruption.

#### Acceptance Criteria

1. THE Infrastructure_Stack SHALL enable Point-in-Time Recovery on the DynamoDB_Table using an AWS CDK custom resource or an equivalent CDK-native mechanism.
2. IF the custom resource fails to enable Point-in-Time Recovery, THEN THE Infrastructure_Stack SHALL surface the error in the CloudFormation deployment output.
3. THE requirements document SHALL include an alternative AWS CLI command to enable Point-in-Time Recovery manually: `aws dynamodb update-continuous-backups --table-name KisanSetuData --point-in-time-recovery-specification PointInTimeRecoveryEnabled=true`.

### Requirement 4: Provisioned Concurrency for Critical Lambdas

**User Story:** As a platform engineer, I want provisioned concurrency on the Router and Orchestrator Lambdas, so that cold starts do not degrade the WhatsApp message response time.

#### Acceptance Criteria

1. THE Infrastructure_Stack SHALL configure provisioned concurrency of 2 instances on the Router_Lambda.
2. THE Infrastructure_Stack SHALL configure provisioned concurrency of 2 instances on the Orchestrator_Lambda.
3. THE Infrastructure_Stack SHALL publish a Lambda version and create an alias for each Lambda_Function that has provisioned concurrency configured.
4. WHEN provisioned concurrency is configured, THE Infrastructure_Stack SHALL update the API_Gateway integration to point to the Lambda alias instead of the $LATEST version.

### Requirement 5: Dashboard Live API Integration

**User Story:** As an FPO manager, I want the dashboard to display real farmer data from the API, so that I can monitor actual platform activity instead of mock data.

#### Acceptance Criteria

1. THE Dashboard SHALL fetch farmer location and NDVI data from the API_Gateway `/webhook` or a dedicated read endpoint and render markers on the satellite map.
2. THE Dashboard SHALL fetch credit score history from the API_Gateway and render the data in the credit score chart.
3. THE Dashboard SHALL fetch recent messages from the API_Gateway and render the data in the live message feed.
4. IF an API request fails, THEN THE Dashboard SHALL display an error message to the user and retry the request after 5 seconds.
5. THE Dashboard SHALL include the `x-api-key` header in all authenticated API_Gateway requests.
6. WHILE the Dashboard is active, THE Dashboard SHALL poll the API_Gateway for new messages every 5 seconds.

### Requirement 6: Remove Dead Redis Code Path from CacheManager

**User Story:** As a developer, I want the CacheManager to contain only the in-memory cache implementation, so that the codebase does not include dead code for an undeployed Redis dependency.

#### Acceptance Criteria

1. THE CacheManager SHALL remove the `import redis` statement and the `REDIS_AVAILABLE` flag.
2. THE CacheManager SHALL remove the `REDIS_ENDPOINT` and `REDIS_PORT` environment variable references.
3. THE CacheManager SHALL remove all Redis client initialization logic from the `__init__` method.
4. THE CacheManager SHALL remove all Redis-specific branches from the `get`, `set`, and `delete` methods.
5. THE CacheManager SHALL retain the in-memory cache implementation with TTL-based expiry as the sole caching mechanism.
6. THE CacheManager module docstring SHALL be updated to reflect that only in-memory caching is supported.

### Requirement 7: Per-Function Least-Privilege IAM Roles

**User Story:** As a security engineer, I want each Lambda function to have its own IAM role with only the permissions it needs, so that a compromise of one function does not grant access to unrelated AWS services.

#### Acceptance Criteria

1. THE Infrastructure_Stack SHALL create a separate IAM role for each of the 8 Lambda functions.
2. THE Infrastructure_Stack SHALL grant each Lambda_Function IAM role only the `AWSLambdaBasicExecutionRole` managed policy plus the specific permissions required by that function.
3. THE Router_Lambda IAM role SHALL include permissions for DynamoDB read/write, S3 read/write, Lambda invoke, Secrets Manager read, SNS publish, and KMS decrypt/encrypt.
4. THE Orchestrator_Lambda IAM role SHALL include permissions for DynamoDB read/write, S3 read, Lambda invoke, Bedrock invoke/converse, Secrets Manager read, SNS publish, and KMS decrypt/encrypt.
5. THE Document Processor Lambda IAM role SHALL include permissions for DynamoDB read/write, S3 read/write, Textract analyze, SNS publish, Secrets Manager read, and KMS decrypt/encrypt.
6. THE Voice Handler Lambda IAM role SHALL include permissions for DynamoDB read/write, S3 read/write, Transcribe start/get, Polly synthesize, Lambda invoke, SNS publish, Secrets Manager read, and KMS decrypt/encrypt.
7. THE Credit Calculator Lambda IAM role SHALL include permissions for DynamoDB read/write, SNS publish, and KMS decrypt/encrypt.
8. THE Satellite Analyzer Lambda IAM role SHALL include permissions for DynamoDB read/write, S3 read/write, SageMaker Geospatial access, SNS publish, and KMS decrypt/encrypt.
9. THE Knowledge Base Lambda IAM role SHALL include permissions for DynamoDB read/write, Bedrock retrieve/invoke, OpenSearch Serverless access, SNS publish, and KMS decrypt/encrypt.
10. THE Sync Handler Lambda IAM role SHALL include permissions for DynamoDB read/write, SNS publish, and KMS decrypt/encrypt.
11. THE Infrastructure_Stack SHALL remove the shared `lambda_role` after all Lambda functions are assigned individual roles.
12. THE Infrastructure_Stack SHALL scope DynamoDB permissions to the specific `KisanSetuData` table ARN instead of using `AmazonDynamoDBFullAccess`.
13. THE Infrastructure_Stack SHALL scope S3 permissions to the specific Kisan Setu bucket ARNs instead of using `AmazonS3FullAccess`.

### Requirement 8: Remove Unused Bedrock Agent Environment Variables

**User Story:** As a developer, I want unused environment variables removed from the CDK stack, so that the configuration does not mislead future maintainers about the system's dependencies.

#### Acceptance Criteria

1. THE Infrastructure_Stack SHALL remove the `BEDROCK_AGENT_ID` environment variable from any Lambda_Function that does not use Bedrock Agent invocations.
2. THE Infrastructure_Stack SHALL remove the `BEDROCK_AGENT_ALIAS_ID` environment variable from any Lambda_Function that does not use Bedrock Agent invocations.


### Requirement 9: Move Module-Level Imports in Satellite Mock

**User Story:** As a developer, I want heavy library imports in `satellite_mock.py` moved to module level, so that cold-start latency is reduced by avoiding repeated import overhead inside function calls.

#### Acceptance Criteria

1. THE Satellite_Mock SHALL import `numpy`, `PIL`, `boto3`, and `io` at module level instead of inside the `generate_mock_heatmap_url` method.
2. THE Satellite_Mock SHALL continue to function correctly when `numpy` or `PIL` are not installed, by using a try/except guard at module level and setting a flag indicating availability.
3. IF `numpy` or `PIL` is not available at import time, THEN THE Satellite_Mock `generate_mock_heatmap_url` method SHALL return None and log a warning.

### Requirement 10: Idempotent Seed Script

**User Story:** As a developer, I want the seed script to be idempotent, so that re-running it does not overwrite manually modified data or produce duplicate side effects.

#### Acceptance Criteria

1. THE Seed_Script SHALL use DynamoDB conditional writes (`attribute_not_exists(PK)`) for all `put_item` calls to prevent overwriting existing items.
2. WHEN a conditional write fails because the item already exists, THE Seed_Script SHALL log a skip message and continue without error.
3. THE Seed_Script SHALL report a summary at completion indicating how many items were created and how many were skipped.

### Requirement 11: Update Project Documentation After All Fixes

**User Story:** As a developer or contributor, I want all project markdown documentation updated to reflect the completed Phase 6 production readiness changes, so that the docs remain accurate and trustworthy.

#### Acceptance Criteria

1. THE `personal_go_to_task.md` SHALL mark all Phase 6 Production Readiness items and Informational items as completed (✅) after their corresponding fixes are implemented.
2. THE `README.md` SHALL be updated to reflect the new production readiness capabilities (CloudWatch alarms, least-privilege IAM, provisioned concurrency, PITR, live dashboard).
3. THE `architecture.md` SHALL be updated to document the per-function IAM roles, CloudWatch alarms, and provisioned concurrency additions.
4. THE `IMPLEMENTATION_STATUS_AND_TASKS.md` SHALL include a Phase 6 section listing all completed production readiness tasks.
5. THE `BENCHMARK_REPORT.md` SHALL be updated to include Phase 6 audit results.
6. THE `FAQ.md` SHALL be updated to address questions about the new production readiness features.
7. THE `TROUBLESHOOTING.md` SHALL be updated with troubleshooting entries for CloudWatch alarms, provisioned concurrency, and PITR.
8. THE `kisan-setu-mvp/README.md` SHALL be updated to reflect the production readiness changes.

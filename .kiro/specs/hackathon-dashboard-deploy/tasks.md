# Implementation Plan: Hackathon Dashboard Deploy

## Overview

Implement the remaining hackathon deliverables for Kisan-Setu: S3 static website deployment for the dashboard, LLM adapter with Bedrock Converse API and multi-model fallback, orchestrator integration, IAM permissions, mock satellite NDVI data, and hackathon submission artifacts (README, presentation outline, demo video script). All implementation is in Python using the existing CDK stack and Lambda architecture.

## Tasks

- [x] 1. Add S3 Dashboard Bucket and deployment to CDK stack
  - [x] 1.1 Add S3 bucket with static website hosting to `infrastructure_stack.py`
    - Import `aws_s3_deployment` and `RemovalPolicy` in `kisan-setu-mvp/infrastructure_stack.py`
    - Create `dashboard_bucket` S3 bucket with `website_index_document="index.html"`, `public_read_access=True`, all `BlockPublicAccess` flags set to `False`, `RemovalPolicy.DESTROY`, and `auto_delete_objects=True`
    - Add `s3_deployment.BucketDeployment` to upload `dashboard/` directory contents to the bucket
    - Add `CfnOutput` named `DashboardURL` with `dashboard_bucket.bucket_website_url`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.6_

  - [ ]* 1.2 Write CDK template assertion tests for dashboard bucket
    - Test that synthesized template contains S3 bucket with `WebsiteConfiguration`
    - Test that template contains public read bucket policy
    - Test that template contains `BucketDeployment` resource
    - Test that template contains `DashboardURL` output
    - Add tests to `kisan-setu-mvp/tests/test_dashboard_deployment.py`
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [x] 2. Implement LLM Adapter with Converse API and multi-model fallback
  - [x] 2.1 Create `LLMAdapter` class in `kisan-setu-mvp/lambda/common/llm_adapter.py`
    - Define `LLMAdapterError` exception class with `errors` list attribute containing per-model `{"model": ..., "error": ...}` entries
    - Implement `LLMAdapter` class with `FALLBACK_CHAIN` list: Claude Sonnet → Claude Haiku → Amazon Titan
    - Implement `converse(prompt, system_prompt=None) -> str` method that:
      - Formats requests using Converse API message structure with `role` and `content` fields
      - Includes `system` field only when `system_prompt` is provided
      - Iterates through fallback chain on error/throttle
      - Extracts text from `output.message.content[0].text`
      - Raises `LLMAdapterError` with all model errors when chain is exhausted
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [ ]* 2.2 Write property test: Converse API request formatting
    - **Property 1: Converse API request formatting**
    - **Validates: Requirements 2.4, 2.6**
    - Add to `kisan-setu-mvp/tests/test_llm_adapter_properties.py`
    - Generate random prompt strings and optional system prompts using Hypothesis
    - Assert request contains `messages` array with `role: "user"` and matching `content` text
    - Assert `system` field present if and only if system prompt provided

  - [ ]* 2.3 Write property test: Fallback on model failure
    - **Property 2: Fallback on model failure**
    - **Validates: Requirements 2.2**
    - Add to `kisan-setu-mvp/tests/test_llm_adapter_properties.py`
    - Generate random failure patterns across model chain (some fail, at least one succeeds)
    - Assert adapter returns response from first successful model in chain order

  - [ ]* 2.4 Write property test: Exhausted fallback chain raises descriptive error
    - **Property 3: Exhausted fallback chain raises descriptive error**
    - **Validates: Requirements 2.3**
    - Add to `kisan-setu-mvp/tests/test_llm_adapter_properties.py`
    - Generate all-fail error combinations for every model in chain
    - Assert `LLMAdapterError` raised with `errors` list length equal to fallback chain length

  - [ ]* 2.5 Write property test: Response text extraction
    - **Property 4: Response text extraction**
    - **Validates: Requirements 2.5**
    - Add to `kisan-setu-mvp/tests/test_llm_adapter_properties.py`
    - Generate random Converse API response payloads with `output.message.content[0].text`
    - Assert adapter returns exactly that text string unmodified

- [x] 3. Integrate LLM Adapter into Orchestrator
  - [x] 3.1 Replace direct Bedrock calls with LLM Adapter in `kisan-setu-mvp/lambda/orchestrator/orchestrator.py`
    - Import `LLMAdapter` and `LLMAdapterError` from `common.llm_adapter`
    - Replace `_invoke_model()` and `_invoke_fallback()` calls with `LLMAdapter.converse()`
    - Pass the existing `SYSTEM_PROMPT` as the `system_prompt` parameter
    - Catch `LLMAdapterError` and return localized user-friendly error message based on farmer's `language` field
    - _Requirements: 3.1, 3.2, 3.3_

  - [ ]* 3.2 Write property test: Localized error response on adapter failure
    - **Property 5: Localized error response on adapter failure**
    - **Validates: Requirements 3.3**
    - Add to `kisan-setu-mvp/tests/test_orchestrator_error_properties.py`
    - Generate random language codes from supported set (hi-IN, mr-IN, ta-IN, en)
    - Assert orchestrator returns non-empty error message string in that language when adapter raises exception

  - [ ]* 3.3 Write unit tests for orchestrator LLM adapter integration
    - Test that orchestrator calls `LLMAdapter.converse()` instead of direct Bedrock calls
    - Test that orchestrator passes system prompt to adapter
    - Add to `kisan-setu-mvp/tests/test_orchestrator.py` or new test file
    - _Requirements: 3.1, 3.2_

- [x] 4. Add Bedrock Converse IAM permissions to CDK stack
  - [x] 4.1 Add `bedrock:Converse` action to Lambda execution role IAM policy in `infrastructure_stack.py`
    - Add `bedrock:Converse` to the existing Bedrock IAM policy statement actions list
    - Use the same resource pattern (`"*"`) as existing Bedrock permissions
    - _Requirements: 4.1, 4.2_

  - [ ]* 4.2 Write CDK template assertion test for Bedrock Converse permission
    - Test that synthesized template IAM policy includes `bedrock:Converse` action
    - Add to `kisan-setu-mvp/tests/test_dashboard_deployment.py`
    - _Requirements: 4.1, 4.2_

- [x] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement Mock Satellite NDVI module
  - [x] 6.1 Create `SatelliteMock` class in `kisan-setu-mvp/lambda/satellite/satellite_mock.py`
    - Define `MAHARASHTRA_BOUNDS` dict with lat/lon min/max (lat 15.6–22.1, lon 72.6–80.9)
    - Implement `get_ndvi_data(latitude, longitude) -> dict | None` that:
      - Returns `None` for coordinates outside Maharashtra bounds
      - Generates deterministic NDVI values (0.3–0.9) using coordinate hash + date component for 24-hour consistency
      - Returns dict with `ndvi_value`, `crop_type`, `maturity_stage`, `health_status`, `estimated_yield`, `coordinates`, `generated_at`, `data_source`
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [ ]* 6.2 Write property test: Mock NDVI completeness and range for Maharashtra coordinates
    - **Property 6: Mock NDVI completeness and range for Maharashtra coordinates**
    - **Validates: Requirements 5.1, 5.2**
    - Add to `kisan-setu-mvp/tests/test_satellite_mock_properties.py`
    - Generate random Maharashtra GPS coordinates using Hypothesis
    - Assert `ndvi_value` in [0.3, 0.9] and all required fields present

  - [ ]* 6.3 Write property test: Mock NDVI consistency within 24 hours
    - **Property 7: Mock NDVI consistency within 24 hours**
    - **Validates: Requirements 5.3**
    - Add to `kisan-setu-mvp/tests/test_satellite_mock_properties.py`
    - Call satellite mock twice with same coordinates and same date
    - Assert identical values for all fields

  - [ ]* 6.4 Write property test: Out-of-bounds coordinates return no data
    - **Property 8: Out-of-bounds coordinates return no data**
    - **Validates: Requirements 5.4**
    - Add to `kisan-setu-mvp/tests/test_satellite_mock_properties.py`
    - Generate random GPS coordinates outside Maharashtra bounds
    - Assert return value is `None`

- [x] 7. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Create Hackathon README
  - [x] 8.1 Create or update `kisan-setu-mvp/README.md` with hackathon submission content
    - Add project title, tagline, and problem statement
    - Add architecture diagram description listing all AWS services (Bedrock, Textract, Transcribe, Polly, SageMaker, DynamoDB, S3, Lambda, API Gateway, AppSync)
    - Add setup and deployment instructions with prerequisites
    - Add "5 Killer Features" section (text, image, voice, credit scoring, satellite)
    - Add live dashboard URL placeholder and demo video link placeholder
    - Add cost analysis section showing system serves 500+ farmers for under $50/month
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

- [x] 9. Create Presentation Outline and Demo Video Script
  - [x] 9.1 Create presentation outline in `kisan-setu-mvp/docs/presentation_outline.md`
    - Write 15-slide outline covering problem, solution, architecture, demo highlights, and impact
    - _Requirements: 7.1_

  - [x] 9.2 Create demo video script in `kisan-setu-mvp/docs/demo_video_script.md`
    - Write 5-minute demo script covering all 5 killer features (text query, image ledger, voice interaction, credit scoring, satellite NDVI)
    - Specify the sequence of WhatsApp interactions to demonstrate each feature
    - _Requirements: 7.2, 7.3_

- [x] 10. Wire end-to-end verification tests
  - [x] 10.1 Create automated E2E test stubs in `kisan-setu-mvp/tests/test_e2e_hackathon_verification.py`
    - Write test for text query processing through orchestrator with LLM adapter
    - Write test for satellite mock NDVI data retrieval with test GPS coordinates
    - Write test for dashboard URL output existence in CDK template
    - Include test stubs for ledger image processing, voice message processing, and credit score calculation (these depend on external services and are marked for manual verification)
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

- [x] 11. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests validate universal correctness properties from the design document
- All Python code uses the existing project patterns (Hypothesis for PBT, pytest, CDK assertions)
- The design uses Python throughout — no language selection needed

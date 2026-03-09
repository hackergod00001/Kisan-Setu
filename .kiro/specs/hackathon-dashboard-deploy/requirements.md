> **Note:** This is a historical spec document. The hackathon is "AI for Bharat Hackathon 2026 powered by AWS" (not "AWS AI Hackathon 2025"). All tasks in this spec have been completed.

# Requirements Document: Hackathon Dashboard Deploy

## Introduction

Kisan-Setu is an AI-powered WhatsApp bot for Indian farmers, built for the AWS AI Hackathon 2025. The project has a working CDK-based backend with Lambda functions, DynamoDB, API Gateway, and AppSync. A static HTML/JS dashboard already exists in `kisan-setu-mvp/dashboard/` showing live message feeds, credit score charts, satellite NDVI maps, and ledger digitization previews.

This spec covers the remaining hackathon deliverables: deploying the dashboard to S3 as a publicly accessible static website (the primary focus for Step 3 MVP Link evaluation), adding the Bedrock Converse API with multi-model fallback to the orchestrator, implementing mock satellite NDVI data, and preparing hackathon submission artifacts (README, presentation, demo video).

## Glossary

- **Dashboard**: The static HTML/JS web application in `kisan-setu-mvp/dashboard/` that displays real-time Kisan-Setu system metrics
- **Dashboard_Bucket**: An S3 bucket configured for static website hosting that serves the Dashboard
- **CDK_Stack**: The AWS CDK infrastructure defined in `infrastructure_stack.py` that provisions all cloud resources
- **LLM_Adapter**: A Python module that wraps the Bedrock Converse API with multi-model fallback logic
- **Orchestrator**: The Bedrock orchestrator Lambda (`lambda/orchestrator/orchestrator.py`) that coordinates AI reasoning across system components
- **Satellite_Mock**: A module providing realistic mock NDVI data for demo purposes when live satellite APIs are unavailable
- **Converse_API**: The Amazon Bedrock Converse API that provides a unified interface across foundation models
- **NDVI**: Normalized Difference Vegetation Index, a satellite-derived measure of vegetation health (range -1.0 to 1.0)
- **Hackathon_Submission**: The collection of artifacts required for AWS AI Hackathon evaluation (MVP link, README, presentation, demo video)

## Requirements

### Requirement 1: S3 Static Website Deployment for Dashboard

**User Story:** As a hackathon judge, I want to access the Kisan-Setu dashboard via a public URL, so that I can evaluate the MVP without setting up any local environment.

#### Acceptance Criteria

1. WHEN the CDK stack is deployed, THE CDK_Stack SHALL create a Dashboard_Bucket with S3 static website hosting enabled
2. WHEN the Dashboard_Bucket is created, THE CDK_Stack SHALL configure a bucket policy that allows public read access to all objects
3. WHEN the CDK stack is deployed, THE CDK_Stack SHALL upload the contents of the `dashboard/` directory (index.html and app.js) to the Dashboard_Bucket
4. WHEN deployment is complete, THE CDK_Stack SHALL output the Dashboard website URL as a CloudFormation output named "DashboardURL"
5. WHEN a user navigates to the Dashboard URL in a browser, THE Dashboard SHALL load and render all panels (message feed, credit chart, satellite map, ledger preview) without errors
6. IF the Dashboard_Bucket already exists from a previous deployment, THEN THE CDK_Stack SHALL update the bucket contents without creating a duplicate bucket

### Requirement 2: LLM Adapter with Converse API and Multi-Model Fallback

**User Story:** As a developer, I want a unified LLM adapter that uses the Bedrock Converse API with automatic fallback across models, so that the system remains functional even if a specific model is unavailable or throttled.

#### Acceptance Criteria

1. THE LLM_Adapter SHALL invoke the Bedrock Converse API as the single interface for all foundation model calls
2. WHEN the primary model (Claude Sonnet) returns an error or is throttled, THE LLM_Adapter SHALL automatically retry with the next model in the fallback chain (Claude Haiku, then Amazon Titan)
3. WHEN all models in the fallback chain fail, THE LLM_Adapter SHALL raise a descriptive exception including the errors from each attempted model
4. WHEN the LLM_Adapter receives a prompt, THE LLM_Adapter SHALL format the request using the Converse API message structure with role and content fields
5. WHEN the LLM_Adapter receives a successful response, THE LLM_Adapter SHALL extract and return the text content from the Converse API response format
6. THE LLM_Adapter SHALL accept an optional system prompt parameter for configuring model behavior per request

### Requirement 3: Orchestrator LLM Integration

**User Story:** As a developer, I want the orchestrator to use the LLM adapter for all AI reasoning, so that the system has reliable multi-model AI capabilities for farmer queries.

#### Acceptance Criteria

1. WHEN the Orchestrator processes a farmer query, THE Orchestrator SHALL use the LLM_Adapter for generating AI responses instead of direct Bedrock Agent calls
2. WHEN the Orchestrator invokes the LLM_Adapter, THE Orchestrator SHALL include a system prompt that defines the Kisan-Setu agricultural assistant persona and available tools
3. WHEN the LLM_Adapter raises an exception, THE Orchestrator SHALL return a user-friendly error message in the farmer's language

### Requirement 4: Bedrock Converse IAM Permissions

**User Story:** As a developer, I want the Lambda execution role to have Bedrock Converse API permissions, so that the LLM adapter can invoke foundation models at runtime.

#### Acceptance Criteria

1. WHEN the CDK stack is deployed, THE CDK_Stack SHALL add `bedrock:Converse` to the IAM policy actions for the Lambda execution role
2. THE CDK_Stack SHALL scope the Bedrock Converse permission to the same resource pattern as existing Bedrock permissions

### Requirement 5: Mock Satellite NDVI Feature

**User Story:** As a hackathon presenter, I want realistic mock satellite NDVI data for demo purposes, so that I can demonstrate the satellite crop health feature without requiring live satellite API access.

#### Acceptance Criteria

1. WHEN a farmer provides GPS coordinates in the Maharashtra region, THE Satellite_Mock SHALL return realistic NDVI values between 0.3 and 0.9 that vary by location
2. WHEN the Satellite_Mock generates NDVI data, THE Satellite_Mock SHALL include crop type, maturity stage, health status, and estimated yield for the given coordinates
3. WHEN the Satellite_Mock generates data for the same coordinates within a 24-hour period, THE Satellite_Mock SHALL return consistent values
4. WHEN GPS coordinates fall outside the supported demo region, THE Satellite_Mock SHALL return a response indicating no satellite data is available for that area

### Requirement 6: Hackathon README

**User Story:** As a hackathon judge reviewing the GitHub repository, I want a comprehensive README, so that I can understand the project architecture, setup instructions, and key features quickly.

#### Acceptance Criteria

1. THE Hackathon_Submission SHALL include a README.md at the repository root with project title, tagline, and problem statement
2. THE Hackathon_Submission README SHALL include an architecture diagram description showing all AWS services used (Bedrock, Textract, Transcribe, Polly, SageMaker, DynamoDB, S3, Lambda, API Gateway, AppSync)
3. THE Hackathon_Submission README SHALL include setup and deployment instructions with prerequisites
4. THE Hackathon_Submission README SHALL include a "5 Killer Features" section describing text, image, voice, credit scoring, and satellite capabilities
5. THE Hackathon_Submission README SHALL include the live dashboard URL and demo video link
6. THE Hackathon_Submission README SHALL include a cost analysis section showing the system can serve 500+ farmers for under $50/month

### Requirement 7: Presentation and Demo Video

**User Story:** As a hackathon presenter, I want a polished slide deck and demo video, so that judges can evaluate the project's innovation and technical depth.

#### Acceptance Criteria

1. THE Hackathon_Submission SHALL include a presentation outline of 15 slides covering problem, solution, architecture, demo highlights, and impact
2. THE Hackathon_Submission SHALL include a demo video script covering all 5 killer features (text query, image ledger processing, voice interaction, credit scoring, satellite NDVI) within 5 minutes
3. WHEN the demo video script is created, THE Hackathon_Submission SHALL specify the sequence of WhatsApp interactions to demonstrate each feature

### Requirement 8: End-to-End Testing and Verification

**User Story:** As a developer preparing for hackathon submission, I want to verify all features work end-to-end, so that the demo runs smoothly during evaluation.

#### Acceptance Criteria

1. WHEN end-to-end testing is performed, THE Kisan_Setu_System SHALL successfully process a text query through WhatsApp and return an AI-generated response
2. WHEN end-to-end testing is performed, THE Kisan_Setu_System SHALL successfully process an uploaded ledger image and return extracted structured data
3. WHEN end-to-end testing is performed, THE Kisan_Setu_System SHALL successfully process a voice message and return a voice response
4. WHEN end-to-end testing is performed, THE Credit_Engine SHALL successfully calculate and return a credit score for a test farmer
5. WHEN end-to-end testing is performed, THE Satellite_Mock SHALL successfully return NDVI data for test GPS coordinates
6. WHEN end-to-end testing is performed, THE Dashboard SHALL be accessible via the public S3 URL and display all panels correctly

# Implementation Plan: Kisan-Setu

## Overview

This implementation plan breaks down the Kisan-Setu AI-powered FPO Operating System into discrete, actionable coding tasks. The system is built on AWS serverless architecture using Python, with WhatsApp as the primary interface, AWS Bedrock for orchestration, and various AWS AI services for document processing, voice interaction, and satellite analysis.

The implementation follows an incremental approach: infrastructure setup → core components → AI integrations → testing → integration. Each task builds on previous work to ensure no orphaned code.

## Tasks

- [x] 1. Set up AWS infrastructure and project foundation
  - Create AWS CDK project structure with Python
  - Define DynamoDB single table schema (KisanSetuData) with PK/SK design
  - Create S3 bucket structure (kisan-setu-raw, kisan-setu-processed, kisan-setu-archive)
  - Set up IAM roles and policies for Lambda, Textract, Transcribe, Polly, SageMaker, Bedrock
  - Configure API Gateway for WhatsApp webhook endpoint
  - Deploy initial CDK stack to AWS
  - _Requirements: 8.1, 9.3_

- [x] 1.1 Write property test for DynamoDB key structure
  - **Property 22: DynamoDB Key Structure Compliance**
  - **Validates: Requirements 8.1**

- [x] 2. Implement core data models and validation
  - Create Python dataclasses for Message, LedgerData, NDVIResult, YieldPrediction, ReliabilityScore, Transaction
  - Implement DynamoDB access patterns (get_farmer, get_transactions, get_credit_score, etc.)
  - Add data validation functions for GPS coordinates, phone numbers, language codes
  - Implement audit trail creation for all data operations
  - _Requirements: 8.1, 8.3, 8.4_

- [x] 2.1 Write property test for referential integrity
  - **Property 23: Referential Integrity Maintenance**
  - **Validates: Requirements 8.3**

- [x] 2.2 Write property test for audit trail creation
  - **Property 24: Audit Trail Creation**
  - **Validates: Requirements 8.4**

- [x] 2.3 Write property test for date range queries
  - **Property 25: Date Range Query Correctness**
  - **Validates: Requirements 8.5**

- [x] 2.4 Write property test for sensitive data encryption
  - **Property 26: Sensitive Data Encryption**
  - **Validates: Requirements 8.6**

- [x] 3. Implement WhatsApp Interface Component
  - Create WhatsAppInterface class with receive_message, send_text_response, send_voice_response, send_document methods
  - Implement webhook handler Lambda function to receive WhatsApp messages
  - Add message type detection (text, voice, image) and routing logic
  - Implement WhatsApp message formatting for structured data (tables, lists)
  - Add error handling for WhatsApp API rate limits and failures
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 3.1 Write property test for message type routing
  - **Property 17: Message Type Routing**
  - **Validates: Requirements 6.1, 6.4**

- [x] 3.2 Write property test for structured data formatting
  - **Property 18: Structured Data Formatting**
  - **Validates: Requirements 6.5**

- [x] 4. Checkpoint - Verify infrastructure and WhatsApp integration
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement Voice Agent Component
  - Create VoiceAgent class with transcribe_audio, synthesize_speech, detect_language methods
  - Integrate Amazon Transcribe for speech-to-text (Hindi, Marathi, Tamil)
  - Integrate Amazon Polly for text-to-speech with language-specific voices
  - Implement language detection and dialect handling
  - Add audio quality validation and error handling
  - Store voice recordings in S3 with proper lifecycle policies
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [x] 5.1 Write property test for language-consistent transcription
  - **Property 1: Language-Consistent Transcription**
  - **Validates: Requirements 1.1, 1.2**

- [x] 5.2 Write property test for text-to-speech language matching
  - **Property 2: Text-to-Speech Language Matching**
  - **Validates: Requirements 1.4**

- [x] 6. Implement Document Processor Component
  - Create DocumentProcessor class with extract_ledger_data, validate_extraction, aggregate_ledgers methods
  - Integrate Amazon Textract Queries for handwritten ledger extraction
  - Define Textract queries for quantity, moisture, price, date, farmer_name, crop_type
  - Implement confidence score validation and low-confidence field flagging
  - Add support for Hindi, Marathi, Tamil scripts
  - Implement ledger aggregation logic for multiple images
  - Store extracted data in DynamoDB and images in S3
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

- [x] 6.1 Write property test for structured ledger extraction (bug found & fixed!)
  - **Property 3: Structured Ledger Extraction**
  - **Validates: Requirements 2.2, 2.4**
  - **Bug Found:** Property test discovered that `_safe_float()` incorrectly handled scientific notation (e.g., '5e-324' parsed as 5324.0 instead of ~0.0)
  - **Fix Applied:** Updated `_safe_float()` to treat extremely small scientific notation values (< 1e-100) as 0.0, which is appropriate for domain values (moisture, quantity, price)

- [x] 6.2 Write property test for multi-script OCR support
  - **Property 4: Multi-Script OCR Support**
  - **Validates: Requirements 2.3**

- [x] 6.3 Write property test for low-confidence field flagging
  - **Property 5: Low-Confidence Field Flagging**
  - **Validates: Requirements 2.5**

- [x] 6.4 Write property test for ledger aggregation completeness
  - **Property 6: Ledger Aggregation Completeness**
  - **Validates: Requirements 2.6**

- [x] 7. Checkpoint - Verify voice and document processing
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Implement Satellite Analyzer Component
  - Create SatelliteAnalyzer class with get_satellite_imagery, calculate_ndvi, predict_yield methods
  - Integrate SageMaker Geospatial for Sentinel-2 satellite imagery retrieval
  - Implement NDVI calculation using band math (B8 - B4) / (B8 + B4)
  - Add crop maturity stage classification (early, mid, late, harvest_ready)
  - Implement yield prediction based on NDVI trends and historical data
  - Handle cloud cover and data unavailability scenarios
  - Implement caching for satellite imagery (24-hour TTL)
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 9.5_

- [x] 8.1 Write property test for GPS-based imagery retrieval
  - **Property 7: GPS-Based Imagery Retrieval**
  - **Validates: Requirements 3.1**

- [x] 8.2 Write property test for NDVI value range validity
  - **Property 8: NDVI Value Range Validity**
  - **Validates: Requirements 3.2**

- [x] 8.3 Write property test for maturity stage classification
  - **Property 9: Maturity Stage Classification**
  - **Validates: Requirements 3.3**

- [x] 8.4 Write property test for yield prediction completeness
  - **Property 10: Yield Prediction Completeness**
  - **Validates: Requirements 3.4, 3.6**

- [x] 8.5 Write property test for satellite data caching
  - **Property 28: Satellite Data Caching**
  - **Validates: Requirements 9.5**

- [x] 9. Implement Credit Engine Component
  - Create CreditEngine class with calculate_reliability_score and component calculation methods
  - Implement calculate_supply_consistency (0-30 points) based on delivery frequency and schedule adherence
  - Implement calculate_quality_metrics (0-25 points) based on moisture, grade consistency, rejection rates
  - Implement calculate_transaction_history (0-20 points) based on volume and relationship length
  - Implement calculate_financial_behavior (0-15 points) based on payment patterns
  - Implement calculate_operational_transparency (0-10 points) based on digitization frequency
  - Add score breakdown generation and significant change detection (>10 points)
  - Store credit scores in DynamoDB with historical tracking
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8_

- [x] 9.1 Write property test for reliability score composition
  - **Property 15: Reliability Score Composition**
  - **Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7**

- [x] 9.2 Write property test for significant score change notification
  - **Property 16: Significant Score Change Notification**
  - **Validates: Requirements 5.8**

- [x] 10. Checkpoint - Verify satellite analysis and credit scoring
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Implement Sync Manager Component for offline-first functionality
  - Create SyncManager class with enable_offline_mode, store_offline_transaction, detect_connectivity, synchronize_data, resolve_conflict methods
  - Implement local storage for offline transactions using device-local database
  - Add connectivity detection and automatic sync trigger
  - Implement chronological sync ordering based on timestamps
  - Add last-write-wins conflict resolution with conflict logging
  - Implement sync status notifications (success_count, failure_count)
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

- [x] 11.1 Write property test for offline transaction persistence
  - **Property 11: Offline Transaction Persistence**
  - **Validates: Requirements 4.2**

- [x] 11.2 Write property test for chronological sync ordering
  - **Property 12: Chronological Sync Ordering**
  - **Validates: Requirements 4.4**

- [x] 11.3 Write property test for last-write-wins conflict resolution
  - **Property 13: Last-Write-Wins Conflict Resolution**
  - **Validates: Requirements 4.5**

- [x] 11.4 Write property test for sync completion notification
  - **Property 14: Sync Completion Notification**
  - **Validates: Requirements 4.6**

- [x] 12. Implement AWS AppSync GraphQL API for offline sync
  - Define GraphQL schema with Farmer, Transaction, CreditScore types
  - Implement mutations for createTransaction and syncOfflineTransactions
  - Implement queries for getFarmer, listTransactions, getCreditScore
  - Configure AppSync resolvers to connect to DynamoDB
  - Add conflict resolution configuration (last-write-wins)
  - Set up AppSync client configuration with offline support
  - _Requirements: 4.1, 4.3, 4.4, 4.5, 4.6_

- [x] 13. Implement Bedrock Orchestration Component
  - Create BedrockOrchestrator class with process_request, decompose_task, invoke_tool, maintain_context methods
  - Configure AWS Bedrock Agent with Claude 3.5 Sonnet v2 model
  - Define agent instruction prompt for FPO operations and multilingual support
  - Create action groups for document processing, satellite analysis, voice processing
  - Implement tool invocation for Textract, SageMaker, Transcribe
  - Add conversation context management in DynamoDB
  - Implement multi-step request decomposition and execution
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 13.1 Write property test for tool invocation correctness
  - **Property 19: Tool Invocation Correctness**
  - **Validates: Requirements 7.2**

- [x] 13.2 Write property test for mathematical calculation accuracy
  - **Property 20: Mathematical Calculation Accuracy**
  - **Validates: Requirements 7.3**

- [x] 13.3 Write property test for conversation context persistence
  - **Property 21: Conversation Context Persistence**
  - **Validates: Requirements 7.4**

- [x] 14. Implement Bedrock Knowledge Base for cost optimization
  - Create OpenSearch Serverless collection for vector storage
  - Configure Bedrock Knowledge Base with Titan Embed Text v2 embeddings
  - Add S3 data source with FPO guidelines and farming best practices documents
  - Implement retrieve_and_generate queries to reduce long-context prompting costs
  - Configure knowledge base integration in Bedrock Agent
  - _Requirements: 9.1_

- [x] 15. Checkpoint - Verify orchestration and knowledge base
  - Ensure all tests pass, ask the user if questions arise.

- [x] 16. Implement error handling and retry logic
  - Create ErrorResponse dataclass with error_code, user_message, technical_details, suggested_action
  - Implement exponential backoff retry logic for external service calls (1s, 2s, 4s delays)
  - Add localized error messages for Hindi, Marathi, Tamil
  - Implement batch processing resilience (continue on individual failures)
  - Add critical error alerting to administrators via SNS
  - Implement circuit breaker pattern for external services
  - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

- [x] 16.1 Write property test for exponential backoff retry logic
  - **Property 29: Exponential Backoff Retry Logic**
  - **Validates: Requirements 10.1**

- [x] 16.2 Write property test for localized error messages
  - **Property 30: Localized Error Messages**
  - **Validates: Requirements 10.2**

- [x] 16.3 Write property test for batch processing resilience
  - **Property 31: Batch Processing Resilience**
  - **Validates: Requirements 10.3**

- [x] 16.4 Write property test for critical error alerting
  - **Property 32: Critical Error Alerting**
  - **Validates: Requirements 10.5**

- [x] 17. Implement cost optimization features
  - Add request batching for Textract calls (batch size: 10)
  - Implement Redis/ElastiCache caching layer for satellite imagery (24-hour TTL)
  - Configure DynamoDB on-demand billing mode
  - Add S3 lifecycle policies (Glacier after 90 days for ledgers, delete voice after 30 days)
  - Implement batch processing with ThreadPoolExecutor for concurrent operations
  - _Requirements: 9.2, 9.3, 9.4, 9.5_

- [x] 17.1 Write property test for request batching efficiency
  - **Property 27: Request Batching Efficiency**
  - **Validates: Requirements 9.4**

- [x] 18. Wire all components together in main Lambda handler
  - Create main message router Lambda that orchestrates all components
  - Implement routing logic: images → DocumentProcessor, voice → VoiceAgent, text → BedrockOrchestrator
  - Add component initialization and dependency injection
  - Implement end-to-end flow: WhatsApp → Router → Component → Response → WhatsApp
  - Add comprehensive logging with CloudWatch Logs
  - Configure Lambda environment variables for all service endpoints
  - _Requirements: 6.1, 6.2, 7.1_

- [x] 19. Create test data generators for property-based testing
  - Implement Hypothesis strategies for farmer_data, transaction_data, ndvi_result
  - Create generators for valid GPS coordinates, phone numbers, language codes
  - Add generators for ledger images, voice recordings, satellite imagery
  - Configure Hypothesis settings (min_examples=100)
  - Create mock services for WhatsApp, Textract, Transcribe, Polly, SageMaker
  - _Requirements: All (testing infrastructure)_

- [x] 20. Set up testing infrastructure and CI/CD
  - Configure pytest with fixtures for DynamoDB Local and LocalStack
  - Set up mock AWS services (Textract, Transcribe, Polly, SageMaker, Bedrock)
  - Create sample test data (Hindi/Marathi/Tamil ledgers, voice recordings, satellite images)
  - Configure GitHub Actions workflow for automated testing
  - Add code coverage reporting (target: 80% for unit tests)
  - Set up integration test environment with real AWS services
  - _Requirements: All (testing infrastructure)_

- [x] 21. Final checkpoint - End-to-end integration testing
  - Test complete flow: WhatsApp message → processing → DynamoDB storage → response
  - Verify all 32 correctness properties pass with 100+ iterations each
  - Test multilingual support (Hindi, Marathi, Tamil) for voice and text
  - Verify offline sync functionality with AppSync
  - Test error handling and retry logic with simulated failures
  - Validate cost optimization features (caching, batching, lifecycle policies)
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional property-based tests and can be skipped for faster MVP
- Each task references specific requirements for traceability
- The implementation uses Python throughout, matching the design document
- AWS services are configured for ap-south-1 (Mumbai) region for optimal latency
- All components follow serverless architecture with Lambda, DynamoDB, S3, and managed AI services
- Property tests use Hypothesis framework with minimum 100 iterations per property
- Checkpoints ensure incremental validation and provide opportunities for user feedback
- Cost target: <$50/month per FPO cluster serving 500+ farmers

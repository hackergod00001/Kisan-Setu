# Kisan-Setu Testing Guide

## Overview

This guide explains how to use the test data generators and mock services for property-based testing in the Kisan-Setu project.

## Test Infrastructure

### 1. Test Data Generators (`generators.py`)

The `generators.py` module provides Hypothesis strategies for generating valid test data for all domain models.

#### Basic Generators

```python
from generators import (
    gps_coordinates,
    indian_phone_number,
    language_code,
    crop_type,
    quality_grade,
    s3_url,
    uuid_string
)

# Generate GPS coordinates
coords = gps_coordinates().example()  # (lat, lon) tuple

# Generate phone number
phone = indian_phone_number().example()  # '+91XXXXXXXXXX'

# Generate language code
lang = language_code().example()  # 'hi-IN', 'mr-IN', or 'ta-IN'
```

#### Domain Model Generators

```python
from generators import (
    farmer_data,
    fpo_data,
    transaction_data,
    ndvi_result,
    yield_prediction,
    reliability_score,
    ledger_data,
    message_data,
    audit_trail
)

# Generate a farmer
farmer = farmer_data().example()

# Generate a transaction
transaction = transaction_data().example()

# Generate NDVI result
ndvi = ndvi_result().example()
```

#### Specialized Generators

```python
from generators import (
    farmer_with_transactions,
    ndvi_time_series,
    ledger_batch,
    conflicting_transactions
)

# Generate farmer with transactions
farmer, transactions = farmer_with_transactions(
    min_transactions=5,
    max_transactions=20
).example()

# Generate NDVI time series
readings = ndvi_time_series(
    min_readings=5,
    max_readings=15
).example()

# Generate batch of ledgers from same farmer
ledgers = ledger_batch(
    min_ledgers=3,
    max_ledgers=10
).example()

# Generate conflicting transactions
txn1, txn2 = conflicting_transactions().example()
```

### 2. Mock Services (`mock_services.py`)

The `mock_services.py` module provides mock implementations of AWS services for testing without actual API calls.

#### Available Mock Services

- **MockWhatsAppService**: WhatsApp Business API
- **MockTextractService**: Amazon Textract (OCR)
- **MockTranscribeService**: Amazon Transcribe (Speech-to-Text)
- **MockPollyService**: Amazon Polly (Text-to-Speech)
- **MockSageMakerGeospatialService**: SageMaker Geospatial (Satellite Analysis)
- **MockBedrockService**: AWS Bedrock (AI Orchestration)

#### Using Mock Services

```python
from mock_services import MockServiceFactory

# Create mock service factory
mock_services = MockServiceFactory()

# Use WhatsApp mock
result = mock_services.whatsapp.send_message(
    phone_number='+919876543210',
    message='Hello',
    message_type='text'
)

# Use Textract mock
extraction = mock_services.textract.analyze_document(
    image_url='s3://bucket/image.jpg',
    queries=['What is the quantity?', 'What is the price?'],
    language='hi-IN'
)

# Use Transcribe mock
transcription = mock_services.transcribe.transcribe_audio(
    audio_url='s3://bucket/audio.mp3',
    language_code='hi-IN'
)

# Use Polly mock
audio = mock_services.polly.synthesize_speech(
    text='नमस्ते',
    language_code='hi-IN'
)

# Use SageMaker mock
imagery = mock_services.sagemaker.get_satellite_imagery(
    gps_coords=(28.6139, 77.2090),
    start_date='2024-01-01',
    end_date='2024-01-31'
)

ndvi_calc = mock_services.sagemaker.calculate_ndvi(
    image_url=imagery['image_url']
)

# Clear all mock service histories
mock_services.clear_all()
```

### 3. Pytest Fixtures (`conftest.py`)

The `conftest.py` module provides shared fixtures for all tests.

#### Available Fixtures

```python
def test_example(mock_services, sample_farmer, sample_transaction):
    """
    Available fixtures:
    - mock_services: MockServiceFactory instance
    - sample_farmer: Predefined Farmer instance
    - sample_fpo: Predefined FPO instance
    - sample_transaction: Predefined Transaction instance
    - sample_ledger: Predefined LedgerData instance
    - sample_ndvi: Predefined NDVIResult instance
    - sample_yield_prediction: Predefined YieldPrediction instance
    - sample_reliability_score: Predefined ReliabilityScore instance
    - sample_message: Predefined Message instance
    """
    pass
```

## Writing Property-Based Tests

### Basic Property Test

```python
from hypothesis import given, settings
from generators import farmer_data

@given(farmer_data())
@settings(max_examples=100)
def test_farmer_phone_validity(farmer):
    """Test that all generated farmers have valid phone numbers."""
    assert farmer.phone.startswith('+91')
    assert len(farmer.phone) == 13
```

### Property Test with Multiple Generators

```python
from hypothesis import given, settings
from generators import farmer_data, transaction_data

@given(farmer_data(), transaction_data())
@settings(max_examples=100)
def test_transaction_references_farmer(farmer, transaction):
    """Test transaction referential integrity."""
    # Override transaction to reference farmer
    transaction.farmer_id = farmer.farmer_id
    transaction.fpo_id = farmer.fpo_id
    
    assert transaction.farmer_id == farmer.farmer_id
    assert transaction.fpo_id == farmer.fpo_id
```

### Property Test with Mock Services

```python
from hypothesis import given, settings
from generators import ledger_data

@given(ledger_data())
@settings(max_examples=100)
def test_textract_extraction(ledger, mock_services):
    """Test document extraction with mock Textract."""
    result = mock_services.textract.analyze_document(
        image_url=ledger.image_url,
        queries=['What is the quantity?'],
        language='hi-IN'
    )
    
    assert 'extracted_data' in result
    assert 'confidence_scores' in result
```

### Property Test Template

Use this template for implementing the 32 correctness properties:

```python
from hypothesis import given, settings
from generators import <appropriate_generator>

@given(<appropriate_generator>())
@settings(max_examples=100)
def test_property_X_<property_name>(data):
    """
    Property X: <Property Name>
    
    <Property description from design document>
    
    **Validates: Requirements X.Y**
    """
    # Test implementation
    assert <property_condition>
```

## Running Tests

### Run All Tests

```bash
pytest tests/
```

### Run Property Tests Only

```bash
pytest tests/ -m property
```

### Run with Specific Hypothesis Profile

```bash
# Development (20 examples)
HYPOTHESIS_PROFILE=dev pytest tests/

# CI (100 examples)
HYPOTHESIS_PROFILE=ci pytest tests/

# Debug (10 examples, verbose)
HYPOTHESIS_PROFILE=debug pytest tests/
```

### Run Specific Test File

```bash
pytest tests/test_property_examples.py -v
```

### Run with Coverage

```bash
pytest tests/ --cov=lambda --cov-report=html
```

## Hypothesis Configuration

### Global Settings

The default configuration is set in `generators.py`:

```python
settings.register_profile("kisan_setu", max_examples=100, deadline=None)
settings.load_profile("kisan_setu")
```

### Per-Test Settings

Override settings for specific tests:

```python
@given(farmer_data())
@settings(max_examples=200, deadline=5000)  # Custom settings
def test_with_custom_settings(farmer):
    pass
```

### Available Profiles

- **ci**: 100 examples, verbose output (for CI/CD)
- **dev**: 20 examples (for local development)
- **debug**: 10 examples, verbose output (for debugging)

## Best Practices

### 1. Use Appropriate Generators

Choose the right generator for your test:

```python
# Good: Use specialized generator
@given(farmer_with_transactions(min_transactions=5))
def test_credit_scoring(farmer_and_txns):
    farmer, transactions = farmer_and_txns
    # Test with guaranteed transaction history

# Bad: Generate separately and hope they match
@given(farmer_data(), st.lists(transaction_data()))
def test_credit_scoring(farmer, transactions):
    # Transactions won't reference farmer
```

### 2. Use Fixtures for Common Setup

```python
# Good: Use fixture
def test_with_mock_services(mock_services):
    result = mock_services.whatsapp.send_message(...)

# Bad: Create mock services in each test
def test_without_fixture():
    mock_services = MockServiceFactory()
    result = mock_services.whatsapp.send_message(...)
```

### 3. Clear Mock Service History

```python
# Good: Use fixture that auto-clears
def test_example(mock_services):
    # Fixture clears history after test
    pass

# Or manually clear
def test_manual_clear():
    mock_services = MockServiceFactory()
    # ... test code ...
    mock_services.clear_all()
```

### 4. Test Properties, Not Examples

```python
# Good: Test universal property
@given(ndvi_result())
def test_ndvi_range(ndvi):
    assert -1.0 <= ndvi.ndvi_value <= 1.0

# Bad: Test specific example
def test_ndvi_specific():
    ndvi = NDVIResult(...specific values...)
    assert ndvi.ndvi_value == 0.75
```

### 5. Use Assumptions When Needed

```python
from hypothesis import given, assume

@given(transaction_data())
def test_high_quality_only(transaction):
    # Only test high-quality transactions
    assume(transaction.quality_grade == 'A')
    
    # Test logic for grade A transactions
    assert transaction.quality_grade == 'A'
```

## Implementing the 32 Correctness Properties

The design document defines 32 correctness properties. Here's how to implement them:

### Example: Property 8 - NDVI Value Range Validity

```python
@given(ndvi_result())
@settings(max_examples=100)
def test_property_8_ndvi_range_validity(ndvi):
    """
    Property 8: NDVI Value Range Validity
    
    For any satellite image with vegetation bands, the calculated NDVI
    value should be within the valid range of -1.0 to 1.0.
    
    **Validates: Requirements 3.2**
    """
    assert -1.0 <= ndvi.ndvi_value <= 1.0
    assert 0.0 <= ndvi.confidence <= 1.0
```

### Example: Property 15 - Reliability Score Composition

```python
@given(reliability_score())
@settings(max_examples=100)
def test_property_15_reliability_score_composition(score):
    """
    Property 15: Reliability Score Composition
    
    For any farmer with transaction history, the calculated reliability
    score should be between 0 and 100 and equal the sum of all components.
    
    **Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7**
    """
    # Score bounds
    assert 0 <= score.total_score <= 100
    
    # Component bounds
    assert 0 <= score.supply_consistency <= 30
    assert 0 <= score.quality_metrics <= 25
    assert 0 <= score.transaction_history <= 20
    assert 0 <= score.financial_behavior <= 15
    assert 0 <= score.operational_transparency <= 10
    
    # Composition property
    expected_total = (
        score.supply_consistency +
        score.quality_metrics +
        score.transaction_history +
        score.financial_behavior +
        score.operational_transparency
    )
    assert abs(score.total_score - expected_total) < 0.01
```

## Troubleshooting

### Hypothesis Finds a Failing Example

When Hypothesis finds a failing example, it will:
1. Print the failing example
2. Save it to `.hypothesis/examples/`
3. Replay it on subsequent runs

```python
# Hypothesis output:
# Falsifying example: test_example(
#     farmer=Farmer(farmer_id='abc123', ...)
# )
```

To debug:
1. Copy the failing example
2. Create a unit test with that specific data
3. Fix the issue
4. Re-run property test to verify

### Tests Are Too Slow

Reduce the number of examples:

```bash
HYPOTHESIS_PROFILE=dev pytest tests/  # 20 examples
```

Or use `@settings`:

```python
@given(farmer_data())
@settings(max_examples=10)  # Fewer examples
def test_fast(farmer):
    pass
```

### Mock Services Not Working

Ensure you're using the fixture:

```python
# Correct
def test_with_mocks(mock_services):
    result = mock_services.whatsapp.send_message(...)

# Incorrect
def test_without_fixture():
    # mock_services not available
    result = mock_services.whatsapp.send_message(...)  # NameError
```

## Additional Resources

- [Hypothesis Documentation](https://hypothesis.readthedocs.io/)
- [Property-Based Testing Guide](https://hypothesis.works/articles/what-is-property-based-testing/)
- [Pytest Documentation](https://docs.pytest.org/)

## Summary

The test infrastructure provides:

1. **Generators** (`generators.py`): Hypothesis strategies for all domain models
2. **Mock Services** (`mock_services.py`): Mock AWS services for testing
3. **Fixtures** (`conftest.py`): Shared test fixtures and configuration
4. **Examples** (`test_property_examples.py`): Example property-based tests

Use these tools to implement the 32 correctness properties defined in the design document with minimum 100 iterations per property test.

"""
Pytest configuration and fixtures for Kisan-Setu tests.

This module provides shared fixtures and configuration for all tests,
including Hypothesis settings and mock service setup.
"""

import sys
import os

# Add lambda directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))

# Mock meta_whatsapp_interface before any lambda module imports it at module level.
# In Lambda runtime, each function has its own local copy, but in tests we mock it
# to avoid AWS credentials / network calls.
from unittest.mock import MagicMock
_mock_whatsapp = MagicMock()
sys.modules.setdefault('meta_whatsapp_interface', _mock_whatsapp)

import pytest
from hypothesis import settings, Verbosity

# Configure Hypothesis profiles
settings.register_profile("ci", max_examples=100, deadline=None, verbosity=Verbosity.verbose)
settings.register_profile("dev", max_examples=20, deadline=None)
settings.register_profile("debug", max_examples=10, deadline=None, verbosity=Verbosity.verbose)

# Load profile based on environment
profile = os.getenv("HYPOTHESIS_PROFILE", "dev")
settings.load_profile(profile)


@pytest.fixture
def mock_services():
    """
    Fixture providing mock AWS services for testing.
    
    Returns: MockServiceFactory instance with all mock services
    """
    from mock_services import MockServiceFactory
    
    factory = MockServiceFactory()
    yield factory
    factory.clear_all()


@pytest.fixture
def sample_farmer():
    """
    Fixture providing a sample farmer for testing.
    
    Returns: Farmer instance with predefined data
    """
    from common.models import Farmer
    from datetime import date
    
    return Farmer(
        farmer_id="test_farmer_123",
        name="Ram Kumar",
        phone="+919876543210",
        fpo_id="test_fpo_456",
        gps_coords=(28.6139, 77.2090),  # Delhi coordinates
        preferred_language="hi-IN",
        join_date=date(2023, 1, 1)
    )


@pytest.fixture
def sample_fpo():
    """
    Fixture providing a sample FPO for testing.
    
    Returns: FPO instance with predefined data
    """
    from common.models import FPO
    from datetime import date
    
    return FPO(
        fpo_id="test_fpo_456",
        name="Delhi Farmers Collective",
        location="Delhi",
        manager_contact="+919876543210",
        created_date=date(2020, 1, 1),
        member_count=150
    )


@pytest.fixture
def sample_transaction():
    """
    Fixture providing a sample transaction for testing.
    
    Returns: Transaction instance with predefined data
    """
    from common.models import Transaction, SyncStatus
    from datetime import datetime
    
    return Transaction(
        transaction_id="test_txn_789",
        farmer_id="test_farmer_123",
        fpo_id="test_fpo_456",
        quantity=100.0,
        crop_type="onion",
        quality_grade="A",
        moisture=12.5,
        price=5000.0,
        timestamp=datetime(2024, 1, 15, 10, 30, 0),
        ledger_image_url="s3://kisan-setu-raw/test_ledger.jpg",
        sync_status=SyncStatus.SYNCED
    )


@pytest.fixture
def sample_ledger():
    """
    Fixture providing a sample ledger for testing.
    
    Returns: LedgerData instance with predefined data
    """
    from common.models import LedgerData
    from datetime import date
    
    return LedgerData(
        ledger_id="test_ledger_101",
        farmer_id="test_farmer_123",
        quantity=100.0,
        moisture=12.5,
        price=5000.0,
        date=date(2024, 1, 15),
        crop_type="onion",
        confidence_scores={
            'quantity': 0.95,
            'moisture': 0.88,
            'price': 0.92,
            'date': 0.65,  # Low confidence
            'farmer_name': 0.90,
            'crop_type': 0.87
        },
        image_url="s3://kisan-setu-raw/test_ledger.jpg",
        fields_needing_review=['date']  # Low confidence field
    )


@pytest.fixture
def sample_ndvi():
    """
    Fixture providing a sample NDVI result for testing.
    
    Returns: NDVIResult instance with predefined data
    """
    from common.models import NDVIResult
    from datetime import datetime
    
    return NDVIResult(
        field_id="test_field_202",
        gps_coords=(28.6139, 77.2090),
        ndvi_value=0.75,
        timestamp=datetime(2024, 1, 15, 12, 0, 0),
        confidence=0.92,
        satellite_image_url="s3://kisan-setu-satellite/test_image.tif"
    )


@pytest.fixture
def sample_yield_prediction():
    """
    Fixture providing a sample yield prediction for testing.
    
    Returns: YieldPrediction instance with predefined data
    """
    from common.models import YieldPrediction, MaturityStage
    from datetime import datetime
    
    return YieldPrediction(
        field_id="test_field_202",
        estimated_volume=500.0,
        confidence_interval=(450.0, 550.0),
        maturity_stage=MaturityStage.MID,
        prediction_date=datetime(2024, 1, 15, 12, 0, 0)
    )


@pytest.fixture
def sample_reliability_score():
    """
    Fixture providing a sample reliability score for testing.
    
    Returns: ReliabilityScore instance with predefined data
    """
    from common.models import ReliabilityScore
    from datetime import datetime
    
    return ReliabilityScore(
        farmer_id="test_farmer_123",
        total_score=75.0,
        supply_consistency=25.0,
        quality_metrics=20.0,
        transaction_history=15.0,
        financial_behavior=10.0,
        operational_transparency=5.0,
        calculation_date=datetime(2024, 1, 15, 12, 0, 0),
        score_change=5.0
    )


@pytest.fixture
def sample_message():
    """
    Fixture providing a sample message for testing.
    
    Returns: Message instance with predefined data
    """
    from common.models import Message, MessageType
    from datetime import datetime
    
    return Message(
        message_id="test_msg_303",
        sender_id="test_farmer_123",
        message_type=MessageType.TEXT,
        content="मेरे खेत की स्थिति कैसी है?",
        timestamp=datetime(2024, 1, 15, 10, 0, 0),
        language="hi-IN"
    )


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "property: mark test as a property-based test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "mock: mark test as using mock services"
    )

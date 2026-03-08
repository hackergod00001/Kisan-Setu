"""
Test data generators for property-based testing with Hypothesis.

This module provides Hypothesis strategies for generating valid test data
for all Kisan-Setu domain models, including farmers, transactions, NDVI results,
and more. All generators produce data that conforms to validation rules.

Configuration: min_examples=100 for all property tests
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))

from hypothesis import strategies as st
from hypothesis import settings
from datetime import datetime, date, timedelta
from common.models import (
    Message, MessageType, LedgerData, NDVIResult, YieldPrediction,
    ReliabilityScore, Transaction, Farmer, FPO, AuditTrail,
    SyncStatus, MaturityStage
)

# Configure Hypothesis settings globally
settings.register_profile("kisan_setu", max_examples=100, deadline=None)
settings.load_profile("kisan_setu")


# ============================================================================
# Basic Data Type Generators
# ============================================================================

@st.composite
def gps_coordinates(draw):
    """
    Generate valid GPS coordinates.
    
    Returns: Tuple[float, float] with (latitude, longitude)
    - Latitude: -90 to 90
    - Longitude: -180 to 180
    """
    latitude = draw(st.floats(min_value=-90.0, max_value=90.0, allow_nan=False, allow_infinity=False))
    longitude = draw(st.floats(min_value=-180.0, max_value=180.0, allow_nan=False, allow_infinity=False))
    return (latitude, longitude)


@st.composite
def indian_phone_number(draw):
    """
    Generate valid Indian phone numbers.
    
    Returns: String in format '+91XXXXXXXXXX' where X is 6-9 followed by 9 digits
    """
    first_digit = draw(st.sampled_from(['6', '7', '8', '9']))
    remaining_digits = draw(st.text(alphabet='0123456789', min_size=9, max_size=9))
    return f"+91{first_digit}{remaining_digits}"


@st.composite
def language_code(draw):
    """
    Generate valid language codes for supported languages.
    
    Returns: String in format 'xx-IN' for Hindi, Marathi, or Tamil
    """
    return draw(st.sampled_from(['hi-IN', 'mr-IN', 'ta-IN']))


@st.composite
def crop_type(draw):
    """
    Generate valid crop types.
    
    Returns: String representing a supported crop type
    """
    return draw(st.sampled_from(['onion', 'wheat', 'rice', 'cotton']))


@st.composite
def quality_grade(draw):
    """
    Generate valid quality grades.
    
    Returns: String 'A', 'B', or 'C'
    """
    return draw(st.sampled_from(['A', 'B', 'C']))


@st.composite
def s3_url(draw, prefix='s3://kisan-setu-raw'):
    """
    Generate valid S3 URLs.
    
    Args:
        prefix: S3 bucket prefix
    
    Returns: String representing an S3 URL
    """
    filename = draw(st.text(alphabet='abcdefghijklmnopqrstuvwxyz0123456789-', min_size=10, max_size=30))
    extension = draw(st.sampled_from(['.jpg', '.png', '.tif', '.mp3', '.wav']))
    return f"{prefix}/{filename}{extension}"


@st.composite
def uuid_string(draw):
    """
    Generate UUID-like strings for IDs.
    
    Returns: String representing a UUID
    """
    return draw(st.uuids()).hex


# ============================================================================
# Domain Model Generators
# ============================================================================

@st.composite
def farmer_data(draw):
    """
    Generate valid Farmer data.
    
    Returns: Farmer instance with all required fields
    """
    return Farmer(
        farmer_id=draw(uuid_string()),
        name=draw(st.text(alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ ', min_size=3, max_size=50)),
        phone=draw(indian_phone_number()),
        fpo_id=draw(uuid_string()),
        gps_coords=draw(gps_coordinates()),
        preferred_language=draw(language_code()),
        join_date=draw(st.dates(min_value=date(2020, 1, 1), max_value=date.today()))
    )


@st.composite
def fpo_data(draw):
    """
    Generate valid FPO data.
    
    Returns: FPO instance with all required fields
    """
    return FPO(
        fpo_id=draw(uuid_string()),
        name=draw(st.text(alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ ', min_size=5, max_size=100)),
        location=draw(st.text(alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ ', min_size=3, max_size=50)),
        manager_contact=draw(indian_phone_number()),
        created_date=draw(st.dates(min_value=date(2015, 1, 1), max_value=date.today())),
        member_count=draw(st.integers(min_value=10, max_value=1000))
    )


@st.composite
def transaction_data(draw):
    """
    Generate valid Transaction data.
    
    Returns: Transaction instance with all required fields
    """
    return Transaction(
        transaction_id=draw(uuid_string()),
        farmer_id=draw(uuid_string()),
        fpo_id=draw(uuid_string()),
        quantity=draw(st.floats(min_value=0.1, max_value=10000.0, allow_nan=False, allow_infinity=False)),
        crop_type=draw(crop_type()),
        quality_grade=draw(quality_grade()),
        moisture=draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)),
        price=draw(st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False)),
        timestamp=draw(st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime.now())),
        ledger_image_url=draw(st.one_of(st.none(), s3_url())),
        sync_status=draw(st.sampled_from(list(SyncStatus)))
    )


@st.composite
def ndvi_result(draw):
    """
    Generate valid NDVIResult data.
    
    Returns: NDVIResult instance with all required fields
    """
    return NDVIResult(
        field_id=draw(uuid_string()),
        gps_coords=draw(gps_coordinates()),
        ndvi_value=draw(st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False)),
        timestamp=draw(st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime.now())),
        confidence=draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)),
        satellite_image_url=draw(s3_url(prefix='s3://kisan-setu-satellite'))
    )


@st.composite
def yield_prediction(draw):
    """
    Generate valid YieldPrediction data.
    
    Returns: YieldPrediction instance with all required fields
    """
    estimated = draw(st.floats(min_value=10.0, max_value=10000.0, allow_nan=False, allow_infinity=False))
    # Confidence interval: lower_bound <= estimate <= upper_bound
    # Margin is 5% to 30% of estimated value
    margin_percent = draw(st.floats(min_value=0.05, max_value=0.3, allow_nan=False, allow_infinity=False))
    margin = estimated * margin_percent
    lower_bound = max(0.0, estimated - margin)
    upper_bound = estimated + margin
    
    return YieldPrediction(
        field_id=draw(uuid_string()),
        estimated_volume=estimated,
        confidence_interval=(lower_bound, upper_bound),
        maturity_stage=draw(st.sampled_from(list(MaturityStage))),
        prediction_date=draw(st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime.now()))
    )


@st.composite
def reliability_score(draw):
    """
    Generate valid ReliabilityScore data.
    
    Returns: ReliabilityScore instance with all required fields
    Note: Components are generated to sum to total_score
    """
    supply_consistency = draw(st.floats(min_value=0.0, max_value=30.0, allow_nan=False, allow_infinity=False))
    quality_metrics = draw(st.floats(min_value=0.0, max_value=25.0, allow_nan=False, allow_infinity=False))
    transaction_history = draw(st.floats(min_value=0.0, max_value=20.0, allow_nan=False, allow_infinity=False))
    financial_behavior = draw(st.floats(min_value=0.0, max_value=15.0, allow_nan=False, allow_infinity=False))
    operational_transparency = draw(st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False))
    
    total = supply_consistency + quality_metrics + transaction_history + financial_behavior + operational_transparency
    
    return ReliabilityScore(
        farmer_id=draw(uuid_string()),
        total_score=total,
        supply_consistency=supply_consistency,
        quality_metrics=quality_metrics,
        transaction_history=transaction_history,
        financial_behavior=financial_behavior,
        operational_transparency=operational_transparency,
        calculation_date=draw(st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime.now())),
        score_change=draw(st.floats(min_value=-50.0, max_value=50.0, allow_nan=False, allow_infinity=False))
    )


@st.composite
def ledger_data(draw):
    """
    Generate valid LedgerData.
    
    Returns: LedgerData instance with all required fields
    Note: Uses processor.LedgerData which includes farmer_name and quality_grade
    """
    # Import processor LedgerData which has all fields
    import importlib.util
    _proc_path = os.path.join(os.path.dirname(__file__), '..', 'lambda', 'processor', 'processor.py')
    _spec = importlib.util.spec_from_file_location('_processor_module', _proc_path)
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    ProcessorLedgerData = _mod.LedgerData
    
    fields = ['quantity', 'moisture', 'price', 'date', 'farmer_name', 'crop_type', 'quality_grade']
    confidence_scores = {
        field.upper(): draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False))
        for field in fields
    }
    
    # Fields with confidence < 70 need review
    fields_needing_review = [field for field, conf in confidence_scores.items() if conf < 70.0]
    
    return ProcessorLedgerData(
        ledger_id=draw(uuid_string()),
        farmer_id=draw(uuid_string()),
        quantity=draw(st.floats(min_value=0.1, max_value=10000.0, allow_nan=False, allow_infinity=False)),
        moisture=draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)),
        price=draw(st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False)),
        date=draw(st.dates(min_value=date(2020, 1, 1), max_value=date.today())).isoformat(),
        crop_type=draw(crop_type()),
        farmer_name=draw(st.text(alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ ', min_size=3, max_size=50)),
        quality_grade=draw(quality_grade()),
        confidence_scores=confidence_scores,
        image_url=draw(s3_url()),
        fields_needing_review=fields_needing_review
    )


@st.composite
def message_data(draw):
    """
    Generate valid Message data.
    
    Returns: Message instance with all required fields
    """
    msg_type = draw(st.sampled_from(list(MessageType)))
    
    # Content depends on message type
    if msg_type == MessageType.TEXT:
        content = draw(st.text(min_size=1, max_size=500))
    else:  # VOICE or IMAGE
        content = draw(s3_url())
    
    return Message(
        message_id=draw(uuid_string()),
        sender_id=draw(uuid_string()),
        message_type=msg_type,
        content=content,
        timestamp=draw(st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime.now())),
        language=draw(language_code())
    )


@st.composite
def audit_trail(draw):
    """
    Generate valid AuditTrail data.
    
    Returns: AuditTrail instance with all required fields
    """
    operation = draw(st.sampled_from(['create', 'update', 'delete']))
    entity_type = draw(st.sampled_from(['Farmer', 'Transaction', 'FPO', 'LedgerData']))
    
    changed_fields = {
        'field1': draw(st.text(min_size=1, max_size=50)),
        'field2': draw(st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False))
    }
    
    # Only update operations have previous values
    previous_values = None
    if operation == 'update':
        previous_values = {
            'field1': draw(st.text(min_size=1, max_size=50)),
            'field2': draw(st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False))
        }
    
    return AuditTrail(
        audit_id=draw(uuid_string()),
        entity_type=entity_type,
        entity_id=draw(uuid_string()),
        operation=operation,
        timestamp=draw(st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime.now())),
        user_id=draw(uuid_string()),
        changed_fields=changed_fields,
        previous_values=previous_values
    )


# ============================================================================
# Specialized Generators for Edge Cases
# ============================================================================

@st.composite
def farmer_with_transactions(draw, min_transactions=1, max_transactions=50):
    """
    Generate a farmer with associated transactions.
    
    Args:
        min_transactions: Minimum number of transactions
        max_transactions: Maximum number of transactions
    
    Returns: Tuple of (Farmer, List[Transaction])
    """
    farmer = draw(farmer_data())
    num_transactions = draw(st.integers(min_value=min_transactions, max_value=max_transactions))
    
    transactions = []
    for _ in range(num_transactions):
        txn = draw(transaction_data())
        # Override farmer_id and fpo_id to match
        txn.farmer_id = farmer.farmer_id
        txn.fpo_id = farmer.fpo_id
        transactions.append(txn)
    
    return (farmer, transactions)


@st.composite
def ndvi_time_series(draw, min_readings=3, max_readings=20):
    """
    Generate a time series of NDVI readings for the same field.
    
    Args:
        min_readings: Minimum number of readings
        max_readings: Maximum number of readings
    
    Returns: List[NDVIResult] with same field_id and gps_coords
    """
    field_id = draw(uuid_string())
    coords = draw(gps_coordinates())
    num_readings = draw(st.integers(min_value=min_readings, max_value=max_readings))
    
    base_date = datetime(2023, 1, 1)
    readings = []
    
    for i in range(num_readings):
        reading = draw(ndvi_result())
        # Override to maintain consistency
        reading.field_id = field_id
        reading.gps_coords = coords
        reading.timestamp = base_date + timedelta(days=i * 7)  # Weekly readings
        readings.append(reading)
    
    return readings


@st.composite
def ledger_batch(draw, min_ledgers=1, max_ledgers=10):
    """
    Generate a batch of ledgers from the same farmer.
    
    Args:
        min_ledgers: Minimum number of ledgers
        max_ledgers: Maximum number of ledgers
    
    Returns: List[LedgerData] with same farmer_id (using processor.LedgerData)
    """
    # Import processor LedgerData which has all fields
    import importlib.util
    _proc_path = os.path.join(os.path.dirname(__file__), '..', 'lambda', 'processor', 'processor.py')
    _spec = importlib.util.spec_from_file_location('_processor_module', _proc_path)
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    ProcessorLedgerData = _mod.LedgerData
    
    farmer_id = draw(uuid_string())
    num_ledgers = draw(st.integers(min_value=min_ledgers, max_value=max_ledgers))
    
    ledgers = []
    for _ in range(num_ledgers):
        # Generate confidence scores
        fields = ['quantity', 'moisture', 'price', 'date', 'farmer_name', 'crop_type', 'quality_grade']
        confidence_scores = {
            field.upper(): draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False))
            for field in fields
        }
        
        # Fields with confidence < 70 need review
        fields_needing_review = [field for field, conf in confidence_scores.items() if conf < 70.0]
        
        ledger = ProcessorLedgerData(
            ledger_id=draw(uuid_string()),
            farmer_id=farmer_id,  # Same farmer for all ledgers
            quantity=draw(st.floats(min_value=0.1, max_value=10000.0, allow_nan=False, allow_infinity=False)),
            moisture=draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)),
            price=draw(st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False)),
            date=draw(st.dates(min_value=date(2020, 1, 1), max_value=date.today())).isoformat(),
            crop_type=draw(crop_type()),
            farmer_name=draw(st.text(alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ ', min_size=3, max_size=50)),
            quality_grade=draw(quality_grade()),
            confidence_scores=confidence_scores,
            image_url=draw(s3_url()),
            fields_needing_review=fields_needing_review
        )
        ledgers.append(ledger)
    
    return ledgers


@st.composite
def conflicting_transactions(draw):
    """
    Generate a pair of conflicting transactions (same ID, different data).
    
    Returns: Tuple of (Transaction, Transaction) representing a conflict
    """
    txn1 = draw(transaction_data())
    txn2 = draw(transaction_data())
    
    # Same transaction_id but different timestamps and data
    txn2.transaction_id = txn1.transaction_id
    txn2.farmer_id = txn1.farmer_id
    txn2.fpo_id = txn1.fpo_id
    
    # Ensure txn2 has a later timestamp
    if txn2.timestamp <= txn1.timestamp:
        txn2.timestamp = txn1.timestamp + timedelta(seconds=1)
    
    return (txn1, txn2)

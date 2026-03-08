"""
Property-Based Tests for Yield Prediction Completeness

Tests Property 10: Yield Prediction Completeness
For any yield prediction, the result should include an estimated volume, confidence
interval where lower_bound <= estimate <= upper_bound, and a maturity stage, and
be based on at least one NDVI reading.

**Validates: Requirements 3.4, 3.6**

Uses Hypothesis framework with minimum 100 iterations.
"""

import pytest
import sys
import os
from hypothesis import given, settings, strategies as st, assume
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from typing import List

# Add lambda directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda', 'satellite'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))

from satellite_analyzer import SatelliteAnalyzer, NDVIResult, YieldPrediction
from common.models import MaturityStage

# Import test data generators
from generators import ndvi_result, uuid_string, gps_coordinates, crop_type


# ============================================================================
# Generators for NDVI Time Series
# ============================================================================

@st.composite
def ndvi_time_series_for_yield(draw, min_readings=1, max_readings=20):
    """
    Generate a time series of NDVI readings for yield prediction.
    
    Args:
        min_readings: Minimum number of readings (at least 1)
        max_readings: Maximum number of readings
    
    Returns: List[NDVIResult] with same field_id and gps_coords
    """
    field_id = draw(uuid_string())
    coords = draw(gps_coordinates())
    num_readings = draw(st.integers(min_value=min_readings, max_value=max_readings))
    
    base_date = datetime(2023, 1, 1)
    readings = []
    
    for i in range(num_readings):
        # Generate NDVI value in valid range
        ndvi_value = draw(st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False))
        confidence = draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False))
        
        reading = NDVIResult(
            field_id=field_id,
            gps_coords=coords,
            ndvi_value=ndvi_value,
            timestamp=base_date + timedelta(days=i * 7),  # Weekly readings
            confidence=confidence,
            satellite_image_url=f's3://kisan-setu-satellite/{field_id}_{i}.tif'
        )
        readings.append(reading)
    
    return readings


# ============================================================================
# Property 10: Yield Prediction Completeness
# ============================================================================

@given(
    ndvi_history=ndvi_time_series_for_yield(min_readings=1, max_readings=20),
    crop=crop_type()
)
@settings(max_examples=100, deadline=None)
def test_property_10_yield_prediction_completeness(ndvi_history, crop):
    """
    **Property 10: Yield Prediction Completeness**
    **Validates: Requirements 3.4, 3.6**
    
    For any yield prediction, the result should include:
    1. An estimated volume (numeric, positive)
    2. A confidence interval where lower_bound <= estimate <= upper_bound
    3. A maturity stage (one of valid stages)
    4. Be based on at least one NDVI reading
    
    This test verifies that:
    - All required fields are present
    - Estimated volume is positive
    - Confidence interval is valid (lower <= estimate <= upper)
    - Maturity stage is one of the valid stages
    - Prediction is based on NDVI data
    """
    # Create analyzer
    analyzer = SatelliteAnalyzer(
        sagemaker_client=Mock(),
        s3_client=Mock(),
        dynamodb_table=Mock()
    )
    
    # Predict yield
    yield_prediction = analyzer.predict_yield(ndvi_history, crop)
    
    # Property 1: Result is a YieldPrediction object
    assert isinstance(yield_prediction, YieldPrediction), \
        "Result should be a YieldPrediction object"
    
    # Property 2: All required fields are present
    assert hasattr(yield_prediction, 'field_id'), "YieldPrediction should have field_id"
    assert hasattr(yield_prediction, 'estimated_volume'), "YieldPrediction should have estimated_volume"
    assert hasattr(yield_prediction, 'confidence_interval'), "YieldPrediction should have confidence_interval"
    assert hasattr(yield_prediction, 'maturity_stage'), "YieldPrediction should have maturity_stage"
    assert hasattr(yield_prediction, 'prediction_date'), "YieldPrediction should have prediction_date"
    
    # Property 3: Estimated volume is numeric and positive
    assert isinstance(yield_prediction.estimated_volume, (int, float)), \
        f"Estimated volume should be numeric, got {type(yield_prediction.estimated_volume)}"
    assert yield_prediction.estimated_volume > 0, \
        f"Estimated volume should be positive, got {yield_prediction.estimated_volume}"
    
    # Property 4: Confidence interval is valid
    assert isinstance(yield_prediction.confidence_interval, tuple), \
        "Confidence interval should be a tuple"
    assert len(yield_prediction.confidence_interval) == 2, \
        f"Confidence interval should have 2 elements, got {len(yield_prediction.confidence_interval)}"
    
    lower_bound, upper_bound = yield_prediction.confidence_interval
    
    assert isinstance(lower_bound, (int, float)), \
        f"Lower bound should be numeric, got {type(lower_bound)}"
    assert isinstance(upper_bound, (int, float)), \
        f"Upper bound should be numeric, got {type(upper_bound)}"
    
    # Property 5: Confidence interval bounds are valid (lower <= estimate <= upper)
    assert lower_bound <= yield_prediction.estimated_volume, \
        f"Lower bound ({lower_bound}) should be <= estimated volume ({yield_prediction.estimated_volume})"
    assert yield_prediction.estimated_volume <= upper_bound, \
        f"Estimated volume ({yield_prediction.estimated_volume}) should be <= upper bound ({upper_bound})"
    
    # Property 6: Lower bound is non-negative
    assert lower_bound >= 0, \
        f"Lower bound should be non-negative, got {lower_bound}"
    
    # Property 7: Maturity stage is one of the valid stages
    valid_stages = ['early', 'mid', 'late', 'harvest_ready']
    assert yield_prediction.maturity_stage in valid_stages, \
        f"Maturity stage must be one of {valid_stages}, got '{yield_prediction.maturity_stage}'"
    
    # Property 8: Prediction is based on NDVI data (field_id matches)
    assert yield_prediction.field_id == ndvi_history[-1].field_id, \
        "Prediction field_id should match the NDVI history field_id"
    
    # Property 9: Prediction date is set
    assert yield_prediction.prediction_date is not None, \
        "Prediction date should be set"
    assert isinstance(yield_prediction.prediction_date, datetime), \
        f"Prediction date should be a datetime, got {type(yield_prediction.prediction_date)}"


@given(
    ndvi_value=st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    crop=crop_type()
)
@settings(max_examples=100, deadline=None)
def test_property_10_single_ndvi_yield_prediction(ndvi_value, crop):
    """
    **Property 10: Yield Prediction Completeness (Single NDVI)**
    **Validates: Requirements 3.4, 3.6**
    
    Test that yield prediction works with a single NDVI reading and produces
    all required fields.
    """
    # Create analyzer
    analyzer = SatelliteAnalyzer(
        sagemaker_client=Mock(),
        s3_client=Mock(),
        dynamodb_table=Mock()
    )
    
    # Create single NDVI reading
    field_id = 'test_field'
    coords = (20.0, 77.0)
    
    ndvi_history = [NDVIResult(
        field_id=field_id,
        gps_coords=coords,
        ndvi_value=ndvi_value,
        timestamp=datetime.utcnow(),
        confidence=0.9,
        satellite_image_url='s3://test/image.tif'
    )]
    
    # Predict yield
    yield_prediction = analyzer.predict_yield(ndvi_history, crop)
    
    # Verify all required fields are present
    assert yield_prediction.estimated_volume > 0, \
        "Estimated volume should be positive"
    
    lower_bound, upper_bound = yield_prediction.confidence_interval
    assert lower_bound <= yield_prediction.estimated_volume <= upper_bound, \
        "Confidence interval should contain estimated volume"
    
    valid_stages = ['early', 'mid', 'late', 'harvest_ready']
    assert yield_prediction.maturity_stage in valid_stages, \
        f"Maturity stage must be valid, got '{yield_prediction.maturity_stage}'"


@given(
    ndvi_values=st.lists(
        st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        min_size=3,
        max_size=10
    ),
    crop=crop_type()
)
@settings(max_examples=100, deadline=None)
def test_property_10_confidence_interval_width(ndvi_values, crop):
    """
    **Property 10: Yield Prediction Completeness (Confidence Interval)**
    **Validates: Requirements 3.4, 3.6**
    
    Test that confidence interval width is reasonable and consistent.
    """
    # Create analyzer
    analyzer = SatelliteAnalyzer(
        sagemaker_client=Mock(),
        s3_client=Mock(),
        dynamodb_table=Mock()
    )
    
    # Create NDVI time series
    field_id = 'test_field'
    coords = (20.0, 77.0)
    base_date = datetime(2023, 1, 1)
    
    ndvi_history = []
    for i, ndvi_value in enumerate(ndvi_values):
        reading = NDVIResult(
            field_id=field_id,
            gps_coords=coords,
            ndvi_value=ndvi_value,
            timestamp=base_date + timedelta(days=i * 7),
            confidence=0.9,
            satellite_image_url=f's3://test/image_{i}.tif'
        )
        ndvi_history.append(reading)
    
    # Predict yield
    yield_prediction = analyzer.predict_yield(ndvi_history, crop)
    
    lower_bound, upper_bound = yield_prediction.confidence_interval
    estimated = yield_prediction.estimated_volume
    
    # Property: Confidence interval is symmetric around estimate (±15% for MVP)
    margin = estimated * 0.15
    expected_lower = max(0, estimated - margin)
    expected_upper = estimated + margin
    
    # Allow small floating-point tolerance
    assert abs(lower_bound - expected_lower) < 0.01, \
        f"Lower bound should be estimate - 15%, expected {expected_lower:.2f}, got {lower_bound:.2f}"
    assert abs(upper_bound - expected_upper) < 0.01, \
        f"Upper bound should be estimate + 15%, expected {expected_upper:.2f}, got {upper_bound:.2f}"


# ============================================================================
# Edge Cases
# ============================================================================

def test_edge_case_empty_ndvi_history():
    """
    Test that yield prediction fails gracefully with empty NDVI history.
    """
    analyzer = SatelliteAnalyzer(
        sagemaker_client=Mock(),
        s3_client=Mock(),
        dynamodb_table=Mock()
    )
    
    # Empty NDVI history should raise ValueError
    with pytest.raises(ValueError) as exc_info:
        analyzer.predict_yield([], 'wheat')
    
    assert 'ndvi' in str(exc_info.value).lower() or 'history' in str(exc_info.value).lower(), \
        "Error message should mention NDVI history"


def test_edge_case_very_low_ndvi_yield():
    """
    Test yield prediction with very low NDVI values (poor crop health).
    """
    analyzer = SatelliteAnalyzer(
        sagemaker_client=Mock(),
        s3_client=Mock(),
        dynamodb_table=Mock()
    )
    
    # Very low NDVI
    field_id = 'test_field'
    coords = (20.0, 77.0)
    
    ndvi_history = [NDVIResult(
        field_id=field_id,
        gps_coords=coords,
        ndvi_value=0.1,
        timestamp=datetime.utcnow(),
        confidence=0.9,
        satellite_image_url='s3://test/image.tif'
    )]
    
    yield_prediction = analyzer.predict_yield(ndvi_history, 'wheat')
    
    # Should still produce valid prediction
    assert yield_prediction.estimated_volume > 0, \
        "Should produce positive yield estimate even with low NDVI"
    
    lower_bound, upper_bound = yield_prediction.confidence_interval
    assert lower_bound <= yield_prediction.estimated_volume <= upper_bound, \
        "Confidence interval should be valid"


def test_edge_case_high_ndvi_yield():
    """
    Test yield prediction with high NDVI values (healthy crop).
    """
    analyzer = SatelliteAnalyzer(
        sagemaker_client=Mock(),
        s3_client=Mock(),
        dynamodb_table=Mock()
    )
    
    # High NDVI
    field_id = 'test_field'
    coords = (20.0, 77.0)
    
    ndvi_history = [NDVIResult(
        field_id=field_id,
        gps_coords=coords,
        ndvi_value=0.8,
        timestamp=datetime.utcnow(),
        confidence=0.9,
        satellite_image_url='s3://test/image.tif'
    )]
    
    yield_prediction = analyzer.predict_yield(ndvi_history, 'wheat')
    
    # Should produce valid prediction
    assert yield_prediction.estimated_volume > 0, \
        "Should produce positive yield estimate with high NDVI"
    
    lower_bound, upper_bound = yield_prediction.confidence_interval
    assert lower_bound <= yield_prediction.estimated_volume <= upper_bound, \
        "Confidence interval should be valid"


def test_edge_case_multiple_crops():
    """
    Test yield prediction for different crop types.
    """
    analyzer = SatelliteAnalyzer(
        sagemaker_client=Mock(),
        s3_client=Mock(),
        dynamodb_table=Mock()
    )
    
    field_id = 'test_field'
    coords = (20.0, 77.0)
    
    ndvi_history = [NDVIResult(
        field_id=field_id,
        gps_coords=coords,
        ndvi_value=0.6,
        timestamp=datetime.utcnow(),
        confidence=0.9,
        satellite_image_url='s3://test/image.tif'
    )]
    
    crops = ['wheat', 'rice', 'onion', 'cotton']
    
    for crop in crops:
        yield_prediction = analyzer.predict_yield(ndvi_history, crop)
        
        # Each crop should produce valid prediction
        assert yield_prediction.estimated_volume > 0, \
            f"Should produce positive yield for {crop}"
        
        lower_bound, upper_bound = yield_prediction.confidence_interval
        assert lower_bound <= yield_prediction.estimated_volume <= upper_bound, \
            f"Confidence interval should be valid for {crop}"
        
        valid_stages = ['early', 'mid', 'late', 'harvest_ready']
        assert yield_prediction.maturity_stage in valid_stages, \
            f"Maturity stage should be valid for {crop}"


def test_edge_case_long_time_series():
    """
    Test yield prediction with a long NDVI time series.
    """
    analyzer = SatelliteAnalyzer(
        sagemaker_client=Mock(),
        s3_client=Mock(),
        dynamodb_table=Mock()
    )
    
    field_id = 'test_field'
    coords = (20.0, 77.0)
    base_date = datetime(2023, 1, 1)
    
    # Create 52 weeks of NDVI data (1 year)
    ndvi_history = []
    for i in range(52):
        # Simulate crop growth cycle
        if i < 10:
            ndvi_value = 0.2 + (i * 0.04)  # Early growth
        elif i < 30:
            ndvi_value = 0.6 + ((i - 10) * 0.01)  # Peak growth
        else:
            ndvi_value = 0.8 - ((i - 30) * 0.02)  # Decline
        
        ndvi_value = max(-1.0, min(1.0, ndvi_value))  # Clamp to valid range
        
        reading = NDVIResult(
            field_id=field_id,
            gps_coords=coords,
            ndvi_value=ndvi_value,
            timestamp=base_date + timedelta(days=i * 7),
            confidence=0.9,
            satellite_image_url=f's3://test/image_{i}.tif'
        )
        ndvi_history.append(reading)
    
    yield_prediction = analyzer.predict_yield(ndvi_history, 'wheat')
    
    # Should produce valid prediction
    assert yield_prediction.estimated_volume > 0, \
        "Should produce positive yield with long time series"
    
    lower_bound, upper_bound = yield_prediction.confidence_interval
    assert lower_bound <= yield_prediction.estimated_volume <= upper_bound, \
        "Confidence interval should be valid"


def test_edge_case_negative_ndvi():
    """
    Test yield prediction with negative NDVI (water/bare soil).
    """
    analyzer = SatelliteAnalyzer(
        sagemaker_client=Mock(),
        s3_client=Mock(),
        dynamodb_table=Mock()
    )
    
    field_id = 'test_field'
    coords = (20.0, 77.0)
    
    ndvi_history = [NDVIResult(
        field_id=field_id,
        gps_coords=coords,
        ndvi_value=-0.3,
        timestamp=datetime.utcnow(),
        confidence=0.9,
        satellite_image_url='s3://test/image.tif'
    )]
    
    yield_prediction = analyzer.predict_yield(ndvi_history, 'wheat')
    
    # Should still produce valid prediction (even if low)
    assert yield_prediction.estimated_volume > 0, \
        "Should produce positive yield estimate even with negative NDVI"
    
    lower_bound, upper_bound = yield_prediction.confidence_interval
    assert lower_bound <= yield_prediction.estimated_volume <= upper_bound, \
        "Confidence interval should be valid"


def test_edge_case_unsorted_ndvi_history():
    """
    Test that yield prediction handles unsorted NDVI history correctly.
    """
    analyzer = SatelliteAnalyzer(
        sagemaker_client=Mock(),
        s3_client=Mock(),
        dynamodb_table=Mock()
    )
    
    field_id = 'test_field'
    coords = (20.0, 77.0)
    base_date = datetime(2023, 1, 1)
    
    # Create unsorted NDVI history
    ndvi_history = [
        NDVIResult(
            field_id=field_id,
            gps_coords=coords,
            ndvi_value=0.5,
            timestamp=base_date + timedelta(days=14),  # Third
            confidence=0.9,
            satellite_image_url='s3://test/image_2.tif'
        ),
        NDVIResult(
            field_id=field_id,
            gps_coords=coords,
            ndvi_value=0.3,
            timestamp=base_date,  # First
            confidence=0.9,
            satellite_image_url='s3://test/image_0.tif'
        ),
        NDVIResult(
            field_id=field_id,
            gps_coords=coords,
            ndvi_value=0.4,
            timestamp=base_date + timedelta(days=7),  # Second
            confidence=0.9,
            satellite_image_url='s3://test/image_1.tif'
        )
    ]
    
    yield_prediction = analyzer.predict_yield(ndvi_history, 'wheat')
    
    # Should produce valid prediction (implementation sorts internally)
    assert yield_prediction.estimated_volume > 0, \
        "Should handle unsorted NDVI history"
    
    lower_bound, upper_bound = yield_prediction.confidence_interval
    assert lower_bound <= yield_prediction.estimated_volume <= upper_bound, \
        "Confidence interval should be valid"

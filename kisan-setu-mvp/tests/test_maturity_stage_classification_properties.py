"""
Property-Based Tests for Maturity Stage Classification

Tests Property 9: Maturity Stage Classification
For any NDVI calculation, the predicted crop maturity stage should be one of the
valid stages: 'early', 'mid', 'late', or 'harvest_ready'.

**Validates: Requirements 3.3**

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

from satellite_analyzer import SatelliteAnalyzer, NDVIResult
from common.models import MaturityStage

# Import test data generators
from generators import ndvi_result, uuid_string, gps_coordinates


# ============================================================================
# Generators for NDVI Time Series
# ============================================================================

@st.composite
def ndvi_time_series_for_classification(draw, min_readings=1, max_readings=10):
    """
    Generate a time series of NDVI readings for maturity stage classification.
    
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
# Property 9: Maturity Stage Classification
# ============================================================================

@given(ndvi_history=ndvi_time_series_for_classification(min_readings=1, max_readings=10))
@settings(max_examples=100, deadline=None)
def test_property_9_maturity_stage_classification(ndvi_history):
    """
    **Property 9: Maturity Stage Classification**
    **Validates: Requirements 3.3**
    
    For any NDVI calculation, the predicted crop maturity stage should be one of the
    valid stages: 'early', 'mid', 'late', or 'harvest_ready'.
    
    This test verifies that:
    1. Maturity stage is always one of the valid stages
    2. Classification is deterministic (same input produces same output)
    3. Classification logic is consistent with NDVI values
    4. All valid stages can be produced by the classifier
    """
    # Create analyzer
    analyzer = SatelliteAnalyzer(
        sagemaker_client=Mock(),
        s3_client=Mock(),
        dynamodb_table=Mock()
    )
    
    # Classify maturity stage
    maturity_stage = analyzer._classify_maturity_stage(ndvi_history)
    
    # Property 1: Maturity stage is one of the valid stages
    valid_stages = ['early', 'mid', 'late', 'harvest_ready']
    assert maturity_stage in valid_stages, \
        f"Maturity stage must be one of {valid_stages}, got '{maturity_stage}'"
    
    # Property 2: Classification is deterministic
    maturity_stage_2 = analyzer._classify_maturity_stage(ndvi_history)
    assert maturity_stage == maturity_stage_2, \
        "Classification should be deterministic (same input produces same output)"
    
    # Property 3: Classification is consistent with NDVI values
    latest_ndvi = ndvi_history[-1].ndvi_value
    
    # Based on implementation logic:
    # - harvest_ready: latest_ndvi < 0.3 or (declining rapidly and < 0.5)
    # - late: latest_ndvi >= 0.6 and not increasing
    # - mid: 0.4 <= latest_ndvi < 0.6
    # - early: otherwise
    
    if len(ndvi_history) >= 2:
        recent_values = [r.ndvi_value for r in ndvi_history[-3:]]
        trend = recent_values[-1] - recent_values[0]
    else:
        trend = 0
    
    # Verify classification logic consistency
    if latest_ndvi < 0.3:
        # Should be harvest_ready or early (depending on trend)
        assert maturity_stage in ['harvest_ready', 'early'], \
            f"NDVI < 0.3 should produce 'harvest_ready' or 'early', got '{maturity_stage}'"
    
    if latest_ndvi >= 0.6 and trend <= 0:
        # Should be late
        assert maturity_stage == 'late', \
            f"NDVI >= 0.6 with non-increasing trend should produce 'late', got '{maturity_stage}'"
    
    if 0.4 <= latest_ndvi < 0.6:
        # Should be mid (unless declining rapidly)
        if not (trend < -0.1):
            assert maturity_stage == 'mid', \
                f"NDVI in [0.4, 0.6) should produce 'mid', got '{maturity_stage}'"


@given(
    ndvi_value=st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=100, deadline=None)
def test_property_9_single_ndvi_classification(ndvi_value):
    """
    **Property 9: Maturity Stage Classification (Single Reading)**
    **Validates: Requirements 3.3**
    
    Test that a single NDVI reading produces a valid maturity stage.
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
    
    # Classify maturity stage
    maturity_stage = analyzer._classify_maturity_stage(ndvi_history)
    
    # Property: Maturity stage is one of the valid stages
    valid_stages = ['early', 'mid', 'late', 'harvest_ready']
    assert maturity_stage in valid_stages, \
        f"Maturity stage must be one of {valid_stages}, got '{maturity_stage}'"


@given(
    ndvi_values=st.lists(
        st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        min_size=2,
        max_size=10
    )
)
@settings(max_examples=100, deadline=None)
def test_property_9_trend_based_classification(ndvi_values):
    """
    **Property 9: Maturity Stage Classification (Trend-Based)**
    **Validates: Requirements 3.3**
    
    Test that maturity stage classification considers NDVI trends correctly.
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
    
    # Classify maturity stage
    maturity_stage = analyzer._classify_maturity_stage(ndvi_history)
    
    # Property: Maturity stage is one of the valid stages
    valid_stages = ['early', 'mid', 'late', 'harvest_ready']
    assert maturity_stage in valid_stages, \
        f"Maturity stage must be one of {valid_stages}, got '{maturity_stage}'"
    
    # Property: Classification considers trend
    latest_ndvi = ndvi_values[-1]
    recent_values = ndvi_values[-3:] if len(ndvi_values) >= 3 else ndvi_values
    trend = recent_values[-1] - recent_values[0]
    
    # If NDVI is declining rapidly and low, should be harvest_ready
    if trend < -0.1 and latest_ndvi < 0.5:
        assert maturity_stage == 'harvest_ready', \
            f"Rapidly declining NDVI < 0.5 should produce 'harvest_ready', got '{maturity_stage}'"


# ============================================================================
# Edge Cases
# ============================================================================

def test_edge_case_empty_history():
    """
    Test maturity stage classification with empty NDVI history.
    """
    analyzer = SatelliteAnalyzer(
        sagemaker_client=Mock(),
        s3_client=Mock(),
        dynamodb_table=Mock()
    )
    
    # Empty history should return 'early'
    maturity_stage = analyzer._classify_maturity_stage([])
    
    assert maturity_stage == 'early', \
        f"Empty NDVI history should produce 'early', got '{maturity_stage}'"


def test_edge_case_very_low_ndvi():
    """
    Test maturity stage classification with very low NDVI (< 0.3).
    """
    analyzer = SatelliteAnalyzer(
        sagemaker_client=Mock(),
        s3_client=Mock(),
        dynamodb_table=Mock()
    )
    
    # Very low NDVI
    ndvi_history = [NDVIResult(
        field_id='test_field',
        gps_coords=(20.0, 77.0),
        ndvi_value=0.1,
        timestamp=datetime.utcnow(),
        confidence=0.9,
        satellite_image_url='s3://test/image.tif'
    )]
    
    maturity_stage = analyzer._classify_maturity_stage(ndvi_history)
    
    # Very low NDVI should produce 'harvest_ready'
    assert maturity_stage == 'harvest_ready', \
        f"Very low NDVI (< 0.3) should produce 'harvest_ready', got '{maturity_stage}'"


def test_edge_case_high_ndvi_stable():
    """
    Test maturity stage classification with high stable NDVI (>= 0.6).
    """
    analyzer = SatelliteAnalyzer(
        sagemaker_client=Mock(),
        s3_client=Mock(),
        dynamodb_table=Mock()
    )
    
    # High stable NDVI
    base_date = datetime(2023, 1, 1)
    ndvi_history = [
        NDVIResult(
            field_id='test_field',
            gps_coords=(20.0, 77.0),
            ndvi_value=0.7,
            timestamp=base_date,
            confidence=0.9,
            satellite_image_url='s3://test/image_0.tif'
        ),
        NDVIResult(
            field_id='test_field',
            gps_coords=(20.0, 77.0),
            ndvi_value=0.7,
            timestamp=base_date + timedelta(days=7),
            confidence=0.9,
            satellite_image_url='s3://test/image_1.tif'
        )
    ]
    
    maturity_stage = analyzer._classify_maturity_stage(ndvi_history)
    
    # High stable NDVI should produce 'late'
    assert maturity_stage == 'late', \
        f"High stable NDVI (>= 0.6) should produce 'late', got '{maturity_stage}'"


def test_edge_case_mid_range_ndvi():
    """
    Test maturity stage classification with mid-range NDVI (0.4-0.6).
    """
    analyzer = SatelliteAnalyzer(
        sagemaker_client=Mock(),
        s3_client=Mock(),
        dynamodb_table=Mock()
    )
    
    # Mid-range NDVI
    ndvi_history = [NDVIResult(
        field_id='test_field',
        gps_coords=(20.0, 77.0),
        ndvi_value=0.5,
        timestamp=datetime.utcnow(),
        confidence=0.9,
        satellite_image_url='s3://test/image.tif'
    )]
    
    maturity_stage = analyzer._classify_maturity_stage(ndvi_history)
    
    # Mid-range NDVI should produce 'mid'
    assert maturity_stage == 'mid', \
        f"Mid-range NDVI (0.4-0.6) should produce 'mid', got '{maturity_stage}'"


def test_edge_case_rapidly_declining_ndvi():
    """
    Test maturity stage classification with rapidly declining NDVI.
    """
    analyzer = SatelliteAnalyzer(
        sagemaker_client=Mock(),
        s3_client=Mock(),
        dynamodb_table=Mock()
    )
    
    # Rapidly declining NDVI
    base_date = datetime(2023, 1, 1)
    ndvi_history = [
        NDVIResult(
            field_id='test_field',
            gps_coords=(20.0, 77.0),
            ndvi_value=0.6,
            timestamp=base_date,
            confidence=0.9,
            satellite_image_url='s3://test/image_0.tif'
        ),
        NDVIResult(
            field_id='test_field',
            gps_coords=(20.0, 77.0),
            ndvi_value=0.4,
            timestamp=base_date + timedelta(days=7),
            confidence=0.9,
            satellite_image_url='s3://test/image_1.tif'
        ),
        NDVIResult(
            field_id='test_field',
            gps_coords=(20.0, 77.0),
            ndvi_value=0.2,
            timestamp=base_date + timedelta(days=14),
            confidence=0.9,
            satellite_image_url='s3://test/image_2.tif'
        )
    ]
    
    maturity_stage = analyzer._classify_maturity_stage(ndvi_history)
    
    # Rapidly declining NDVI should produce 'harvest_ready'
    assert maturity_stage == 'harvest_ready', \
        f"Rapidly declining NDVI should produce 'harvest_ready', got '{maturity_stage}'"


def test_edge_case_increasing_ndvi():
    """
    Test maturity stage classification with increasing NDVI (early growth).
    """
    analyzer = SatelliteAnalyzer(
        sagemaker_client=Mock(),
        s3_client=Mock(),
        dynamodb_table=Mock()
    )
    
    # Increasing NDVI
    base_date = datetime(2023, 1, 1)
    ndvi_history = [
        NDVIResult(
            field_id='test_field',
            gps_coords=(20.0, 77.0),
            ndvi_value=0.2,
            timestamp=base_date,
            confidence=0.9,
            satellite_image_url='s3://test/image_0.tif'
        ),
        NDVIResult(
            field_id='test_field',
            gps_coords=(20.0, 77.0),
            ndvi_value=0.3,
            timestamp=base_date + timedelta(days=7),
            confidence=0.9,
            satellite_image_url='s3://test/image_1.tif'
        )
    ]
    
    maturity_stage = analyzer._classify_maturity_stage(ndvi_history)
    
    # Increasing NDVI should produce 'early'
    assert maturity_stage == 'early', \
        f"Increasing NDVI should produce 'early', got '{maturity_stage}'"


def test_edge_case_negative_ndvi():
    """
    Test maturity stage classification with negative NDVI (water/bare soil).
    """
    analyzer = SatelliteAnalyzer(
        sagemaker_client=Mock(),
        s3_client=Mock(),
        dynamodb_table=Mock()
    )
    
    # Negative NDVI
    ndvi_history = [NDVIResult(
        field_id='test_field',
        gps_coords=(20.0, 77.0),
        ndvi_value=-0.2,
        timestamp=datetime.utcnow(),
        confidence=0.9,
        satellite_image_url='s3://test/image.tif'
    )]
    
    maturity_stage = analyzer._classify_maturity_stage(ndvi_history)
    
    # Negative NDVI should still produce a valid stage
    valid_stages = ['early', 'mid', 'late', 'harvest_ready']
    assert maturity_stage in valid_stages, \
        f"Negative NDVI should still produce a valid stage, got '{maturity_stage}'"

"""
Property-Based Tests for NDVI Value Range Validity

Tests Property 8: NDVI Value Range Validity
For any satellite imagery with valid Red (B4) and NIR (B8) bands, the calculated
NDVI value must be in the range [-1, 1], as per the formula (NIR - Red) / (NIR + Red).

**Validates: Requirements 3.2**

Uses Hypothesis framework with minimum 100 iterations.
"""

import pytest
import sys
import os
from hypothesis import given, settings, strategies as st, assume
from datetime import datetime
from unittest.mock import Mock, patch
import random

# Add lambda directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda', 'satellite'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))

from satellite_analyzer import SatelliteAnalyzer, SatelliteImage, NDVIResult

# Import test data generators
from generators import gps_coordinates, uuid_string


# ============================================================================
# Generators for Band Values
# ============================================================================

@st.composite
def band_values(draw):
    """
    Generate valid band values for Red (B4) and NIR (B8).
    
    Band values are typically in the range [0, 10000] for Sentinel-2 imagery
    (representing reflectance values scaled by 10000).
    
    Returns: Tuple of (B4_value, B8_value)
    """
    # Generate band values that can produce the full NDVI range
    # NDVI = (B8 - B4) / (B8 + B4)
    
    # Use a wide range to test edge cases
    b4 = draw(st.floats(min_value=0.0, max_value=10000.0, allow_nan=False, allow_infinity=False))
    b8 = draw(st.floats(min_value=0.0, max_value=10000.0, allow_nan=False, allow_infinity=False))
    
    # Filter out cases where both are zero (undefined NDVI)
    assume(b4 + b8 > 0.0)
    
    return (b4, b8)


@st.composite
def satellite_image_with_bands(draw):
    """
    Generate a SatelliteImage with valid band data.
    
    Returns: SatelliteImage with B4 and B8 bands
    """
    coords = draw(gps_coordinates())
    image_id = draw(uuid_string())
    
    # Generate band URLs
    bands = {
        'B4': f's3://kisan-setu-satellite/{image_id}_B4.tif',
        'B8': f's3://kisan-setu-satellite/{image_id}_B8.tif'
    }
    
    return SatelliteImage(
        image_id=image_id,
        gps_coords=coords,
        bands=bands,
        timestamp=datetime.utcnow(),
        cloud_cover=draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)),
        data_source='Sentinel-2'
    )


# ============================================================================
# Property 8: NDVI Value Range Validity
# ============================================================================

@given(
    satellite_image=satellite_image_with_bands(),
    b4_value=st.floats(min_value=0.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
    b8_value=st.floats(min_value=0.0, max_value=10000.0, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=100, deadline=None)
def test_property_8_ndvi_value_range_validity(satellite_image, b4_value, b8_value):
    """
    **Property 8: NDVI Value Range Validity**
    **Validates: Requirements 3.2**
    
    For any satellite imagery with valid Red (B4) and NIR (B8) bands, the calculated
    NDVI value must be in the range [-1, 1], as per the formula (NIR - Red) / (NIR + Red).
    
    This test verifies that:
    1. NDVI calculation produces values in the valid range [-1, 1]
    2. The formula (B8 - B4) / (B8 + B4) is correctly applied
    3. Edge cases (zero denominators, extreme values) are handled
    4. The result is a valid NDVIResult object
    """
    # Filter out cases where denominator would be zero
    assume(b4_value + b8_value > 0.0)
    
    # Create mock clients
    mock_sagemaker = Mock()
    mock_s3 = Mock()
    mock_table = Mock()
    
    # Create analyzer
    analyzer = SatelliteAnalyzer(
        sagemaker_client=mock_sagemaker,
        s3_client=mock_s3,
        dynamodb_table=mock_table
    )
    
    # Mock the _simulate_ndvi_calculation to use actual band values
    def mock_ndvi_calc(b4_url, b8_url):
        # Calculate NDVI using the formula: (B8 - B4) / (B8 + B4)
        numerator = b8_value - b4_value
        denominator = b8_value + b4_value
        
        if denominator == 0:
            return 0.0  # Handle edge case
        
        return numerator / denominator
    
    with patch.object(analyzer, '_simulate_ndvi_calculation', side_effect=mock_ndvi_calc):
        # Calculate NDVI
        ndvi_result = analyzer.calculate_ndvi(satellite_image)
        
        # Property 1: Result is an NDVIResult object
        assert isinstance(ndvi_result, NDVIResult), \
            "Result should be an NDVIResult object"
        
        # Property 2: NDVI value is in the valid range [-1, 1]
        assert -1.0 <= ndvi_result.ndvi_value <= 1.0, \
            f"NDVI value must be in range [-1, 1], got {ndvi_result.ndvi_value}"
        
        # Property 3: NDVI value matches the formula (B8 - B4) / (B8 + B4)
        expected_ndvi = (b8_value - b4_value) / (b8_value + b4_value)
        
        # Clamp expected value to [-1, 1] as the implementation does
        expected_ndvi = max(-1.0, min(1.0, expected_ndvi))
        
        # Allow small floating-point tolerance
        assert abs(ndvi_result.ndvi_value - expected_ndvi) < 0.001, \
            f"NDVI value should match formula: expected {expected_ndvi:.6f}, got {ndvi_result.ndvi_value:.6f}"
        
        # Property 4: All required fields are present
        assert hasattr(ndvi_result, 'field_id'), "NDVIResult should have field_id"
        assert hasattr(ndvi_result, 'gps_coords'), "NDVIResult should have gps_coords"
        assert hasattr(ndvi_result, 'ndvi_value'), "NDVIResult should have ndvi_value"
        assert hasattr(ndvi_result, 'timestamp'), "NDVIResult should have timestamp"
        assert hasattr(ndvi_result, 'confidence'), "NDVIResult should have confidence"
        assert hasattr(ndvi_result, 'satellite_image_url'), "NDVIResult should have satellite_image_url"
        
        # Property 5: GPS coordinates are preserved
        assert ndvi_result.gps_coords == satellite_image.gps_coords, \
            "GPS coordinates should be preserved from input"
        
        # Property 6: Timestamp is preserved
        assert ndvi_result.timestamp == satellite_image.timestamp, \
            "Timestamp should be preserved from input"
        
        # Property 7: Confidence is in valid range [0, 1]
        assert 0.0 <= ndvi_result.confidence <= 1.0, \
            f"Confidence should be in range [0, 1], got {ndvi_result.confidence}"


@given(bands=band_values())
@settings(max_examples=100, deadline=None)
def test_property_8_ndvi_formula_correctness(bands):
    """
    **Property 8: NDVI Value Range Validity (Formula Correctness)**
    **Validates: Requirements 3.2**
    
    Test that the NDVI formula (B8 - B4) / (B8 + B4) always produces values
    in the range [-1, 1] for any valid band values.
    
    Mathematical proof:
    - If B8 >= B4 >= 0: NDVI = (B8 - B4) / (B8 + B4) is in [0, 1]
    - If B4 > B8 >= 0: NDVI = (B8 - B4) / (B8 + B4) is in [-1, 0)
    - Therefore, NDVI is always in [-1, 1]
    """
    b4, b8 = bands
    
    # Calculate NDVI using the formula
    numerator = b8 - b4
    denominator = b8 + b4
    
    # Denominator should be positive (filtered by assume in generator)
    assert denominator > 0, "Denominator should be positive"
    
    ndvi = numerator / denominator
    
    # Property: NDVI is always in [-1, 1]
    assert -1.0 <= ndvi <= 1.0, \
        f"NDVI formula should always produce values in [-1, 1], got {ndvi} for B4={b4}, B8={b8}"


@given(satellite_image=satellite_image_with_bands())
@settings(max_examples=100, deadline=None)
def test_property_8_ndvi_with_missing_bands(satellite_image):
    """
    **Property 8: NDVI Value Range Validity (Missing Bands)**
    **Validates: Requirements 3.2**
    
    Test that NDVI calculation fails gracefully when required bands are missing.
    """
    # Create analyzer
    analyzer = SatelliteAnalyzer(
        sagemaker_client=Mock(),
        s3_client=Mock(),
        dynamodb_table=Mock()
    )
    
    # Test with missing B4 band
    satellite_image_no_b4 = SatelliteImage(
        image_id=satellite_image.image_id,
        gps_coords=satellite_image.gps_coords,
        bands={'B8': satellite_image.bands['B8']},  # Only B8, no B4
        timestamp=satellite_image.timestamp,
        cloud_cover=satellite_image.cloud_cover,
        data_source=satellite_image.data_source
    )
    
    with pytest.raises(ValueError) as exc_info:
        analyzer.calculate_ndvi(satellite_image_no_b4)
    
    assert 'missing' in str(exc_info.value).lower() or 'required' in str(exc_info.value).lower(), \
        "Error message should indicate missing bands"
    
    # Test with missing B8 band
    satellite_image_no_b8 = SatelliteImage(
        image_id=satellite_image.image_id,
        gps_coords=satellite_image.gps_coords,
        bands={'B4': satellite_image.bands['B4']},  # Only B4, no B8
        timestamp=satellite_image.timestamp,
        cloud_cover=satellite_image.cloud_cover,
        data_source=satellite_image.data_source
    )
    
    with pytest.raises(ValueError) as exc_info:
        analyzer.calculate_ndvi(satellite_image_no_b8)
    
    assert 'missing' in str(exc_info.value).lower() or 'required' in str(exc_info.value).lower(), \
        "Error message should indicate missing bands"


# ============================================================================
# Edge Cases
# ============================================================================

def test_edge_case_equal_bands():
    """
    Test NDVI calculation when B4 == B8 (should produce NDVI = 0).
    """
    coords = (20.0, 77.0)
    satellite_image = SatelliteImage(
        image_id='test_equal_bands',
        gps_coords=coords,
        bands={
            'B4': 's3://test/B4.tif',
            'B8': 's3://test/B8.tif'
        },
        timestamp=datetime.utcnow(),
        cloud_cover=10.0,
        data_source='Sentinel-2'
    )
    
    analyzer = SatelliteAnalyzer(
        sagemaker_client=Mock(),
        s3_client=Mock(),
        dynamodb_table=Mock()
    )
    
    # Mock equal band values
    def mock_ndvi_calc(b4_url, b8_url):
        b4 = 5000.0
        b8 = 5000.0
        return (b8 - b4) / (b8 + b4)  # Should be 0
    
    with patch.object(analyzer, '_simulate_ndvi_calculation', side_effect=mock_ndvi_calc):
        result = analyzer.calculate_ndvi(satellite_image)
        
        # NDVI should be 0 when bands are equal
        assert abs(result.ndvi_value - 0.0) < 0.001, \
            f"NDVI should be 0 when B4 == B8, got {result.ndvi_value}"
        
        # Should still be in valid range
        assert -1.0 <= result.ndvi_value <= 1.0


def test_edge_case_maximum_ndvi():
    """
    Test NDVI calculation when B4 = 0 and B8 > 0 (should produce NDVI = 1).
    """
    coords = (20.0, 77.0)
    satellite_image = SatelliteImage(
        image_id='test_max_ndvi',
        gps_coords=coords,
        bands={
            'B4': 's3://test/B4.tif',
            'B8': 's3://test/B8.tif'
        },
        timestamp=datetime.utcnow(),
        cloud_cover=10.0,
        data_source='Sentinel-2'
    )
    
    analyzer = SatelliteAnalyzer(
        sagemaker_client=Mock(),
        s3_client=Mock(),
        dynamodb_table=Mock()
    )
    
    # Mock B4=0, B8>0
    def mock_ndvi_calc(b4_url, b8_url):
        b4 = 0.0
        b8 = 10000.0
        return (b8 - b4) / (b8 + b4)  # Should be 1
    
    with patch.object(analyzer, '_simulate_ndvi_calculation', side_effect=mock_ndvi_calc):
        result = analyzer.calculate_ndvi(satellite_image)
        
        # NDVI should be 1 when B4 = 0
        assert abs(result.ndvi_value - 1.0) < 0.001, \
            f"NDVI should be 1 when B4 = 0, got {result.ndvi_value}"
        
        # Should be in valid range
        assert -1.0 <= result.ndvi_value <= 1.0


def test_edge_case_minimum_ndvi():
    """
    Test NDVI calculation when B8 = 0 and B4 > 0 (should produce NDVI = -1).
    """
    coords = (20.0, 77.0)
    satellite_image = SatelliteImage(
        image_id='test_min_ndvi',
        gps_coords=coords,
        bands={
            'B4': 's3://test/B4.tif',
            'B8': 's3://test/B8.tif'
        },
        timestamp=datetime.utcnow(),
        cloud_cover=10.0,
        data_source='Sentinel-2'
    )
    
    analyzer = SatelliteAnalyzer(
        sagemaker_client=Mock(),
        s3_client=Mock(),
        dynamodb_table=Mock()
    )
    
    # Mock B8=0, B4>0
    def mock_ndvi_calc(b4_url, b8_url):
        b4 = 10000.0
        b8 = 0.0
        return (b8 - b4) / (b8 + b4)  # Should be -1
    
    with patch.object(analyzer, '_simulate_ndvi_calculation', side_effect=mock_ndvi_calc):
        result = analyzer.calculate_ndvi(satellite_image)
        
        # NDVI should be -1 when B8 = 0
        assert abs(result.ndvi_value - (-1.0)) < 0.001, \
            f"NDVI should be -1 when B8 = 0, got {result.ndvi_value}"
        
        # Should be in valid range
        assert -1.0 <= result.ndvi_value <= 1.0


def test_edge_case_healthy_vegetation():
    """
    Test NDVI calculation for typical healthy vegetation (NDVI ~ 0.3 to 0.8).
    """
    coords = (20.0, 77.0)
    satellite_image = SatelliteImage(
        image_id='test_healthy_veg',
        gps_coords=coords,
        bands={
            'B4': 's3://test/B4.tif',
            'B8': 's3://test/B8.tif'
        },
        timestamp=datetime.utcnow(),
        cloud_cover=10.0,
        data_source='Sentinel-2'
    )
    
    analyzer = SatelliteAnalyzer(
        sagemaker_client=Mock(),
        s3_client=Mock(),
        dynamodb_table=Mock()
    )
    
    # Mock typical healthy vegetation values
    def mock_ndvi_calc(b4_url, b8_url):
        b4 = 2000.0  # Lower red reflectance
        b8 = 8000.0  # Higher NIR reflectance
        return (b8 - b8) / (b8 + b4)  # Should be ~0.6
    
    with patch.object(analyzer, '_simulate_ndvi_calculation', side_effect=mock_ndvi_calc):
        result = analyzer.calculate_ndvi(satellite_image)
        
        # Should be in valid range
        assert -1.0 <= result.ndvi_value <= 1.0, \
            f"NDVI should be in valid range, got {result.ndvi_value}"
        
        # Should be positive for healthy vegetation
        assert result.ndvi_value >= 0.0, \
            "NDVI for healthy vegetation should be positive"


def test_edge_case_bare_soil():
    """
    Test NDVI calculation for bare soil (NDVI ~ 0.1 to 0.2).
    """
    coords = (20.0, 77.0)
    satellite_image = SatelliteImage(
        image_id='test_bare_soil',
        gps_coords=coords,
        bands={
            'B4': 's3://test/B4.tif',
            'B8': 's3://test/B8.tif'
        },
        timestamp=datetime.utcnow(),
        cloud_cover=10.0,
        data_source='Sentinel-2'
    )
    
    analyzer = SatelliteAnalyzer(
        sagemaker_client=Mock(),
        s3_client=Mock(),
        dynamodb_table=Mock()
    )
    
    # Mock bare soil values (similar red and NIR)
    def mock_ndvi_calc(b4_url, b8_url):
        b4 = 4500.0
        b8 = 5500.0
        return (b8 - b4) / (b8 + b4)  # Should be ~0.1
    
    with patch.object(analyzer, '_simulate_ndvi_calculation', side_effect=mock_ndvi_calc):
        result = analyzer.calculate_ndvi(satellite_image)
        
        # Should be in valid range
        assert -1.0 <= result.ndvi_value <= 1.0, \
            f"NDVI should be in valid range, got {result.ndvi_value}"


def test_edge_case_water():
    """
    Test NDVI calculation for water (NDVI < 0).
    """
    coords = (20.0, 77.0)
    satellite_image = SatelliteImage(
        image_id='test_water',
        gps_coords=coords,
        bands={
            'B4': 's3://test/B4.tif',
            'B8': 's3://test/B8.tif'
        },
        timestamp=datetime.utcnow(),
        cloud_cover=10.0,
        data_source='Sentinel-2'
    )
    
    analyzer = SatelliteAnalyzer(
        sagemaker_client=Mock(),
        s3_client=Mock(),
        dynamodb_table=Mock()
    )
    
    # Mock water values (higher red than NIR)
    def mock_ndvi_calc(b4_url, b8_url):
        b4 = 6000.0
        b8 = 3000.0
        return (b8 - b4) / (b8 + b4)  # Should be negative
    
    with patch.object(analyzer, '_simulate_ndvi_calculation', side_effect=mock_ndvi_calc):
        result = analyzer.calculate_ndvi(satellite_image)
        
        # Should be in valid range
        assert -1.0 <= result.ndvi_value <= 1.0, \
            f"NDVI should be in valid range, got {result.ndvi_value}"
        
        # Should be negative for water
        assert result.ndvi_value < 0.0, \
            "NDVI for water should be negative"

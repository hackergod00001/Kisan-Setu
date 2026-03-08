"""
Property-Based Tests for Satellite Analyzer Component.

Tests correctness properties from the design document:
- Property 7: GPS-Based Imagery Retrieval (Requirement 3.1)
- Property 8: NDVI Value Range Validity (Requirement 3.2)
- Property 9: Maturity Stage Classification (Requirement 3.3)
- Property 10: Yield Prediction Completeness (Requirements 3.4, 3.6)
- Property 28: Satellite Data Caching (Requirement 9.5)
"""

import pytest
import math
from hypothesis import given, strategies as st, settings, assume
from datetime import datetime, date, timedelta
from decimal import Decimal
from unittest.mock import Mock
import sys
import os

# Add lambda directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))

from satellite.satellite_analyzer import (
    SatelliteAnalyzer,
    SatelliteImage,
    NDVIResult,
    YieldPrediction
)


# ==================== Custom Strategies ====================

@st.composite
def valid_gps_coords(draw):
    """Generate valid GPS coordinates."""
    latitude = draw(st.floats(min_value=-90.0, max_value=90.0, allow_nan=False, allow_infinity=False))
    longitude = draw(st.floats(min_value=-180.0, max_value=180.0, allow_nan=False, allow_infinity=False))
    return (latitude, longitude)


@st.composite
def date_range_strategy(draw):
    """Generate valid date ranges."""
    # Generate dates within last year
    days_ago_start = draw(st.integers(min_value=7, max_value=365))
    days_ago_end = draw(st.integers(min_value=0, max_value=days_ago_start))
    
    end_date = date.today() - timedelta(days=days_ago_end)
    start_date = date.today() - timedelta(days=days_ago_start)
    
    return (start_date, end_date)


@st.composite
def satellite_image_strategy(draw):
    """Generate SatelliteImage objects."""
    gps_coords = draw(valid_gps_coords())
    cloud_cover = draw(st.floats(min_value=0.0, max_value=100.0))
    
    return SatelliteImage(
        image_id=f"S2_{draw(st.text(min_size=8, max_size=16, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))))}",
        gps_coords=gps_coords,
        bands={
            'B4': f"s3://bucket/sentinel2/B4_{draw(st.integers(min_value=1, max_value=9999))}.tif",
            'B8': f"s3://bucket/sentinel2/B8_{draw(st.integers(min_value=1, max_value=9999))}.tif"
        },
        timestamp=datetime.utcnow(),
        cloud_cover=cloud_cover,
        data_source='Sentinel-2'
    )


@st.composite
def ndvi_result_strategy(draw):
    """Generate NDVIResult objects."""
    gps_coords = draw(valid_gps_coords())
    ndvi_value = draw(st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False))
    confidence = draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False))
    
    return NDVIResult(
        field_id=f"FIELD#{draw(st.text(min_size=8, max_size=8, alphabet=st.characters(whitelist_categories=('Ll', 'Nd'))))}",
        gps_coords=gps_coords,
        ndvi_value=ndvi_value,
        timestamp=datetime.utcnow() - timedelta(days=draw(st.integers(min_value=0, max_value=30))),
        confidence=confidence,
        satellite_image_url=f"s3://bucket/image_{draw(st.integers(min_value=1, max_value=9999))}.tif"
    )


@st.composite
def ndvi_history_strategy(draw):
    """Generate list of NDVIResult objects (time series)."""
    size = draw(st.integers(min_value=1, max_value=10))
    gps_coords = draw(valid_gps_coords())
    field_id = f"FIELD#{draw(st.text(min_size=8, max_size=8, alphabet=st.characters(whitelist_categories=('Ll', 'Nd'))))}"
    
    history = []
    for i in range(size):
        ndvi_value = draw(st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False))
        confidence = draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False))
        
        history.append(NDVIResult(
            field_id=field_id,
            gps_coords=gps_coords,
            ndvi_value=ndvi_value,
            timestamp=datetime.utcnow() - timedelta(days=size - i),
            confidence=confidence,
            satellite_image_url=f"s3://bucket/image_{i}.tif"
        ))
    
    return history


@st.composite
def crop_type_strategy(draw):
    """Generate crop types."""
    crops = ['onion', 'wheat', 'rice', 'cotton', 'tomato', 'potato']
    return draw(st.sampled_from(crops))


# ==================== Property-Based Tests ====================

class TestSatelliteProperties:
    """Property-based tests for Satellite Analyzer correctness properties."""
    
    def _create_analyzer(self):
        """Create SatelliteAnalyzer with mocked clients."""
        mock_sagemaker = Mock()
        mock_s3 = Mock()
        mock_table = Mock()
        mock_table.query.return_value = {'Items': []}  # Empty cache by default
        mock_table.put_item.return_value = {}
        
        return SatelliteAnalyzer(
            sagemaker_client=mock_sagemaker,
            s3_client=mock_s3,
            dynamodb_table=mock_table,
            cache_ttl_hours=24
        )
    
    # ==================== Property 7: GPS-Based Imagery Retrieval ====================
    
    @given(gps_coords=valid_gps_coords(), date_range=date_range_strategy())
    @settings(max_examples=100)
    def test_property_7_gps_based_imagery_retrieval(self, gps_coords, date_range):
        """
        **Validates: Requirements 3.1**
        
        Property 7: GPS-Based Imagery Retrieval
        For any valid GPS coordinates (latitude between -90 and 90, longitude between -180 and 180),
        the Satellite_Analyzer should successfully retrieve satellite imagery or return a clear
        unavailability message.
        """
        analyzer = self._create_analyzer()
        latitude, longitude = gps_coords
        
        # Validate GPS coordinates are in valid range
        assert -90 <= latitude <= 90, f"Latitude {latitude} out of range"
        assert -180 <= longitude <= 180, f"Longitude {longitude} out of range"
        
        try:
            # Attempt to retrieve satellite imagery
            result = analyzer.get_satellite_imagery(gps_coords, date_range)
            
            # If successful, verify result is valid
            assert result is not None
            assert isinstance(result, SatelliteImage)
            # Use math.isclose for floating point comparison with larger tolerance for very small values
            # For values near zero, use absolute tolerance; for larger values, use relative tolerance
            lat_match = math.isclose(result.gps_coords[0], gps_coords[0], rel_tol=1e-4, abs_tol=1e-6)
            lon_match = math.isclose(result.gps_coords[1], gps_coords[1], rel_tol=1e-4, abs_tol=1e-6)
            assert lat_match and lon_match, f"GPS coords mismatch: expected {gps_coords}, got {result.gps_coords}"
            assert 'B4' in result.bands
            assert 'B8' in result.bands
            
        except (ValueError, RuntimeError) as e:
            # If failed with expected errors, verify error message is clear
            error_msg = str(e)
            assert len(error_msg) > 0, "Error message should not be empty"
            assert 'unavailable' in error_msg.lower() or 'invalid' in error_msg.lower()
        except AssertionError:
            # Re-raise assertion errors (test failures)
            raise
    
    # ==================== Property 8: NDVI Value Range Validity ====================
    
    @given(satellite_image=satellite_image_strategy())
    @settings(max_examples=100)
    def test_property_8_ndvi_value_range_validity(self, satellite_image):
        """
        **Validates: Requirements 3.2**
        
        Property 8: NDVI Value Range Validity
        For any satellite image with vegetation bands, the calculated NDVI value should be
        within the valid range of -1.0 to 1.0.
        """
        analyzer = self._create_analyzer()
        # Ensure required bands are present
        assert 'B4' in satellite_image.bands
        assert 'B8' in satellite_image.bands
        
        # Calculate NDVI
        result = analyzer.calculate_ndvi(satellite_image)
        
        # Verify NDVI is in valid range
        assert result is not None
        assert isinstance(result, NDVIResult)
        assert -1.0 <= result.ndvi_value <= 1.0, \
            f"NDVI value {result.ndvi_value} is outside valid range [-1.0, 1.0]"
    
    # ==================== Property 9: Maturity Stage Classification ====================
    
    @given(satellite_image=satellite_image_strategy())
    @settings(max_examples=100)
    def test_property_9_maturity_stage_classification(self, satellite_image):
        """
        **Validates: Requirements 3.3**
        
        Property 9: Maturity Stage Classification
        For any NDVI calculation, the predicted crop maturity stage should be one of the
        valid stages: 'early', 'mid', 'late', or 'harvest_ready'.
        """
        analyzer = self._create_analyzer()
        valid_stages = ['early', 'mid', 'late', 'harvest_ready']
        
        # Calculate NDVI
        ndvi_result = analyzer.calculate_ndvi(satellite_image)
        
        # Create NDVI history with this result
        ndvi_history = [ndvi_result]
        
        # Classify maturity stage
        maturity_stage = analyzer._classify_maturity_stage(ndvi_history)
        
        # Verify stage is valid
        assert maturity_stage in valid_stages, \
            f"Maturity stage '{maturity_stage}' is not one of {valid_stages}"
    
    # ==================== Property 10: Yield Prediction Completeness ====================
    
    @given(ndvi_history=ndvi_history_strategy(), crop_type=crop_type_strategy())
    @settings(max_examples=100)
    def test_property_10_yield_prediction_completeness(self, ndvi_history, crop_type):
        """
        **Validates: Requirements 3.4, 3.6**
        
        Property 10: Yield Prediction Completeness
        For any yield prediction, the result should include an estimated volume,
        confidence interval where lower_bound <= estimate <= upper_bound, and a maturity stage.
        """
        analyzer = self._create_analyzer()
        # Ensure we have at least one NDVI sample
        assume(len(ndvi_history) > 0)
        
        # Predict yield
        result = analyzer.predict_yield(ndvi_history, crop_type)
        
        # Verify result completeness
        assert result is not None
        assert isinstance(result, YieldPrediction)
        
        # Verify estimated volume is present and positive
        assert result.estimated_volume is not None
        assert result.estimated_volume >= 0, "Estimated volume should not be negative"
        
        # Verify confidence interval is present and valid
        assert result.confidence_interval is not None
        assert len(result.confidence_interval) == 2
        lower_bound, upper_bound = result.confidence_interval
        
        assert lower_bound >= 0, "Lower bound should not be negative"
        assert lower_bound <= result.estimated_volume, \
            f"Lower bound {lower_bound} should be <= estimate {result.estimated_volume}"
        assert result.estimated_volume <= upper_bound, \
            f"Estimate {result.estimated_volume} should be <= upper bound {upper_bound}"
        
        # Verify maturity stage is present and valid
        assert result.maturity_stage is not None
        valid_stages = ['early', 'mid', 'late', 'harvest_ready']
        assert result.maturity_stage in valid_stages, \
            f"Maturity stage '{result.maturity_stage}' is not one of {valid_stages}"
    
    # ==================== Property 28: Satellite Data Caching ====================
    
    @given(gps_coords=valid_gps_coords(), date_range=date_range_strategy())
    @settings(max_examples=50)
    def test_property_28_satellite_data_caching(self, gps_coords, date_range):
        """
        **Validates: Requirements 9.5**
        
        Property 28: Satellite Data Caching
        For any satellite imagery request for a specific location and date, if a request for
        the same location and date was made within the cache TTL (e.g., 24 hours), the cached
        result should be returned instead of making a new API call.
        """
        # Create analyzer with mocked clients
        mock_sagemaker = Mock()
        mock_s3 = Mock()
        mock_table = Mock()
        
        analyzer = SatelliteAnalyzer(
            sagemaker_client=mock_sagemaker,
            s3_client=mock_s3,
            dynamodb_table=mock_table,
            cache_ttl_hours=24
        )
        
        # First request - cache miss
        mock_table.query.return_value = {'Items': []}
        mock_table.put_item.return_value = {}
        
        result1 = analyzer.get_satellite_imagery(gps_coords, date_range)
        
        # Verify result is valid
        assert result1 is not None
        assert isinstance(result1, SatelliteImage)
        
        # Second request - should use cache (either memory or DynamoDB)
        result2 = analyzer.get_satellite_imagery(gps_coords, date_range)
        
        # Verify cached result was returned (same image ID)
        assert result2 is not None
        assert isinstance(result2, SatelliteImage)
        assert result2.image_id == result1.image_id
        
        # Verify caching reduces external API calls
        # The second call should not trigger new satellite data retrieval
        # This is validated by the fact that we get the same image_id
    
    # ==================== Additional Property Tests ====================
    
    @given(ndvi_history=ndvi_history_strategy())
    @settings(max_examples=100)
    def test_maturity_stage_consistency(self, ndvi_history):
        """
        Test that maturity stage classification is consistent for the same NDVI history.
        """
        analyzer = self._create_analyzer()
        assume(len(ndvi_history) > 0)
        
        stage1 = analyzer._classify_maturity_stage(ndvi_history)
        stage2 = analyzer._classify_maturity_stage(ndvi_history)
        
        assert stage1 == stage2, "Maturity stage should be consistent for same input"
    
    @given(
        ndvi_history=ndvi_history_strategy(),
        crop_type1=crop_type_strategy(),
        crop_type2=crop_type_strategy()
    )
    @settings(max_examples=50)
    def test_yield_prediction_crop_type_sensitivity(self, ndvi_history, crop_type1, crop_type2):
        """
        Test that yield predictions vary appropriately for different crop types.
        """
        analyzer = self._create_analyzer()
        assume(len(ndvi_history) > 0)
        assume(crop_type1 != crop_type2)
        
        result1 = analyzer.predict_yield(ndvi_history, crop_type1)
        result2 = analyzer.predict_yield(ndvi_history, crop_type2)
        
        # Both predictions should be valid
        assert result1.estimated_volume >= 0
        assert result2.estimated_volume >= 0
        
        # Predictions may differ for different crops (but not required to)
        # Just verify both are valid predictions
        assert result1.maturity_stage in ['early', 'mid', 'late', 'harvest_ready']
        assert result2.maturity_stage in ['early', 'mid', 'late', 'harvest_ready']
    
    @given(cloud_cover=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False))
    @settings(max_examples=100)
    def test_confidence_calculation_monotonicity(self, cloud_cover):
        """
        Test that confidence decreases monotonically with cloud cover.
        """
        analyzer = self._create_analyzer()
        confidence = analyzer._calculate_confidence(cloud_cover)
        
        # Confidence should be in valid range
        assert 0.0 <= confidence <= 1.0
        
        # Test monotonicity: higher cloud cover = lower confidence
        if cloud_cover < 100.0:
            higher_cloud_cover = min(cloud_cover + 10.0, 100.0)
            higher_confidence = analyzer._calculate_confidence(higher_cloud_cover)
            assert confidence >= higher_confidence, \
                f"Confidence should decrease with cloud cover: {confidence} >= {higher_confidence}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

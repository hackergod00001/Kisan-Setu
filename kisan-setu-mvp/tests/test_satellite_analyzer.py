"""
Unit tests for Satellite Analyzer Component.

Tests cover:
- Satellite imagery retrieval
- NDVI calculation
- Yield prediction
- Maturity stage classification
- Caching functionality
- Error handling
"""

import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch
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


class TestSatelliteAnalyzer:
    """Test suite for SatelliteAnalyzer class."""
    
    @pytest.fixture
    def mock_clients(self):
        """Create mock AWS clients."""
        mock_sagemaker = Mock()
        mock_s3 = Mock()
        mock_table = Mock()
        return mock_sagemaker, mock_s3, mock_table
    
    @pytest.fixture
    def analyzer(self, mock_clients):
        """Create SatelliteAnalyzer instance with mocked clients."""
        mock_sagemaker, mock_s3, mock_table = mock_clients
        return SatelliteAnalyzer(
            sagemaker_client=mock_sagemaker,
            s3_client=mock_s3,
            dynamodb_table=mock_table,
            cache_ttl_hours=24
        )
    
    @pytest.fixture
    def sample_gps_coords(self):
        """Sample GPS coordinates (Mumbai, India)."""
        return (19.0760, 72.8777)
    
    @pytest.fixture
    def sample_date_range(self):
        """Sample date range (last 7 days)."""
        end_date = date.today()
        start_date = end_date - timedelta(days=7)
        return (start_date, end_date)
    
    @pytest.fixture
    def sample_satellite_image(self, sample_gps_coords):
        """Sample SatelliteImage object."""
        return SatelliteImage(
            image_id='S2_20240101_120000',
            gps_coords=sample_gps_coords,
            bands={
                'B4': 's3://bucket/sentinel2/S2_20240101_120000/B4.tif',
                'B8': 's3://bucket/sentinel2/S2_20240101_120000/B8.tif'
            },
            timestamp=datetime.utcnow(),
            cloud_cover=10.0,
            data_source='Sentinel-2'
        )
    
    @pytest.fixture
    def sample_ndvi_result(self, sample_gps_coords):
        """Sample NDVIResult object."""
        return NDVIResult(
            field_id='FIELD#abc123',
            gps_coords=sample_gps_coords,
            ndvi_value=0.65,
            timestamp=datetime.utcnow(),
            confidence=0.9,
            satellite_image_url='s3://bucket/sentinel2/image.tif'
        )
    
    # ==================== GPS Validation Tests ====================
    
    def test_valid_gps_coordinates(self, analyzer, sample_gps_coords, sample_date_range):
        """Test that valid GPS coordinates are accepted."""
        # Should not raise exception
        try:
            result = analyzer.get_satellite_imagery(sample_gps_coords, sample_date_range)
            assert result is not None
        except ValueError:
            pytest.fail("Valid GPS coordinates should not raise ValueError")
    
    def test_invalid_latitude_too_high(self, analyzer, sample_date_range):
        """Test that latitude > 90 raises ValueError."""
        invalid_coords = (91.0, 72.8777)
        with pytest.raises(ValueError, match="Invalid GPS coordinates"):
            analyzer.get_satellite_imagery(invalid_coords, sample_date_range)
    
    def test_invalid_latitude_too_low(self, analyzer, sample_date_range):
        """Test that latitude < -90 raises ValueError."""
        invalid_coords = (-91.0, 72.8777)
        with pytest.raises(ValueError, match="Invalid GPS coordinates"):
            analyzer.get_satellite_imagery(invalid_coords, sample_date_range)
    
    def test_invalid_longitude_too_high(self, analyzer, sample_date_range):
        """Test that longitude > 180 raises ValueError."""
        invalid_coords = (19.0760, 181.0)
        with pytest.raises(ValueError, match="Invalid GPS coordinates"):
            analyzer.get_satellite_imagery(invalid_coords, sample_date_range)
    
    def test_invalid_longitude_too_low(self, analyzer, sample_date_range):
        """Test that longitude < -180 raises ValueError."""
        invalid_coords = (19.0760, -181.0)
        with pytest.raises(ValueError, match="Invalid GPS coordinates"):
            analyzer.get_satellite_imagery(invalid_coords, sample_date_range)
    
    def test_boundary_gps_coordinates(self, analyzer, sample_date_range):
        """Test boundary GPS coordinates (±90, ±180)."""
        boundary_coords = [
            (90.0, 180.0),
            (-90.0, -180.0),
            (0.0, 0.0),
            (90.0, -180.0),
            (-90.0, 180.0)
        ]
        
        for coords in boundary_coords:
            try:
                result = analyzer.get_satellite_imagery(coords, sample_date_range)
                assert result is not None
            except ValueError:
                pytest.fail(f"Boundary coordinates {coords} should be valid")
    
    # ==================== Satellite Imagery Tests ====================
    
    def test_get_satellite_imagery_success(self, analyzer, sample_gps_coords, sample_date_range):
        """Test successful satellite imagery retrieval."""
        result = analyzer.get_satellite_imagery(sample_gps_coords, sample_date_range)
        
        assert result is not None
        assert isinstance(result, SatelliteImage)
        assert result.gps_coords == sample_gps_coords
        assert 'B4' in result.bands
        assert 'B8' in result.bands
        assert result.data_source == 'Sentinel-2'
        assert 0 <= result.cloud_cover <= 100
    
    def test_get_satellite_imagery_returns_required_bands(self, analyzer, sample_gps_coords, sample_date_range):
        """Test that retrieved imagery contains required bands for NDVI."""
        result = analyzer.get_satellite_imagery(sample_gps_coords, sample_date_range)
        
        assert 'B4' in result.bands, "Missing B4 (Red) band"
        assert 'B8' in result.bands, "Missing B8 (NIR) band"
    
    def test_field_id_generation_consistency(self, analyzer):
        """Test that same GPS coordinates generate same field ID."""
        coords = (19.0760, 72.8777)
        field_id_1 = analyzer._generate_field_id(coords)
        field_id_2 = analyzer._generate_field_id(coords)
        
        assert field_id_1 == field_id_2
        assert field_id_1.startswith('FIELD#')
    
    def test_field_id_generation_uniqueness(self, analyzer):
        """Test that different GPS coordinates generate different field IDs."""
        coords_1 = (19.0760, 72.8777)
        coords_2 = (19.0761, 72.8778)
        
        field_id_1 = analyzer._generate_field_id(coords_1)
        field_id_2 = analyzer._generate_field_id(coords_2)
        
        assert field_id_1 != field_id_2
    
    # ==================== NDVI Calculation Tests ====================
    
    def test_calculate_ndvi_success(self, analyzer, sample_satellite_image):
        """Test successful NDVI calculation."""
        result = analyzer.calculate_ndvi(sample_satellite_image)
        
        assert result is not None
        assert isinstance(result, NDVIResult)
        assert -1.0 <= result.ndvi_value <= 1.0
        assert 0.0 <= result.confidence <= 1.0
        assert result.gps_coords == sample_satellite_image.gps_coords
    
    def test_calculate_ndvi_value_range(self, analyzer, sample_satellite_image):
        """Test that NDVI value is always within valid range [-1.0, 1.0]."""
        result = analyzer.calculate_ndvi(sample_satellite_image)
        
        assert result.ndvi_value >= -1.0, "NDVI value below minimum"
        assert result.ndvi_value <= 1.0, "NDVI value above maximum"
    
    def test_calculate_ndvi_missing_b4_band(self, analyzer, sample_satellite_image):
        """Test that missing B4 band raises ValueError."""
        sample_satellite_image.bands = {'B8': 's3://bucket/B8.tif'}
        
        with pytest.raises(ValueError, match="Missing required bands"):
            analyzer.calculate_ndvi(sample_satellite_image)
    
    def test_calculate_ndvi_missing_b8_band(self, analyzer, sample_satellite_image):
        """Test that missing B8 band raises ValueError."""
        sample_satellite_image.bands = {'B4': 's3://bucket/B4.tif'}
        
        with pytest.raises(ValueError, match="Missing required bands"):
            analyzer.calculate_ndvi(sample_satellite_image)
    
    def test_calculate_ndvi_confidence_based_on_cloud_cover(self, analyzer, sample_gps_coords):
        """Test that confidence decreases with cloud cover."""
        # Low cloud cover
        image_low_cloud = SatelliteImage(
            image_id='S2_1',
            gps_coords=sample_gps_coords,
            bands={'B4': 's3://b/B4.tif', 'B8': 's3://b/B8.tif'},
            timestamp=datetime.utcnow(),
            cloud_cover=10.0,
            data_source='Sentinel-2'
        )
        
        # High cloud cover
        image_high_cloud = SatelliteImage(
            image_id='S2_2',
            gps_coords=sample_gps_coords,
            bands={'B4': 's3://b/B4.tif', 'B8': 's3://b/B8.tif'},
            timestamp=datetime.utcnow(),
            cloud_cover=80.0,
            data_source='Sentinel-2'
        )
        
        result_low = analyzer.calculate_ndvi(image_low_cloud)
        result_high = analyzer.calculate_ndvi(image_high_cloud)
        
        assert result_low.confidence > result_high.confidence
    
    # ==================== Maturity Stage Classification Tests ====================
    
    def test_classify_maturity_stage_early(self, analyzer, sample_gps_coords):
        """Test early maturity stage classification (NDVI < 0.4)."""
        ndvi_history = [
            NDVIResult(
                field_id='FIELD#test',
                gps_coords=sample_gps_coords,
                ndvi_value=0.35,
                timestamp=datetime.utcnow(),
                confidence=0.9,
                satellite_image_url='s3://bucket/image.tif'
            )
        ]
        
        stage = analyzer._classify_maturity_stage(ndvi_history)
        assert stage == 'early'
    
    def test_classify_maturity_stage_mid(self, analyzer, sample_gps_coords):
        """Test mid maturity stage classification (NDVI 0.4-0.6)."""
        ndvi_history = [
            NDVIResult(
                field_id='FIELD#test',
                gps_coords=sample_gps_coords,
                ndvi_value=0.5,
                timestamp=datetime.utcnow(),
                confidence=0.9,
                satellite_image_url='s3://bucket/image.tif'
            )
        ]
        
        stage = analyzer._classify_maturity_stage(ndvi_history)
        assert stage == 'mid'
    
    def test_classify_maturity_stage_late(self, analyzer, sample_gps_coords):
        """Test late maturity stage classification (NDVI 0.6-0.8)."""
        ndvi_history = [
            NDVIResult(
                field_id='FIELD#test',
                gps_coords=sample_gps_coords,
                ndvi_value=0.7,
                timestamp=datetime.utcnow() - timedelta(days=2),
                confidence=0.9,
                satellite_image_url='s3://bucket/image1.tif'
            ),
            NDVIResult(
                field_id='FIELD#test',
                gps_coords=sample_gps_coords,
                ndvi_value=0.68,
                timestamp=datetime.utcnow(),
                confidence=0.9,
                satellite_image_url='s3://bucket/image2.tif'
            )
        ]
        
        stage = analyzer._classify_maturity_stage(ndvi_history)
        assert stage == 'late'
    
    def test_classify_maturity_stage_harvest_ready(self, analyzer, sample_gps_coords):
        """Test harvest_ready maturity stage classification (NDVI declining rapidly)."""
        ndvi_history = [
            NDVIResult(
                field_id='FIELD#test',
                gps_coords=sample_gps_coords,
                ndvi_value=0.25,
                timestamp=datetime.utcnow(),
                confidence=0.9,
                satellite_image_url='s3://bucket/image.tif'
            )
        ]
        
        stage = analyzer._classify_maturity_stage(ndvi_history)
        assert stage == 'harvest_ready'
    
    def test_classify_maturity_stage_valid_stages(self, analyzer, sample_gps_coords):
        """Test that maturity stage is always one of the valid stages."""
        valid_stages = ['early', 'mid', 'late', 'harvest_ready']
        
        # Test with various NDVI values
        for ndvi_value in [0.2, 0.35, 0.5, 0.65, 0.8]:
            ndvi_history = [
                NDVIResult(
                    field_id='FIELD#test',
                    gps_coords=sample_gps_coords,
                    ndvi_value=ndvi_value,
                    timestamp=datetime.utcnow(),
                    confidence=0.9,
                    satellite_image_url='s3://bucket/image.tif'
                )
            ]
            
            stage = analyzer._classify_maturity_stage(ndvi_history)
            assert stage in valid_stages
    
    # ==================== Yield Prediction Tests ====================
    
    def test_predict_yield_success(self, analyzer, sample_ndvi_result):
        """Test successful yield prediction."""
        ndvi_history = [sample_ndvi_result]
        crop_type = 'onion'
        
        result = analyzer.predict_yield(ndvi_history, crop_type)
        
        assert result is not None
        assert isinstance(result, YieldPrediction)
        assert result.estimated_volume > 0
        assert result.maturity_stage in ['early', 'mid', 'late', 'harvest_ready']
    
    def test_predict_yield_empty_history(self, analyzer):
        """Test that empty NDVI history raises ValueError."""
        with pytest.raises(ValueError, match="Cannot predict yield without NDVI history"):
            analyzer.predict_yield([], 'onion')
    
    def test_predict_yield_confidence_interval(self, analyzer, sample_ndvi_result):
        """Test that confidence interval bounds are correct."""
        ndvi_history = [sample_ndvi_result]
        crop_type = 'onion'
        
        result = analyzer.predict_yield(ndvi_history, crop_type)
        
        lower, upper = result.confidence_interval
        assert lower <= result.estimated_volume <= upper
        assert lower >= 0, "Lower bound should not be negative"
    
    def test_predict_yield_different_crops(self, analyzer, sample_ndvi_result):
        """Test yield prediction for different crop types."""
        ndvi_history = [sample_ndvi_result]
        crops = ['onion', 'wheat', 'rice', 'cotton']
        
        for crop in crops:
            result = analyzer.predict_yield(ndvi_history, crop)
            assert result.estimated_volume > 0
            assert result.maturity_stage in ['early', 'mid', 'late', 'harvest_ready']
    
    def test_predict_yield_includes_maturity_stage(self, analyzer, sample_ndvi_result):
        """Test that yield prediction includes maturity stage."""
        ndvi_history = [sample_ndvi_result]
        crop_type = 'onion'
        
        result = analyzer.predict_yield(ndvi_history, crop_type)
        
        assert result.maturity_stage is not None
        assert result.maturity_stage in ['early', 'mid', 'late', 'harvest_ready']
    
    # ==================== Caching Tests ====================
    
    def test_cache_imagery_stores_in_dynamodb(self, analyzer, sample_satellite_image, mock_clients):
        """Test that satellite imagery is cached in DynamoDB."""
        _, _, mock_table = mock_clients
        
        analyzer._cache_imagery(sample_satellite_image)
        
        # Verify put_item was called
        assert mock_table.put_item.called
        call_args = mock_table.put_item.call_args
        item = call_args[1]['Item']
        
        assert item['entity_type'] == 'SatelliteImage'
        assert item['image_id'] == sample_satellite_image.image_id
        assert 'PK' in item
        assert 'SK' in item
        assert item['SK'].startswith('SATELLITE#')
    
    def test_get_cached_imagery_returns_none_when_empty(self, analyzer, mock_clients):
        """Test that get_cached_imagery returns None when cache is empty."""
        _, _, mock_table = mock_clients
        mock_table.query.return_value = {'Items': []}
        
        result = analyzer._get_cached_imagery('FIELD#test', date.today(), date.today())
        
        assert result is None
    
    def test_get_cached_imagery_returns_none_when_expired(self, analyzer, mock_clients):
        """Test that get_cached_imagery returns None when cache is expired."""
        _, _, mock_table = mock_clients
        
        # Mock expired cache entry (25 hours old, TTL is 24 hours)
        expired_timestamp = datetime.utcnow() - timedelta(hours=25)
        mock_table.query.return_value = {
            'Items': [{
                'image_id': 'S2_old',
                'latitude': Decimal('19.0760'),
                'longitude': Decimal('72.8777'),
                'bands': {'B4': 's3://b/B4.tif', 'B8': 's3://b/B8.tif'},
                'timestamp': expired_timestamp.isoformat(),
                'cloud_cover': Decimal('10.0'),
                'data_source': 'Sentinel-2'
            }]
        }
        
        result = analyzer._get_cached_imagery('FIELD#test', date.today(), date.today())
        
        assert result is None
    
    def test_get_cached_imagery_returns_valid_cache(self, analyzer, mock_clients):
        """Test that get_cached_imagery returns valid cached imagery."""
        _, _, mock_table = mock_clients
        
        # Mock valid cache entry (1 hour old)
        recent_timestamp = datetime.utcnow() - timedelta(hours=1)
        mock_table.query.return_value = {
            'Items': [{
                'image_id': 'S2_recent',
                'latitude': Decimal('19.0760'),
                'longitude': Decimal('72.8777'),
                'bands': {'B4': 's3://b/B4.tif', 'B8': 's3://b/B8.tif'},
                'timestamp': recent_timestamp.isoformat(),
                'cloud_cover': Decimal('10.0'),
                'data_source': 'Sentinel-2'
            }]
        }
        
        result = analyzer._get_cached_imagery('FIELD#test', date.today(), date.today())
        
        assert result is not None
        assert isinstance(result, SatelliteImage)
        assert result.image_id == 'S2_recent'
    
    # ==================== Helper Method Tests ====================
    
    def test_create_bounding_box(self, analyzer):
        """Test bounding box creation around GPS coordinates."""
        latitude, longitude = 19.0760, 72.8777
        buffer_km = 0.5
        
        bbox = analyzer._create_bounding_box(latitude, longitude, buffer_km)
        
        assert 'min_lat' in bbox
        assert 'max_lat' in bbox
        assert 'min_lon' in bbox
        assert 'max_lon' in bbox
        assert bbox['min_lat'] < latitude < bbox['max_lat']
        assert bbox['min_lon'] < longitude < bbox['max_lon']
    
    def test_calculate_confidence_zero_cloud_cover(self, analyzer):
        """Test confidence calculation with 0% cloud cover."""
        confidence = analyzer._calculate_confidence(0.0)
        assert confidence == 1.0
    
    def test_calculate_confidence_full_cloud_cover(self, analyzer):
        """Test confidence calculation with 100% cloud cover."""
        confidence = analyzer._calculate_confidence(100.0)
        assert confidence == 0.0
    
    def test_calculate_confidence_partial_cloud_cover(self, analyzer):
        """Test confidence calculation with partial cloud cover."""
        confidence_50 = analyzer._calculate_confidence(50.0)
        assert 0.0 < confidence_50 < 1.0
        assert abs(confidence_50 - 0.5) < 0.01
    
    # ==================== Edge Cases ====================
    
    def test_single_ndvi_sample_prediction(self, analyzer, sample_ndvi_result):
        """Test yield prediction with single NDVI sample."""
        ndvi_history = [sample_ndvi_result]
        
        result = analyzer.predict_yield(ndvi_history, 'onion')
        
        assert result is not None
        assert result.estimated_volume > 0
    
    def test_multiple_ndvi_samples_prediction(self, analyzer, sample_gps_coords):
        """Test yield prediction with multiple NDVI samples."""
        ndvi_history = [
            NDVIResult(
                field_id='FIELD#test',
                gps_coords=sample_gps_coords,
                ndvi_value=0.4,
                timestamp=datetime.utcnow() - timedelta(days=14),
                confidence=0.9,
                satellite_image_url='s3://bucket/image1.tif'
            ),
            NDVIResult(
                field_id='FIELD#test',
                gps_coords=sample_gps_coords,
                ndvi_value=0.6,
                timestamp=datetime.utcnow() - timedelta(days=7),
                confidence=0.9,
                satellite_image_url='s3://bucket/image2.tif'
            ),
            NDVIResult(
                field_id='FIELD#test',
                gps_coords=sample_gps_coords,
                ndvi_value=0.7,
                timestamp=datetime.utcnow(),
                confidence=0.9,
                satellite_image_url='s3://bucket/image3.tif'
            )
        ]
        
        result = analyzer.predict_yield(ndvi_history, 'onion')
        
        assert result is not None
        assert result.estimated_volume > 0
    
    def test_unknown_crop_type_uses_default(self, analyzer, sample_ndvi_result):
        """Test that unknown crop type uses default yield factor."""
        ndvi_history = [sample_ndvi_result]
        
        result = analyzer.predict_yield(ndvi_history, 'unknown_crop')
        
        assert result is not None
        assert result.estimated_volume > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

"""
Unit tests for Satellite Analyzer Component.

Tests cover:
- Satellite imagery retrieval (SageMaker Geospatial API)
- NDVI calculation (rasterio COG reading)
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

# Check if rasterio is available (required for NDVI computation tests)
try:
    import rasterio
    RASTERIO_AVAILABLE = True
except ImportError:
    RASTERIO_AVAILABLE = False

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
        """Sample SatelliteImage object with real-format COG URLs."""
        return SatelliteImage(
            image_id='S2B_43QCC_20260309_0_L2A',
            gps_coords=sample_gps_coords,
            bands={
                'B4': 'https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/43/Q/CC/2026/3/S2B_43QCC_20260309_0_L2A/B04.tif',
                'B8': 'https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/43/Q/CC/2026/3/S2B_43QCC_20260309_0_L2A/B08.tif',
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

    @pytest.fixture
    def mock_sagemaker_response(self):
        """Mock SageMaker Geospatial search_raster_data_collection response."""
        return {
            'ApproximateResultCount': 1,
            'Items': [{
                'Assets': {
                    'red': {'Href': 'https://sentinel-cogs.s3.us-west-2.amazonaws.com/B04.tif'},
                    'nir': {'Href': 'https://sentinel-cogs.s3.us-west-2.amazonaws.com/B08.tif'},
                    'green': {'Href': 'https://sentinel-cogs.s3.us-west-2.amazonaws.com/B03.tif'},
                    'blue': {'Href': 'https://sentinel-cogs.s3.us-west-2.amazonaws.com/B02.tif'},
                },
                'DateTime': '2026-03-09T11:13:25.356000+05:30',
                'Id': 'S2B_43QCC_20260309_0_L2A',
                'Properties': {'EoCloudCover': 0.003671, 'Platform': 'sentinel-2b'},
                'Geometry': {
                    'Coordinates': [[[73.52, 20.79], [73.29, 19.80], [74.14, 19.81], [74.13, 20.80], [73.52, 20.79]]],
                    'Type': 'Polygon'
                }
            }]
        }

    # ==================== GPS Validation Tests ====================

    def test_valid_gps_coordinates(self, analyzer, sample_gps_coords, sample_date_range, mock_clients, mock_sagemaker_response):
        """Test that valid GPS coordinates are accepted."""
        mock_sagemaker, _, mock_table = mock_clients
        mock_sagemaker.search_raster_data_collection.return_value = mock_sagemaker_response
        mock_table.query.return_value = {'Items': []}

        result = analyzer.get_satellite_imagery(sample_gps_coords, sample_date_range)
        assert result is not None
        assert isinstance(result, SatelliteImage)

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

    def test_boundary_gps_coordinates(self, analyzer, sample_date_range, mock_clients, mock_sagemaker_response):
        """Test boundary GPS coordinates (±90, ±180)."""
        mock_sagemaker, _, mock_table = mock_clients
        mock_sagemaker.search_raster_data_collection.return_value = mock_sagemaker_response
        mock_table.query.return_value = {'Items': []}

        boundary_coords = [
            (90.0, 180.0),
            (-90.0, -180.0),
            (0.0, 0.0),
        ]

        for coords in boundary_coords:
            result = analyzer.get_satellite_imagery(coords, sample_date_range)
            assert result is not None

    # ==================== Satellite Imagery Tests ====================

    def test_get_satellite_imagery_success(self, analyzer, sample_gps_coords, sample_date_range, mock_clients, mock_sagemaker_response):
        """Test successful satellite imagery retrieval via SageMaker Geospatial."""
        mock_sagemaker, _, mock_table = mock_clients
        mock_sagemaker.search_raster_data_collection.return_value = mock_sagemaker_response
        mock_table.query.return_value = {'Items': []}

        result = analyzer.get_satellite_imagery(sample_gps_coords, sample_date_range)

        assert result is not None
        assert isinstance(result, SatelliteImage)
        assert result.gps_coords == sample_gps_coords
        assert 'B4' in result.bands
        assert 'B8' in result.bands
        assert result.data_source == 'Sentinel-2'
        assert result.cloud_cover < 1  # Our mock has 0.003%

    def test_get_satellite_imagery_no_results(self, analyzer, mock_clients):
        """Test that no results raises an exception."""
        mock_sagemaker, _, mock_table = mock_clients
        mock_sagemaker.search_raster_data_collection.return_value = {'Items': []}
        mock_table.query.return_value = {'Items': []}

        # Use unique coordinates to avoid cache hits from other tests
        unique_coords = (10.1234, 76.5678)
        end_date = date.today()
        start_date = end_date - timedelta(days=3)

        with pytest.raises(Exception):
            analyzer.get_satellite_imagery(unique_coords, (start_date, end_date))

    def test_get_satellite_imagery_returns_required_bands(self, analyzer, sample_gps_coords, sample_date_range, mock_clients, mock_sagemaker_response):
        """Test that retrieved imagery contains required bands for NDVI."""
        mock_sagemaker, _, mock_table = mock_clients
        mock_sagemaker.search_raster_data_collection.return_value = mock_sagemaker_response
        mock_table.query.return_value = {'Items': []}

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

    @patch.object(SatelliteAnalyzer, '_compute_ndvi_from_cog', return_value=0.55)
    def test_calculate_ndvi_success(self, mock_cog, analyzer, sample_satellite_image):
        """Test successful NDVI calculation."""
        result = analyzer.calculate_ndvi(sample_satellite_image)

        assert result is not None
        assert isinstance(result, NDVIResult)
        assert -1.0 <= result.ndvi_value <= 1.0
        assert result.ndvi_value == 0.55
        assert 0.0 <= result.confidence <= 1.0
        assert result.gps_coords == sample_satellite_image.gps_coords

    @patch.object(SatelliteAnalyzer, '_compute_ndvi_from_cog', return_value=0.72)
    def test_calculate_ndvi_value_range(self, mock_cog, analyzer, sample_satellite_image):
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

    @patch.object(SatelliteAnalyzer, '_compute_ndvi_from_cog', return_value=0.6)
    def test_calculate_ndvi_confidence_based_on_cloud_cover(self, mock_cog, analyzer, sample_gps_coords):
        """Test that confidence decreases with cloud cover."""
        image_low_cloud = SatelliteImage(
            image_id='S2_1', gps_coords=sample_gps_coords,
            bands={'B4': 'https://example.com/B4.tif', 'B8': 'https://example.com/B8.tif'},
            timestamp=datetime.utcnow(), cloud_cover=10.0, data_source='Sentinel-2'
        )
        image_high_cloud = SatelliteImage(
            image_id='S2_2', gps_coords=sample_gps_coords,
            bands={'B4': 'https://example.com/B4.tif', 'B8': 'https://example.com/B8.tif'},
            timestamp=datetime.utcnow(), cloud_cover=80.0, data_source='Sentinel-2'
        )

        result_low = analyzer.calculate_ndvi(image_low_cloud)
        result_high = analyzer.calculate_ndvi(image_high_cloud)

        assert result_low.confidence > result_high.confidence

    # ==================== Maturity Stage Classification Tests ====================

    def test_classify_maturity_stage_early(self, analyzer, sample_gps_coords):
        """Test early maturity stage classification (NDVI < 0.4)."""
        ndvi_history = [
            NDVIResult(
                field_id='FIELD#test', gps_coords=sample_gps_coords,
                ndvi_value=0.35, timestamp=datetime.utcnow(),
                confidence=0.9, satellite_image_url='s3://bucket/image.tif'
            )
        ]

        stage = analyzer._classify_maturity_stage(ndvi_history)
        assert stage == 'early'

    def test_classify_maturity_stage_mid(self, analyzer, sample_gps_coords):
        """Test mid maturity stage classification (NDVI 0.4-0.6)."""
        ndvi_history = [
            NDVIResult(
                field_id='FIELD#test', gps_coords=sample_gps_coords,
                ndvi_value=0.5, timestamp=datetime.utcnow(),
                confidence=0.9, satellite_image_url='s3://bucket/image.tif'
            )
        ]

        stage = analyzer._classify_maturity_stage(ndvi_history)
        assert stage == 'mid'

    def test_classify_maturity_stage_late(self, analyzer, sample_gps_coords):
        """Test late maturity stage classification (NDVI 0.6-0.8)."""
        ndvi_history = [
            NDVIResult(
                field_id='FIELD#test', gps_coords=sample_gps_coords,
                ndvi_value=0.7, timestamp=datetime.utcnow() - timedelta(days=2),
                confidence=0.9, satellite_image_url='s3://bucket/image1.tif'
            ),
            NDVIResult(
                field_id='FIELD#test', gps_coords=sample_gps_coords,
                ndvi_value=0.68, timestamp=datetime.utcnow(),
                confidence=0.9, satellite_image_url='s3://bucket/image2.tif'
            )
        ]

        stage = analyzer._classify_maturity_stage(ndvi_history)
        assert stage == 'late'

    def test_classify_maturity_stage_harvest_ready(self, analyzer, sample_gps_coords):
        """Test harvest_ready maturity stage classification (NDVI declining rapidly)."""
        ndvi_history = [
            NDVIResult(
                field_id='FIELD#test', gps_coords=sample_gps_coords,
                ndvi_value=0.25, timestamp=datetime.utcnow(),
                confidence=0.9, satellite_image_url='s3://bucket/image.tif'
            )
        ]

        stage = analyzer._classify_maturity_stage(ndvi_history)
        assert stage == 'harvest_ready'

    def test_classify_maturity_stage_valid_stages(self, analyzer, sample_gps_coords):
        """Test that maturity stage is always one of the valid stages."""
        valid_stages = ['early', 'mid', 'late', 'harvest_ready']

        for ndvi_value in [0.2, 0.35, 0.5, 0.65, 0.8]:
            ndvi_history = [
                NDVIResult(
                    field_id='FIELD#test', gps_coords=sample_gps_coords,
                    ndvi_value=ndvi_value, timestamp=datetime.utcnow(),
                    confidence=0.9, satellite_image_url='s3://bucket/image.tif'
                )
            ]

            stage = analyzer._classify_maturity_stage(ndvi_history)
            assert stage in valid_stages

    # ==================== Yield Prediction Tests ====================

    def test_predict_yield_success(self, analyzer, sample_ndvi_result):
        """Test successful yield prediction."""
        ndvi_history = [sample_ndvi_result]

        result = analyzer.predict_yield(ndvi_history, 'onion')

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

        result = analyzer.predict_yield(ndvi_history, 'onion')

        lower, upper = result.confidence_interval
        assert lower <= result.estimated_volume <= upper
        assert lower >= 0, "Lower bound should not be negative"

    def test_predict_yield_different_crops(self, analyzer, sample_ndvi_result):
        """Test yield prediction for different crop types."""
        ndvi_history = [sample_ndvi_result]
        crops = ['onion', 'wheat', 'rice', 'cotton', 'sugarcane', 'maize', 'groundnut']

        for crop in crops:
            result = analyzer.predict_yield(ndvi_history, crop)
            assert result.estimated_volume > 0
            assert result.maturity_stage in ['early', 'mid', 'late', 'harvest_ready']

    def test_predict_yield_includes_maturity_stage(self, analyzer, sample_ndvi_result):
        """Test that yield prediction includes maturity stage."""
        ndvi_history = [sample_ndvi_result]

        result = analyzer.predict_yield(ndvi_history, 'onion')

        assert result.maturity_stage is not None
        assert result.maturity_stage in ['early', 'mid', 'late', 'harvest_ready']

    # ==================== Caching Tests ====================

    def test_cache_imagery_stores_in_dynamodb(self, analyzer, sample_satellite_image, mock_clients):
        """Test that satellite imagery is cached in DynamoDB."""
        _, _, mock_table = mock_clients

        analyzer._cache_imagery(sample_satellite_image)

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

        expired_timestamp = datetime.utcnow() - timedelta(hours=25)
        mock_table.query.return_value = {
            'Items': [{
                'image_id': 'S2_old',
                'latitude': Decimal('19.0760'),
                'longitude': Decimal('72.8777'),
                'bands': {'B4': 'https://example.com/B4.tif', 'B8': 'https://example.com/B8.tif'},
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

        recent_timestamp = datetime.utcnow() - timedelta(hours=1)
        mock_table.query.return_value = {
            'Items': [{
                'image_id': 'S2_recent',
                'latitude': Decimal('19.0760'),
                'longitude': Decimal('72.8777'),
                'bands': {'B4': 'https://example.com/B4.tif', 'B8': 'https://example.com/B8.tif'},
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
        """Test bounding box creation returns GeoJSON polygon coordinates."""
        latitude, longitude = 19.0760, 72.8777
        buffer_km = 0.5

        bbox = analyzer._create_bounding_box(latitude, longitude, buffer_km)

        # Should be a list of coordinate rings (GeoJSON polygon format)
        assert isinstance(bbox, list)
        assert len(bbox) == 1  # One ring
        ring = bbox[0]
        assert len(ring) == 5  # 4 corners + closing point
        assert ring[0] == ring[-1]  # Ring is closed

        # All coordinates should be [lon, lat] pairs
        for point in ring:
            assert len(point) == 2

        # Center point should be inside the bounding box
        min_lon = min(p[0] for p in ring)
        max_lon = max(p[0] for p in ring)
        min_lat = min(p[1] for p in ring)
        max_lat = max(p[1] for p in ring)
        assert min_lat < latitude < max_lat
        assert min_lon < longitude < max_lon

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
                field_id='FIELD#test', gps_coords=sample_gps_coords,
                ndvi_value=0.4, timestamp=datetime.utcnow() - timedelta(days=14),
                confidence=0.9, satellite_image_url='s3://bucket/image1.tif'
            ),
            NDVIResult(
                field_id='FIELD#test', gps_coords=sample_gps_coords,
                ndvi_value=0.6, timestamp=datetime.utcnow() - timedelta(days=7),
                confidence=0.9, satellite_image_url='s3://bucket/image2.tif'
            ),
            NDVIResult(
                field_id='FIELD#test', gps_coords=sample_gps_coords,
                ndvi_value=0.7, timestamp=datetime.utcnow(),
                confidence=0.9, satellite_image_url='s3://bucket/image3.tif'
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

    def test_new_crop_types_have_yield_factors(self, analyzer, sample_ndvi_result):
        """Test that all new crop types have yield factors."""
        ndvi_history = [sample_ndvi_result]
        new_crops = ['sugarcane', 'soybean', 'grape', 'jowar', 'bajra',
                     'tur', 'groundnut', 'mustard', 'maize', 'chana',
                     'chilli', 'turmeric']

        for crop in new_crops:
            result = analyzer.predict_yield(ndvi_history, crop)
            assert result.estimated_volume > 0, f"No yield factor for {crop}"

    # ==================== NDVI Heatmap Tests ====================

    @pytest.mark.skipif(
        not RASTERIO_AVAILABLE,
        reason="rasterio library required for NDVI computation (available in Lambda Layer only)"
    )
    def test_compute_ndvi_array_returns_2d_array(self, analyzer):
        """Test that _compute_ndvi_array returns a 2D numpy array of correct shape."""
        import numpy as np

        # Mock rasterio and pyproj
        mock_red_ds = MagicMock()
        mock_red_ds.crs = 'EPSG:32643'
        mock_red_ds.height = 10000
        mock_red_ds.width = 10000
        mock_red_ds.transform = MagicMock()
        mock_red_ds.read.return_value = np.full((100, 100), 1000, dtype=np.float64)
        mock_red_ds.__enter__ = Mock(return_value=mock_red_ds)
        mock_red_ds.__exit__ = Mock(return_value=False)

        mock_nir_ds = MagicMock()
        mock_nir_ds.read.return_value = np.full((100, 100), 3000, dtype=np.float64)
        mock_nir_ds.__enter__ = Mock(return_value=mock_nir_ds)
        mock_nir_ds.__exit__ = Mock(return_value=False)

        with patch('rasterio.open', side_effect=[mock_red_ds, mock_nir_ds]), \
             patch('pyproj.Transformer.from_crs') as mock_transformer, \
             patch('rasterio.transform.rowcol', return_value=(5000, 5000)):
            mock_t = Mock()
            mock_t.transform.return_value = (500000, 2100000)
            mock_transformer.return_value = mock_t

            result = analyzer._compute_ndvi_array(
                'https://example.com/B04.tif',
                'https://example.com/B08.tif',
                (19.0760, 72.8777),
                window_size=100,
            )

        assert isinstance(result, np.ndarray)
        assert result.shape == (100, 100)
        # NDVI = (3000-1000)/(3000+1000) = 0.5
        expected_ndvi = 0.5
        assert abs(result[50, 50] - expected_ndvi) < 0.01

    def test_render_ndvi_heatmap_produces_valid_png(self, analyzer):
        """Test that rendered heatmap is a valid PNG image."""
        import numpy as np

        ndvi_array = np.random.uniform(0.2, 0.8, (100, 100))
        png_bytes = analyzer._render_ndvi_heatmap(
            ndvi_array, crop_type='Onion', gps_coords=(19.0760, 72.8777)
        )

        # PNG magic bytes
        assert png_bytes[:8] == b'\x89PNG\r\n\x1a\n', "Not a valid PNG"
        assert len(png_bytes) > 1000, "PNG too small — likely empty"

    def test_render_ndvi_heatmap_different_ndvi_ranges(self, analyzer):
        """Test heatmap renders correctly for various NDVI ranges."""
        import numpy as np

        # All stressed (low NDVI)
        low_ndvi = np.full((50, 50), 0.1)
        png_low = analyzer._render_ndvi_heatmap(low_ndvi, crop_type='Wheat')
        assert png_low[:8] == b'\x89PNG\r\n\x1a\n'

        # All healthy (high NDVI)
        high_ndvi = np.full((50, 50), 0.85)
        png_high = analyzer._render_ndvi_heatmap(high_ndvi, crop_type='Wheat')
        assert png_high[:8] == b'\x89PNG\r\n\x1a\n'

        # Images should be different (different colors)
        assert png_low != png_high

    def test_upload_heatmap_to_s3(self, analyzer, mock_clients):
        """Test heatmap upload to S3."""
        _, mock_s3, _ = mock_clients
        image_bytes = b'\x89PNG\r\n\x1a\nfake_png_data'

        s3_key = analyzer._upload_heatmap_to_s3(image_bytes, 'FIELD#abc123')

        assert mock_s3.put_object.called
        call_kwargs = mock_s3.put_object.call_args[1]
        assert call_kwargs['ContentType'] == 'image/png'
        assert call_kwargs['Body'] == image_bytes
        assert s3_key.startswith('ndvi-heatmaps/FIELD#abc123/')
        assert s3_key.endswith('.png')

    def test_generate_presigned_url(self, analyzer, mock_clients):
        """Test presigned URL generation."""
        _, mock_s3, _ = mock_clients
        mock_s3.generate_presigned_url.return_value = 'https://s3.amazonaws.com/bucket/key?signature=abc'

        url = analyzer._generate_presigned_url('ndvi-heatmaps/FIELD#abc/20260311.png')

        assert url.startswith('https://')
        mock_s3.generate_presigned_url.assert_called_once()
        call_args = mock_s3.generate_presigned_url.call_args
        assert call_args[1]['ExpiresIn'] == 3600

    def test_generate_presigned_url_custom_expiry(self, analyzer, mock_clients):
        """Test presigned URL with custom expiry."""
        _, mock_s3, _ = mock_clients
        mock_s3.generate_presigned_url.return_value = 'https://s3.example.com/image.png'

        analyzer._generate_presigned_url('key.png', expires_in=7200)

        call_args = mock_s3.generate_presigned_url.call_args
        assert call_args[1]['ExpiresIn'] == 7200


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

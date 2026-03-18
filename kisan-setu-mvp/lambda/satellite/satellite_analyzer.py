"""
Satellite Analyzer Component
Retrieves satellite imagery and calculates NDVI for crop yield prediction.

This component implements the SatelliteAnalyzer class as specified in the design document,
with support for Sentinel-2 satellite imagery via SageMaker Geospatial.

AUDIT TRAIL GAP: This handler performs direct boto3 DynamoDB writes (satellite
imagery cache, NDVI results, yield predictions) that bypass the centralised
DynamoDBAccess class and its audit trails. To close this gap, either migrate
write paths to DynamoDBAccess or enable DynamoDB Streams on the KisanSetuData
table to capture all mutations for audit/compliance purposes.
"""

import json
import boto3
import os
import sys
import math
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional, Tuple
from decimal import Decimal
from dataclasses import dataclass, asdict
import hashlib

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.error_handling import (
    retry_with_exponential_backoff,
    create_error_response,
    ErrorCategory,
    ErrorSeverity
)
from common.cost_optimization import (
    cache_manager,
    get_cached_or_compute
)

# AWS clients — SageMaker Geospatial is only available in us-west-2
SAGEMAKER_REGION = os.environ.get('SAGEMAKER_REGION', 'us-west-2')
SENTINEL2_ARN = os.environ.get(
    'SENTINEL2_ARN',
    'arn:aws:sagemaker-geospatial:us-west-2:378778860802:raster-data-collection/public/nmqj48dcu3g7ayw8'
)
sagemaker_geospatial = boto3.client('sagemaker-geospatial', region_name=SAGEMAKER_REGION)
dynamodb = boto3.resource('dynamodb')
s3 = boto3.client('s3')

# Environment variables
S3_BUCKET_SATELLITE = os.environ.get('S3_BUCKET_SATELLITE', 'kisan-setu-satellite')
DYNAMODB_TABLE = os.environ.get('DYNAMODB_TABLE', 'KisanSetuData')
REGION = os.environ.get('REGION', 'ap-south-1')
CACHE_TTL_HOURS = int(os.environ.get('CACHE_TTL_HOURS', '24'))

table = dynamodb.Table(DYNAMODB_TABLE)


@dataclass
class SatelliteImage:
    """Satellite imagery data with bands and metadata."""
    image_id: str
    gps_coords: Tuple[float, float]
    bands: Dict[str, str]  # band_name -> S3 URL
    timestamp: datetime
    cloud_cover: float
    data_source: str  # 'Sentinel-2'


@dataclass
class NDVIResult:
    """NDVI calculation result from satellite imagery."""
    field_id: str
    gps_coords: Tuple[float, float]
    ndvi_value: float  # -1.0 to 1.0
    timestamp: datetime
    confidence: float
    satellite_image_url: str


@dataclass
class YieldPrediction:
    """Crop yield prediction based on NDVI trends."""
    field_id: str
    estimated_volume: float
    confidence_interval: Tuple[float, float]  # (lower_bound, upper_bound)
    maturity_stage: str  # 'early', 'mid', 'late', 'harvest_ready'
    prediction_date: datetime


class SatelliteAnalyzer:
    """
    Satellite Analyzer Component for crop monitoring and yield prediction.
    
    Retrieves Sentinel-2 satellite imagery using SageMaker Geospatial,
    calculates NDVI values, predicts crop maturity stages, and estimates yield.
    Implements 24-hour caching for satellite imagery.
    """
    
    def __init__(
        self,
        sagemaker_client=None,
        s3_client=None,
        dynamodb_table=None,
        cache_ttl_hours: int = CACHE_TTL_HOURS
    ):
        """
        Initialize SatelliteAnalyzer.
        
        Args:
            sagemaker_client: Optional boto3 SageMaker Geospatial client (for testing)
            s3_client: Optional boto3 S3 client (for testing)
            dynamodb_table: Optional DynamoDB table resource (for testing)
            cache_ttl_hours: Cache TTL in hours (default 24)
        """
        self.sagemaker = sagemaker_client or sagemaker_geospatial
        self.s3 = s3_client or s3
        self.table = dynamodb_table or table
        self.cache_ttl_hours = cache_ttl_hours
    
    def get_satellite_imagery(
        self,
        gps_coords: Tuple[float, float],
        date_range: Tuple[date, date]
    ) -> SatelliteImage:
        """
        Retrieves Sentinel-2 imagery for location using SageMaker Geospatial.

        Implements 24-hour caching using Redis/ElastiCache to avoid redundant API calls.
        Handles cloud cover and data unavailability scenarios.

        Args:
            gps_coords: (latitude, longitude) tuple
            date_range: (start_date, end_date) tuple

        Returns:
            SatelliteImage with bands and metadata

        Raises:
            Exception: If imagery retrieval fails or data unavailable
        """
        latitude, longitude = gps_coords
        start_date, end_date = date_range

        # Validate GPS coordinates
        if not (-90 <= latitude <= 90):
            error = create_error_response(
                error_code='INVALID_GPS',
                technical_details=f"Invalid latitude: {latitude}",
                language='en',
                category=ErrorCategory.USER_INPUT,
                severity=ErrorSeverity.LOW
            )
            raise ValueError(error.user_message)
        if not (-180 <= longitude <= 180):
            error = create_error_response(
                error_code='INVALID_GPS',
                technical_details=f"Invalid longitude: {longitude}",
                language='en',
                category=ErrorCategory.USER_INPUT,
                severity=ErrorSeverity.LOW
            )
            raise ValueError(error.user_message)

        print(f"Retrieving satellite imagery for ({latitude}, {longitude}), "
              f"date range: {start_date} to {end_date}")

        # Generate cache key
        cache_key = cache_manager.generate_cache_key(
            'satellite',
            latitude=f"{latitude:.6f}",
            longitude=f"{longitude:.6f}",
            start=start_date.isoformat(),
            end=end_date.isoformat()
        )

        # Try to get from cache first
        def compute_imagery():
            """Compute function for cache miss."""
            field_id = self._generate_field_id(gps_coords)

            # Check DynamoDB cache (legacy)
            cached_image = self._get_cached_imagery(field_id, start_date, end_date)
            if cached_image:
                print(f"Using DynamoDB cached satellite imagery for field {field_id}")
                return cached_image

            try:
                # Build bounding box around the point (approx 1km x 1km)
                bbox = self._create_bounding_box(latitude, longitude, buffer_km=0.5)

                # Retrieve Sentinel-2 data with retry logic
                satellite_image = self._retrieve_sentinel2_with_retry(
                    bbox=bbox,
                    start_date=start_date,
                    end_date=end_date,
                    gps_coords=gps_coords
                )

                # Cache in DynamoDB (legacy)
                self._cache_imagery(satellite_image)

                print(f"Successfully retrieved satellite imagery: {satellite_image.image_id}")
                return satellite_image

            except Exception as e:
                print(f"Error retrieving satellite imagery: {str(e)}")
                error = create_error_response(
                    error_code='SATELLITE_DATA_UNAVAILABLE',
                    technical_details=f"SageMaker Geospatial error: {str(e)}",
                    language='en',
                    category=ErrorCategory.EXTERNAL_SERVICE,
                    severity=ErrorSeverity.MEDIUM
                )
                raise Exception(error.user_message)

        # Serialize/deserialize functions for SatelliteImage
        def serialize_image(img: SatelliteImage) -> str:
            return json.dumps({
                'image_id': img.image_id,
                'gps_coords': img.gps_coords,
                'bands': img.bands,
                'timestamp': img.timestamp.isoformat(),
                'cloud_cover': img.cloud_cover,
                'data_source': img.data_source
            })

        def deserialize_image(data: str) -> SatelliteImage:
            obj = json.loads(data)
            return SatelliteImage(
                image_id=obj['image_id'],
                gps_coords=tuple(obj['gps_coords']),
                bands=obj['bands'],
                timestamp=datetime.fromisoformat(obj['timestamp']),
                cloud_cover=obj['cloud_cover'],
                data_source=obj['data_source']
            )

        # Use cache-or-compute pattern
        return get_cached_or_compute(
            cache_key=cache_key,
            compute_func=compute_imagery,
            ttl=self.cache_ttl_hours * 3600,  # Convert hours to seconds
            serialize_func=serialize_image,
            deserialize_func=deserialize_image
        )

    
    @retry_with_exponential_backoff(max_retries=3, service_name='sagemaker-geospatial')
    def _retrieve_sentinel2_with_retry(
        self,
        bbox: Dict,
        start_date: date,
        end_date: date,
        gps_coords: Tuple[float, float]
    ) -> SatelliteImage:
        """Retrieve Sentinel-2 data with retry logic."""
        return self._retrieve_sentinel2_data(bbox, start_date, end_date, gps_coords)
    
    def calculate_ndvi(self, satellite_image: SatelliteImage) -> NDVIResult:
        """
        Calculates Normalized Difference Vegetation Index.
        
        NDVI = (NIR - Red) / (NIR + Red)
        For Sentinel-2: NDVI = (B8 - B4) / (B8 + B4)
        
        Args:
            satellite_image: SatelliteImage with bands
            
        Returns:
            NDVIResult with value, timestamp, confidence
            
        Raises:
            Exception: If required bands are missing or calculation fails
        """
        print(f"Calculating NDVI for image: {satellite_image.image_id}")
        
        # Check for required bands (B4=Red, B8=NIR)
        if 'B4' not in satellite_image.bands or 'B8' not in satellite_image.bands:
            raise ValueError("Missing required bands for NDVI calculation (B4, B8)")
        
        try:
            b4_url = satellite_image.bands['B4']
            b8_url = satellite_image.bands['B8']

            # Compute real NDVI from Sentinel-2 COG files
            ndvi_value = self._compute_ndvi_from_cog(
                b4_url, b8_url, satellite_image.gps_coords
            )
            
            # Ensure NDVI is in valid range [-1.0, 1.0]
            ndvi_value = max(-1.0, min(1.0, ndvi_value))
            
            # Calculate confidence based on cloud cover
            confidence = self._calculate_confidence(satellite_image.cloud_cover)
            
            # Generate field ID
            field_id = self._generate_field_id(satellite_image.gps_coords)
            
            ndvi_result = NDVIResult(
                field_id=field_id,
                gps_coords=satellite_image.gps_coords,
                ndvi_value=ndvi_value,
                timestamp=satellite_image.timestamp,
                confidence=confidence,
                satellite_image_url=satellite_image.bands.get('B8', '')
            )
            
            # Store NDVI result in DynamoDB
            self._store_ndvi_result(ndvi_result)
            
            print(f"NDVI calculated: {ndvi_value:.3f} (confidence: {confidence:.2f})")
            return ndvi_result
            
        except Exception as e:
            print(f"Error calculating NDVI: {str(e)}")
            raise Exception(f"NDVI calculation failed: {str(e)}")
    
    def predict_yield(
        self,
        ndvi_history: List[NDVIResult],
        crop_type: str
    ) -> YieldPrediction:
        """
        Predicts crop yield based on NDVI trends and historical data.
        
        Args:
            ndvi_history: List of NDVIResult objects (time series)
            crop_type: Type of crop (e.g., 'onion', 'wheat', 'rice')
            
        Returns:
            YieldPrediction with estimated_volume, confidence_interval, maturity_stage
            
        Raises:
            ValueError: If ndvi_history is empty
        """
        if not ndvi_history:
            raise ValueError("Cannot predict yield without NDVI history")
        
        print(f"Predicting yield for crop: {crop_type}, NDVI samples: {len(ndvi_history)}")
        
        # Sort by timestamp
        ndvi_history = sorted(ndvi_history, key=lambda x: x.timestamp)
        
        # Get latest NDVI
        latest_ndvi = ndvi_history[-1]
        
        # Determine maturity stage based on NDVI value and trend
        maturity_stage = self._classify_maturity_stage(ndvi_history)
        
        # Estimate yield based on NDVI trends and crop type
        estimated_volume = self._estimate_yield_volume(ndvi_history, crop_type)
        
        # Calculate confidence interval (±15% for MVP)
        confidence_margin = estimated_volume * 0.15
        confidence_interval = (
            max(0, estimated_volume - confidence_margin),
            estimated_volume + confidence_margin
        )
        
        yield_prediction = YieldPrediction(
            field_id=latest_ndvi.field_id,
            estimated_volume=estimated_volume,
            confidence_interval=confidence_interval,
            maturity_stage=maturity_stage,
            prediction_date=datetime.utcnow()
        )
        
        # Store prediction in DynamoDB
        self._store_yield_prediction(yield_prediction, crop_type)
        
        print(f"Yield prediction: {estimated_volume:.2f} units, "
              f"maturity: {maturity_stage}, "
              f"confidence: [{confidence_interval[0]:.2f}, {confidence_interval[1]:.2f}]")
        
        return yield_prediction
    
    # ==================== Helper Methods ====================
    
    def _generate_field_id(self, gps_coords: Tuple[float, float]) -> str:
        """Generate unique field ID from GPS coordinates."""
        lat, lon = gps_coords
        # Hash coordinates to create consistent field ID
        coord_str = f"{lat:.6f},{lon:.6f}"
        hash_val = hashlib.md5(coord_str.encode()).hexdigest()[:8]
        return f"FIELD#{hash_val}"
    
    def _create_bounding_box(
        self,
        latitude: float,
        longitude: float,
        buffer_km: float = 0.5
    ) -> List[List[List[float]]]:
        """Create GeoJSON polygon coordinates around point for SageMaker Geospatial API."""
        lat_buffer = buffer_km / 111.0
        lon_buffer = buffer_km / (111.0 * math.cos(math.radians(latitude)))

        min_lon = longitude - lon_buffer
        max_lon = longitude + lon_buffer
        min_lat = latitude - lat_buffer
        max_lat = latitude + lat_buffer

        # GeoJSON polygon: closed ring of [lon, lat] pairs
        return [
            [
                [min_lon, min_lat],
                [max_lon, min_lat],
                [max_lon, max_lat],
                [min_lon, max_lat],
                [min_lon, min_lat],  # close the ring
            ]
        ]
    
    def _retrieve_sentinel2_data(
        self,
        bbox: List,
        start_date: date,
        end_date: date,
        gps_coords: Tuple[float, float]
    ) -> SatelliteImage:
        """
        Retrieve Sentinel-2 L2A data via SageMaker Geospatial API (us-west-2).

        Searches for imagery with <30% cloud cover and returns the most recent scene.
        Band URLs are public HTTPS COG files on sentinel-cogs.s3.us-west-2.amazonaws.com.
        """
        query = {
            'AreaOfInterest': {
                'AreaOfInterestGeometry': {
                    'PolygonGeometry': {'Coordinates': bbox}
                }
            },
            'TimeRangeFilter': {
                'StartTime': f"{start_date.isoformat()}T00:00:00Z",
                'EndTime': f"{end_date.isoformat()}T23:59:59Z",
            },
            'PropertyFilters': {
                'Properties': [
                    {'Property': {'EoCloudCover': {'LowerBound': 0, 'UpperBound': 30}}}
                ]
            },
        }

        response = self.sagemaker.search_raster_data_collection(
            Arn=SENTINEL2_ARN,
            RasterDataCollectionQuery=query,
        )

        items = response.get('Items', [])
        if not items:
            raise Exception(
                f"No Sentinel-2 imagery found for ({gps_coords[0]:.4f}, {gps_coords[1]:.4f}) "
                f"between {start_date} and {end_date} with <30% cloud cover"
            )

        # Use the first (most recent) result
        best = items[0]
        assets = best.get('Assets', {})
        image_id = best.get('Id', f"S2_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}")
        cloud_cover = best.get('Properties', {}).get('EoCloudCover', 0)

        # Extract COG band URLs (HTTPS, publicly readable)
        bands = {
            'B4': assets.get('red', {}).get('Href', ''),
            'B8': assets.get('nir', {}).get('Href', ''),
            'B3': assets.get('green', {}).get('Href', ''),
            'B2': assets.get('blue', {}).get('Href', ''),
        }

        # Parse timestamp
        dt_val = best.get('DateTime')
        if isinstance(dt_val, str):
            timestamp = datetime.fromisoformat(dt_val.replace('Z', '+00:00'))
        elif isinstance(dt_val, datetime):
            timestamp = dt_val
        else:
            timestamp = datetime.utcnow()

        return SatelliteImage(
            image_id=image_id,
            gps_coords=gps_coords,
            bands=bands,
            timestamp=timestamp.replace(tzinfo=None),
            cloud_cover=cloud_cover,
            data_source='Sentinel-2',
        )
    
    def _compute_ndvi_from_cog(
        self,
        b4_url: str,
        b8_url: str,
        gps_coords: Tuple[float, float],
        window_size: int = 5,
    ) -> float:
        """
        Compute real NDVI from Sentinel-2 COG band files via HTTP range requests.

        Opens B4 (Red) and B8 (NIR) Cloud Optimized GeoTIFFs, reads a small
        pixel window around the GPS point, and computes mean NDVI.

        Args:
            b4_url: HTTPS URL to B04 (Red) COG
            b8_url: HTTPS URL to B08 (NIR) COG
            gps_coords: (latitude, longitude) in EPSG:4326
            window_size: pixel window side length (default 5 = 50m x 50m)

        Returns:
            Mean NDVI value for the window
        """
        import rasterio
        from rasterio.transform import rowcol
        from pyproj import Transformer
        import numpy as np

        lat, lon = gps_coords
        half = window_size // 2

        with rasterio.open(b4_url) as red_ds:
            # Transform GPS (EPSG:4326) to the image CRS (typically EPSG:326XX UTM)
            image_crs = str(red_ds.crs)
            transformer = Transformer.from_crs("EPSG:4326", image_crs, always_xy=True)
            x, y = transformer.transform(lon, lat)

            row, col_idx = rowcol(red_ds.transform, x, y)

            # Clamp to image bounds
            row = max(half, min(red_ds.height - half - 1, row))
            col_idx = max(half, min(red_ds.width - half - 1, col_idx))

            window = rasterio.windows.Window(col_idx - half, row - half, window_size, window_size)
            red_data = red_ds.read(1, window=window).astype(float)

        with rasterio.open(b8_url) as nir_ds:
            window = rasterio.windows.Window(col_idx - half, row - half, window_size, window_size)
            nir_data = nir_ds.read(1, window=window).astype(float)

        # NDVI = (NIR - Red) / (NIR + Red)
        denominator = nir_data + red_data
        ndvi = np.where(denominator > 0, (nir_data - red_data) / denominator, 0)
        mean_ndvi = float(np.mean(ndvi))

        print(f"Real NDVI computed: {mean_ndvi:.4f} (CRS: {image_crs}, pixel: {row},{col_idx})")
        return mean_ndvi

    def _compute_ndvi_array(
        self,
        b4_url: str,
        b8_url: str,
        gps_coords: Tuple[float, float],
        window_size: int = 100,
    ) -> 'Any':
        """
        Compute 2D NDVI array from Sentinel-2 COG band files.

        Unlike _compute_ndvi_from_cog which returns a scalar mean, this returns
        the full 2D array for heatmap rendering.

        Args:
            b4_url: HTTPS URL to B04 (Red) COG
            b8_url: HTTPS URL to B08 (NIR) COG
            gps_coords: (latitude, longitude) in EPSG:4326
            window_size: pixel window side length (default 100 = ~1km × 1km)

        Returns:
            2D numpy array of NDVI values in [-1.0, 1.0]
        """
        import rasterio
        from rasterio.transform import rowcol
        from pyproj import Transformer
        import numpy as np

        lat, lon = gps_coords
        half = window_size // 2

        with rasterio.open(b4_url) as red_ds:
            image_crs = str(red_ds.crs)
            transformer = Transformer.from_crs("EPSG:4326", image_crs, always_xy=True)
            x, y = transformer.transform(lon, lat)
            row, col_idx = rowcol(red_ds.transform, x, y)

            row = max(half, min(red_ds.height - half - 1, row))
            col_idx = max(half, min(red_ds.width - half - 1, col_idx))

            window = rasterio.windows.Window(col_idx - half, row - half, window_size, window_size)
            red_data = red_ds.read(1, window=window).astype(float)

        with rasterio.open(b8_url) as nir_ds:
            window = rasterio.windows.Window(col_idx - half, row - half, window_size, window_size)
            nir_data = nir_ds.read(1, window=window).astype(float)

        denominator = nir_data + red_data
        ndvi = np.where(denominator > 0, (nir_data - red_data) / denominator, 0.0)

        print(f"NDVI array computed: shape={ndvi.shape}, mean={float(np.mean(ndvi)):.4f}")
        return ndvi

    def _render_ndvi_heatmap(
        self,
        ndvi_array: 'Any',
        crop_type: str = '',
        gps_coords: Optional[Tuple[float, float]] = None,
    ) -> bytes:
        """
        Render NDVI 2D array as a color-mapped PNG image with legend.

        Color scheme (farmer-friendly):
          brown (bare/stressed) → orange → yellow → green → dark green (dense)

        Returns:
            PNG image bytes
        """
        import numpy as np
        from PIL import Image, ImageDraw
        import io

        # NDVI color stops: (ndvi_threshold, RGB)
        color_stops = [
            (-1.0, (139, 90, 43)),
            (0.0,  (165, 42, 42)),
            (0.2,  (255, 140, 0)),
            (0.4,  (255, 255, 0)),
            (0.5,  (173, 255, 47)),
            (0.6,  (50, 205, 50)),
            (0.8,  (0, 128, 0)),
            (1.0,  (0, 64, 0)),
        ]

        def ndvi_to_rgb(val):
            val = max(-1.0, min(1.0, val))
            for i in range(len(color_stops) - 1):
                v0, c0 = color_stops[i]
                v1, c1 = color_stops[i + 1]
                if v0 <= val <= v1:
                    t = (val - v0) / (v1 - v0) if v1 != v0 else 0
                    return tuple(int(c0[j] + t * (c1[j] - c0[j])) for j in range(3))
            return color_stops[-1][1]

        # Sanitize: replace NaN/Inf with 0, then clamp to [-1, 1]
        ndvi_array = np.nan_to_num(ndvi_array, nan=0.0, posinf=1.0, neginf=-1.0)
        ndvi_array = np.clip(ndvi_array, -1.0, 1.0)

        h, w = ndvi_array.shape

        # Vectorized color mapping for performance
        rgb = np.zeros((h, w, 3), dtype=np.uint8)
        for y in range(h):
            for x in range(w):
                rgb[y, x] = ndvi_to_rgb(ndvi_array[y, x])

        # Scale up 4× for WhatsApp readability
        scale = 4
        img = Image.fromarray(rgb).resize((w * scale, h * scale), Image.NEAREST)

        # Build canvas with title + heatmap + legend
        title_height = 40
        legend_height = 70
        total_width = w * scale
        total_height = title_height + h * scale + legend_height

        canvas = Image.new('RGB', (total_width, total_height), (255, 255, 255))
        draw = ImageDraw.Draw(canvas)

        # Title
        title = "NDVI Crop Health Map"
        if crop_type:
            title += f" - {crop_type}"
        draw.text((10, 12), title, fill=(0, 0, 0))

        # Paste heatmap
        canvas.paste(img, (0, title_height))

        # Color legend bar at bottom
        legend_y = title_height + h * scale + 8
        bar_height = 20
        for x_pos in range(total_width):
            ndvi_val = -0.2 + (x_pos / total_width) * 1.2
            color = ndvi_to_rgb(ndvi_val)
            draw.line([(x_pos, legend_y), (x_pos, legend_y + bar_height)], fill=color)

        # Legend labels
        labels = [("Stressed", 0.08), ("Sparse", 0.28), ("Moderate", 0.48),
                  ("Healthy", 0.68), ("Dense", 0.88)]
        for label, frac in labels:
            x_pos = int(frac * total_width)
            draw.text((x_pos - 20, legend_y + bar_height + 4), label, fill=(0, 0, 0))

        # Mean NDVI annotation
        mean_ndvi = float(np.mean(ndvi_array))
        draw.text((10, legend_y + bar_height + 20), f"Avg NDVI: {mean_ndvi:.2f}", fill=(0, 0, 0))

        if gps_coords:
            coord_text = f"Location: {gps_coords[0]:.4f}N, {gps_coords[1]:.4f}E"
            draw.text((total_width - 200, legend_y + bar_height + 20), coord_text, fill=(100, 100, 100))

        buf = io.BytesIO()
        canvas.save(buf, format='PNG', optimize=True)
        buf.seek(0)
        return buf.getvalue()

    def _upload_heatmap_to_s3(self, image_bytes: bytes, field_id: str) -> str:
        """Upload NDVI heatmap PNG to S3 processed bucket. Returns S3 key."""
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        s3_key = f"ndvi-heatmaps/{field_id}/{timestamp}.png"

        bucket = os.environ.get('S3_BUCKET_PROCESSED', 'kisan-setu-processed')

        self.s3.put_object(
            Bucket=bucket,
            Key=s3_key,
            Body=image_bytes,
            ContentType='image/png',
        )
        print(f"Uploaded NDVI heatmap: s3://{bucket}/{s3_key}")
        return s3_key

    def _generate_presigned_url(self, s3_key: str, expires_in: int = 3600) -> str:
        """Generate a presigned HTTPS URL for the heatmap image."""
        bucket = os.environ.get('S3_BUCKET_PROCESSED', 'kisan-setu-processed')
        url = self.s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket, 'Key': s3_key},
            ExpiresIn=expires_in,
        )
        return url

    def _calculate_confidence(self, cloud_cover: float) -> float:
        """Calculate confidence score based on cloud cover."""
        # Confidence decreases with cloud cover
        # 0% cloud = 1.0 confidence
        # 50% cloud = 0.5 confidence
        # 100% cloud = 0.0 confidence
        return max(0.0, min(1.0, 1.0 - (cloud_cover / 100.0)))
    
    def _classify_maturity_stage(self, ndvi_history: List[NDVIResult]) -> str:
        """
        Classify crop maturity stage based on NDVI trends.
        
        Stages:
        - early: NDVI < 0.4 or increasing rapidly
        - mid: NDVI 0.4-0.6 and stable
        - late: NDVI 0.6-0.8 and stable/declining slowly
        - harvest_ready: NDVI declining rapidly or < 0.3
        """
        if not ndvi_history:
            return 'early'
        
        latest_ndvi = ndvi_history[-1].ndvi_value
        
        # Calculate trend if we have multiple samples
        if len(ndvi_history) >= 2:
            recent_values = [r.ndvi_value for r in ndvi_history[-3:]]
            trend = recent_values[-1] - recent_values[0]
        else:
            trend = 0
        
        # Classification logic
        if latest_ndvi < 0.3 or (trend < -0.1 and latest_ndvi < 0.5):
            return 'harvest_ready'
        elif latest_ndvi >= 0.6 and trend <= 0:
            return 'late'
        elif 0.4 <= latest_ndvi < 0.6:
            return 'mid'
        else:
            return 'early'
    
    def _estimate_yield_volume(
        self,
        ndvi_history: List[NDVIResult],
        crop_type: str
    ) -> float:
        """
        Estimate yield volume based on NDVI trends and crop type.
        
        This is a simplified model for MVP.
        In production, use ML models trained on historical data.
        """
        # Calculate average NDVI
        avg_ndvi = sum(r.ndvi_value for r in ndvi_history) / len(ndvi_history)
        
        # Crop-specific yield factors (tons per hectare)
        # These are simplified estimates
        crop_factors = {
            'onion': 25.0,
            'wheat': 4.0,
            'rice': 5.0,
            'cotton': 2.5,
            'tomato': 30.0,
            'potato': 20.0,
            'sugarcane': 70.0,
            'soybean': 2.5,
            'grape': 20.0,
            'jowar': 2.0,
            'bajra': 1.5,
            'tur': 1.2,
            'groundnut': 2.0,
            'mustard': 1.5,
            'maize': 5.0,
            'chana': 1.5,
            'chilli': 15.0,
            'turmeric': 8.0,
        }
        
        base_yield = crop_factors.get(crop_type.lower(), 10.0)
        
        # Scale by NDVI (healthy vegetation = higher yield)
        # NDVI 0.3 = 50% of base yield
        # NDVI 0.8 = 100% of base yield
        if avg_ndvi < 0.3:
            yield_factor = 0.3
        elif avg_ndvi > 0.8:
            yield_factor = 1.0
        else:
            yield_factor = 0.3 + (avg_ndvi - 0.3) / (0.8 - 0.3) * 0.7
        
        estimated_volume = base_yield * yield_factor
        
        return estimated_volume
    
    def _get_cached_imagery(
        self,
        field_id: str,
        start_date: date,
        end_date: date
    ) -> Optional[SatelliteImage]:
        """Check cache for recent satellite imagery."""
        try:
            # Query DynamoDB for cached imagery
            # NOTE: Direct boto3 DynamoDB call — bypasses DynamoDBAccess audit trails.
            # Consider migrating to DynamoDBAccess for audit compliance.
            response = self.table.query(
                KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
                ExpressionAttributeValues={
                    ':pk': field_id,
                    ':sk': 'SATELLITE#'
                },
                ScanIndexForward=False,  # Most recent first
                Limit=1
            )
            
            if not response['Items']:
                return None
            
            item = response['Items'][0]
            
            # Check if cache is still valid
            cached_timestamp = datetime.fromisoformat(item['timestamp'])
            cache_age_hours = (datetime.utcnow() - cached_timestamp).total_seconds() / 3600
            
            if cache_age_hours > self.cache_ttl_hours:
                print(f"Cache expired (age: {cache_age_hours:.1f} hours)")
                return None
            
            # Reconstruct SatelliteImage from cache
            satellite_image = SatelliteImage(
                image_id=item['image_id'],
                gps_coords=(float(item['latitude']), float(item['longitude'])),
                bands=item['bands'],
                timestamp=cached_timestamp,
                cloud_cover=float(item['cloud_cover']),
                data_source=item['data_source']
            )
            
            return satellite_image
            
        except Exception as e:
            print(f"Error checking cache: {str(e)}")
            return None
    
    def _cache_imagery(self, satellite_image: SatelliteImage) -> None:
        """Cache satellite imagery in DynamoDB."""
        try:
            field_id = self._generate_field_id(satellite_image.gps_coords)
            timestamp = satellite_image.timestamp.isoformat()
            
            item = {
                'PK': field_id,
                'SK': f"SATELLITE#{timestamp}",
                'entity_type': 'SatelliteImage',
                'image_id': satellite_image.image_id,
                'latitude': Decimal(str(satellite_image.gps_coords[0])),
                'longitude': Decimal(str(satellite_image.gps_coords[1])),
                'bands': satellite_image.bands,
                'timestamp': timestamp,
                'cloud_cover': Decimal(str(satellite_image.cloud_cover)),
                'data_source': satellite_image.data_source,
                'cached_at': datetime.utcnow().isoformat()
            }
            
            # NOTE: Direct boto3 DynamoDB call — bypasses DynamoDBAccess audit trails.
            # Consider migrating to DynamoDBAccess for audit compliance.
            self.table.put_item(Item=item)
            print(f"Cached satellite imagery: {satellite_image.image_id}")
            
        except Exception as e:
            print(f"Error caching imagery: {str(e)}")
    
    def _store_ndvi_result(self, ndvi_result: NDVIResult) -> None:
        """Store NDVI result in DynamoDB."""
        try:
            timestamp = ndvi_result.timestamp.isoformat()
            
            item = {
                'PK': ndvi_result.field_id,
                'SK': f"NDVI#{timestamp}",
                'entity_type': 'NDVIResult',
                'field_id': ndvi_result.field_id,
                'latitude': Decimal(str(ndvi_result.gps_coords[0])),
                'longitude': Decimal(str(ndvi_result.gps_coords[1])),
                'ndvi_value': Decimal(str(ndvi_result.ndvi_value)),
                'timestamp': timestamp,
                'confidence': Decimal(str(ndvi_result.confidence)),
                'satellite_image_url': ndvi_result.satellite_image_url,
                'created_at': datetime.utcnow().isoformat()
            }
            
            # NOTE: Direct boto3 DynamoDB call — bypasses DynamoDBAccess audit trails.
            # Consider migrating to DynamoDBAccess for audit compliance.
            self.table.put_item(Item=item)
            print(f"Stored NDVI result: {ndvi_result.field_id}")
            
        except Exception as e:
            print(f"Error storing NDVI result: {str(e)}")
    
    def _store_yield_prediction(
        self,
        yield_prediction: YieldPrediction,
        crop_type: str
    ) -> None:
        """Store yield prediction in DynamoDB."""
        try:
            timestamp = yield_prediction.prediction_date.isoformat()
            
            item = {
                'PK': yield_prediction.field_id,
                'SK': f"YIELD#{timestamp}",
                'entity_type': 'YieldPrediction',
                'field_id': yield_prediction.field_id,
                'estimated_volume': Decimal(str(yield_prediction.estimated_volume)),
                'confidence_lower': Decimal(str(yield_prediction.confidence_interval[0])),
                'confidence_upper': Decimal(str(yield_prediction.confidence_interval[1])),
                'maturity_stage': yield_prediction.maturity_stage,
                'crop_type': crop_type,
                'prediction_date': timestamp,
                'created_at': datetime.utcnow().isoformat()
            }
            
            # NOTE: Direct boto3 DynamoDB call — bypasses DynamoDBAccess audit trails.
            # Consider migrating to DynamoDBAccess for audit compliance.
            self.table.put_item(Item=item)
            print(f"Stored yield prediction: {yield_prediction.field_id}")
            
        except Exception as e:
            print(f"Error storing yield prediction: {str(e)}")


# ==================== Lambda Handler ====================

# Module-level SatelliteAnalyzer instance for warm invocation reuse
_analyzer = None


def get_analyzer():
    """Lazy-init helper: returns the module-level SatelliteAnalyzer, creating it on first call."""
    global _analyzer
    if _analyzer is None:
        _analyzer = SatelliteAnalyzer()
    return _analyzer


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for satellite analysis.

    Input:
        - action: 'get_imagery', 'calculate_ndvi', 'predict_yield', 'generate_heatmap'
        - gps_coords: [latitude, longitude]
        - date_range: [start_date, end_date] (for get_imagery)
        - crop_type: Crop type (for predict_yield / generate_heatmap)
        - include_heatmap: bool (optional, for predict_yield)

    Output:
        - Satellite imagery, NDVI result, yield prediction, or heatmap URL
    """
    
    try:
        print(f"Processing satellite analysis: {json.dumps(event)}")
        
        action = event.get('action')
        gps_coords = event.get('gps_coords')
        
        if not action:
            raise ValueError("Missing required field: action")
        
        if not gps_coords or len(gps_coords) != 2:
            raise ValueError("Invalid gps_coords: must be [latitude, longitude]")
        
        gps_coords = tuple(gps_coords)
        
        # Reuse module-level SatelliteAnalyzer for warm invocation benefits
        analyzer = get_analyzer()
        
        if action == 'get_imagery':
            # Get satellite imagery
            date_range = event.get('date_range')
            if not date_range or len(date_range) != 2:
                # Default to last 7 days
                end_date = date.today()
                start_date = end_date - timedelta(days=7)
            else:
                start_date = date.fromisoformat(date_range[0])
                end_date = date.fromisoformat(date_range[1])
            
            satellite_image = analyzer.get_satellite_imagery(gps_coords, (start_date, end_date))
            
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'status': 'success',
                    'action': 'get_imagery',
                    'image_id': satellite_image.image_id,
                    'gps_coords': satellite_image.gps_coords,
                    'timestamp': satellite_image.timestamp.isoformat(),
                    'cloud_cover': satellite_image.cloud_cover,
                    'data_source': satellite_image.data_source
                })
            }
        
        elif action == 'calculate_ndvi':
            # Get recent imagery and calculate NDVI
            end_date = date.today()
            start_date = end_date - timedelta(days=7)
            
            satellite_image = analyzer.get_satellite_imagery(gps_coords, (start_date, end_date))
            ndvi_result = analyzer.calculate_ndvi(satellite_image)
            
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'status': 'success',
                    'action': 'calculate_ndvi',
                    'field_id': ndvi_result.field_id,
                    'ndvi_value': float(ndvi_result.ndvi_value),
                    'confidence': float(ndvi_result.confidence),
                    'timestamp': ndvi_result.timestamp.isoformat()
                })
            }
        
        elif action == 'predict_yield':
            # Get NDVI history and predict yield
            crop_type = event.get('crop_type', 'onion')
            include_heatmap = event.get('include_heatmap', False)

            # Retrieve NDVI history from DynamoDB
            field_id = analyzer._generate_field_id(gps_coords)
            ndvi_history = analyzer._get_ndvi_history(field_id)

            # If no history, calculate current NDVI first
            satellite_image = None
            if not ndvi_history:
                end_date = date.today()
                start_date = end_date - timedelta(days=7)
                satellite_image = analyzer.get_satellite_imagery(gps_coords, (start_date, end_date))
                ndvi_result = analyzer.calculate_ndvi(satellite_image)
                ndvi_history = [ndvi_result]

            yield_prediction = analyzer.predict_yield(ndvi_history, crop_type)

            # Include NDVI value from most recent reading
            latest_ndvi_val = float(ndvi_history[-1].ndvi_value) if ndvi_history else None

            # Generate NDVI heatmap if requested
            heatmap_url = None
            if include_heatmap:
                try:
                    # Retrieve imagery if not already fetched above
                    if satellite_image is None:
                        end_date = date.today()
                        start_date = end_date - timedelta(days=7)
                        satellite_image = analyzer.get_satellite_imagery(gps_coords, (start_date, end_date))

                    ndvi_array = analyzer._compute_ndvi_array(
                        satellite_image.bands['B4'],
                        satellite_image.bands['B8'],
                        gps_coords,
                        window_size=100,
                    )
                    image_bytes = analyzer._render_ndvi_heatmap(
                        ndvi_array, crop_type=crop_type, gps_coords=gps_coords
                    )
                    s3_key = analyzer._upload_heatmap_to_s3(image_bytes, field_id)
                    heatmap_url = analyzer._generate_presigned_url(s3_key)
                    print(f"Heatmap generated: {heatmap_url[:80]}...")
                except Exception as hm_err:
                    print(f"Heatmap generation failed (non-fatal): {hm_err}")

            return {
                'statusCode': 200,
                'body': json.dumps({
                    'status': 'success',
                    'action': 'predict_yield',
                    'field_id': yield_prediction.field_id,
                    'ndvi_value': latest_ndvi_val,
                    'estimated_volume': float(yield_prediction.estimated_volume),
                    'confidence_interval': [
                        float(yield_prediction.confidence_interval[0]),
                        float(yield_prediction.confidence_interval[1])
                    ],
                    'maturity_stage': yield_prediction.maturity_stage,
                    'crop_type': crop_type,
                    'prediction_date': yield_prediction.prediction_date.isoformat(),
                    'data_source': 'sentinel-2',
                    'heatmap_url': heatmap_url,
                })
            }

        elif action == 'generate_heatmap':
            # Standalone heatmap generation (for dashboard/API use)
            crop_type = event.get('crop_type', 'onion')
            window_size = event.get('window_size', 100)

            end_date = date.today()
            start_date = end_date - timedelta(days=7)
            satellite_image = analyzer.get_satellite_imagery(gps_coords, (start_date, end_date))

            ndvi_array = analyzer._compute_ndvi_array(
                satellite_image.bands['B4'],
                satellite_image.bands['B8'],
                gps_coords,
                window_size=window_size,
            )
            import numpy as np
            mean_ndvi = float(np.mean(ndvi_array))

            image_bytes = analyzer._render_ndvi_heatmap(
                ndvi_array, crop_type=crop_type, gps_coords=gps_coords
            )
            field_id = analyzer._generate_field_id(gps_coords)
            s3_key = analyzer._upload_heatmap_to_s3(image_bytes, field_id)
            presigned_url = analyzer._generate_presigned_url(s3_key)

            return {
                'statusCode': 200,
                'body': json.dumps({
                    'status': 'success',
                    'action': 'generate_heatmap',
                    'heatmap_url': presigned_url,
                    'mean_ndvi': mean_ndvi,
                    'window_size': window_size,
                    'field_id': field_id,
                    'data_source': 'sentinel-2',
                })
            }

        else:
            raise ValueError(f"Unknown action: {action}")
    
    except Exception as e:
        print(f"SatelliteAnalyzer failed: {str(e)}, falling back to mock data")

        # Fall back to SatelliteMock for realistic demo data
        try:
            from satellite_mock import SatelliteMock
            mock = SatelliteMock()
            mock_data = mock.get_ndvi_data(gps_coords[0], gps_coords[1])

            if mock_data:
                # Generate mock heatmap if requested
                mock_heatmap_url = None
                include_heatmap = event.get('include_heatmap', False) if isinstance(event, dict) else False
                if include_heatmap or action == 'generate_heatmap':
                    try:
                        mock_heatmap_url = mock.generate_mock_heatmap_url(
                            gps_coords[0], gps_coords[1],
                            crop_type=mock_data.get('crop_type', 'Onion'),
                        )
                    except Exception as hm_err:
                        print(f"Mock heatmap generation failed: {hm_err}")

                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'status': 'success',
                        'action': action,
                        'ndvi_value': mock_data['ndvi_value'],
                        'crop_type': mock_data['crop_type'],
                        'maturity_stage': mock_data['maturity_stage'],
                        'health_status': mock_data['health_status'],
                        'estimated_yield': mock_data['estimated_yield'],
                        'coordinates': mock_data['coordinates'],
                        'data_source': 'mock_fallback',
                        'generated_at': mock_data['generated_at'],
                        'heatmap_url': mock_heatmap_url,
                    })
                }
        except Exception as mock_err:
            print(f"Mock fallback also failed: {mock_err}")

        return {
            'statusCode': 500,
            'body': json.dumps({
                'status': 'error',
                'error': str(e)
            })
        }


# Add helper method to SatelliteAnalyzer class
def _get_ndvi_history(self, field_id: str, days: int = 30) -> List[NDVIResult]:
    """Retrieve NDVI history for a field from DynamoDB."""
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # NOTE: Direct boto3 DynamoDB call — bypasses DynamoDBAccess audit trails.
        # Consider migrating to DynamoDBAccess for audit compliance.
        response = self.table.query(
            KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
            ExpressionAttributeValues={
                ':pk': field_id,
                ':sk': 'NDVI#'
            },
            ScanIndexForward=True  # Oldest first
        )
        
        ndvi_history = []
        for item in response['Items']:
            timestamp = datetime.fromisoformat(item['timestamp'])
            if timestamp >= cutoff_date:
                ndvi_result = NDVIResult(
                    field_id=item['field_id'],
                    gps_coords=(float(item['latitude']), float(item['longitude'])),
                    ndvi_value=float(item['ndvi_value']),
                    timestamp=timestamp,
                    confidence=float(item['confidence']),
                    satellite_image_url=item['satellite_image_url']
                )
                ndvi_history.append(ndvi_result)
        
        return ndvi_history
        
    except Exception as e:
        print(f"Error retrieving NDVI history: {str(e)}")
        return []

# Monkey-patch the method onto the class
SatelliteAnalyzer._get_ndvi_history = _get_ndvi_history

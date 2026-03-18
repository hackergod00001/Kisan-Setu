"""
Mock Satellite NDVI Data Generator
Provides realistic mock NDVI data for hackathon demo purposes when live
satellite APIs are unavailable.
"""

import hashlib
import io
import os
from datetime import datetime, timezone
from typing import Optional

import boto3

try:
    import numpy as np
    from PIL import Image, ImageDraw
    IMAGING_AVAILABLE = True
except ImportError:
    np = None
    Image = None
    ImageDraw = None
    IMAGING_AVAILABLE = False


# India geographic bounds (fallback covers all of India)
INDIA_BOUNDS = {
    "lat_min": 6.5,
    "lat_max": 37.5,
    "lon_min": 68.0,
    "lon_max": 97.5,
}

# Realistic Maharashtra crops
CROP_TYPES = ["Onion", "Soybean", "Cotton", "Sugarcane", "Wheat", "Jowar", "Bajra", "Tur"]

MATURITY_STAGES = ["early", "mid", "late", "harvest"]

# Estimated yield ranges by crop type (kg/hectare)
YIELD_RANGES = {
    "Onion": (3000, 6000),
    "Soybean": (1500, 3000),
    "Cotton": (1000, 2500),
    "Sugarcane": (50000, 100000),
    "Wheat": (2500, 5000),
    "Jowar": (1000, 2500),
    "Bajra": (800, 2000),
    "Tur": (800, 1800),
}


def _health_status_from_ndvi(ndvi: float) -> str:
    """Derive health status from NDVI value."""
    if ndvi > 0.8:
        return "Excellent"
    elif ndvi >= 0.6:
        return "Healthy"
    elif ndvi >= 0.45:
        return "Moderate"
    else:
        return "Stressed"


def _deterministic_hash(latitude: float, longitude: float) -> int:
    """Generate a deterministic integer hash from coordinates + current date."""
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    key = f"{latitude:.6f}:{longitude:.6f}:{date_str}"
    digest = hashlib.sha256(key.encode()).hexdigest()
    return int(digest, 16)


class SatelliteMock:
    """Mock NDVI data generator for hackathon demo."""

    def get_ndvi_data(self, latitude: float, longitude: float) -> Optional[dict]:
        """
        Generate deterministic mock NDVI data for given coordinates.

        Args:
            latitude: GPS latitude
            longitude: GPS longitude

        Returns:
            Dict with ndvi_value, crop_type, maturity_stage, health_status,
            estimated_yield, coordinates, generated_at, data_source — or
            None if coordinates are outside Maharashtra bounds.
        """
        if not self._in_india(latitude, longitude):
            return None

        h = _deterministic_hash(latitude, longitude)

        # NDVI in [0.3, 0.9]
        ndvi_value = 0.3 + (h % 10000) / 10000 * 0.6
        ndvi_value = round(ndvi_value, 4)

        crop_type = CROP_TYPES[h % len(CROP_TYPES)]
        maturity_stage = MATURITY_STAGES[(h >> 16) % len(MATURITY_STAGES)]
        health_status = _health_status_from_ndvi(ndvi_value)

        yield_min, yield_max = YIELD_RANGES[crop_type]
        estimated_yield_val = yield_min + ((h >> 32) % 10000) / 10000 * (yield_max - yield_min)
        estimated_yield_val = round(estimated_yield_val)

        return {
            "ndvi_value": ndvi_value,
            "crop_type": crop_type,
            "maturity_stage": maturity_stage,
            "health_status": health_status,
            "estimated_yield": f"{estimated_yield_val} kg/hectare",
            "coordinates": {"latitude": latitude, "longitude": longitude},
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "data_source": "mock",
        }

    def generate_mock_heatmap_url(
        self, latitude: float, longitude: float, crop_type: str = "Onion"
    ) -> Optional[str]:
        """
        Generate a mock NDVI heatmap PNG, upload to S3, and return presigned URL.

        Creates a deterministic synthetic NDVI field pattern for demo purposes.
        """
        if not IMAGING_AVAILABLE:
            import logging
            logging.warning("numpy/PIL not available — cannot generate heatmap")
            return None

        h = _deterministic_hash(latitude, longitude)
        rng = np.random.RandomState(h % (2**31))

        # Base NDVI from the same hash used in get_ndvi_data
        base_ndvi = 0.3 + (h % 10000) / 10000 * 0.6
        noise = rng.normal(0, 0.08, (100, 100))

        # Simple smoothing: average each pixel with its neighbors
        ndvi_array = np.clip(base_ndvi + noise, -0.1, 1.0)
        smoothed = ndvi_array.copy()
        smoothed[1:-1, 1:-1] = (
            ndvi_array[:-2, 1:-1] + ndvi_array[2:, 1:-1] +
            ndvi_array[1:-1, :-2] + ndvi_array[1:-1, 2:] +
            ndvi_array[1:-1, 1:-1]
        ) / 5.0
        ndvi_array = smoothed

        # Render using the same logic as SatelliteAnalyzer._render_ndvi_heatmap

        color_stops = [
            (-1.0, (139, 90, 43)), (0.0, (165, 42, 42)),
            (0.2, (255, 140, 0)), (0.4, (255, 255, 0)),
            (0.5, (173, 255, 47)), (0.6, (50, 205, 50)),
            (0.8, (0, 128, 0)), (1.0, (0, 64, 0)),
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

        hh, ww = ndvi_array.shape
        rgb = np.zeros((hh, ww, 3), dtype=np.uint8)
        for y in range(hh):
            for x in range(ww):
                rgb[y, x] = ndvi_to_rgb(ndvi_array[y, x])

        scale = 4
        img = Image.fromarray(rgb).resize((ww * scale, hh * scale), Image.NEAREST)

        title_height = 40
        legend_height = 70
        total_width = ww * scale
        total_height = title_height + hh * scale + legend_height

        canvas = Image.new("RGB", (total_width, total_height), (255, 255, 255))
        draw = ImageDraw.Draw(canvas)
        draw.text((10, 12), f"NDVI Crop Health Map - {crop_type} (Demo)", fill=(0, 0, 0))
        canvas.paste(img, (0, title_height))

        legend_y = title_height + hh * scale + 8
        bar_height = 20
        for x_pos in range(total_width):
            ndvi_val = -0.2 + (x_pos / total_width) * 1.2
            draw.line([(x_pos, legend_y), (x_pos, legend_y + bar_height)], fill=ndvi_to_rgb(ndvi_val))

        labels = [("Stressed", 0.08), ("Sparse", 0.28), ("Moderate", 0.48),
                  ("Healthy", 0.68), ("Dense", 0.88)]
        for label, frac in labels:
            draw.text((int(frac * total_width) - 20, legend_y + bar_height + 4), label, fill=(0, 0, 0))

        mean_ndvi = float(np.mean(ndvi_array))
        draw.text((10, legend_y + bar_height + 20), f"Avg NDVI: {mean_ndvi:.2f}", fill=(0, 0, 0))

        buf = io.BytesIO()
        canvas.save(buf, format="PNG", optimize=True)
        buf.seek(0)

        # Upload to S3 and generate presigned URL
        s3_client = boto3.client("s3")
        bucket = os.environ.get("S3_BUCKET_PROCESSED", "kisan-setu-processed")
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        s3_key = f"ndvi-heatmaps/mock/{latitude:.4f}_{longitude:.4f}/{timestamp}.png"

        s3_client.put_object(
            Bucket=bucket, Key=s3_key, Body=buf.getvalue(), ContentType="image/png"
        )

        url = s3_client.generate_presigned_url(
            "get_object", Params={"Bucket": bucket, "Key": s3_key}, ExpiresIn=3600
        )
        return url

    @staticmethod
    def _in_india(latitude: float, longitude: float) -> bool:
        """Check if coordinates fall within India bounds."""
        return (
            INDIA_BOUNDS["lat_min"] <= latitude <= INDIA_BOUNDS["lat_max"]
            and INDIA_BOUNDS["lon_min"] <= longitude <= INDIA_BOUNDS["lon_max"]
        )

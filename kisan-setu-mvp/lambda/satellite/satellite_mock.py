"""
Mock Satellite NDVI Data Generator
Provides realistic mock NDVI data for hackathon demo purposes when live
satellite APIs are unavailable.
"""

import hashlib
from datetime import datetime, timezone
from typing import Optional


# Maharashtra geographic bounds
MAHARASHTRA_BOUNDS = {
    "lat_min": 15.6,
    "lat_max": 22.1,
    "lon_min": 72.6,
    "lon_max": 80.9,
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
        if not self._in_maharashtra(latitude, longitude):
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

    @staticmethod
    def _in_maharashtra(latitude: float, longitude: float) -> bool:
        """Check if coordinates fall within Maharashtra bounds."""
        return (
            MAHARASHTRA_BOUNDS["lat_min"] <= latitude <= MAHARASHTRA_BOUNDS["lat_max"]
            and MAHARASHTRA_BOUNDS["lon_min"] <= longitude <= MAHARASHTRA_BOUNDS["lon_max"]
        )

"""
Unit tests for validation functions.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))

import pytest
from common.validation import (
    validate_gps_coordinates,
    validate_phone_number,
    validate_language_code,
    validate_ndvi_value,
    validate_confidence_score,
    validate_reliability_score,
    validate_quality_grade,
    validate_crop_type,
    validate_moisture_level,
    normalize_phone_number
)


class TestGPSValidation:
    """Tests for GPS coordinate validation."""
    
    def test_valid_coordinates(self):
        """Test valid GPS coordinates."""
        assert validate_gps_coordinates((0.0, 0.0))
        assert validate_gps_coordinates((28.6139, 77.2090))  # Delhi
        assert validate_gps_coordinates((-33.8688, 151.2093))  # Sydney
        assert validate_gps_coordinates((90.0, 180.0))  # Boundaries
        assert validate_gps_coordinates((-90.0, -180.0))  # Boundaries
    
    def test_invalid_latitude(self):
        """Test invalid latitude values."""
        assert not validate_gps_coordinates((91.0, 0.0))
        assert not validate_gps_coordinates((-91.0, 0.0))
        assert not validate_gps_coordinates((100.0, 0.0))
    
    def test_invalid_longitude(self):
        """Test invalid longitude values."""
        assert not validate_gps_coordinates((0.0, 181.0))
        assert not validate_gps_coordinates((0.0, -181.0))
        assert not validate_gps_coordinates((0.0, 200.0))
    
    def test_invalid_format(self):
        """Test invalid coordinate formats."""
        assert not validate_gps_coordinates((0.0,))  # Single value
        assert not validate_gps_coordinates((0.0, 0.0, 0.0))  # Three values
        assert not validate_gps_coordinates("0.0, 0.0")  # String
        assert not validate_gps_coordinates([0.0, 0.0])  # List instead of tuple
        assert not validate_gps_coordinates(("0.0", "0.0"))  # String values


class TestPhoneValidation:
    """Tests for phone number validation."""
    
    def test_valid_phone_numbers(self):
        """Test valid Indian phone numbers."""
        assert validate_phone_number("+919876543210")
        assert validate_phone_number("+91 9876543210")
        assert validate_phone_number("9876543210")
        assert validate_phone_number("+91-9876543210")
        assert validate_phone_number("9123456789")
        assert validate_phone_number("+918765432109")
    
    def test_invalid_phone_numbers(self):
        """Test invalid phone numbers."""
        assert not validate_phone_number("1234567890")  # Doesn't start with 6-9
        assert not validate_phone_number("98765432")  # Too short
        assert not validate_phone_number("98765432101")  # Too long
        assert not validate_phone_number("+1234567890")  # Wrong country code
        assert not validate_phone_number("abcdefghij")  # Letters
        assert not validate_phone_number("")  # Empty
        assert not validate_phone_number(123456789)  # Not a string
    
    def test_normalize_phone_number(self):
        """Test phone number normalization."""
        assert normalize_phone_number("9876543210") == "+919876543210"
        assert normalize_phone_number("+919876543210") == "+919876543210"
        assert normalize_phone_number("+91 9876543210") == "+919876543210"
        assert normalize_phone_number("+91-9876543210") == "+919876543210"
        assert normalize_phone_number("919876543210") == "+919876543210"
        assert normalize_phone_number("invalid") is None


class TestLanguageValidation:
    """Tests for language code validation."""
    
    def test_valid_languages(self):
        """Test valid language codes."""
        assert validate_language_code("hi-IN")
        assert validate_language_code("mr-IN")
        assert validate_language_code("ta-IN")
    
    def test_invalid_languages(self):
        """Test invalid language codes."""
        assert not validate_language_code("en-US")
        assert not validate_language_code("hi")
        assert not validate_language_code("IN")
        assert not validate_language_code("")
        assert not validate_language_code("hindi")


class TestNDVIValidation:
    """Tests for NDVI value validation."""
    
    def test_valid_ndvi(self):
        """Test valid NDVI values."""
        assert validate_ndvi_value(0.0)
        assert validate_ndvi_value(0.5)
        assert validate_ndvi_value(-0.5)
        assert validate_ndvi_value(1.0)
        assert validate_ndvi_value(-1.0)
        assert validate_ndvi_value(0.8)
    
    def test_invalid_ndvi(self):
        """Test invalid NDVI values."""
        assert not validate_ndvi_value(1.1)
        assert not validate_ndvi_value(-1.1)
        assert not validate_ndvi_value(2.0)
        assert not validate_ndvi_value(-2.0)
        assert not validate_ndvi_value("0.5")


class TestConfidenceValidation:
    """Tests for confidence score validation."""
    
    def test_valid_confidence(self):
        """Test valid confidence scores."""
        assert validate_confidence_score(0.0)
        assert validate_confidence_score(0.5)
        assert validate_confidence_score(1.0)
        assert validate_confidence_score(0.95)
    
    def test_invalid_confidence(self):
        """Test invalid confidence scores."""
        assert not validate_confidence_score(-0.1)
        assert not validate_confidence_score(1.1)
        assert not validate_confidence_score(2.0)
        assert not validate_confidence_score("0.5")


class TestReliabilityScoreValidation:
    """Tests for reliability score validation."""
    
    def test_valid_scores(self):
        """Test valid reliability scores."""
        assert validate_reliability_score(0)
        assert validate_reliability_score(50)
        assert validate_reliability_score(100)
        assert validate_reliability_score(75.5)
    
    def test_invalid_scores(self):
        """Test invalid reliability scores."""
        assert not validate_reliability_score(-1)
        assert not validate_reliability_score(101)
        assert not validate_reliability_score(150)
        assert not validate_reliability_score("50")


class TestQualityGradeValidation:
    """Tests for quality grade validation."""
    
    def test_valid_grades(self):
        """Test valid quality grades."""
        assert validate_quality_grade("A")
        assert validate_quality_grade("B")
        assert validate_quality_grade("C")
    
    def test_invalid_grades(self):
        """Test invalid quality grades."""
        assert not validate_quality_grade("D")
        assert not validate_quality_grade("a")
        assert not validate_quality_grade("1")
        assert not validate_quality_grade("")


class TestCropTypeValidation:
    """Tests for crop type validation."""
    
    def test_valid_crop_types(self):
        """Test valid crop types."""
        assert validate_crop_type("onion")
        assert validate_crop_type("wheat")
        assert validate_crop_type("rice")
        assert validate_crop_type("cotton")
        assert validate_crop_type("Onion")  # Case insensitive
        assert validate_crop_type("WHEAT")
    
    def test_invalid_crop_types(self):
        """Test invalid crop types."""
        assert not validate_crop_type("tomato")
        assert not validate_crop_type("potato")
        assert not validate_crop_type("")


class TestMoistureValidation:
    """Tests for moisture level validation."""
    
    def test_valid_moisture(self):
        """Test valid moisture levels."""
        assert validate_moisture_level(0)
        assert validate_moisture_level(50)
        assert validate_moisture_level(100)
        assert validate_moisture_level(12.5)
    
    def test_invalid_moisture(self):
        """Test invalid moisture levels."""
        assert not validate_moisture_level(-1)
        assert not validate_moisture_level(101)
        assert not validate_moisture_level(150)
        assert not validate_moisture_level("50")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

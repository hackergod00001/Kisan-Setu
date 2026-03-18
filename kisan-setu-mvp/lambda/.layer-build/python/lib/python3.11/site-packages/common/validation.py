"""
Data validation functions for Kisan-Setu system.

This module provides validation for GPS coordinates, phone numbers,
language codes, and other data inputs.
"""

import re
from typing import Tuple, Optional


# Supported language codes
SUPPORTED_LANGUAGES = {'hi-IN', 'mr-IN', 'ta-IN'}

# Valid quality grades
VALID_QUALITY_GRADES = {'A', 'B', 'C'}

# Valid crop types
VALID_CROP_TYPES = {'onion', 'wheat', 'rice', 'cotton', 'soybean', 'maize'}


def validate_gps_coordinates(coords: Tuple[float, float]) -> bool:
    """
    Validate GPS coordinates.
    
    Args:
        coords: Tuple of (latitude, longitude)
        
    Returns:
        True if coordinates are valid, False otherwise
        
    Valid ranges:
        - Latitude: -90 to 90
        - Longitude: -180 to 180
    """
    if not isinstance(coords, tuple) or len(coords) != 2:
        return False
    
    latitude, longitude = coords
    
    if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)):
        return False
    
    return -90 <= latitude <= 90 and -180 <= longitude <= 180


def validate_phone_number(phone: str) -> bool:
    """
    Validate Indian phone number format.
    
    Args:
        phone: Phone number string
        
    Returns:
        True if phone number is valid, False otherwise
        
    Valid formats:
        - +919876543210
        - +91 9876543210
        - 919876543210
        - 9876543210
    """
    if not isinstance(phone, str):
        return False
    
    # Remove spaces and hyphens
    cleaned = phone.replace(' ', '').replace('-', '')
    
    # Check for +91 prefix, 91 prefix, or 10-digit number
    pattern = r'^(\+91|91)?[6-9]\d{9}$'
    return bool(re.match(pattern, cleaned))


def validate_language_code(language: str) -> bool:
    """
    Validate language code.
    
    Args:
        language: Language code string (e.g., 'hi-IN', 'mr-IN', 'ta-IN')
        
    Returns:
        True if language code is supported, False otherwise
    """
    return language in SUPPORTED_LANGUAGES


def validate_ndvi_value(ndvi: float) -> bool:
    """
    Validate NDVI value range.
    
    Args:
        ndvi: NDVI value
        
    Returns:
        True if NDVI is in valid range [-1.0, 1.0], False otherwise
    """
    return isinstance(ndvi, (int, float)) and -1.0 <= ndvi <= 1.0


def validate_confidence_score(confidence: float) -> bool:
    """
    Validate confidence score range.
    
    Args:
        confidence: Confidence score
        
    Returns:
        True if confidence is in valid range [0.0, 1.0], False otherwise
    """
    return isinstance(confidence, (int, float)) and 0.0 <= confidence <= 1.0


def validate_reliability_score(score: float) -> bool:
    """
    Validate reliability score range.
    
    Args:
        score: Reliability score
        
    Returns:
        True if score is in valid range [0, 100], False otherwise
    """
    return isinstance(score, (int, float)) and 0 <= score <= 100


def validate_quality_grade(grade: str) -> bool:
    """
    Validate quality grade.
    
    Args:
        grade: Quality grade string
        
    Returns:
        True if grade is valid, False otherwise
    """
    return grade in VALID_QUALITY_GRADES


def validate_crop_type(crop_type: str) -> bool:
    """
    Validate crop type.
    
    Args:
        crop_type: Crop type string
        
    Returns:
        True if crop type is valid, False otherwise
    """
    return crop_type.lower() in VALID_CROP_TYPES


def validate_moisture_level(moisture: float) -> bool:
    """
    Validate moisture level percentage.
    
    Args:
        moisture: Moisture level percentage
        
    Returns:
        True if moisture is in valid range [0, 100], False otherwise
    """
    return isinstance(moisture, (int, float)) and 0 <= moisture <= 100


def normalize_phone_number(phone: str) -> Optional[str]:
    """
    Normalize phone number to standard format (+919876543210).
    
    Args:
        phone: Phone number string
        
    Returns:
        Normalized phone number or None if invalid
    """
    if not validate_phone_number(phone):
        return None
    
    # Remove spaces and hyphens
    cleaned = phone.replace(' ', '').replace('-', '')
    
    # Add +91 prefix if not present
    if not cleaned.startswith('+91'):
        if cleaned.startswith('91'):
            cleaned = '+' + cleaned
        else:
            cleaned = '+91' + cleaned
    
    return cleaned

"""
Test data loader utilities.

This module provides helper functions for loading test data from the test_data directory.
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional


# Get the test_data directory path
TEST_DATA_DIR = Path(__file__).parent


def get_test_ledger(language: str, sample_num: int = 1) -> str:
    """
    Get path to test ledger image.
    
    Args:
        language: Language code ('hindi', 'marathi', 'tamil')
        sample_num: Sample number (1, 2, 3, etc.)
    
    Returns: Path to ledger image file
    """
    ledger_path = TEST_DATA_DIR / 'ledgers' / language / f'sample_ledger_{sample_num}.jpg'
    return str(ledger_path)


def get_test_voice(language: str, query_type: str) -> str:
    """
    Get path to test voice recording.
    
    Args:
        language: Language code ('hindi', 'marathi', 'tamil')
        query_type: Type of query ('query_crop_status', 'query_price', etc.)
    
    Returns: Path to voice recording file
    """
    voice_path = TEST_DATA_DIR / 'voice' / language / f'{query_type}.mp3'
    return str(voice_path)


def get_test_satellite_image(gps_coords: tuple) -> str:
    """
    Get path to test satellite image.
    
    Args:
        gps_coords: Tuple of (latitude, longitude)
    
    Returns: Path to satellite image file
    """
    lat, lon = gps_coords
    image_path = TEST_DATA_DIR / 'satellite' / 'sentinel2' / f'field_{lat}_{lon}.tif'
    return str(image_path)


def load_test_fixture(fixture_name: str) -> Dict[str, Any]:
    """
    Load JSON test fixture.
    
    Args:
        fixture_name: Name of fixture file (without .json extension)
    
    Returns: Parsed JSON data as dictionary
    """
    fixture_path = TEST_DATA_DIR / 'fixtures' / f'{fixture_name}.json'
    with open(fixture_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_ndvi_sample(stage: str) -> Dict[str, Any]:
    """
    Load NDVI sample data.
    
    Args:
        stage: Growth stage ('early_stage', 'mid_stage', 'late_stage', 'harvest_ready')
    
    Returns: NDVI data as dictionary
    """
    ndvi_path = TEST_DATA_DIR / 'satellite' / 'ndvi' / f'{stage}.json'
    with open(ndvi_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_all_farmers() -> List[Dict[str, Any]]:
    """
    Get all test farmers.
    
    Returns: List of farmer dictionaries
    """
    data = load_test_fixture('farmers')
    return data.get('farmers', [])


def get_farmer_by_id(farmer_id: str) -> Optional[Dict[str, Any]]:
    """
    Get specific farmer by ID.
    
    Args:
        farmer_id: Farmer ID to search for
    
    Returns: Farmer dictionary or None if not found
    """
    farmers = get_all_farmers()
    for farmer in farmers:
        if farmer['farmer_id'] == farmer_id:
            return farmer
    return None


def get_all_fpos() -> List[Dict[str, Any]]:
    """
    Get all test FPOs.
    
    Returns: List of FPO dictionaries
    """
    data = load_test_fixture('fpos')
    return data.get('fpos', [])


def get_fpo_by_id(fpo_id: str) -> Optional[Dict[str, Any]]:
    """
    Get specific FPO by ID.
    
    Args:
        fpo_id: FPO ID to search for
    
    Returns: FPO dictionary or None if not found
    """
    fpos = get_all_fpos()
    for fpo in fpos:
        if fpo['fpo_id'] == fpo_id:
            return fpo
    return None


def get_all_transactions() -> List[Dict[str, Any]]:
    """
    Get all test transactions.
    
    Returns: List of transaction dictionaries
    """
    data = load_test_fixture('transactions')
    return data.get('transactions', [])


def get_transactions_by_farmer(farmer_id: str) -> List[Dict[str, Any]]:
    """
    Get all transactions for a specific farmer.
    
    Args:
        farmer_id: Farmer ID to filter by
    
    Returns: List of transaction dictionaries
    """
    transactions = get_all_transactions()
    return [txn for txn in transactions if txn['farmer_id'] == farmer_id]


def get_all_credit_scores() -> List[Dict[str, Any]]:
    """
    Get all test credit scores.
    
    Returns: List of credit score dictionaries
    """
    data = load_test_fixture('credit_scores')
    return data.get('credit_scores', [])


def get_credit_score_by_farmer(farmer_id: str) -> Optional[Dict[str, Any]]:
    """
    Get credit score for a specific farmer.
    
    Args:
        farmer_id: Farmer ID to search for
    
    Returns: Credit score dictionary or None if not found
    """
    scores = get_all_credit_scores()
    for score in scores:
        if score['farmer_id'] == farmer_id:
            return score
    return None


def get_ndvi_time_series(field_id: str = "test_field_001") -> List[Dict[str, Any]]:
    """
    Get NDVI time series for a field.
    
    Args:
        field_id: Field ID (default: test_field_001)
    
    Returns: List of NDVI readings in chronological order
    """
    stages = ['early_stage', 'mid_stage', 'late_stage', 'harvest_ready']
    return [load_ndvi_sample(stage) for stage in stages]


# ============================================================================
# Test Data Validation
# ============================================================================

def validate_test_data() -> Dict[str, bool]:
    """
    Validate that all test data files exist and are valid.
    
    Returns: Dictionary with validation results for each data type
    """
    results = {}
    
    # Check fixtures
    fixtures = ['farmers', 'fpos', 'transactions', 'credit_scores']
    for fixture in fixtures:
        try:
            load_test_fixture(fixture)
            results[f'fixture_{fixture}'] = True
        except Exception:
            results[f'fixture_{fixture}'] = False
    
    # Check NDVI samples
    stages = ['early_stage', 'mid_stage', 'late_stage', 'harvest_ready']
    for stage in stages:
        try:
            load_ndvi_sample(stage)
            results[f'ndvi_{stage}'] = True
        except Exception:
            results[f'ndvi_{stage}'] = False
    
    return results


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == '__main__':
    # Validate all test data
    print("Validating test data...")
    validation_results = validate_test_data()
    
    for data_type, is_valid in validation_results.items():
        status = "✓" if is_valid else "✗"
        print(f"{status} {data_type}")
    
    # Load and display sample data
    print("\n" + "="*60)
    print("Sample Farmers:")
    print("="*60)
    farmers = get_all_farmers()
    for farmer in farmers[:3]:
        print(f"- {farmer['name']} ({farmer['farmer_id']}) - {farmer['preferred_language']}")
    
    print("\n" + "="*60)
    print("Sample Transactions:")
    print("="*60)
    transactions = get_all_transactions()
    for txn in transactions[:3]:
        print(f"- {txn['transaction_id']}: {txn['quantity']}kg {txn['crop_type']} @ ₹{txn['price']}")
    
    print("\n" + "="*60)
    print("NDVI Time Series:")
    print("="*60)
    ndvi_series = get_ndvi_time_series()
    for ndvi in ndvi_series:
        print(f"- {ndvi['maturity_stage']}: NDVI={ndvi['ndvi_value']} (confidence={ndvi['confidence']})")

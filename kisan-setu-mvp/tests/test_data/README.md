# Test Data for Kisan-Setu

This directory contains sample test data for testing the Kisan-Setu system without requiring actual AWS services or real farmer data.

## Directory Structure

```
test_data/
├── ledgers/          # Sample handwritten ledger images
│   ├── hindi/        # Hindi script ledgers
│   ├── marathi/      # Marathi script ledgers
│   └── tamil/        # Tamil script ledgers
├── voice/            # Sample voice recordings
│   ├── hindi/        # Hindi voice samples
│   ├── marathi/      # Marathi voice samples
│   └── tamil/        # Tamil voice samples
├── satellite/        # Sample satellite imagery
│   ├── sentinel2/    # Sentinel-2 imagery samples
│   └── ndvi/         # Pre-calculated NDVI samples
└── fixtures/         # JSON fixtures for testing
    ├── farmers.json
    ├── transactions.json
    ├── fpos.json
    └── credit_scores.json
```

## Ledger Images

Sample handwritten ledger images in different scripts:

### Hindi Ledgers
- `ledgers/hindi/sample_ledger_1.jpg` - Clean, high-quality ledger
- `ledgers/hindi/sample_ledger_2.jpg` - Slightly faded ledger
- `ledgers/hindi/sample_ledger_3.jpg` - Crumpled ledger with stains

### Marathi Ledgers
- `ledgers/marathi/sample_ledger_1.jpg` - Clean, high-quality ledger
- `ledgers/marathi/sample_ledger_2.jpg` - Low-light photo

### Tamil Ledgers
- `ledgers/tamil/sample_ledger_1.jpg` - Clean, high-quality ledger
- `ledgers/tamil/sample_ledger_2.jpg` - Angled photo

## Voice Recordings

Sample voice recordings in different languages:

### Hindi Voice Samples
- `voice/hindi/query_crop_status.mp3` - "मेरे खेत की स्थिति कैसी है?"
- `voice/hindi/query_price.mp3` - "आज प्याज का भाव क्या है?"
- `voice/hindi/query_credit_score.mp3` - "मेरा विश्वसनीयता स्कोर क्या है?"

### Marathi Voice Samples
- `voice/marathi/query_crop_status.mp3` - "माझ्या शेतातील पिकाची स्थिती कशी आहे?"
- `voice/marathi/query_price.mp3` - "आज कांद्याचा भाव काय आहे?"

### Tamil Voice Samples
- `voice/tamil/query_crop_status.mp3` - "என் வயலில் பயிர் நிலை எப்படி உள்ளது?"
- `voice/tamil/query_price.mp3` - "இன்று வெங்காயத்தின் விலை என்ன?"

## Satellite Imagery

Sample satellite imagery and NDVI data:

### Sentinel-2 Imagery
- `satellite/sentinel2/field_28.6139_77.2090.tif` - Delhi region field
- `satellite/sentinel2/field_19.0760_72.8777.tif` - Mumbai region field
- `satellite/sentinel2/field_13.0827_80.2707.tif` - Chennai region field

### NDVI Samples
- `satellite/ndvi/early_stage.json` - NDVI 0.3 (early growth)
- `satellite/ndvi/mid_stage.json` - NDVI 0.5 (mid growth)
- `satellite/ndvi/late_stage.json` - NDVI 0.7 (late growth)
- `satellite/ndvi/harvest_ready.json` - NDVI 0.85 (harvest ready)

## JSON Fixtures

Pre-defined test data in JSON format:

### farmers.json
```json
{
  "farmers": [
    {
      "farmer_id": "test_farmer_001",
      "name": "Ram Kumar",
      "phone": "+919876543210",
      "fpo_id": "test_fpo_001",
      "gps_coords": [28.6139, 77.2090],
      "preferred_language": "hi-IN",
      "join_date": "2023-01-01"
    }
  ]
}
```

### transactions.json
```json
{
  "transactions": [
    {
      "transaction_id": "test_txn_001",
      "farmer_id": "test_farmer_001",
      "fpo_id": "test_fpo_001",
      "quantity": 100.0,
      "crop_type": "onion",
      "quality_grade": "A",
      "moisture": 12.5,
      "price": 5000.0,
      "timestamp": "2024-01-15T10:30:00Z"
    }
  ]
}
```

## Usage in Tests

### Loading Ledger Images

```python
import os
from pathlib import Path

def get_test_ledger(language: str, sample_num: int = 1) -> str:
    """Get path to test ledger image."""
    test_data_dir = Path(__file__).parent / 'test_data'
    ledger_path = test_data_dir / 'ledgers' / language / f'sample_ledger_{sample_num}.jpg'
    return str(ledger_path)

# Usage
hindi_ledger = get_test_ledger('hindi', 1)
```

### Loading Voice Recordings

```python
def get_test_voice(language: str, query_type: str) -> str:
    """Get path to test voice recording."""
    test_data_dir = Path(__file__).parent / 'test_data'
    voice_path = test_data_dir / 'voice' / language / f'{query_type}.mp3'
    return str(voice_path)

# Usage
hindi_voice = get_test_voice('hindi', 'query_crop_status')
```

### Loading Satellite Imagery

```python
def get_test_satellite_image(gps_coords: tuple) -> str:
    """Get path to test satellite image."""
    lat, lon = gps_coords
    test_data_dir = Path(__file__).parent / 'test_data'
    image_path = test_data_dir / 'satellite' / 'sentinel2' / f'field_{lat}_{lon}.tif'
    return str(image_path)

# Usage
satellite_image = get_test_satellite_image((28.6139, 77.2090))
```

### Loading JSON Fixtures

```python
import json

def load_test_fixture(fixture_name: str) -> dict:
    """Load JSON test fixture."""
    test_data_dir = Path(__file__).parent / 'test_data'
    fixture_path = test_data_dir / 'fixtures' / f'{fixture_name}.json'
    with open(fixture_path, 'r') as f:
        return json.load(f)

# Usage
farmers = load_test_fixture('farmers')
```

## Generating Test Data

To generate additional test data, use the provided scripts:

```bash
# Generate sample ledger images
python tests/test_data/generate_ledgers.py --language hindi --count 5

# Generate sample voice recordings (requires TTS)
python tests/test_data/generate_voice.py --language marathi --count 3

# Generate sample satellite imagery (requires satellite data access)
python tests/test_data/generate_satellite.py --coords 28.6139,77.2090
```

## Notes

- All test data is synthetic and does not contain real farmer information
- Ledger images are generated using handwriting fonts and sample data
- Voice recordings are generated using Amazon Polly or similar TTS services
- Satellite imagery is either synthetic or from public datasets
- All data is for testing purposes only and should not be used in production

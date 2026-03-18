#!/usr/bin/env python3
"""
Seed DynamoDB with test data for Kisan-Setu MVP.

Creates:
- 1 FPO (Farmer Producer Organization)
- 3 Farmers with realistic profiles
- 10-15 transactions per farmer (spanning 6 months)
- Credit scores for each farmer
- NDVI satellite results
"""

import boto3
import uuid
from decimal import Decimal
from datetime import datetime, timedelta
import random
from botocore.exceptions import ClientError

REGION = 'ap-south-1'
TABLE_NAME = 'KisanSetuData'

dynamodb = boto3.resource('dynamodb', region_name=REGION)
table = dynamodb.Table(TABLE_NAME)


def _put_item_idempotent(item):
    """Put item only if PK doesn't already exist. Returns True if created, False if skipped."""
    try:
        table.put_item(
            Item=item,
            ConditionExpression='attribute_not_exists(PK)'
        )
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            return False
        raise


def seed_fpo():
    """Seed FPO data."""
    created, skipped = 0, 0
    fpo = {
        'PK': 'FPO#FPO001',
        'SK': 'METADATA',
        'entity_type': 'FPO',
        'fpo_id': 'FPO001',
        'name': 'Nashik Grape Growers FPO',
        'location': 'Nashik, Maharashtra',
        'manager_contact': '+919876543210',
        'created_date': '2023-01-15',
        'member_count': 120,
    }
    if _put_item_idempotent(fpo):
        created += 1
        print(f"  Created FPO: {fpo['name']}")
    else:
        skipped += 1
        print(f"  Skipped FPO (already exists): {fpo['name']}")
    print(f"  FPO: {created} created, {skipped} skipped")
    return fpo, created, skipped


def seed_farmers():
    """Seed farmer profiles."""
    created, skipped = 0, 0
    # Use the real WhatsApp sandbox number from existing conversations
    farmers = [
        {
            'PK': 'FARMER#917303969321',
            'SK': 'METADATA',
            'entity_type': 'Farmer',
            'farmer_id': '917303969321',
            'name': 'Rajesh Patil',
            'phone': '+917303969321',
            'fpo_id': 'FPO001',
            'gps_latitude': Decimal('19.9975'),
            'gps_longitude': Decimal('73.7898'),
            'preferred_language': 'en',
            'preferredLanguage': 'en',
            'join_date': '2023-03-01',
        },
        {
            'PK': 'FARMER#919876543210',
            'SK': 'METADATA',
            'entity_type': 'Farmer',
            'farmer_id': '919876543210',
            'name': 'Suresh Kumar',
            'phone': '+919876543210',
            'fpo_id': 'FPO001',
            'gps_latitude': Decimal('20.0063'),
            'gps_longitude': Decimal('73.7620'),
            'preferred_language': 'hi-IN',
            'preferredLanguage': 'hi-IN',
            'join_date': '2023-06-15',
        },
        {
            'PK': 'FARMER#919123456789',
            'SK': 'METADATA',
            'entity_type': 'Farmer',
            'farmer_id': '919123456789',
            'name': 'Lakshmi Devi',
            'phone': '+919123456789',
            'fpo_id': 'FPO001',
            'gps_latitude': Decimal('19.9800'),
            'gps_longitude': Decimal('73.8100'),
            'preferred_language': 'mr-IN',
            'preferredLanguage': 'mr-IN',
            'join_date': '2024-01-10',
        },
    ]

    for farmer in farmers:
        if _put_item_idempotent(farmer):
            created += 1
            print(f"  Created Farmer: {farmer['name']} ({farmer['phone']})")
        else:
            skipped += 1
            print(f"  Skipped Farmer (already exists): {farmer['name']} ({farmer['phone']})")

    print(f"  Farmers: {created} created, {skipped} skipped")
    return farmers, created, skipped


def seed_transactions(farmers):
    """Seed transaction data for each farmer."""
    crop_types = ['onion', 'wheat', 'rice', 'cotton', 'soybean', 'grape', 'tomato']
    quality_grades = ['A', 'B', 'C']

    created, skipped = 0, 0
    for farmer in farmers:
        farmer_id = farmer['farmer_id']
        num_txns = random.randint(10, 15)

        for i in range(num_txns):
            # Spread transactions over past 6 months
            days_ago = random.randint(1, 180)
            txn_date = datetime.utcnow() - timedelta(days=days_ago)
            timestamp = txn_date.isoformat()

            crop = random.choice(crop_types)
            grade = random.choice(quality_grades)
            quantity = Decimal(str(round(random.uniform(50, 500), 1)))
            moisture = Decimal(str(round(random.uniform(8, 18), 1)))
            price = Decimal(str(round(random.uniform(15, 80), 2)))

            txn = {
                'PK': f'FARMER#{farmer_id}',
                'SK': f'TXN#{timestamp}',
                'entity_type': 'Transaction',
                'transaction_id': str(uuid.uuid4())[:8],
                'farmer_id': farmer_id,
                'fpo_id': 'FPO001',
                'crop_type': crop,
                'quality_grade': grade,
                'quantity': quantity,
                'moisture': moisture,
                'price': price,
                'timestamp': timestamp,
                'date': txn_date.strftime('%Y-%m-%d'),
                'sync_status': 'SYNCED',
            }
            if _put_item_idempotent(txn):
                created += 1
            else:
                skipped += 1

    print(f"  Transactions: {created} created, {skipped} skipped across {len(farmers)} farmers")
    return created, skipped


def seed_credit_scores(farmers):
    """Seed credit scores for each farmer."""
    created, skipped = 0, 0
    for farmer in farmers:
        farmer_id = farmer['farmer_id']

        # Create 3 historical scores (showing improvement)
        base_score = random.randint(55, 70)
        for months_ago in [3, 1, 0]:
            score_date = (datetime.utcnow() - timedelta(days=months_ago * 30)).strftime('%Y-%m-%d')
            score = min(100, base_score + (3 - months_ago) * random.randint(3, 8))

            score_item = {
                'PK': f'FARMER#{farmer_id}',
                'SK': f'SCORE#{score_date}',
                'entity_type': 'CreditScore',
                'farmer_id': farmer_id,
                'total_score': score,
                'supply_consistency': Decimal(str(round(random.uniform(18, 28), 1))),
                'quality_metrics': Decimal(str(round(random.uniform(15, 23), 1))),
                'transaction_history': Decimal(str(round(random.uniform(12, 18), 1))),
                'financial_behavior': Decimal(str(round(random.uniform(8, 14), 1))),
                'operational_transparency': Decimal(str(round(random.uniform(5, 9), 1))),
                'calculation_date': score_date,
                'score_change': Decimal(str(round(random.uniform(-2, 8), 1))),
            }
            if _put_item_idempotent(score_item):
                created += 1
            else:
                skipped += 1

    print(f"  Credit Scores: {created} created, {skipped} skipped for {len(farmers)} farmers")
    return created, skipped


def seed_ndvi_data(farmers):
    """Seed satellite NDVI data for farmer locations."""
    stages = [
        ('EARLY', Decimal('0.30'), Decimal('0.92')),
        ('MID', Decimal('0.50'), Decimal('0.95')),
        ('LATE', Decimal('0.70'), Decimal('0.93')),
        ('HARVEST_READY', Decimal('0.85'), Decimal('0.96')),
    ]

    created, skipped = 0, 0
    for farmer in farmers:
        farmer_id = farmer['farmer_id']
        lat = farmer['gps_latitude']
        lon = farmer['gps_longitude']
        coords_hash = f"{lat}_{lon}"

        for i, (stage, ndvi, confidence) in enumerate(stages):
            days_ago = (len(stages) - i) * 15
            scan_date = (datetime.utcnow() - timedelta(days=days_ago)).isoformat()

            ndvi_item = {
                'PK': f'FIELD#{coords_hash}',
                'SK': f'NDVI#{scan_date}',
                'entity_type': 'NDVIResult',
                'farmer_id': farmer_id,
                'field_id': coords_hash,
                'gps_latitude': lat,
                'gps_longitude': lon,
                'ndvi_value': ndvi,
                'confidence': confidence,
                'maturity_stage': stage,
                'crop_type': 'onion',
                'scan_date': scan_date,
                'satellite_source': 'Sentinel-2',
            }
            if _put_item_idempotent(ndvi_item):
                created += 1
            else:
                skipped += 1

    print(f"  NDVI Data: {created} created, {skipped} skipped for {len(farmers)} farmers")
    return created, skipped


def main():
    print("Seeding KisanSetuData DynamoDB table...")
    print()

    total_created, total_skipped = 0, 0

    print("[1/5] Seeding FPO...")
    fpo, c, s = seed_fpo()
    total_created += c
    total_skipped += s

    print("[2/5] Seeding Farmers...")
    farmers, c, s = seed_farmers()
    total_created += c
    total_skipped += s

    print("[3/5] Seeding Transactions...")
    c, s = seed_transactions(farmers)
    total_created += c
    total_skipped += s

    print("[4/5] Seeding Credit Scores...")
    c, s = seed_credit_scores(farmers)
    total_created += c
    total_skipped += s

    print("[5/5] Seeding NDVI Data...")
    c, s = seed_ndvi_data(farmers)
    total_created += c
    total_skipped += s

    print()
    print(f"Seed complete! Created: {total_created}, Skipped: {total_skipped}")


if __name__ == '__main__':
    main()

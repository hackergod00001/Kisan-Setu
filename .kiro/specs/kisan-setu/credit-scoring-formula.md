# Credit Scoring Formula - Detailed Specification

## Overview

The Kisan-Setu credit scoring system generates a reliability score (0-100) for farmers based on their transaction history with the FPO. This score serves as an alternative credit score for farmers who lack traditional credit histories, making them bankable to financial institutions.

## Total Score Composition

**Total Score = 100 points**

```
Reliability Score = Supply Consistency (30)
                  + Quality Metrics (25)
                  + Transaction History (20)
                  + Financial Behavior (15)
                  + Operational Transparency (10)
```

## Component 1: Supply Consistency (30 points)

Measures how reliably the farmer delivers produce to the FPO.

### Sub-components:

#### 1.1 Delivery Frequency (10 points)
**Formula:**
```
Score = min(10, (actual_deliveries / expected_deliveries) * 10)
```

**Calculation:**
- Expected deliveries: Based on crop cycle and FPO agreements
- Actual deliveries: Count of completed deliveries in period
- Period: Rolling 12 months

**Example:**
- Expected: 24 deliveries/year (bi-weekly)
- Actual: 22 deliveries
- Score: (22/24) * 10 = 9.17 points

#### 1.2 Schedule Adherence (10 points)
**Formula:**
```
On_time_rate = on_time_deliveries / total_deliveries
Score = On_time_rate * 10
```

**Definition of "On-time":**
- Within ±2 days of committed delivery date
- Or within harvest window specified by FPO

**Example:**
- Total deliveries: 22
- On-time deliveries: 19
- Score: (19/22) * 10 = 8.64 points

#### 1.3 Fulfillment Rate (10 points)
**Formula:**
```
Fulfillment_rate = actual_quantity / committed_quantity
Score = min(10, Fulfillment_rate * 10)
```

**Calculation:**
- Committed quantity: Sum of all committed quantities
- Actual quantity: Sum of all delivered quantities
- Capped at 10 (over-delivery doesn't give extra points)

**Example:**
- Committed: 5000 kg over year
- Delivered: 4800 kg
- Score: (4800/5000) * 10 = 9.6 points

### Supply Consistency Total Example:
```
Delivery Frequency:    9.17
Schedule Adherence:    8.64
Fulfillment Rate:      9.60
─────────────────────────
Total:                27.41 / 30
```

## Component 2: Quality Metrics (25 points)

Measures the quality of produce delivered by the farmer.

### Sub-components:

#### 2.1 Moisture Level Consistency (10 points)
**Formula:**
```
Acceptable_rate = deliveries_within_moisture_range / total_deliveries
Score = Acceptable_rate * 10
```

**Moisture Ranges (crop-specific):**
- Onions: 12-15% (optimal)
- Wheat: 12-14% (optimal)
- Rice: 13-15% (optimal)

**Penalty for out-of-range:**
- 1-2% outside range: 50% credit
- >2% outside range: 0% credit

**Example:**
- Total deliveries: 22
- Within range: 20
- 1% outside range: 1
- >2% outside range: 1
- Score: ((20 * 1.0) + (1 * 0.5) + (1 * 0.0)) / 22 * 10 = 9.32 points

#### 2.2 Grade Consistency (10 points)
**Formula:**
```
Grade_score = (A_grade * 1.0 + B_grade * 0.7 + C_grade * 0.4) / total_deliveries
Score = Grade_score * 10
```

**Grade Definitions:**
- A-grade: Premium quality, no defects
- B-grade: Good quality, minor defects
- C-grade: Acceptable quality, visible defects

**Example:**
- A-grade deliveries: 15
- B-grade deliveries: 5
- C-grade deliveries: 2
- Total: 22
- Score: ((15*1.0) + (5*0.7) + (2*0.4)) / 22 * 10 = 8.50 points

#### 2.3 Rejection Rate (5 points)
**Formula:**
```
Acceptance_rate = (total_deliveries - rejected_deliveries) / total_deliveries
Score = Acceptance_rate * 5
```

**Rejection Reasons:**
- Quality below minimum standard
- Contamination or foreign matter
- Pest damage
- Incorrect variety

**Example:**
- Total deliveries: 22
- Rejected: 1
- Score: ((22-1)/22) * 5 = 4.77 points

### Quality Metrics Total Example:
```
Moisture Consistency:  9.32
Grade Consistency:     8.50
Rejection Rate:        4.77
─────────────────────────
Total:                22.59 / 25
```

## Component 3: Transaction History (20 points)

Measures the depth and breadth of the farmer's relationship with the FPO.

### Sub-components:

#### 3.1 Volume Score (7 points)
**Formula:**
```
Percentile = farmer_volume_rank / total_farmers_in_fpo
Score = Percentile * 7
```

**Calculation:**
- Rank farmers by total volume delivered (12 months)
- Convert rank to percentile
- Higher volume = higher score

**Example:**
- Farmer rank: 15 out of 100 farmers
- Percentile: 85th percentile
- Score: 0.85 * 7 = 5.95 points

#### 3.2 Relationship Length (7 points)
**Formula:**
```
Years = months_active / 12
Score = min(7, Years * 1.4)
```

**Calculation:**
- Months active: From first transaction to present
- Capped at 5 years (7 points)

**Example:**
- Months active: 36 months (3 years)
- Score: 3 * 1.4 = 4.2 points

#### 3.3 Transaction Success Rate (6 points)
**Formula:**
```
Success_rate = successful_transactions / total_transactions
Score = Success_rate * 6
```

**Successful Transaction:**
- Delivered as committed
- Accepted by FPO
- Payment settled

**Example:**
- Total transactions: 22
- Successful: 21
- Score: (21/22) * 6 = 5.73 points

### Transaction History Total Example:
```
Volume Score:          5.95
Relationship Length:   4.20
Success Rate:          5.73
─────────────────────────
Total:                15.88 / 20
```

## Component 4: Financial Behavior (15 points)

Measures the farmer's financial discipline and payment patterns.

### Sub-components:

#### 4.1 Payment Timeliness (10 points)
**Formula:**
```
On_time_payment_rate = on_time_payments / total_payments_due
Score = On_time_payment_rate * 10
```

**On-time Definition:**
- Payment received within agreed terms (e.g., 7 days)
- Or advance payment for inputs

**Example:**
- Total payments due: 20
- On-time payments: 18
- Score: (18/20) * 10 = 9.0 points

#### 4.2 Outstanding Dues (5 points)
**Formula:**
```
if outstanding_dues == 0:
    Score = 5
elif outstanding_dues <= 10% of annual_volume_value:
    Score = 3
elif outstanding_dues <= 25% of annual_volume_value:
    Score = 1
else:
    Score = 0
```

**Calculation:**
- Outstanding dues: Current unpaid balance
- Annual volume value: Total value of deliveries in 12 months

**Example:**
- Outstanding dues: ₹5,000
- Annual volume value: ₹100,000
- Percentage: 5%
- Score: 3 points

### Financial Behavior Total Example:
```
Payment Timeliness:    9.0
Outstanding Dues:      3.0
─────────────────────────
Total:                12.0 / 15
```

## Component 5: Operational Transparency (10 points)

Measures how actively the farmer engages with digital record-keeping.

### Sub-components:

#### 5.1 Digitization Frequency (5 points)
**Formula:**
```
Digitization_rate = digitized_transactions / total_transactions
Score = Digitization_rate * 5
```

**Digitized Transaction:**
- Photo of ledger uploaded
- Voice note recorded
- GPS location shared

**Example:**
- Total transactions: 22
- Digitized: 20
- Score: (20/22) * 5 = 4.55 points

#### 5.2 Documentation Completeness (5 points)
**Formula:**
```
Completeness = avg(field_completion_rates)
Score = Completeness * 5
```

**Required Fields:**
- Quantity
- Moisture level
- Price
- Date
- Crop variety

**Calculation:**
- For each transaction, calculate % of fields completed
- Average across all transactions

**Example:**
- Transaction 1: 5/5 fields = 100%
- Transaction 2: 4/5 fields = 80%
- Transaction 3: 5/5 fields = 100%
- Average: 93.3%
- Score: 0.933 * 5 = 4.67 points

### Operational Transparency Total Example:
```
Digitization Frequency:    4.55
Documentation Complete:    4.67
─────────────────────────────
Total:                     9.22 / 10
```

## Final Score Calculation

### Example Farmer: Ramesh Kumar

```
Component                          Score    Max
─────────────────────────────────────────────────
1. Supply Consistency             27.41    30
   - Delivery Frequency            9.17    10
   - Schedule Adherence            8.64    10
   - Fulfillment Rate              9.60    10

2. Quality Metrics                22.59    25
   - Moisture Consistency          9.32    10
   - Grade Consistency             8.50    10
   - Rejection Rate                4.77     5

3. Transaction History            15.88    20
   - Volume Score                  5.95     7
   - Relationship Length           4.20     7
   - Success Rate                  5.73     6

4. Financial Behavior             12.00    15
   - Payment Timeliness            9.00    10
   - Outstanding Dues              3.00     5

5. Operational Transparency        9.22    10
   - Digitization Frequency        4.55     5
   - Documentation Completeness    4.67     5

─────────────────────────────────────────────────
TOTAL RELIABILITY SCORE           87.10   100
─────────────────────────────────────────────────
```

### Score Interpretation

| Score Range | Rating | Interpretation | Loan Eligibility |
|-------------|--------|----------------|------------------|
| 90-100 | Excellent | Highly reliable, consistent quality | High-value loans |
| 75-89 | Good | Reliable, minor inconsistencies | Standard loans |
| 60-74 | Fair | Moderate reliability, some issues | Small loans |
| 40-59 | Poor | Significant reliability issues | Micro-loans only |
| 0-39 | Very Poor | Unreliable, major issues | Not eligible |

**Ramesh Kumar's Score: 87.10 (Good)**
- Eligible for standard loans
- Recommended loan amount: Up to 50% of annual volume value
- Interest rate: Standard FPO rate

## Score Change Notifications

### Trigger Conditions

A notification is sent to the FPO manager when:
1. Score changes by >10 points (up or down)
2. Score crosses a rating boundary (e.g., Fair → Good)
3. Score drops below 60 (loan eligibility threshold)

### Notification Format

```
📊 Credit Score Update: Ramesh Kumar

Previous Score: 75.30 (Good)
Current Score:  87.10 (Good)
Change:        +11.80 points ⬆️

Key Improvements:
✅ Supply Consistency: +8.5 points
   - Better schedule adherence
   - Higher fulfillment rate

✅ Quality Metrics: +3.3 points
   - Improved moisture consistency

Recommendation: Eligible for increased loan limit
```

## Data Requirements

### Minimum Data for Score Calculation

To generate a reliable credit score, the system requires:

1. **Minimum Transaction History:**
   - At least 6 transactions
   - Spanning at least 3 months
   - At least 3 different transaction dates

2. **Required Fields per Transaction:**
   - Quantity (mandatory)
   - Date (mandatory)
   - Price (mandatory)
   - Quality grade (optional, defaults to B)
   - Moisture level (optional, defaults to acceptable)

3. **Farmer Profile:**
   - Join date
   - FPO membership
   - Contact information

### Handling Insufficient Data

If minimum data requirements are not met:
```
Score = null
Status = "Insufficient Data"
Message = "Minimum 6 transactions over 3 months required"
```

## Score Recalculation Frequency

### Automatic Recalculation Triggers:
1. New transaction added
2. Payment received
3. Monthly batch recalculation (1st of month)
4. Manual request by FPO manager

### Calculation Performance:
- Target latency: <200ms
- Strategy: Pre-compute components, cache for 24 hours
- Invalidate cache on new transaction

## Implementation Notes

### Database Schema

```python
# DynamoDB Item
{
    "PK": "FARMER#123",
    "SK": "SCORE#2024-01-15",
    "total_score": 87.10,
    "supply_consistency": 27.41,
    "quality_metrics": 22.59,
    "transaction_history": 15.88,
    "financial_behavior": 12.00,
    "operational_transparency": 9.22,
    "calculation_date": "2024-01-15T10:30:00Z",
    "previous_score": 75.30,
    "score_change": 11.80,
    "rating": "Good",
    "transactions_analyzed": 22,
    "data_period_months": 12
}
```

### API Endpoint

```python
GET /api/v1/farmers/{farmer_id}/credit-score

Response:
{
    "farmer_id": "FARMER#123",
    "farmer_name": "Ramesh Kumar",
    "total_score": 87.10,
    "rating": "Good",
    "components": {
        "supply_consistency": {
            "score": 27.41,
            "max": 30,
            "breakdown": {
                "delivery_frequency": 9.17,
                "schedule_adherence": 8.64,
                "fulfillment_rate": 9.60
            }
        },
        // ... other components
    },
    "loan_eligibility": {
        "eligible": true,
        "max_loan_amount": 50000,
        "recommended_interest_rate": 8.5
    },
    "calculation_date": "2024-01-15T10:30:00Z",
    "data_period": "2023-01-15 to 2024-01-15"
}
```

## Validation & Testing

### Property-Based Tests

**Property: Score Bounds**
```python
For any farmer with valid transaction history:
    0 <= total_score <= 100
    0 <= supply_consistency <= 30
    0 <= quality_metrics <= 25
    0 <= transaction_history <= 20
    0 <= financial_behavior <= 15
    0 <= operational_transparency <= 10
```

**Property: Score Composition**
```python
For any farmer with valid transaction history:
    total_score == (supply_consistency + quality_metrics + 
                   transaction_history + financial_behavior + 
                   operational_transparency)
    (within 0.01 floating point tolerance)
```

### Unit Tests

Test cases for edge conditions:
- Farmer with zero transactions
- Farmer with perfect record (100 score)
- Farmer with all rejections (low score)
- Farmer with missing optional fields
- Farmer with negative payment history

## Future Enhancements

### Phase 2 Additions:
1. **Satellite Data Integration:**
   - Add crop health score (5 points)
   - Adjust total to 105 points, normalize to 100

2. **Market Behavior:**
   - Price acceptance rate
   - Flexibility on delivery timing

3. **Social Factors:**
   - Peer recommendations
   - Community standing

### Machine Learning Enhancement:
- Train ML model to predict default risk
- Use credit score as one feature among many
- Improve accuracy over rule-based system

"""
Credit Calculator Lambda
Calculates farmer reliability scores based on transaction history
"""

import json
import boto3
import os
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Optional
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from common.models import ReliabilityScore

# AWS clients
dynamodb = boto3.resource('dynamodb')

# Environment variables
DYNAMODB_TABLE = os.environ.get('DYNAMODB_TABLE', 'KisanSetuData')
REGION = os.environ.get('REGION', 'ap-south-1')

table = dynamodb.Table(DYNAMODB_TABLE)


class CreditEngine:
    """
    Credit Engine Component for calculating farmer reliability scores.
    
    Calculates scores (0-100) based on:
    - Supply consistency (0-30 points)
    - Quality metrics (0-25 points)
    - Transaction history (0-20 points)
    - Financial behavior (0-15 points)
    - Operational transparency (0-10 points)
    """
    
    def __init__(self, dynamodb_table):
        """Initialize Credit Engine with DynamoDB table."""
        self.table = dynamodb_table
    
    def calculate_reliability_score(self, farmer_id: str) -> ReliabilityScore:
        """
        Calculate 0-100 reliability score based on transaction history.
        
        Args:
            farmer_id: Unique identifier for the farmer
            
        Returns:
            ReliabilityScore with total_score and component_breakdown
        """
        # Get farmer transactions
        transactions = self._get_farmer_transactions(farmer_id)
        
        # Get previous score for change detection
        previous_score = self._get_previous_score(farmer_id)
        
        # Calculate component scores
        supply_consistency = self.calculate_supply_consistency(farmer_id, transactions)
        quality_metrics = self.calculate_quality_metrics(farmer_id, transactions)
        transaction_history = self.calculate_transaction_history(farmer_id, transactions)
        financial_behavior = self.calculate_financial_behavior(farmer_id, transactions)
        operational_transparency = self.calculate_operational_transparency(farmer_id, transactions)
        
        # Calculate total score
        total_score = (
            supply_consistency +
            quality_metrics +
            transaction_history +
            financial_behavior +
            operational_transparency
        )
        
        # Calculate score change
        score_change = 0.0
        if previous_score:
            score_change = total_score - previous_score
        
        # Create ReliabilityScore object
        reliability_score = ReliabilityScore(
            farmer_id=farmer_id,
            total_score=total_score,
            supply_consistency=supply_consistency,
            quality_metrics=quality_metrics,
            transaction_history=transaction_history,
            financial_behavior=financial_behavior,
            operational_transparency=operational_transparency,
            calculation_date=datetime.utcnow(),
            score_change=score_change
        )
        
        # Store score in DynamoDB
        self._store_score(reliability_score)
        
        # Check for significant change (>10 points)
        if abs(score_change) > 10:
            self._notify_significant_change(reliability_score)
        
        return reliability_score
    
    def calculate_supply_consistency(self, farmer_id: str, transactions: Optional[List[Dict]] = None) -> float:
        """
        Calculate supply consistency score (0-30 points).
        
        Based on: delivery frequency, schedule adherence, fulfillment rate
        
        Args:
            farmer_id: Unique identifier for the farmer
            transactions: Optional list of transactions (fetched if not provided)
            
        Returns:
            Score out of 30
        """
        if transactions is None:
            transactions = self._get_farmer_transactions(farmer_id)
        
        if not transactions:
            return 0.0
        
        # Calculate delivery frequency (transactions per month)
        frequency_score = self._calculate_frequency_score(transactions)
        
        # Calculate schedule adherence (consistency of delivery intervals)
        adherence_score = self._calculate_adherence_score(transactions)
        
        # Calculate fulfillment rate (successful vs total transactions)
        fulfillment_score = self._calculate_fulfillment_score(transactions)
        
        # Weighted combination: 40% frequency, 40% adherence, 20% fulfillment
        total = (frequency_score * 0.4 + adherence_score * 0.4 + fulfillment_score * 0.2)
        
        return min(30.0, total)
    
    def calculate_quality_metrics(self, farmer_id: str, transactions: Optional[List[Dict]] = None) -> float:
        """
        Calculate quality metrics score (0-25 points).
        
        Based on: moisture levels, grade consistency, rejection rates
        
        Args:
            farmer_id: Unique identifier for the farmer
            transactions: Optional list of transactions (fetched if not provided)
            
        Returns:
            Score out of 25
        """
        if transactions is None:
            transactions = self._get_farmer_transactions(farmer_id)
        
        if not transactions:
            return 0.0
        
        # Calculate moisture level score (optimal: <15%)
        moisture_score = self._calculate_moisture_score(transactions)
        
        # Calculate grade consistency score
        grade_score = self._calculate_grade_consistency_score(transactions)
        
        # Calculate rejection rate score (lower is better)
        rejection_score = self._calculate_rejection_score(transactions)
        
        # Weighted combination: 40% moisture, 40% grade, 20% rejection
        total = (moisture_score * 0.4 + grade_score * 0.4 + rejection_score * 0.2)
        
        return min(25.0, total)
    
    def calculate_transaction_history(self, farmer_id: str, transactions: Optional[List[Dict]] = None) -> float:
        """
        Calculate transaction history score (0-20 points).
        
        Based on: volume, relationship length, successful transactions
        
        Args:
            farmer_id: Unique identifier for the farmer
            transactions: Optional list of transactions (fetched if not provided)
            
        Returns:
            Score out of 20
        """
        if transactions is None:
            transactions = self._get_farmer_transactions(farmer_id)
        
        if not transactions:
            return 0.0
        
        # Calculate volume score
        volume_score = self._calculate_volume_score(transactions)
        
        # Calculate relationship length score
        relationship_score = self._calculate_relationship_score(transactions)
        
        # Calculate successful transaction ratio
        success_score = self._calculate_success_score(transactions)
        
        # Weighted combination: 40% volume, 30% relationship, 30% success
        total = (volume_score * 0.4 + relationship_score * 0.3 + success_score * 0.3)
        
        return min(20.0, total)
    
    def calculate_financial_behavior(self, farmer_id: str, transactions: Optional[List[Dict]] = None) -> float:
        """
        Calculate financial behavior score (0-15 points).
        
        Based on: payment patterns, outstanding dues
        
        Args:
            farmer_id: Unique identifier for the farmer
            transactions: Optional list of transactions (fetched if not provided)
            
        Returns:
            Score out of 15
        """
        if transactions is None:
            transactions = self._get_farmer_transactions(farmer_id)
        
        if not transactions:
            return 0.0
        
        # Calculate payment timeliness score
        payment_score = self._calculate_payment_score(transactions)
        
        # Calculate outstanding dues score
        dues_score = self._calculate_dues_score(farmer_id)
        
        # Weighted combination: 70% payment, 30% dues
        total = (payment_score * 0.7 + dues_score * 0.3)
        
        return min(15.0, total)
    
    def calculate_operational_transparency(self, farmer_id: str, transactions: Optional[List[Dict]] = None) -> float:
        """
        Calculate operational transparency score (0-10 points).
        
        Based on: digitization frequency, documentation completeness
        
        Args:
            farmer_id: Unique identifier for the farmer
            transactions: Optional list of transactions (fetched if not provided)
            
        Returns:
            Score out of 10
        """
        if transactions is None:
            transactions = self._get_farmer_transactions(farmer_id)
        
        if not transactions:
            return 0.0
        
        # Calculate digitization frequency score
        digitization_score = self._calculate_digitization_score(transactions)
        
        # Calculate documentation completeness score
        completeness_score = self._calculate_completeness_score(transactions)
        
        # Weighted combination: 50% digitization, 50% completeness
        total = (digitization_score * 0.5 + completeness_score * 0.5)
        
        return min(10.0, total)
    
    # Private helper methods
    
    def _ensure_pk_prefix(self, farmer_id: str) -> str:
        """Ensure farmer_id has the FARMER# prefix for DynamoDB queries."""
        if farmer_id.startswith('FARMER#'):
            return farmer_id
        return f'FARMER#{farmer_id}'

    def _get_farmer_transactions(self, farmer_id: str) -> List[Dict]:
        """Get all transactions for a farmer."""
        try:
            pk = self._ensure_pk_prefix(farmer_id)
            result = self.table.query(
                KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
                ExpressionAttributeValues={
                    ':pk': pk,
                    ':sk': 'TXN#'
                }
            )
            return result.get('Items', [])
        except Exception as e:
            print(f"Error fetching transactions: {str(e)}")
            return []

    def _get_previous_score(self, farmer_id: str) -> Optional[float]:
        """Get the most recent score for a farmer."""
        try:
            pk = self._ensure_pk_prefix(farmer_id)
            result = self.table.query(
                KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
                ExpressionAttributeValues={
                    ':pk': pk,
                    ':sk': 'SCORE#'
                },
                ScanIndexForward=False,  # Descending order
                Limit=1
            )
            items = result.get('Items', [])
            if items:
                return float(items[0].get('total_score', 0))
            return None
        except Exception as e:
            print(f"Error fetching previous score: {str(e)}")
            return None

    def _store_score(self, score: ReliabilityScore):
        """Store reliability score in DynamoDB."""
        try:
            pk = self._ensure_pk_prefix(score.farmer_id)
            score_data = {
                'PK': pk,
                'SK': f"SCORE#{score.calculation_date.date().isoformat()}",
                'total_score': Decimal(str(score.total_score)),
                'supply_consistency': Decimal(str(score.supply_consistency)),
                'quality_metrics': Decimal(str(score.quality_metrics)),
                'transaction_history': Decimal(str(score.transaction_history)),
                'financial_behavior': Decimal(str(score.financial_behavior)),
                'operational_transparency': Decimal(str(score.operational_transparency)),
                'score_change': Decimal(str(score.score_change)),
                'calculation_date': score.calculation_date.isoformat()
            }
            self.table.put_item(Item=score_data)
        except Exception as e:
            print(f"Error storing score: {str(e)}")
    
    def _notify_significant_change(self, score: ReliabilityScore):
        """Notify FPO manager of significant score change (>10 points)."""
        print(f"SIGNIFICANT SCORE CHANGE: Farmer {score.farmer_id} score changed by {score.score_change:.2f} points")
        print(f"New score: {score.total_score:.2f}")

        try:
            sns_topic_arn = os.environ.get('SNS_ALERT_TOPIC_ARN')
            if sns_topic_arn:
                sns_client = boto3.client('sns')
                direction = "increased" if score.score_change > 0 else "decreased"
                sns_client.publish(
                    TopicArn=sns_topic_arn,
                    Subject=f"Credit Score Alert - Farmer {score.farmer_id}",
                    Message=(
                        f"Significant credit score change detected.\n\n"
                        f"Farmer ID: {score.farmer_id}\n"
                        f"New Score: {score.total_score:.1f}/100\n"
                        f"Change: {direction} by {abs(score.score_change):.1f} points\n"
                        f"Rating: {get_rating(score.total_score)}\n\n"
                        f"Breakdown:\n"
                        f"  Supply Consistency: {score.supply_consistency:.1f}/30\n"
                        f"  Quality Metrics: {score.quality_metrics:.1f}/25\n"
                        f"  Transaction History: {score.transaction_history:.1f}/20\n"
                        f"  Financial Behavior: {score.financial_behavior:.1f}/15\n"
                        f"  Operational Transparency: {score.operational_transparency:.1f}/10"
                    )
                )
        except Exception as sns_err:
            print(f"Failed to send SNS notification: {sns_err}")
    
    # Component calculation helpers
    
    def _calculate_frequency_score(self, transactions: List[Dict]) -> float:
        """Calculate delivery frequency score (0-12 points)."""
        if not transactions:
            return 0.0
        
        # Calculate average transactions per month
        if len(transactions) < 2:
            return 6.0  # Minimum score for having any transactions
        
        # Get date range
        dates = [datetime.fromisoformat(t['timestamp']) for t in transactions if 'timestamp' in t]
        if not dates:
            return 6.0
        
        date_range = (max(dates) - min(dates)).days
        if date_range == 0:
            return 6.0
        
        months = date_range / 30.0
        txn_per_month = len(transactions) / max(months, 1)
        
        # Score based on frequency
        if txn_per_month >= 4:  # Weekly or more
            return 12.0
        elif txn_per_month >= 2:  # Bi-weekly
            return 10.0
        elif txn_per_month >= 1:  # Monthly
            return 8.0
        else:
            return 6.0
    
    def _calculate_adherence_score(self, transactions: List[Dict]) -> float:
        """Calculate schedule adherence score (0-12 points)."""
        if len(transactions) < 3:
            return 6.0  # Minimum score
        
        # Calculate consistency of intervals between transactions
        dates = sorted([datetime.fromisoformat(t['timestamp']) for t in transactions if 'timestamp' in t])
        if len(dates) < 3:
            return 6.0
        
        intervals = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
        if not intervals:
            return 6.0
        
        # Calculate coefficient of variation (lower is better)
        avg_interval = sum(intervals) / len(intervals)
        if avg_interval == 0:
            return 6.0
        
        variance = sum((x - avg_interval) ** 2 for x in intervals) / len(intervals)
        std_dev = variance ** 0.5
        cv = std_dev / avg_interval
        
        # Score based on consistency (lower CV = higher score)
        if cv < 0.2:  # Very consistent
            return 12.0
        elif cv < 0.4:  # Consistent
            return 10.0
        elif cv < 0.6:  # Moderately consistent
            return 8.0
        else:
            return 6.0
    
    def _calculate_fulfillment_score(self, transactions: List[Dict]) -> float:
        """Calculate fulfillment rate score (0-6 points)."""
        if not transactions:
            return 0.0
        
        # Assume all transactions are fulfilled unless marked otherwise
        fulfilled = sum(1 for t in transactions if t.get('status', 'fulfilled') == 'fulfilled')
        fulfillment_rate = fulfilled / len(transactions)
        
        return 6.0 * fulfillment_rate
    
    def _calculate_moisture_score(self, transactions: List[Dict]) -> float:
        """Calculate moisture level score (0-10 points)."""
        if not transactions:
            return 0.0
        
        # Count transactions with optimal moisture (<15%)
        optimal_count = sum(1 for t in transactions if float(t.get('moisture', 100)) < 15)
        optimal_rate = optimal_count / len(transactions)
        
        return 10.0 * optimal_rate
    
    def _calculate_grade_consistency_score(self, transactions: List[Dict]) -> float:
        """Calculate grade consistency score (0-10 points)."""
        if not transactions:
            return 0.0
        
        # Count high-grade transactions (A or B)
        high_grade_count = sum(1 for t in transactions if t.get('quality_grade', '') in ['A', 'B'])
        high_grade_rate = high_grade_count / len(transactions)
        
        return 10.0 * high_grade_rate
    
    def _calculate_rejection_score(self, transactions: List[Dict]) -> float:
        """Calculate rejection rate score (0-5 points)."""
        if not transactions:
            return 0.0
        
        # Assume no rejections unless marked
        rejected = sum(1 for t in transactions if t.get('rejected', False))
        rejection_rate = rejected / len(transactions)
        
        # Lower rejection rate = higher score
        return 5.0 * (1 - rejection_rate)
    
    def _calculate_volume_score(self, transactions: List[Dict]) -> float:
        """Calculate volume score (0-8 points)."""
        if not transactions:
            return 0.0
        
        total_quantity = sum(float(t.get('quantity', 0)) for t in transactions)
        
        # Score based on total volume
        if total_quantity >= 10000:
            return 8.0
        elif total_quantity >= 5000:
            return 6.5
        elif total_quantity >= 2000:
            return 5.0
        elif total_quantity >= 1000:
            return 3.5
        else:
            return 2.0
    
    def _calculate_relationship_score(self, transactions: List[Dict]) -> float:
        """Calculate relationship length score (0-6 points)."""
        if not transactions:
            return 0.0
        
        # Get date range
        dates = [datetime.fromisoformat(t['timestamp']) for t in transactions if 'timestamp' in t]
        if not dates:
            return 0.0
        
        relationship_days = (max(dates) - min(dates)).days
        relationship_months = relationship_days / 30.0
        
        # Score based on relationship length
        if relationship_months >= 24:  # 2+ years
            return 6.0
        elif relationship_months >= 12:  # 1+ year
            return 5.0
        elif relationship_months >= 6:  # 6+ months
            return 4.0
        elif relationship_months >= 3:  # 3+ months
            return 3.0
        else:
            return 2.0
    
    def _calculate_success_score(self, transactions: List[Dict]) -> float:
        """Calculate successful transaction ratio score (0-6 points)."""
        if not transactions:
            return 0.0
        
        # Assume all transactions are successful unless marked otherwise
        successful = sum(1 for t in transactions if t.get('status', 'success') == 'success')
        success_rate = successful / len(transactions)
        
        return 6.0 * success_rate
    
    def _calculate_payment_score(self, transactions: List[Dict]) -> float:
        """Calculate payment timeliness score (0-10.5 points)."""
        if not transactions:
            return 0.0
        
        # Assume timely payments unless marked otherwise
        timely = sum(1 for t in transactions if t.get('payment_status', 'timely') == 'timely')
        timely_rate = timely / len(transactions)
        
        return 10.5 * timely_rate
    
    def _calculate_dues_score(self, farmer_id: str) -> float:
        """Calculate outstanding dues score (0-4.5 points)."""
        # TODO: Query for outstanding dues
        # For now, assume no outstanding dues
        return 4.5
    
    def _calculate_digitization_score(self, transactions: List[Dict]) -> float:
        """Calculate digitization frequency score (0-5 points)."""
        if not transactions:
            return 0.0
        
        # Count transactions with ledger images
        digitized = sum(1 for t in transactions if t.get('ledger_image_url'))
        digitization_rate = digitized / len(transactions)
        
        return 5.0 * digitization_rate
    
    def _calculate_completeness_score(self, transactions: List[Dict]) -> float:
        """Calculate documentation completeness score (0-5 points)."""
        if not transactions:
            return 0.0
        
        # Check if all key fields are present
        complete_records = 0
        required_fields = ['quantity', 'price', 'crop_type', 'moisture', 'quality_grade']
        
        for txn in transactions:
            if all(txn.get(field) for field in required_fields):
                complete_records += 1
        
        completeness_rate = complete_records / len(transactions)
        
        return 5.0 * completeness_rate


def handler(event, context):
    """Calculate reliability score for a farmer"""
    
    try:
        print(f"Calculating credit score: {json.dumps(event)}")
        
        # Parse request — support both API Gateway (body as JSON string) and direct Lambda invocation
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event
        farmer_id = body.get('farmer_id')
        
        if not farmer_id:
            return response(400, {'error': 'farmer_id required'})
        
        # Initialize Credit Engine
        credit_engine = CreditEngine(table)
        
        # Calculate reliability score
        reliability_score = credit_engine.calculate_reliability_score(farmer_id)
        
        # Determine rating
        rating = get_rating(reliability_score.total_score)
        
        return response(200, {
            'farmer_id': reliability_score.farmer_id,
            'total_score': float(reliability_score.total_score),
            'rating': rating,
            'score_change': float(reliability_score.score_change),
            'breakdown': {
                'supply_consistency': float(reliability_score.supply_consistency),
                'quality_metrics': float(reliability_score.quality_metrics),
                'transaction_history': float(reliability_score.transaction_history),
                'financial_behavior': float(reliability_score.financial_behavior),
                'operational_transparency': float(reliability_score.operational_transparency)
            },
            'calculation_date': reliability_score.calculation_date.isoformat()
        })
    
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return response(500, {'error': str(e)})


def get_rating(score: float) -> str:
    """Convert score to rating"""
    
    if score >= 90:
        return 'Excellent'
    elif score >= 75:
        return 'Good'
    elif score >= 60:
        return 'Fair'
    elif score >= 40:
        return 'Poor'
    else:
        return 'Very Poor'


def response(status_code: int, body: Any) -> Dict[str, Any]:
    """Format API Gateway response"""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps(body, default=str)
    }

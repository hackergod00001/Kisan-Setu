"""
Unit tests for Credit Engine Component.

Tests the CreditEngine class and its component calculation methods.
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# Add lambda directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))

from credit.credit import CreditEngine, get_rating
from common.models import ReliabilityScore


@pytest.fixture
def mock_table():
    """Create a mock DynamoDB table."""
    return Mock()


@pytest.fixture
def credit_engine(mock_table):
    """Create a CreditEngine instance with mock table."""
    return CreditEngine(mock_table)


@pytest.fixture
def sample_transactions():
    """Create sample transaction data."""
    base_date = datetime.utcnow()
    return [
        {
            'PK': 'FARMER#123',
            'SK': f'TXN#{(base_date - timedelta(days=90)).isoformat()}',
            'quantity': 500.0,
            'moisture': 12.0,
            'quality_grade': 'A',
            'price': 25000.0,
            'crop_type': 'onion',
            'timestamp': (base_date - timedelta(days=90)).isoformat(),
            'ledger_image_url': 's3://bucket/image1.jpg',
            'status': 'completed',
            'payment_status': 'timely'
        },
        {
            'PK': 'FARMER#123',
            'SK': f'TXN#{(base_date - timedelta(days=60)).isoformat()}',
            'quantity': 600.0,
            'moisture': 14.0,
            'quality_grade': 'A',
            'price': 30000.0,
            'crop_type': 'onion',
            'timestamp': (base_date - timedelta(days=60)).isoformat(),
            'ledger_image_url': 's3://bucket/image2.jpg',
            'status': 'completed',
            'payment_status': 'timely'
        },
        {
            'PK': 'FARMER#123',
            'SK': f'TXN#{(base_date - timedelta(days=30)).isoformat()}',
            'quantity': 550.0,
            'moisture': 13.5,
            'quality_grade': 'B',
            'price': 27500.0,
            'crop_type': 'onion',
            'timestamp': (base_date - timedelta(days=30)).isoformat(),
            'ledger_image_url': 's3://bucket/image3.jpg',
            'status': 'completed',
            'payment_status': 'timely'
        }
    ]


class TestCreditEngine:
    """Test suite for CreditEngine class."""
    
    def test_calculate_reliability_score_returns_score_object(self, credit_engine, mock_table, sample_transactions):
        """Test that calculate_reliability_score returns a ReliabilityScore object."""
        mock_table.query.return_value = {'Items': sample_transactions}
        mock_table.put_item.return_value = {}
        
        result = credit_engine.calculate_reliability_score('FARMER#123')
        
        assert isinstance(result, ReliabilityScore)
        assert result.farmer_id == 'FARMER#123'
        assert 0 <= result.total_score <= 100
    
    def test_calculate_reliability_score_components_sum_to_total(self, credit_engine, mock_table, sample_transactions):
        """Test that component scores sum to total score."""
        mock_table.query.return_value = {'Items': sample_transactions}
        mock_table.put_item.return_value = {}
        
        result = credit_engine.calculate_reliability_score('FARMER#123')
        
        component_sum = (
            result.supply_consistency +
            result.quality_metrics +
            result.transaction_history +
            result.financial_behavior +
            result.operational_transparency
        )
        
        assert abs(result.total_score - component_sum) < 0.01
    
    def test_calculate_reliability_score_stores_in_dynamodb(self, credit_engine, mock_table, sample_transactions):
        """Test that reliability score is stored in DynamoDB."""
        mock_table.query.return_value = {'Items': sample_transactions}
        mock_table.put_item.return_value = {}
        
        credit_engine.calculate_reliability_score('FARMER#123')
        
        # Verify put_item was called
        assert mock_table.put_item.called
        call_args = mock_table.put_item.call_args[1]
        item = call_args['Item']
        
        assert item['PK'] == 'FARMER#123'
        assert item['SK'].startswith('SCORE#')
        assert 'total_score' in item
        assert 'supply_consistency' in item
    
    def test_calculate_reliability_score_detects_significant_change(self, credit_engine, mock_table, sample_transactions):
        """Test that significant score changes (>10 points) are detected."""
        # First query returns previous score
        # Second query returns transactions
        mock_table.query.side_effect = [
            {'Items': [{'total_score': Decimal('50.0')}]},  # Previous score
            {'Items': sample_transactions}  # Transactions
        ]
        mock_table.put_item.return_value = {}
        
        with patch.object(credit_engine, '_notify_significant_change') as mock_notify:
            result = credit_engine.calculate_reliability_score('FARMER#123')
            
            # If score changed by >10 points, notification should be called
            if abs(result.score_change) > 10:
                assert mock_notify.called
    
    def test_calculate_supply_consistency_range(self, credit_engine, sample_transactions):
        """Test that supply consistency score is within 0-30 range."""
        score = credit_engine.calculate_supply_consistency('FARMER#123', sample_transactions)
        
        assert 0 <= score <= 30
    
    def test_calculate_supply_consistency_empty_transactions(self, credit_engine):
        """Test supply consistency with no transactions."""
        score = credit_engine.calculate_supply_consistency('FARMER#123', [])
        
        assert score == 0.0
    
    def test_calculate_quality_metrics_range(self, credit_engine, sample_transactions):
        """Test that quality metrics score is within 0-25 range."""
        score = credit_engine.calculate_quality_metrics('FARMER#123', sample_transactions)
        
        assert 0 <= score <= 25
    
    def test_calculate_quality_metrics_optimal_moisture(self, credit_engine):
        """Test quality metrics with optimal moisture levels."""
        transactions = [
            {
                'moisture': 12.0,
                'quality_grade': 'A',
                'timestamp': datetime.utcnow().isoformat()
            },
            {
                'moisture': 13.0,
                'quality_grade': 'A',
                'timestamp': datetime.utcnow().isoformat()
            }
        ]
        
        score = credit_engine.calculate_quality_metrics('FARMER#123', transactions)
        
        # Should get high score for optimal moisture and grade
        # Score is weighted: 40% moisture + 40% grade + 20% rejection
        # With optimal moisture and grade, expect around 9-10 points
        assert score > 8
    
    def test_calculate_transaction_history_range(self, credit_engine, sample_transactions):
        """Test that transaction history score is within 0-20 range."""
        score = credit_engine.calculate_transaction_history('FARMER#123', sample_transactions)
        
        assert 0 <= score <= 20
    
    def test_calculate_transaction_history_high_volume(self, credit_engine):
        """Test transaction history with high volume."""
        transactions = [
            {
                'quantity': 5000.0,
                'timestamp': datetime.utcnow().isoformat(),
                'status': 'completed'
            },
            {
                'quantity': 6000.0,
                'timestamp': datetime.utcnow().isoformat(),
                'status': 'completed'
            }
        ]
        
        score = credit_engine.calculate_transaction_history('FARMER#123', transactions)
        
        # High volume (11000 total) should give good score
        # Score is weighted: 40% volume + 30% relationship + 30% success
        # With 11000 volume, expect around 5-6 points
        assert score > 5
    
    def test_calculate_financial_behavior_range(self, credit_engine, mock_table, sample_transactions):
        """Test that financial behavior score is within 0-15 range."""
        # _calculate_dues_score now queries DynamoDB, so set up the mock
        mock_table.query.return_value = {'Items': sample_transactions}
        score = credit_engine.calculate_financial_behavior('FARMER#123', sample_transactions)
        
        assert 0 <= score <= 15
    
    def test_calculate_operational_transparency_range(self, credit_engine, sample_transactions):
        """Test that operational transparency score is within 0-10 range."""
        score = credit_engine.calculate_operational_transparency('FARMER#123', sample_transactions)
        
        assert 0 <= score <= 10
    
    def test_calculate_operational_transparency_complete_records(self, credit_engine):
        """Test operational transparency with complete records."""
        transactions = [
            {
                'quantity': 500.0,
                'price': 25000.0,
                'crop_type': 'onion',
                'moisture': 12.0,
                'quality_grade': 'A',
                'ledger_image_url': 's3://bucket/image.jpg',
                'timestamp': datetime.utcnow().isoformat()
            }
        ]
        
        score = credit_engine.calculate_operational_transparency('FARMER#123', transactions)
        
        # Complete records should give high score
        # Score is weighted: 50% digitization + 50% completeness
        # With complete record, expect 5 points (50% of 10)
        assert score >= 5


class TestRatingFunction:
    """Test suite for rating conversion function."""
    
    def test_get_rating_excellent(self):
        """Test rating for excellent score."""
        assert get_rating(95) == 'Excellent'
        assert get_rating(90) == 'Excellent'
    
    def test_get_rating_good(self):
        """Test rating for good score."""
        assert get_rating(85) == 'Good'
        assert get_rating(75) == 'Good'
    
    def test_get_rating_fair(self):
        """Test rating for fair score."""
        assert get_rating(65) == 'Fair'
        assert get_rating(60) == 'Fair'
    
    def test_get_rating_poor(self):
        """Test rating for poor score."""
        assert get_rating(50) == 'Poor'
        assert get_rating(40) == 'Poor'
    
    def test_get_rating_very_poor(self):
        """Test rating for very poor score."""
        assert get_rating(30) == 'Very Poor'
        assert get_rating(0) == 'Very Poor'


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_no_transactions(self, credit_engine, mock_table):
        """Test score calculation with no transactions."""
        mock_table.query.return_value = {'Items': []}
        mock_table.put_item.return_value = {}
        
        result = credit_engine.calculate_reliability_score('FARMER#123')
        
        assert result.total_score == 0.0
        assert result.supply_consistency == 0.0
        assert result.quality_metrics == 0.0
    
    def test_single_transaction(self, credit_engine, mock_table):
        """Test score calculation with single transaction."""
        transaction = [{
            'quantity': 500.0,
            'moisture': 12.0,
            'quality_grade': 'A',
            'price': 25000.0,
            'crop_type': 'onion',
            'timestamp': datetime.utcnow().isoformat(),
            'ledger_image_url': 's3://bucket/image.jpg',
            'status': 'completed',
            'payment_status': 'timely'
        }]
        
        mock_table.query.return_value = {'Items': transaction}
        mock_table.put_item.return_value = {}
        
        result = credit_engine.calculate_reliability_score('FARMER#123')
        
        assert result.total_score > 0
        assert 0 <= result.total_score <= 100
    
    def test_missing_optional_fields(self, credit_engine):
        """Test handling of transactions with missing optional fields."""
        transactions = [
            {
                'quantity': 500.0,
                'timestamp': datetime.utcnow().isoformat()
                # Missing moisture, quality_grade, etc.
            }
        ]
        
        # Should not raise exception
        score = credit_engine.calculate_quality_metrics('FARMER#123', transactions)
        assert score >= 0


class TestCalculateDuesScore:
    """Tests for the _calculate_dues_score method (Task 4.1.1 & 4.1.2)."""

    def test_dues_score_queries_dynamodb(self, credit_engine, mock_table):
        """Test that _calculate_dues_score queries DynamoDB instead of returning hardcoded value."""
        mock_table.query.return_value = {'Items': [
            {'payment_status': 'timely'},
            {'payment_status': 'timely'},
        ]}

        score = credit_engine._calculate_dues_score('FARMER#123')

        # Should have queried DynamoDB
        mock_table.query.assert_called_once()
        call_kwargs = mock_table.query.call_args[1]
        assert call_kwargs['ExpressionAttributeValues'][':pk'] == 'FARMER#123'
        assert call_kwargs['ExpressionAttributeValues'][':sk'] == 'TXN#'

    def test_dues_score_all_paid_returns_max(self, credit_engine, mock_table):
        """Test that all paid dues returns max score of 15.0."""
        mock_table.query.return_value = {'Items': [
            {'payment_status': 'timely'},
            {'payment_status': 'paid'},
            {'payment_status': 'timely'},
        ]}

        score = credit_engine._calculate_dues_score('F001')
        assert score == 15.0

    def test_dues_score_all_outstanding_returns_zero(self, credit_engine, mock_table):
        """Test that all outstanding dues returns 0."""
        mock_table.query.return_value = {'Items': [
            {'payment_status': 'overdue'},
            {'payment_status': 'pending'},
            {'payment_status': 'late'},
        ]}

        score = credit_engine._calculate_dues_score('F001')
        assert score == 0.0

    def test_dues_score_mixed_returns_proportional(self, credit_engine, mock_table):
        """Test that mixed paid/outstanding returns proportional score."""
        mock_table.query.return_value = {'Items': [
            {'payment_status': 'timely'},
            {'payment_status': 'overdue'},
            {'payment_status': 'paid'},
            {'payment_status': 'late'},
        ]}

        score = credit_engine._calculate_dues_score('F001')
        # 2 paid out of 4 = 50% => 15.0 * 0.5 = 7.5
        assert score == pytest.approx(7.5)

    def test_dues_score_no_records_returns_neutral(self, credit_engine, mock_table):
        """Test that no records returns neutral default score."""
        mock_table.query.return_value = {'Items': []}

        score = credit_engine._calculate_dues_score('F001')
        assert score == 7.5

    def test_dues_score_dynamodb_error_returns_neutral(self, credit_engine, mock_table):
        """Test that DynamoDB errors return neutral default score."""
        mock_table.query.side_effect = Exception("DynamoDB error")

        score = credit_engine._calculate_dues_score('F001')
        assert score == 7.5

    def test_dues_score_range(self, credit_engine, mock_table):
        """Test that dues score is always within 0-15.0 range."""
        mock_table.query.return_value = {'Items': [
            {'payment_status': 'timely'},
            {'payment_status': 'overdue'},
        ]}

        score = credit_engine._calculate_dues_score('F001')
        assert 0.0 <= score <= 15.0

    def test_dues_score_no_payment_status_treated_as_outstanding(self, credit_engine, mock_table):
        """Test that records without payment_status are treated as outstanding."""
        mock_table.query.return_value = {'Items': [
            {'quantity': 500},  # no payment_status
            {'payment_status': 'timely'},
        ]}

        score = credit_engine._calculate_dues_score('F001')
        # 1 paid out of 2 = 50% => 15.0 * 0.5 = 7.5
        assert score == pytest.approx(7.5)

    def test_dues_score_adds_farmer_prefix(self, credit_engine, mock_table):
        """Test that farmer_id without prefix gets FARMER# prefix added."""
        mock_table.query.return_value = {'Items': []}

        credit_engine._calculate_dues_score('F001')

        call_kwargs = mock_table.query.call_args[1]
        assert call_kwargs['ExpressionAttributeValues'][':pk'] == 'FARMER#F001'

    def test_dues_score_preserves_existing_prefix(self, credit_engine, mock_table):
        """Test that farmer_id with existing FARMER# prefix is not double-prefixed."""
        mock_table.query.return_value = {'Items': []}

        credit_engine._calculate_dues_score('FARMER#F001')

        call_kwargs = mock_table.query.call_args[1]
        assert call_kwargs['ExpressionAttributeValues'][':pk'] == 'FARMER#F001'

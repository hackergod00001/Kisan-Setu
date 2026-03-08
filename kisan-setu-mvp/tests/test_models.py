"""
Unit tests for data models.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))

import pytest
from datetime import datetime, date
from common.models import (
    Message, MessageType, LedgerData, NDVIResult, YieldPrediction,
    ReliabilityScore, Transaction, Farmer, FPO, AuditTrail,
    SyncStatus, MaturityStage
)


class TestMessage:
    """Tests for Message dataclass."""
    
    def test_create_message(self):
        """Test creating a message."""
        msg = Message(
            message_id="msg123",
            sender_id="user456",
            message_type=MessageType.TEXT,
            content="Hello",
            timestamp=datetime.now(),
            language="hi-IN"
        )
        assert msg.message_id == "msg123"
        assert msg.sender_id == "user456"
        assert msg.message_type == MessageType.TEXT
        assert msg.content == "Hello"
        assert msg.language == "hi-IN"
    
    def test_message_types(self):
        """Test different message types."""
        text_msg = Message("1", "u1", MessageType.TEXT, "text", datetime.now(), "hi-IN")
        voice_msg = Message("2", "u1", MessageType.VOICE, "url", datetime.now(), "hi-IN")
        image_msg = Message("3", "u1", MessageType.IMAGE, "url", datetime.now(), "hi-IN")
        
        assert text_msg.message_type == MessageType.TEXT
        assert voice_msg.message_type == MessageType.VOICE
        assert image_msg.message_type == MessageType.IMAGE


class TestLedgerData:
    """Tests for LedgerData dataclass."""
    
    def test_create_ledger_data(self):
        """Test creating ledger data."""
        ledger = LedgerData(
            ledger_id="ledger123",
            farmer_id="farmer456",
            quantity=100.0,
            moisture=12.5,
            price=5000.0,
            date=date.today(),
            crop_type="onion",
            confidence_scores={"quantity": 0.95, "moisture": 0.88},
            image_url="s3://bucket/image.jpg",
            fields_needing_review=["date"]
        )
        assert ledger.ledger_id == "ledger123"
        assert ledger.quantity == 100.0
        assert ledger.moisture == 12.5
        assert "quantity" in ledger.confidence_scores
        assert "date" in ledger.fields_needing_review


class TestNDVIResult:
    """Tests for NDVIResult dataclass."""
    
    def test_create_ndvi_result(self):
        """Test creating NDVI result."""
        ndvi = NDVIResult(
            field_id="field123",
            gps_coords=(28.6139, 77.2090),
            ndvi_value=0.75,
            timestamp=datetime.now(),
            confidence=0.92,
            satellite_image_url="s3://bucket/satellite.tif"
        )
        assert ndvi.field_id == "field123"
        assert ndvi.gps_coords == (28.6139, 77.2090)
        assert -1.0 <= ndvi.ndvi_value <= 1.0
        assert 0.0 <= ndvi.confidence <= 1.0


class TestYieldPrediction:
    """Tests for YieldPrediction dataclass."""
    
    def test_create_yield_prediction(self):
        """Test creating yield prediction."""
        prediction = YieldPrediction(
            field_id="field123",
            estimated_volume=500.0,
            confidence_interval=(450.0, 550.0),
            maturity_stage=MaturityStage.MID,
            prediction_date=datetime.now()
        )
        assert prediction.field_id == "field123"
        assert prediction.estimated_volume == 500.0
        assert prediction.confidence_interval[0] <= prediction.estimated_volume <= prediction.confidence_interval[1]
        assert prediction.maturity_stage == MaturityStage.MID
    
    def test_maturity_stages(self):
        """Test all maturity stages."""
        stages = [MaturityStage.EARLY, MaturityStage.MID, MaturityStage.LATE, MaturityStage.HARVEST_READY]
        for stage in stages:
            prediction = YieldPrediction("f1", 100.0, (90.0, 110.0), stage, datetime.now())
            assert prediction.maturity_stage == stage


class TestReliabilityScore:
    """Tests for ReliabilityScore dataclass."""
    
    def test_create_reliability_score(self):
        """Test creating reliability score."""
        score = ReliabilityScore(
            farmer_id="farmer123",
            total_score=75.0,
            supply_consistency=25.0,
            quality_metrics=20.0,
            transaction_history=15.0,
            financial_behavior=10.0,
            operational_transparency=5.0,
            calculation_date=datetime.now(),
            score_change=5.0
        )
        assert score.farmer_id == "farmer123"
        assert 0 <= score.total_score <= 100
        assert 0 <= score.supply_consistency <= 30
        assert 0 <= score.quality_metrics <= 25
        assert 0 <= score.transaction_history <= 20
        assert 0 <= score.financial_behavior <= 15
        assert 0 <= score.operational_transparency <= 10
    
    def test_score_composition(self):
        """Test that total score equals sum of components."""
        score = ReliabilityScore(
            farmer_id="farmer123",
            total_score=75.0,
            supply_consistency=25.0,
            quality_metrics=20.0,
            transaction_history=15.0,
            financial_behavior=10.0,
            operational_transparency=5.0,
            calculation_date=datetime.now(),
            score_change=0.0
        )
        expected_total = (score.supply_consistency + score.quality_metrics + 
                         score.transaction_history + score.financial_behavior + 
                         score.operational_transparency)
        assert abs(score.total_score - expected_total) < 0.01


class TestTransaction:
    """Tests for Transaction dataclass."""
    
    def test_create_transaction(self):
        """Test creating transaction."""
        txn = Transaction(
            transaction_id="txn123",
            farmer_id="farmer456",
            fpo_id="fpo789",
            quantity=100.0,
            crop_type="wheat",
            quality_grade="A",
            moisture=12.0,
            price=5000.0,
            timestamp=datetime.now(),
            ledger_image_url="s3://bucket/ledger.jpg",
            sync_status=SyncStatus.SYNCED
        )
        assert txn.transaction_id == "txn123"
        assert txn.farmer_id == "farmer456"
        assert txn.fpo_id == "fpo789"
        assert txn.sync_status == SyncStatus.SYNCED
    
    def test_sync_statuses(self):
        """Test different sync statuses."""
        statuses = [SyncStatus.SYNCED, SyncStatus.PENDING, SyncStatus.CONFLICT]
        for status in statuses:
            txn = Transaction("t1", "f1", "fpo1", 100.0, "wheat", "A", 12.0, 5000.0, 
                            datetime.now(), None, status)
            assert txn.sync_status == status


class TestFarmer:
    """Tests for Farmer dataclass."""
    
    def test_create_farmer(self):
        """Test creating farmer."""
        farmer = Farmer(
            farmer_id="farmer123",
            name="Ram Kumar",
            phone="+919876543210",
            fpo_id="fpo456",
            gps_coords=(28.6139, 77.2090),
            preferred_language="hi-IN",
            join_date=date.today()
        )
        assert farmer.farmer_id == "farmer123"
        assert farmer.name == "Ram Kumar"
        assert farmer.phone == "+919876543210"
        assert farmer.preferred_language == "hi-IN"


class TestFPO:
    """Tests for FPO dataclass."""
    
    def test_create_fpo(self):
        """Test creating FPO."""
        fpo = FPO(
            fpo_id="fpo123",
            name="Delhi Farmers Collective",
            location="Delhi",
            manager_contact="+919876543210",
            created_date=date.today(),
            member_count=150
        )
        assert fpo.fpo_id == "fpo123"
        assert fpo.name == "Delhi Farmers Collective"
        assert fpo.member_count == 150


class TestAuditTrail:
    """Tests for AuditTrail dataclass."""
    
    def test_create_audit_trail(self):
        """Test creating audit trail."""
        audit = AuditTrail(
            audit_id="audit123",
            entity_type="Farmer",
            entity_id="farmer456",
            operation="create",
            timestamp=datetime.now(),
            user_id="admin123",
            changed_fields={"name": "Ram Kumar", "phone": "+919876543210"},
            previous_values=None
        )
        assert audit.audit_id == "audit123"
        assert audit.entity_type == "Farmer"
        assert audit.operation == "create"
        assert "name" in audit.changed_fields
    
    def test_audit_with_previous_values(self):
        """Test audit trail with previous values."""
        audit = AuditTrail(
            audit_id="audit123",
            entity_type="Farmer",
            entity_id="farmer456",
            operation="update",
            timestamp=datetime.now(),
            user_id="admin123",
            changed_fields={"phone": "+919999999999"},
            previous_values={"phone": "+919876543210"}
        )
        assert audit.operation == "update"
        assert audit.previous_values is not None
        assert "phone" in audit.previous_values


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""
Core data models for Kisan-Setu system.

This module defines all dataclasses used across the system, matching the
DynamoDB single-table design with PK/SK patterns.
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional, Dict, List, Tuple
from enum import Enum


class MessageType(Enum):
    """Types of messages supported by the system."""
    TEXT = "text"
    VOICE = "voice"
    IMAGE = "image"


class SyncStatus(Enum):
    """Synchronization status for offline transactions."""
    SYNCED = "synced"
    PENDING = "pending"
    CONFLICT = "conflict"


class MaturityStage(Enum):
    """Crop maturity stages based on NDVI analysis."""
    EARLY = "early"
    MID = "mid"
    LATE = "late"
    HARVEST_READY = "harvest_ready"


@dataclass
class Message:
    """Represents a message from WhatsApp or other interfaces."""
    message_id: str
    sender_id: str
    message_type: MessageType
    content: str  # text or URL to audio/image
    timestamp: datetime
    language: str  # e.g., 'hi-IN', 'mr-IN', 'ta-IN'


@dataclass
class LedgerData:
    """Structured data extracted from handwritten ledger images."""
    ledger_id: str
    farmer_id: str
    quantity: float
    moisture: float
    price: float
    date: date
    crop_type: str
    confidence_scores: Dict[str, float]  # field_name -> confidence
    image_url: str
    fields_needing_review: List[str]


@dataclass
class NDVIResult:
    """NDVI calculation result from satellite imagery."""
    field_id: str
    gps_coords: Tuple[float, float]  # (latitude, longitude)
    ndvi_value: float  # -1.0 to 1.0
    timestamp: datetime
    confidence: float
    satellite_image_url: str


@dataclass
class YieldPrediction:
    """Crop yield prediction based on NDVI trends."""
    field_id: str
    estimated_volume: float
    confidence_interval: Tuple[float, float]  # (lower_bound, upper_bound)
    maturity_stage: MaturityStage
    prediction_date: datetime


@dataclass
class ReliabilityScore:
    """Farmer reliability/credit score (0-100)."""
    farmer_id: str
    total_score: float  # 0-100
    supply_consistency: float  # 0-30
    quality_metrics: float  # 0-25
    transaction_history: float  # 0-20
    financial_behavior: float  # 0-15
    operational_transparency: float  # 0-10
    calculation_date: datetime
    score_change: float  # change from previous score


@dataclass
class Transaction:
    """Farmer transaction record."""
    transaction_id: str
    farmer_id: str
    fpo_id: str
    quantity: float
    crop_type: str
    quality_grade: str
    moisture: float
    price: float
    timestamp: datetime
    ledger_image_url: Optional[str] = None
    sync_status: SyncStatus = SyncStatus.SYNCED


@dataclass
class Farmer:
    """Farmer entity."""
    farmer_id: str
    name: str
    phone: str
    fpo_id: str
    gps_coords: Tuple[float, float]
    preferred_language: str
    join_date: date


@dataclass
class FPO:
    """Farmer Producer Organization entity."""
    fpo_id: str
    name: str
    location: str
    manager_contact: str
    created_date: date
    member_count: int


@dataclass
class AuditTrail:
    """Audit trail record for data operations."""
    audit_id: str
    entity_type: str  # 'Farmer', 'Transaction', 'FPO', etc.
    entity_id: str
    operation: str  # 'create', 'update', 'delete'
    timestamp: datetime
    user_id: str
    changed_fields: Dict[str, any]  # field_name -> new_value
    previous_values: Optional[Dict[str, any]] = None

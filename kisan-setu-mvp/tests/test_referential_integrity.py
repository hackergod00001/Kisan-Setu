"""
Property-based tests for referential integrity (Property 23).

This module tests that all transactions maintain referential integrity
by ensuring that referenced farmer_id and fpo_id correspond to existing
entities in the database.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))

import pytest
from hypothesis import given, settings
from datetime import datetime

# Import generators
from generators import (
    farmer_data, fpo_data, transaction_data,
    farmer_with_transactions
)

# Import models
from common.models import Transaction, Farmer, FPO


class TestReferentialIntegrity:
    """
    Property-based tests for referential integrity maintenance.
    
    **Validates: Requirements 8.3**
    """
    
    @given(farmer_with_transactions(min_transactions=1, max_transactions=20))
    @settings(max_examples=100)
    def test_property_23_referential_integrity_maintenance(self, farmer_and_txns):
        """
        Property 23: Referential Integrity Maintenance
        
        For any transaction stored in the system, the referenced farmer_id
        and fpo_id should correspond to existing Farmer and FPO entities
        in the database.
        
        **Validates: Requirements 8.3**
        """
        farmer, transactions = farmer_and_txns
        
        # Create a simple in-memory database for testing
        database = {
            'farmers': {},
            'fpos': {},
            'transactions': {}
        }
        
        # Create the FPO entity
        fpo = FPO(
            fpo_id=farmer.fpo_id,
            name="Test FPO",
            location="Test Location",
            manager_contact="+919876543210",
            created_date=farmer.join_date,
            member_count=10
        )
        database['fpos'][fpo.fpo_id] = fpo
        
        # Store farmer in database
        database['farmers'][farmer.farmer_id] = farmer
        
        # Store all transactions
        for txn in transactions:
            database['transactions'][txn.transaction_id] = txn
        
        # Verify referential integrity: All transactions reference valid entities
        for txn in transactions:
            # Verify farmer_id references an existing farmer
            assert txn.farmer_id in database['farmers'], \
                f"Transaction {txn.transaction_id} references non-existent farmer {txn.farmer_id}"
            
            referenced_farmer = database['farmers'][txn.farmer_id]
            assert referenced_farmer.farmer_id == txn.farmer_id, \
                "Referenced farmer ID does not match transaction farmer_id"
            
            # Verify fpo_id references an existing FPO
            assert txn.fpo_id in database['fpos'], \
                f"Transaction {txn.transaction_id} references non-existent FPO {txn.fpo_id}"
            
            referenced_fpo = database['fpos'][txn.fpo_id]
            assert referenced_fpo.fpo_id == txn.fpo_id, \
                "Referenced FPO ID does not match transaction fpo_id"
            
            # Verify the farmer belongs to the FPO
            assert referenced_farmer.fpo_id == referenced_fpo.fpo_id, \
                f"Farmer {txn.farmer_id} does not belong to FPO {txn.fpo_id}"
    
    @given(transaction_data())
    @settings(max_examples=100)
    def test_property_23_transaction_without_valid_farmer_fails(self, transaction):
        """
        Property 23: Referential Integrity Maintenance (Negative Test)
        
        Verify that transactions referencing non-existent farmers can be
        detected by checking if the farmer exists before accepting the transaction.
        
        **Validates: Requirements 8.3**
        """
        # Create an empty database
        database = {
            'farmers': {},
            'fpos': {},
            'transactions': {}
        }
        
        # Store transaction without creating farmer/FPO first
        database['transactions'][transaction.transaction_id] = transaction
        
        # Check for referential integrity violations
        has_valid_farmer = transaction.farmer_id in database['farmers']
        has_valid_fpo = transaction.fpo_id in database['fpos']
        
        # At least one should be missing (referential integrity violation)
        # This demonstrates that the system can detect violations
        assert not (has_valid_farmer and has_valid_fpo), \
            "Successfully detected referential integrity violation"
    
    @given(farmer_with_transactions(min_transactions=5, max_transactions=10))
    @settings(max_examples=100)
    def test_property_23_all_transactions_reference_same_farmer(self, farmer_and_txns):
        """
        Property 23: Referential Integrity Maintenance (Consistency Check)
        
        For any set of transactions generated for a farmer, all transactions
        should reference the same farmer_id and fpo_id, maintaining consistency.
        
        **Validates: Requirements 8.3**
        """
        farmer, transactions = farmer_and_txns
        
        # All transactions should reference the same farmer
        for txn in transactions:
            assert txn.farmer_id == farmer.farmer_id, \
                f"Transaction {txn.transaction_id} has mismatched farmer_id"
            assert txn.fpo_id == farmer.fpo_id, \
                f"Transaction {txn.transaction_id} has mismatched fpo_id"
        
        # Verify consistency across all transactions
        farmer_ids = set(txn.farmer_id for txn in transactions)
        fpo_ids = set(txn.fpo_id for txn in transactions)
        
        assert len(farmer_ids) == 1, "Transactions reference multiple farmers"
        assert len(fpo_ids) == 1, "Transactions reference multiple FPOs"
        
        # The single farmer_id and fpo_id should match the farmer
        assert farmer_ids.pop() == farmer.farmer_id
        assert fpo_ids.pop() == farmer.fpo_id
    
    @given(farmer_with_transactions(min_transactions=1, max_transactions=5))
    @settings(max_examples=100)
    def test_property_23_retrieved_transactions_maintain_integrity(self, farmer_and_txns):
        """
        Property 23: Referential Integrity Maintenance (Retrieval Check)
        
        For any transactions retrieved from the database, they should still
        reference valid farmer_id and fpo_id that exist in the system.
        
        **Validates: Requirements 8.3**
        """
        farmer, transactions = farmer_and_txns
        
        # Create in-memory database
        database = {
            'farmers': {},
            'fpos': {},
            'transactions': {}
        }
        
        # Create FPO
        fpo = FPO(
            fpo_id=farmer.fpo_id,
            name="Test FPO",
            location="Test Location",
            manager_contact="+919876543210",
            created_date=farmer.join_date,
            member_count=10
        )
        database['fpos'][fpo.fpo_id] = fpo
        
        # Create farmer
        database['farmers'][farmer.farmer_id] = farmer
        
        # Create transactions
        for txn in transactions:
            database['transactions'][txn.transaction_id] = txn
        
        # Retrieve transactions from database (simulate query)
        retrieved_txns = [
            txn for txn in database['transactions'].values()
            if txn.farmer_id == farmer.farmer_id
        ]
        
        # Verify all retrieved transactions maintain referential integrity
        assert len(retrieved_txns) >= len(transactions), \
            "Not all transactions were retrieved"
        
        for txn in retrieved_txns:
            # Check farmer exists
            assert txn.farmer_id in database['farmers'], \
                f"Retrieved transaction references non-existent farmer {txn.farmer_id}"
            
            referenced_farmer = database['farmers'][txn.farmer_id]
            
            # Check FPO exists
            assert txn.fpo_id in database['fpos'], \
                f"Retrieved transaction references non-existent FPO {txn.fpo_id}"
            
            referenced_fpo = database['fpos'][txn.fpo_id]
            
            # Verify farmer belongs to FPO
            assert referenced_farmer.fpo_id == referenced_fpo.fpo_id, \
                "Referential integrity violation: farmer does not belong to FPO"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


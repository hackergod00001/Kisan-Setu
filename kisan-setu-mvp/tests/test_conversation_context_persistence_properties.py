"""
Property-Based Tests for Conversation Context Persistence

Tests Property 21: Conversation Context Persistence
For any multi-turn conversation, the context (previous messages, user preferences,
ongoing tasks) must be persisted in DynamoDB and retrievable for subsequent
interactions within the same session.

**Validates: Requirements 7.4**

Uses Hypothesis framework with minimum 100 iterations.
"""

import pytest
import sys
import os
import importlib
import importlib.util
from unittest.mock import Mock, patch, MagicMock
from hypothesis import given, settings, strategies as st
from datetime import datetime, timedelta
from decimal import Decimal

# Add lambda directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda', 'orchestrator'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))

# Load orchestrator module directly to avoid namespace package conflicts
_orch_path = os.path.join(os.path.dirname(__file__), '..', 'lambda', 'orchestrator', 'orchestrator.py')
_orch_spec = importlib.util.spec_from_file_location('_orchestrator_ctx', _orch_path)
_orch_mod = importlib.util.module_from_spec(_orch_spec)
_orch_spec.loader.exec_module(_orch_mod)
BedrockOrchestrator = _orch_mod.BedrockOrchestrator
Message = _orch_mod.Message
ConversationContext = _orch_mod.ConversationContext

# Import test data generators
from generators import (
    uuid_string, language_code, indian_phone_number
)


# ============================================================================
# Property 21: Conversation Context Persistence
# ============================================================================

@given(
    sender_id=indian_phone_number(),
    message_content=st.text(min_size=1, max_size=500),
    language=language_code(),
    message_id=uuid_string()
)
@settings(max_examples=100, deadline=None)
def test_property_21_message_persistence(sender_id, message_content, language, message_id):
    """
    **Property 21: Conversation Context Persistence (Message Persistence)**
    **Validates: Requirements 7.4**
    
    For any message added to a conversation, retrieving the conversation history
    should include that message with its original content, timestamp, and metadata.
    
    This property verifies that:
    1. Messages are stored in DynamoDB with correct structure
    2. Messages can be retrieved with all original fields intact
    3. Message content is not modified during storage/retrieval
    """
    # Create mock DynamoDB table
    mock_table = Mock()
    mock_table.query.return_value = {'Items': []}
    mock_table.put_item.return_value = {}
    
    # Create orchestrator with mock table
    orchestrator = BedrockOrchestrator()
    orchestrator.table = mock_table
    
    # Create message
    message = Message(
        message_id=message_id,
        sender_id=sender_id,
        content=message_content,
        timestamp=datetime.utcnow().isoformat(),
        language=language,
        message_type='text'
    )
    
    # Generate conversation ID
    conversation_id = f"CONV#{sender_id}#{datetime.utcnow().strftime('%Y%m%d')}"
    
    # Maintain context (stores message)
    context = orchestrator.maintain_context(conversation_id, message)
    
    # Verify put_item was called to store the message
    assert mock_table.put_item.called, \
        "Message should be stored in DynamoDB"
    
    # Extract stored item
    call_kwargs = mock_table.put_item.call_args[1]
    stored_item = call_kwargs['Item']
    
    # Property: Message content is preserved
    assert stored_item['content'] == message_content, \
        f"Message content should be preserved: expected '{message_content}', got '{stored_item['content']}'"
    
    # Property: Message metadata is preserved
    assert stored_item['sender_id'] == sender_id, \
        f"Sender ID should be preserved: expected '{sender_id}', got '{stored_item['sender_id']}'"
    
    assert stored_item['language'] == language, \
        f"Language should be preserved: expected '{language}', got '{stored_item['language']}'"
    
    assert stored_item['message_type'] == 'text', \
        f"Message type should be preserved: expected 'text', got '{stored_item['message_type']}'"
    
    # Property: Message has correct DynamoDB key structure
    assert stored_item['PK'] == conversation_id, \
        f"Partition key should be conversation ID: expected '{conversation_id}', got '{stored_item['PK']}'"
    
    assert stored_item['SK'].startswith('MSG#'), \
        f"Sort key should start with 'MSG#': got '{stored_item['SK']}'"
    
    # Property: Message has timestamp
    assert 'timestamp' in stored_item, \
        "Stored message should have timestamp"
    
    assert stored_item['timestamp'] == message.timestamp, \
        f"Timestamp should be preserved: expected '{message.timestamp}', got '{stored_item['timestamp']}'"


@given(
    sender_id=indian_phone_number(),
    num_messages=st.integers(min_value=2, max_value=20),
    language=language_code()
)
@settings(max_examples=100, deadline=None)
def test_property_21_multi_turn_context_retrieval(sender_id, num_messages, language):
    """
    **Property 21: Conversation Context Persistence (Multi-Turn Retrieval)**
    **Validates: Requirements 7.4**
    
    For any multi-turn conversation, retrieving the context should return all
    messages in chronological order with complete metadata.
    
    This verifies that conversation history is maintained across multiple turns.
    """
    # Create mock DynamoDB table
    mock_table = Mock()
    
    # Generate conversation ID
    conversation_id = f"CONV#{sender_id}#{datetime.utcnow().strftime('%Y%m%d')}"
    
    # Create historical messages
    base_time = datetime.utcnow()
    historical_messages = []
    
    for i in range(num_messages):
        msg_time = base_time + timedelta(seconds=i)
        historical_messages.append({
            'PK': conversation_id,
            'SK': f"MSG#{msg_time.isoformat()}",
            'message_id': f"msg_{i}",
            'sender_id': sender_id,
            'content': f"Message {i}",
            'timestamp': msg_time.isoformat(),
            'language': language,
            'message_type': 'text'
        })
    
    # Mock query to return historical messages
    mock_table.query.return_value = {'Items': historical_messages}
    mock_table.put_item.return_value = {}
    
    # Create orchestrator with mock table
    orchestrator = BedrockOrchestrator()
    orchestrator.table = mock_table
    
    # Create new message
    new_message = Message(
        message_id=f"msg_{num_messages}",
        sender_id=sender_id,
        content=f"Message {num_messages}",
        timestamp=(base_time + timedelta(seconds=num_messages)).isoformat(),
        language=language,
        message_type='text'
    )
    
    # Maintain context
    context = orchestrator.maintain_context(conversation_id, new_message)
    
    # Property: Context contains conversation ID
    assert context.conversation_id == conversation_id, \
        f"Context should have correct conversation ID: expected '{conversation_id}', got '{context.conversation_id}'"
    
    # Property: Context contains farmer ID
    assert context.farmer_id == sender_id, \
        f"Context should have correct farmer ID: expected '{sender_id}', got '{context.farmer_id}'"
    
    # Property: Context contains historical messages
    assert len(context.history) == num_messages, \
        f"Context should contain {num_messages} historical messages, got {len(context.history)}"
    
    # Property: Historical messages are preserved
    for i, msg in enumerate(context.history):
        assert msg['content'] == f"Message {i}", \
            f"Message {i} content should be preserved"
        assert msg['sender_id'] == sender_id, \
            f"Message {i} sender_id should be preserved"
        assert msg['language'] == language, \
            f"Message {i} language should be preserved"
    
    # Property: Context state contains language preference
    assert context.state.get('language') == language, \
        f"Context state should preserve language preference: expected '{language}', got '{context.state.get('language')}'"
    
    # Property: New message was stored
    assert mock_table.put_item.called, \
        "New message should be stored in DynamoDB"


@given(
    sender_id=indian_phone_number(),
    message_content=st.text(min_size=1, max_size=500),
    language=language_code(),
    message_id=uuid_string()
)
@settings(max_examples=100, deadline=None)
def test_property_21_context_state_persistence(sender_id, message_content, language, message_id):
    """
    **Property 21: Conversation Context Persistence (State Persistence)**
    **Validates: Requirements 7.4**
    
    For any conversation, the context state (user preferences, ongoing tasks)
    should be persisted and retrievable across interactions.
    
    This verifies that conversation state is maintained beyond just message history.
    """
    # Create mock DynamoDB table
    mock_table = Mock()
    mock_table.query.return_value = {'Items': []}
    mock_table.put_item.return_value = {}
    
    # Create orchestrator with mock table
    orchestrator = BedrockOrchestrator()
    orchestrator.table = mock_table
    
    # Create message
    message = Message(
        message_id=message_id,
        sender_id=sender_id,
        content=message_content,
        timestamp=datetime.utcnow().isoformat(),
        language=language,
        message_type='text'
    )
    
    # Generate conversation ID
    conversation_id = f"CONV#{sender_id}#{datetime.utcnow().strftime('%Y%m%d')}"
    
    # Maintain context
    context = orchestrator.maintain_context(conversation_id, message)
    
    # Property: Context state exists
    assert context.state is not None, \
        "Context should have state object"
    
    # Property: Context state contains language preference
    assert 'language' in context.state, \
        "Context state should contain language preference"
    
    assert context.state['language'] == language, \
        f"Context state language should match message language: expected '{language}', got '{context.state['language']}'"
    
    # Property: Context state contains last message time
    assert 'last_message_time' in context.state, \
        "Context state should contain last message time"
    
    assert context.state['last_message_time'] == message.timestamp, \
        f"Context state should track last message time: expected '{message.timestamp}', got '{context.state['last_message_time']}'"
    
    # Property: Context has last_updated timestamp
    assert context.last_updated is not None, \
        "Context should have last_updated timestamp"
    
    # Verify last_updated is a valid ISO timestamp
    try:
        datetime.fromisoformat(context.last_updated)
    except ValueError:
        pytest.fail(f"Context last_updated should be valid ISO timestamp: got '{context.last_updated}'")


@given(
    sender_id=indian_phone_number(),
    num_turns=st.integers(min_value=3, max_value=10),
    language=language_code()
)
@settings(max_examples=100, deadline=None)
def test_property_21_conversation_continuity(sender_id, num_turns, language):
    """
    **Property 21: Conversation Context Persistence (Conversation Continuity)**
    **Validates: Requirements 7.4**
    
    For any multi-turn conversation, each turn should be able to retrieve
    the context from previous turns, ensuring continuity.
    
    This verifies that conversation context persists across multiple interactions.
    """
    # Create mock DynamoDB table
    mock_table = Mock()
    
    # Generate conversation ID
    conversation_id = f"CONV#{sender_id}#{datetime.utcnow().strftime('%Y%m%d')}"
    
    # Create orchestrator with mock table
    orchestrator = BedrockOrchestrator()
    orchestrator.table = mock_table
    
    # Simulate multiple conversation turns
    all_messages = []
    base_time = datetime.utcnow()
    
    for turn in range(num_turns):
        # Mock query to return all previous messages
        mock_table.query.return_value = {'Items': all_messages.copy()}
        mock_table.put_item.return_value = {}
        
        # Create message for this turn
        message = Message(
            message_id=f"msg_{turn}",
            sender_id=sender_id,
            content=f"Turn {turn} message",
            timestamp=(base_time + timedelta(seconds=turn)).isoformat(),
            language=language,
            message_type='text'
        )
        
        # Maintain context
        context = orchestrator.maintain_context(conversation_id, message)
        
        # Property: Context contains all previous messages
        assert len(context.history) == turn, \
            f"Turn {turn} should have {turn} previous messages in history, got {len(context.history)}"
        
        # Property: Context conversation ID is consistent
        assert context.conversation_id == conversation_id, \
            f"Conversation ID should be consistent across turns: expected '{conversation_id}', got '{context.conversation_id}'"
        
        # Property: Context farmer ID is consistent
        assert context.farmer_id == sender_id, \
            f"Farmer ID should be consistent across turns: expected '{sender_id}', got '{context.farmer_id}'"
        
        # Add stored message to all_messages for next turn
        stored_message = {
            'PK': conversation_id,
            'SK': f"MSG#{message.timestamp}",
            'message_id': message.message_id,
            'sender_id': sender_id,
            'content': message.content,
            'timestamp': message.timestamp,
            'language': language,
            'message_type': 'text'
        }
        all_messages.append(stored_message)
    
    # Property: All turns were stored
    assert mock_table.put_item.call_count == num_turns, \
        f"All {num_turns} turns should be stored, got {mock_table.put_item.call_count} calls"


@given(
    sender_id=indian_phone_number(),
    message_content=st.text(min_size=1, max_size=500),
    language=language_code(),
    message_id=uuid_string()
)
@settings(max_examples=100, deadline=None)
def test_property_21_message_metadata_completeness(sender_id, message_content, language, message_id):
    """
    **Property 21: Conversation Context Persistence (Metadata Completeness)**
    **Validates: Requirements 7.4**
    
    For any message stored in conversation context, all required metadata fields
    should be present and correctly formatted.
    
    This verifies that message metadata is complete and well-formed.
    """
    # Create mock DynamoDB table
    mock_table = Mock()
    mock_table.query.return_value = {'Items': []}
    mock_table.put_item.return_value = {}
    
    # Create orchestrator with mock table
    orchestrator = BedrockOrchestrator()
    orchestrator.table = mock_table
    
    # Create message
    timestamp = datetime.utcnow().isoformat()
    
    message = Message(
        message_id=message_id,
        sender_id=sender_id,
        content=message_content,
        timestamp=timestamp,
        language=language,
        message_type='text'
    )
    
    # Generate conversation ID
    conversation_id = f"CONV#{sender_id}#{datetime.utcnow().strftime('%Y%m%d')}"
    
    # Maintain context
    context = orchestrator.maintain_context(conversation_id, message)
    
    # Verify put_item was called
    assert mock_table.put_item.called, \
        "Message should be stored in DynamoDB"
    
    # Extract stored item
    call_kwargs = mock_table.put_item.call_args[1]
    stored_item = call_kwargs['Item']
    
    # Property: All required fields are present
    required_fields = ['PK', 'SK', 'message_id', 'sender_id', 'content', 'timestamp', 'language', 'message_type']
    
    for field in required_fields:
        assert field in stored_item, \
            f"Stored message should have required field '{field}'"
    
    # Property: Field values match original message
    assert stored_item['message_id'] == message_id, \
        f"Message ID should match: expected '{message_id}', got '{stored_item['message_id']}'"
    
    assert stored_item['sender_id'] == sender_id, \
        f"Sender ID should match: expected '{sender_id}', got '{stored_item['sender_id']}'"
    
    assert stored_item['content'] == message_content, \
        f"Content should match: expected '{message_content}', got '{stored_item['content']}'"
    
    assert stored_item['timestamp'] == timestamp, \
        f"Timestamp should match: expected '{timestamp}', got '{stored_item['timestamp']}'"
    
    assert stored_item['language'] == language, \
        f"Language should match: expected '{language}', got '{stored_item['language']}'"
    
    assert stored_item['message_type'] == 'text', \
        f"Message type should match: expected 'text', got '{stored_item['message_type']}'"


@given(
    sender_id=indian_phone_number(),
    language=language_code(),
    message_id=uuid_string()
)
@settings(max_examples=100, deadline=None)
def test_property_21_empty_history_handling(sender_id, language, message_id):
    """
    **Property 21: Conversation Context Persistence (Empty History Handling)**
    **Validates: Requirements 7.4**
    
    For any new conversation with no history, the context should be created
    with an empty history list and appropriate initial state.
    
    This verifies that new conversations are handled correctly.
    """
    # Create mock DynamoDB table
    mock_table = Mock()
    # Return empty history for new conversation
    mock_table.query.return_value = {'Items': []}
    mock_table.put_item.return_value = {}
    
    # Create orchestrator with mock table
    orchestrator = BedrockOrchestrator()
    orchestrator.table = mock_table
    
    # Create first message
    message = Message(
        message_id=message_id,
        sender_id=sender_id,
        content="First message",
        timestamp=datetime.utcnow().isoformat(),
        language=language,
        message_type='text'
    )
    
    # Generate conversation ID
    conversation_id = f"CONV#{sender_id}#{datetime.utcnow().strftime('%Y%m%d')}"
    
    # Maintain context
    context = orchestrator.maintain_context(conversation_id, message)
    
    # Property: Context is created for new conversation
    assert context is not None, \
        "Context should be created for new conversation"
    
    # Property: History is empty for new conversation
    assert len(context.history) == 0, \
        f"New conversation should have empty history, got {len(context.history)} messages"
    
    # Property: Context has correct conversation ID
    assert context.conversation_id == conversation_id, \
        f"Context should have correct conversation ID: expected '{conversation_id}', got '{context.conversation_id}'"
    
    # Property: Context has correct farmer ID
    assert context.farmer_id == sender_id, \
        f"Context should have correct farmer ID: expected '{sender_id}', got '{context.farmer_id}'"
    
    # Property: Context state is initialized
    assert context.state is not None, \
        "Context state should be initialized for new conversation"
    
    assert context.state.get('language') == language, \
        f"Context state should have language preference: expected '{language}', got '{context.state.get('language')}'"
    
    # Property: New message is stored
    assert mock_table.put_item.called, \
        "First message should be stored in DynamoDB"


@given(
    sender_id=indian_phone_number(),
    message_content=st.text(min_size=1, max_size=500),
    language=language_code(),
    message_id=uuid_string()
)
@settings(max_examples=100, deadline=None)
def test_property_21_context_error_handling(sender_id, message_content, language, message_id):
    """
    **Property 21: Conversation Context Persistence (Error Handling)**
    **Validates: Requirements 7.4**
    
    For any conversation, if DynamoDB operations fail, the system should
    return a minimal valid context rather than crashing.
    
    This verifies graceful error handling in context persistence.
    """
    # Create mock DynamoDB table that raises exceptions
    mock_table = Mock()
    mock_table.query.side_effect = Exception("DynamoDB query failed")
    mock_table.put_item.side_effect = Exception("DynamoDB put_item failed")
    
    # Create orchestrator with mock table
    orchestrator = BedrockOrchestrator()
    orchestrator.table = mock_table
    
    # Create message
    message = Message(
        message_id=message_id,
        sender_id=sender_id,
        content=message_content,
        timestamp=datetime.utcnow().isoformat(),
        language=language,
        message_type='text'
    )
    
    # Generate conversation ID
    conversation_id = f"CONV#{sender_id}#{datetime.utcnow().strftime('%Y%m%d')}"
    
    # Maintain context (should not raise exception)
    context = orchestrator.maintain_context(conversation_id, message)
    
    # Property: Context is returned even on error
    assert context is not None, \
        "Context should be returned even when DynamoDB operations fail"
    
    # Property: Context has minimal valid structure
    assert context.conversation_id == conversation_id, \
        "Context should have conversation ID even on error"
    
    assert context.farmer_id == sender_id, \
        "Context should have farmer ID even on error"
    
    assert context.history is not None, \
        "Context should have history (even if empty) on error"
    
    assert context.state is not None, \
        "Context should have state on error"
    
    assert context.state.get('language') == language, \
        "Context state should have language preference even on error"


# ============================================================================
# Edge Cases
# ============================================================================

def test_edge_case_very_long_message():
    """
    Test that very long messages are stored and retrieved correctly.
    """
    # Create mock DynamoDB table
    mock_table = Mock()
    mock_table.query.return_value = {'Items': []}
    mock_table.put_item.return_value = {}
    
    # Create orchestrator with mock table
    orchestrator = BedrockOrchestrator()
    orchestrator.table = mock_table
    
    # Create very long message (10KB)
    long_content = "A" * 10000
    
    message = Message(
        message_id="test_id",
        sender_id="+919876543210",
        content=long_content,
        timestamp=datetime.utcnow().isoformat(),
        language='hi-IN',
        message_type='text'
    )
    
    conversation_id = "CONV#+919876543210#20240101"
    
    # Maintain context
    context = orchestrator.maintain_context(conversation_id, message)
    
    # Verify message was stored
    assert mock_table.put_item.called
    
    # Extract stored item
    call_kwargs = mock_table.put_item.call_args[1]
    stored_item = call_kwargs['Item']
    
    # Verify content is preserved
    assert stored_item['content'] == long_content, \
        "Very long message content should be preserved"


def test_edge_case_special_characters_in_message():
    """
    Test that messages with special characters are stored correctly.
    """
    # Create mock DynamoDB table
    mock_table = Mock()
    mock_table.query.return_value = {'Items': []}
    mock_table.put_item.return_value = {}
    
    # Create orchestrator with mock table
    orchestrator = BedrockOrchestrator()
    orchestrator.table = mock_table
    
    # Create message with special characters
    special_content = "Hello! @#$%^&*() नमस्ते 你好 مرحبا"
    
    message = Message(
        message_id="test_id",
        sender_id="+919876543210",
        content=special_content,
        timestamp=datetime.utcnow().isoformat(),
        language='hi-IN',
        message_type='text'
    )
    
    conversation_id = "CONV#+919876543210#20240101"
    
    # Maintain context
    context = orchestrator.maintain_context(conversation_id, message)
    
    # Verify message was stored
    assert mock_table.put_item.called
    
    # Extract stored item
    call_kwargs = mock_table.put_item.call_args[1]
    stored_item = call_kwargs['Item']
    
    # Verify content with special characters is preserved
    assert stored_item['content'] == special_content, \
        "Message with special characters should be preserved"


def test_edge_case_concurrent_messages():
    """
    Test that messages with same timestamp are handled correctly.
    """
    # Create mock DynamoDB table
    mock_table = Mock()
    mock_table.query.return_value = {'Items': []}
    mock_table.put_item.return_value = {}
    
    # Create orchestrator with mock table
    orchestrator = BedrockOrchestrator()
    orchestrator.table = mock_table
    
    # Create two messages with same timestamp
    timestamp = datetime.utcnow().isoformat()
    conversation_id = "CONV#+919876543210#20240101"
    
    message1 = Message(
        message_id="msg1",
        sender_id="+919876543210",
        content="Message 1",
        timestamp=timestamp,
        language='hi-IN',
        message_type='text'
    )
    
    message2 = Message(
        message_id="msg2",
        sender_id="+919876543210",
        content="Message 2",
        timestamp=timestamp,
        language='hi-IN',
        message_type='text'
    )
    
    # Store both messages
    orchestrator.maintain_context(conversation_id, message1)
    orchestrator.maintain_context(conversation_id, message2)
    
    # Verify both messages were stored
    assert mock_table.put_item.call_count == 2, \
        "Both messages should be stored even with same timestamp"

"""
Tests for per-sender rate limiting in the Router Lambda.

Validates Requirements 2.9 (rate limiting) and 3.9 (normal rate messages unaffected).
"""

import pytest
import json
import os
import sys
import time
from unittest.mock import patch, MagicMock
from decimal import Decimal

# Ensure lambda path is available
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))

from router.router import (
    check_rate_limit,
    RATE_LIMIT_MAX_MESSAGES,
    RATE_LIMIT_WINDOW_SECONDS,
)


# ---------------------------------------------------------------------------
# 2.5.1  DynamoDB-based rate limit check function
# ---------------------------------------------------------------------------

class TestCheckRateLimit:
    """Validates: Requirement 2.9 — per-sender rate limiting (10 msg/min)."""

    @patch('router.router.table')
    def test_first_message_allowed(self, mock_table):
        """First message from a sender should always be allowed."""
        mock_table.update_item.return_value = {
            'Attributes': {'msg_count': Decimal('1')}
        }
        is_allowed, msg = check_rate_limit('+919876543210')
        assert is_allowed is True
        assert msg is None

    @patch('router.router.table')
    def test_message_at_limit_allowed(self, mock_table):
        """The 10th message (exactly at limit) should be allowed."""
        mock_table.update_item.return_value = {
            'Attributes': {'msg_count': Decimal('10')}
        }
        is_allowed, msg = check_rate_limit('+919876543210')
        assert is_allowed is True
        assert msg is None

    @patch('router.router.table')
    def test_message_over_limit_rejected(self, mock_table):
        """The 11th message (over limit) should be rejected."""
        mock_table.update_item.return_value = {
            'Attributes': {'msg_count': Decimal('11')}
        }
        is_allowed, msg = check_rate_limit('+919876543210')
        assert is_allowed is False
        assert msg is not None
        assert 'wait' in msg.lower()

    @patch('router.router.table')
    def test_dynamo_error_fails_open(self, mock_table):
        """If DynamoDB call fails, message should be allowed (fail open)."""
        mock_table.update_item.side_effect = Exception('DynamoDB timeout')
        is_allowed, msg = check_rate_limit('+919876543210')
        assert is_allowed is True
        assert msg is None

    @patch('router.router.table')
    def test_uses_atomic_counter(self, mock_table):
        """Verify the update_item call uses ADD for atomic increment."""
        mock_table.update_item.return_value = {
            'Attributes': {'msg_count': Decimal('1')}
        }
        check_rate_limit('+919876543210')

        call_kwargs = mock_table.update_item.call_args[1]
        assert 'ADD msg_count' in call_kwargs['UpdateExpression']
        assert call_kwargs['ExpressionAttributeValues'][':inc'] == 1
        assert call_kwargs['ReturnValues'] == 'ALL_NEW'

    @patch('router.router.table')
    def test_key_includes_sender(self, mock_table):
        """Verify the DynamoDB key is scoped to the sender phone number."""
        mock_table.update_item.return_value = {
            'Attributes': {'msg_count': Decimal('1')}
        }
        check_rate_limit('+919876543210')

        call_kwargs = mock_table.update_item.call_args[1]
        pk = call_kwargs['Key']['PK']
        assert pk == 'RATELIMIT#+919876543210'

    @patch('router.router.table')
    def test_ttl_is_set(self, mock_table):
        """Verify TTL attribute is set for automatic cleanup."""
        mock_table.update_item.return_value = {
            'Attributes': {'msg_count': Decimal('1')}
        }
        check_rate_limit('+919876543210')

        call_kwargs = mock_table.update_item.call_args[1]
        assert '#ttl' in call_kwargs['ExpressionAttributeNames']
        ttl_val = call_kwargs['ExpressionAttributeValues'][':ttl']
        # TTL should be in the future
        assert ttl_val > time.time()

    @patch('router.router.table')
    def test_different_senders_independent(self, mock_table):
        """Different senders should have independent rate limit keys."""
        mock_table.update_item.return_value = {
            'Attributes': {'msg_count': Decimal('1')}
        }

        check_rate_limit('+919876543210')
        pk1 = mock_table.update_item.call_args[1]['Key']['PK']

        check_rate_limit('+919876543211')
        pk2 = mock_table.update_item.call_args[1]['Key']['PK']

        assert pk1 != pk2
        assert '+919876543210' in pk1
        assert '+919876543211' in pk2


# ---------------------------------------------------------------------------
# 2.5.2  Integration: rate limit in handle_meta_message()
# ---------------------------------------------------------------------------

class TestHandleMetaMessageRateLimiting:
    """Validates: Requirement 2.9 — rate limit integrated into message handling."""

    def _make_meta_body(self, sender='+919876543210', msg_id='msg_001', msg_type='text', text='Hello'):
        """Helper to build a Meta WhatsApp webhook body."""
        message = {
            'type': msg_type,
            'from': sender,
            'id': msg_id,
        }
        if msg_type == 'text':
            message['text'] = {'body': text}
        elif msg_type == 'image':
            message['image'] = {'id': 'img_001', 'mime_type': 'image/jpeg'}
        return {
            'entry': [{
                'changes': [{
                    'value': {
                        'messages': [message]
                    }
                }]
            }]
        }

    @patch('router.router.check_rate_limit', return_value=(False, 'Please wait a moment.'))
    @patch('router.router.table')
    def test_rate_limited_message_returns_friendly_message(self, mock_table, mock_rate):
        """When rate limit exceeded, return friendly 'please wait' response."""
        from router.router import handle_meta_message

        # Mock dedup check to pass
        mock_table.get_item.return_value = {}
        mock_table.put_item.return_value = {}

        body = self._make_meta_body()
        result = handle_meta_message(body, 'req_001')

        assert result['statusCode'] == 200
        resp_body = json.loads(result['body'])
        assert resp_body['status'] == 'rate_limited'
        assert 'wait' in resp_body['message'].lower()

    @patch('router.router.check_rate_limit', return_value=(True, None))
    @patch('router.router.lambda_client')
    @patch('router.router.update_message_status')
    @patch('router.router.store_message_metadata')
    @patch('router.router.detect_user_language', return_value='en')
    @patch('router.router.detect_language_from_text', return_value='en')
    @patch('router.router.table')
    def test_normal_rate_message_processed(self, mock_table, mock_lang_text,
                                            mock_lang, mock_store, mock_status,
                                            mock_lambda, mock_rate):
        """Validates: Requirement 3.9 — normal rate messages processed without delay."""
        from router.router import handle_meta_message

        mock_table.get_item.return_value = {}
        mock_table.put_item.return_value = {}
        mock_lambda.invoke.return_value = {'StatusCode': 202}

        body = self._make_meta_body(text='What is the price of onions?')
        result = handle_meta_message(body, 'req_002')

        assert result['statusCode'] == 200
        resp_body = json.loads(result['body'])
        assert resp_body['status'] == 'processing'

    @patch('router.router.check_rate_limit', return_value=(False, 'Please wait.'))
    @patch('router.router.table')
    def test_rate_limit_blocks_all_message_types(self, mock_table, mock_rate):
        """Rate limiting applies to all message types, not just text."""
        from router.router import handle_meta_message

        mock_table.get_item.return_value = {}
        mock_table.put_item.return_value = {}

        # Test with image message
        body = self._make_meta_body(msg_type='image')
        result = handle_meta_message(body, 'req_003')

        assert result['statusCode'] == 200
        resp_body = json.loads(result['body'])
        assert resp_body['status'] == 'rate_limited'

    @patch('router.router.check_rate_limit', return_value=(False, 'Please wait.'))
    @patch('router.router.lambda_client')
    @patch('router.router.table')
    def test_rate_limit_prevents_lambda_invocation(self, mock_table, mock_lambda, mock_rate):
        """When rate limited, downstream Lambda should NOT be invoked."""
        from router.router import handle_meta_message

        mock_table.get_item.return_value = {}
        mock_table.put_item.return_value = {}

        body = self._make_meta_body()
        handle_meta_message(body, 'req_004')

        mock_lambda.invoke.assert_not_called()

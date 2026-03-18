"""
Bug Condition Exploration Tests for Code Audit Bugfixes.

These tests encode the EXPECTED behavior (what the code SHOULD look like
after the fix). On UNFIXED code they MUST FAIL — failure confirms the
bugs exist.

Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9
"""

import re
from pathlib import Path

import pytest

# Resolve project root relative to this test file
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Test 1a — Stale Model Names in orchestrator.py
# Bug: Three locations reference "Opus 4.6", "Sonnet 4", or "Haiku 4.5"
#       instead of the actual Nova model names.
# Validates: Requirements 1.1, 1.2, 1.3
# ---------------------------------------------------------------------------

class TestStaleModelNames:
    """Assert orchestrator.py does NOT contain stale model name references."""

    @pytest.fixture(autouse=True)
    def _load_source(self):
        path = _PROJECT_ROOT / "lambda" / "orchestrator" / "orchestrator.py"
        self.source = path.read_text()

    def test_no_opus_46(self):
        """Opus 4.6 should not appear anywhere in orchestrator.py."""
        assert "Opus 4.6" not in self.source, (
            "Found stale model name 'Opus 4.6' in orchestrator.py"
        )

    def test_no_standalone_sonnet_4(self):
        """'Sonnet 4' (standalone, not 'Sonnet v2') should not appear."""
        # Match "Sonnet 4" but NOT "Sonnet v2" or "Sonnet 3.5"
        matches = re.findall(r"Sonnet 4(?!\.\d)", self.source)
        assert len(matches) == 0, (
            f"Found {len(matches)} stale 'Sonnet 4' reference(s) in orchestrator.py"
        )

    def test_no_haiku_45(self):
        """Haiku 4.5 should not appear anywhere in orchestrator.py."""
        assert "Haiku 4.5" not in self.source, (
            "Found stale model name 'Haiku 4.5' in orchestrator.py"
        )


# ---------------------------------------------------------------------------
# Test 1b — Dead Code in satellite_analyzer.py
# Bug: INDIA_BOUNDS is defined but never referenced.
# Validates: Requirements 1.4
# ---------------------------------------------------------------------------

class TestDeadCode:
    """Assert satellite_analyzer.py does NOT define INDIA_BOUNDS."""

    def test_no_india_bounds_definition(self):
        path = _PROJECT_ROOT / "lambda" / "satellite" / "satellite_analyzer.py"
        source = path.read_text()
        assert "INDIA_BOUNDS" not in source, (
            "Found dead code: INDIA_BOUNDS is defined in satellite_analyzer.py "
            "but never referenced"
        )


# ---------------------------------------------------------------------------
# Test 1c — Missing Env Vars in infrastructure_stack.py
# Bug: VoiceHandler, MessageRouter, SatelliteAnalyzer, KnowledgeBase
#      are missing KMS_KEY_ID; KnowledgeBase also missing DYNAMODB_TABLE.
# Validates: Requirements 1.5, 1.6, 1.7, 1.8
# ---------------------------------------------------------------------------

class TestMissingEnvVars:
    """Assert all required Lambda env vars are present in CDK stack."""

    @pytest.fixture(autouse=True)
    def _load_source(self):
        path = _PROJECT_ROOT / "infrastructure_stack.py"
        self.source = path.read_text()

    def _extract_lambda_env_block(self, construct_id: str) -> str:
        """Extract the environment dict block for a given Lambda construct."""
        # Find the Lambda construct by its CDK construct ID string
        construct_pattern = rf'self,\s*"{construct_id}"'
        m = re.search(construct_pattern, self.source)
        assert m is not None, (
            f"Could not find Lambda construct '{construct_id}'"
        )

        # Search for 'environment={' after the construct match
        env_start = self.source.find("environment={", m.end())
        if env_start == -1:
            env_start = self.source.find("environment = {", m.end())
        assert env_start != -1, (
            f"Could not find environment block for Lambda '{construct_id}'"
        )

        # Find the opening brace and use brace-counting
        brace_pos = self.source.index("{", env_start)
        depth = 0
        i = brace_pos
        while i < len(self.source):
            if self.source[i] == "{":
                depth += 1
            elif self.source[i] == "}":
                depth -= 1
                if depth == 0:
                    return self.source[brace_pos + 1 : i]
            i += 1

        raise AssertionError(
            f"Unbalanced braces in environment block for '{construct_id}'"
        )

    def test_voice_handler_has_kms_key_id(self):
        """VoiceHandler Lambda must have KMS_KEY_ID env var."""
        env_block = self._extract_lambda_env_block("VoiceHandler")
        assert "KMS_KEY_ID" in env_block, (
            "VoiceHandler Lambda is missing KMS_KEY_ID environment variable"
        )

    def test_message_router_has_kms_key_id(self):
        """MessageRouter Lambda must have KMS_KEY_ID env var."""
        env_block = self._extract_lambda_env_block("MessageRouter")
        assert "KMS_KEY_ID" in env_block, (
            "MessageRouter Lambda is missing KMS_KEY_ID environment variable"
        )

    def test_satellite_analyzer_has_kms_key_id(self):
        """SatelliteAnalyzer Lambda must have KMS_KEY_ID env var."""
        env_block = self._extract_lambda_env_block("SatelliteAnalyzer")
        assert "KMS_KEY_ID" in env_block, (
            "SatelliteAnalyzer Lambda is missing KMS_KEY_ID environment variable"
        )

    def test_knowledge_base_has_kms_key_id(self):
        """KnowledgeBase Lambda must have KMS_KEY_ID env var."""
        env_block = self._extract_lambda_env_block("KnowledgeBase")
        assert "KMS_KEY_ID" in env_block, (
            "KnowledgeBase Lambda is missing KMS_KEY_ID environment variable"
        )

    def test_knowledge_base_has_dynamodb_table(self):
        """KnowledgeBase Lambda must have DYNAMODB_TABLE env var."""
        env_block = self._extract_lambda_env_block("KnowledgeBase")
        assert "DYNAMODB_TABLE" in env_block, (
            "KnowledgeBase Lambda is missing DYNAMODB_TABLE environment variable"
        )


# ---------------------------------------------------------------------------
# Test 1d — Unused GraphQL Arg in schema.graphql
# Bug: updateTransaction has a standalone transactionId: ID! arg that
#      the resolver ignores.
# Validates: Requirements 1.9
# ---------------------------------------------------------------------------

class TestUnusedGraphQLArg:
    """Assert updateTransaction does NOT have standalone transactionId arg."""

    def test_no_standalone_transaction_id_arg(self):
        path = _PROJECT_ROOT / "schema.graphql"
        source = path.read_text()
        # Match the updateTransaction mutation signature
        match = re.search(
            r"updateTransaction\s*\(([^)]*)\)",
            source,
        )
        assert match is not None, "Could not find updateTransaction mutation"
        args = match.group(1)
        # Check that transactionId: ID! is NOT a standalone argument
        has_standalone_txn_id = re.search(
            r"\btransactionId\s*:\s*ID!", args
        )
        assert has_standalone_txn_id is None, (
            "updateTransaction mutation has unused standalone 'transactionId: ID!' "
            f"argument. Current signature args: {args.strip()}"
        )

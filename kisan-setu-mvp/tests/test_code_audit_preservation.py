"""
Preservation Property Tests for Code Audit Bugfixes.

These tests capture the BASELINE behavior of non-buggy code.
They MUST PASS on unfixed code and CONTINUE to pass after the fix,
ensuring no regressions are introduced.

Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7
"""

import re
from pathlib import Path

import pytest

# Resolve project root relative to this test file
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Test 2a — Model Routing Preservation
# Verify MODEL_TIERS, SIMPLE_PATTERNS, COMPLEX_PATTERNS are unchanged.
# Validates: Requirements 3.1
# ---------------------------------------------------------------------------

class TestModelRoutingPreservation:
    """Assert model routing configuration in orchestrator.py is unchanged."""

    @pytest.fixture(autouse=True)
    def _load_source(self):
        path = _PROJECT_ROOT / "lambda" / "orchestrator" / "orchestrator.py"
        self.source = path.read_text()

    def test_model_tiers_has_primary_key(self):
        """MODEL_TIERS dict must contain 'primary' key."""
        assert "'primary'" in self.source, "MODEL_TIERS missing 'primary' key"

    def test_model_tiers_has_default_key(self):
        """MODEL_TIERS dict must contain 'default' key."""
        assert "'default'" in self.source, "MODEL_TIERS missing 'default' key"

    def test_model_tiers_has_secondary_key(self):
        """MODEL_TIERS dict must contain 'secondary' key."""
        assert "'secondary'" in self.source, "MODEL_TIERS missing 'secondary' key"

    def test_primary_model_id(self):
        """Primary tier model_id must be apac.amazon.nova-pro-v1:0."""
        assert "apac.amazon.nova-pro-v1:0" in self.source, (
            "Primary model_id 'apac.amazon.nova-pro-v1:0' not found"
        )

    def test_secondary_model_id(self):
        """Secondary tier model_id must be apac.amazon.nova-lite-v1:0."""
        assert "apac.amazon.nova-lite-v1:0" in self.source, (
            "Secondary model_id 'apac.amazon.nova-lite-v1:0' not found"
        )

    def test_simple_patterns_has_six_or_more(self):
        """SIMPLE_PATTERNS list must have at least 6 patterns."""
        matches = re.findall(r"SIMPLE_PATTERNS\s*=\s*\[(.*?)\]", self.source, re.DOTALL)
        assert len(matches) == 1, "Could not find SIMPLE_PATTERNS list"
        # Count the regex pattern strings inside the list
        patterns = re.findall(r"r'[^']*'|r\"[^\"]*\"", matches[0])
        assert len(patterns) >= 6, (
            f"SIMPLE_PATTERNS has {len(patterns)} patterns, expected at least 6"
        )

    def test_complex_patterns_exists(self):
        """COMPLEX_PATTERNS list must exist."""
        assert "COMPLEX_PATTERNS" in self.source, "COMPLEX_PATTERNS not found"


# ---------------------------------------------------------------------------
# Test 2b — Satellite Runtime Preservation
# Verify satellite_analyzer.py retains all runtime classes and functions.
# Validates: Requirements 3.2
# ---------------------------------------------------------------------------

class TestSatelliteRuntimePreservation:
    """Assert satellite_analyzer.py runtime code is unchanged."""

    @pytest.fixture(autouse=True)
    def _load_source(self):
        path = _PROJECT_ROOT / "lambda" / "satellite" / "satellite_analyzer.py"
        self.source = path.read_text()

    def test_satellite_image_class_exists(self):
        """SatelliteImage dataclass must exist."""
        assert "class SatelliteImage" in self.source

    def test_ndvi_result_class_exists(self):
        """NDVIResult dataclass must exist."""
        assert "class NDVIResult" in self.source

    def test_satellite_analyzer_class_exists(self):
        """SatelliteAnalyzer class must exist."""
        assert "class SatelliteAnalyzer" in self.source

    def test_handler_function_exists(self):
        """Top-level handler function must exist."""
        assert re.search(r"^def handler\b", self.source, re.MULTILINE), (
            "def handler function not found in satellite_analyzer.py"
        )

    def test_calculate_ndvi_method_exists(self):
        """calculate_ndvi method must exist."""
        assert "def calculate_ndvi" in self.source

    def test_predict_yield_method_exists(self):
        """predict_yield method must exist."""
        assert "def predict_yield" in self.source

    def test_get_satellite_imagery_method_exists(self):
        """get_satellite_imagery method must exist."""
        assert "def get_satellite_imagery" in self.source


# ---------------------------------------------------------------------------
# Test 2c — Existing Lambda Env Vars Preservation
# Verify Lambdas that already have KMS_KEY_ID keep it, and Router keeps
# all its existing env vars.
# Validates: Requirements 3.3, 3.4, 3.7
# ---------------------------------------------------------------------------

class TestExistingLambdaEnvVarsPreservation:
    """Assert existing Lambda env vars are unchanged."""

    @pytest.fixture(autouse=True)
    def _load_source(self):
        path = _PROJECT_ROOT / "infrastructure_stack.py"
        self.source = path.read_text()

    def _extract_lambda_env_block(self, construct_id: str) -> str:
        """Extract the environment dict block for a given Lambda construct.

        Uses brace-counting to handle nested f-string braces like
        ``f"kisan-setu-raw-{account_id}"``.
        """
        # Find the construct, then locate the 'environment={' that follows
        construct_pattern = rf'self,\s*"{construct_id}"'
        m = re.search(construct_pattern, self.source)
        assert m is not None, f"Could not find Lambda construct '{construct_id}'"

        # Search for 'environment={' after the construct match
        env_start = self.source.find("environment={", m.end())
        if env_start == -1:
            env_start = self.source.find("environment = {", m.end())
        assert env_start != -1, (
            f"Could not find environment block for Lambda '{construct_id}'"
        )

        # Find the opening brace
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

    # --- Lambdas that already have KMS_KEY_ID ---

    def test_document_processor_has_kms_key_id(self):
        """DocumentProcessor Lambda must retain KMS_KEY_ID."""
        env_block = self._extract_lambda_env_block("DocumentProcessor")
        assert "KMS_KEY_ID" in env_block

    def test_credit_calculator_has_kms_key_id(self):
        """CreditCalculator Lambda must retain KMS_KEY_ID."""
        env_block = self._extract_lambda_env_block("CreditCalculator")
        assert "KMS_KEY_ID" in env_block

    def test_bedrock_orchestrator_has_kms_key_id(self):
        """BedrockOrchestrator Lambda must retain KMS_KEY_ID."""
        env_block = self._extract_lambda_env_block("BedrockOrchestrator")
        assert "KMS_KEY_ID" in env_block

    def test_sync_handler_has_kms_key_id(self):
        """SyncHandler Lambda must retain KMS_KEY_ID."""
        env_block = self._extract_lambda_env_block("SyncHandler")
        assert "KMS_KEY_ID" in env_block

    # --- MessageRouter existing env vars ---

    def test_message_router_has_dynamodb_table(self):
        """MessageRouter Lambda must retain DYNAMODB_TABLE."""
        env_block = self._extract_lambda_env_block("MessageRouter")
        assert "DYNAMODB_TABLE" in env_block

    def test_message_router_has_region(self):
        """MessageRouter Lambda must retain REGION."""
        env_block = self._extract_lambda_env_block("MessageRouter")
        assert "REGION" in env_block

    def test_message_router_has_whatsapp_secret_name(self):
        """MessageRouter Lambda must retain WHATSAPP_SECRET_NAME."""
        env_block = self._extract_lambda_env_block("MessageRouter")
        assert "WHATSAPP_SECRET_NAME" in env_block

    def test_message_router_has_webhook_verify_token(self):
        """MessageRouter Lambda must retain WEBHOOK_VERIFY_TOKEN."""
        env_block = self._extract_lambda_env_block("MessageRouter")
        assert "WEBHOOK_VERIFY_TOKEN" in env_block

    def test_message_router_has_sns_alert_topic_arn(self):
        """MessageRouter Lambda must retain SNS_ALERT_TOPIC_ARN."""
        env_block = self._extract_lambda_env_block("MessageRouter")
        assert "SNS_ALERT_TOPIC_ARN" in env_block

    # --- VoiceHandler existing env vars ---

    def test_voice_handler_has_dynamodb_table(self):
        """VoiceHandler Lambda must retain DYNAMODB_TABLE."""
        env_block = self._extract_lambda_env_block("VoiceHandler")
        assert "DYNAMODB_TABLE" in env_block

    def test_voice_handler_has_region(self):
        """VoiceHandler Lambda must retain REGION."""
        env_block = self._extract_lambda_env_block("VoiceHandler")
        assert "REGION" in env_block

    def test_voice_handler_has_sns_alert_topic_arn(self):
        """VoiceHandler Lambda must retain SNS_ALERT_TOPIC_ARN."""
        env_block = self._extract_lambda_env_block("VoiceHandler")
        assert "SNS_ALERT_TOPIC_ARN" in env_block

    def test_voice_handler_has_whatsapp_secret_name(self):
        """VoiceHandler Lambda must retain WHATSAPP_SECRET_NAME."""
        env_block = self._extract_lambda_env_block("VoiceHandler")
        assert "WHATSAPP_SECRET_NAME" in env_block


# ---------------------------------------------------------------------------
# Test 2d — Other Mutations Preservation
# Verify createTransaction and syncOfflineTransactions are unchanged.
# Validates: Requirements 3.5
# ---------------------------------------------------------------------------

class TestOtherMutationsPreservation:
    """Assert other GraphQL mutations are unchanged."""

    @pytest.fixture(autouse=True)
    def _load_source(self):
        path = _PROJECT_ROOT / "schema.graphql"
        self.source = path.read_text()

    def test_create_transaction_mutation_exists(self):
        """createTransaction(input: TransactionInput!): Transaction must exist."""
        pattern = r"createTransaction\s*\(\s*input\s*:\s*TransactionInput!\s*\)\s*:\s*Transaction"
        assert re.search(pattern, self.source), (
            "createTransaction(input: TransactionInput!): Transaction not found"
        )

    def test_sync_offline_transactions_mutation_exists(self):
        """syncOfflineTransactions(transactions: [TransactionInput!]!): SyncResult must exist."""
        pattern = r"syncOfflineTransactions\s*\(\s*transactions\s*:\s*\[TransactionInput!\]!\s*\)\s*:\s*SyncResult"
        assert re.search(pattern, self.source), (
            "syncOfflineTransactions(transactions: [TransactionInput!]!): SyncResult not found"
        )


# ---------------------------------------------------------------------------
# Test 2e — Resolver Preservation
# Verify UpdateTransactionResolver uses input.farmerId and input.timestamp.
# Validates: Requirements 3.6
# ---------------------------------------------------------------------------

class TestResolverPreservation:
    """Assert UpdateTransactionResolver key structure is unchanged."""

    @pytest.fixture(autouse=True)
    def _load_source(self):
        path = _PROJECT_ROOT / "infrastructure_stack.py"
        self.source = path.read_text()

    def test_resolver_uses_input_farmer_id(self):
        """UpdateTransactionResolver must use $ctx.args.input.farmerId as PK."""
        assert "$ctx.args.input.farmerId" in self.source, (
            "UpdateTransactionResolver does not use $ctx.args.input.farmerId"
        )

    def test_resolver_uses_input_timestamp(self):
        """UpdateTransactionResolver must use $ctx.args.input.timestamp as SK."""
        assert "$ctx.args.input.timestamp" in self.source, (
            "UpdateTransactionResolver does not use $ctx.args.input.timestamp"
        )

"""
End-to-end hackathon verification tests for Kisan-Setu MVP.

Validates Requirements 8.1–8.6: text query processing, satellite mock NDVI,
dashboard URL output, ledger image processing, voice message processing,
and credit score calculation.
"""

import sys
import os
import json
from unittest.mock import MagicMock

import pytest

# Ensure lambda modules are importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))


# ---------------------------------------------------------------------------
# Requirement 8.1: Text query processing through orchestrator with LLM adapter
# ---------------------------------------------------------------------------

class TestTextQueryProcessing:
    """Verify text query processing through orchestrator with LLM adapter."""

    def test_llm_adapter_converse_returns_response(self):
        """LLM adapter should call bedrock_runtime.converse and return text."""
        from common.llm_adapter import LLMAdapter

        mock_bedrock = MagicMock()
        mock_bedrock.converse.return_value = {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"text": "Wheat is best sown in November."}],
                }
            },
            "usage": {"inputTokens": 10, "outputTokens": 20},
            "stopReason": "end_turn",
        }

        adapter = LLMAdapter(bedrock_runtime=mock_bedrock)
        result = adapter.converse("When should I sow wheat?")

        # converse() returns (text, input_tokens, output_tokens)
        assert result[0] == "Wheat is best sown in November."
        mock_bedrock.converse.assert_called_once()

    def test_llm_adapter_converse_with_system_prompt(self):
        """LLM adapter should include system prompt when provided."""
        from common.llm_adapter import LLMAdapter

        mock_bedrock = MagicMock()
        mock_bedrock.converse.return_value = {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"text": "Use drip irrigation."}],
                }
            },
            "usage": {"inputTokens": 15, "outputTokens": 25},
            "stopReason": "end_turn",
        }

        adapter = LLMAdapter(bedrock_runtime=mock_bedrock)
        result = adapter.converse(
            "How to save water?",
            system_prompt="You are an agricultural assistant.",
        )

        # converse() returns (text, input_tokens, output_tokens)
        assert result[0] == "Use drip irrigation."
        call_kwargs = mock_bedrock.converse.call_args[1]
        assert "system" in call_kwargs
        assert call_kwargs["system"] == [{"text": "You are an agricultural assistant."}]


# ---------------------------------------------------------------------------
# Requirement 8.5: Satellite mock NDVI data retrieval
# ---------------------------------------------------------------------------

class TestSatelliteMockNDVI:
    """Verify satellite mock returns correct NDVI data for test coordinates."""

    def test_maharashtra_coordinates_return_valid_data(self):
        """NDVI data for Maharashtra coords (19.75, 75.71) has all fields and valid range."""
        from satellite.satellite_mock import SatelliteMock

        mock = SatelliteMock()
        result = mock.get_ndvi_data(19.75, 75.71)

        assert result is not None
        assert 0.3 <= result["ndvi_value"] <= 0.9
        assert "crop_type" in result
        assert "maturity_stage" in result
        assert "health_status" in result
        assert "estimated_yield" in result
        assert result["coordinates"] == {"latitude": 19.75, "longitude": 75.71}
        assert result["data_source"] == "mock"

    def test_out_of_bounds_coordinates_return_none(self):
        """Coordinates outside Maharashtra should return None."""
        from satellite.satellite_mock import SatelliteMock

        mock = SatelliteMock()

        # North of Maharashtra bounds
        assert mock.get_ndvi_data(40.0, 75.0) is None
        # West of Maharashtra bounds
        assert mock.get_ndvi_data(19.0, 60.0) is None
        # South of Maharashtra bounds
        assert mock.get_ndvi_data(10.0, 75.0) is None


# ---------------------------------------------------------------------------
# Requirement 8.6: Dashboard URL output in CDK template
# ---------------------------------------------------------------------------

class TestDashboardCDKTemplate:
    """Verify CDK template contains DashboardURL output and Bedrock Converse permission."""

    def test_cdk_template_has_dashboard_url_output(self):
        """Synthesized CDK template should contain a DashboardURL output."""
        try:
            import aws_cdk as cdk
            from aws_cdk import assertions
        except ImportError:
            pytest.skip("aws_cdk not installed — run in CDK environment")

        # Import stack relative to the project root
        project_root = os.path.join(os.path.dirname(__file__), "..")
        sys.path.insert(0, project_root)
        from infrastructure_stack import KisanSetuMVPStack

        app = cdk.App()
        stack = KisanSetuMVPStack(app, "TestStack")
        template = assertions.Template.from_stack(stack)

        template.has_output("DashboardURL", {"Value": assertions.Match.any_value()})

    def test_cdk_template_has_bedrock_converse_permission(self):
        """Synthesized CDK template IAM policy should include bedrock:Converse."""
        try:
            import aws_cdk as cdk
            from aws_cdk import assertions
        except ImportError:
            pytest.skip("aws_cdk not installed — run in CDK environment")

        project_root = os.path.join(os.path.dirname(__file__), "..")
        sys.path.insert(0, project_root)
        from infrastructure_stack import KisanSetuMVPStack

        app = cdk.App()
        stack = KisanSetuMVPStack(app, "TestStack")
        template = assertions.Template.from_stack(stack)

        template.has_resource_properties(
            "AWS::IAM::Policy",
            assertions.Match.object_like({
                "PolicyDocument": assertions.Match.object_like({
                    "Statement": assertions.Match.array_with([
                        assertions.Match.object_like({
                            "Action": assertions.Match.array_with(["bedrock:Converse"]),
                            "Effect": "Allow",
                        })
                    ])
                })
            }),
        )


# ---------------------------------------------------------------------------
# Requirements 8.2, 8.3, 8.4: Stubs for manual verification
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="Requires deployed AWS services")
class TestLedgerImageProcessing:
    """Stub: ledger image processing requires Textract and deployed Lambda."""

    def test_ledger_image_extraction(self):
        """Process an uploaded ledger image and return extracted structured data."""
        pass


@pytest.mark.skip(reason="Requires deployed AWS services")
class TestVoiceMessageProcessing:
    """Stub: voice message processing requires Transcribe/Polly and deployed Lambda."""

    def test_voice_message_round_trip(self):
        """Process a voice message and return a voice response."""
        pass


@pytest.mark.skip(reason="Requires deployed AWS services")
class TestCreditScoreCalculation:
    """Stub: credit score calculation requires DynamoDB data and deployed Lambda."""

    def test_credit_score_for_test_farmer(self):
        """Calculate and return a credit score for a test farmer."""
        pass
